# Модуль локального HTTPS/TLS для AirShare PC (v1.3.5):
# 1. Чистый Python-генератор корневого сертификата (AirShare PC Local Root CA) и серверного SAN-сертификата (IP + *.sslip.io) без внешних утилит.
# 2. Автоматическое определение протокола HTTP / HTTPS на одном и том же порту через socket.MSG_PEEK.
# 3. Генерация одноразового Windows-установщика (Enable_AirShare_HTTPS.bat) и сертификата (AirShare_Root_CA.crt) для работы HTTPS без предупреждений браузера.

import base64
import datetime
import hashlib
import ipaddress
import json
import logging
import os
import secrets
import ssl
import threading

from config import SETTINGS_DIR
from utils import get_sslip_domain

logger = logging.getLogger("airshare.tls")

_tls_lock = threading.Lock()
_cached_ssl_ctx = None
_cached_ssl_ip = None
_cached_ca_pem = None


def _der_len(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(b)]) + b


def _der_tlv(tag: int, content: bytes) -> bytes:
    return bytes([tag]) + _der_len(len(content)) + content


def _der_seq(*items: bytes) -> bytes:
    return _der_tlv(0x30, b"".join(items))


def _der_set(*items: bytes) -> bytes:
    return _der_tlv(0x31, b"".join(items))


def _der_int(n: int) -> bytes:
    if n == 0:
        return _der_tlv(0x02, b"\x00")
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    if b[0] & 0x80:
        b = b"\x00" + b
    return _der_tlv(0x02, b)


def _der_octets(b: bytes) -> bytes:
    return _der_tlv(0x04, b)


def _der_bitstring(b: bytes) -> bytes:
    return _der_tlv(0x03, b"\x00" + b)


def _der_utf8(s: str) -> bytes:
    return _der_tlv(0x0C, s.encode("utf-8"))


def _der_utctime(dt: datetime.datetime) -> bytes:
    return _der_tlv(0x17, dt.strftime("%y%m%d%H%M%SZ").encode("ascii"))


def _der_oid(oid_tuple: tuple) -> bytes:
    first = 40 * oid_tuple[0] + oid_tuple[1]
    out = bytearray([first])
    for val in oid_tuple[2:]:
        if val == 0:
            out.append(0)
        else:
            buf = bytearray()
            while val > 0:
                buf.append(val & 0x7F)
                val >>= 7
            for i in range(len(buf) - 1, 0, -1):
                out.append(buf[i] | 0x80)
            out.append(buf[0])
    return _der_tlv(0x06, bytes(out))


def _is_probable_prime(n: int, k: int = 12) -> bool:
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53):
        if n == p:
            return True
        if n % p == 0:
            return False
    d = n - 1
    s = 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for _ in range(k):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _gen_prime(bits: int = 1024) -> int:
    while True:
        cand = secrets.randbits(bits) | (1 << (bits - 1)) | 1
        if _is_probable_prime(cand):
            return cand


def _gen_rsa_key(bits: int = 2048) -> dict:
    e = 65537
    half = bits // 2
    while True:
        p = _gen_prime(half)
        q = _gen_prime(half)
        if p != q and (p - 1) % e != 0 and (q - 1) % e != 0:
            break
    n = p * q
    phi = (p - 1) * (q - 1)
    d = pow(e, -1, phi)
    return {
        "n": n,
        "e": e,
        "d": d,
        "p": p,
        "q": q,
        "dp": d % (p - 1),
        "dq": d % (q - 1),
        "qinv": pow(q, -1, p),
    }


def _rsa_priv_der(k: dict) -> bytes:
    return _der_seq(
        _der_int(0),
        _der_int(k["n"]),
        _der_int(k["e"]),
        _der_int(k["d"]),
        _der_int(k["p"]),
        _der_int(k["q"]),
        _der_int(k["dp"]),
        _der_int(k["dq"]),
        _der_int(k["qinv"]),
    )


def _rsa_spki_der(k: dict) -> bytes:
    alg = _der_seq(_der_oid((1, 2, 840, 113549, 1, 1, 1)), b"\x05\x00")
    pub = _der_seq(_der_int(k["n"]), _der_int(k["e"]))
    return _der_seq(alg, _der_bitstring(pub))


def _rsa_sign_sha256(k: dict, data: bytes) -> bytes:
    digest = hashlib.sha256(data).digest()
    digest_info = bytes.fromhex("3031300d060960864801650304020105000420") + digest
    k_len = (k["n"].bit_length() + 7) // 8
    pad_len = k_len - len(digest_info) - 3
    em = b"\x00\x01" + (b"\xff" * pad_len) + b"\x00" + digest_info
    m = int.from_bytes(em, "big")
    s = pow(m, k["d"], k["n"])
    return s.to_bytes(k_len, "big")


def _rdn_name(cn: str, org: str = "AirShare PC") -> bytes:
    return _der_seq(
        _der_set(_der_seq(_der_oid((2, 5, 4, 10)), _der_utf8(org))),
        _der_set(_der_seq(_der_oid((2, 5, 4, 3)), _der_utf8(cn))),
    )


def _to_pem(label: str, der_bytes: bytes) -> str:
    b64 = base64.encodebytes(der_bytes).decode("ascii").replace("\n", "")
    lines = [b64[i : i + 64] for i in range(0, len(b64), 64)]
    return f"-----BEGIN {label}-----\n" + "\n".join(lines) + f"\n-----END {label}-----\n"


def _load_or_create_keys() -> tuple:
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    keystore_file = os.path.join(SETTINGS_DIR, ".airshare_tls_keys.json")
    if os.path.isfile(keystore_file):
        try:
            with open(keystore_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            ca_key = {k: int(v) for k, v in data["ca_key"].items()}
            srv_key = {k: int(v) for k, v in data["srv_key"].items()}
            ca_serial = int(data["ca_serial"])
            return ca_key, srv_key, ca_serial
        except Exception as exc:
            logger.debug("Пересоздаём ключи TLS: %s", exc)

    ca_key = _gen_rsa_key(2048)
    srv_key = _gen_rsa_key(2048)
    ca_serial = secrets.randbits(62) | 1
    try:
        payload = {
            "ca_key": {k: str(v) for k, v in ca_key.items()},
            "srv_key": {k: str(v) for k, v in srv_key.items()},
            "ca_serial": str(ca_serial),
        }
        with open(keystore_file, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except OSError:
        pass
    return ca_key, srv_key, ca_serial


def ensure_tls_context(ip_str: str = "127.0.0.1"):
    global _cached_ssl_ctx, _cached_ssl_ip, _cached_ca_pem
    clean_ip = str(ip_str or "127.0.0.1").strip()
    with _tls_lock:
        if _cached_ssl_ctx is not None and _cached_ssl_ip == clean_ip and _cached_ca_pem:
            return _cached_ssl_ctx, _cached_ca_pem

        try:
            ca_key, srv_key, ca_serial = _load_or_create_keys()
            now = datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
            later = datetime.datetime(2036, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)

            ca_name = _rdn_name("AirShare PC Local Root CA")
            ext_bc_ca = _der_seq(
                _der_oid((2, 5, 29, 19)),
                _der_tlv(0x01, b"\xff"),
                _der_octets(_der_seq(_der_tlv(0x01, b"\xff"))),
            )
            ext_ku_ca = _der_seq(
                _der_oid((2, 5, 29, 15)),
                _der_tlv(0x01, b"\xff"),
                _der_octets(_der_tlv(0x03, b"\x01\x06")),
            )
            ca_tbs = _der_seq(
                _der_tlv(0xA0, _der_int(2)),
                _der_int(ca_serial),
                _der_seq(_der_oid((1, 2, 840, 113549, 1, 1, 11)), b"\x05\x00"),
                ca_name,
                _der_seq(_der_utctime(now), _der_utctime(later)),
                ca_name,
                _rsa_spki_der(ca_key),
                _der_tlv(0xA3, _der_seq(ext_bc_ca, ext_ku_ca)),
            )
            ca_sig = _rsa_sign_sha256(ca_key, ca_tbs)
            ca_cert_der = _der_seq(
                ca_tbs,
                _der_seq(_der_oid((1, 2, 840, 113549, 1, 1, 11)), b"\x05\x00"),
                _der_bitstring(ca_sig),
            )
            ca_pem = _to_pem("CERTIFICATE", ca_cert_der)

            sslip_host = get_sslip_domain(clean_ip)
            san_items = [
                _der_tlv(0x82, sslip_host.encode("ascii")),
                _der_tlv(0x82, b"localhost"),
                _der_tlv(0x87, ipaddress.IPv4Address("127.0.0.1").packed),
            ]
            try:
                ip_packed = ipaddress.IPv4Address(clean_ip).packed
                if clean_ip != "127.0.0.1":
                    san_items.insert(2, _der_tlv(0x87, ip_packed))
            except ValueError:
                pass

            ext_bc_leaf = _der_seq(_der_oid((2, 5, 29, 19)), _der_tlv(0x01, b"\xff"), _der_octets(_der_seq()))
            ext_ku_leaf = _der_seq(
                _der_oid((2, 5, 29, 15)),
                _der_tlv(0x01, b"\xff"),
                _der_octets(_der_tlv(0x03, b"\x05\xa0")),
            )
            ext_eku_leaf = _der_seq(
                _der_oid((2, 5, 29, 37)),
                _der_octets(_der_seq(_der_oid((1, 3, 6, 1, 5, 5, 7, 3, 1)))),
            )
            ext_san = _der_seq(_der_oid((2, 5, 29, 17)), _der_octets(_der_seq(*san_items)))

            srv_serial = int.from_bytes(hashlib.sha256(clean_ip.encode("utf-8")).digest()[:8], "big") | 1
            srv_name = _rdn_name(sslip_host)
            srv_tbs = _der_seq(
                _der_tlv(0xA0, _der_int(2)),
                _der_int(srv_serial),
                _der_seq(_der_oid((1, 2, 840, 113549, 1, 1, 11)), b"\x05\x00"),
                ca_name,
                _der_seq(_der_utctime(now), _der_utctime(later)),
                srv_name,
                _rsa_spki_der(srv_key),
                _der_tlv(0xA3, _der_seq(ext_bc_leaf, ext_ku_leaf, ext_eku_leaf, ext_san)),
            )
            srv_sig = _rsa_sign_sha256(ca_key, srv_tbs)
            srv_cert_der = _der_seq(
                srv_tbs,
                _der_seq(_der_oid((1, 2, 840, 113549, 1, 1, 11)), b"\x05\x00"),
                _der_bitstring(srv_sig),
            )

            cert_chain_path = os.path.join(SETTINGS_DIR, ".airshare_server_chain.pem")
            key_path = os.path.join(SETTINGS_DIR, ".airshare_server_key.pem")
            with open(cert_chain_path, "w", encoding="utf-8") as f:
                f.write(_to_pem("CERTIFICATE", srv_cert_der) + ca_pem)
            with open(key_path, "w", encoding="utf-8") as f:
                f.write(_to_pem("RSA PRIVATE KEY", _rsa_priv_der(srv_key)))

            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(certfile=cert_chain_path, keyfile=key_path)
            _cached_ssl_ctx = ctx
            _cached_ssl_ip = clean_ip
            _cached_ca_pem = ca_pem
            return ctx, ca_pem
        except Exception as exc:
            logger.warning("Не удалось инициализировать TLS-контекст: %s", exc)
            return None, ""


def build_windows_https_installer_bat(ca_pem: str, https_url: str) -> bytes:
    clean_lines = [line.strip() for line in ca_pem.strip().splitlines() if line.strip()]
    echo_cmds = "\r\n".join(f"echo {line}>> \"%CERT_FILE%\"" for line in clean_lines)
    bat = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        "title AirShare PC — Установка доверенного HTTPS сертификата\r\n"
        "set \"CERT_FILE=%TEMP%\\AirShare_Root_CA.crt\"\r\n"
        "if exist \"%CERT_FILE%\" del /f /q \"%CERT_FILE%\"\r\n"
        f"{echo_cmds}\r\n"
        "echo Устанавливаем корневой сертификат AirShare PC в доверенные центры Windows...\r\n"
        "certutil -user -addstore Root \"%CERT_FILE%\"\r\n"
        "del /f /q \"%CERT_FILE%\" 2>nul\r\n"
        f"start \"\" \"{https_url}\"\r\n"
    )
    return bat.encode("utf-8")

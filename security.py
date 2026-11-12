# Модуль безопасности AirShare PC (v1.3.5): уникальные сессионные токены устройств, защита от перебора PIN, Path Traversal, фильтрация .part и проверка целостности SHA-256

import hashlib
import hmac
import logging
import os
import secrets
import threading
import time
import urllib.parse

from config import RATE_LIMIT_BLOCK_SECONDS, RATE_LIMIT_MAX_ATTEMPTS

logger = logging.getLogger("airshare.security")

SANDBOX_EXTENSIONS = frozenset({".html", ".htm", ".svg", ".xhtml", ".js", ".mjs", ".xml"})
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif", ".heic"})
VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v", ".3gp"})

HASH_CHUNK_SIZE = 1024 * 1024


def is_temp_part_file(name: str) -> bool:
    return name.startswith(".airshare_upload_") or name.endswith(".part")


def is_within_storage(real_storage: str, candidate_path: str) -> bool:
    try:
        real_candidate = os.path.realpath(candidate_path)
        return os.path.commonpath([real_storage, real_candidate]) == real_storage
    except ValueError:
        return False


def make_content_disposition(filename: str, disposition: str = "attachment") -> str:
    clean_name = os.path.basename(filename).replace('"', "_").replace("\r", "").replace("\n", "")
    ascii_fallback = clean_name.encode("ascii", "ignore").decode("ascii").strip()
    if not ascii_fallback or ascii_fallback.startswith("."):
        _, ext = os.path.splitext(clean_name)
        ascii_fallback = f"download{ext}"
    utf8_quoted = urllib.parse.quote(clean_name, safe="")
    return f'{disposition}; filename="{ascii_fallback}"; filename*=UTF-8\'\'{utf8_quoted}'


def get_unique_filepath(target_dir: str, filename: str):
    candidate = os.path.realpath(os.path.join(target_dir, filename))
    if not os.path.exists(candidate):
        return candidate, filename
    stem, ext = os.path.splitext(filename)
    counter = 1
    while True:
        new_name = f"{stem} ({counter}){ext}"
        candidate = os.path.realpath(os.path.join(target_dir, new_name))
        if not os.path.exists(candidate):
            return candidate, new_name
        counter += 1


def verify_sha256_digest(actual_hex: str, expected_hex: str) -> bool:
    if not expected_hex:
        return True
    return hmac.compare_digest(
        actual_hex.strip().lower().encode("ascii"),
        expected_hex.strip().lower().encode("ascii"),
    )


def compute_cached_file_sha256(target_file: str, st_stat, cache_dict: dict, lock: threading.Lock) -> str:
    cache_key = (target_file, st_stat.st_mtime_ns, st_stat.st_size)
    with lock:
        cached_digest = cache_dict.get(cache_key)
    if cached_digest:
        return cached_digest

    hasher = hashlib.sha256()
    with open(target_file, "rb") as f:
        while True:
            chunk = f.read(HASH_CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
    digest = hasher.hexdigest()
    with lock:
        if len(cache_dict) > 512:
            cache_dict.clear()
        cache_dict[cache_key] = digest
    return digest


def create_device_session_token(
    session_secret: str,
    device_sessions: dict,
    lock: threading.Lock,
    client_ip: str,
    expected_pwd: str,
) -> str:
    nonce = secrets.token_hex(16)
    msg = f"{client_ip}:{expected_pwd}:{nonce}".encode("utf-8")
    tok = hmac.new(session_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    with lock:
        if len(device_sessions) >= 256:
            oldest_key = next(iter(device_sessions))
            device_sessions.pop(oldest_key, None)
        device_sessions[tok] = {
            "ip": str(client_ip).strip(),
            "pwd": expected_pwd,
            "created": time.monotonic(),
        }
    return tok


def make_legacy_session_token(session_secret: str, expected_pwd: str) -> str:
    msg = f"airshare_session:{expected_pwd}".encode("utf-8")
    return hmac.new(session_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def is_valid_session_cookie(
    tok: str,
    client_ip: str,
    expected_pwd: str,
    session_secret: str,
    device_sessions: dict,
    lock: threading.Lock,
) -> bool:
    if not tok:
        return False
    with lock:
        meta = device_sessions.get(tok)
        if meta is not None:
            if meta.get("ip") == client_ip and hmac.compare_digest(
                str(meta.get("pwd", "")).encode("utf-8"),
                expected_pwd.encode("utf-8"),
            ):
                return True
            return False
    legacy_tok = make_legacy_session_token(session_secret, expected_pwd)
    return hmac.compare_digest(tok.encode("utf-8"), legacy_tok.encode("utf-8"))


def check_ip_rate_limit(client_ip: str, failed_attempts: dict, lock: threading.Lock):
    now = time.monotonic()
    with lock:
        record = failed_attempts.get(client_ip)
        if not record:
            return False, 0
        _count, blocked_until = record
        if blocked_until > now:
            return True, int(blocked_until - now) + 1
        if blocked_until > 0 and blocked_until <= now:
            del failed_attempts[client_ip]
        return False, 0


def register_auth_failure(client_ip: str, failed_attempts: dict, lock: threading.Lock):
    now = time.monotonic()
    with lock:
        count, blocked_until = failed_attempts.get(client_ip, (0, 0.0))
        if blocked_until > 0 and blocked_until <= now:
            count = 0
        count += 1
        if count >= RATE_LIMIT_MAX_ATTEMPTS:
            blocked_until = now + RATE_LIMIT_BLOCK_SECONDS
            logger.warning(
                "IP %s заблокирован на %d сек после %d неудачных попыток входа",
                client_ip,
                RATE_LIMIT_BLOCK_SECONDS,
                count,
            )
        else:
            blocked_until = 0.0
        failed_attempts[client_ip] = (count, blocked_until)


def get_sha256_js() -> str:
    # Чистая JS-реализация SHA-256 (работает по локальному http://192.168..., где WebCrypto API отключён браузером)
    return """
    function sha256Bytes(bytes) {
        const K = new Uint32Array([
            0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
            0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
            0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
            0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
            0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
            0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
            0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
            0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
        ]);
        let h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a;
        let h4 = 0x510e527f, h5 = 0x9b05688c, h6 = 0x1f83d9ab, h7 = 0x5be0cd19;
        const len = bytes.length;
        const bitLenHi = Math.floor((len * 8) / 0x100000000);
        const bitLenLo = (len * 8) >>> 0;
        const padLen = ((len + 9 + 63) & ~63);
        const buf = new Uint8Array(padLen);
        buf.set(bytes);
        buf[len] = 0x80;
        const view = new DataView(buf.buffer);
        view.setUint32(padLen - 8, bitLenHi, false);
        view.setUint32(padLen - 4, bitLenLo, false);
        const W = new Uint32Array(64);
        for (let off = 0; off < padLen; off += 64) {
            for (let i = 0; i < 16; i++) W[i] = view.getUint32(off + i * 4, false);
            for (let i = 16; i < 64; i++) {
                const x = W[i - 15], y = W[i - 2];
                const s0 = ((x >>> 7) | (x << 25)) ^ ((x >>> 18) | (x << 14)) ^ (x >>> 3);
                const s1 = ((y >>> 17) | (y << 15)) ^ ((y >>> 19) | (y << 13)) ^ (y >>> 10);
                W[i] = (W[i - 16] + s0 + W[i - 7] + s1) >>> 0;
            }
            let a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, h = h7;
            for (let i = 0; i < 64; i++) {
                const S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
                const ch = (e & f) ^ (~e & g);
                const t1 = (h + S1 + ch + K[i] + W[i]) >>> 0;
                const S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
                const maj = (a & b) ^ (a & c) ^ (b & c);
                const t2 = (S0 + maj) >>> 0;
                h = g; g = f; f = e; e = (d + t1) >>> 0;
                d = c; c = b; b = a; a = (t1 + t2) >>> 0;
            }
            h0 = (h0 + a) >>> 0; h1 = (h1 + b) >>> 0; h2 = (h2 + c) >>> 0; h3 = (h3 + d) >>> 0;
            h4 = (h4 + e) >>> 0; h5 = (h5 + f) >>> 0; h6 = (h6 + g) >>> 0; h7 = (h7 + h) >>> 0;
        }
        return [h0, h1, h2, h3, h4, h5, h6, h7].map(v => v.toString(16).padStart(8, "0")).join("");
    }

    async function computeFileSha256(file) {
        if (file.size > 64 * 1024 * 1024) return "";
        const ab = await file.arrayBuffer();
        return sha256Bytes(new Uint8Array(ab));
    }

    async function verifyFileHash(quotedName, pillEl) {
        if (!pillEl) return;
        pillEl.innerText = "⏳ SHA-256...";
        try {
            const res = await fetch("?hash=" + quotedName, { credentials: "same-origin" });
            if (!res.ok) throw new Error("HTTP " + res.status);
            const data = await res.json();
            if (data && data.sha256) {
                pillEl.innerText = "✓ " + data.sha256.slice(0, 10) + "…";
                pillEl.title = "SHA-256: " + data.sha256;
                try { navigator.clipboard.writeText(data.sha256); } catch (e) {}
            }
        } catch (e) {
            pillEl.innerText = "⚠️ SHA-256";
        }
    }
    """

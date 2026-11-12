# HTTP-сервер AirShare PC (v1.3.5): маршрутизация GET/POST/HEAD, стриминг Range 206 + sendfile и потоковый ZIP (безопасность в security.py, плеер в player_ui.py, поиск и PWA в pwa_search.py)

import base64
import hashlib
import hmac
import html
import json
import logging
import math
import mimetypes
import os
import secrets
import select
import socket
import threading
import time
import urllib.parse
import zipfile
from email.utils import formatdate
from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO

from config import (
    MAX_CONCURRENT_CONNECTIONS,
    MAX_DIR_ITEMS_PER_PAGE,
    MAX_UPLOAD_SIZE,
    RATE_LIMIT_BLOCK_SECONDS,
    SOCKET_TIMEOUT_SECONDS,
    STORAGE_PATH,
)
from i18n import SUPPORTED_CODES, tr
from player_ui import get_media_modal_html
from pwa_search import search_storage_index, serve_pwa_asset
from security import (
    IMAGE_EXTENSIONS,
    SANDBOX_EXTENSIONS,
    VIDEO_EXTENSIONS,
    check_ip_rate_limit,
    compute_cached_file_sha256,
    create_device_session_token,
    get_unique_filepath,
    is_temp_part_file,
    is_valid_session_cookie,
    is_within_storage,
    make_content_disposition,
    register_auth_failure,
    verify_sha256_digest,
)
from utils import add_recent_ip, format_size, load_settings
from web_ui import (
    get_css,
    get_download_svg,
    get_pin_login_page,
    get_star_script,
    get_theme_script,
    get_top_controls_html,
    get_upload_script,
)

logger = logging.getLogger("airshare.server")

STREAM_CHUNK_SIZE = 1024 * 1024
SOCKET_SEND_BUFFER = 4 * 1024 * 1024


class _ZipStream:
    def __init__(self, wfile):
        self.wfile = wfile
        self.offset = 0

    def seekable(self):
        return False

    def write(self, data):
        self.wfile.write(data)
        self.offset += len(data)
        return len(data)

    def tell(self):
        return self.offset

    def flush(self):
        pass


class ReusableThreadingServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._conn_semaphore = threading.BoundedSemaphore(MAX_CONCURRENT_CONNECTIONS)

    def process_request(self, request, client_address):
        if not self._conn_semaphore.acquire(blocking=False):
            try:
                request.close()
            except OSError:
                pass
            return
        t = threading.Thread(target=self._process_request_guarded, args=(request, client_address), daemon=True)
        t.start()

    def _process_request_guarded(self, request, client_address):
        try:
            try:
                request.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                request.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SOCKET_SEND_BUFFER)
                request.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, SOCKET_SEND_BUFFER)
            except Exception:
                pass
            self.process_request_thread(request, client_address)
        finally:
            self._conn_semaphore.release()


class AirShareHandler(SimpleHTTPRequestHandler):
    timeout = SOCKET_TIMEOUT_SECONDS

    current_password = ""
    default_theme = "dark"
    current_language = "en"
    on_client_connected = None
    on_file_transfer = None
    on_transfer_progress = None
    on_bad_pin_attempt = None

    _auth_lock = threading.Lock()
    _failed_attempts = {}
    _disconnected_ips = set()
    _notified_ips = set()
    _device_sessions = {}
    _session_secret = secrets.token_hex(16)
    _hash_cache = {}
    _search_cache = {"root": "", "ts": 0.0, "entries": []}

    def __init__(self, *args, **kwargs):
        self._pending_auth_cookie = None
        self.real_storage = os.path.realpath(STORAGE_PATH)
        super().__init__(*args, directory=self.real_storage, **kwargs)

    def _get_cb(self, name):
        for cls in type(self).__mro__:
            if name in cls.__dict__:
                val = cls.__dict__[name]
                if isinstance(val, staticmethod):
                    return val.__func__
                return val
        return None

    def end_headers(self):
        if getattr(self, "_pending_auth_cookie", None):
            self.send_header(
                "Set-Cookie",
                f"airshare_auth={self._pending_auth_cookie}; Path=/; Max-Age=86400; HttpOnly; SameSite=Lax",
            )
            self._pending_auth_cookie = None
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    @classmethod
    def reset_rate_limits(cls):
        with cls._auth_lock:
            cls._failed_attempts.clear()
            cls._device_sessions.clear()

    @classmethod
    def set_ip_disconnected(cls, ip_str, disconnected=True):
        clean_ip = str(ip_str).strip()
        with cls._auth_lock:
            if disconnected:
                cls._disconnected_ips.add(clean_ip)
                stale_tokens = [t for t, meta in cls._device_sessions.items() if meta.get("ip") == clean_ip]
                for t in stale_tokens:
                    cls._device_sessions.pop(t, None)
            else:
                cls._disconnected_ips.discard(clean_ip)

    @classmethod
    def is_ip_disconnected(cls, ip_str):
        with cls._auth_lock:
            return str(ip_str).strip() in cls._disconnected_ips

    @classmethod
    def _create_device_session(cls, client_ip, expected_pwd):
        return create_device_session_token(
            cls._session_secret,
            cls._device_sessions,
            cls._auth_lock,
            client_ip,
            expected_pwd,
        )

    def _get_client_ip(self):
        if self.client_address and len(self.client_address) > 0:
            return str(self.client_address[0])
        return "127.0.0.1"

    def _is_ip_blocked(self, client_ip):
        return check_ip_rate_limit(client_ip, self._failed_attempts, self._auth_lock)

    def _record_auth_failure(self, client_ip):
        register_auth_failure(client_ip, self._failed_attempts, self._auth_lock)
        cb = self._get_cb("on_bad_pin_attempt")
        if callable(cb):
            try:
                cb(client_ip)
            except Exception as exc:
                logger.debug("Ошибка уведомления UI о неверном PIN: %s", exc)

    def _clear_auth_failures(self, client_ip):
        with self._auth_lock:
            self._failed_attempts.pop(client_ip, None)

    def _ensure_password_loaded(self):
        pwd = str(self.current_password or "").strip()
        if not pwd:
            pwd = str(load_settings().get("password", "")).strip()
            AirShareHandler.current_password = pwd
        return pwd

    def _evaluate_auth(self):
        expected_pwd = self._ensure_password_loaded()
        client_ip = self._get_client_ip()

        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "pin" in params and params["pin"]:
            cand_pin = str(params["pin"][0]).strip()
            if hmac.compare_digest(cand_pin.encode("utf-8"), expected_pwd.encode("utf-8")):
                return "ok_pin_query"
            return "fail_attempt"

        cookie_hdr = self.headers.get("Cookie", "")
        if cookie_hdr:
            try:
                c = cookies.SimpleCookie()
                c.load(cookie_hdr)
                if "airshare_auth" in c:
                    tok = c["airshare_auth"].value.strip()
                    if is_valid_session_cookie(
                        tok,
                        client_ip,
                        expected_pwd,
                        self._session_secret,
                        self._device_sessions,
                        self._auth_lock,
                    ):
                        return "ok"
            except Exception:
                pass

        header = self.headers.get("Authorization", "")
        if header.startswith("Basic "):
            try:
                raw = base64.b64decode(header[6:]).decode("utf-8")
                _user, sep, pwd = raw.partition(":")
                if sep and hmac.compare_digest(pwd.encode("utf-8"), expected_pwd.encode("utf-8")):
                    return "ok"
            except Exception as exc:
                logger.warning("Ошибка разбора заголовка Authorization: %s", exc)
            return "fail_attempt"

        return "no_creds"

    def is_authenticated(self):
        return self._evaluate_auth() in ("ok", "ok_pin_query")

    def check_auth_or_respond(self):
        client_ip = self._get_client_ip()
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        req_lang = self._get_request_lang(params)

        if self.is_ip_disconnected(client_ip):
            body = f"<h3>{html.escape(tr('web_dev_blocked', req_lang))}</h3>".encode("utf-8")
            self.send_response(403, "Forbidden")
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return False

        blocked, retry_after = self._is_ip_blocked(client_ip)
        if blocked:
            self.send_rate_limit_response(retry_after, lang=req_lang)
            return False

        status = self._evaluate_auth()
        if status == "ok_pin_query":
            self._clear_auth_failures(client_ip)
            expected_pwd = self._ensure_password_loaded()
            tok = self._create_device_session(client_ip, expected_pwd)
            params.pop("pin", None)
            clean_query = urllib.parse.urlencode(params, doseq=True)
            clean_url = parsed.path or "/"
            if clean_query:
                clean_url = f"{clean_url}?{clean_query}"

            if any(k in params for k in ("download", "zip", "download_selected", "files", "upload", "hash")):
                self._pending_auth_cookie = tok
                return True

            self._parse_client_device()
            self.send_response(302, "Found")
            self.send_header(
                "Set-Cookie", f"airshare_auth={tok}; Path=/; Max-Age=86400; HttpOnly; SameSite=Lax"
            )
            self.send_header("Location", clean_url)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return False

        if status == "ok":
            self._clear_auth_failures(client_ip)
            return True

        if status == "fail_attempt":
            self._record_auth_failure(client_ip)
            blocked_now, retry_after = self._is_ip_blocked(client_ip)
            if blocked_now:
                self.send_rate_limit_response(retry_after, lang=req_lang)
            else:
                self.request_auth(is_failed=True)
            return False

        self.request_auth(is_failed=False)
        return False

    def _handle_post_login(self):
        client_ip = self._get_client_ip()
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        req_lang = self._get_request_lang(params)

        if self.is_ip_disconnected(client_ip):
            body = f"<h3>{html.escape(tr('web_dev_blocked', req_lang))}</h3>".encode("utf-8")
            self.send_response(403, "Forbidden")
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        blocked, retry_after = self._is_ip_blocked(client_ip)
        if blocked:
            self.send_rate_limit_response(retry_after, lang=req_lang)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        raw_body = self.rfile.read(min(length, 4096)).decode("utf-8", errors="replace") if length > 0 else ""
        form_data = urllib.parse.parse_qs(raw_body)
        cand_pin = str(form_data.get("pin", [""])[0]).strip()
        next_url = str(form_data.get("next", ["/"])[0]).strip()
        if not next_url.startswith("/") or next_url.startswith("//") or next_url.startswith("/login"):
            next_url = "/"

        expected_pwd = self._ensure_password_loaded()
        if cand_pin and hmac.compare_digest(cand_pin.encode("utf-8"), expected_pwd.encode("utf-8")):
            self._clear_auth_failures(client_ip)
            tok = self._create_device_session(client_ip, expected_pwd)
            self._parse_client_device()
            self.send_response(303, "See Other")
            self.send_header(
                "Set-Cookie", f"airshare_auth={tok}; Path=/; Max-Age=86400; HttpOnly; SameSite=Lax"
            )
            self.send_header("Location", next_url)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        self._record_auth_failure(client_ip)
        blocked_now, retry_after = self._is_ip_blocked(client_ip)
        if blocked_now:
            self.send_rate_limit_response(retry_after, lang=req_lang)
        else:
            self.request_auth(is_failed=True, next_path=next_url)

    def send_rate_limit_response(self, retry_after=RATE_LIMIT_BLOCK_SECONDS, lang=None):
        use_lang = lang or self._get_request_lang()
        msg = tr("web_rate_limit", use_lang, sec=retry_after)
        body = f"<h3>{html.escape(msg)}</h3>".encode("utf-8")
        self.send_response(429, "Too Many Requests")
        self.send_header("Retry-After", str(retry_after))
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def request_auth(self, is_failed=False, next_path=None):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        theme = self._get_request_theme(params)
        lang = self._get_request_lang(params)
        err_msg = tr("toast_bad_pin", lang, ip=self._get_client_ip()) if is_failed else ""
        target_next = next_path or (parsed.path if parsed.path and parsed.path != "/login" else "/")
        page_html = get_pin_login_page(theme=theme, lang=lang, error_msg=err_msg, next_path=target_next)
        body = page_html.encode("utf-8")
        self.send_response(401)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        if "lang" in params and params["lang"]:
            self.send_header("Set-Cookie", f"airshare_lang={lang}; Path=/; Max-Age=31536000; SameSite=Lax")
        self.end_headers()
        self.wfile.write(body)

    def _parse_client_device(self, fast_skip_if_known=False):
        try:
            client_ip = self._get_client_ip()
            if client_ip in ("127.0.0.1", "::1"):
                return
            if fast_skip_if_known:
                with self._auth_lock:
                    if client_ip in self._notified_ips:
                        return
            ua = self.headers.get("User-Agent", "")
            if "Windows NT 10.0" in ua or "Windows NT 11.0" in ua:
                device_title, os_badge = "Desktop PC", "Windows 11"
            elif "Windows" in ua:
                device_title, os_badge = "Desktop PC", "Windows"
            elif "Macintosh" in ua or "Mac OS X" in ua:
                device_title, os_badge = "MacBook", "macOS"
            elif "Android" in ua:
                device_title, os_badge = "Smartphone", "Android"
            elif "iPhone" in ua or "iPad" in ua:
                device_title, os_badge = "iPhone / iPad", "iOS"
            elif "Linux" in ua:
                device_title, os_badge = "Desktop PC", "Linux"
            else:
                device_title, os_badge = "Connected Device", client_ip

            entry = f"{device_title} ({os_badge}) • {client_ip}"
            add_recent_ip(entry)
            is_first_notify = False
            with self._auth_lock:
                if client_ip not in self._notified_ips:
                    self._notified_ips.add(client_ip)
                    is_first_notify = True
            cb = self._get_cb("on_client_connected")
            if callable(cb):
                cb(device_title, os_badge, client_ip, is_first_notify)
        except Exception as exc:
            logger.warning("Не удалось определить устройство клиента: %s", exc)

    def _notify_progress(self, filename, transferred_bytes, total_bytes, direction="upload"):
        try:
            cb = self._get_cb("on_transfer_progress")
            if callable(cb):
                cb(filename, transferred_bytes, total_bytes, direction)
        except Exception as exc:
            logger.debug("Ошибка уведомления UI о прогрессе файла: %s", exc)

    def _notify_transfer(self, filename, size_bytes, direction="done"):
        try:
            cb = self._get_cb("on_file_transfer")
            if callable(cb):
                cb(filename, format_size(size_bytes), direction)
        except Exception as exc:
            logger.warning("Ошибка уведомления UI о передаче файла: %s", exc)

    def _is_within_storage(self, candidate_path):
        return is_within_storage(self.real_storage, candidate_path)

    def translate_path(self, path):
        resolved = os.path.realpath(super().translate_path(path))
        if not self._is_within_storage(resolved):
            return self.real_storage
        return resolved

    def _get_request_theme(self, params):
        if "theme" in params and params["theme"]:
            t = params["theme"][0].lower()
            if t in ("light", "dark"):
                return t
        cookie_hdr = self.headers.get("Cookie", "")
        if cookie_hdr:
            try:
                c = cookies.SimpleCookie()
                c.load(cookie_hdr)
                if "airshare_theme" in c:
                    val = c["airshare_theme"].value.lower()
                    if val in ("light", "dark"):
                        return val
            except Exception as exc:
                logger.debug("Не удалось разобрать Cookie темы: %s", exc)
        return self.default_theme if self.default_theme in ("light", "dark") else "dark"

    def _get_request_lang(self, params=None):
        if params and "lang" in params and params["lang"]:
            cand = str(params["lang"][0]).strip().lower()
            if cand in SUPPORTED_CODES:
                return cand
        cookie_hdr = self.headers.get("Cookie", "")
        if cookie_hdr:
            try:
                c = cookies.SimpleCookie()
                c.load(cookie_hdr)
                if "airshare_lang" in c:
                    val = c["airshare_lang"].value.strip().lower()
                    if val in SUPPORTED_CODES:
                        return val
            except Exception as exc:
                logger.debug("Не удалось разобрать Cookie языка: %s", exc)
        return self.current_language if self.current_language in SUPPORTED_CODES else "en"

    def _serve_file_hash(self, current_url_path, target_name):
        rel_dir = urllib.parse.unquote(current_url_path).lstrip("/")
        base_dir = os.path.realpath(os.path.join(self.real_storage, rel_dir))
        clean_target = os.path.basename(target_name)
        target_file = os.path.realpath(os.path.join(base_dir, clean_target))

        if not self._is_within_storage(target_file) or not os.path.isfile(target_file):
            self.send_error(404, "File not found")
            return

        try:
            st = os.stat(target_file)
            digest = compute_cached_file_sha256(target_file, st, self._hash_cache, self._auth_lock)
            payload = json.dumps(
                {"filename": clean_target, "sha256": digest, "size": st.st_size},
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except OSError as exc:
            logger.warning("Ошибка вычисления SHA-256 для %s: %s", clean_target, exc)
            self.send_error(500, "Hash error")

    def do_HEAD(self):
        parsed = urllib.parse.urlparse(self.path)
        if serve_pwa_asset(self, parsed.path):
            return
        if not self.check_auth_or_respond():
            return
        self._parse_client_device(fast_skip_if_known=True)
        params = urllib.parse.parse_qs(parsed.query)
        if "download" in params and params["download"]:
            self.stream_single_file(parsed.path, params["download"][0], as_attachment=True, head_only=True)
            return
        target_path = self.translate_path(parsed.path)
        if os.path.isfile(target_path):
            parent_url = os.path.dirname(urllib.parse.unquote(parsed.path))
            self.stream_single_file(parent_url, os.path.basename(target_path), as_attachment=False, head_only=True)
            return
        super().do_HEAD()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if serve_pwa_asset(self, parsed.path):
            return

        if not self.check_auth_or_respond():
            return

        params = urllib.parse.parse_qs(parsed.query)

        if "hash" in params and params["hash"]:
            self._parse_client_device(fast_skip_if_known=True)
            self._serve_file_hash(parsed.path, params["hash"][0])
            return

        if "q" in params and params.get("ajax") == ["1"]:
            self._parse_client_device(fast_skip_if_known=True)
            results = search_storage_index(
                self.real_storage,
                params["q"][0],
                self.current_language,
                self._search_cache,
                self._auth_lock,
            )
            body = json.dumps({"results": results}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if "download" in params and params["download"]:
            self._parse_client_device(fast_skip_if_known=True)
            self.stream_single_file(parsed.path, params["download"][0], as_attachment=True)
            return

        if "zip" in params and params["zip"]:
            self._parse_client_device(fast_skip_if_known=True)
            self.stream_folder_zip(parsed.path, params["zip"][0])
            return

        if "download_selected" in params or "files" in params:
            selected = params.get("files", [])
            if selected:
                self._parse_client_device(fast_skip_if_known=True)
                self.download_selected_files(selected)
                return

        target_path = self.translate_path(parsed.path)
        if os.path.isfile(target_path):
            self._parse_client_device(fast_skip_if_known=True)
            parent_url = os.path.dirname(urllib.parse.unquote(parsed.path))
            self.stream_single_file(parent_url, os.path.basename(target_path), as_attachment=False)
            return

        self._parse_client_device(fast_skip_if_known=False)
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/login":
            self._handle_post_login()
            return

        if not self.check_auth_or_respond():
            return

        self._parse_client_device(fast_skip_if_known=True)
        params = urllib.parse.parse_qs(parsed.query)

        raw_name = None
        if "upload" in params and params["upload"]:
            raw_name = params["upload"][0]
        elif self.headers.get("X-File-Name"):
            raw_name = urllib.parse.unquote(self.headers.get("X-File-Name"))

        if not raw_name:
            self.send_error(400, "Missing filename")
            return

        filename = os.path.basename(raw_name.strip())
        if not filename or filename in (".", ".."):
            self.send_error(400, "Invalid filename")
            return

        raw_len = self.headers.get("Content-Length")
        if raw_len is None:
            self.send_error(411, "Length Required")
            return
        try:
            length = int(raw_len)
        except ValueError:
            self.send_error(411, "Length Required")
            return
        if length <= 0:
            self.send_error(411, "Length Required")
            return
        if length > MAX_UPLOAD_SIZE:
            self.send_error(413, "Payload Too Large")
            return

        rel_dir = urllib.parse.unquote(parsed.path).lstrip("/")
        target_dir = os.path.realpath(os.path.join(self.real_storage, rel_dir))

        if not self._is_within_storage(target_dir) or not os.path.isdir(target_dir):
            self.send_error(403, "Forbidden")
            return

        dest_path, final_filename = get_unique_filepath(target_dir, filename)
        if not self._is_within_storage(dest_path):
            self.send_error(403, "Forbidden")
            return

        expected_sha256 = str(self.headers.get("X-Content-SHA256", "")).strip().lower()
        tmp_name = f".airshare_upload_{secrets.token_hex(6)}.part"
        tmp_path = os.path.join(target_dir, tmp_name)
        try:
            bytes_received = 0
            hasher = hashlib.sha256()
            last_prog_ts = 0.0
            with open(tmp_path, "wb") as f:
                remaining = length
                while remaining > 0:
                    chunk = self.rfile.read(min(STREAM_CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    f.write(chunk)
                    hasher.update(chunk)
                    bytes_received += len(chunk)
                    remaining -= len(chunk)
                    now_ts = time.monotonic()
                    if now_ts - last_prog_ts >= 0.12 or remaining == 0:
                        last_prog_ts = now_ts
                        self._notify_progress(final_filename, bytes_received, length, "upload")
                f.flush()
                os.fsync(f.fileno())

            if bytes_received != length:
                logger.warning(
                    "Загрузка файла %s прервана (%d из %d байт)", final_filename, bytes_received, length
                )
                self.send_error(400, "Incomplete upload")
                return

            actual_sha256 = hasher.hexdigest().lower()
            if not verify_sha256_digest(actual_sha256, expected_sha256):
                logger.warning(
                    "Несовпадение SHA-256 для %s: ожидался %s, получен %s",
                    final_filename,
                    expected_sha256,
                    actual_sha256,
                )
                self.send_error(422, "SHA-256 mismatch")
                return

            dest_path, final_filename = get_unique_filepath(target_dir, filename)
            os.replace(tmp_path, dest_path)

            self._notify_transfer(final_filename, length, "upload")
            resp = b"OK"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("X-Verified-SHA256", actual_sha256)
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
        except OSError as exc:
            logger.exception("Ошибка сохранения загруженного файла %s: %s", final_filename, exc)
            self.send_error(500, "Internal server error")
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError as cleanup_exc:
                    logger.warning("Не удалось удалить временный файл %s: %s", tmp_path, cleanup_exc)

    def _parse_byte_range(self, range_header, file_size):
        if not range_header or not range_header.startswith("bytes="):
            return None
        spec = range_header[6:].strip().split(",")[0].strip()
        if "-" not in spec:
            return None
        start_str, _, end_str = spec.partition("-")
        try:
            if start_str == "":
                suffix_len = int(end_str)
                if suffix_len <= 0:
                    return None
                start = max(0, file_size - suffix_len)
                end = file_size - 1
            else:
                start = int(start_str)
                end = int(end_str) if end_str else (file_size - 1)
        except ValueError:
            return None
        if start < 0 or start >= file_size or end < start:
            return "invalid"
        return start, min(end, file_size - 1)

    def _send_file_body_fast(self, file_obj, start_offset, total_bytes, filename="", full_size=0, notify_prog=False):
        try:
            self.wfile.flush()
        except Exception:
            pass

        last_prog_ts = 0.0
        conn = getattr(self, "connection", None)
        if hasattr(os, "sendfile") and conn is not None and hasattr(conn, "fileno"):
            try:
                out_fd = conn.fileno()
                in_fd = file_obj.fileno()
                offset = start_offset
                remaining = total_bytes
                while remaining > 0:
                    step = min(STREAM_CHUNK_SIZE, remaining)
                    try:
                        sent = os.sendfile(out_fd, in_fd, offset, step)
                    except BlockingIOError:
                        select.select([], [out_fd], [], 5.0)
                        continue
                    except InterruptedError:
                        continue
                    if sent == 0:
                        break
                    offset += sent
                    remaining -= sent
                    if notify_prog and full_size > 0:
                        now_ts = time.monotonic()
                        if now_ts - last_prog_ts >= 0.12 or remaining == 0:
                            last_prog_ts = now_ts
                            self._notify_progress(filename, offset, full_size, "download")
                return
            except (OSError, ValueError, AttributeError):
                pass

        file_obj.seek(start_offset)
        remaining = total_bytes
        sent_total = start_offset
        while remaining > 0:
            buf = file_obj.read(min(STREAM_CHUNK_SIZE, remaining))
            if not buf:
                break
            self.wfile.write(buf)
            remaining -= len(buf)
            sent_total += len(buf)
            if notify_prog and full_size > 0:
                now_ts = time.monotonic()
                if now_ts - last_prog_ts >= 0.12 or remaining == 0:
                    last_prog_ts = now_ts
                    self._notify_progress(filename, sent_total, full_size, "download")

    def stream_single_file(self, current_url_path, target_name, as_attachment=True, head_only=False):
        rel_dir = urllib.parse.unquote(current_url_path).lstrip("/")
        base_dir = os.path.realpath(os.path.join(self.real_storage, rel_dir))
        clean_target = os.path.basename(target_name)
        target_file = os.path.realpath(os.path.join(base_dir, clean_target))

        if not self._is_within_storage(target_file) or not os.path.isfile(target_file):
            self.send_error(404, "File not found")
            return

        try:
            st = os.stat(target_file)
            file_size = st.st_size
            mtime_http = formatdate(st.st_mtime, usegmt=True)
            etag_val = f'"{int(st.st_mtime):x}-{file_size:x}"'

            ctype, _ = mimetypes.guess_type(target_file)
            if not ctype:
                ctype = "application/octet-stream"

            _, ext = os.path.splitext(target_file)
            force_attachment = as_attachment or (ext.lower() in SANDBOX_EXTENSIONS)

            range_hdr = self.headers.get("Range")
            byte_range = self._parse_byte_range(range_hdr, file_size) if file_size > 0 else None

            if byte_range == "invalid":
                self.send_response(416, "Requested Range Not Satisfiable")
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.end_headers()
                return

            if byte_range is not None:
                start, end = byte_range
                chunk_len = end - start + 1
                self.send_response(206, "Partial Content")
                self.send_header("Content-Type", ctype)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(chunk_len))
            else:
                start, chunk_len = 0, file_size
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(file_size))

            self.send_header("Last-Modified", mtime_http)
            self.send_header("ETag", etag_val)
            if not force_attachment:
                self.send_header("Cache-Control", "private, max-age=3600")

            if ext.lower() in SANDBOX_EXTENSIONS:
                self.send_header("Content-Security-Policy", "sandbox")
            if force_attachment:
                self.send_header(
                    "Content-Disposition", make_content_disposition(os.path.basename(target_file), "attachment")
                )
            self.end_headers()

            if head_only:
                return

            base_fname = os.path.basename(target_file)
            with open(target_file, "rb") as f:
                self._send_file_body_fast(
                    f,
                    start,
                    chunk_len,
                    filename=base_fname,
                    full_size=file_size,
                    notify_prog=force_attachment,
                )

            if force_attachment and start == 0:
                self._notify_transfer(base_fname, file_size, "download")
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            logger.debug("Клиент закрыл соединение при потоковой передаче %s", clean_target)
        except OSError as exc:
            logger.exception("Ошибка при отправке файла %s: %s", clean_target, exc)
            try:
                self.send_error(500, "Internal server error")
            except Exception:
                pass

    def stream_folder_zip(self, current_url_path, target_name):
        rel_dir = urllib.parse.unquote(current_url_path).lstrip("/")
        base_dir = os.path.realpath(os.path.join(self.real_storage, rel_dir))
        clean_target = os.path.basename(target_name)
        target_dir = os.path.realpath(os.path.join(base_dir, clean_target))

        if not self._is_within_storage(target_dir) or not os.path.isdir(target_dir):
            self.send_error(404, "Directory not found")
            return

        folder_basename = os.path.basename(target_dir) or "archive"
        parent_dir = os.path.dirname(target_dir)

        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", make_content_disposition(f"{folder_basename}.zip"))
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        stream = _ZipStream(self.wfile)
        try:
            with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_STORED) as zf:
                for root, _, files in os.walk(target_dir, followlinks=False):
                    for file in files:
                        if is_temp_part_file(file):
                            continue
                        full_path = os.path.join(root, file)
                        if os.path.islink(full_path):
                            real_fp = os.path.realpath(full_path)
                            if not self._is_within_storage(real_fp):
                                logger.warning("Пропущен внешний симлинк при архивации: %s", full_path)
                                continue
                        elif not self._is_within_storage(full_path):
                            continue
                        rel_path = os.path.relpath(full_path, parent_dir)
                        try:
                            zf.write(full_path, arcname=rel_path)
                        except OSError as exc:
                            logger.warning("Не удалось добавить файл %s в ZIP: %s", full_path, exc)
                            continue
            self._notify_transfer(f"{folder_basename}.zip", stream.tell(), "download")
        except (BrokenPipeError, ConnectionResetError):
            logger.debug("Клиент прервал скачивание ZIP-архива %s", folder_basename)

    def download_selected_files(self, files):
        valid_entries = []
        seen_arcnames = set()

        for item_rel_path in files:
            clean_rel = str(item_rel_path).replace("\\", "/").lstrip("/")
            candidate_path = os.path.join(self.real_storage, clean_rel)
            if os.path.islink(candidate_path):
                real_cand = os.path.realpath(candidate_path)
                if not self._is_within_storage(real_cand):
                    logger.warning("Пропущен внешний симлинк: %s", item_rel_path)
                    continue
            full_path = os.path.realpath(candidate_path)
            if not self._is_within_storage(full_path):
                logger.warning("Пропущен путь вне хранилища при скачивании выбранного: %s", item_rel_path)
                continue
            if os.path.isfile(full_path):
                if is_temp_part_file(os.path.basename(full_path)):
                    continue
                arcname = os.path.relpath(full_path, self.real_storage).replace("\\", "/")
                if arcname not in seen_arcnames:
                    seen_arcnames.add(arcname)
                    valid_entries.append((full_path, arcname))
            elif os.path.isdir(full_path):
                for root, _, subfiles in os.walk(full_path, followlinks=False):
                    for f in subfiles:
                        if is_temp_part_file(f):
                            continue
                        fp = os.path.join(root, f)
                        real_fp = os.path.realpath(fp)
                        if not self._is_within_storage(real_fp) or not os.path.isfile(real_fp):
                            logger.warning("Пропущен внешний симлинк/файл в папке: %s", fp)
                            continue
                        arcname = os.path.relpath(real_fp, self.real_storage).replace("\\", "/")
                        if arcname not in seen_arcnames:
                            seen_arcnames.add(arcname)
                            valid_entries.append((real_fp, arcname))

        if not valid_entries:
            self.send_error(404, "No valid files selected")
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", make_content_disposition("selected_files.zip"))
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        stream = _ZipStream(self.wfile)
        try:
            with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_STORED) as zf:
                for full_path, arcname in valid_entries:
                    try:
                        zf.write(full_path, arcname=arcname)
                    except OSError as exc:
                        logger.warning("Не удалось упаковать файл %s: %s", full_path, exc)
                        continue
            self._notify_transfer("selected_files.zip", stream.tell(), "download")
        except (BrokenPipeError, ConnectionResetError):
            logger.debug("Клиент прервал скачивание выбранных файлов")

    def list_directory(self, path):
        real_path = os.path.realpath(path)
        if not self._is_within_storage(real_path):
            self.send_error(403, "Forbidden")
            return None

        try:
            raw_list = os.listdir(real_path)
        except OSError as exc:
            logger.warning("Нет доступа к директории %s: %s", real_path, exc)
            self.send_error(403, "Access denied")
            return None

        list_dir = [name for name in raw_list if not is_temp_part_file(name)]
        list_dir.sort(key=lambda a: (not os.path.isdir(os.path.join(real_path, a)), a.lower()))

        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        theme = self._get_request_theme(params)
        lang = self._get_request_lang(params)
        displaypath = html.escape(urllib.parse.unquote(parsed.path))

        total_items = len(list_dir)
        total_pages = max(1, math.ceil(total_items / MAX_DIR_ITEMS_PER_PAGE))
        try:
            page = int(params.get("page", ["1"])[0])
        except ValueError:
            page = 1
        page = max(1, min(total_pages, page))
        start_idx = (page - 1) * MAX_DIR_ITEMS_PER_PAGE
        page_items = list_dir[start_idx : start_idx + MAX_DIR_ITEMS_PER_PAGE]

        search_ph = html.escape(tr("web_search_ph", lang))
        r = []
        r.append('<!DOCTYPE html><html><head><meta charset="utf-8">')
        r.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
        r.append('<link rel="manifest" href="/manifest.webmanifest">')
        r.append('<title>AirShare PC</title>')
        r.append(f'<style>{get_css(theme)}</style>')
        r.append(f'</head><body class="{theme}">')
        r.append('<canvas id="skyCanvas"></canvas>')
        r.append(get_top_controls_html(theme, lang=lang, show_preview_toggle=True))

        r.append('<div class="container">')
        r.append(f'<div class="header"><h1>AirShare PC</h1><p>{displaypath}</p>')
        r.append('<div class="actions-bar">')
        r.append(
            f'<button type="button" class="upload-btn" onclick="triggerUpload()">'
            f'{html.escape(tr("web_upload_btn", lang))}</button>'
        )
        r.append('<input type="file" id="up" multiple style="display:none" onchange="uploadFiles(this.files)">')
        if real_path != self.real_storage:
            r.append(f'<a class="upload-btn" href="../">{html.escape(tr("web_back_btn", lang))}</a>')
        r.append('</div>')
        r.append('<p id="status" style="margin-top:12px;color:#60a5fa;min-height:20px;"></p></div>')

        r.append(
            '<div class="search-wrap">'
            f'<input type="search" id="fileSearchInput" class="search-input" placeholder="{search_ph}" oninput="onSearchInput(this)" autocomplete="off">'
            '<button type="button" id="searchClearBtn" class="search-clear-btn" onclick="clearSearch()">✕</button>'
            '</div>'
            '<div id="serverSearchBox" style="display:none;"></div>'
        )

        r.append('<form id="fileForm" method="GET" onsubmit="return submitSelectedDownload(event)">')
        r.append('<input type="hidden" name="download_selected" value="1">')
        if total_items > 0:
            r.append(
                '<div class="toolbar">'
                f'<label><input type="checkbox" class="checkbox" onchange="toggleSelectAll(this)"> '
                f'{html.escape(tr("web_select_all", lang))}</label>'
                f'<span>{html.escape(tr("web_total_items", lang, count=total_items))}</span>'
                '</div>'
            )
        r.append('<ul class="file-list" id="mainFileList">')

        folder_label = html.escape(tr("web_folder", lang))
        dl_svg = get_download_svg()
        for name in page_items:
            fullname = os.path.join(real_path, name)
            rel_path = os.path.relpath(fullname, self.real_storage).replace("\\", "/")
            safe_val = html.escape(rel_path, quote=True)
            safe_name = html.escape(name)
            safe_data_name = html.escape(name.lower(), quote=True)
            quoted_name = urllib.parse.quote(name, safe="")
            js_safe_name = html.escape(name.replace("\\", "\\\\").replace("'", "\\'"), quote=True)

            if os.path.isdir(fullname):
                r.append(
                    f'<li class="file-item" data-name="{safe_data_name}">'
                    f'<input type="checkbox" class="checkbox" name="files" value="{safe_val}">'
                    f'<div class="file-info"><div class="file-text-col">'
                    f'<a class="file-link" href="{urllib.parse.quote(name + "/")}">📁 {safe_name}</a>'
                    f'<div class="file-meta"><span>{folder_label}</span></div></div></div>'
                    f'<div class="item-actions">'
                    f'<a class="download-btn" href="?zip={quoted_name}" title="ZIP">{dl_svg}</a>'
                    f'</div></li>'
                )
            else:
                try:
                    size_str = format_size(os.path.getsize(fullname))
                except OSError:
                    size_str = "—"

                _, ext = os.path.splitext(name)
                ext_low = ext.lower()
                hash_badge = (
                    f'<span class="hash-pill" onclick="verifyFileHash(\'{quoted_name}\', this)" '
                    f'title="SHA-256">🛡️ SHA-256</span>'
                )
                if ext_low in IMAGE_EXTENSIONS:
                    play_onclick = f"return openMediaPlayer('{quoted_name}', '{js_safe_name}', 'image');"
                    r.append(
                        f'<li class="file-item has-thumb" data-name="{safe_data_name}">'
                        f'<input type="checkbox" class="checkbox" name="files" value="{safe_val}">'
                        f'<div class="file-info">'
                        f'<a class="thumb-box" href="{quoted_name}" onclick="{play_onclick}" tabindex="-1">'
                        f'<img class="file-thumb" data-src="{quoted_name}" loading="lazy" decoding="async" alt="">'
                        f'</a>'
                        f'<div class="file-text-col">'
                        f'<a class="file-link" href="{quoted_name}" onclick="{play_onclick}"><span class="doc-icon">📄 </span>{safe_name}</a>'
                        f'<div class="file-meta"><span>{size_str}</span>{hash_badge}</div></div></div>'
                        f'<div class="item-actions">'
                        f'<a class="download-btn" href="?download={quoted_name}" download="{safe_name}">{dl_svg}</a>'
                        f'</div></li>'
                    )
                elif ext_low in VIDEO_EXTENSIONS:
                    play_onclick = f"return openMediaPlayer('{quoted_name}', '{js_safe_name}', 'video');"
                    r.append(
                        f'<li class="file-item has-thumb" data-name="{safe_data_name}">'
                        f'<input type="checkbox" class="checkbox" name="files" value="{safe_val}">'
                        f'<div class="file-info">'
                        f'<a class="thumb-box" href="{quoted_name}" onclick="{play_onclick}" tabindex="-1">'
                        f'<video class="file-thumb" data-src="{quoted_name}#t=0.5" preload="metadata" muted playsinline></video>'
                        f'<span class="vid-badge">▶</span>'
                        f'</a>'
                        f'<div class="file-text-col">'
                        f'<a class="file-link" href="{quoted_name}" onclick="{play_onclick}"><span class="doc-icon">📄 </span>{safe_name}</a>'
                        f'<div class="file-meta"><span>{size_str}</span>{hash_badge}</div></div></div>'
                        f'<div class="item-actions">'
                        f'<a class="download-btn" href="?download={quoted_name}" download="{safe_name}">{dl_svg}</a>'
                        f'</div></li>'
                    )
                else:
                    r.append(
                        f'<li class="file-item" data-name="{safe_data_name}">'
                        f'<input type="checkbox" class="checkbox" name="files" value="{safe_val}">'
                        f'<div class="file-info"><div class="file-text-col">'
                        f'<a class="file-link" href="{quoted_name}" target="_blank">📄 {safe_name}</a>'
                        f'<div class="file-meta"><span>{size_str}</span>{hash_badge}</div></div></div>'
                        f'<div class="item-actions">'
                        f'<a class="download-btn" href="?download={quoted_name}" download="{safe_name}">{dl_svg}</a>'
                        f'</div></li>'
                    )

        r.append('</ul>')
        if total_pages > 1:
            r.append('<div class="pagination">')
            if page > 1:
                r.append(f'<a class="upload-btn" href="?page={page - 1}">{html.escape(tr("web_page_prev", lang))}</a>')
            r.append(f'<span>{html.escape(tr("web_page_info", lang, page=page, total=total_pages))}</span>')
            if page < total_pages:
                r.append(f'<a class="upload-btn" href="?page={page + 1}">{html.escape(tr("web_page_next", lang))}</a>')
            r.append('</div>')

        if total_items > 0:
            r.append('<div style="text-align:center;margin-top:22px;">')
            r.append(
                f'<button type="submit" class="upload-btn">{html.escape(tr("web_download_zip", lang))}</button>'
            )
            r.append('</div>')
        r.append('</form></div>')
        r.append(get_media_modal_html(lang))
        r.append('<div class="credit-badge">Crafted by JackBrownUA • Powered by Gemini</div>')
        r.append(f'<script>{get_star_script()}{get_upload_script(lang)}{get_theme_script()}</script>')
        r.append('</body></html>')

        encoded = "\n".join(r).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        if "theme" in params and params["theme"]:
            self.send_header("Set-Cookie", f"airshare_theme={theme}; Path=/; Max-Age=31536000; SameSite=Lax")
        if "lang" in params and params["lang"]:
            self.send_header("Set-Cookie", f"airshare_lang={lang}; Path=/; Max-Age=31536000; SameSite=Lax")
        self.end_headers()
        return BytesIO(encoded)

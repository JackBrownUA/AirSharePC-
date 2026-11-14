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
THUMB_MAX_BYTES = 1536 * 1024


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
                request.settimeout(SOCKET_TIMEOUT_SECONDS)
            except Exception:
                pass
            self.process_request_thread(request, client_address)
        finally:
            self._conn_semaphore.release()


class AirShareHandler(SimpleHTTPRequestHandler):
    timeout = SOCKET_TIMEOUT_SECONDS

    _pending_auth_cookie = None
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

    @classmethod
    def reset_rate_limits(cls):
        with cls._auth_lock:
            cls._failed_attempts.clear()
            cls._device_sessions.clear()
            cls._session_secret = secrets.token_hex(16)

    @classmethod
    def reset_auth_sessions(cls, new_password=""):
        with cls._auth_lock:
            cls.current_password = str(new_password or "")
            cls._session_secret = secrets.token_hex(16)
            cls._failed_attempts.clear()
            cls._disconnected_ips.clear()
            cls._notified_ips.clear()
            cls._device_sessions.clear()

    @classmethod
    def set_ip_disconnected(cls, ip, disconnected=True):
        if not ip:
            return
        with cls._auth_lock:
            if disconnected:
                cls._disconnected_ips.add(ip)
                cls._notified_ips.discard(ip)
                to_remove = [k for k, v in cls._device_sessions.items() if v.get("ip") == ip]
                for k in to_remove:
                    cls._device_sessions.pop(k, None)
            else:
                cls._disconnected_ips.discard(ip)

    @classmethod
    def is_ip_disconnected(cls, ip) -> bool:
        with cls._auth_lock:
            return ip in cls._disconnected_ips

    def _is_within_storage(self, target_path: str) -> bool:
        return is_within_storage(self.real_storage, target_path)

    def translate_path(self, path):
        clean_path = (path or "/").replace("\x00", "")
        raw_path = super().translate_path(clean_path)
        try:
            resolved = os.path.realpath(raw_path)
        except (ValueError, OSError):
            return self.real_storage
        if not self._is_within_storage(resolved):
            logger.warning("Заблокирована попытка обхода директории: %s -> %s", path, resolved)
            return self.real_storage
        return resolved

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "no-referrer")
        if self._pending_auth_cookie:
            self.send_header("Set-Cookie", self._pending_auth_cookie)
            self._pending_auth_cookie = None
        super().end_headers()

    def _get_client_ip(self) -> str:
        return self.client_address[0] if self.client_address else "unknown"

    def _check_rate_limit(self):
        is_blocked, retry_after = check_ip_rate_limit(
            self._get_client_ip(), self._failed_attempts, self._auth_lock
        )
        return (not is_blocked), retry_after

    def _register_auth_failure(self):
        ip = self._get_client_ip()
        register_auth_failure(ip, self._failed_attempts, self._auth_lock)
        cb = getattr(type(self), "on_bad_pin_attempt", None)
        if cb:
            try:
                cb(ip)
            except Exception as exc:
                logger.debug("Ошибка колбэка on_bad_pin_attempt: %s", exc)

    def _clear_auth_failures(self):
        ip = self._get_client_ip()
        with self._auth_lock:
            self._failed_attempts.pop(ip, None)

    def _ensure_password_loaded(self) -> str:
        with self._auth_lock:
            pwd = self.current_password
        if not pwd:
            pwd = str(load_settings().get("password", "") or "")
            with self._auth_lock:
                if not self.current_password and pwd:
                    self.__class__.current_password = pwd
        return pwd

    def _issue_session_cookie_str(self) -> str:
        pwd = self._ensure_password_loaded()
        ip = self._get_client_ip()
        token = create_device_session_token(
            self._session_secret,
            self._device_sessions,
            self._auth_lock,
            ip,
            pwd,
        )
        return f"airshare_auth={token}; HttpOnly; Path=/; SameSite=Lax"

    def _is_authenticated_request(self) -> bool:
        pwd = self._ensure_password_loaded()
        ip = self._get_client_ip()
        cookie_hdr = self.headers.get("Cookie", "")
        if cookie_hdr:
            try:
                jar = cookies.SimpleCookie()
                jar.load(cookie_hdr)
                for cname in ("airshare_auth", "airshare_session"):
                    if cname in jar:
                        tok = jar[cname].value
                        if is_valid_session_cookie(
                            tok,
                            ip,
                            pwd,
                            self._session_secret,
                            self._device_sessions,
                            self._auth_lock,
                        ):
                            return True
            except cookies.CookieError:
                pass

        auth_header = self.headers.get("Authorization")
        if auth_header and auth_header.startswith("Basic "):
            try:
                encoded = auth_header.split(" ", 1)[1].strip()
                decoded = base64.b64decode(encoded).decode("utf-8", errors="ignore")
                _, _, provided_pwd = decoded.partition(":")
                if hmac.compare_digest(provided_pwd.encode("utf-8", "surrogatepass"), pwd.encode("utf-8", "surrogatepass")):
                    self._pending_auth_cookie = self._issue_session_cookie_str()
                    return True
            except Exception as exc:
                logger.debug("Ошибка разбора Basic-авторизации: %s", exc)
            self._register_auth_failure()
        return False

    def _get_request_theme(self, params=None) -> str:
        if params is None:
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
        url_theme = params.get("theme", [None])[0]
        if url_theme in ("light", "dark"):
            return url_theme
        cookie_hdr = self.headers.get("Cookie", "")
        if cookie_hdr:
            try:
                jar = cookies.SimpleCookie()
                jar.load(cookie_hdr)
                if "airshare_theme" in jar:
                    c_theme = jar["airshare_theme"].value
                    if c_theme in ("light", "dark"):
                        return c_theme
            except cookies.CookieError:
                pass
        return self.default_theme if self.default_theme in ("light", "dark") else "dark"

    def _get_request_lang(self, params=None) -> str:
        if params is None:
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
        url_lang = params.get("lang", [None])[0]
        if url_lang and url_lang.lower() in SUPPORTED_CODES:
            return url_lang.lower()
        cookie_hdr = self.headers.get("Cookie", "")
        if cookie_hdr:
            try:
                jar = cookies.SimpleCookie()
                jar.load(cookie_hdr)
                if "airshare_lang" in jar:
                    c_lang = jar["airshare_lang"].value.lower()
                    if c_lang in SUPPORTED_CODES:
                        return c_lang
            except cookies.CookieError:
                pass
        accept_lang = self.headers.get("Accept-Language", "")
        if accept_lang:
            for part in accept_lang.split(","):
                code = part.split(";")[0].strip().lower()[:2]
                if code in SUPPORTED_CODES:
                    return code
        return self.current_language if self.current_language in SUPPORTED_CODES else "en"

    def _send_html_page(self, status_code: int, html_str: str, extra_headers=None):
        body = html_str.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def check_auth_or_respond(self) -> bool:
        ip = self._get_client_ip()
        theme = self._get_request_theme()
        lang = self._get_request_lang()

        if self.is_ip_disconnected(ip):
            msg = tr("web_dev_blocked", lang)
            self._send_html_page(403, get_pin_login_page(theme=theme, lang=lang, error_msg=msg, next_path=self.path))
            return False

        allowed, retry_after = self._check_rate_limit()
        if not allowed:
            msg = tr("web_rate_limit", lang, sec=retry_after)
            self._send_html_page(
                429,
                get_pin_login_page(theme=theme, lang=lang, error_msg=msg, next_path=self.path),
                extra_headers={"Retry-After": str(retry_after)},
            )
            return False

        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "pin" in params and params["pin"]:
            provided_pin = params["pin"][0].strip()
            pwd = self._ensure_password_loaded()
            if hmac.compare_digest(provided_pin.encode("utf-8", "surrogatepass"), pwd.encode("utf-8", "surrogatepass")):
                self._clear_auth_failures()
                clean_query = urllib.parse.urlencode(
                    {k: v for k, v in params.items() if k != "pin"}, doseq=True
                )
                redirect_target = parsed.path or "/"
                if clean_query:
                    redirect_target = f"{redirect_target}?{clean_query}"
                self.send_response(303)
                self.send_header("Location", redirect_target)
                self.send_header("Set-Cookie", self._issue_session_cookie_str())
                self.send_header("Content-Length", "0")
                self.end_headers()
                return False
            self._register_auth_failure()
            allowed_after, retry_after_pin = self._check_rate_limit()
            if not allowed_after:
                msg = tr("web_rate_limit", lang, sec=retry_after_pin)
                self._send_html_page(
                    429,
                    get_pin_login_page(theme=theme, lang=lang, error_msg=msg, next_path=self.path),
                    extra_headers={"Retry-After": str(retry_after_pin)},
                )
                return False

        if self._is_authenticated_request():
            self._clear_auth_failures()
            return True

        allowed_now, retry_now = self._check_rate_limit()
        if not allowed_now:
            msg = tr("web_rate_limit", lang, sec=retry_now)
            self._send_html_page(
                429,
                get_pin_login_page(theme=theme, lang=lang, error_msg=msg, next_path=self.path),
                extra_headers={"Retry-After": str(retry_now)},
            )
            return False

        extra = {}
        if "lang" in params and params["lang"]:
            extra["Set-Cookie"] = f"airshare_lang={lang}; Path=/; Max-Age=31536000; SameSite=Lax"
        self._send_html_page(
            401,
            get_pin_login_page(theme=theme, lang=lang, next_path=self.path),
            extra_headers=extra,
        )
        return False

    def _handle_login_post(self):
        ip = self._get_client_ip()
        theme = self._get_request_theme()
        lang = self._get_request_lang()

        if self.is_ip_disconnected(ip):
            msg = tr("web_dev_blocked", lang)
            self._send_html_page(403, get_pin_login_page(theme=theme, lang=lang, error_msg=msg))
            return

        allowed, retry_after = self._check_rate_limit()
        if not allowed:
            msg = tr("web_rate_limit", lang, sec=retry_after)
            self._send_html_page(
                429,
                get_pin_login_page(theme=theme, lang=lang, error_msg=msg),
                extra_headers={"Retry-After": str(retry_after)},
            )
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        raw_body = self.rfile.read(max(0, min(length, 4096))).decode("utf-8", errors="ignore") if length > 0 else ""
        form = urllib.parse.parse_qs(raw_body)
        provided_pin = (form.get("pin", [""])[0] or "").strip()
        raw_next = form.get("next", ["/"])[0] or "/"
        if "\r" in raw_next or "\n" in raw_next or not raw_next.startswith("/") or raw_next.startswith("//") or raw_next.startswith("/\\"):
            next_path = "/"
        else:
            next_path = raw_next

        pwd = self._ensure_password_loaded()
        if hmac.compare_digest(provided_pin.encode("utf-8", "surrogatepass"), pwd.encode("utf-8", "surrogatepass")):
            self._clear_auth_failures()
            self.send_response(303)
            self.send_header("Location", next_path)
            self.send_header("Set-Cookie", self._issue_session_cookie_str())
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        self._register_auth_failure()
        allowed_now, retry_now = self._check_rate_limit()
        if not allowed_now:
            err = tr("web_rate_limit", lang, sec=retry_now)
            self._send_html_page(
                429,
                get_pin_login_page(theme=theme, lang=lang, error_msg=err, next_path=next_path),
                extra_headers={"Retry-After": str(retry_now)},
            )
            return
        err = tr("pin_hint", lang)
        self._send_html_page(401, get_pin_login_page(theme=theme, lang=lang, error_msg=err, next_path=next_path))

    def _parse_client_device(self, fast_skip_if_known=False):
        ip = self.client_address[0]
        if fast_skip_if_known:
            with self._auth_lock:
                if ip in self._notified_ips:
                    return
        ua = self.headers.get("User-Agent", "")
        os_name = "Unknown OS"
        if "Windows" in ua:
            os_name = "Windows PC"
        elif "Macintosh" in ua or "Mac OS" in ua:
            os_name = "Mac"
        elif "Android" in ua:
            os_name = "Android"
        elif "iPhone" in ua or "iPad" in ua:
            os_name = "iOS"
        elif "Linux" in ua:
            os_name = "Linux PC"

        browser = "Browser"
        if "Edg/" in ua:
            browser = "Edge"
        elif "OPR/" in ua or "Opera" in ua:
            browser = "Opera"
        elif "Chrome/" in ua:
            browser = "Chrome"
        elif "Firefox/" in ua:
            browser = "Firefox"
        elif "Safari/" in ua and "Chrome/" not in ua:
            browser = "Safari"

        device_title = f"{os_name} ({browser})"
        with self._auth_lock:
            is_new = ip not in self._notified_ips
            if is_new:
                self._notified_ips.add(ip)

        if is_new:
            add_recent_ip(ip)
        cb = getattr(type(self), "on_client_connected", None)
        if cb:
            try:
                cb(device_title, os_name, ip, is_first=is_new)
            except Exception as exc:
                logger.debug("Ошибка колбэка on_client_connected: %s", exc)

    def _notify_transfer(self, filename: str, size_bytes: int, direction: str):
        cb = getattr(type(self), "on_file_transfer", None)
        if cb:
            try:
                cb(filename, format_size(size_bytes), direction)
            except Exception as exc:
                logger.debug("Ошибка колбэка on_file_transfer: %s", exc)

    def _notify_progress(self, filename: str, done_bytes: int, total_bytes: int, direction: str):
        cb = getattr(type(self), "on_transfer_progress", None)
        if cb:
            try:
                cb(filename, done_bytes, total_bytes, direction)
            except Exception as exc:
                logger.debug("Ошибка колбэка on_transfer_progress: %s", exc)

    def _serve_file_hash(self, current_url_path: str, target_name: str):
        rel_dir = urllib.parse.unquote(current_url_path).lstrip("/")
        base_dir = os.path.realpath(os.path.join(self.real_storage, rel_dir))
        clean_target = os.path.basename((target_name or "").replace("\x00", ""))
        target_file = os.path.realpath(os.path.join(base_dir, clean_target))
        if not self._is_within_storage(target_file) or not os.path.isfile(target_file):
            self.send_error(404, "File not found")
            return
        try:
            st_stat = os.stat(target_file)
            digest = compute_cached_file_sha256(target_file, st_stat, self._hash_cache, self._auth_lock)
            body = json.dumps({"name": clean_target, "sha256": digest}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError:
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
        if os.path.isdir(target_path):
            f = self.list_directory(target_path)
            if f:
                f.close()
            return
        self.send_error(404, "File not found")

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
            payload = json.dumps({"results": results}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if "download" in params and params["download"]:
            self._parse_client_device(fast_skip_if_known=True)
            self.stream_single_file(parsed.path, params["download"][0], as_attachment=True)
            return

        if "zip" in params and params["zip"]:
            self._parse_client_device(fast_skip_if_known=True)
            self.stream_folder_zip(parsed.path, params["zip"][0])
            return

        if "download_selected" in params and "files" in params:
            self._parse_client_device(fast_skip_if_known=True)
            self.download_selected_files(params["files"])
            return

        target_path = self.translate_path(parsed.path)
        if os.path.isfile(target_path):
            self._parse_client_device(fast_skip_if_known=True)
            parent_url = os.path.dirname(urllib.parse.unquote(parsed.path))
            self.stream_single_file(parent_url, os.path.basename(target_path), as_attachment=False)
            return

        self._parse_client_device(fast_skip_if_known=False)
        if os.path.isdir(target_path):
            if not urllib.parse.unquote(parsed.path).replace("\x00", "").endswith("/"):
                self.send_response(301)
                new_loc = parsed.path + "/" + (f"?{parsed.query}" if parsed.query else "")
                self.send_header("Location", new_loc)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            f = self.list_directory(target_path)
            if f:
                try:
                    self.copyfile(f, self.wfile)
                finally:
                    f.close()
            return
        self.send_error(404, "File not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/login":
            self._handle_login_post()
            return

        if not self.check_auth_or_respond():
            return
        self._parse_client_device(fast_skip_if_known=True)

        params = urllib.parse.parse_qs(parsed.query)
        raw_filename = ""
        if "upload" in params and params["upload"]:
            raw_filename = params["upload"][0]
        elif "X-File-Name" in self.headers:
            raw_filename = urllib.parse.unquote(self.headers.get("X-File-Name", ""))

        filename = os.path.basename(raw_filename.replace("\x00", "").strip())
        if not filename or filename in (".", ".."):
            self.send_error(400, "Invalid filename")
            return

        rel_dir = urllib.parse.unquote(parsed.path).lstrip("/")
        target_dir = os.path.realpath(os.path.join(self.real_storage, rel_dir))
        if not self._is_within_storage(target_dir) or not os.path.isdir(target_dir):
            self.send_error(403, "Forbidden target directory")
            return

        try:
            length = int(self.headers.get("Content-Length", -1))
        except ValueError:
            self.send_error(400, "Invalid Content-Length")
            return

        if length < 0:
            self.send_error(411, "Content-Length required")
            return
        if length > MAX_UPLOAD_SIZE:
            self.send_error(413, "File too large")
            return

        expected_sha256 = (self.headers.get("X-Content-SHA256") or "").strip().lower()
        dest_path, final_filename = get_unique_filepath(target_dir, filename)
        tmp_path = os.path.join(target_dir, f".airshare_{threading.get_ident()}_{secrets.token_hex(4)}.part")

        hasher = hashlib.sha256()
        try:
            remaining = length
            received = 0
            last_prog_ts = 0.0
            with open(tmp_path, "wb") as f:
                while remaining > 0:
                    chunk_size = min(remaining, STREAM_CHUNK_SIZE)
                    chunk = self.rfile.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    hasher.update(chunk)
                    remaining -= len(chunk)
                    received += len(chunk)
                    now_ts = time.monotonic()
                    if now_ts - last_prog_ts >= 0.12 or remaining == 0:
                        last_prog_ts = now_ts
                        self._notify_progress(final_filename, received, length, "upload")

            if remaining != 0:
                logger.warning("Неполная загрузка файла %s (осталось %d байт)", final_filename, remaining)
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                self.send_error(400, "Incomplete upload")
                return

            actual_sha256 = hasher.hexdigest().lower()
            if expected_sha256 and not verify_sha256_digest(actual_sha256, expected_sha256):
                logger.error(
                    "Несовпадение SHA-256 при загрузке %s: ожидался %s, получен %s",
                    final_filename,
                    expected_sha256,
                    actual_sha256,
                )
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
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
        offset = start_offset
        remaining = total_bytes
        if hasattr(os, "sendfile") and conn is not None and hasattr(conn, "fileno"):
            try:
                out_fd = conn.fileno()
                in_fd = file_obj.fileno()
                idle_wait = 0.0
                while remaining > 0:
                    step = min(STREAM_CHUNK_SIZE, remaining)
                    try:
                        sent = os.sendfile(out_fd, in_fd, offset, step)
                        idle_wait = 0.0
                    except BlockingIOError:
                        _, wready, _ = select.select([], [out_fd], [], 5.0)
                        if not wready:
                            idle_wait += 5.0
                            if idle_wait >= SOCKET_TIMEOUT_SECONDS:
                                raise TimeoutError("sendfile write timeout")
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
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                raise
            except (OSError, ValueError, AttributeError):
                pass

        file_obj.seek(offset)
        sent_total = offset
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
        clean_target = os.path.basename((target_name or "").replace("\x00", ""))
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

            is_thumb = "thumb=1" in urllib.parse.urlparse(self.path).query
            if byte_range is not None:
                start, end = byte_range
                if is_thumb and (end - start + 1) > THUMB_MAX_BYTES:
                    end = min(file_size - 1, start + THUMB_MAX_BYTES - 1)
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
        clean_target = os.path.basename((target_name or "").replace("\x00", ""))
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
                        except (BrokenPipeError, ConnectionResetError, TimeoutError):
                            raise
                        except OSError as exc:
                            logger.warning("Не удалось добавить файл %s в ZIP: %s", full_path, exc)
                            continue
            self._notify_transfer(f"{folder_basename}.zip", stream.tell(), "download")
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
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
                        if os.path.islink(fp):
                            real_fp = os.path.realpath(fp)
                            if not self._is_within_storage(real_fp) or not os.path.isfile(real_fp):
                                logger.warning("Пропущен внешний симлинк в папке: %s", fp)
                                continue
                        else:
                            real_fp = os.path.realpath(fp)
                            if not self._is_within_storage(real_fp) or not os.path.isfile(real_fp):
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
                    except (BrokenPipeError, ConnectionResetError, TimeoutError):
                        raise
                    except OSError as exc:
                        logger.warning("Не удалось упаковать файл %s: %s", full_path, exc)
                        continue
            self._notify_transfer("selected_files.zip", stream.tell(), "download")
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
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
            '<button type="button" class="upload-btn" onclick="triggerUpload()">'
            f'{html.escape(tr("web_upload_btn", lang))}</button>'
        )
        r.append('<input type="file" id="up" multiple style="display:none" onchange="uploadFiles(this.files)">')
        if real_path != self.real_storage:
            r.append(f'<a class="upload-btn" href="../">{html.escape(tr("web_back_btn", lang))}</a>')
        r.append('</div>')
        r.append('<p id="status"></p></div>')

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
                '<label><input type="checkbox" class="checkbox" onchange="toggleSelectAll(this)"> '
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
            js_safe_name = html.escape(name.replace("\\", "\\\\").replace("'", "\\'").replace("\r", "").replace("\n", " "), quote=True)

            if os.path.isdir(fullname):
                r.append(
                    f'<li class="file-item" data-name="{safe_data_name}">'
                    f'<input type="checkbox" class="checkbox" name="files" value="{safe_val}">'
                    '<div class="file-info"><div class="file-text-col">'
                    f'<a class="file-link" href="{urllib.parse.quote(name + "/")}">📁 {safe_name}</a>'
                    f'<div class="file-meta"><span>{folder_label}</span></div></div></div>'
                    '<div class="item-actions">'
                    f'<a class="download-btn" href="?zip={quoted_name}" title="ZIP">{dl_svg}</a>'
                    '</div></li>'
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
                    'title="SHA-256">🛡️ SHA-256</span>'
                )
                if ext_low in IMAGE_EXTENSIONS:
                    play_onclick = f"return openMediaPlayer('{quoted_name}', '{js_safe_name}', 'image');"
                    r.append(
                        f'<li class="file-item has-thumb" data-name="{safe_data_name}">'
                        f'<input type="checkbox" class="checkbox" name="files" value="{safe_val}">'
                        '<div class="file-info">'
                        f'<a class="thumb-box" href="{quoted_name}" onclick="{play_onclick}" tabindex="-1">'
                        f'<img class="file-thumb" data-src="{quoted_name}" loading="lazy" decoding="async" alt="">'
                        '</a>'
                        '<div class="file-text-col">'
                        f'<a class="file-link" href="{quoted_name}" onclick="{play_onclick}"><span class="doc-icon">📄 </span>{safe_name}</a>'
                        f'<div class="file-meta"><span>{size_str}</span>{hash_badge}</div></div></div>'
                        '<div class="item-actions">'
                        f'<a class="download-btn" href="?download={quoted_name}" download="{safe_name}">{dl_svg}</a>'
                        '</div></li>'
                    )
                elif ext_low in VIDEO_EXTENSIONS:
                    play_onclick = f"return openMediaPlayer('{quoted_name}', '{js_safe_name}', 'video');"
                    r.append(
                        f'<li class="file-item has-thumb" data-name="{safe_data_name}">'
                        f'<input type="checkbox" class="checkbox" name="files" value="{safe_val}">'
                        '<div class="file-info">'
                        f'<a class="thumb-box" href="{quoted_name}" onclick="{play_onclick}" tabindex="-1">'
                        f'<video class="file-thumb" data-src="{quoted_name}?thumb=1#t=0.5" preload="metadata" muted playsinline></video>'
                        '<span class="vid-badge">▶</span>'
                        '</a>'
                        '<div class="file-text-col">'
                        f'<a class="file-link" href="{quoted_name}" onclick="{play_onclick}"><span class="doc-icon">📄 </span>{safe_name}</a>'
                        f'<div class="file-meta"><span>{size_str}</span>{hash_badge}</div></div></div>'
                        '<div class="item-actions">'
                        f'<a class="download-btn" href="?download={quoted_name}" download="{safe_name}">{dl_svg}</a>'
                        '</div></li>'
                    )
                else:
                    r.append(
                        f'<li class="file-item" data-name="{safe_data_name}">'
                        f'<input type="checkbox" class="checkbox" name="files" value="{safe_val}">'
                        '<div class="file-info"><div class="file-text-col">'
                        f'<a class="file-link" href="{quoted_name}" target="_blank">📄 {safe_name}</a>'
                        f'<div class="file-meta"><span>{size_str}</span>{hash_badge}</div></div></div>'
                        '<div class="item-actions">'
                        f'<a class="download-btn" href="?download={quoted_name}" download="{safe_name}">{dl_svg}</a>'
                        '</div></li>'
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
        r.append(f'<script>{get_star_script()}</script>')
        r.append(f'<script>{get_upload_script(lang)}</script>')
        r.append(f'<script>{get_theme_script()}</script>')
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


def run_server(port=8080, password="", theme="dark", lang="en"):
    os.makedirs(STORAGE_PATH, exist_ok=True)
    AirShareHandler.default_theme = theme if theme in ("light", "dark") else "dark"
    AirShareHandler.current_language = lang if lang in SUPPORTED_CODES else "en"
    AirShareHandler.reset_auth_sessions(password)
    server = ReusableThreadingServer(("0.0.0.0", port), AirShareHandler)
    logger.info("Сервер AirShare запущен на порту %d (папка: %s)", port, STORAGE_PATH)
    return server

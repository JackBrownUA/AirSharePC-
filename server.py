# HTTP-сервер AirShare PC: авторизация, HTTP Range (206), потоковый ZIP, пагинация и отключение клиентов

import base64
import hmac
import html
import logging
import math
import mimetypes
import os
import secrets
import threading
import time
import urllib.parse
import zipfile
from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO

from config import (
    MAX_CONCURRENT_CONNECTIONS,
    MAX_DIR_ITEMS_PER_PAGE,
    MAX_UPLOAD_SIZE,
    RATE_LIMIT_BLOCK_SECONDS,
    RATE_LIMIT_MAX_ATTEMPTS,
    SOCKET_TIMEOUT_SECONDS,
    STORAGE_PATH,
)
from i18n import tr
from utils import add_recent_ip, format_size, load_settings
from web_ui import get_css, get_star_script, get_theme_script, get_upload_script

logger = logging.getLogger("airshare.server")

# Расширения файлов, которые браузер может попытаться выполнить в контексте origin сервера
_SANDBOX_EXTENSIONS = frozenset({".html", ".htm", ".svg", ".xhtml", ".js", ".mjs", ".xml"})


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
        # Ограничиваем число одновременных HTTP-соединений для защиты от исчерпания потоков
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
            self.process_request_thread(request, client_address)
        finally:
            self._conn_semaphore.release()


def _make_content_disposition(filename, disposition="attachment"):
    clean_name = os.path.basename(filename).replace('"', "_").replace("\r", "").replace("\n", "")
    ascii_fallback = clean_name.encode("ascii", "ignore").decode("ascii").strip()
    if not ascii_fallback or ascii_fallback.startswith("."):
        _, ext = os.path.splitext(clean_name)
        ascii_fallback = f"download{ext}"
    utf8_quoted = urllib.parse.quote(clean_name, safe="")
    return f'{disposition}; filename="{ascii_fallback}"; filename*=UTF-8\'\'{utf8_quoted}'


def _get_unique_filepath(target_dir, filename):
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


class AirShareHandler(SimpleHTTPRequestHandler):
    # Таймаут чтения/записи сокета против зависших подключений (п. 11)
    timeout = SOCKET_TIMEOUT_SECONDS

    current_password = ""
    default_theme = "dark"
    current_language = "en"
    on_client_connected = None
    on_file_transfer = None
    on_bad_pin_attempt = None

    _auth_lock = threading.Lock()
    _failed_attempts = {}
    _disconnected_ips = set()
    _notified_ips = set()

    def __init__(self, *args, **kwargs):
        self.real_storage = os.path.realpath(STORAGE_PATH)
        super().__init__(*args, directory=self.real_storage, **kwargs)

    def end_headers(self):
        # Защитные HTTP-заголовки для каждого ответа сервера (п. 10)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    @classmethod
    def reset_rate_limits(cls):
        with cls._auth_lock:
            cls._failed_attempts.clear()

    @classmethod
    def set_ip_disconnected(cls, ip_str, disconnected=True):
        with cls._auth_lock:
            if disconnected:
                cls._disconnected_ips.add(str(ip_str).strip())
            else:
                cls._disconnected_ips.discard(str(ip_str).strip())

    @classmethod
    def is_ip_disconnected(cls, ip_str):
        with cls._auth_lock:
            return str(ip_str).strip() in cls._disconnected_ips

    def _get_client_ip(self):
        if self.client_address and len(self.client_address) > 0:
            return str(self.client_address[0])
        return "127.0.0.1"

    def _is_ip_blocked(self, client_ip):
        now = time.monotonic()
        with self._auth_lock:
            record = self._failed_attempts.get(client_ip)
            if not record:
                return False, 0
            count, blocked_until = record
            if blocked_until > now:
                return True, int(blocked_until - now) + 1
            if blocked_until > 0 and blocked_until <= now:
                del self._failed_attempts[client_ip]
            return False, 0

    def _record_auth_failure(self, client_ip):
        now = time.monotonic()
        with self._auth_lock:
            count, blocked_until = self._failed_attempts.get(client_ip, (0, 0.0))
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
            self._failed_attempts[client_ip] = (count, blocked_until)

        if callable(self.on_bad_pin_attempt):
            try:
                self.on_bad_pin_attempt(client_ip)
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

    def check_auth_or_respond(self):
        client_ip = self._get_client_ip()
        if self.is_ip_disconnected(client_ip):
            body = f"<h3>{html.escape(tr('web_dev_blocked', self.current_language))}</h3>".encode("utf-8")
            self.send_response(403, "Forbidden")
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return False

        blocked, retry_after = self._is_ip_blocked(client_ip)
        if blocked:
            self.send_rate_limit_response(retry_after)
            return False
        if self.is_authenticated():
            self._clear_auth_failures(client_ip)
            return True
        self._record_auth_failure(client_ip)
        blocked_now, retry_after = self._is_ip_blocked(client_ip)
        if blocked_now:
            self.send_rate_limit_response(retry_after)
        else:
            self.request_auth()
        return False

    def is_authenticated(self):
        expected_pwd = self._ensure_password_loaded()
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            raw = base64.b64decode(header[6:]).decode("utf-8")
            _user, sep, pwd = raw.partition(":")
            if not sep:
                return False
            return hmac.compare_digest(pwd.encode("utf-8"), expected_pwd.encode("utf-8"))
        except Exception as exc:
            logger.warning("Ошибка разбора заголовка Authorization: %s", exc)
            return False

    def send_rate_limit_response(self, retry_after=RATE_LIMIT_BLOCK_SECONDS):
        msg = tr("web_rate_limit", self.current_language, sec=retry_after)
        body = f"<h3>{html.escape(msg)}</h3>".encode("utf-8")
        self.send_response(429, "Too Many Requests")
        self.send_header("Retry-After", str(retry_after))
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def request_auth(self):
        msg = tr("web_auth_req", self.current_language)
        body = f"<h3>{html.escape(msg)}</h3>".encode("utf-8")
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="AirShare PC"')
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _parse_client_device(self):
        try:
            client_ip = self._get_client_ip()
            if client_ip in ("127.0.0.1", "::1"):
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
            if callable(self.on_client_connected):
                self.on_client_connected(device_title, os_badge, client_ip, is_first_notify)
        except Exception as exc:
            logger.warning("Не удалось определить устройство клиента: %s", exc)

    def _notify_transfer(self, filename, size_bytes, direction="done"):
        try:
            if callable(self.on_file_transfer):
                self.on_file_transfer(filename, format_size(size_bytes), direction)
        except Exception as exc:
            logger.warning("Ошибка уведомления UI о передаче файла: %s", exc)

    def _is_within_storage(self, candidate_path):
        try:
            real_candidate = os.path.realpath(candidate_path)
            return os.path.commonpath([self.real_storage, real_candidate]) == self.real_storage
        except ValueError:
            return False

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

    def do_HEAD(self):
        if not self.check_auth_or_respond():
            return
        self._parse_client_device()
        super().do_HEAD()

    def do_GET(self):
        if not self.check_auth_or_respond():
            return

        self._parse_client_device()
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "download" in params and params["download"]:
            self.stream_single_file(parsed.path, params["download"][0], as_attachment=True)
            return

        if "zip" in params and params["zip"]:
            self.stream_folder_zip(parsed.path, params["zip"][0])
            return

        if "download_selected" in params or "files" in params:
            selected = params.get("files", [])
            if selected:
                self.download_selected_files(selected)
                return

        # Если запрашивается конкретный файл по прямому пути, отдаём его через stream_single_file
        # с поддержкой HTTP Range (206) и защитой от выполнения чужого HTML/JS (п. 10, 23)
        target_path = self.translate_path(parsed.path)
        if os.path.isfile(target_path):
            parent_url = os.path.dirname(urllib.parse.unquote(parsed.path))
            self.stream_single_file(parent_url, os.path.basename(target_path), as_attachment=False)
            return

        super().do_GET()

    def do_POST(self):
        if not self.check_auth_or_respond():
            return

        self._parse_client_device()
        parsed = urllib.parse.urlparse(self.path)
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

        dest_path, final_filename = _get_unique_filepath(target_dir, filename)
        if not self._is_within_storage(dest_path):
            self.send_error(403, "Forbidden")
            return

        tmp_name = f".airshare_upload_{secrets.token_hex(6)}.part"
        tmp_path = os.path.join(target_dir, tmp_name)
        try:
            bytes_received = 0
            with open(tmp_path, "wb") as f:
                remaining = length
                while remaining > 0:
                    chunk = self.rfile.read(min(65536, remaining))
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_received += len(chunk)
                    remaining -= len(chunk)
                f.flush()
                os.fsync(f.fileno())

            if bytes_received != length:
                logger.warning(
                    "Загрузка файла %s прервана (%d из %d байт)", final_filename, bytes_received, length
                )
                self.send_error(400, "Incomplete upload")
                return

            dest_path, final_filename = _get_unique_filepath(target_dir, filename)
            os.replace(tmp_path, dest_path)

            self._notify_transfer(final_filename, length, "upload")
            resp = b"OK"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
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
        # Разбираем заголовок Range: bytes=start-end для докачки и перемотки видео (п. 23)
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

    def stream_single_file(self, current_url_path, target_name, as_attachment=True):
        rel_dir = urllib.parse.unquote(current_url_path).lstrip("/")
        base_dir = os.path.realpath(os.path.join(self.real_storage, rel_dir))
        clean_target = os.path.basename(target_name)
        target_file = os.path.realpath(os.path.join(base_dir, clean_target))

        if not self._is_within_storage(target_file) or not os.path.isfile(target_file):
            self.send_error(404, "File not found")
            return

        try:
            file_size = os.path.getsize(target_file)
            ctype, _ = mimetypes.guess_type(target_file)
            if not ctype:
                ctype = "application/octet-stream"

            _, ext = os.path.splitext(target_file)
            force_attachment = as_attachment or (ext.lower() in _SANDBOX_EXTENSIONS)

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

            if ext.lower() in _SANDBOX_EXTENSIONS:
                self.send_header("Content-Security-Policy", "sandbox")
            if force_attachment:
                self.send_header(
                    "Content-Disposition", _make_content_disposition(os.path.basename(target_file), "attachment")
                )
            self.end_headers()

            with open(target_file, "rb") as f:
                if start > 0:
                    f.seek(start)
                remaining = chunk_len
                while remaining > 0:
                    buf = f.read(min(65536, remaining))
                    if not buf:
                        break
                    self.wfile.write(buf)
                    remaining -= len(buf)

            if start == 0:
                self._notify_transfer(os.path.basename(target_file), file_size, "download")
        except (BrokenPipeError, ConnectionResetError):
            logger.debug("Клиент прервал скачивание файла %s", clean_target)
        except OSError as exc:
            logger.exception("Ошибка при отправке файла %s: %s", clean_target, exc)
            self.send_error(500, "Internal server error")

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
        self.send_header("Content-Disposition", _make_content_disposition(f"{folder_basename}.zip"))
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        stream = _ZipStream(self.wfile)
        try:
            with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_STORED) as zf:
                for root, _, files in os.walk(target_dir, followlinks=False):
                    for file in files:
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
        # Сначала собираем проверенный список файлов и только потом отправляем 200 OK (п. 8)
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
                arcname = os.path.relpath(full_path, self.real_storage).replace("\\", "/")
                if arcname not in seen_arcnames:
                    seen_arcnames.add(arcname)
                    valid_entries.append((full_path, arcname))
            elif os.path.isdir(full_path):
                for root, _, subfiles in os.walk(full_path, followlinks=False):
                    for f in subfiles:
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
        self.send_header("Content-Disposition", _make_content_disposition("selected_files.zip"))
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
            list_dir = os.listdir(real_path)
        except OSError as exc:
            logger.warning("Нет доступа к директории %s: %s", real_path, exc)
            self.send_error(403, "Access denied")
            return None

        list_dir.sort(key=lambda a: (not os.path.isdir(os.path.join(real_path, a)), a.lower()))

        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        theme = self._get_request_theme(params)
        lang = self.current_language
        displaypath = html.escape(urllib.parse.unquote(parsed.path))

        # Пагинация для быстрого открытия больших папок (DCIM) без пересчёта содержимого подпапок (п. 22)
        total_items = len(list_dir)
        total_pages = max(1, math.ceil(total_items / MAX_DIR_ITEMS_PER_PAGE))
        try:
            page = int(params.get("page", ["1"])[0])
        except ValueError:
            page = 1
        page = max(1, min(total_pages, page))
        start_idx = (page - 1) * MAX_DIR_ITEMS_PER_PAGE
        page_items = list_dir[start_idx : start_idx + MAX_DIR_ITEMS_PER_PAGE]

        r = []
        r.append('<!DOCTYPE html><html><head><meta charset="utf-8">')
        r.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
        r.append('<title>AirShare PC</title>')
        r.append(f'<style>{get_css(theme)}</style>')
        r.append(f'</head><body class="{theme}">')
        r.append('<div id="starfield"></div>')

        icon = "🌙" if theme == "light" else "☀️"
        r.append(f'<button type="button" id="themeBtn" class="theme-toggle" onclick="toggleTheme()">{icon}</button>')
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
        r.append('<p id="status" style="margin-top:12px;color:#667eea;min-height:20px;"></p></div>')

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
        r.append('<ul class="file-list">')

        folder_label = html.escape(tr("web_folder", lang))
        for name in page_items:
            fullname = os.path.join(real_path, name)
            rel_path = os.path.relpath(fullname, self.real_storage).replace("\\", "/")
            safe_val = html.escape(rel_path, quote=True)
            safe_name = html.escape(name)
            quoted_name = urllib.parse.quote(name, safe="")

            if os.path.isdir(fullname):
                r.append(
                    f'<li class="file-item">'
                    f'<input type="checkbox" class="checkbox" name="files" value="{safe_val}">'
                    f'<div class="file-info">'
                    f'<a class="file-link" href="{urllib.parse.quote(name + "/")}">📁 {safe_name}</a>'
                    f'<div class="file-meta">{folder_label}</div></div>'
                    f'<a class="download-btn" href="?zip={quoted_name}" title="ZIP">⬇</a>'
                    f'</li>'
                )
            else:
                try:
                    size_str = format_size(os.path.getsize(fullname))
                except OSError:
                    size_str = "—"

                r.append(
                    f'<li class="file-item">'
                    f'<input type="checkbox" class="checkbox" name="files" value="{safe_val}">'
                    f'<div class="file-info">'
                    f'<a class="file-link" href="{quoted_name}" target="_blank">📄 {safe_name}</a>'
                    f'<div class="file-meta">{size_str}</div></div>'
                    f'<a class="download-btn" href="?download={quoted_name}" download="{safe_name}">⬇</a>'
                    f'</li>'
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
            r.append('<div style="text-align:center;margin-top:20px;">')
            r.append(
                f'<button type="submit" class="upload-btn">{html.escape(tr("web_download_zip", lang))}</button>'
            )
            r.append('</div>')
        r.append('</form></div>')
        r.append(f'<script>{get_star_script()}{get_upload_script(lang)}{get_theme_script()}</script>')
        r.append('</body></html>')

        encoded = "\n".join(r).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        if "theme" in params and params["theme"]:
            self.send_header("Set-Cookie", f"airshare_theme={theme}; Path=/; Max-Age=31536000; SameSite=Lax")
        self.end_headers()
        return BytesIO(encoded)

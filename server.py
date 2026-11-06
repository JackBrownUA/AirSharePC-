# HTTP server for AirShare PC
# Handles file serving, ZIP streaming, device detection, and transfer notifications

import os
import html
import base64
import shutil
import zipfile
import mimetypes
import urllib.parse
from io import BytesIO
from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from config import SERVER_PORT, STORAGE_PATH
from utils import format_size, add_recent_ip
from web_ui import get_css, get_star_script, get_upload_script, get_theme_script


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


def _make_content_disposition(filename):
    clean_name = os.path.basename(filename).replace('"', "_").replace("\r", "").replace("\n", "")
    ascii_fallback = clean_name.encode("ascii", "ignore").decode("ascii").strip()
    if not ascii_fallback or ascii_fallback.startswith("."):
        _, ext = os.path.splitext(clean_name)
        ascii_fallback = f"download{ext}"
    utf8_quoted = urllib.parse.quote(clean_name, safe="")
    return f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{utf8_quoted}'


class AirShareHandler(SimpleHTTPRequestHandler):
    current_password = ""
    default_theme = "dark"
    on_client_connected = None
    on_file_transfer = None

    def __init__(self, *args, **kwargs):
        self.real_storage = os.path.realpath(STORAGE_PATH)
        super().__init__(*args, directory=self.real_storage, **kwargs)

    def _parse_client_device(self):
        try:
            client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
            if client_ip in ("127.0.0.1", "::1"):
                return
            ua = self.headers.get("User-Agent", "")
            device_title = "Desktop PC"
            os_badge = "Windows 11"
            if "Windows NT 10.0" in ua or "Windows NT 11.0" in ua:
                device_title = "Desktop PC"
                os_badge = "Windows 11"
            elif "Windows" in ua:
                device_title = "Desktop PC"
                os_badge = "Windows"
            elif "Macintosh" in ua or "Mac OS X" in ua:
                device_title = "MacBook"
                os_badge = "macOS"
            elif "Android" in ua:
                device_title = "Smartphone"
                os_badge = "Android"
            elif "iPhone" in ua or "iPad" in ua:
                device_title = "iPhone / iPad"
                os_badge = "iOS"
            elif "Linux" in ua:
                device_title = "Desktop PC"
                os_badge = "Linux"
            else:
                device_title = "Connected Device"
                os_badge = client_ip

            entry = f"{device_title} ({os_badge}) • {client_ip}"
            add_recent_ip(entry)
            if callable(self.on_client_connected):
                self.on_client_connected(device_title, os_badge, client_ip)
        except Exception:
            pass

    def _notify_transfer(self, filename, size_bytes, direction="done"):
        try:
            if callable(self.on_file_transfer):
                self.on_file_transfer(filename, format_size(size_bytes), direction)
        except Exception:
            pass

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
            except Exception:
                pass
        return self.default_theme if self.default_theme in ("light", "dark") else "dark"

    def is_authenticated(self):
        if not self.current_password:
            return True
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            raw = base64.b64decode(header[6:]).decode("utf-8")
            user, _, pwd = raw.partition(":")
            return pwd == self.current_password or user == self.current_password
        except Exception:
            return False

    def request_auth(self):
        body = "<h3>Требуется авторизация (AirShare PC)</h3>".encode("utf-8")
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="AirShare PC"')
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        if not self.is_authenticated():
            self.request_auth()
            return
        self._parse_client_device()
        super().do_HEAD()

    def do_GET(self):
        if not self.is_authenticated():
            self.request_auth()
            return

        self._parse_client_device()
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "download" in params and params["download"]:
            self.stream_single_file(parsed.path, params["download"][0])
            return

        if "zip" in params and params["zip"]:
            self.stream_folder_zip(parsed.path, params["zip"][0])
            return

        if "download_selected" in params or "files" in params:
            selected = params.get("files", [])
            if selected:
                self.download_selected_files(selected)
                return

        super().do_GET()

    def do_POST(self):
        if not self.is_authenticated():
            self.request_auth()
            return

        self._parse_client_device()
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        raw_name = None
        if "upload" in params and params["upload"]:
            raw_name = params["upload"][0]
        elif self.headers.get("X-File-Name"):
            raw_name = self.headers.get("X-File-Name")

        if not raw_name:
            self.send_error(400, "Missing filename")
            return

        filename = os.path.basename(urllib.parse.unquote(raw_name).strip())
        if not filename or filename in (".", ".."):
            self.send_error(400, "Invalid filename")
            return

        rel_dir = urllib.parse.unquote(parsed.path).lstrip("/")
        target_dir = os.path.realpath(os.path.join(self.real_storage, rel_dir))

        if not self._is_within_storage(target_dir) or not os.path.isdir(target_dir):
            self.send_error(403, "Forbidden")
            return

        dest_path = os.path.realpath(os.path.join(target_dir, filename))
        if not self._is_within_storage(dest_path):
            self.send_error(403, "Forbidden")
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0

        try:
            with open(dest_path, "wb") as f:
                remaining = length
                while remaining > 0:
                    chunk = self.rfile.read(min(65536, remaining))
                    if not chunk:
                        break
                    f.write(chunk)
                    remaining -= len(chunk)
            self._notify_transfer(filename, length, "upload")
            resp = b"OK"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
        except OSError as e:
            self.send_error(500, str(e))

    def stream_single_file(self, current_url_path, target_name):
        rel_dir = urllib.parse.unquote(current_url_path).lstrip("/")
        base_dir = os.path.realpath(os.path.join(self.real_storage, rel_dir))
        target_file = os.path.realpath(os.path.join(base_dir, urllib.parse.unquote(target_name)))

        if not self._is_within_storage(target_file) or not os.path.isfile(target_file):
            self.send_error(404, "File not found")
            return

        try:
            file_size = os.path.getsize(target_file)
            ctype, _ = mimetypes.guess_type(target_file)
            if not ctype:
                ctype = "application/octet-stream"

            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Content-Disposition", _make_content_disposition(os.path.basename(target_file)))
            self.end_headers()

            with open(target_file, "rb") as f:
                shutil.copyfileobj(f, self.wfile, length=65536)
            self._notify_transfer(os.path.basename(target_file), file_size, "download")
        except (BrokenPipeError, ConnectionResetError):
            pass
        except OSError as e:
            self.send_error(500, str(e))

    def stream_folder_zip(self, current_url_path, target_name):
        rel_dir = urllib.parse.unquote(current_url_path).lstrip("/")
        base_dir = os.path.realpath(os.path.join(self.real_storage, rel_dir))
        target_dir = os.path.realpath(os.path.join(base_dir, urllib.parse.unquote(target_name)))

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
                for root, _, files in os.walk(target_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, parent_dir)
                        try:
                            zf.write(full_path, arcname=rel_path)
                        except OSError:
                            continue
            self._notify_transfer(f"{folder_basename}.zip", stream.tell(), "download")
        except (BrokenPipeError, ConnectionResetError):
            pass

    def download_selected_files(self, files):
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", _make_content_disposition("selected_files.zip"))
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        stream = _ZipStream(self.wfile)
        try:
            with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_STORED) as zf:
                for item_rel_path in files:
                    clean_rel = urllib.parse.unquote(item_rel_path).replace("\\", "/").lstrip("/")
                    full_path = os.path.realpath(os.path.join(self.real_storage, clean_rel))
                    if not self._is_within_storage(full_path):
                        continue
                    if os.path.isfile(full_path):
                        try:
                            zf.write(full_path, arcname=os.path.basename(full_path))
                        except OSError:
                            continue
                    elif os.path.isdir(full_path):
                        parent_dir = os.path.dirname(full_path)
                        for root, _, subfiles in os.walk(full_path):
                            for f in subfiles:
                                fp = os.path.join(root, f)
                                try:
                                    zf.write(fp, arcname=os.path.relpath(fp, parent_dir))
                                except OSError:
                                    continue
            self._notify_transfer("selected_files.zip", stream.tell(), "download")
        except (BrokenPipeError, ConnectionResetError):
            pass

    def list_directory(self, path):
        real_path = os.path.realpath(path)
        if not self._is_within_storage(real_path):
            self.send_error(403, "Forbidden")
            return None

        try:
            list_dir = os.listdir(real_path)
        except OSError:
            self.send_error(404, "Access denied")
            return None

        list_dir.sort(key=lambda a: (not os.path.isdir(os.path.join(real_path, a)), a.lower()))
        r = []

        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        theme = self._get_request_theme(params)
        displaypath = html.escape(urllib.parse.unquote(parsed.path))

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
        r.append('<button type="button" class="upload-btn" onclick="triggerUpload()">⬆ Загрузить файлы на устройство</button>')
        r.append('<input type="file" id="up" multiple style="display:none" onchange="uploadFiles(this.files)">')
        if real_path != self.real_storage:
            r.append('<a class="upload-btn" href="../">⬅ Назад</a>')
        r.append('</div>')
        r.append('<p id="status" style="margin-top:12px;color:#667eea;min-height:20px;"></p></div>')

        r.append('<form id="fileForm" method="GET" onsubmit="return submitSelectedDownload(event)">')
        r.append('<input type="hidden" name="download_selected" value="1">')
        if list_dir:
            r.append(
                '<div class="toolbar">'
                '<label><input type="checkbox" class="checkbox" onchange="toggleSelectAll(this)"> Выбрать все</label>'
                f'<span>Всего объектов: {len(list_dir)}</span>'
                '</div>'
            )
        r.append('<ul class="file-list">')

        for name in list_dir:
            fullname = os.path.join(real_path, name)
            rel_path = os.path.relpath(fullname, self.real_storage).replace("\\", "/")
            safe_val = html.escape(rel_path, quote=True)
            safe_name = html.escape(name)
            quoted_name = urllib.parse.quote(name)

            if os.path.isdir(fullname):
                try:
                    with os.scandir(fullname) as entries:
                        count = sum(1 for _ in entries)
                    meta_info = f"Папка • {count} объект(ов)"
                except OSError:
                    meta_info = "Папка"

                r.append(
                    f'<li class="file-item">'
                    f'<input type="checkbox" class="checkbox" name="files" value="{safe_val}">'
                    f'<div class="file-info">'
                    f'<a class="file-link" href="{urllib.parse.quote(name + "/")}">📁 {safe_name}</a>'
                    f'<div class="file-meta">{meta_info}</div></div>'
                    f'<a class="download-btn" href="?zip={quoted_name}" title="Скачать папку ZIP">⬇</a>'
                    f'</li>'
                )
            else:
                try:
                    size_str = format_size(os.path.getsize(fullname))
                except OSError:
                    size_str = "Неизвестно"

                r.append(
                    f'<li class="file-item">'
                    f'<input type="checkbox" class="checkbox" name="files" value="{safe_val}">'
                    f'<div class="file-info">'
                    f'<a class="file-link" href="{quoted_name}" target="_blank">📄 {safe_name}</a>'
                    f'<div class="file-meta">{size_str}</div></div>'
                    f'<a class="download-btn" href="?download={quoted_name}" download="{safe_name}" title="Скачать файл">⬇</a>'
                    f'</li>'
                )

        r.append('</ul>')
        if list_dir:
            r.append('<div style="text-align:center;margin-top:20px;">')
            r.append('<button type="submit" class="upload-btn">⬇ Скачать выбранное (ZIP)</button>')
            r.append('</div>')
        r.append('</form></div>')
        r.append(f'<script>{get_star_script()}{get_upload_script()}{get_theme_script()}</script>')
        r.append('</body></html>')

        encoded = "\n".join(r).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        if "theme" in params and params["theme"]:
            self.send_header("Set-Cookie", f"airshare_theme={theme}; Path=/; Max-Age=31536000; SameSite=Lax")
        self.end_headers()
        return BytesIO(encoded)

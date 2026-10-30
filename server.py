"""
HTTP server for AirShare PC
Handles file serving, ZIP creation, and file uploads
"""

import os
import base64
import zipfile
import urllib.parse
from io import BytesIO
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from config import SERVER_PORT, STORAGE_PATH
from utils import format_size
from web_ui import get_css, get_star_script, get_upload_script, get_theme_script

class _ZipStream:
    """Streams ZIP directly to socket without loading into RAM"""
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

class AirShareHandler(SimpleHTTPRequestHandler):
    current_password = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STORAGE_PATH, **kwargs)

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
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="AirShare PC"')
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("<h3>Access required</h3>".encode("utf-8"))

    def do_HEAD(self):
        if not self.is_authenticated():
            self.request_auth()
            return
        super().do_HEAD()

    def do_GET(self):
        if not self.is_authenticated():
            self.request_auth()
            return

        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "zip" in params:
            self.stream_folder_zip(parsed.path, params["zip"][0])
            return

        if "download_selected" in params:
            self.download_selected_files(params.get("files", []))
            return

        super().do_GET()

    def do_POST(self):
        """Receive files from PC to phone"""
        if not self.is_authenticated():
            self.request_auth()
            return

        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "upload" not in params:
            self.send_error(400, "Missing filename")
            return

        filename = os.path.basename(urllib.parse.unquote(params["upload"][0]))
        rel_dir = urllib.parse.unquote(parsed.path).lstrip("/")
        target_dir = os.path.realpath(os.path.join(STORAGE_PATH, rel_dir))

        if os.path.commonpath([STORAGE_PATH, target_dir]) != STORAGE_PATH or not os.path.isdir(target_dir):
            self.send_error(403, "Forbidden")
            return

        dest_path = os.path.join(target_dir, filename)
        length = int(self.headers.get("Content-Length", 0))

        try:
            with open(dest_path, "wb") as f:
                remaining = length
                while remaining > 0:
                    chunk = self.rfile.read(min(65536, remaining))
                    if not chunk:
                        break
                    f.write(chunk)
                    remaining -= len(chunk)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        except OSError as e:
            self.send_error(500, str(e))

    def stream_folder_zip(self, current_url_path, target_name):
        """Download folder as ZIP archive"""
        rel_dir = urllib.parse.unquote(current_url_path).lstrip("/")
        base_dir = os.path.realpath(os.path.join(STORAGE_PATH, rel_dir))
        target_dir = os.path.realpath(os.path.join(base_dir, urllib.parse.unquote(target_name)))

        if os.path.commonpath([STORAGE_PATH, target_dir]) != STORAGE_PATH or not os.path.isdir(target_dir):
            self.send_error(404, "Directory not found")
            return

        folder_basename = os.path.basename(target_dir)
        parent_dir = os.path.dirname(target_dir)
        safe_filename = urllib.parse.quote(f"{folder_basename}.zip")

        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header(
            "Content-Disposition",
            f"attachment; filename=\"{folder_basename}.zip\"; filename*=UTF-8''{safe_filename}"
        )
        self.end_headers()

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
        except (BrokenPipeError, ConnectionResetError):
            pass

    def download_selected_files(self, files):
        """Download selected files as ZIP"""
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", "attachment; filename=\"selected_files.zip\"")
        self.end_headers()

        stream = _ZipStream(self.wfile)
        try:
            with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_STORED) as zf:
                for file_path in files:
                    full_path = os.path.realpath(os.path.join(STORAGE_PATH, urllib.parse.unquote(file_path)))
                    if os.path.commonpath([STORAGE_PATH, full_path]) == STORAGE_PATH and os.path.isfile(full_path):
                        zf.write(full_path, arcname=os.path.basename(full_path))
        except (BrokenPipeError, ConnectionResetError):
            pass

    def list_directory(self, path):
        """Display file list with theme support"""
        try:
            list_dir = os.listdir(path)
        except OSError:
            self.send_error(404, "Access denied")
            return None

        list_dir.sort(key=lambda a: a.lower())
        r = []
        displaypath = urllib.parse.unquote(urllib.parse.unquote(self.path))
        
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        theme = params.get("theme", ["dark"])[0]

        r.append('<!DOCTYPE html><html><head><meta charset="utf-8">')
        r.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
        r.append('<title>AirShare PC</title>')
        r.append(f'<style>{get_css(theme)}</style>')
        r.append('</head><body>')
        
        if theme == "dark":
            r.append('<div id="starfield"></div>')
        
        r.append(f'<button class="theme-toggle" onclick="toggleTheme()">{"" if theme == "light" else "☀️"}</button>')
        r.append('<div class="container">')
        r.append(f'<div class="header"><h1>AirShare PC</h1><p>{displaypath}</p>')
        r.append('<label class="upload-btn">Upload files to phone<input type="file" id="up" multiple style="display:none" onchange="uploadFiles(this.files)"></label>')
        r.append('<p id="status" style="margin-top:10px;color:#667eea;"></p></div>')
        r.append('<form id="fileForm"><ul class="file-list">')

        for name in list_dir:
            fullname = os.path.join(path, name)
            if os.path.isdir(fullname):
                try:
                    size = 0
                    count = 0
                    for dirpath, dirnames, filenames in os.walk(fullname):
                        count += len(filenames)
                        for filename in filenames:
                            try:
                                size += os.path.getsize(os.path.join(dirpath, filename))
                            except:
                                pass
                    meta_info = f"{count} items • {format_size(size)}"
                except OSError:
                    meta_info = "Folder"
                
                rel_path = os.path.relpath(fullname, STORAGE_PATH)
                r.append(f'<li class="file-item"><input type="checkbox" class="checkbox" name="files" value="{urllib.parse.quote(rel_path)}"><div class="file-info"><a class="file-link" href="{urllib.parse.quote(name + "/")}">{name}/</a><div class="file-meta">{meta_info}</div></div>')
                r.append(f'<a class="download-btn" href="?zip={urllib.parse.quote(rel_path)}" title="Download ZIP"></a></li>')
            else:
                try:
                    size_str = format_size(os.path.getsize(fullname))
                except OSError:
                    size_str = "Unknown"
                
                rel_path = os.path.relpath(fullname, STORAGE_PATH)
                r.append(f'<li class="file-item"><input type="checkbox" class="checkbox" name="files" value="{urllib.parse.quote(rel_path)}"><div class="file-info"><a class="file-link" href="{urllib.parse.quote(name)}">{name}</a><div class="file-meta">{size_str}</div></div></li>')

        r.append('</ul><button type="submit" class="upload-btn" style="margin-top:20px;">Download selected</button></form></div>')
        r.append(f'<script>{get_star_script()}{get_upload_script()}{get_theme_script()}</script>')
        r.append('</body></html>')

        encoded = '\n'.join(r).encode('utf-8')
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        return BytesIO(encoded)

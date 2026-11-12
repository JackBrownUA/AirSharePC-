# Автоматические тесты безопасности (security.py), плеера (player_ui.py), PWA и поиска (pwa_search.py), Android-моста (android_bridge.py), графа импортов (main.py), POST /login, SHA-256 и p4a_hook (v1.3.5)

import ast
import base64
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
import types
import unittest
import urllib.parse
import zipfile
from pathlib import Path
from unittest import mock

import android_bridge
import config
import i18n
import p4a_hook
import player_ui
import pwa_search
import security
import server
import utils
import web_ui


class _DummySocket:
    def __init__(self, req_bytes=b""):
        self._rfile = io.BytesIO(req_bytes)
        self._wfile = io.BytesIO()

    def makefile(self, mode, *args, **kwargs):
        if "r" in mode:
            return self._rfile
        return self._wfile

    def sendall(self, data):
        self._wfile.write(data)

    def settimeout(self, timeout):
        self.timeout = timeout

    def close(self):
        pass


def _run_request(storage_dir, raw_request, client_ip="192.168.1.55"):
    sock = _DummySocket(raw_request)
    with mock.patch.object(server, "STORAGE_PATH", storage_dir):
        server.AirShareHandler(sock, (client_ip, 54321), None)
    return sock._wfile.getvalue()


def _basic_auth_header(user, pwd):
    token = base64.b64encode(f"{user}:{pwd}".encode("utf-8")).decode("ascii")
    return f"Authorization: Basic {token}\r\n"


class AirShareSecurityAndQualityTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.storage_dir = os.path.realpath(os.path.join(self.tmp_dir.name, "storage"))
        os.makedirs(self.storage_dir, exist_ok=True)
        self.settings_file = os.path.join(self.tmp_dir.name, ".airshare_settings.json")

        self.patcher_storage = mock.patch.object(config, "STORAGE_PATH", self.storage_dir)
        self.patcher_utils_storage = mock.patch.object(utils, "STORAGE_PATH", self.storage_dir)
        self.patcher_settings = mock.patch.object(utils, "SETTINGS_FILE", self.settings_file)
        self.patcher_storage.start()
        self.patcher_utils_storage.start()
        self.patcher_settings.start()

        utils._seen_recent_ips.clear()
        server.AirShareHandler.reset_rate_limits()
        server.AirShareHandler._disconnected_ips.clear()
        server.AirShareHandler._notified_ips.clear()
        server.AirShareHandler._hash_cache.clear()
        server.AirShareHandler.current_password = "918273"
        server.AirShareHandler.current_language = "en"

    def tearDown(self):
        self.patcher_settings.stop()
        self.patcher_utils_storage.stop()
        self.patcher_storage.stop()
        self.tmp_dir.cleanup()

    def test_01_random_pin_generation_and_compromised_replacement(self):
        s1 = utils.load_settings()
        self.assertEqual(len(s1["password"]), 6)
        self.assertTrue(s1["password"].isdigit())
        self.assertNotEqual(s1["password"], "06102000")

        with open(self.settings_file, "w", encoding="utf-8") as f:
            f.write('{"password": "06102000", "port": 8080}')
        s2 = utils.load_settings()
        self.assertNotEqual(s2["password"], "06102000")
        self.assertEqual(len(s2["password"]), 6)

        saved_empty = utils.save_settings(password="")
        self.assertTrue(len(saved_empty["password"]) == 6 and saved_empty["password"].isdigit())

    def test_02_corrupted_json_creates_backup(self):
        with open(self.settings_file, "w", encoding="utf-8") as f:
            f.write("{corrupted_json:")
        loaded = utils.load_settings()
        self.assertTrue(os.path.isfile(self.settings_file + ".bak"))
        self.assertEqual(len(loaded["password"]), 6)

    def test_03_auth_checks_only_password_and_blocks_brute_force(self):
        bad_req = (
            "GET / HTTP/1.1\r\nHost: localhost\r\n"
            + _basic_auth_header("918273", "wrong_pass")
            + "\r\n"
        ).encode("utf-8")
        resp = _run_request(self.storage_dir, bad_req, client_ip="10.0.0.99")
        self.assertIn(b"401", resp.splitlines()[0])

        for _ in range(4):
            _run_request(self.storage_dir, bad_req, client_ip="10.0.0.99")
        resp_blocked = _run_request(self.storage_dir, bad_req, client_ip="10.0.0.99")
        self.assertIn(b"429", resp_blocked.splitlines()[0])

        good_req = (
            "GET / HTTP/1.1\r\nHost: localhost\r\n"
            + _basic_auth_header("airshare", "918273")
            + "\r\n"
        ).encode("utf-8")
        resp_ok = _run_request(self.storage_dir, good_req, client_ip="10.0.0.50")
        self.assertIn(b"200 OK", resp_ok.splitlines()[0])

    def test_04_upload_no_overwrite_and_sha256_verification_and_part_hidden(self):
        req_no_len = (
            "POST /?upload=empty.txt HTTP/1.1\r\nHost: localhost\r\n"
            + _basic_auth_header("airshare", "918273")
            + "\r\n"
        ).encode("utf-8")
        resp_411 = _run_request(self.storage_dir, req_no_len)
        self.assertIn(b"411", resp_411.splitlines()[0])
        self.assertFalse(os.path.exists(os.path.join(self.storage_dir, "empty.txt")))

        bad_sha_body = b"corrupted_payload"
        bad_sha_req = (
            "POST /?upload=bad_hash.bin HTTP/1.1\r\nHost: localhost\r\n"
            f"Content-Length: {len(bad_sha_body)}\r\n"
            "X-Content-SHA256: 0000000000000000000000000000000000000000000000000000000000000000\r\n"
            + _basic_auth_header("airshare", "918273")
            + "\r\n"
        ).encode("utf-8") + bad_sha_body
        resp_422 = _run_request(self.storage_dir, bad_sha_req)
        self.assertIn(b"422", resp_422.splitlines()[0])
        self.assertFalse(os.path.exists(os.path.join(self.storage_dir, "bad_hash.bin")))

        prog_events = []
        server.AirShareHandler.on_transfer_progress = lambda fn, cur, tot, d: prog_events.append((fn, cur, tot, d))
        for idx, body in enumerate([b"first", b"second", b"third"]):
            valid_sha = hashlib.sha256(body).hexdigest()
            req = (
                "POST /?upload=report.txt HTTP/1.1\r\nHost: localhost\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"X-Content-SHA256: {valid_sha}\r\n"
                + _basic_auth_header("airshare", "918273")
                + "\r\n"
            ).encode("utf-8") + body
            resp = _run_request(self.storage_dir, req)
            self.assertIn(b"200 OK", resp.splitlines()[0], f"Upload #{idx} failed")

        self.assertTrue(len(prog_events) >= 3)

        hash_req = (
            "GET /?hash=report.txt HTTP/1.1\r\nHost: localhost\r\n"
            + _basic_auth_header("airshare", "918273")
            + "\r\n"
        ).encode("utf-8")
        hash_resp = _run_request(self.storage_dir, hash_req)
        _, _, hash_body = hash_resp.partition(b"\r\n\r\n")
        hash_data = json.loads(hash_body.decode("utf-8"))
        self.assertEqual(hash_data["sha256"], hashlib.sha256(b"first").hexdigest())

        with open(os.path.join(self.storage_dir, ".airshare_upload_abc.part"), "wb") as f:
            f.write(b"partial")
        list_req = (
            "GET / HTTP/1.1\r\nHost: localhost\r\n"
            + _basic_auth_header("airshare", "918273")
            + "\r\n"
        ).encode("utf-8")
        list_resp = _run_request(self.storage_dir, list_req)
        self.assertNotIn(b".airshare_upload_abc.part", list_resp)

    def test_05_percent_and_cyrillic_filenames_not_double_decoded(self):
        for fname in ("скидка50%.pdf", "a%20b.txt"):
            payload = f"content-of-{fname}".encode("utf-8")
            q_name = urllib.parse.quote(fname, safe="")
            post_req = (
                f"POST /?upload={q_name} HTTP/1.1\r\nHost: localhost\r\n"
                f"Content-Length: {len(payload)}\r\n"
                + _basic_auth_header("airshare", "918273")
                + "\r\n"
            ).encode("utf-8") + payload
            post_resp = _run_request(self.storage_dir, post_req)
            self.assertIn(b"200 OK", post_resp.splitlines()[0])
            expected_path = os.path.join(self.storage_dir, fname)
            self.assertTrue(os.path.isfile(expected_path), f"Missing uploaded file {fname}")

            get_req = (
                f"GET /?download={q_name} HTTP/1.1\r\nHost: localhost\r\n"
                + _basic_auth_header("airshare", "918273")
                + "\r\n"
            ).encode("utf-8")
            get_resp = _run_request(self.storage_dir, get_req)
            header_part, _, body_part = get_resp.partition(b"\r\n\r\n")
            self.assertIn(b"200 OK", header_part.splitlines()[0])
            self.assertEqual(body_part, payload)

    def test_06_path_traversal_and_zip_relative_paths_and_symlinks(self):
        sub_a = os.path.join(self.storage_dir, "folderA")
        sub_b = os.path.join(self.storage_dir, "folderB")
        os.makedirs(sub_a, exist_ok=True)
        os.makedirs(sub_b, exist_ok=True)
        with open(os.path.join(sub_a, "same.txt"), "wb") as f:
            f.write(b"from_A")
        with open(os.path.join(sub_b, "same.txt"), "wb") as f:
            f.write(b"from_B")

        outside_file = os.path.join(self.tmp_dir.name, "secret_outside.txt")
        with open(outside_file, "wb") as f:
            f.write(b"TOP_SECRET")
        symlink_path = os.path.join(sub_a, "evil_link.txt")
        os.symlink(outside_file, symlink_path)

        req_zip = (
            "GET /?download_selected=1&files=folderA/same.txt&files=folderB/same.txt"
            "&files=folderA/evil_link.txt&files=../../secret_outside.txt HTTP/1.1\r\n"
            "Host: localhost\r\n"
            + _basic_auth_header("airshare", "918273")
            + "\r\n"
        ).encode("utf-8")
        resp_zip = _run_request(self.storage_dir, req_zip)
        _, _, zip_bytes = resp_zip.partition(b"\r\n\r\n")
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            names = set(zf.namelist())
            self.assertIn("folderA/same.txt", names)
            self.assertIn("folderB/same.txt", names)
            self.assertNotIn("folderA/evil_link.txt", names)
            self.assertNotIn("secret_outside.txt", names)
            self.assertEqual(zf.read("folderA/same.txt"), b"from_A")
            self.assertEqual(zf.read("folderB/same.txt"), b"from_B")

    def test_07_http_range_206_shortcut_and_disconnect(self):
        video_path = os.path.join(self.storage_dir, "clip.mp4")
        with open(video_path, "wb") as f:
            f.write(b"0123456789ABCDEFGHIJ")

        range_req = (
            "GET /?download=clip.mp4 HTTP/1.1\r\nHost: localhost\r\n"
            "Range: bytes=5-14\r\n"
            + _basic_auth_header("airshare", "918273")
            + "\r\n"
        ).encode("utf-8")
        resp = _run_request(self.storage_dir, range_req, client_ip="192.168.1.77")
        hdr, _, body = resp.partition(b"\r\n\r\n")
        self.assertIn(b"206 Partial Content", hdr.splitlines()[0])
        self.assertIn(b"Content-Range: bytes 5-14/20", hdr)
        self.assertIn(b"X-Content-Type-Options: nosniff", hdr)
        self.assertEqual(body, b"56789ABCDE")

        sc_resp = _run_request(self.storage_dir, b"GET /?shortcut=1 HTTP/1.1\r\nHost: 192.168.50.98:8080\r\n\r\n")
        self.assertIn(b"[InternetShortcut]", sc_resp)
        self.assertIn(b"URL=http://192.168.50.98:8080/", sc_resp)

        server.AirShareHandler.set_ip_disconnected("192.168.1.77", True)
        resp_disc = _run_request(self.storage_dir, range_req, client_ip="192.168.1.77")
        self.assertIn(b"403", resp_disc.splitlines()[0])

    def test_08_modular_architecture_js_syntax_and_all_i18n_keys_used(self):
        self.assertTrue(hasattr(security, "verify_sha256_digest"))
        self.assertTrue(hasattr(player_ui, "get_media_modal_html"))
        self.assertTrue(hasattr(pwa_search, "serve_pwa_asset"))
        self.assertTrue(hasattr(android_bridge, "set_android_foreground_notification"))
        self.assertFalse(utils.is_private_lan_ip("100.71.184.228"))
        self.assertFalse(utils.is_private_lan_ip("127.0.0.1"))
        self.assertTrue(utils.is_private_lan_ip("192.168.1.55"))
        self.assertEqual(utils.get_sslip_domain("192.168.50.72"), "192-168-50-72.sslip.io")
        self.assertEqual(utils.format_size(604), "604 B")

        if shutil.which("node"):
            for code in ("en", "es", "de", "lt", "ru", "uk"):
                for name, js_code in (
                    (f"star_{code}", web_ui.get_star_script()),
                    (f"theme_{code}", web_ui.get_theme_script()),
                    (f"upload_{code}", web_ui.get_upload_script(code)),
                ):
                    js_path = os.path.join(self.tmp_dir.name, f"{name}.js")
                    Path(js_path).write_text(js_code, encoding="utf-8")
                    res = subprocess.run(["node", "--check", js_path], capture_output=True, text=True)
                    self.assertEqual(res.returncode, 0, f"JS syntax error in {name}: {res.stderr}")

        en_keys = set(i18n.TRANSLATIONS["en"].keys())
        for code in ("en", "es", "de", "lt", "ru", "uk"):
            self.assertEqual(set(i18n.TRANSLATIONS[code].keys()), en_keys, f"Key mismatch in {code}")

        all_source = ""
        for fname in (
            "main.py",
            "server.py",
            "web_ui.py",
            "player_ui.py",
            "security.py",
            "pwa_search.py",
            "android_bridge.py",
            "ui_widgets.py",
            "utils.py",
        ):
            all_source += Path(fname).read_text(encoding="utf-8") + "\n"
        for k in en_keys:
            if k == "web_install_pwa":
                continue
            self.assertIn(f'"{k}"', all_source.replace("'", '"'), f"Unused translation key: {k}")

    def test_09_post_login_per_device_token_pwa_search_and_cinema_player(self):
        resp_login = _run_request(self.storage_dir, b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n", client_ip="192.168.50.56")
        self.assertIn(b"401", resp_login.splitlines()[0])
        self.assertIn(b'action="/login"', resp_login)
        self.assertIn(b'id="pinEyeBtn"', resp_login)
        self.assertIn(b'id="langGlobeBtn"', resp_login)
        self.assertIn(b'id="shortcutBtn"', resp_login)
        self.assertNotIn(b"httpsSetupBtn", resp_login)

        post_body = b"pin=918273&next=%2F"
        post_login_req = (
            "POST /login HTTP/1.1\r\nHost: localhost\r\n"
            "Content-Type: application/x-www-form-urlencoded\r\n"
            f"Content-Length: {len(post_body)}\r\n\r\n"
        ).encode("utf-8") + post_body
        resp_post = _run_request(self.storage_dir, post_login_req, client_ip="192.168.50.56")
        hdr_lines = resp_post.partition(b"\r\n\r\n")[0].decode("utf-8").splitlines()
        self.assertIn("303", hdr_lines[0])
        cookie_line = [line for line in hdr_lines if line.lower().startswith("set-cookie: airshare_auth=")][0]
        cookie_kv = cookie_line.split(":", 1)[1].strip().split(";")[0]

        hijack_req = f"GET / HTTP/1.1\r\nHost: localhost\r\nCookie: {cookie_kv}\r\n\r\n".encode("utf-8")
        resp_hijack = _run_request(self.storage_dir, hijack_req, client_ip="192.168.50.99")
        self.assertIn(b"401", resp_hijack.splitlines()[0])

        with open(os.path.join(self.storage_dir, "20250819_144102.mp4"), "wb") as f:
            f.write(b"0123456789ABCDEF" * 64)
        req_with_cookie = f"GET /?lang=ru HTTP/1.1\r\nHost: localhost\r\nCookie: {cookie_kv}\r\n\r\n".encode("utf-8")
        resp_dir = _run_request(self.storage_dir, req_with_cookie, client_ip="192.168.50.56")
        self.assertIn(b"200 OK", resp_dir.splitlines()[0])
        self.assertIn(b'id="ambilightCanvas"', resp_dir)
        self.assertIn(b'id="uploadProgressDock"', resp_dir)
        self.assertIn(b'id="fileSearchInput"', resp_dir)
        self.assertIn(b'id="scrubCanvas"', resp_dir)
        self.assertIn(b'id="shortcutBtn"', resp_dir)

        search_req = f"GET /?q=144102&ajax=1 HTTP/1.1\r\nHost: localhost\r\nCookie: {cookie_kv}\r\n\r\n".encode("utf-8")
        search_resp = _run_request(self.storage_dir, search_req, client_ip="192.168.50.56")
        _, _, search_body = search_resp.partition(b"\r\n\r\n")
        search_json = json.loads(search_body.decode("utf-8"))
        self.assertEqual(len(search_json["results"]), 1)
        self.assertEqual(search_json["results"][0]["name"], "20250819_144102.mp4")

        pwa_resp = _run_request(self.storage_dir, b"GET /manifest.webmanifest HTTP/1.1\r\nHost: localhost\r\n\r\n")
        self.assertIn(b"200 OK", pwa_resp.splitlines()[0])
        self.assertIn(b'"display": "standalone"', pwa_resp)

    def test_10_p4a_hook_targets_api_35_clean_manifest_and_sdl_keep_alive(self):
        self.assertEqual(config.APP_VERSION, "1.3.5")
        self.assertEqual(p4a_hook.TARGET_API, "35")

        main_code = Path("main.py").read_text(encoding="utf-8")
        self.assertNotIn('shorten_from="middle"', main_code)
        self.assertNotIn("request_ignore_battery_optimizations", main_code)
        self.assertNotIn("tls_cert", main_code)
        nav_match = re.search(r"def _on_nav_transfer\(.*?(?=\n    def )", main_code, re.S)
        self.assertIsNotNone(nav_match)
        self.assertNotIn("toggle_server", nav_match.group(0))

        fake_dist = Path(self.tmp_dir.name) / "fake_dist"
        (fake_dist / "src" / "main" / "java" / "org" / "libsdl" / "app").mkdir(parents=True, exist_ok=True)
        props_file = fake_dist / "project.properties"
        props_file.write_text("target=android-33\nAPP_PLATFORM=24\n", encoding="utf-8")

        gradle_file = fake_dist / "build.gradle"
        gradle_file.write_text(
            "android {\n    compileSdkVersion 33\n    defaultConfig {\n        minSdkVersion 24\n        targetSdkVersion 33\n    }\n}\n",
            encoding="utf-8",
        )

        manifest_file = fake_dist / "src" / "main" / "AndroidManifest.xml"
        manifest_file.write_text(
            '<manifest><uses-sdk android:minSdkVersion="24" android:targetSdkVersion="33" />'
            '<uses-permission android:name="android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS" />'
            '<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />'
            '<application android:requestLegacyExternalStorage="true"></application></manifest>',
            encoding="utf-8",
        )

        hid_file = fake_dist / "src" / "main" / "java" / "org" / "libsdl" / "app" / "HIDDeviceManager.java"
        hid_file.write_text(
            "class HIDDeviceManager {\n"
            "  void init() {\n"
            "    mContext.registerReceiver(mUsbBroadcast, filter);\n"
            "    mContext.registerReceiver(mBluetoothBroadcast, filter);\n"
            "  }\n"
            "}\n",
            encoding="utf-8",
        )

        sdl_file = fake_dist / "src" / "main" / "java" / "org" / "libsdl" / "app" / "SDLActivity.java"
        sdl_file.write_text(
            "class SDLActivity {\n"
            "  public static boolean mIsPaused = false;\n"
            "  static void handlePause() { SDLActivity.nativePause(); }\n"
            "  static void handleResume() { SDLActivity.nativeResume(); }\n"
            "}\n",
            encoding="utf-8",
        )
        counts = p4a_hook.patch_build_tree(fake_dist)
        self.assertEqual(counts["props"], 1)
        self.assertEqual(counts["gradle"], 1)
        self.assertEqual(counts["manifest"], 1)
        self.assertEqual(counts["hid"], 1)
        self.assertEqual(counts["sdl"], 1)
        self.assertNotIn("SDLActivity.nativePause();", sdl_file.read_text(encoding="utf-8"))
        self.assertIn("targetSdkVersion 35", gradle_file.read_text(encoding="utf-8"))
        self.assertIn('android:targetSdkVersion="35"', manifest_file.read_text(encoding="utf-8"))
        self.assertNotIn("REQUEST_IGNORE_BATTERY_OPTIMIZATIONS", manifest_file.read_text(encoding="utf-8"))
        self.assertNotIn("FOREGROUND_SERVICE", manifest_file.read_text(encoding="utf-8"))

    def test_11_import_graph_ruff_and_dynamic_handler_startup(self):
        # 1. Проверяем граф импортов всех .py файлов (защита от ModuleNotFoundError при запуске на Android)
        external_allowed = {"kivy", "jnius", "android"}
        stdlib = sys.stdlib_module_names
        py_files = {p.stem: p for p in Path(".").glob("*.py")}

        for _stem, p in sorted(py_files.items()):
            src = p.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=str(p))

            # Проверка F541 (f-строки без плейсхолдеров)
            for tok in tokenize.generate_tokens(io.StringIO(src).readline):
                if tok.type == tokenize.STRING:
                    s = tok.string
                    prefix = ""
                    for ch in s:
                        if ch in "\"'":
                            break
                        prefix += ch.lower()
                    if "f" in prefix and "{" not in s:
                        self.fail(f"F541 f-string without placeholders in {p}:{tok.start[0]}")

            # Проверка существования всех импортируемых локальных модулей и символов
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".")[0]
                        self.assertTrue(
                            root in stdlib or root in external_allowed or root in py_files,
                            f"Missing module {alias.name} imported in {p}:{node.lineno}",
                        )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    root = node.module.split(".")[0]
                    if root not in stdlib and root not in external_allowed:
                        self.assertIn(root, py_files, f"Missing module {node.module} imported in {p}:{node.lineno}")
                        target_tree = ast.parse(py_files[root].read_text(encoding="utf-8"))
                        defined = set()
                        for tnode in ast.walk(target_tree):
                            if isinstance(tnode, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                                defined.add(tnode.name)
                            elif isinstance(tnode, ast.Assign):
                                for t in tnode.targets:
                                    if isinstance(t, ast.Name):
                                        defined.add(t.id)
                            elif isinstance(tnode, ast.Import):
                                for a in tnode.names:
                                    defined.add(a.asname or a.name.split(".")[0])
                            elif isinstance(tnode, ast.ImportFrom):
                                for a in tnode.names:
                                    defined.add(a.asname or a.name)
                        for alias in node.names:
                            self.assertIn(
                                alias.name,
                                defined,
                                f"Missing symbol {alias.name} from {root} in {p}:{node.lineno}",
                            )

        # 2. Проверяем импорт main.py с заглушками Kivy и работу DynamicAirShareHandler
        dummy_kivy_mods = {}
        for mod_name in (
            "kivy",
            "kivy.animation",
            "kivy.app",
            "kivy.clock",
            "kivy.core",
            "kivy.core.window",
            "kivy.core.clipboard",
            "kivy.graphics",
            "kivy.metrics",
            "kivy.properties",
            "kivy.uix",
            "kivy.uix.anchorlayout",
            "kivy.uix.behaviors",
            "kivy.uix.boxlayout",
            "kivy.uix.floatlayout",
            "kivy.uix.image",
            "kivy.uix.label",
            "kivy.uix.scrollview",
            "kivy.uix.stencilview",
            "kivy.uix.textinput",
            "kivy.uix.widget",
            "kivy.utils",
        ):
            class _KivyMod(types.ModuleType):
                def __getattr__(self, name):
                    return type(name, (object,), {"__init__": lambda s, *a, **kw: None})
            m = _KivyMod(mod_name)
            for cls_name in (
                "Animation",
                "App",
                "AnchorLayout",
                "ButtonBehavior",
                "BoxLayout",
                "FloatLayout",
                "Image",
                "Label",
                "ScrollView",
                "StencilView",
                "TextInput",
                "Widget",
                "Color",
                "Ellipse",
                "Line",
                "Rectangle",
                "RoundedRectangle",
                "Scale",
                "PushMatrix",
                "PopMatrix",
                "Translate",
            ):
                setattr(m, cls_name, type(cls_name, (object,), {"__init__": lambda self, *a, **kw: None}))
            for prop_name in ("BooleanProperty", "ColorProperty", "ListProperty", "NumericProperty", "StringProperty"):
                setattr(m, prop_name, lambda default=None, **kw: default)
            m.Clock = mock.MagicMock()
            m.Window = mock.MagicMock()
            m.Clipboard = mock.MagicMock()
            m.dp = lambda x: x
            m.sp = lambda x: x
            m.platform = "linux"
            dummy_kivy_mods[mod_name] = m

        with mock.patch.dict(sys.modules, dummy_kivy_mods):
            import importlib
            import main as app_main
            importlib.reload(app_main)
            app_main.DynamicAirShareHandler.active_storage_path = self.storage_dir
            app_main.DynamicAirShareHandler.current_password = "918273"
            sock = _DummySocket(
                ("GET / HTTP/1.1\r\nHost: localhost\r\n" + _basic_auth_header("airshare", "918273") + "\r\n").encode(
                    "utf-8"
                )
            )
            app_main.DynamicAirShareHandler(sock, ("192.168.1.55", 54321), None)
            self.assertIn(b"200 OK", sock._wfile.getvalue().splitlines()[0])



    def test_12_ui_radius_clamp_modal_reset_and_session_cap(self):
        uw_src = Path("ui_widgets.py").read_text(encoding="utf-8")
        self.assertIn("self.height * 0.48", uw_src)
        self.assertNotIn("1794233814531.jpg", uw_src)

        m_src = Path("main.py").read_text(encoding="utf-8")
        self.assertIn("setattr(self, \"active_modal\", None)", m_src)
        self.assertIn("del self.transfer_history[50:]", m_src)

        sessions = {}
        lock = server.threading.Lock()
        for i in range(300):
            security.create_device_session_token("sec", sessions, lock, f"192.168.1.{i % 250}", "918273")
        self.assertLessEqual(len(sessions), 256)


if __name__ == "__main__":
    unittest.main()

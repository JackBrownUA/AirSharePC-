# Автоматические тесты безопасности, HTTP Range (206), локализации (i18n), фильтрации Wi-Fi IP, ZIP-архивации и хука сборки p4a_hook

import base64
import io
import os
import tempfile
import unittest
import urllib.parse
import zipfile
from pathlib import Path
from unittest import mock

import config
import i18n
import p4a_hook
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
        server.AirShareHandler.current_password = "918273"

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

    def test_04_upload_no_overwrite_and_411_without_content_length(self):
        req_no_len = (
            "POST /?upload=empty.txt HTTP/1.1\r\nHost: localhost\r\n"
            + _basic_auth_header("airshare", "918273")
            + "\r\n"
        ).encode("utf-8")
        resp_411 = _run_request(self.storage_dir, req_no_len)
        self.assertIn(b"411", resp_411.splitlines()[0])
        self.assertFalse(os.path.exists(os.path.join(self.storage_dir, "empty.txt")))

        for idx, body in enumerate([b"first", b"second", b"third"]):
            req = (
                "POST /?upload=report.txt HTTP/1.1\r\nHost: localhost\r\n"
                f"Content-Length: {len(body)}\r\n"
                + _basic_auth_header("airshare", "918273")
                + "\r\n"
            ).encode("utf-8") + body
            resp = _run_request(self.storage_dir, req)
            self.assertIn(b"200 OK", resp.splitlines()[0], f"Upload #{idx} failed")

        with open(os.path.join(self.storage_dir, "report.txt"), "rb") as f:
            self.assertEqual(f.read(), b"first")
        with open(os.path.join(self.storage_dir, "report (1).txt"), "rb") as f:
            self.assertEqual(f.read(), b"second")
        with open(os.path.join(self.storage_dir, "report (2).txt"), "rb") as f:
            self.assertEqual(f.read(), b"third")

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

    def test_07_http_range_206_and_security_headers_and_disconnect(self):
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

        # Проверяем кнопку «Отключить» для IP
        server.AirShareHandler.set_ip_disconnected("192.168.1.77", True)
        resp_disc = _run_request(self.storage_dir, range_req, client_ip="192.168.1.77")
        self.assertIn(b"403", resp_disc.splitlines()[0])

    def test_08_wifi_ip_filter_and_integer_bytes_and_i18n(self):
        # CG-NAT мобильного оператора (100.71.184.228) не должен считаться Wi-Fi LAN IP
        self.assertFalse(utils.is_private_lan_ip("100.71.184.228"))
        self.assertFalse(utils.is_private_lan_ip("127.0.0.1"))
        self.assertTrue(utils.is_private_lan_ip("192.168.1.55"))
        self.assertTrue(utils.is_private_lan_ip("10.246.82.39"))
        self.assertEqual(utils.format_size(604), "604 B")
        for code in ("en", "es", "de", "lt", "ru", "uk"):
            self.assertTrue(len(i18n.tr("connect", code)) > 0)
        css_light = web_ui.get_css("light")
        self.assertIn("color-scheme: light", css_light)

    def test_09_cookie_pin_auth_and_no_false_pin_alert(self):
        # 1. Простой GET / без пароля возвращает страницу ввода PIN (401), но НЕ увеличивает счётчик ошибок и не шлёт ложный алерт
        alerts = []
        server.AirShareHandler.on_bad_pin_attempt = lambda ip: alerts.append(ip)
        for _ in range(7):
            resp_login = _run_request(self.storage_dir, b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n", client_ip="192.168.50.56")
            self.assertIn(b"401", resp_login.splitlines()[0])
            self.assertIn(b"skyCanvas", resp_login)
        self.assertEqual(len(alerts), 0)

        # 2. Вход по ссылке ?pin=918273 возвращает 302 редирект и устанавливает сессионную Cookie airshare_auth
        resp_pin = _run_request(self.storage_dir, b"GET /?pin=918273 HTTP/1.1\r\nHost: localhost\r\n\r\n", client_ip="192.168.50.56")
        hdr_lines = resp_pin.partition(b"\r\n\r\n")[0].decode("utf-8").splitlines()
        self.assertIn("302", hdr_lines[0])
        cookie_line = [line for line in hdr_lines if line.lower().startswith("set-cookie: airshare_auth=")][0]
        cookie_kv = cookie_line.split(":", 1)[1].strip().split(";")[0]

        # 3. Последующие переходы по папкам и POST-загрузки с Cookie проходят с кодом 200 без Basic Auth
        req_with_cookie = f"GET / HTTP/1.1\r\nHost: localhost\r\nCookie: {cookie_kv}\r\n\r\n".encode("utf-8")
        resp_dir = _run_request(self.storage_dir, req_with_cookie, client_ip="192.168.50.56")
        self.assertIn(b"200 OK", resp_dir.splitlines()[0])
        self.assertIn(b"Crafted by JackBrownUA", resp_dir)
        # 4. Проверяем наличие тумблера Предпросмотр (previewToggle), ленивых миниатюр data-src и заголовков стриминга видео
        with open(os.path.join(self.storage_dir, "20250819_113031.jpg"), "wb") as f:
            f.write(b"\xff\xd8\xff\xe0fakejpeg")
        with open(os.path.join(self.storage_dir, "20250819_144102.mp4"), "wb") as f:
            f.write(b"0123456789ABCDEF" * 64)
        resp_with_media = _run_request(self.storage_dir, req_with_cookie, client_ip="192.168.50.56")
        self.assertIn(b'id="previewToggle"', resp_with_media)
        self.assertIn(b'data-src="20250819_113031.jpg"', resp_with_media)
        self.assertIn(b'data-src="20250819_144102.mp4#t=0.5"', resp_with_media)

        head_req = f"HEAD /20250819_144102.mp4 HTTP/1.1\r\nHost: localhost\r\nCookie: {cookie_kv}\r\n\r\n".encode("utf-8")
        head_resp = _run_request(self.storage_dir, head_req, client_ip="192.168.50.56")
        self.assertIn(b"Accept-Ranges: bytes", head_resp)
        self.assertIn(b"Cache-Control: private, max-age=3600", head_resp)

    def test_10_p4a_hook_patches_project_properties_and_kivy_shorten_from_valid(self):
        # 1. Проверяем, что в main.py и ui_widgets.py нигде не передаётся невалидный для Kivy shorten_from="middle"
        main_code = Path("main.py").read_text(encoding="utf-8")
        self.assertNotIn('shorten_from="middle"', main_code)
        self.assertIn('shorten_from="center"', main_code)

        # 2. Проверяем, что p4a_hook корректно патчит закэшированный dist (project.properties, build.gradle, AndroidManifest.xml и HIDDeviceManager.java)
        fake_dist = Path(self.tmp_dir.name) / "fake_dist"
        (fake_dist / "src" / "main" / "java" / "org" / "libsdl" / "app").mkdir(parents=True, exist_ok=True)
        props_file = fake_dist / "project.properties"
        props_file.write_text("target=android-33\nAPP_PLATFORM=24\n", encoding="utf-8")

        gradle_file = fake_dist / "build.gradle"
        gradle_file.write_text("android {\n    compileSdkVersion 33\n    defaultConfig {\n        minSdkVersion 24\n        targetSdkVersion 33\n    }\n}\n", encoding="utf-8")

        manifest_file = fake_dist / "src" / "main" / "AndroidManifest.xml"
        manifest_file.write_text(
            '<manifest><uses-sdk android:minSdkVersion="24" android:targetSdkVersion="33" />'
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

        counts = p4a_hook.patch_build_tree(fake_dist)
        self.assertEqual(counts["props"], 1)
        self.assertEqual(counts["gradle"], 1)
        self.assertEqual(counts["manifest"], 1)
        self.assertEqual(counts["hid"], 1)

        self.assertIn("target=android-35", props_file.read_text(encoding="utf-8"))
        self.assertIn("targetSdkVersion 35", gradle_file.read_text(encoding="utf-8"))
        self.assertIn('android:targetSdkVersion="35"', manifest_file.read_text(encoding="utf-8"))
        self.assertNotIn("requestLegacyExternalStorage", manifest_file.read_text(encoding="utf-8"))
        self.assertIn("mContext.registerReceiver(mUsbBroadcast, filter, 2)", hid_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

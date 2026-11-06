# Автоматические тесты безопасности, загрузки файлов, ZIP-архивации и атомарных настроек AirShare PC

import base64
import io
import os
import tempfile
import unittest
import urllib.parse
import zipfile
from unittest import mock

import config
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
        server.AirShareHandler.current_password = "918273"

    def tearDown(self):
        self.patcher_settings.stop()
        self.patcher_utils_storage.stop()
        self.patcher_storage.stop()
        self.tmp_dir.cleanup()

    def test_01_random_pin_generation_and_compromised_replacement(self):
        # Первый запуск генерирует 6-значный PIN, а старый "06102000" или пустой заменяется
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
        # Совпадение логина с паролем при неверном пароле больше не пускает
        bad_req = (
            "GET / HTTP/1.1\r\nHost: localhost\r\n"
            + _basic_auth_header("918273", "wrong_pass")
            + "\r\n"
        ).encode("utf-8")
        resp = _run_request(self.storage_dir, bad_req, client_ip="10.0.0.99")
        self.assertIn(b"401", resp.splitlines()[0])

        # После 5 неудачных попыток возвращается 429 Too Many Requests
        for _ in range(4):
            _run_request(self.storage_dir, bad_req, client_ip="10.0.0.99")
        resp_blocked = _run_request(self.storage_dir, bad_req, client_ip="10.0.0.99")
        self.assertIn(b"429", resp_blocked.splitlines()[0])

        # Другой IP с правильным паролем проходит успешно
        good_req = (
            "GET / HTTP/1.1\r\nHost: localhost\r\n"
            + _basic_auth_header("airshare", "918273")
            + "\r\n"
        ).encode("utf-8")
        resp_ok = _run_request(self.storage_dir, good_req, client_ip="10.0.0.50")
        self.assertIn(b"200 OK", resp_ok.splitlines()[0])

    def test_04_upload_no_overwrite_and_411_without_content_length(self):
        # Запрос без Content-Length возвращает 411 и не создаёт пустой файл
        req_no_len = (
            "POST /?upload=empty.txt HTTP/1.1\r\nHost: localhost\r\n"
            + _basic_auth_header("airshare", "918273")
            + "\r\n"
        ).encode("utf-8")
        resp_411 = _run_request(self.storage_dir, req_no_len)
        self.assertIn(b"411", resp_411.splitlines()[0])
        self.assertFalse(os.path.exists(os.path.join(self.storage_dir, "empty.txt")))

        # Повторная загрузка одноимённого файла создаёт " (1)" и " (2)"
        for idx, body in enumerate([b"first", b"second", b"third"]):
            req = (
                f"POST /?upload=report.txt HTTP/1.1\r\nHost: localhost\r\n"
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
        # Проверяем файлы "скидка50%.pdf" и "a%20b.txt" при загрузке и скачивании
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

        # Создаём внешний файл за пределами хранилища и симлинк на него внутри folderA
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

    def test_07_web_ui_reduced_motion_and_theme_css(self):
        css_light = web_ui.get_css("light")
        self.assertIn("color-scheme: light", css_light)
        self.assertIn("prefers-reduced-motion: reduce", css_light)
        self.assertIn("35", web_ui.get_star_script())


if __name__ == "__main__":
    unittest.main()

# Вспомогательные функции AirShare PC: сеть, безопасное хранение настроек и информация об устройстве

import json
import logging
import os
import secrets
import shutil
import socket
import threading
from config import (
    COMPROMISED_PASSWORDS,
    MAX_RECENT_IPS,
    SERVER_PORT,
    SETTINGS_FILE,
    STORAGE_PATH,
)

logger = logging.getLogger("airshare.utils")

# Реентерабельная блокировка защищает файл настроек от гонки при параллельных HTTP-запросах
_settings_lock = threading.RLock()
# Кэш уже записанных в этой сессии клиентов, чтобы не перезаписывать диск на каждый HTTP-запрос
_seen_recent_ips = set()


def generate_pin():
    # Генерируем криптографически стойкий 6-значный PIN-код (от 000000 до 999999)
    return f"{secrets.randbelow(10**6):06d}"


def _sanitize_pin(candidate):
    val = str(candidate or "").strip()
    if val in COMPROMISED_PASSWORDS:
        return generate_pin(), True
    return val, False


def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(1.5)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            if ip and not ip.startswith("127."):
                return ip
        except OSError:
            pass
        return "127.0.0.1"


def get_network_label():
    # Показываем реальный статус локальной сети вместо выдуманных характеристик Wi-Fi 6 / 850 Mbps
    ip = get_local_ip()
    if ip and ip not in ("127.0.0.1", "0.0.0.0"):
        return f"Wi-Fi • {ip}"
    return "Wi-Fi • Offline"


def format_size(size):
    size = float(size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def get_device_info():
    # Определяем реальное имя телефона на Android или имя хоста на ПК (без фейкового Pixel 9 Pro)
    try:
        from kivy.utils import platform
    except Exception:
        platform = "unknown"

    if platform == "android":
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            SettingsGlobal = autoclass("android.provider.Settings$Global")
            activity = PythonActivity.mActivity
            if activity is not None:
                resolver = activity.getContentResolver()
                dev_name = SettingsGlobal.getString(resolver, "device_name")
                if dev_name and str(dev_name).strip():
                    return str(dev_name).strip()
        except Exception as exc:
            logger.debug("Не удалось получить Settings.Global.device_name: %s", exc)
        try:
            from jnius import autoclass
            Build = autoclass("android.os.Build")
            model = str(Build.MODEL or "").strip()
            known_models = {
                "SM-S928B": "Galaxy S24 Ultra",
                "SM-S928U": "Galaxy S24 Ultra",
                "SM-S928N": "Galaxy S24 Ultra",
                "SM-S926B": "Galaxy S24+",
                "SM-S921B": "Galaxy S24",
                "SM-S918B": "Galaxy S23 Ultra",
            }
            if model in known_models:
                return known_models[model]
            manufacturer = str(Build.MANUFACTURER or "").capitalize()
            if model.startswith(manufacturer):
                return model
            full_name = f"{manufacturer} {model}".strip()
            if full_name:
                return full_name
        except Exception as exc:
            logger.debug("Не удалось прочитать android.os.Build: %s", exc)
        return "Android Device"

    try:
        hostname = socket.gethostname()
        if hostname:
            return hostname
    except OSError:
        pass
    return "Unknown"


def get_storage_stats():
    # Возвращаем реальную статистику памяти или прочерки при ошибке вместо фейковых 64.5 / 128 GB
    try:
        target = STORAGE_PATH if os.path.exists(STORAGE_PATH) else os.path.expanduser("~")
        stat = os.statvfs(target)
        free_bytes = stat.f_bavail * stat.f_frsize
        total_bytes = stat.f_blocks * stat.f_frsize
        used_bytes = total_bytes - free_bytes
        total_gb = total_bytes / (1024 ** 3)
        free_gb = free_bytes / (1024 ** 3)
        used_gb = used_bytes / (1024 ** 3)
        percent = (used_bytes / total_bytes) if total_bytes > 0 else 0.0
        return {
            "total_gb": round(total_gb, 1),
            "free_gb": round(free_gb, 1),
            "used_gb": round(used_gb, 1),
            "percent": min(1.0, max(0.0, percent)),
            "text": f"Storage: {used_gb:.1f} GB / {total_gb:.0f} GB",
        }
    except Exception as exc:
        logger.warning("Не удалось определить объём хранилища: %s", exc)
        return {
            "total_gb": 0.0,
            "free_gb": 0.0,
            "used_gb": 0.0,
            "percent": 0.0,
            "text": "Storage: — / —",
        }


def _atomic_write_json(filepath, payload):
    parent = os.path.dirname(filepath)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp_path = f"{filepath}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, filepath)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def load_settings():
    with _settings_lock:
        defaults = {
            "password": "",
            "recent_ips": [],
            "theme_mode": "dark",
            "port": SERVER_PORT,
        }
        needs_persist = False

        if os.path.isfile(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    raw_pwd = str(data.get("password", "")).strip()
                    clean_pwd, rotated = _sanitize_pin(raw_pwd)
                    defaults["password"] = clean_pwd
                    if rotated:
                        needs_persist = True

                    ips = data.get("recent_ips", [])
                    if isinstance(ips, list):
                        defaults["recent_ips"] = [str(x) for x in ips if x][:MAX_RECENT_IPS]

                    mode = data.get("theme_mode", "dark")
                    if mode in ("system", "dark", "light"):
                        defaults["theme_mode"] = mode

                    try:
                        port_val = int(data.get("port", SERVER_PORT))
                        if 1024 <= port_val <= 65535:
                            defaults["port"] = port_val
                    except (ValueError, TypeError):
                        pass
            except (json.JSONDecodeError, OSError) as exc:
                # При повреждении JSON сохраняем резервную копию .bak и логируем проблему
                logger.warning("Файл настроек повреждён (%s), создаём резервную копию .bak", exc)
                try:
                    if os.path.isfile(SETTINGS_FILE):
                        shutil.copy2(SETTINGS_FILE, SETTINGS_FILE + ".bak")
                except OSError as bak_exc:
                    logger.warning("Не удалось создать резервную копию настроек: %s", bak_exc)
                defaults["password"] = generate_pin()
                needs_persist = True
        else:
            defaults["password"] = generate_pin()
            needs_persist = True

        if not defaults["password"] or defaults["password"] in COMPROMISED_PASSWORDS:
            defaults["password"] = generate_pin()
            needs_persist = True

        if needs_persist:
            try:
                _atomic_write_json(SETTINGS_FILE, defaults)
            except OSError as exc:
                logger.warning("Не удалось сохранить начальные настройки: %s", exc)

        return defaults


def save_settings(password=None, recent_ips=None, theme_mode=None, port=None):
    with _settings_lock:
        current = load_settings()
        if password is not None:
            clean_pwd, _ = _sanitize_pin(password)
            current["password"] = clean_pwd
        if recent_ips is not None:
            current["recent_ips"] = [str(x) for x in recent_ips if x][:MAX_RECENT_IPS]
            _seen_recent_ips.clear()
            _seen_recent_ips.update(current["recent_ips"])
        if theme_mode in ("system", "dark", "light"):
            current["theme_mode"] = theme_mode
        if port is not None:
            try:
                port_val = int(port)
                if 1024 <= port_val <= 65535:
                    current["port"] = port_val
            except (ValueError, TypeError):
                pass
        try:
            _atomic_write_json(SETTINGS_FILE, current)
        except OSError as exc:
            logger.warning("Ошибка атомарного сохранения настроек: %s", exc)
        return current


def add_recent_ip(ip_entry):
    if not ip_entry:
        return load_settings()["recent_ips"]
    ip_entry = str(ip_entry).strip()
    if not ip_entry:
        return load_settings()["recent_ips"]

    with _settings_lock:
        # Не дергаем файловую систему на каждый HTTP-запрос от уже известного устройства
        if ip_entry in _seen_recent_ips:
            return load_settings()["recent_ips"]
        settings = load_settings()
        ips = [x for x in settings.get("recent_ips", []) if x != ip_entry]
        ips.insert(0, ip_entry)
        ips = ips[:MAX_RECENT_IPS]
        _seen_recent_ips.add(ip_entry)
        save_settings(recent_ips=ips)
        return ips


def get_device_theme():
    try:
        from kivy.utils import platform
    except Exception:
        platform = "unknown"

    if platform == "android":
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Configuration = autoclass("android.content.res.Configuration")
            activity = PythonActivity.mActivity
            if activity is not None:
                ui_mode = activity.getResources().getConfiguration().uiMode
                night_mask = ui_mode & Configuration.UI_MODE_NIGHT_MASK
                if night_mask == Configuration.UI_MODE_NIGHT_NO:
                    return "light"
                if night_mask == Configuration.UI_MODE_NIGHT_YES:
                    return "dark"
        except Exception as exc:
            logger.debug("Не удалось определить системную тему Android: %s", exc)
        return "dark"

    return "dark"


def request_android_full_storage():
    try:
        from kivy.utils import platform
    except Exception:
        return
    if platform != "android":
        return
    try:
        from android.permissions import request_permissions, Permission
        perms = [
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE,
            Permission.INTERNET,
        ]
        request_permissions(perms)
        from jnius import autoclass
        BuildVersion = autoclass("android.os.Build$VERSION")
        if BuildVersion.SDK_INT >= 30:
            Environment = autoclass("android.os.Environment")
            if not Environment.isExternalStorageManager():
                Intent = autoclass("android.content.Intent")
                Settings = autoclass("android.provider.Settings")
                Uri = autoclass("android.net.Uri")
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                activity = PythonActivity.mActivity
                intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
                uri = Uri.parse(f"package:{activity.getPackageName()}")
                intent.setData(uri)
                activity.startActivity(intent)
    except Exception as exc:
        logger.warning("Не удалось запросить доступ к хранилищу Android: %s", exc)

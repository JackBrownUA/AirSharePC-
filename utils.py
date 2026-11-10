# Вспомогательные функции AirShare PC: проверка Wi-Fi, форматирование размеров и потокобезопасные настройки

import json
import logging
import os
import secrets
import shutil
import socket
import struct
import threading
from config import (
    COMPROMISED_PASSWORDS,
    MAX_RECENT_IPS,
    SERVER_PORT,
    SETTINGS_FILE,
    STORAGE_PATH,
)
from i18n import SUPPORTED_CODES, detect_system_language, tr

logger = logging.getLogger("airshare.utils")

_settings_lock = threading.RLock()
_seen_recent_ips = set()

_WIFI_IFACE_PREFIXES = ("wlan", "swlan", "ap", "softap", "wifi", "p2p", "eth", "rndis", "en", "wl")


def generate_pin():
    # Генерируем криптографически стойкий 6-значный PIN-код (от 000000 до 999999)
    return f"{secrets.randbelow(10**6):06d}"


def _sanitize_pin(candidate):
    val = str(candidate or "").strip()
    if val in COMPROMISED_PASSWORDS:
        return generate_pin(), True
    return val, False


def is_private_lan_ip(ip_str):
    # Проверяем, что адрес принадлежит локальной сети RFC 1918 (192.168.x.x, 10.x.x.x, 172.16-31.x.x),
    # исключая мобильные сети CG-NAT (100.64.0.0/10) и loopback (127.x.x.x)
    if not ip_str or not isinstance(ip_str, str):
        return False
    parts = ip_str.strip().split(".")
    if len(parts) != 4:
        return False
    try:
        a, b, c, d = (int(p) for p in parts)
    except ValueError:
        return False
    if not all(0 <= x <= 255 for x in (a, b, c, d)):
        return False
    if a == 10:
        return True
    if a == 172 and 16 <= b <= 31:
        return True
    if a == 192 and b == 168:
        return True
    return False


def _get_android_wifi_ip():
    # На Android берём IP только с интерфейсов Wi-Fi / точки доступа (wlan*, ap*, swlan*),
    # игнорируя мобильный интернет (rmnet*, ccmni*)
    try:
        from jnius import autoclass
        NetworkInterface = autoclass("java.net.NetworkInterface")
        interfaces = NetworkInterface.getNetworkInterfaces()
        if interfaces is not None:
            while interfaces.hasMoreElements():
                nif = interfaces.nextElement()
                if nif is None or not nif.isUp() or nif.isLoopback():
                    continue
                name = str(nif.getName() or "").lower()
                if not name.startswith(_WIFI_IFACE_PREFIXES):
                    continue
                addrs = nif.getInetAddresses()
                while addrs.hasMoreElements():
                    addr = addrs.nextElement()
                    if addr is None or addr.isLoopbackAddress():
                        continue
                    host = str(addr.getHostAddress() or "").split("%")[0].strip()
                    if is_private_lan_ip(host):
                        return host
    except Exception as exc:
        logger.debug("Не удалось проверить NetworkInterface на Android: %s", exc)

    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")
        activity = getattr(PythonActivity, "mActivity", None)
        if activity is not None:
            wm = activity.getApplicationContext().getSystemService(Context.WIFI_SERVICE)
            if wm is not None and wm.isWifiEnabled():
                info = wm.getConnectionInfo()
                if info is not None:
                    ip_int = info.getIpAddress()
                    if ip_int:
                        ip_str = socket.inet_ntoa(struct.pack("<I", ip_int & 0xFFFFFFFF))
                        if is_private_lan_ip(ip_str):
                            return ip_str
    except Exception as exc:
        logger.debug("Не удалось получить IP через WifiManager: %s", exc)

    return None


def get_local_ip():
    try:
        from kivy.utils import platform
    except Exception:
        platform = "unknown"

    if platform == "android":
        wifi_ip = _get_android_wifi_ip()
        return wifi_ip if wifi_ip else "127.0.0.1"

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(1.5)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if is_private_lan_ip(ip):
                return ip
    except OSError:
        pass

    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if is_private_lan_ip(ip):
            return ip
    except OSError:
        pass
    return "127.0.0.1"


def is_wifi_connected():
    ip = get_local_ip()
    return is_private_lan_ip(ip)


def get_network_label(lang=None):
    # В верхнем правом чипе показываем аккуратный статус без обрезанного IP с точками посередине
    if lang is None:
        lang = load_settings().get("language", "en")
    if is_wifi_connected():
        return tr("wifi_online", lang)
    return tr("no_wifi", lang)


def format_size(size):
    # Байты выводим целым числом без дробной части ("604 B" вместо "604.0 B")
    size = float(size)
    if size < 1024:
        return f"{int(round(size))} B"
    size /= 1024.0
    for unit in ["KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def get_device_info():
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


def get_storage_stats(lang=None):
    if lang is None:
        lang = load_settings().get("language", "en")
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
            "text": tr("storage_fmt", lang, used=f"{used_gb:.1f}", total=f"{total_gb:.0f}"),
        }
    except Exception as exc:
        logger.warning("Не удалось определить объём хранилища: %s", exc)
        return {
            "total_gb": 0.0,
            "free_gb": 0.0,
            "used_gb": 0.0,
            "percent": 0.0,
            "text": tr("storage_unknown", lang),
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
            "language": detect_system_language(),
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

                    lang = str(data.get("language", "")).strip().lower()
                    if lang in SUPPORTED_CODES:
                        defaults["language"] = lang

                    try:
                        port_val = int(data.get("port", SERVER_PORT))
                        if 1024 <= port_val <= 65535:
                            defaults["port"] = port_val
                    except (ValueError, TypeError):
                        pass
            except (json.JSONDecodeError, OSError) as exc:
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


def save_settings(password=None, recent_ips=None, theme_mode=None, port=None, language=None):
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
        if language is not None and str(language).lower() in SUPPORTED_CODES:
            current["language"] = str(language).lower()
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
    # Запрашиваем доступ ко всем файлам (MANAGE_EXTERNAL_STORAGE) только когда пользователь явно выбрал весь накопитель
    try:
        from kivy.utils import platform
    except Exception:
        return
    if platform != "android":
        return
    try:
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
        else:
            from android.permissions import Permission, request_permissions
            request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
    except Exception as exc:
        logger.warning("Не удалось запросить доступ к хранилищу Android: %s", exc)


def request_ignore_battery_optimizations():
    # Просим Android (One UI / MIUI) не усыплять фоновый поток сервера при сворачивании приложения
    try:
        from kivy.utils import platform
    except Exception:
        return
    if platform != "android":
        return
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")
        Intent = autoclass("android.content.Intent")
        Settings = autoclass("android.provider.Settings")
        Uri = autoclass("android.net.Uri")
        activity = getattr(PythonActivity, "mActivity", None)
        if activity is not None:
            pkg = activity.getPackageName()
            pm = activity.getSystemService(Context.POWER_SERVICE)
            if pm is not None and not pm.isIgnoringBatteryOptimizations(pkg):
                intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
                intent.setData(Uri.parse(f"package:{pkg}"))
                activity.startActivity(intent)
    except Exception as exc:
        logger.debug("Не удалось запросить исключение из оптимизации батареи: %s", exc)

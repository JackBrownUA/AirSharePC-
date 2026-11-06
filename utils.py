# Helper functions for AirShare PC

import os
import json
import socket
from config import DEFAULT_PASSWORD, MAX_RECENT_IPS, SETTINGS_FILE, STORAGE_PATH


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


def format_size(size):
    size = float(size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def get_device_info():
    """Detect real marketing device name (e.g. Galaxy S24 Ultra) on Android"""
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
        except Exception:
            pass
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
            return f"{manufacturer} {model}".strip()
        except Exception:
            pass
        return "Android Phone"

    try:
        hostname = socket.gethostname()
        if hostname:
            return hostname
    except Exception:
        pass
    return "Pixel 9 Pro"


def get_storage_stats():
    """Get total, used, free storage and percent for device storage bar"""
    try:
        target = STORAGE_PATH if os.path.exists(STORAGE_PATH) else os.path.expanduser("~")
        stat = os.statvfs(target)
        free_bytes = stat.f_bavail * stat.f_frsize
        total_bytes = stat.f_blocks * stat.f_frsize
        used_bytes = total_bytes - free_bytes
        total_gb = total_bytes / (1024 ** 3)
        free_gb = free_bytes / (1024 ** 3)
        used_gb = used_bytes / (1024 ** 3)
        percent = (used_bytes / total_bytes) if total_bytes > 0 else 0.5
        return {
            "total_gb": round(total_gb, 1),
            "free_gb": round(free_gb, 1),
            "used_gb": round(used_gb, 1),
            "percent": min(1.0, max(0.0, percent)),
            "text": f"Storage: {used_gb:.1f} GB / {total_gb:.0f} GB",
        }
    except Exception:
        return {
            "total_gb": 128.0,
            "free_gb": 63.5,
            "used_gb": 64.5,
            "percent": 0.5,
            "text": "Storage: 64.5 GB / 128 GB",
        }


def load_settings():
    """Load persisted user password, recent IP list, theme, and port"""
    defaults = {
        "password": DEFAULT_PASSWORD,
        "recent_ips": [],
        "theme_mode": "dark",
        "port": 8080,
    }
    try:
        if os.path.isfile(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                defaults["password"] = str(data.get("password", DEFAULT_PASSWORD))
                ips = data.get("recent_ips", [])
                if isinstance(ips, list):
                    defaults["recent_ips"] = [str(x) for x in ips if x][:MAX_RECENT_IPS]
                mode = data.get("theme_mode", "dark")
                if mode in ("system", "dark", "light"):
                    defaults["theme_mode"] = mode
                defaults["port"] = int(data.get("port", 8080))
    except Exception:
        pass
    return defaults


def save_settings(password=None, recent_ips=None, theme_mode=None, port=None):
    """Save user password, recent IP list, theme, and port to disk"""
    current = load_settings()
    if password is not None:
        current["password"] = str(password)
    if recent_ips is not None:
        current["recent_ips"] = [str(x) for x in recent_ips if x][:MAX_RECENT_IPS]
    if theme_mode in ("system", "dark", "light"):
        current["theme_mode"] = theme_mode
    if port is not None:
        try:
            current["port"] = int(port)
        except Exception:
            pass
    try:
        parent = os.path.dirname(SETTINGS_FILE)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return current


def add_recent_ip(ip_entry):
    """Add an IP address or device record to remembered list (most recent first)"""
    if not ip_entry:
        return load_settings()["recent_ips"]
    ip_entry = str(ip_entry).strip()
    if not ip_entry:
        return load_settings()["recent_ips"]
    settings = load_settings()
    ips = [x for x in settings.get("recent_ips", []) if x != ip_entry]
    ips.insert(0, ip_entry)
    ips = ips[:MAX_RECENT_IPS]
    save_settings(recent_ips=ips)
    return ips


def get_device_theme():
    """Detect system dark/light theme on Android and desktop platforms"""
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
        except Exception:
            pass
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
    except Exception:
        pass

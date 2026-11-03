"""
Helper functions for AirShare PC
"""

import os
import json
import socket
from config import DEFAULT_PASSWORD, MAX_RECENT_IPS, SETTINGS_FILE


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


def load_settings():
    """Load persisted user password, recent IP list, and theme preference"""
    defaults = {
        "password": DEFAULT_PASSWORD,
        "recent_ips": [],
        "theme_mode": "system",
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
                mode = data.get("theme_mode", "system")
                if mode in ("system", "dark", "light"):
                    defaults["theme_mode"] = mode
    except Exception:
        pass
    return defaults


def save_settings(password=None, recent_ips=None, theme_mode=None):
    """Save user password, recent IP list, and theme preference to disk"""
    current = load_settings()
    if password is not None:
        current["password"] = str(password)
    if recent_ips is not None:
        current["recent_ips"] = [str(x) for x in recent_ips if x][:MAX_RECENT_IPS]
    if theme_mode in ("system", "dark", "light"):
        current["theme_mode"] = theme_mode
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
    """Add an IP address or server URL to the remembered list (most recent first)"""
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

    if platform == "win":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            )
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return "light" if val == 1 else "dark"
        except Exception:
            pass
    elif platform == "macosx":
        try:
            import subprocess
            out = subprocess.check_output(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                stderr=subprocess.DEVNULL
            ).decode("utf-8", errors="ignore").strip().lower()
            return "dark" if "dark" in out else "light"
        except Exception:
            return "light"
    else:
        try:
            import subprocess
            out = subprocess.check_output(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                stderr=subprocess.DEVNULL
            ).decode("utf-8", errors="ignore").strip().lower()
            if "light" in out:
                return "light"
            if "dark" in out:
                return "dark"
        except Exception:
            pass

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

"""
Конфигурация AirShare PC
Меняй настройки здесь, не трогая основной код
"""

import os

try:
    from kivy.utils import platform
except Exception:
    platform = "unknown"

# Настройки сервера
SERVER_PORT = 8080
DEFAULT_PASSWORD = "06102000"
MAX_RECENT_IPS = 10

# Путь к файлам
if platform == "android":
    _raw_storage = "/storage/emulated/0"
    STORAGE_PATH = os.path.realpath(_raw_storage) if os.path.exists(_raw_storage) else _raw_storage
    SETTINGS_DIR = os.environ.get("ANDROID_PRIVATE", os.path.expanduser("~"))
else:
    STORAGE_PATH = os.path.realpath(os.path.expanduser("~"))
    SETTINGS_DIR = STORAGE_PATH

SETTINGS_FILE = os.path.join(SETTINGS_DIR, ".airshare_settings.json")

# Название приложения
APP_NAME = "AirShare PC"
APP_VERSION = "1.0.0"

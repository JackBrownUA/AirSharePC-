# Конфигурация приложения AirShare PC

import os

try:
    from kivy.utils import platform
except Exception:
    platform = "unknown"

SERVER_PORT = 8080
MAX_RECENT_IPS = 10

# Лимит размера одного загружаемого файла (2 ГБ) для защиты памяти и хранилища
MAX_UPLOAD_SIZE = 2 * 1024 * 1024 * 1024

# Защита от перебора PIN-кода: максимум 5 неудачных попыток, блокировка IP на 3 минуты
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_BLOCK_SECONDS = 180

# Старый захардкоженный пароль считается скомпрометированным и заменяется при запуске
COMPROMISED_PASSWORDS = frozenset({"", "06102000"})

if platform == "android":
    _raw_storage = "/storage/emulated/0"
    STORAGE_PATH = os.path.realpath(_raw_storage) if os.path.exists(_raw_storage) else _raw_storage
    SETTINGS_DIR = os.environ.get("ANDROID_PRIVATE", os.path.expanduser("~"))
else:
    STORAGE_PATH = os.path.realpath(os.path.expanduser("~"))
    SETTINGS_DIR = STORAGE_PATH

SETTINGS_FILE = os.path.join(SETTINGS_DIR, ".airshare_settings.json")

APP_NAME = "AirShare PC"
APP_VERSION = "1.1.0"

# Конфигурация приложения AirShare PC

import os

try:
    from kivy.utils import platform
except Exception:
    platform = "unknown"

SERVER_PORT = 8080
MAX_RECENT_IPS = 10

# Лимит размера одного загружаемого файла (4 ГБ) для защиты памяти и хранилища
MAX_UPLOAD_SIZE = 4 * 1024 * 1024 * 1024

# Лимит элементов на одной странице веб-листинга для мгновенного открытия больших папок (например, DCIM)
MAX_DIR_ITEMS_PER_PAGE = 300

# Таймаут соединения и лимит одновременных HTTP-потоков
SOCKET_TIMEOUT_SECONDS = 30
MAX_CONCURRENT_CONNECTIONS = 32

# Защита от перебора PIN-кода: максимум 5 неудачных попыток, блокировка IP на 5 минут (300 сек)
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_BLOCK_SECONDS = 300

# Старый захардкоженный пароль считается скомпрометированным и заменяется при запуске
COMPROMISED_PASSWORDS = frozenset({"", "06102000"})

if platform == "android":
    _raw_storage = "/storage/emulated/0"
    STORAGE_PATH = os.path.realpath(_raw_storage) if os.path.exists(_raw_storage) else _raw_storage
    SETTINGS_DIR = os.environ.get("ANDROID_PRIVATE", os.path.expanduser("~"))
else:
    # На ПК раздаём только выделенную папку ~/AirShareFiles, а настройки храним отдельно в ~/.config/airshare
    _desktop_share = os.path.expanduser("~/AirShareFiles")
    try:
        os.makedirs(_desktop_share, exist_ok=True)
    except OSError:
        _desktop_share = os.path.expanduser("~")
    STORAGE_PATH = os.path.realpath(_desktop_share)
    SETTINGS_DIR = os.path.join(os.path.expanduser("~"), ".config", "airshare")

SETTINGS_FILE = os.path.join(SETTINGS_DIR, ".airshare_settings.json")

APP_NAME = "AirShare PC"
APP_VERSION = "1.3.0"

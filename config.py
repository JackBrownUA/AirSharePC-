"""
Конфигурация AirShare PC
Меняй настройки здесь, не трогая основной код
"""

import os
from kivy.utils import platform

# Настройки сервера
SERVER_PORT = 8080
DEFAULT_PASSWORD = "06102000"

# Путь к файлам
if platform == "android":
    STORAGE_PATH = "/storage/emulated/0"
else:
    STORAGE_PATH = os.path.realpath(os.path.expanduser("~"))

# Название приложения
APP_NAME = "AirShare PC"
APP_VERSION = "1.0.0"

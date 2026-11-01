"""Налаштування лаунчера. Єдине, що ТРЕБА змінити, - CLIENT_ID."""
import os

APP_NAME = "WAVE LAUNCHER"
APP_SHORT = "WAVE"
LAUNCHER_VERSION = "4.0"

# Репозиторій GitHub, з релізів якого лаунчер бере оновлення.
GITHUB_REPO = "VL333333/MyCraftLauncher"

# Application (client) ID вашого застосунку в Azure (див. README, розділ 4).
# Можна також задати через змінну середовища MYCRAFT_CLIENT_ID.
CLIENT_ID = os.environ.get("MYCRAFT_CLIENT_ID", "PASTE-YOUR-AZURE-CLIENT-ID-HERE")

# Redirect URI має ТОЧНО збігатися з тим, що вказано в Azure.
REDIRECT_PORT = 53682
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}"
LOGIN_TIMEOUT_SECONDS = 180

_APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
DATA_DIR = os.path.join(_APPDATA, "MyCraftLauncher")  # Keeps existing settings and account data
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
ACCOUNT_FILE = os.path.join(DATA_DIR, "account.json")
LOG_FILE = os.path.join(DATA_DIR, "game.log")

DEFAULT_GAME_DIR = os.path.join(_APPDATA, ".minecraft")
DEFAULT_VERSION = "1.21.1"


def client_id_is_set() -> bool:
    return bool(CLIENT_ID) and not CLIENT_ID.startswith("PASTE-")

"""Список версій, встановлення та запуск Minecraft."""
import hashlib
import os
import re
import shlex
import shutil
import subprocess
import uuid

import minecraft_launcher_lib as mll

import config
from errors import InputError, JavaNotFoundError

_NAME_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")


def offline_account(name: str) -> dict:
    """Офлайн-профіль БЕЗ Microsoft: нік + стандартний офлайн-UUID, токена немає.
    Дає змогу грати в одиночній грі та на серверах з online-mode=false.
    На звичайні (онлайн) сервери з таким профілем зайти НЕ можна."""
    if not _NAME_RE.match(name):
        raise InputError("Нік має містити 3-16 символів: латинські літери, цифри або _.")
    h = bytearray(hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest())
    h[6] = (h[6] & 0x0F) | 0x30  # UUID v3, як у Java UUID.nameUUIDFromBytes
    h[8] = (h[8] & 0x3F) | 0x80
    return {"name": name, "id": str(uuid.UUID(bytes=bytes(h))), "access_token": "0"}


def get_versions(game_dir: str, show_snapshots: bool) -> tuple[list[str], bool]:
    """Повертає (список id версій, чи вдалося отримати онлайн-список)."""
    try:
        versions = mll.utils.get_version_list()
        allowed = {"release", "snapshot"} if show_snapshots else {"release"}
        return [v["id"] for v in versions if v["type"] in allowed], True
    except Exception:
        try:
            return [v["id"] for v in mll.utils.get_installed_versions(game_dir)], False
        except Exception:
            return [], False


def install_version(version: str, game_dir: str, on_detail, on_percent) -> None:
    os.makedirs(game_dir, exist_ok=True)
    state = {"max": 0, "last": -1}

    def set_max(value: int):
        state["max"] = value

    def set_progress(value: int):
        if state["max"] > 0:
            pct = min(100, int(value * 100 / state["max"]))
            if pct != state["last"]:
                state["last"] = pct
                on_percent(pct)

    mll.install.install_minecraft_version(
        version,
        game_dir,
        callback={"setStatus": on_detail, "setProgress": set_progress, "setMax": set_max},
    )


def _check_java(command: list[str]) -> None:
    exe = command[0]
    if os.path.isabs(exe) or os.sep in exe:
        found = os.path.exists(exe)
    else:
        found = shutil.which(exe) is not None
    if not found:
        raise JavaNotFoundError(
            "Java не знайдено. Лаунчер зазвичай завантажує потрібну Java сам разом із версією гри; "
            "якщо цього не сталося - встановіть Java 21 (напр. Eclipse Temurin) і спробуйте ще раз."
        )


def launch(version: str, game_dir: str, account: dict, ram_gb: int = 4) -> subprocess.Popen:
    """Запускає гру з РЕАЛЬНИМИ даними Microsoft-акаунта. Вивід гри пишеться у LOG_FILE."""
    options = {
        "username": account["name"],
        "uuid": account["id"],
        "token": account["access_token"],
        "launcherName": "WAVELauncher",
        "launcherVersion": config.LAUNCHER_VERSION,
        "gameDirectory": game_dir,
        "jvmArguments": [f"-Xms1G", f"-Xmx{max(1, min(32, int(ram_gb)))}G"],
    }
    command = mll.command.get_minecraft_command(version, game_dir, options)
    _check_java(command)

    os.makedirs(config.DATA_DIR, exist_ok=True)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # без чорного вікна консолі на Windows
    with open(config.LOG_FILE, "wb") as log:  # саму команду (з токеном) у лог НЕ пишемо
        return subprocess.Popen(
            command, cwd=game_dir, stdout=log, stderr=subprocess.STDOUT, creationflags=flags
        )


def launch_external(exe: str, args: str, account_name: str = "") -> subprocess.Popen:
    """Запускає сторонній клієнт (напр. написаний на Rust: Leafish, Stevenarella).
    Такий клієнт має власний екран входу, тому токени Microsoft йому НЕ передаються.
    У рядку аргументів можна вживати {name} - нік з налаштувань лаунчера."""
    exe = (exe or "").strip().strip('"')
    if not exe or not os.path.isfile(exe):
        raise InputError("Не знайдено файл Rust-клієнта. Вкажи шлях до .exe у вкладці «Профілі».")
    try:
        extra = shlex.split((args or "").replace("{name}", account_name or "Player"), posix=(os.name != "nt"))
    except ValueError as exc:
        raise InputError(f"Некоректні аргументи запуску: {exc}")
    os.makedirs(config.DATA_DIR, exist_ok=True)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with open(config.LOG_FILE, "wb") as log:
        return subprocess.Popen(
            [exe, *extra], cwd=os.path.dirname(exe), stdout=log, stderr=subprocess.STDOUT, creationflags=flags
        )

"""Збереження налаштувань та даних акаунта у %APPDATA%\\WAVELauncher."""
import json
import os

import config

_DEFAULT_SETTINGS = {
    "game_dir": config.DEFAULT_GAME_DIR,
    "version": config.DEFAULT_VERSION,
    "show_snapshots": False,
    "auth_mode": "microsoft",  # "microsoft" або "offline"
    "offline_name": "Player",
    "ram_gb": 4,
    "active_profile": "За замовчуванням",
    "profiles": {"За замовчуванням": {"version": config.DEFAULT_VERSION, "game_dir": config.DEFAULT_GAME_DIR, "ram_gb": 4}},
}


def _read(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_settings() -> dict:
    s = dict(_DEFAULT_SETTINGS)
    s.update(_read(config.SETTINGS_FILE))
    return s


def save_settings(settings: dict) -> None:
    try:
        _write(config.SETTINGS_FILE, settings)
    except OSError:
        pass  # не критично


def load_account() -> dict:
    return _read(config.ACCOUNT_FILE)


def save_account(name: str, uuid: str, refresh_token: str) -> None:
    """Зберігаємо ЛИШЕ refresh-токен і нік. Паролів лаунчер не бачить і не зберігає."""
    _write(config.ACCOUNT_FILE, {"name": name, "uuid": uuid, "refresh_token": refresh_token})


def clear_account() -> None:
    try:
        os.remove(config.ACCOUNT_FILE)
    except FileNotFoundError:
        pass


def profiles_from_settings(settings: dict) -> dict:
    """Return validated profile dictionary, migrating older settings safely."""
    profiles = settings.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        profiles = {"За замовчуванням": {
            "version": settings.get("version", config.DEFAULT_VERSION),
            "game_dir": settings.get("game_dir", config.DEFAULT_GAME_DIR),
            "ram_gb": settings.get("ram_gb", 4),
        }}
    clean = {}
    for name, profile in profiles.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(profile, dict):
            continue
        try:
            ram = int(profile.get("ram_gb", 4))
        except (TypeError, ValueError):
            ram = 4
        clean[name[:40]] = {
            "version": str(profile.get("version", config.DEFAULT_VERSION)),
            "game_dir": str(profile.get("game_dir", config.DEFAULT_GAME_DIR)),
            "ram_gb": max(1, min(32, ram)),
        }
    return clean or {"За замовчуванням": {"version": config.DEFAULT_VERSION, "game_dir": config.DEFAULT_GAME_DIR, "ram_gb": 4}}

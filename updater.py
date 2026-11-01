"""Автооновлення: перевіряє останній реліз на GitHub і ставить новий інсталятор."""
import hashlib
import os
import re
import subprocess
import sys
import tempfile

import requests

import config

ASSET_NAME = "WAVE_Launcher_Setup.exe"
API_URL = f"https://api.github.com/repos/{config.GITHUB_REPO}/releases/latest"


def _parse(version: str) -> tuple:
    nums = re.findall(r"\d+", version or "")
    return tuple(int(n) for n in nums) or (0,)


def is_newer(remote: str, local: str) -> bool:
    a, b = _parse(remote), _parse(local)
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def check_for_update(installed_version: str = "") -> dict | None:
    """Повертає {'version','url','sha256','notes'} або None, якщо оновлень немає / немає мережі."""
    try:
        r = requests.get(API_URL, timeout=8, headers={"Accept": "application/vnd.github+json"})
        if r.status_code != 200:
            return None
        data = r.json()
        tag = data.get("tag_name", "")
        if not is_newer(tag, config.LAUNCHER_VERSION):
            return None
        # Захист від нескінченного циклу: якщо цю версію вже встановлювали - не пропонуємо знову.
        if installed_version and not is_newer(tag, installed_version):
            return None
        for asset in data.get("assets", []):
            if asset.get("name") == ASSET_NAME:
                digest = (asset.get("digest") or "").removeprefix("sha256:")
                return {
                    "version": tag.lstrip("vV"),
                    "url": asset["browser_download_url"],
                    "sha256": digest.lower(),
                    "notes": (data.get("body") or "").strip()[:600],
                }
    except Exception:
        return None
    return None


def can_self_update() -> bool:
    """Автооновлення працює тільки у зібраній .exe-версії на Windows."""
    return bool(getattr(sys, "frozen", False)) and sys.platform == "win32"


def download_installer(info: dict, on_percent=None) -> str:
    path = os.path.join(tempfile.gettempdir(), f"WAVE_Launcher_Setup_{info['version']}.exe")
    sha = hashlib.sha256()
    with requests.get(info["url"], stream=True, timeout=30) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)
                sha.update(chunk)
                done += len(chunk)
                if on_percent and total:
                    on_percent(min(100, int(done * 100 / total)))
    if info.get("sha256") and sha.hexdigest().lower() != info["sha256"]:
        os.remove(path)
        raise RuntimeError("Контрольна сума файлу оновлення не збігається. Оновлення скасовано.")
    return path


def run_installer(path: str) -> None:
    """Тихо запускає інсталятор; він сам закриє лаунчер і запустить нову версію."""
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(
        [path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
        creationflags=flags, close_fds=True,
    )

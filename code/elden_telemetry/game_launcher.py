"""Offline launch: eldenring.exe -eac-nop-loaded, with Steam IDs passed via env vars."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

STEAM_APP_ID = "1245620"
GAME_EXE = "eldenring.exe"
EAC_MARKER = "easyanticheat"


def _steam_libraries() -> list[Path]:
    import winreg  # Windows only

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
        steam_path = Path(winreg.QueryValueEx(k, "SteamPath")[0])
    libs = [steam_path]
    vdf = steam_path / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        text = vdf.read_text(encoding="utf-8", errors="replace")
        libs += [Path(m.replace("\\\\", "\\")) for m in re.findall(r'"path"\s+"([^"]+)"', text)]
    seen, out = set(), []
    for lib in libs:
        if lib not in seen:
            seen.add(lib)
            out.append(lib)
    return out


def find_game_dir(override: str | None = None) -> Path:
    if override:
        d = Path(override)
        if not (d / GAME_EXE).is_file():
            raise FileNotFoundError(f"{GAME_EXE} not found in {d}")
        return d
    try:
        libs = _steam_libraries()
    except OSError as exc:
        raise FileNotFoundError(f"Steam not found in registry ({exc}); use --game-dir") from exc
    for lib in libs:
        d = lib / "steamapps" / "common" / "ELDEN RING" / "Game"
        if (d / GAME_EXE).is_file():
            return d
    raise FileNotFoundError("Elden Ring not found in any Steam library; use --game-dir")


def launch(game_dir: Path) -> subprocess.Popen:
    env = dict(os.environ, SteamAppId=STEAM_APP_ID, SteamGameId=STEAM_APP_ID)
    return subprocess.Popen(
        [str(game_dir / GAME_EXE), "-eac-nop-loaded"], cwd=str(game_dir), env=env
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:  # read-only
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def has_eac(module_names) -> bool:
    return any(EAC_MARKER in n.lower() for n in module_names)

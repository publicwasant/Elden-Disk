"""Offline launch: eldenring.exe -eac-nop-loaded, with Steam IDs passed via env vars."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from ..game.processes import GAME_EXE

STEAM_APP_ID = "1245620"


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


DETACHED_PROCESS, CREATE_NEW_PROCESS_GROUP = 0x00000008, 0x00000200


def creation_flags() -> int:
    """The game must not share the host's console. A child on the same console receives the host's Ctrl+C (it quits
    with it) and is killed when the console window is closed, which would defeat "Ctrl+C keeps the game running" and
    "closing the console leaves the restore to `vault restore`". Detached + own process group: neither reaches it."""
    return (DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP) if sys.platform == "win32" else 0


def launch(game_dir: Path) -> subprocess.Popen:
    env = dict(os.environ, SteamAppId=STEAM_APP_ID, SteamGameId=STEAM_APP_ID)
    return subprocess.Popen(
        [str(game_dir / GAME_EXE), "-eac-nop-loaded"], cwd=str(game_dir), env=env,
        creationflags=creation_flags(), close_fds=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

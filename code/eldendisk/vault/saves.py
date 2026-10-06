"""Finding and checking the live save folder (%APPDATA%\\EldenRing\\<SteamID64>), and remembering it in the registry."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .errors import VaultError

SAVE_FILE_HINT = ".sl2"
REG_KEY_PATH = r"Software\EldenDisk"


def load_registry_save_dir() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY_PATH, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, "SaveDir")
            if val and Path(val).is_dir():
                p = Path(val)
                if any(f.suffix.lower() == SAVE_FILE_HINT for f in p.iterdir() if f.is_file()):
                    return str(p)
    except Exception:
        return None
    return None


def save_registry_save_dir(save_dir: str) -> None:
    if sys.platform != "win32" or not save_dir:
        return
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY_PATH) as key:
            winreg.SetValueEx(key, "SaveDir", 0, winreg.REG_SZ, str(save_dir))
    except Exception:
        pass


def find_save_dir(appdata: Path | None = None, base_dir: Path | None = None) -> Path:
    """%APPDATA%\\EldenRing\\<SteamID64>. Exactly one candidate or it refuses to guess (A5, safety rule 5)."""
    if appdata is None:
        reg_dir = load_registry_save_dir()
        if reg_dir:
            p = Path(reg_dir)
            if p.is_dir() and any(f.suffix.lower() == SAVE_FILE_HINT for f in p.iterdir() if f.is_file()):
                return p

    base = Path(appdata) if appdata else Path(os.environ.get("APPDATA", "")) / "EldenRing"
    if not base.is_dir():
        raise VaultError(f"save root not found: {base} (use --save-dir)")
    cands = [d for d in base.iterdir() if d.is_dir() and d.name.isdigit()
             and any(f.suffix.lower() == SAVE_FILE_HINT for f in d.iterdir() if f.is_file())]
    if len(cands) != 1:
        names = ", ".join(d.name for d in cands) or "none"
        raise VaultError(f"expected exactly one save folder under {base}, found {len(cands)} ({names}); use --save-dir")

    found = cands[0]
    if appdata is None:
        save_registry_save_dir(str(found))
    return found


def check_live_dir(live_dir: Path) -> None:
    """Refuse folders that cannot be a save folder (restore deletes unknown files inside it)."""
    p = Path(live_dir).resolve()
    if not p.is_dir():
        raise VaultError(f"save folder does not exist: {p}")
    if p == Path(p.anchor) or p == Path.home().resolve() or len(p.parts) < 3:
        raise VaultError(f"refusing to treat {p} as a save folder")
    if not any(f.is_file() for f in p.rglob("*")):
        raise VaultError(f"save folder has no files: {p}")

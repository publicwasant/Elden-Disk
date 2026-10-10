"""Where the vault lives. Resolution order for every command: `--vault` > the path remembered in the Registry >
`%LOCALAPPDATA%\\EldenDisk\\vault`.

The default is deliberately NOT next to the exe: the exe sits in `build/dist` while it is developed, and a rebuild deletes that folder, and a vault holds
the only clean copy of the save. `run --vault X` remembers X (same Registry key as `--save-dir`), so `read`, `write` and
`vault` find the very same vault without repeating the flag.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .errors import VaultError
from .saves import REG_KEY_PATH

VAULT_VALUE = "VaultDir"


def default_vault_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / "AppData" / "Local") / "EldenDisk" / "vault"


def load_registry_vault_dir() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY_PATH, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, VAULT_VALUE)
            return str(val) if val else None
    except Exception:
        return None


def save_registry_vault_dir(vault_dir: str) -> None:
    if sys.platform != "win32" or not vault_dir:
        return
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY_PATH) as key:
            winreg.SetValueEx(key, VAULT_VALUE, 0, winreg.REG_SZ, str(vault_dir))
    except Exception:
        pass


def resolve_vault(explicit: str | None, *, remember: bool = False) -> Path:
    """The vault directory to use. `remember=True` (only `run`) stores an explicit choice in the Registry."""
    if explicit:
        path = Path(explicit)
        if remember:
            save_registry_vault_dir(str(path))
        return path
    remembered = load_registry_vault_dir()
    if remembered:
        path = Path(remembered)
        if path.is_dir() or path.parent.is_dir():
            return path
        # never fall back to a fresh empty vault: an owed restore would become invisible
        raise VaultError(f"the remembered vault {path} is not available (its folder is missing); "
                         "pass --vault to choose one")
    return default_vault_dir()

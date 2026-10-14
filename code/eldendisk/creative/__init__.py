"""The creative features (1.8.0, spec 1.8.0 part 2): what exists only in the parallel world. Each is a sub-package: `innovate_spells`
(new spells built into regulation.bin), `scripts` (your Python scripts next to the game), `resurrect` (beaten bosses alive again). What
they build and keep lives in the vault: `<vault>\\creative\\` (`--creative-dir` replaces it). The package never touches the vault or the
host; only scripts/backend.py touches the game (tests/test_architecture.py)."""
from __future__ import annotations

from pathlib import Path

NAMES = ("innovate-spells", "scripts", "resurrect")
SUBDIR = "creative"                          # <vault>/creative
OLD_SUBDIRS = ("design", "extension")        # the names of that folder before 1.8.0 (renamed once by commands/innovate.py)


def data_dir(explicit: str | None, vault_dir: Path | str) -> Path:
    """The folder the creative features write in: `--creative-dir`, else `<vault>/creative`."""
    return Path(explicit) if explicit else Path(vault_dir) / SUBDIR


def open_spells(creative_folder: Path | str, spec_path: Path | str | None = None):
    from .innovate_spells.service import Spells
    return Spells(Path(creative_folder), spec_path)

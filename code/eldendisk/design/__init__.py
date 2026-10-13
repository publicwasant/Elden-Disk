"""Designs: optional features that build things for the game outside the game. Each lives in its own sub-package
(`innovate_items`, with one sub-package per kind of item: `innovate_items.spells`) and keeps its output in the vault:
`<vault>\\design\\innovate-items\\spells\\` (`--design-dir` replaces `<vault>\\design`). The files a design builds are
the ones the vault swaps into the game, so they live under the vault's roof. This package never touches the game, the vault or
the host: it is given the folder and builds files; the commands decide what to do with them."""
from __future__ import annotations

from pathlib import Path

NAMES = ("innovate-items",)
KINDS = {"innovate-items": ("spells",)}        # design -> its kinds of items
SUBDIR = "design"                           # <vault>/design


def data_dir(explicit: str | None, vault_dir: Path | str) -> Path:
    """The folder the designs write in: `--design-dir`, else `<vault>/design`."""
    return Path(explicit) if explicit else Path(vault_dir) / SUBDIR


def open_spells(design_folder: Path | str, spec_path: Path | str | None = None):
    from .innovate_items.spells.service import Spells
    return Spells(Path(design_folder), spec_path)

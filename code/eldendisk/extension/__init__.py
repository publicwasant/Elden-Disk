"""Extensions: optional features that build things for the game outside the game. Each lives in its own sub-package
(`innovate_items`, with one sub-package per kind of item: `innovate_items.spells`) and keeps its output in the vault:
`<vault>\\extension\\innovate-items\\spells\\` (`--extension-dir` replaces `<vault>\\extension`). The files an extension builds are
the ones the vault swaps into the game, so they live under the vault's roof. This package never touches the game, the vault or
the host: it is given the folder and builds files; the commands decide what to do with them."""
from __future__ import annotations

from pathlib import Path

NAMES = ("innovate-items",)
KINDS = {"innovate-items": ("spells",)}        # extension -> its kinds of items
SUBDIR = "extension"                           # <vault>/extension


def data_dir(explicit: str | None, vault_dir: Path | str) -> Path:
    """The folder the extensions write in: `--extension-dir`, else `<vault>/extension`."""
    return Path(explicit) if explicit else Path(vault_dir) / SUBDIR


def open_spells(ext_dir: Path | str, spec_path: Path | str | None = None):
    from .innovate_items.spells.service import Spells
    return Spells(Path(ext_dir), spec_path)

"""Extensions: optional features that build things for the game outside the game. Each lives in its own sub-package and keeps
its output in `%LOCALAPPDATA%\\EldenDisk\\extension\\<name>` (`--extension-dir` overrides). This package never touches the game,
the vault or the host: it builds files; the commands decide what to do with them."""
from __future__ import annotations

import os
from pathlib import Path

NAMES = ("customize-items",)


def default_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / "AppData" / "Local") / "EldenDisk" / "extension"


def data_dir(explicit: str | None = None) -> Path:
    return Path(explicit) if explicit else default_dir()


def open_customize_items(explicit: str | None = None, spec_path: Path | str | None = None):
    from .customize_items.service import CustomizeItems
    return CustomizeItems(data_dir(explicit), spec_path)

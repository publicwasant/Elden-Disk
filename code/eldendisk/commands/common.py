"""Pieces several commands share."""
from __future__ import annotations

import argparse
from pathlib import Path

from .. import ui
from ..logbook import book
from ..vault import SessionLog, saves


def live_dir(save_dir: str | None) -> Path:
    """The live save folder: --save-dir (remembered in the registry when valid), else auto-detected."""
    if save_dir:
        p = Path(save_dir)
        if p.is_dir():
            saves.save_registry_save_dir(str(p))
        return p
    return saves.find_save_dir()


VAULT_HELP = "snapshot vault directory (default: the one remembered by `run --vault`, else %%LOCALAPPDATA%%\\EldenDisk\\vault)"


def add_vault_option(parser: argparse.ArgumentParser, *, leaf: bool = False) -> None:
    """`--vault` on a command group and, with leaf=True, on its subcommands too.

    The leaf copy uses SUPPRESS so that `--vault V` given before the subcommand is not overwritten by the default.
    """
    parser.add_argument("--vault", default=argparse.SUPPRESS if leaf else None,
                        help=VAULT_HELP if not leaf else "snapshot vault directory")


def add_verbose(parser: argparse.ArgumentParser, *, leaf: bool = False) -> None:
    """`-v`: show the log itself, live, instead of the concise lines (on groups and on their subcommands)."""
    parser.add_argument("-v", "--verbose", action="store_true", default=argparse.SUPPRESS if leaf else False,
                        help="show the full log live (the lines that go to <vault>/eldendisk.log) instead of the concise view")


def session_log() -> SessionLog:
    """The session log whose events also go to the tool's logbook (log file and console)."""
    return SessionLog(emit=book.emit)


def begin(args, title: str, rows: list[tuple[str, str]]) -> None:
    """Start of a long-running command: the configuration goes to the log; the banner shows it unless `-v` is on
    (then the console shows the log itself)."""
    for k, v in rows:
        book.d("config", f"{k}: {v}")
    if not getattr(args, "verbose", False):
        ui.header(title, rows)


def log_config(label: str, path) -> None:
    """`config: <label>: <path> (<where>)` in the log, only when the file is not the copy built into the exe (one the user put next to
    it, `--offsets FILE`, or the source tree): the built-in one is the same every time, so it is not said every time."""
    from ..paths import describe_resource
    where = describe_resource(path)
    if where != "embedded":
        book.d("config", f"{label}: {path} ({where})")


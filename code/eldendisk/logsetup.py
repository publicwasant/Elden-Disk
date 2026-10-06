"""Starts the logbook for one command: the log file next to the vault and the console sink."""
from __future__ import annotations

import sys

from . import __version__, ui
from .logbook import LOG_NAME, book
from .vault import VaultError, resolve_vault

LONG_RUNNING = ("run", "read")   # commands that stay open: their console lines carry the time


def start(args, argv: list[str]) -> None:
    verbose = bool(getattr(args, "verbose", False))
    console = ui.raw_sink() if verbose else ui.pretty_sink(show_time=args.cmd in LONG_RUNNING)
    try:
        log_file = resolve_vault(getattr(args, "vault", None)) / LOG_NAME
    except VaultError:
        log_file = None   # the remembered vault is unavailable: the command reports that itself
    book.configure(file=log_file, console=console)
    book.d("cli", f"eldendisk {__version__} {' '.join(argv)}".rstrip())


def finish(code: int) -> None:
    book.d("cli", f"exit {code}")
    book.close()


def argv_of(argv) -> list[str]:
    return list(sys.argv[1:] if argv is None else argv)

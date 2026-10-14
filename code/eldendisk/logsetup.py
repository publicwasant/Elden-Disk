"""Starts the logbook for one command: the log file next to the vault and the console sink."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import ui
from .logbook import LOG_NAME, book
from .vault import VaultError, resolve_vault

STARTED_BY = "ELDENDISK_STARTED_BY"   # set by `run` for the steps it starts (their command line is in run's own log line)
LONG_RUNNING = ("run", "read", "export", "scripts")   # commands that stay open: their console lines carry the time


def _short_program(prog: str) -> str:
    """The program without its folder: `eldendisk.exe`, `python`. (Windows hands the exe's full path to the process.)"""
    p = Path(prog)
    return p.name if p.is_absolute() else prog


def command_line(argv: list[str], orig: list[str] | None = None) -> str:
    """The command as typed: `eldendisk.exe run -v`, `python -m eldendisk run`. `orig` is `sys.orig_argv` (program and
    interpreter options included). Without it (called from code or a test) the program is just `eldendisk`."""
    head = ["eldendisk"]
    if orig and len(orig) > len(argv) and orig[len(orig) - len(argv):] == list(argv):
        head = list(orig[:len(orig) - len(argv)])
        head[0] = _short_program(head[0])
    return subprocess.list2cmdline(head + list(argv))


def start(args, argv: list[str], real: bool = False) -> None:
    """`real`: argv is what this process was started with, so sys.orig_argv says how it was typed."""
    verbose = bool(getattr(args, "verbose", False))
    console = ui.raw_sink() if verbose else ui.pretty_sink(show_time=args.cmd in LONG_RUNNING)
    try:
        log_file = resolve_vault(getattr(args, "vault", None)) / LOG_NAME
    except VaultError:
        log_file = None   # the remembered vault is unavailable: the command reports that itself
    book.configure(file=log_file, console=console)
    if not os.environ.get(STARTED_BY):        # a step `run` started: its line `design: starting: ...` says it already
        book.d("client", "run: " + command_line(argv, getattr(sys, "orig_argv", None) if real else None))
    if verbose:
        on, why = ui.links_status(sys.stderr)
        book.d("client", f"clickable paths {'on' if on else 'off'}: {why}")


def finish(code: int) -> None:
    book.d("client", f"exit {code}")
    book.close()


def argv_of(argv) -> list[str]:
    return list(sys.argv[1:] if argv is None else argv)

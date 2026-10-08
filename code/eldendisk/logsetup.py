"""Starts the logbook for one command: the log file next to the vault and the console sink."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__, ui
from .logbook import LOG_NAME, book
from .vault import VaultError, resolve_vault

LONG_RUNNING = ("run", "read")   # commands that stay open: their console lines carry the time


def _short_program(prog: str, cwd: Path) -> str:
    """The program as a person types it: `.\\eldendisk.exe` below the current folder, the bare name when it is found on PATH,
    otherwise as given."""
    p = Path(prog)
    if not p.is_absolute():
        return prog
    if p.name.lower().startswith("python"):          # an interpreter: `python -m eldendisk ...`
        return p.name
    try:
        return "." + os.sep + str(p.relative_to(cwd))
    except ValueError:
        pass
    found = shutil.which(p.name)
    if found and os.path.normcase(os.path.abspath(found)) == os.path.normcase(str(p)):
        return p.name
    return prog


def command_line(argv: list[str], orig: list[str] | None = None, cwd: Path | None = None) -> str:
    """The command as typed: `.\\eldendisk.exe run -v`, `python -m eldendisk run`. `orig` is `sys.orig_argv` (program and
    interpreter options included). Without it (called from code or a test) the program is just `eldendisk`."""
    head = ["eldendisk"]
    if orig and len(orig) > len(argv) and orig[len(orig) - len(argv):] == list(argv):
        head = list(orig[:len(orig) - len(argv)])
        head[0] = _short_program(head[0], cwd or Path.cwd())
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
    book.d("cli", f"version {__version__}")
    book.d("cli", command_line(argv, getattr(sys, "orig_argv", None) if real else None))


def finish(code: int) -> None:
    book.d("cli", f"exit {code}")
    book.close()


def argv_of(argv) -> list[str]:
    return list(sys.argv[1:] if argv is None else argv)

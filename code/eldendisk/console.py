"""Small console helpers shared by the commands."""
from __future__ import annotations

import struct
import sys

_ASCII = {"\u2713": "OK", "\u2716\ufe0f": "FAILED", "\u2716": "FAILED", "\u2014": "-", "\u2192": "->",
          "\u2500": "-", "\u2502": "|", "\u256d": "+", "\u2570": "+", "\u251c": "+", "\u2514": "+", "\u2026": "...",
          "\u25a0": "#", "\u00b7": "-"}


def printable(msg: str, encoding: str | None) -> str:
    """`msg` as the console can show it. Consoles with a legacy code page (cp874, cp1252, ...) cannot print the check
    mark, and Python would then print it as a literal `\\u2713`; use plain words instead."""
    enc = encoding or "ascii"
    try:
        msg.encode(enc)
        return msg
    except UnicodeEncodeError:
        pass
    for symbol, word in _ASCII.items():
        msg = msg.replace(symbol, word)
    return msg.encode(enc, errors="replace").decode(enc)


def log(msg: str) -> None:
    print(printable(msg, getattr(sys.stderr, "encoding", None)), file=sys.stderr, flush=True)


def require_windows_x64() -> None:
    if sys.platform != "win32":
        sys.exit("This tool only runs on Windows.")
    if struct.calcsize("P") != 8:
        sys.exit("64-bit Python is required.")

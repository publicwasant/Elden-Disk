"""What the console shows. One look for every command:

    23:41:02  ✓  vault   snapshot 20261007-234102, 5 files verified

Without `-v` the log events are rendered in this concise layout (warnings and errors in colour when the console
supports it). With `-v` the console shows the raw log lines (see `logbook`) instead, nothing else.
Event lines go to stderr, the result of a command (tables, status) to stdout.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from urllib.parse import quote
from typing import Callable

from . import __version__
from .console import printable
from .logbook import Event, format_line, parse_line

_SYMBOLS = {"ok": ("\u2713", "+"), "info": ("\u00b7", "-"), "warn": ("!", "!"), "error": ("\u2716", "x")}
_COLORS = {"ok": "32", "warn": "33", "error": "31", "dim": "2", "bold": "1", "cyan": "36", "hot": "1;33", "tick": "35", "unknown": "36"}
RULE = "\u2500"


def use_color(stream) -> bool:
    """NO_COLOR wins, FORCE_COLOR forces (IDE run windows are not terminals but show ANSI), else a real terminal."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    try:
        if not stream.isatty():
            return False
    except (AttributeError, ValueError):
        return False
    return _enable_windows_ansi(stream)


def _enable_windows_ansi(stream) -> bool:
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = k32.GetStdHandle(-12 if stream is sys.stderr else -11)
        mode = wintypes.DWORD()
        if not k32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(k32.SetConsoleMode(handle, mode.value | 0x0004))   # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        return False


def paint(text: str, kind: str, color: bool) -> str:
    return f"\x1b[{_COLORS[kind]}m{text}\x1b[0m" if color and kind in _COLORS else text


_TICKS = re.compile(r"`([^`\r\n]+)`")
_FILE_WORD = re.compile(r"(?<![\\/\w.])regulation\.bin\b")       # the file's name on its own, not as the end of a path


def emphasize(text: str, color: bool) -> str:
    """`name` -> name in cyan on a colour console (the backticks are what the colour replaces); a bare `regulation.bin` is cyan too.
    Without colour the text is unchanged."""
    if not color:
        return text
    text = _TICKS.sub(lambda m: paint(m.group(1), "cyan", True), text)
    return _FILE_WORD.sub(lambda m: paint(m.group(0), "cyan", True), text)


def symbol(kind: str, encoding: str | None) -> str:
    uni, plain = _SYMBOLS[kind]
    try:
        uni.encode(encoding or "ascii")
        return uni
    except UnicodeEncodeError:
        return plain


def kind_of(e: Event) -> str:
    return "error" if e.level == "E" else "warn" if e.level == "W" else "ok" if e.ok else "info"


# ---- clickable paths (OSC 8 hyperlinks) ----
_PATH = re.compile(r"[A-Za-z]:\\[^\"'<>|*?\r\n\x1b]*")     # a Windows path; it may contain spaces, so the end is found by looking
_MODERN = ("WT_SESSION", "VTE_VERSION", "KITTY_WINDOW_ID", "WEZTERM_EXECUTABLE")            # terminals known to understand OSC 8
_MODERN_PROGRAMS = ("vscode", "iTerm.app", "WezTerm", "ghostty")


def links_status(stream) -> tuple[bool, str]:
    """(clickable paths on?, why). Only a real terminal known to understand OSC 8 (Windows Terminal, VS Code, ...) turns them on
    by itself; ELDENDISK_LINKS=1 forces it on, =0 off. IDE run windows (FORCE_COLOR) are not trusted: an unknown escape could print as text."""
    flag = os.environ.get("ELDENDISK_LINKS")
    if os.environ.get("NO_COLOR"):
        return False, "NO_COLOR is set"
    if flag is not None:
        on = flag.strip().lower() in ("1", "true", "yes", "on")
        return on, f"ELDENDISK_LINKS={flag}"
    try:
        if not stream.isatty():
            return False, "output is not a terminal"
    except (AttributeError, ValueError):
        return False, "output is not a terminal"
    for k in _MODERN:
        if os.environ.get(k):
            return True, f"{k} is set"
    prog = os.environ.get("TERM_PROGRAM")
    if prog in _MODERN_PROGRAMS:
        return True, f"TERM_PROGRAM={prog}"
    return False, "terminal not known to support links (set ELDENDISK_LINKS=1 to try)"


def use_links(stream) -> bool:
    return links_status(stream)[0]


def _link(path: str) -> str:
    url = "file:///" + quote(path.replace("\\", "/"), safe="/:")
    return f"\x1b]8;;{url}\x1b\\{path}\x1b]8;;\x1b\\"


def linkify(text: str, exists=None) -> str:
    """Wrap every Windows path in `text` that exists (a file or a folder) in an OSC 8 hyperlink. The path may have spaces
    (`...\\ELDEN RING\\Game\\regulation.bin`), so the longest prefix ending at a space or at the end that exists is taken."""
    exists = exists or os.path.exists

    def sub(m):
        raw = m.group(0)
        ends = sorted({len(raw)} | {i for i, c in enumerate(raw) if c == " "}, reverse=True)
        for end in ends:
            cand = raw[:end].rstrip(" .,;:)]")
            if len(cand) > 3 and exists(cand):
                return _link(cand) + raw[len(cand):]
        return raw
    return _PATH.sub(sub, text)


def _emit(text: str, stream=None) -> None:
    stream = stream or sys.stderr
    if use_links(stream):
        text = linkify(text)
    print(printable(text, getattr(stream, "encoding", None)), file=stream, flush=True)


def pretty_sink(*, show_time: bool = False, stream=None) -> Callable[[Event], None]:
    """Concise lines: time (long-running commands only), symbol, tag, message. Verbose and debug events are not shown."""
    def sink(e: Event) -> None:
        if e.level in "VD":
            return
        out = stream or sys.stderr
        color = use_color(out)
        kind = kind_of(e)
        sym = paint(symbol(kind, getattr(out, "encoding", None)), kind, color)
        stamp = paint(f"{e.when:%H:%M:%S}", "dim", color) + "  " if show_time else ""
        tag = paint(f"{e.tag:<6}", "dim", color)
        msg = paint(e.msg, kind, color) if kind in ("warn", "error") else emphasize(e.msg, color)
        _emit(f" {stamp}{sym}  {tag} {msg}", out)
    return sink


_CLI_LINE = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d{3} +\d+ D client *: )(?!(?:exit -?\d+|version \S+|clickable paths .*)$)(.+)$")


def _dim_line(line: str, color: bool) -> str:
    """A debug line of the log in dim; the command that started a process (`D client : eldendisk.exe run -v`) in cyan.
    Only the console gets the colour: the file keeps the plain line."""
    m = _CLI_LINE.match(line) if color else None
    if m:
        return paint(m.group(1), "dim", color) + paint(m.group(2), "cyan", color)
    return paint(line, "dim", color)


def raw_sink(stream=None) -> Callable[[Event], None]:
    """`-v`: the log itself, live."""
    def sink(e: Event) -> None:
        out = stream or sys.stderr
        color = use_color(out)
        kind = {"E": "error", "W": "warn", "V": "dim", "D": "dim"}.get(e.level)
        line = format_line(e)
        _emit(_dim_line(line, color) if e.level == "D" else paint(line, kind, color) if kind else emphasize(line, color), out)
    return sink


def raw_line(line: str, stream=None) -> None:
    """A log line written by another command, shown as it is in the file (coloured by its level letter)."""
    out = stream or sys.stderr
    got = parse_line(line)
    kind = {"E": "error", "W": "warn", "V": "dim", "D": "dim"}.get(got[1]) if got else None
    color = use_color(out)
    _emit(_dim_line(line, color) if got and got[1] == "D" else paint(line, kind, color) if kind else emphasize(line, color), out)


def header(title: str, rows: list[tuple[str, str]] | None = None, stream=None) -> None:
    """Command banner: title, rule and key/value rows. Printed by `run` and `read` before their events."""
    stream = stream or sys.stderr
    color = use_color(stream)
    width = max(24, min(shutil.get_terminal_size((80, 24)).columns - 2, 64))
    _emit(f" {paint(f'Elden-Disk {__version__}', 'bold', color)} \u00b7 {title}", stream)
    _emit(" " + paint(RULE * width, "dim", color), stream)
    if rows:
        key = max(len(k) for k, _ in rows)
        for k, v in rows:
            _emit(f"   {paint(k.ljust(key), 'dim', color)}  {v}", stream)
        _emit(" " + paint(RULE * width, "dim", color), stream)


def mark(kind: str, stream=None) -> str:
    """The coloured symbol of `kind` for a result on stdout (table cells)."""
    stream = stream or sys.stdout
    return paint(symbol(kind, getattr(stream, "encoding", None)), kind, use_color(stream))


def out(text: str = "") -> None:
    """Result of a command (stdout)."""
    _emit(text, sys.stdout)


def result(kind: str, text: str) -> None:
    """A result line in the same look as events but without time or tag (stdout), e.g. for `vault status`."""
    stream = sys.stdout
    color = use_color(stream)
    sym = paint(symbol(kind, getattr(stream, "encoding", None)), kind, color)
    _emit(f" {sym}  {text}", stream)


def format_rows(items, *, indent: int = 1, color: bool = False, hot=frozenset(), ticking=frozenset(),
                columns: int | None = None) -> list[str]:
    """Rows of `Row(level, key, value|None, path)` as tree lines: `value` None makes the key a heading, the others align.

    Values whose path is in `hot` are highlighted (a change just happened); those in `ticking` (countdowns that change
    all the time) have their own colour, `hot` wins; with `columns` every line is cut to fit (so it never wraps).
    """
    items = list(items)
    width = min(44, max((2 * r.indent + len(r.key) for r in items if r.value is not None), default=0))
    lines = []
    for r in items:
        pad = " " * indent + "  " * r.indent
        if r.value is None:
            title = r.key if columns is None else r.key[:max(0, columns - 1 - len(pad))]
            lines.append(pad + paint(title, "bold", color))
            continue
        key = r.key.ljust(max(0, width - 2 * r.indent))
        value = r.value
        if columns is not None:
            room = columns - 1 - len(pad) - len(key) - 2
            if len(value) > room:
                value = value[:max(0, room - 1)] + "\u2026" if room > 1 else ""
        kind = "hot" if r.path in hot else "tick" if r.path in ticking else ""
        lines.append(pad + paint(key, "dim", color) + "  " + paint(value, kind, color))
    return lines


def rows(items, indent: int = 1) -> None:
    """The tree on stdout (see `format_rows`)."""
    stream = sys.stdout
    for line in format_rows(items, indent=indent, color=use_color(stream)):
        _emit(line, stream)


def _join(segs, width: int, color: bool) -> str:
    """Painted text of `(text, kind)` segments, cut to `width` visible characters."""
    out, left = [], width
    for text, kind in segs:
        if left <= 0:
            break
        text = text[:left]
        left -= len(text)
        out.append(paint(text, kind, color) if kind else text)
    return "".join(out)


def format_ledger(title: str, summary: str, lines, *, color: bool = False, columns: int = 80, max_rows: int = 1000,
                  waiting: str | None = None) -> list[str]:
    """A monitor's table: a title line, a column header, then one row per id (`lines`: reader.ledger.Line).

        buffs     7 active · 23 seen · 5 unmapped
          id  name                  timer           time
        +  311100  Gold Scarab        permanent       04:06:12.750
        -  2000000  Unknown                           04:06:07.512

    `max_rows` bounds the whole block; rows that do not fit are summarised in one line at its end. A row that just
    changed is highlighted, an id that is not mapped is shown as `Unknown`.
    """
    head = paint(title, "bold", color) + "   " + (paint(f"waiting: {waiting}", "warn", color) if waiting else summary)
    out = [" " + head]
    lines = list(lines)
    if not lines:
        out.append("    " + paint("(nothing yet)", "dim", color))
        return out[:max_rows]
    idw = max(9, max(len(str(l.id)) for l in lines))
    detw = max((len(l.detail) for l in lines), default=0)
    stampw = 12
    fixed = 4 + idw + 2 + 2 + (detw + 2 if detw else 0) + stampw
    namew = max(7, min(30, max(len(l.name or "Unknown") for l in lines), columns - 1 - fixed))
    cols = ["id".rjust(idw), "name".ljust(namew)] + (["timer".ljust(detw)] if detw else []) + ["time"]
    out.append("    " + paint("  ".join(cols), "dim", color))
    room = max_rows - len(out)
    shown = lines if len(lines) <= room else lines[:max(0, room - 1)]
    for l in shown:
        name = l.name if l.name is not None else "Unknown"
        if len(name) > namew:
            name = name[:namew - 1] + "\u2026"
        hot = "hot" if l.hot else ""
        segs = [(" ", ""), ("+" if l.active else "-", hot or ("ok" if l.active else "dim")), ("  ", ""),
                (str(l.id).rjust(idw), hot), ("  ", ""),
                (name.ljust(namew), hot or ("unknown" if l.name is None else ""))]
        if detw:
            segs += [("  ", ""), (l.detail.ljust(detw), hot)]
        segs += [("  ", ""), (l.stamp, hot or "dim")]
        out.append(_join(segs, columns - 1, color))
    if len(shown) < len(lines):
        out.append("    " + paint(f"\u2026 {len(lines) - len(shown)} more (make the window taller, or use --mapped / --unmapped)",
                                  "dim", color))
    return out


def can_redraw(stream=None) -> bool:
    """True when `stream` is a terminal that moves the cursor (not an IDE run window, a pipe or `TERM=dumb`)."""
    stream = stream or sys.stdout
    try:
        if not stream.isatty() or os.environ.get("TERM") == "dumb":
            return False
    except (AttributeError, ValueError):
        return False
    return _enable_windows_ansi(stream)


class Screen:
    """A block of lines on stdout that is redrawn where it stands (cursor up, rewrite every line, clear what is left).

    It never shows more lines than fit the window (the rest is summarised), and cuts nothing else: callers pass lines
    already fitted to `columns()`. Each frame is one write, so the terminal does not flicker.
    """

    def __init__(self, stream=None):
        self.stream = stream or sys.stdout
        self.height = 0
        self._hidden = False

    @staticmethod
    def size() -> tuple[int, int]:
        t = shutil.get_terminal_size((80, 24))
        return max(20, t.columns), max(4, t.lines)

    def show(self, lines: list[str]) -> None:
        rows = self.size()[1] - 1
        if len(lines) > rows:
            hidden = len(lines) - (rows - 1)
            lines = lines[:rows - 1] + [f" \u2026 {hidden} more lines (make the window taller, or use --query)"]
        enc = getattr(self.stream, "encoding", None)
        lines = [printable(l, enc) for l in lines]
        out = []
        if not self._hidden:
            out.append("\x1b[?25l")
            self._hidden = True
        if self.height:
            out.append(f"\x1b[{self.height}A\r")
        out += [f"\x1b[2K{line}\n" for line in lines]
        spare = self.height - len(lines)
        if spare > 0:
            out += ["\x1b[2K\n"] * spare + [f"\x1b[{spare}A"]
        self.height = len(lines)
        self.stream.write("".join(out))
        self.stream.flush()

    def detach(self) -> None:
        """Leave what is on screen where it is; the next frame starts below it (after other output)."""
        self.height = 0

    def close(self) -> None:
        if self._hidden:
            self.stream.write("\x1b[?25h")
            self.stream.flush()
            self._hidden = False


def fields(rows: list[tuple[str, str]], indent: int = 5) -> None:
    """Aligned `key  value` rows under a result line (stdout)."""
    stream = sys.stdout
    color = use_color(stream)
    key = max(len(k) for k, _ in rows)
    for k, v in rows:
        _emit(" " * indent + paint(k.ljust(key), "dim", color) + "  " + v, stream)

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
import threading
import time
from datetime import datetime
from urllib.parse import quote
from typing import Callable

from . import __version__
from .console import printable
from .logbook import EXT_TAG, TAG_WIDTH, Event, book, format_line, parse_line

_SYMBOLS = {"ok": ("\u2713", "+"), "info": ("\u00b7", "-"), "warn": ("!", "!"), "error": ("\u2716", "x")}
_COLORS = {"ok": "32", "warn": "33", "error": "31", "dim": "2", "bold": "1", "cyan": "36", "hot": "1;33", "tick": "35", "unknown": "36", "spell": "35", "file": "38;5;208",
           "id": "38;5;179", "addr": "38;5;75", "path": "38;5;110"}
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


FILE_EXTENSIONS = ("bin", "sl2", "bak", "err", "vdf", "json", "exe", "log", "txt", "dll", "ini", "cfg", "csv", "md", "py",
                   "toml", "xml", "tmp", "zip")
# A file name with an extension: `regulation.bin`, `ER0000.sl2.bak`, `steam_autocloud.vdf`. Not the end of a path (`...\Game\regulation.bin`
# stays as it is: colour codes in the middle of a path would break its clickable link) and not part of a longer word or dotted name.
_FILE_NAME = r"[A-Za-z0-9_][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*\.(?:%s)\b" % "|".join(FILE_EXTENSIONS)
_FILE_ONLY = re.compile(_FILE_NAME, re.IGNORECASE)
_EMPHASIS = re.compile(r"`([^`\r\n]+)`|(?<![\\/\w.:-])(%s)(?![\w\\/-])" % _FILE_NAME, re.IGNORECASE)


def emphasize(text: str, color: bool, resume: str = "", ticks: bool = True) -> str:
    """On a colour console: a file name with an extension (`regulation.bin`, `ER0000.sl2.bak`, `steam_autocloud.vdf`), with or without
    backticks, is orange; any other `name` in backticks is cyan (the backticks are what the colour replaces; `ticks=False` leaves them,
    as in warnings). `resume` is the colour code of the line the text sits in, put back after each painted word. The end of a path is
    not touched here (see `paint_tails`). Without colour the text is unchanged."""
    if not color:
        return text

    def sub(m):
        if m.group(1) is not None:
            if not ticks:
                return m.group(0)
            return paint(m.group(1), "file" if _FILE_ONLY.fullmatch(m.group(1)) else "cyan", True) + resume
        return paint(m.group(2), "file", True) + resume
    return _EMPHASIS.sub(sub, text)


_TAIL = re.compile(r"(?<=[\\/])(%s)(?![\w\\/-])" % _FILE_NAME, re.IGNORECASE)


def paint_tails(text: str, resume: str = "") -> str:
    """The file name at the end of a path (`...\\Game\\regulation.bin`) in orange; the folders stay as they are."""
    return _TAIL.sub(lambda m: paint(m.group(1), "file", True) + resume, text)


_ANSI = re.compile(r"(\x1b\[[0-9;]*m)")
# An id (4 or more digits: 114880, 2230000) or an address (0x7ff3cbbb0000). Not part of a word, a path, a time, a decimal or a date
# (`20261012-185726`), and never inside an escape sequence.
_NUMBER = re.compile(r"(?<![\w.:\\/\-#])(0x[0-9a-fA-F]{4,}|[0-9]{4,})(?![\w.:\\/\-])")
_HEX = re.compile(r"(?<![\w&])#([0-9a-fA-F]{6})(?![\w])")       # a colour as the design writes it: #90D5FF


def paint_hex(text: str, color: bool, resume: str = "") -> str:
    """On a colour console: each colour `#RRGGBB` written in that colour (bright, even in a dim debug line). Never inside an escape."""
    if not color or "#" not in text:
        return text
    parts = _ANSI.split(text)
    for i in range(0, len(parts), 2):
        parts[i] = _HEX.sub(lambda m: "\x1b[22;38;2;%d;%d;%dm%s\x1b[0m%s" % (
            int(m.group(1)[0:2], 16), int(m.group(1)[2:4], 16), int(m.group(1)[4:6], 16), m.group(0), resume), parts[i])
    return "".join(parts)


def paint_numbers(text: str, color: bool, resume: str = "") -> str:
    """On a colour console: ids and addresses (`114880`, `0x7ff3cbbb0000`) each in a colour of their own. `resume` is the colour code
    of the line the text sits in (a warning, a debug line), put back after each painted number."""
    if not color:
        return text
    parts = _ANSI.split(text)
    for i in range(0, len(parts), 2):
        parts[i] = _NUMBER.sub(lambda m: paint(m.group(1), "addr" if m.group(1).startswith("0x") else "id", True) + resume, parts[i])
    return paint_hex("".join(parts), color, resume)


def swatch(rgb, color: bool) -> str:
    """A little square in the colour `rgb` (three numbers, 1 = the full colour; above 1 shines brighter, shown as the full colour)."""
    if not color:
        return "\u25a0"
    r, g, b = (max(0, min(255, round(float(x) * 255))) for x in rgb)
    return f"\x1b[38;2;{r};{g};{b}m\u25a0\x1b[0m"


_SPELL_IDS: re.Pattern | None = None


def mark_spell_ids(ids) -> None:
    """The ids of the spells of the design (`reverse_curse_technique`, ...): on a colour console they are purple in the lines of the
    `ext` tag, wherever they appear (the list of names, a diff line `id.shop.price  1 -> 2`). The log file keeps plain text.
    An id inside a path or a longer word is left alone. Called again with the current design; no ids clears it."""
    global _SPELL_IDS
    ids = sorted({i for i in ids if i}, key=len, reverse=True)
    _SPELL_IDS = re.compile(r"(?<![\w\\/.-])(%s)(?![\w\\/-])" % "|".join(re.escape(i) for i in ids)) if ids else None


def highlight_spells(text: str, color: bool, tag: str) -> str:
    if not color or tag != EXT_TAG or _SPELL_IDS is None:
        return text
    return _SPELL_IDS.sub(lambda m: paint(m.group(1), "spell", True), text)


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


def _link(path: str, color: bool = False, resume: str = "") -> str:
    url = "file:///" + quote(path.replace("\\", "/"), safe="/:")
    shown = paint_tails(path, resume) if color else path       # the colour is in the visible text only, never in the url
    return f"\x1b]8;;{url}\x1b\\{shown}\x1b]8;;\x1b\\"


def linkify(text: str, exists=None, color: bool = False, resume: str = "") -> str:
    """Wrap every Windows path in `text` that exists (a file or a folder) in an OSC 8 hyperlink. The path may have spaces
    (`...\\ELDEN RING\\Game\\regulation.bin`), so the longest prefix ending at a space or at the end that exists is taken.
    `color`: the file name at the end of a path is orange in the visible text (never in the url); a path that is not linked gets it too."""
    exists = exists or os.path.exists
    tails = (lambda t: paint_tails(t, resume)) if color else (lambda t: t)

    def sub(m):
        raw = m.group(0)
        ends = sorted({len(raw)} | {i for i, c in enumerate(raw) if c == " "}, reverse=True)
        for end in ends:
            cand = raw[:end].rstrip(" .,;:)]")
            if len(cand) > 3 and exists(cand):
                return _link(cand, color, resume) + tails(raw[len(cand):])
        return tails(raw)
    return _PATH.sub(sub, text)


def _emit(text: str, stream=None, resume: str = "") -> None:
    """Print a line. `resume`: the colour code the whole line is painted in (warning, error, dim), put back after an orange file name."""
    stream = stream or sys.stderr
    color = use_color(stream)
    if use_links(stream):
        text = linkify(text, color=color, resume=resume)
    elif color:
        text = paint_tails(text, resume)
    line = printable(text, getattr(stream, "encoding", None))
    with _screen:
        live = _live if _live is not None and _live.stream is stream else None
        if live is not None:
            live.wipe()
        print(line, file=stream, flush=True)
        if live is not None:
            live.draw()


# ---- a step that takes a while: one status line redrawn in place ----
_screen = threading.RLock()        # taken for every write to the console that a status line may share
_live = None                       # the Working that is drawn now (at most one)
_FRAMES = "\u280b\u2819\u2839\u2838\u283c\u2834\u2826\u2827\u2807\u280f"
_FRAMES_ASCII = "|/-\\"


def seconds(s: float) -> str:
    """12.3 s, then 1:05 from a minute on."""
    return f"{s:.1f} s" if s < 60 else f"{int(s // 60)}:{int(s % 60):02d}"


class Working:
    """A step that takes a while (the build of the regulation, a few seconds):

        with ui.working("design", "building ...") as w:
            ...
            w.done("built")                       # -> a check-mark line that ends with the time it took

    On a real terminal with colour the step shows one line that spins and counts the seconds, redrawn in place; the lines of other
    events appear above it. Anywhere else (a pipe, an IDE run window, NO_COLOR, `-v`) there is no animation: the step is the plain
    start line, then the plain end line, as before (`short` is only for the spinning line). The log file gets the same two lines in both cases, never an escape."""

    def __init__(self, tag: str, text: str, *, short: str | None = None, stream=None, animate: bool | None = None, clock=time.monotonic,
                 interval: float = 0.1):
        self.tag, self.text, self.stream = tag, text, stream or sys.stderr
        self.short = short or text          # what the spinning line says (the log has `text`)
        self._clock, self._interval = clock, interval
        self.animated = (can_redraw(self.stream) and use_color(self.stream)) if animate is None else animate
        self.t0, self._frame, self._drawn, self._closed = 0.0, 0, False, False
        self._stop, self._thread = threading.Event(), None

    def elapsed(self) -> float:
        return self._clock() - self.t0

    def __enter__(self):
        global _live
        self.t0 = self._clock()
        with _screen:
            if _live is not None:
                self.animated = False            # one status line at a time
            elif self.animated:
                _live = self
        if self.animated:
            book.d(self.tag, self.text)          # the file has the line; the console has the spinner
            self.draw()
            self._thread = threading.Thread(target=self._spin, name="working", daemon=True)
            self._thread.start()
        else:
            book.i(self.tag, self.text)
        return self

    def __exit__(self, *exc):
        self._finish()
        return False

    def line(self) -> str:
        color = use_color(self.stream)
        frames = _FRAMES if symbol("ok", getattr(self.stream, "encoding", None)) == _SYMBOLS["ok"][0] else _FRAMES_ASCII
        tail = "  " + seconds(self.elapsed())
        spin = paint(frames[self._frame % len(frames)], 'cyan', color)
        if _in_block(self.stream, self.tag):          # inside a block: the gutter instead of the tag column
            room = max(10, shutil.get_terminal_size((80, 24)).columns - 1 - 7 - len(tail))
            text = self.short if len(self.short) <= room else self.short[:room - 1] + "\u2026"
            return f" {paint(chr(0x2502), 'dim', color)}  {spin}  {paint_numbers(emphasize(text, color), color)}{paint(tail, 'dim', color)}"
        room = max(10, shutil.get_terminal_size((80, 24)).columns - 1 - (5 + TAG_WIDTH) - len(tail))
        text = self.short if len(self.short) <= room else self.short[:room - 1] + "\u2026"
        return (f" {spin}  {paint(f'{self.tag:<{TAG_WIDTH}}', 'dim', color)} "
                f"{emphasize(text, color)}{paint(tail, 'dim', color)}")

    def draw(self) -> None:
        enc = getattr(self.stream, "encoding", None)
        self.stream.write("\r\x1b[2K" + printable(self.line(), enc))
        self.stream.flush()
        self._drawn = True

    def wipe(self) -> None:
        if self._drawn:
            self.stream.write("\r\x1b[2K")
            self.stream.flush()
            self._drawn = False

    def _spin(self) -> None:
        while not self._stop.wait(self._interval):
            with _screen:
                if _live is self:
                    self._frame += 1
                    self.draw()

    def _finish(self) -> None:
        global _live
        if self._closed:
            return
        self._closed = True
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
        with _screen:
            self.wipe()
            if _live is self:
                _live = None

    def done(self, msg: str) -> None:
        took = self.elapsed()
        self._finish()
        book.ok(self.tag, f"{msg}  ({seconds(took)})")


def working(tag: str, text: str, **kw) -> Working:
    return Working(tag, text, **kw)


# ---- one block for the whole of `extension innovate-items spells`: what changed, the build, the gate, the ids ----
_block = None                      # the Block that is open (at most one); the lines of the `design` tag go inside it


def _in_block(stream, tag: str) -> bool:
    return _block is not None and tag == EXT_TAG and _block.stream is stream


_PROBLEM = re.compile(r"^((?:\x1b\[[0-9;]*m)?\s*)(\$\.[^\s:]+(?:\[[^\]]*\][^\s:]*)?): (.*)$", re.DOTALL)


def _problem_line(msg: str, color: bool, resume: str) -> str:
    """A problem of the design (`$.innovate_items...customs.basic: unknown field`): the place in cyan, the reason after it."""
    m = _PROBLEM.match(msg) if color else None
    return msg if not m else f"{m.group(1)}{paint(m.group(2), 'cyan', True)}{resume}: {m.group(3)}"


class Block:
    """

         \u256d\u2500 design
         \u2502  \u00b7  building because the design changed (1 field)
         \u2502     \u2514\u2500 customs.basic.SpEffect.1642100.effectEndurance  20 -> 30
         \u2502  \u2713  reverse_cursed_technique built, gate passed (26 blocks re-encoded)  (5.8 s)
         \u2570\u2500 regulation.bin  C:\\...\\regulation.bin

    Every line of the `design` tag between `with Block(...)` and its end goes inside it (see pretty_sink); `rows` and `note` write lines
    of their own. `active=False` (`-v`, where the console shows the log itself) makes it do nothing at all."""

    def __init__(self, title: str, *, stream=None, active: bool = True, clock=time.monotonic):
        self.title, self.stream, self.active, self._clock = title, stream or sys.stderr, active, clock
        self.t0, self.closed = 0.0, False

    def _bar(self, color: bool) -> str:
        return paint(chr(0x2502), "dim", color)

    def __enter__(self):
        global _block
        self.t0 = self._clock()
        if not self.active or _block is not None:
            self.active = False
            return self
        color = use_color(self.stream)
        _emit(f" {paint(chr(0x256d) + chr(0x2500), 'dim', color)} {paint(self.title, 'bold', color)}", self.stream)
        _block = self
        return self

    def __exit__(self, exc_type, exc, tb):
        if not self.closed:
            self.close("stopped" if exc_type is not None else "", "error" if exc_type is not None else "ok")
        return False

    def close(self, text: str = "", kind: str = "ok") -> None:
        """The last line: a result, and how long the block took."""
        global _block
        if self.closed:
            return
        self.closed = True
        if not self.active:
            return
        if _block is self:
            _block = None
        color = use_color(self.stream)
        took = paint(f"  ({seconds(self._clock() - self.t0)})", "dim", color)
        sym = paint(symbol(kind, getattr(self.stream, "encoding", None)), kind, color) + "  " if text else ""
        _emit(f" {paint(chr(0x2570) + chr(0x2500), 'dim', color)} {sym}{paint_numbers(emphasize(text, color), color)}{took}", self.stream)

    def note(self, text: str, kind: str = "info") -> None:
        """A line in the block that is not an event (it is not in the log file): the same look as an event."""
        if not self.active:
            return
        color = use_color(self.stream)
        sym = paint(symbol(kind, getattr(self.stream, "encoding", None)), kind, color)
        _emit(f" {self._bar(color)}  {sym}  {paint_numbers(highlight_spells(text, color, EXT_TAG), color)}", self.stream)

    def rows(self, rows: list[tuple[str, str]], indent: int = 5) -> None:
        """`key  value` rows under the line before them (values may hold colour codes already; ids and addresses get theirs here)."""
        if not self.active or not rows:
            return
        color = use_color(self.stream)
        key = max(len(k) for k, _ in rows)
        for k, v in rows:
            _emit(f" {self._bar(color)}{' ' * (indent - 1)}{paint(k.ljust(key), 'dim', color)}  {paint_numbers(v, color)}", self.stream)


def block(title: str, *, verbose: bool = False, stream=None) -> Block:
    """The block of a command; with `verbose` it is not drawn (the console shows the log itself)."""
    return Block(title, stream=stream, active=not verbose)


def card(title: str, rows: list[tuple[str, str]], stream=None) -> None:
    """A small block for one thing the command made (a spell), on the console only:

         \u256d reverse_cursed_technique
         \u2502 name   Reverse Cursed Technique
         \u2570"""
    stream = stream or sys.stderr
    color = use_color(stream)
    key = max((len(k) for k, _ in rows), default=0)
    _emit(f" {paint(chr(0x256d), 'dim', color)} {paint(title, 'spell', color)}", stream)
    for k, v in rows:
        _emit(f" {paint(chr(0x2502), 'dim', color)} {paint(k.ljust(key), 'dim', color)}  {v}", stream)
    _emit(f" {paint(chr(0x2570), 'dim', color)}", stream)


# ---- what the other processes of a `run` did (read back from the log file) ----
_LOG_LINE = re.compile(r"^\d\d-\d\d (\d\d):(\d\d):(\d\d)\.\d{3} +\d+ ([VDIWE]) (\S+) *: (.*)$")
CHILD_TAGS = ("write", "scripts")
CHILD_DONE = "it lasts until the game closes"     # the end of the line a `write` step ends with when it has done its work


def child_line(line: str, stream=None, show_time: bool = True) -> None:
    """A line another process of this `run` (the text and the flame step) wrote to the log file, shown in the concise layout. Only its
    information, warnings and errors; a line that ends the step's work gets the check mark."""
    m = _LOG_LINE.match(line)
    if not m or m.group(4) in "VD" or m.group(5) not in CHILD_TAGS:
        return
    h, mi, s, level, tag, msg = m.groups()
    when = datetime.now().replace(hour=int(h), minute=int(mi), second=int(s), microsecond=0)
    ok = level == "I" and (CHILD_DONE in msg or (tag == "scripts" and ": live (every " in msg))     # a script that started
    pretty_sink(show_time=show_time, stream=stream)(Event(when, 0, level, tag, msg, ok))


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
        tag = paint(f"{e.tag:<{TAG_WIDTH}}", "dim", color)
        resume = f"\x1b[{_COLORS[kind]}m" if kind in ("warn", "error") else ""
        msg = (paint(emphasize(e.msg, color, resume, ticks=False), kind, color) if resume
               else emphasize(highlight_spells(e.msg, color, e.tag), color))
        msg = paint_numbers(msg, color, resume)
        if _in_block(out, e.tag):                      # a line of the block of `extension innovate-items spells`
            msg = _problem_line(msg, color, resume)
            _emit(f" {paint(chr(0x2502), 'dim', color)}  {sym}  {msg}", out, resume)
            return
        _emit(f" {stamp}{sym}  {tag} {msg}", out, resume)
    return sink


_CLI_LINE = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d{3} +\d+ D client *: (?:run: )?)(?!(?:exit -?\d+|version \S+|clickable paths .*)$)(.+)$")


def _dim_line(line: str, color: bool) -> str:
    """A debug line of the log in dim; the command that started a process (`D client : run: eldendisk.exe run -v`) in cyan.
    Only the console gets the colour: the file keeps the plain line."""
    m = _CLI_LINE.match(line) if color else None
    if m:
        return paint(m.group(1), "dim", color) + paint(m.group(2), "cyan", color)
    return paint(emphasize(line, color, "\x1b[2m", ticks=False), "dim", color)


def _line(line: str, kind: str | None, color: bool, level: str) -> tuple[str, str]:
    """(the log line painted for its level, the colour code to resume after a path's file name)."""
    if level == "D":
        return _dim_line(line, color), "\x1b[2m"
    if kind:
        code = f"\x1b[{_COLORS[kind]}m"
        return paint(emphasize(line, color, code, ticks=False), kind, color), code
    return emphasize(line, color), ""


_EXT_LINE = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d{3} +\d+ [VDIWE] %s *: )(.*)$" % EXT_TAG)


def raw_sink(stream=None) -> Callable[[Event], None]:
    """`-v`: the log itself, live."""
    def sink(e: Event) -> None:
        out = stream or sys.stderr
        color = use_color(out)
        kind = {"E": "error", "W": "warn", "V": "dim", "D": "dim"}.get(e.level)
        back = {"E": "\x1b[31m", "W": "\x1b[33m", "V": "\x1b[2m", "D": "\x1b[2m"}.get(e.level, "")
        msg = paint_numbers(e.msg, color, back)
        line = format_line(e._replace(msg=highlight_spells(msg, color, e.tag)) if kind is None else e._replace(msg=msg))
        text, resume = _line(line, kind, color, e.level)
        _emit(text, out, resume)
    return sink


def raw_line(line: str, stream=None) -> None:
    """A log line written by another command, shown as it is in the file (coloured by its level letter)."""
    out = stream or sys.stderr
    got = parse_line(line)
    kind = {"E": "error", "W": "warn", "V": "dim", "D": "dim"}.get(got[1]) if got else None
    color = use_color(out)
    m = _LOG_LINE.match(line) if got else None
    if m:                          # the message after "tag   : " gets the colours of ids and addresses; the prefix (time, pid, tag) is not touched
        back = {"E": "\x1b[31m", "W": "\x1b[33m", "V": "\x1b[2m", "D": "\x1b[2m"}.get(got[1], "")
        msg = paint_numbers(m.group(6), color, back)
        if kind is None and m.group(5) == EXT_TAG:
            msg = highlight_spells(msg, color, EXT_TAG)
        line = line[:len(line) - len(m.group(6))] + msg
    text, resume = _line(line, kind, color, got[1] if got else "I")
    _emit(text, out, resume)


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

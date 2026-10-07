"""One log for the whole tool, in the style of Android's logcat.

    10-07 23:41:02.123  4242 I host   : game running, pid 8812

Every event of every command goes to a file next to the vault (`<vault>/eldendisk.log`, rotated) at all levels, and to
the console through a sink the command chooses (the concise layout of `ui`, or with `-v` these very lines).
Logging must never break the tool: a failing sink is dropped silently.
"""
from __future__ import annotations

import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, NamedTuple

LEVELS = "VDIWE"            # verbose, debug, info, warning, error (logcat letters)
LOG_NAME = "eldendisk.log"
MAX_BYTES = 2 * 1024 * 1024
KEEP_FILES = 3              # eldendisk.log, .1, .2


class Event(NamedTuple):
    when: datetime
    pid: int
    level: str              # one of LEVELS
    tag: str
    msg: str
    ok: bool = False        # an info event that reports something done (shown as a check mark)


def format_line(e: Event) -> str:
    """The logcat line (file and `-v`)."""
    return f"{e.when:%m-%d %H:%M:%S}.{e.when.microsecond // 1000:03d} {e.pid:>5} {e.level} {e.tag:<6}: {e.msg}"


class _FileSink:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._size = self.path.stat().st_size if self.path.exists() else 0
        self._fh = open(self.path, "a", encoding="utf-8", buffering=1)

    def write(self, line: str) -> None:
        data = line + "\n"
        if self._size + len(data) > MAX_BYTES:
            self._rotate()
        self._fh.write(data)
        self._fh.flush()
        self._size += len(data.encode("utf-8"))

    def _rotate(self) -> None:
        """Move the log aside. Several commands append to this file at once (one per terminal), and Windows will not
        rename a file another process holds open: then the file simply keeps growing."""
        self._fh.close()
        try:
            for i in range(KEEP_FILES - 1, 0, -1):
                src = self.path if i == 1 else self.path.with_name(f"{self.path.name}.{i - 1}")
                dst = self.path.with_name(f"{self.path.name}.{i}")
                if src.exists():
                    os.replace(src, dst)
        except OSError:
            pass
        self._fh = open(self.path, "a", encoding="utf-8", buffering=1)
        self._size = self.path.stat().st_size if self.path.exists() else 0

    def close(self) -> None:
        try:
            self._fh.close()
        except OSError:
            pass


class Logbook:
    def __init__(self):
        self._lock = threading.RLock()
        self._file: _FileSink | None = None
        self._console: Callable[[Event], None] | None = None
        self.pid = os.getpid()
        self.path: Path | None = None

    def configure(self, *, file: Path | None = None, console: Callable[[Event], None] | None = None) -> None:
        with self._lock:
            self.close()
            self._console = console
            if file is not None:
                try:
                    self._file, self.path = _FileSink(Path(file)), Path(file)
                except OSError:
                    self._file, self.path = None, None   # no log file is better than no tool

    def close(self) -> None:
        with self._lock:
            if self._file is not None:
                self._file.close()
            self._file, self.path = None, None

    def emit(self, level: str, tag: str, msg: str, *, ok: bool = False) -> None:
        if level not in LEVELS:
            level = "I"
        with self._lock:
            for line in str(msg).splitlines() or [""]:
                event = Event(datetime.now().astimezone(), self.pid, level, tag, line, ok)
                if self._file is not None:
                    try:
                        self._file.write(format_line(event))
                    except (OSError, ValueError):
                        self._file = None
                if self._console is not None:
                    try:
                        self._console(event)
                    except Exception:
                        self._console = None

    def locked(self, fn: Callable, *args) -> None:
        """Run `fn` while no event is being written, so console lines from two threads never interleave."""
        with self._lock:
            fn(*args)

    def v(self, tag, msg): self.emit("V", tag, msg)
    def d(self, tag, msg): self.emit("D", tag, msg)
    def i(self, tag, msg): self.emit("I", tag, msg)
    def ok(self, tag, msg): self.emit("I", tag, msg, ok=True)
    def w(self, tag, msg): self.emit("W", tag, msg)
    def e(self, tag, msg): self.emit("E", tag, msg)


book = Logbook()

_LINE = re.compile(r"^\d\d-\d\d \d\d:\d\d:\d\d\.\d{3} +(\d+) ([VDIWE]) ")


def parse_line(line: str) -> tuple[int, str] | None:
    """(pid, level) of a log line as `format_line` writes it, None for anything else."""
    m = _LINE.match(line)
    return (int(m.group(1)), m.group(2)) if m else None


class Tail:
    """Shows what other commands append to the log file while this one runs (`run -v`): every terminal's lines,
    in the file's own format. Starts at the end of the file; lines of this process (`own_pid`) are not repeated."""

    def __init__(self, path: Path, show: Callable[[str], None], own_pid: int, poll: float = 0.2):
        self.path, self.show, self.own_pid, self.poll = Path(path), show, own_pid, poll
        self._offset = 0
        self._ident = None
        self._partial = b""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        try:
            st = self.path.stat()
            self._offset, self._ident = st.st_size, (st.st_dev, st.st_ino)
        except OSError:
            self._offset = 0
        self._thread = threading.Thread(target=self._run, name="log-tail", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self.poll_once()   # whatever arrived since the last look

    def _run(self) -> None:
        while not self._stop.wait(self.poll):
            self.poll_once()

    def poll_once(self) -> None:
        try:
            st = self.path.stat()
            size, ident = st.st_size, (st.st_dev, st.st_ino)
            if size < self._offset or (self._ident is not None and ident != self._ident):
                self._offset, self._partial = 0, b""   # rotated (a new file) or emptied: start over
            self._ident = ident
            if size == self._offset:
                return
            with open(self.path, "rb") as fh:
                fh.seek(self._offset)
                data = self._partial + fh.read(size - self._offset)
            self._offset = size
        except OSError:
            return
        *whole, self._partial = data.split(b"\n")   # a line that is still being written waits for its newline
        for raw in whole:
            line = raw.decode("utf-8", errors="replace").rstrip("\r")
            got = parse_line(line)
            if got and got[0] != self.own_pid:
                try:
                    self.show(line)
                except Exception:
                    return

"""The host of the external scripts (1.7.2): finds the scripts, runs each in a thread of its own, keeps their pace, watches them, ends them.

One process (`eldendisk extension external-scripts --run`, which `run` starts) holds every script. A Python thread cannot be killed, so
the process is what ends for sure: when the game closes the host asks every script to stop, waits a moment for each, and returns
(the threads are daemons). Nothing a script does can keep the vault from putting the save back: `run` does that, not this process.

The life of a script:

    loaded -> setup -> live -> stopped | dead          (off: `enabled = False`;  failed: the file could not be loaded)

  * setup() once, then loop() every `every` seconds (from the start of one call to the start of the next; a call that takes longer is
    followed by the next one at once, and the log says once that the script is slower than its pace);
  * reading in `character` while no character is in the world (the title screen, a loading screen) skips that call: the script
    waits, it is not an error;
  * tools.dead() ends the script ("stopped"); any exception ends it ("dead", the traceback in the log);
  * a loop() that does not return for STUCK seconds is reported once as stuck (it keeps its thread: it cannot be taken away);
  * teardown() always.

The status of every script is kept in `<extension dir>/external-scripts.status.json` for `extension external-scripts --list`."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from . import edstdlib as ed

TAG = "scripts"
MIN_EVERY = 0.05          # the fastest pace a script may ask for (seconds)
STUCK = 10.0              # seconds a loop() may run before it is reported as stuck
JOIN = 3.0                # seconds the host waits for each script to end when it stops them
WATCH = 0.5               # seconds between two looks of the supervisor
STATUS_FILE = "external-scripts.status.json"
_clock = time.monotonic


class _Say:
    """The host's lines. Like the other engines it does not know the console or the log file: the command gives it a function
    (`set_log(fn)`, fn(level, message) with level I / OK / W / E / D); without one the lines go nowhere."""
    fn = staticmethod(lambda level, msg: None)

    def i(self, _tag, msg): self.fn("I", msg)
    def ok(self, _tag, msg): self.fn("OK", msg)
    def w(self, _tag, msg): self.fn("W", msg)
    def e(self, _tag, msg): self.fn("E", msg)
    def d(self, _tag, msg): self.fn("D", msg)


book = _Say()


def set_log(fn) -> None:
    """Where the host's lines go: fn(level, message)."""
    _Say.fn = staticmethod(fn)


def install() -> None:
    """Make `import edstdlib` work for the scripts (the package does it when imported; this says so)."""
    sys.modules.setdefault("edstdlib", ed)


# ---------------------------------------------------------------------------------------------------------------------------- loading
@dataclass
class Found:
    """What one file gave: its scripts, or why it could not be loaded."""
    path: Path
    scripts: list = field(default_factory=list)
    error: str | None = None


def script_files(folder: Path) -> list[Path]:
    """The scripts of `folder`: every `*.py` in it (not in subfolders), by name; a name that starts with `_` is a helper, not a script."""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.glob("*.py") if p.is_file() and not p.name.startswith("_"))


def load_file(path: Path) -> Found:
    """Import one script file and make one object of every Interface class defined in it."""
    install()
    name = f"edscript_{path.stem}"
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    except BaseException as exc:          # a broken file (SyntaxError, an import, SystemExit) never stops the host
        sys.modules.pop(name, None)
        return Found(path, error=_short(exc))
    found = Found(path)
    for obj in vars(module).values():
        if isinstance(obj, type) and issubclass(obj, ed.Interface) and obj is not ed.Interface and obj.__module__ == name:
            if obj.loop is ed.Interface.loop:
                found.error = f"{obj.__name__} has no loop()"
                continue
            try:
                found.scripts.append(obj())
            except BaseException as exc:
                found.error = f"{obj.__name__}(): {_short(exc)}"
    if not found.scripts and found.error is None:
        found.error = "no Interface class in it (class MyScript(Interface): ... def loop(self): ...)"
    return found


def _short(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__


# ---------------------------------------------------------------------------------------------------------------------------- one script
class Runner:
    """One script and its thread."""

    def __init__(self, script: ed.Interface, path: Path | None = None):
        self.script, self.path = script, path
        self.name = script.name
        self.every = max(MIN_EVERY, float(getattr(script, "every", 1.0) or 1.0))
        self.state = "loaded"
        self.error: str | None = None
        self.loops = 0
        self.skipped = 0              # calls of loop() skipped because no character was in the world
        self.in_loop_since: float | None = None
        self.stuck = False
        self._slow_said = False
        self._waiting = False
        self.thread = threading.Thread(target=self._run, name=f"script:{self.name}", daemon=True)
        self.on_change = lambda r: None

    # the thread
    def _run(self) -> None:
        s = self.script
        ed._set_current(s)
        try:
            self._set("setup")
            s.setup()
            self._set("live")
            book.ok(TAG, f"{self.name}: live (every {self.every:g} s)")
            while not s.stopping:
                t = _clock()
                self.in_loop_since = t
                try:
                    s.loop()
                    if self._waiting:
                        self._waiting = False
                        book.i(TAG, f"{self.name}: a character is in the world again")
                except ed._NotInWorld:
                    self.skipped += 1
                    if not self._waiting:
                        self._waiting = True
                        book.i(TAG, f"{self.name}: waiting, no character in the world")
                finally:
                    self.in_loop_since = None
                self.loops += 1
                took = _clock() - t
                if took > self.every and not self._slow_said:
                    self._slow_said = True
                    book.w(TAG, f"{self.name}: loop() took {took:.2f} s, longer than its pace of {self.every:g} s")
                s.wait(self.every - took)
            self._end("stopped")
        except ed._Dead:
            self._end("stopped", "tools.dead()")
        except BaseException as exc:          # SystemExit / KeyboardInterrupt from a script end the script, not the host
            self.error = _short(exc)
            book.e(TAG, f"{self.name}: dead: {self.error}")
            for line in traceback.format_exc().rstrip().splitlines():
                book.d(TAG, f"{self.name}:   {line}")
            self._end("dead")
        finally:
            ed._set_current(None)

    def _end(self, state: str, why: str | None = None) -> None:
        s = self.script
        try:
            s.teardown()
        except BaseException as exc:
            book.e(TAG, f"{self.name}: teardown(): {_short(exc)}")
            if state != "dead":
                self.error = f"teardown(): {_short(exc)}"
        if state == "stopped":
            book.i(TAG, f"{self.name}: stopped" + (f" ({why})" if why else "") + f" after {self.loops} loop(s)")
        self._set(state)

    def _set(self, state: str) -> None:
        self.state = state
        self.on_change(self)

    # the supervisor's side
    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.script.stop()

    def view(self) -> dict:
        out = {"name": self.name, "file": self.path.name if self.path else None, "state": "stuck" if self.stuck and self.state == "live"
               else self.state, "every": self.every, "loops": self.loops}
        if self.error:
            out["error"] = self.error
        return out


# ---------------------------------------------------------------------------------------------------------------------------- all of them
class Supervisor:
    """Starts every script, watches them, ends them. `alive()`: is the game still running (the backend's)."""

    def __init__(self, found: list[Found], alive, status_path: Path | None = None):
        self.found, self.alive, self.status_path = found, alive, status_path
        self.runners: list[Runner] = []
        self.off: list[dict] = []
        self._lock = threading.Lock()
        self._stopping = threading.Event()
        names = set()
        for f in found:
            if f.error and not f.scripts:
                self.off.append({"name": f.path.stem, "file": f.path.name, "state": "failed", "error": f.error})
                book.e(TAG, f"{f.path.name}: not loaded: {f.error}")
                continue
            if f.error:
                book.e(TAG, f"{f.path.name}: {f.error}")
            for s in f.scripts:
                if not getattr(s, "enabled", True):
                    self.off.append({"name": s.name, "file": f.path.name, "state": "off"})
                    continue
                if s.name in names:              # two scripts of the same name: the second gets the file's name too
                    s.name = f"{s.name}@{f.path.stem}"
                names.add(s.name)
                r = Runner(s, f.path)
                r.on_change = lambda _r: self.save_status()
                self.runners.append(r)

    def start(self) -> None:
        book.i(TAG, f"{len(self.runners)} script(s): " + (", ".join(r.name for r in self.runners) or "none")
               + (f"; not running: {', '.join(o['name'] + ' (' + o['state'] + ')' for o in self.off)}" if self.off else ""))
        for r in self.runners:
            r.start()
        self.save_status()

    def watch(self, until=None) -> None:
        """Look after the scripts until the game closes, every script has ended, or `until()` says so."""
        while not self._stopping.is_set():
            if not self.alive():
                book.i(TAG, "the game closed: stopping every script")
                break
            if until is not None and until():
                break
            now = _clock()
            for r in self.runners:
                since = r.in_loop_since
                if since is not None and now - since > STUCK and not r.stuck:
                    r.stuck = True
                    book.w(TAG, f"{r.name}: loop() has not returned for {now - since:.0f} s (stuck); it cannot be taken away, the other "
                                "scripts go on")
                    self.save_status()
                elif since is None and r.stuck:
                    r.stuck = False
            if self.runners and all(not r.thread.is_alive() for r in self.runners):
                book.i(TAG, "every script has ended")
                break
            self._stopping.wait(WATCH)
        self.stop()

    def stop(self) -> None:
        self._stopping.set()
        for r in self.runners:
            r.stop()
        for r in self.runners:
            r.thread.join(JOIN)
            if r.thread.is_alive():
                book.w(TAG, f"{r.name}: did not end within {JOIN:g} s (left behind; the process ends anyway)")
        self.save_status()

    def save_status(self) -> None:
        if self.status_path is None:
            return
        with self._lock:
            doc = {"kind": "external-scripts status", "pid": os.getpid(), "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "scripts": [r.view() for r in self.runners] + self.off}
            try:
                self.status_path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.status_path.with_suffix(".tmp")
                tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
                os.replace(tmp, self.status_path)
            except OSError as exc:
                book.d(TAG, f"could not write {self.status_path.name}: {exc}")


def read_status(path: Path) -> dict | None:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) and isinstance(doc.get("scripts"), list) else None
    except (OSError, ValueError):
        return None

"""The host of the scripts (1.7.2; 1.8.0 part 2): finds the scripts, runs each in a thread of its own, keeps their pace, watches them,
ends them.

One process (`eldendisk scripts start`, which `run` starts too) holds every script of the session. A Python thread cannot be killed, so
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

The status of the host and of every script is kept in `<vault>\\creative\\scripts.status.json` (`scripts`, `scripts status`, the
document's `creative.scripts`). Another terminal controls the host through small request files in `<vault>\\creative\\scripts.requests\\`
(`scripts start | restart | stop NAME`, `scripts add | remove | change`): the host looks for them once a second, does what each asks and
answers in the status file. No port is opened."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import edstdlib as ed

TAG = "scripts"
MIN_EVERY = 0.05          # the fastest pace a script may ask for (seconds)
STUCK = 10.0              # seconds a loop() may run before it is reported as stuck
JOIN = 3.0                # seconds the host waits for each script to end when it stops them
WATCH = 0.5               # seconds between two looks of the supervisor
STATUS_FILE = "scripts.status.json"           # 1.8.0 (external-scripts.status.json before)
REQUESTS_DIR = "scripts.requests"            # one file per request from another terminal
POLL_REQUESTS = 1.0       # seconds between two looks for requests
REPLIES_KEPT = 20         # the answers to the last requests, in the status file
SAVE_TRIES = 5            # tries to replace the status file while a reader holds it
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
    """What one file gave: its scripts, or why it could not be loaded. `added`: a file of `scripts.added` in creative.json (not one of
    the defaults the exe carries)."""
    path: Path
    scripts: list = field(default_factory=list)
    error: str | None = None
    added: bool = False


def script_files(folder: Path) -> list[Path]:
    """The scripts of `folder`: every `*.py` in it (not in subfolders), by name; a name that starts with `_` is a helper, not a script."""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.glob("*.py") if p.is_file() and not p.name.startswith("_"))


def load_file(path: Path, added: bool = False) -> Found:
    """Import one script file and make one object of every Interface class defined in it."""
    install()
    path = Path(path)
    name = f"edscript_{path.stem}"
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    except BaseException as exc:          # a broken file (SyntaxError, an import, SystemExit) never stops the host
        sys.modules.pop(name, None)
        return Found(path, error=_short(exc), added=added)
    found = Found(path, added=added)
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
    """One script and its thread. `sid`: its number in the host (the `ID` of `NAME:ID:PROCESS_ID`)."""

    def __init__(self, script: ed.Interface, path: Path | None = None, sid: int = 0, added: bool = False):
        self.script, self.path, self.sid, self.added = script, path, sid, added
        self.name = script.name
        self.every = max(MIN_EVERY, float(getattr(script, "every", 1.0) or 1.0))
        self.state = "loaded"
        self.error: str | None = None
        self.loops = 0
        self.skipped = 0              # calls of loop() skipped because no character was in the world
        self.in_loop_since: float | None = None
        self.stuck = False
        self.slow = False             # a loop() longer than its pace was seen
        self.started: str | None = None
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
                        self.on_change(self)
                except ed._NotInWorld:
                    self.skipped += 1
                    if not self._waiting:
                        self._waiting = True
                        book.i(TAG, f"{self.name}: waiting, no character in the world")
                        self.on_change(self)
                finally:
                    self.in_loop_since = None
                self.loops += 1
                took = _clock() - t
                if took > self.every and not self.slow:
                    self.slow = True
                    book.d(TAG, f"{self.name}: loop() took {took:.2f} s, longer than its pace of {self.every:g} s")
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
        self.started = time.strftime("%Y-%m-%d %H:%M:%S")
        self.thread.start()

    def stop(self) -> None:
        self.script.stop()

    @property
    def running(self) -> bool:
        return self.thread.is_alive()

    def view(self) -> dict:
        state = self.state
        if state == "live" and self.stuck:
            state = "stuck"
        elif state == "live" and self._waiting:
            state = "waiting"
        return {"name": self.name, "id": self.sid, "file": self.path.name if self.path else None,
                "path": str(self.path) if self.path else None, "added": self.added, "state": state, "every": self.every,
                "loops": self.loops, "slow": self.slow, "started": self.started, "last_error": self.error}


@dataclass
class Off:
    """A script that does not run: `failed` (its file could not be loaded) or `off` (`enabled = False`)."""
    name: str
    path: Path
    state: str
    sid: int = 0
    added: bool = False
    error: str | None = None
    every: float | None = None

    running = False

    def view(self) -> dict:
        return {"name": self.name, "id": self.sid, "file": self.path.name, "path": str(self.path), "added": self.added,
                "state": self.state, "every": self.every, "loops": 0, "slow": False, "started": None, "last_error": self.error}


# ---------------------------------------------------------------------------------------------------------------------------- addressing
def parse_target(text: str) -> tuple[str | None, int | None, int | None]:
    """`NAME[:ID[:PROCESS_ID]]` -> (name, id, process id); `*` / `all` / "" -> (None, None, None): every script. ValueError otherwise."""
    t = (text or "").strip()
    if t in ("", "*", "all"):
        return None, None, None
    name, *rest = t.split(":")
    if len(rest) > 2 or not name.strip():
        raise ValueError(f"{text!r}: a script is NAME, NAME:ID or NAME:ID:PROCESS_ID")
    try:
        nums = [int(x) for x in rest]
    except ValueError:
        raise ValueError(f"{text!r}: ID and PROCESS_ID are numbers (NAME:ID:PROCESS_ID)") from None
    return name.strip(), (nums[0] if nums else None), (nums[1] if len(nums) > 1 else None)


def match(entries: list, text: str, pid: int | None = None) -> list:
    """The entries (Runner / Off, or the status views as dicts) `text` names. A name is the script's name in any letter case, or its
    file's name (without .py). ValueError when it names none."""
    name, sid, want_pid = parse_target(text)
    if want_pid is not None and pid is not None and want_pid != pid:
        raise ValueError(f"{text!r}: the scripts' host is process {pid}, not {want_pid}")
    if name is None:
        return list(entries)

    def get(e, k):
        return e.get(k) if isinstance(e, dict) else getattr(e, k, None)

    def stem(e):
        p = get(e, "path")
        return Path(p).stem.lower() if p else ""

    key = name.lower()
    hits = [e for e in entries if str(get(e, "name")).lower() == key] or [e for e in entries if stem(e) == key]
    if sid is not None:
        hits = [e for e in hits if (get(e, "sid") if not isinstance(e, dict) else e.get("id")) == sid]
    if not hits:
        known = ", ".join(f"{get(e, 'name')}:{get(e, 'sid') if not isinstance(e, dict) else e.get('id')}" for e in entries) or "none"
        raise ValueError(f"no script {text!r} (the scripts: {known})")
    return hits


# ---------------------------------------------------------------------------------------------------------------------------- requests
def send_request(folder: Path, action: str, target: str = "*", path: str | None = None) -> str:
    """Leave a request for the host in `folder` (the creative folder): {"id", "action", "target", "path"}. -> its id; the answer is in
    the status file's `replies` once the host has read it (within POLL_REQUESTS seconds)."""
    rid = uuid.uuid4().hex
    d = Path(folder) / REQUESTS_DIR
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f"{rid}.tmp"
    tmp.write_text(json.dumps({"id": rid, "action": action, "target": target, "path": path}), encoding="utf-8")
    os.replace(tmp, d / f"{rid}.json")
    return rid


def take_requests(folder: Path) -> list[dict]:
    """Every request waiting in `folder`, oldest first; each file is removed once read."""
    d = Path(folder) / REQUESTS_DIR
    if not d.is_dir():
        return []
    out = []
    files = []
    for f in d.glob("*.json"):
        try:
            files.append((f.stat().st_mtime, f))
        except OSError:
            pass
    for _t, f in sorted(files):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            doc = None
        try:
            f.unlink()
        except OSError:
            pass
        if isinstance(doc, dict) and doc.get("id") and doc.get("action"):
            out.append(doc)
    return out


# ---------------------------------------------------------------------------------------------------------------------------- all of them
class Supervisor:
    """Starts the scripts, watches them, does what the requests ask, ends them. `alive()`: is the game still running (the backend's).
    `only`: the targets to start at first (None: every script). `control`: the creative folder whose requests the host answers (None:
    no control, and the host ends once every script has ended)."""

    def __init__(self, found: list[Found], alive, status_path: Path | None = None, only: list[str] | None = None,
                 control: Path | None = None):
        self.alive, self.status_path, self.only, self.control = alive, status_path, only, control
        self.entries: list = []
        self.replies: list[dict] = []
        self.started = time.strftime("%Y-%m-%d %H:%M:%S")
        self.state = "running"
        self._next = 1
        self._unsaved = False
        self._lock = threading.Lock()
        self._stopping = threading.Event()
        for f in found:
            self._take(f)

    # what the host holds
    @property
    def runners(self) -> list[Runner]:
        return [e for e in self.entries if isinstance(e, Runner)]

    @property
    def off(self) -> list[dict]:
        return [e.view() for e in self.entries if isinstance(e, Off)]

    def _sid(self) -> int:
        n, self._next = self._next, self._next + 1
        return n

    def _take(self, f: Found, sids: dict | None = None) -> list:
        """The scripts of one loaded file as entries (their ids kept from `sids`, name -> id, when the file is loaded again)."""
        sids = sids or {}
        if f.error and not f.scripts:
            book.e(TAG, f"{f.path.name}: not loaded: {f.error}")
            e = Off(f.path.stem, f.path, "failed", sids.get(f.path.stem) or self._sid(), f.added, f.error)
            self.entries.append(e)
            return [e]
        if f.error:
            book.e(TAG, f"{f.path.name}: {f.error}")
        new = []
        names = {e.name for e in self.entries}
        for s in f.scripts:
            if s.name in names and s.name not in sids:       # two scripts of the same name: the second gets the file's name too
                s.name = f"{s.name}@{f.path.stem}"
            names.add(s.name)
            sid = sids.get(s.name) or self._sid()
            if not getattr(s, "enabled", True):
                e = Off(s.name, f.path, "off", sid, f.added, None, max(MIN_EVERY, float(getattr(s, "every", 1.0) or 1.0)))
            else:
                e = Runner(s, f.path, sid, f.added)
                e.on_change = lambda _r: self.save_status()
            self.entries.append(e)
            new.append(e)
        return new

    # the life of the host
    def _wanted(self, e) -> bool:
        if self.only is None:
            return True
        for t in self.only:
            try:
                if any(x is e for x in match(self.entries, t)):
                    return True
            except ValueError:
                pass
        return False

    def start(self) -> None:
        for t in self.only or []:
            try:
                match(self.entries, t, os.getpid())
            except ValueError as exc:
                book.e(TAG, str(exc))
        go = [r for r in self.runners if self._wanted(r)]
        book.i(TAG, f"{len(go)} script(s): " + (", ".join(f"{r.name}:{r.sid}" for r in go) or "none")
               + (f"; not running: {', '.join(o['name'] + ' (' + o['state'] + ')' for o in self.off)}" if self.off else ""))
        for r in go:
            r.start()
        self.save_status()

    def watch(self, until=None) -> None:
        """Look after the scripts until the game closes, `scripts stop *`, `until()` says so, or (without control) every script has
        ended."""
        next_look = _clock()
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
            if self._unsaved:
                self.save_status()
            if self.control is not None and now >= next_look:
                next_look = now + POLL_REQUESTS
                for req in take_requests(self.control):
                    self.answer(req)
                if self._stopping.is_set():
                    break
            if self.control is None and self.runners and all(not r.running for r in self.runners):
                book.i(TAG, "every script has ended")
                break
            self._stopping.wait(WATCH)
        self.stop()

    def stop(self) -> None:
        self._stopping.set()
        for r in self.runners:
            r.stop()
        for r in self.runners:
            if r.thread.ident is not None:
                r.thread.join(JOIN)
            if r.running:
                book.w(TAG, f"{r.name}: did not end within {JOIN:g} s (left behind; the process ends anyway)")
        self.state = "stopped"
        self.save_status()

    # what another terminal asks
    def answer(self, req: dict) -> dict:
        """Do one request ({"id", "action": start | stop | restart | load | unload, "target", "path"}) and keep the answer."""
        action, target = str(req.get("action")), str(req.get("target") or "*")
        lines, ok = [], True
        try:
            if action == "load":
                lines = self._load(Path(str(req.get("path"))))
            elif action == "unload":
                lines = self._unload(Path(str(req.get("path"))))
            elif action in ("start", "stop", "restart"):
                hits = match(self.entries, target, os.getpid())
                if action == "stop" and parse_target(target)[0] is None:
                    lines = [f"every script asked to stop; the host (process {os.getpid()}) ends"]
                    self._stopping.set()
                else:
                    for e in hits:
                        lines.append(getattr(self, "_" + action)(e))
            else:
                raise ValueError(f"unknown request {action!r}")
        except ValueError as exc:
            ok, lines = False, [str(exc)]
        for line in lines:
            (book.i if ok else book.e)(TAG, line)
        reply = {"id": req.get("id"), "ok": ok, "lines": lines, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
        self.replies = (self.replies + [reply])[-REPLIES_KEPT:]
        self.save_status()
        return reply

    def _start(self, e) -> str:
        if isinstance(e, Off):
            if e.state == "off":
                return f"{e.name}:{e.sid}: off (enabled = False in {e.path.name})"
            return self._restart(e)
        if e.running:
            return f"{e.name}:{e.sid}: already {e.view()['state']}"
        if e.thread.ident is not None:             # it ran and ended: a new object of the same class (a thread starts once)
            try:
                fresh = Runner(type(e.script)(), e.path, e.sid, e.added)
            except BaseException as exc:
                return f"{e.name}:{e.sid}: cannot be made again: {_short(exc)}"
            fresh.script.name = fresh.name = e.name
            fresh.on_change = lambda _r: self.save_status()
            self.entries[self.entries.index(e)] = fresh
            e = fresh
        e.start()
        return f"{e.name}:{e.sid}: started"

    def _stop(self, e) -> str:
        if not e.running:
            return f"{e.name}:{e.sid}: not running ({e.view()['state']})"
        e.stop()
        e.thread.join(JOIN)
        if e.running:
            return f"{e.name}:{e.sid}: asked to stop; its loop() has not returned (stuck): it ends with the host (`scripts stop *`)"
        return f"{e.name}:{e.sid}: stopped"

    def _restart(self, e) -> str:
        """Stop every script of `e`'s file, load the file again, start what it holds (the ids are kept)."""
        if e.path is None:
            return self._start(e)
        mine = [x for x in self.entries if x.path is not None and _same(x.path, e.path)]
        for x in mine:
            if x.running:
                said = self._stop(x)
                if x.running:
                    return said
        sids = {x.name: x.sid for x in mine}
        sids.setdefault(e.path.stem, e.sid)
        at = self.entries.index(mine[0])
        for x in mine:
            self.entries.remove(x)
        before = len(self.entries)
        new = self._take(load_file(e.path, e.added), sids)
        del self.entries[before:]
        self.entries[at:at] = new
        out = []
        for x in new:
            if isinstance(x, Runner):
                x.start()
                out.append(f"{x.name}:{x.sid}: loaded again and started")
            else:
                out.append(f"{x.name}:{x.sid}: {x.state}" + (f" ({x.error})" if x.error else ""))
        return "; ".join(out)

    def _load(self, path: Path) -> list[str]:
        files = script_files(path) if path.is_dir() else [path]
        out = []
        for p in files:
            if any(x.path is not None and _same(x.path, p) for x in self.entries):
                out.append(f"{p.name}: already in the host")
                continue
            for x in self._take(load_file(p, True)):
                if isinstance(x, Runner):
                    x.start()
                    out.append(f"{x.name}:{x.sid}: added and started")
                else:
                    out.append(f"{x.name}:{x.sid}: {x.state}" + (f" ({x.error})" if x.error else ""))
        return out or [f"{path}: no script in it"]

    def _unload(self, path: Path) -> list[str]:
        mine = [x for x in self.entries if x.path is not None and (_same(x.path, path) or _same(x.path.parent, path))]
        out = []
        for x in mine:
            if x.running:
                out.append(self._stop(x))
            self.entries.remove(x)
            out.append(f"{x.name}:{x.sid}: taken out of the host")
        return out or [f"{path}: not in the host"]

    def save_status(self) -> None:
        if self.status_path is None:
            return
        with self._lock:
            doc = {"kind": "scripts status", "pid": os.getpid(), "state": self.state, "started": self.started,
                   "updated": time.strftime("%Y-%m-%d %H:%M:%S"), "scripts": [e.view() for e in self.entries],
                   "replies": self.replies}
            for attempt in range(SAVE_TRIES):        # a reader holding the file open (`scripts status`) keeps it from being replaced
                try:
                    self.status_path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = self.status_path.with_suffix(".tmp")
                    tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
                    os.replace(tmp, self.status_path)
                    self._unsaved = False
                    return
                except OSError as exc:
                    why = exc
                    time.sleep(0.01 * (attempt + 1))
            self._unsaved = True                      # the supervisor tries again at its next look
            book.d(TAG, f"could not write {self.status_path.name}: {why}")


def host_running(status: dict | None, alive) -> bool:
    """Does the host that wrote `status` still run? `alive(pid)`: is that process alive (game/processes.process_alive)."""
    if not isinstance(status, dict) or status.get("state") == "stopped":
        return False
    try:
        return bool(status.get("pid")) and bool(alive(int(status["pid"])))
    except (TypeError, ValueError):
        return False


def block_of(status: dict | None, running: bool) -> dict | None:
    """The document's `creative.scripts` from the host's status file: {"host": {process_id, state, started, scripts} | None (no host
    runs), "defaults": {NAME: {id, file, state, every, loops, slow, last_error}}, "added": {NAME: ...}}. None without a status file.
    A script of a host that has ended is `stopped` (unless it ended `dead`, `failed` or `off`)."""
    if not isinstance(status, dict):
        return None
    scripts = [s for s in status.get("scripts", []) if isinstance(s, dict)]
    out = {"host": {"process_id": status.get("pid"), "state": "running", "started": status.get("started"),
                    "scripts": len(scripts)} if running else None, "defaults": {}, "added": {}}
    for n, sc in enumerate(scripts, 1):
        state = sc.get("state")
        if not running and state not in ("stopped", "dead", "failed", "off"):
            state = "stopped"
        out["added" if sc.get("added") else "defaults"][sc.get("name") or f"script {n}"] = {
            "id": sc.get("id", n), "file": sc.get("file"), "state": state, "every": sc.get("every"), "loops": sc.get("loops", 0),
            "slow": bool(sc.get("slow")), "last_error": sc.get("last_error", sc.get("error"))}
    return out


def _same(a: Path, b: Path) -> bool:
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return str(a).lower() == str(b).lower()


def read_status(path: Path) -> dict | None:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) and isinstance(doc.get("scripts"), list) else None
    except (OSError, ValueError):
        return None

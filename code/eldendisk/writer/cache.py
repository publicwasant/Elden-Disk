"""Where the steps of a game process found what they changed, so a later write in the SAME game needs no look through its memory
(1.7.2). `memory-cache.json` in the vault folder, tied to the pid and the start time of the game process (like params-snapshot.json):
a new game starts empty, and nothing of it is ever used for another process.

  text  the address of each text table's pointer (the array's slots `innovate-spells apply` switched) and the texts written, by goods id
  fxr   per effect file: the addresses of its copies and the colours they carry now (`main` for the plan's colours, `accent` for the
        accent places; None = the game's own)

Several processes write it in the same game (`innovate-spells apply` and the scripts under `run`):
save() reads the file again and writes only what THIS object changed over it, under a lock file, so one step never wipes what another
found while it was busy (seen 2026-10-13: the text step, started before the colours were painted and done after, saved its old copy over
them, and the scripts could not change a colour).

An address is a hint, never trusted: before anything is written there, the bytes are checked (writer/fxr.repaint,
writer/text.read_table); when the game moved or reloaded something, the step that uses the cache looks again.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

CACHE_NAME = "memory-cache.json"
LOCK_WAIT = 2.0          # seconds a save waits for another process's save
LOCK_STALE = 10.0        # a lock file older than this was left by a process that died


class MemoryCache:
    def __init__(self, path: Path, pid: int, started):
        self.path, self.pid, self.started = Path(path), pid, started
        self.text: dict = {"slots": {}, "rows": {}}
        self.fxr: dict = {}
        self._mine: dict = {"slots": {}, "rows": {}, "fxr": {}}     # what this object changed, written over the file by save()

    def load(self) -> "MemoryCache":
        self.text, self.fxr = self._read()
        return self

    def _read(self) -> tuple[dict, dict]:
        """(text, fxr) of the file when it is of this game process; empty ones otherwise."""
        try:
            doc = json.loads(self.path.read_text(encoding="utf-8"))
            if doc.get("game_pid") == self.pid and doc.get("game_started") == self.started:
                t = doc.get("text", {})
                return {"slots": dict(t.get("slots", {})), "rows": {k: dict(v) for k, v in t.get("rows", {}).items()}}, \
                    dict(doc.get("fxr", {}))
        except (OSError, ValueError, AttributeError):
            pass                      # no file, a broken one, another game process: nothing is known
        return {"slots": {}, "rows": {}}, {}

    # ---- text
    def text_slots(self) -> dict:
        """{table name: the address of its pointer}."""
        return {k: int(v) for k, v in self.text["slots"].items()}

    def set_text(self, slots: dict, rows: dict) -> None:
        """`slots` {table name: pointer address}; `rows` {goods id: {field: text}} (merged over what was written before)."""
        self.text["slots"].update({k: int(v) for k, v in slots.items()})
        self._mine["slots"].update({k: int(v) for k, v in slots.items()})
        for gid, fields in rows.items():
            self.text["rows"].setdefault(str(gid), {}).update(fields)
            self._mine["rows"].setdefault(str(gid), {}).update(fields)

    def texts(self, goods: int) -> dict:
        return dict(self.text["rows"].get(str(goods), {}))

    # ---- effect files
    def effect(self, eid: str) -> dict | None:
        """{"bases": [addresses], "main": rgb | None, "accent": rgb | None, "places": {offset: 16 bytes}}, or None when nothing is
        known of it. `places` (1.8.3 part 2): the places a design gave their own colour, with the bytes they hold now."""
        e = self.fxr.get(str(eid))
        if e is None:
            return None
        out = {"bases": [int(b) for b in e.get("bases", ())], "main": e.get("main"), "accent": e.get("accent")}
        if e.get("places"):
            out["places"] = {int(at, 16): bytes.fromhex(h) for at, h in e["places"].items()}
        return out

    def set_effect(self, eid: str, bases, main=None, accent=None, places=None) -> None:
        self.fxr[str(eid)] = self._mine["fxr"][str(eid)] = {
            "bases": sorted({int(b) for b in bases}), "main": list(main) if main is not None else None,
            "accent": list(accent) if accent is not None else None,
            **({"places": {"0x%x" % at: b.hex() for at, b in sorted(places.items())}} if places else {})}

    def save(self) -> None:
        """The file as it is now, with what this object changed written over it (an OSError when it cannot be written)."""
        with _Lock(self.path.with_name(self.path.name + ".lock")):
            text, fxr = self._read()
            text["slots"].update(self._mine["slots"])
            for gid, fields in self._mine["rows"].items():
                text["rows"].setdefault(gid, {}).update(fields)
            fxr.update(self._mine["fxr"])
            doc = {"game_pid": self.pid, "game_started": self.started, "text": text, "fxr": fxr}
            tmp = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
            tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
            _replace(tmp, self.path)
        self.text, self.fxr = text, fxr


REPLACE_TRIES = 10            # a reader may hold the file open for a moment (Windows refuses to replace it then: WinError 5)
REPLACE_PAUSE = 0.05


def _replace(tmp: Path, path: Path) -> None:
    """os.replace, tried again while another process holds `path` open (PermissionError on Windows); the temporary file is removed when
    it never succeeds (the OSError is raised: the caller says the cache was not saved)."""
    for n in range(REPLACE_TRIES):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if n == REPLACE_TRIES - 1:
                try:
                    tmp.unlink()
                except OSError:
                    pass
                raise
            time.sleep(REPLACE_PAUSE)


class _Lock:
    """A lock file for the read-change-write of save() across processes. When it cannot be had within LOCK_WAIT the save goes on
    without it (a cache is only hints: a lost entry means a later step looks through the memory again, never a wrong write)."""

    def __init__(self, path: Path):
        self.path, self.held = path, False

    def __enter__(self):
        end = time.monotonic() + LOCK_WAIT
        while True:
            try:
                os.close(os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                self.held = True
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > LOCK_STALE:
                        self.path.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
            except OSError:
                return self                    # the folder cannot hold a lock file: save without it
            if time.monotonic() > end:
                return self
            time.sleep(0.02)

    def __exit__(self, *exc):
        if self.held:
            try:
                self.path.unlink(missing_ok=True)
            except OSError:
                pass

"""The read baselines (1.8.0 part 2, `reset`): what `read` counts from, kept in a small file so every reader of the same game shares it.

    <TOOLS-DIR>\\baselines.json   {"pid": 1234, "started": 1.7e9, "runes": {"at": "...", "total": 55214603},
                                   "buffs": {"at": "..."}, "animations": {"at": "..."}}

`reset` writes it (nothing is written to the game): `runes` makes `character.runes.baseline` the total of that moment (so `delta` counts
from 0 again), `buffs` / `animations` clear the history of the monitors (what was seen and has ended). A reader (`read --live`, the
monitors, `export --live`) looks at the file every few seconds and takes what is new; a one-shot `read` takes the runes baseline at once.
The file is for one game process: a baseline of another one (an earlier game) is not used.

Pure file work; the reader decides what to do with it."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from ..paths import app_data_dir

FILE = "baselines.json"
NAMES = ("runes", "buffs", "animations")
ALIASES = {"runes": "runes", "character.runes": "runes", "character.runes.delta": "runes", "runes.delta": "runes",
           "character.runes.baseline": "runes", "runes.baseline": "runes",
           "buffs": "buffs", "character.buffs": "buffs", "monitor-buffs": "buffs",
           "animations": "animations", "character.animations": "animations", "monitor-animations": "animations"}


def default_path() -> Path:
    return app_data_dir() / FILE


def names_of(words: list[str]) -> list[str]:
    """`reset` names -> the baselines (`runes`, `buffs`, `animations`); nothing, `*` or `all`: every one. ValueError otherwise."""
    if not words or any(w.strip().lower() in ("*", "all") for w in words):
        if len(words) > 1:
            raise ValueError("`*` and `all` stand alone")
        return list(NAMES)
    out = []
    for w in words:
        key = w.strip().lower()
        if key == "monitor":
            got = ["buffs", "animations"]
        elif key in ALIASES:
            got = [ALIASES[key]]
        else:
            raise ValueError(f"{w!r}: no baseline of that name (runes, buffs, animations, monitor, or * / all)")
        out += [g for g in got if g not in out]
    return out


def load(path: Path | None = None) -> dict:
    try:
        doc = json.loads(Path(path or default_path()).read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def save(pid: int, started, what: dict, path: Path | None = None) -> Path:
    """Write the baselines `what` ({"runes": total | None, "buffs": None, ...}) for the game process `pid` (started at `started`); the
    others are kept when the file is of the same process."""
    p = Path(path or default_path())
    doc = load(p)
    if doc.get("pid") != pid or doc.get("started") != started:
        doc = {}
    doc.update({"pid": pid, "started": started})
    at = time.strftime("%Y-%m-%d %H:%M:%S")
    for name, value in what.items():
        doc[name] = {"at": at, "stamp": time.time(), **({"total": value} if name == "runes" else {})}
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    os.replace(tmp, p)
    return p


class Watch:
    """What a reader takes from the file: `new()` -> {name: entry} of the baselines set since the last look, for this game process."""

    def __init__(self, pid: int, started, path: Path | None = None, since: float | None = None):
        self.pid, self.started, self.path = pid, started, Path(path or default_path())
        self.seen: dict[str, float] = {}
        self._stamp = None
        if since is not None:          # what was set before this reader started counts as seen (except the runes, taken at once)
            doc = self._doc()
            for name in NAMES:
                if name != "runes" and isinstance(doc.get(name), dict):
                    self.seen[name] = doc[name].get("stamp", 0)

    def _doc(self) -> dict:
        doc = load(self.path)
        return doc if doc.get("pid") == self.pid and doc.get("started") == self.started else {}

    def new(self) -> dict[str, dict]:
        try:
            st = self.path.stat()
            stamp = (st.st_mtime_ns, st.st_size)
        except OSError:
            return {}
        if stamp == self._stamp:
            return {}
        self._stamp = stamp
        out = {}
        for name, entry in self._doc().items():
            if name in NAMES and isinstance(entry, dict) and entry.get("stamp", 0) > self.seen.get(name, -1):
                self.seen[name] = entry.get("stamp", 0)
                out[name] = entry
        return out

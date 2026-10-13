"""Where the steps of a game process found what they changed, so a later write in the SAME game needs no look through its memory
(1.7.2). `memory-cache.json` in the vault folder, tied to the pid and the start time of the game process (like params-snapshot.json):
a new game starts empty, and nothing of it is ever used for another process.

  text  the address of each text table's pointer (the array's slots `write --text` switched) and the texts written, by goods id
  fxr   per effect file: the addresses of its copies and the colours they carry now (`main` for the plan's colours, `accent` for the
        accent places; None = the game's own)

An address is a hint, never trusted: before anything is written there, the bytes are checked (writer/fxr.repaint,
writer/text.read_table); when the game moved or reloaded something, the step that uses the cache looks again.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

CACHE_NAME = "memory-cache.json"


class MemoryCache:
    def __init__(self, path: Path, pid: int, started):
        self.path, self.pid, self.started = Path(path), pid, started
        self.text: dict = {"slots": {}, "rows": {}}
        self.fxr: dict = {}

    def load(self) -> "MemoryCache":
        try:
            doc = json.loads(self.path.read_text(encoding="utf-8"))
            if doc.get("game_pid") == self.pid and doc.get("game_started") == self.started:
                self.text = {"slots": dict(doc.get("text", {}).get("slots", {})), "rows": dict(doc.get("text", {}).get("rows", {}))}
                self.fxr = dict(doc.get("fxr", {}))
        except (OSError, ValueError, AttributeError):
            pass                      # no file, a broken one, another game process: nothing is known
        return self

    # ---- text
    def text_slots(self) -> dict:
        """{table name: the address of its pointer}."""
        return {k: int(v) for k, v in self.text["slots"].items()}

    def set_text(self, slots: dict, rows: dict) -> None:
        """`slots` {table name: pointer address}; `rows` {goods id: {field: text}} (merged over what was written before)."""
        self.text["slots"].update({k: int(v) for k, v in slots.items()})
        for gid, fields in rows.items():
            self.text["rows"].setdefault(str(gid), {}).update(fields)

    def texts(self, goods: int) -> dict:
        return dict(self.text["rows"].get(str(goods), {}))

    # ---- effect files
    def effect(self, eid: str) -> dict | None:
        """{"bases": [addresses], "main": rgb | None, "accent": rgb | None}, or None when nothing is known of it."""
        e = self.fxr.get(str(eid))
        return None if e is None else {"bases": [int(b) for b in e.get("bases", ())], "main": e.get("main"), "accent": e.get("accent")}

    def set_effect(self, eid: str, bases, main=None, accent=None) -> None:
        self.fxr[str(eid)] = {"bases": sorted({int(b) for b in bases}), "main": list(main) if main is not None else None,
                              "accent": list(accent) if accent is not None else None}

    def save(self) -> None:
        doc = {"game_pid": self.pid, "game_started": self.started, "text": self.text, "fxr": self.fxr}
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)

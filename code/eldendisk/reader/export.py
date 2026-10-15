"""`export`: the document (`disk.json`, the single source of truth) and the policy for writing it.

Write policy (spec 1.6.2 section 5): sample at the loop rate, but write only when the document changed, never more
often than `interval`, and a change that arrives inside the interval is written when it elapses. A change that is only
a buff countdown is refreshed at most every `timer_interval` seconds (0 = never). The last document is written on exit.
Every write goes to a temp file that replaces the target.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ..game.paramnames import has_fields
from ..game.params import ParamError
from ..game.paramtables import Tables, decode_row
from .sampler import Sample

RETRIES = 5
RETRY_DELAY_S = 0.01


class JsonLogger:
    """Atomic JSON writer. Refuses to write inside the game folder."""

    def __init__(self, out_dir: Path, game_dir: Path | None = None, filename: str = "disk.json"):
        out = Path(out_dir).resolve()
        if game_dir is not None:
            g = Path(game_dir).resolve()
            if out == g or g in out.parents:
                raise ValueError(f"output directory must not be inside the game folder: {out}")
        out.mkdir(parents=True, exist_ok=True)
        self.path = out / filename
        self._tmp = out / (filename + ".tmp")

    def write(self, doc: dict) -> bool:
        """True when the file was replaced. False if a reader/antivirus held the file (caller retries later)."""
        text = json.dumps(doc, indent=2)
        for _ in range(RETRIES):
            try:
                self._tmp.write_text(text, encoding="utf-8")
                os.replace(self._tmp, self.path)
                return True
            except PermissionError:  # tmp or target locked by another process
                time.sleep(RETRY_DELAY_S)
        return False

    def write_chunks(self, chunks) -> bool:
        """`write` of a document too big to hold as one string (`params.json`: hundreds of MB): the pieces go to the temp file as
        they come, then it replaces the target. False if the target stayed locked."""
        with open(self._tmp, "w", encoding="utf-8", newline="\n") as f:
            for piece in chunks:
                f.write(piece)
        for _ in range(RETRIES * 10):
            try:
                os.replace(self._tmp, self.path)
                return True
            except PermissionError:
                time.sleep(RETRY_DELAY_S * 10)
        return False


PARAMS_NAME = "params.json"


def params_chunks(tables: Tables, profile: dict, progress: Callable[[int, int, str], None] | None = None,
                  stats: dict | None = None):
    """The pieces of `params.json` (1.8.0 part 4, `export --params`): every table of the game the tool finds, every row with every
    field, read from the game now, one table at a time and one row a line (`findstr "10000000"` gives the row). A table no layout
    decodes has each row as its bytes (`{"_raw": "hex"}`); a table that cannot be read is listed under `skipped` with the reason.
    `stats` gets tables, rows, raw (the tables given as bytes) and skipped."""
    stats = stats if stats is not None else {}
    stats.update(tables=0, rows=0, raw=[], skipped={})
    names = list(tables.index())
    head = {"profile": profile, "written": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    yield "{\n" + "".join(f"  {json.dumps(k)}: {json.dumps(v)},\n" for k, v in head.items()) + '  "params": {'
    first = True
    for i, table in enumerate(names):
        if progress:
            progress(i, len(names), table)
        try:
            if has_fields(table):
                rows = {rid: decode_row(table, raw) for rid, raw in tables.all_rows(table).items()}
            else:
                rows = {rid: {"_raw": raw.hex()} for rid, raw in tables.all_rows(table, raw=True).items()}
                stats["raw"].append(table)
        except ParamError as exc:
            stats["skipped"][table] = str(exc)
            continue
        body = ",\n".join(f"      {json.dumps(str(rid))}: {json.dumps(row)}" for rid, row in rows.items())
        yield ("" if first else ",") + f"\n    {json.dumps(table)}: {{\n{body}\n    }}"
        first = False
        stats["tables"] += 1
        stats["rows"] += len(rows)
    yield f'\n  }},\n  "skipped": {json.dumps(stats["skipped"])}\n}}\n'


def build_document(*, now: datetime | None = None, state: str, pid: int | None, anti_cheat: str,
                   exe_sha256: str | None, profile_label: str | None,
                   buffs_supported: bool = True,
                   animations_supported: bool = True,
                   creative_supported: bool = True,
                   sample: Sample | None,
                   note: str | None = None, last_character: dict | None = None,
                   mode: str = "telemetry",
                   read_only: bool = True,
                   creative: bool = False) -> dict:
    has_character = sample is not None and sample.character is not None
    game_connected = state in ("CONNECTED", "IDLE")

    if has_character:
        character = sample.character
    elif last_character is not None:
        character = last_character
    else:
        character = None

    version = profile_label
    if profile_label and "Elden Ring " in profile_label:
        version = profile_label.replace("Elden Ring ", "")

    profile = {
        "sha256": exe_sha256,
        "game": "eldenring.exe",
        "version": version,
    }

    features = {
        "buffs_supported": buffs_supported,
        "animations_supported": animations_supported,
        "creative_supported": creative_supported,
    }

    status = {
        "pid": pid,
        "tool_state": state,
        "anti_cheat_state": anti_cheat,
        "game_connected": game_connected,
        "ignored": {
            "buffs": sample.ignored_buffs if sample else 0,
            "animations": sample.ignored_animations if sample else 0,
        },
    }

    session = {
        "mode": mode,
        "read_only": read_only,
        "creative": creative,
    }

    systems: dict = {
        "profile": profile,
        "features": features,
        "status": status,
        "session": session,
    }

    err_msg = note or (sample.error if sample else None)
    if err_msg:
        ts_dt = now or datetime.now(timezone.utc)
        ts_str = ts_dt.isoformat().replace("+00:00", "Z")
        systems["errors"] = {
            "code": 1,
            "message": err_msg,
            "details": None,
            "timestamp": ts_str,
        }

    # no `params`: the tables are not the disk's (1.8.0 part 4). `read params...` reads them from the game, `export --params`
    # writes every row to params.json
    return {
        "systems": systems,
        "character": character,
    }


def doc_signature(doc: dict) -> dict:
    """The document minus the per-tick countdown (`buff_duration`): equal signatures mean only timers moved."""
    ch = doc.get("character")
    if not isinstance(ch, dict) or not ch.get("buffs"):
        return doc
    buffs = {}
    for eid, buff in ch["buffs"].items():
        times = buff.get("times")
        if times is not None:
            buff = {**buff, "times": {k: v for k, v in times.items() if k != "buff_duration"}}
        buffs[eid] = buff
    return {**doc, "character": {**ch, "buffs": buffs}}


class ExportWriter:
    """Builds the document from what the reader knows and decides when it reaches the disk."""

    def __init__(self, logger: JsonLogger | None, *, interval: float = 0.5, timer_interval: float = 2.0,
                 verbose: bool = False, log: Callable[[str], None] = lambda _m: None,
                 clock: Callable[[], float] = time.monotonic):
        self.logger = logger
        self.interval, self.timer_interval = interval, timer_interval
        self.verbose, self._log, self._clock = verbose, log, clock
        self.pid: int | None = None
        self.anti_cheat = "UNKNOWN"
        self.sha: str | None = None
        self.label: str | None = None
        self.buffs_supported = False
        self.animations_supported = False
        self.creative = False                     # a valid RUNNING session record exists: the portal is open (set by the reader loop)
        self.writes = 0
        self._last_character: dict | None = None
        self._last_doc: dict | None = None
        self._last_sig: dict | None = None
        self._last_t = 0.0
        self._latest: dict | None = None
        self._busy_warned = False
        self._last_verbose: tuple | None = None
        self.creative_block: Callable[[], dict | None] | None = None    # the `creative` block (1.8.0), when the command gives one

    def _due(self, doc: dict, now: float) -> bool:
        if self._last_doc is None:
            return True
        if doc == self._last_doc:
            return False
        gap = now - self._last_t
        if doc_signature(doc) != self._last_sig:
            return gap >= self.interval
        return self.timer_interval > 0 and gap >= max(self.interval, self.timer_interval)

    def _write(self, doc: dict, now: float) -> bool:
        if self.logger.write(doc):
            self._last_doc, self._last_sig, self._last_t = doc, doc_signature(doc), now
            self._busy_warned = False
            self.writes += 1
            return True
        if not self._busy_warned:
            self._busy_warned = True
            self._log("warning: output file busy, will retry (further skips are not repeated)")
        return False

    def build(self, state: str, sample: Sample | None = None, note: str | None = None) -> dict:
        """The document for this sample (also remembers the character, so a lost world keeps the last one)."""
        if sample is not None and sample.character is not None:
            self._last_character = sample.character
        doc = build_document(
            state=state, pid=self.pid, anti_cheat=self.anti_cheat, exe_sha256=self.sha, profile_label=self.label,
            buffs_supported=self.buffs_supported, animations_supported=self.animations_supported,
            sample=sample, last_character=self._last_character, note=note,
            mode="creative" if self.creative else "telemetry", read_only=not self.creative, creative=self.creative,
        )
        if self.creative_block is not None:
            doc["creative"] = self.creative_block()
        return doc

    def emit(self, state: str, sample: Sample | None = None, note: str | None = None, now: float | None = None) -> None:
        doc = self.build(state, sample, note)
        self._latest = doc
        now = self._clock() if now is None else now
        if self.logger is not None and self._due(doc, now):
            self._write(doc, now)
        if self.verbose:
            err = doc["systems"]["errors"]["message"] if "errors" in doc["systems"] else None
            if (state, err) != self._last_verbose:
                self._last_verbose = (state, err)
                self._log(f"[{state}]" + (f" {err}" if err else ""))

    def close(self) -> None:
        """Final write: whatever the last emitted document was reaches the disk."""
        if self.logger is not None and self._latest is not None and self._latest != self._last_doc:
            self._write(self._latest, self._clock())

"""Planning edits of any numeric field of the six workbench tables (`write --set params.Magic.6230.mp=10`) and the snapshot
of the game's own values that `--reset` puts back. No memory is touched here: the writer (writer.py) does that.

A name is `params.<Table>.<id>.<field>`; the table is one of paramlayouts.LAYOUTS (any spelling paramtables knows), the id is
one row, the field is a name or a pattern (`ref*`). A value is checked against the field's type, not clamped. A field that
holds the id of another row is allowed, with a note.

The snapshot is a small file: `write` is a new process every time, and "the game's own value" is what a field held before
the first change made in this game process. A new game process (pid or start time differs) starts a new snapshot.
"""
from __future__ import annotations

import difflib
import json
import math
import os
import re
import struct
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from ..game.paramlayouts import LAYOUTS
from ..game.params import ParamNameError
from ..game.paramtables import TABLES, UNIT_FORMATS, table_name

SNAPSHOT_NAME = "params-snapshot.json"
_RANGES = {"s8": (-(1 << 7), (1 << 7) - 1), "u8": (0, (1 << 8) - 1), "s16": (-(1 << 15), (1 << 15) - 1),
           "u16": (0, (1 << 16) - 1), "s32": (-(1 << 31), (1 << 31) - 1), "u32": (0, (1 << 32) - 1), "b32": (-(1 << 31), (1 << 31) - 1)}
_F32_MAX = 3.4028234663852886e38
# a field that names another row (an id that matches nothing can crash the game when the row is used)
_ID_LIKE = re.compile(r"(Id|ID)(\d+|_\w+)?$")


@dataclass(frozen=True)
class CatalogEdit:
    """One field of one row of a workbench table to change. `value` None: back to the game's own value (`--reset`)."""
    table: str
    row: int
    field: str
    value: float | int | None = None

    @property
    def key(self) -> str:
        return f"{self.table}.{self.row}.{self.field}"

    @property
    def name(self) -> str:
        return f"params.{self.key}"


def is_catalog_name(name: str, profile_keys) -> bool:
    """True for `params.<Table>...` where Table is one of the six and not a table key of the profile (`effects`)."""
    parts = name.strip().split(".")
    return len(parts) >= 2 and parts[0].lower() == "params" and parts[1].lower() in TABLES \
        and parts[1].lower() not in {k.lower() for k in profile_keys}


def _split(name: str, *, need_field: bool) -> tuple[str, str | None, str | None]:
    parts = name.strip().split(".")
    if len(parts) < 2 or parts[0].lower() != "params":
        raise ParamNameError(f"{name!r}: expected params.<Table>.<id>.<field>")
    table = table_name(parts[1])
    if len(parts) == 2:
        return table, None, None
    if not parts[2].isdigit():
        raise ParamNameError(f"{name!r}: the row id must be one number (no pattern), got {parts[2]!r}")
    if len(parts) > 4:
        raise ParamNameError(f"{name!r}: expected params.<Table>.<id>.<field>")
    return table, parts[2], (parts[3] if len(parts) == 4 else None)


def fields_matching(table: str, pattern: str) -> list[str]:
    """The fields of `table` named by `pattern` (letter case does not matter), in the layout's order."""
    fields = LAYOUTS[table]["fields"]
    low = pattern.lower()
    if any(c in pattern for c in "*?["):
        hits = [f for f in fields if fnmatchcase(f.lower(), low)]
    else:
        hits = [f for f in fields if f.lower() == low]
    if not hits:
        near = difflib.get_close_matches(pattern, list(fields), n=3, cutoff=0.6)
        raise ParamNameError(f"{table} has no field {pattern!r}" + (f"; did you mean {', '.join(near)}?" if near else ""))
    return hits


def check_value(table: str, field: str, raw: str) -> float | int:
    """The number typed after `=`, checked against the field's type and bit width (an error, never a clamp)."""
    ftype, _off, _size, _bpos, bits, arr = LAYOUTS[table]["fields"][field]
    if arr != 1 or ftype not in UNIT_FORMATS:
        raise ParamNameError(f"{table}.{field} cannot be set (it is not a single number)")
    text = raw.strip().replace("_", "")
    if ftype == "f32":
        try:
            value = float(text)
        except ValueError:
            raise ParamNameError(f"{raw!r}: {field} takes a number") from None
        if not math.isfinite(value) or abs(value) > _F32_MAX:
            raise ParamNameError(f"{raw!r}: {field} is a 32-bit float, the value does not fit")
        return value
    try:
        value = int(text)
    except ValueError:
        raise ParamNameError(f"{raw!r}: {field} takes a whole number") from None
    lo, hi = (0, (1 << bits) - 1) if bits else _RANGES[ftype]
    if not lo <= value <= hi:
        what = f"{bits} bit(s)" if bits else ftype
        raise ParamNameError(f"{field} = {value}: {what} takes {lo}..{hi}")
    return value


_NOT_A_ROW_ID = {"sortId", "iconId", "modelId", "yesNoDialogMessageId", "createLimitGroupId", "syncNumVaryId"}


def looks_like_an_id(field: str) -> bool:
    return field not in _NOT_A_ROW_ID and bool(_ID_LIKE.search(field))


# ---- bytes of a field ---------------------------------------------------------------------------------------------
def unit_size(table: str, field: str) -> int:
    return struct.calcsize(UNIT_FORMATS[LAYOUTS[table]["fields"][field][0]])


def field_value(table: str, field: str, unit: bytes) -> float | int:
    """What the field holds, from the bytes of the unit (1, 2 or 4 bytes) it lives in."""
    ftype, _off, _size, bpos, bits, _arr = LAYOUTS[table]["fields"][field]
    value = struct.unpack(UNIT_FORMATS[ftype], unit)[0]
    if ftype == "f32":
        return float(f"{value:.7g}")
    return (value >> bpos) & ((1 << bits) - 1) if bits else value


def with_value(table: str, field: str, unit: bytes, value: float | int) -> bytes:
    """`unit` with this field set to `value` (the other bits of a shared unit stay as they are)."""
    ftype, _off, _size, bpos, bits, _arr = LAYOUTS[table]["fields"][field]
    fmt = UNIT_FORMATS[ftype]
    if not bits:
        return struct.pack(fmt, float(value) if ftype == "f32" else int(value))
    cur = int.from_bytes(unit, "little")
    mask = ((1 << bits) - 1) << bpos
    new = (cur & ~mask) | ((int(value) << bpos) & mask)
    return new.to_bytes(len(unit), "little")


def restore(table: str, field: str, unit: bytes, original: bytes) -> bytes:
    """`unit` with this field's bits taken back from `original` (the whole unit when the field has it to itself)."""
    _t, _off, _size, bpos, bits, _arr = LAYOUTS[table]["fields"][field]
    if not bits:
        return original
    mask = ((1 << bits) - 1) << bpos
    new = (int.from_bytes(unit, "little") & ~mask) | (int.from_bytes(original, "little") & mask)
    return new.to_bytes(len(unit), "little")


# ---- the snapshot --------------------------------------------------------------------------------------------------
class Snapshot:
    """`{Table.id.field: original unit bytes}` for the game process (pid, started) it was made in."""

    def __init__(self, path: Path, pid: int, started):
        self.path, self.pid, self.started = Path(path), pid, started
        self.values: dict[str, bytes] = {}
        self.dirty = False

    def load(self) -> None:
        try:
            doc = json.loads(self.path.read_text(encoding="utf-8"))
            if doc.get("game_pid") == self.pid and doc.get("game_started") == self.started:
                self.values = {k: bytes.fromhex(v) for k, v in doc.get("values", {}).items()}
        except (OSError, ValueError, AttributeError):
            self.values = {}         # no file, a broken file, another game process: nothing is remembered

    def get(self, key: str) -> bytes | None:
        return self.values.get(key)

    def record(self, key: str, unit: bytes) -> None:
        """Remember the game's own value, only the first time (a later change must not replace it)."""
        if key not in self.values:
            self.values[key], self.dirty = bytes(unit), True

    def drop(self, key: str) -> None:
        if self.values.pop(key, None) is not None:
            self.dirty = True

    def keys(self) -> list[str]:
        return list(self.values)

    def save(self) -> None:
        if not self.dirty:
            return
        doc = {"game_pid": self.pid, "game_started": self.started, "values": {k: v.hex() for k, v in self.values.items()}}
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)
        self.dirty = False


# ---- planning ------------------------------------------------------------------------------------------------------
def plan_catalog(sets, resets, snapshot: Snapshot | None) -> tuple[list[CatalogEdit], list[str]]:
    """([CatalogEdit], notes) for `--set` (name, value as typed) and `--reset` names. ParamNameError: nothing may be written."""
    edits: dict[str, CatalogEdit] = {}
    notes: list[str] = []
    for name, raw in sets:
        table, row, pattern = _split(name, need_field=True)
        if row is None or pattern is None:
            raise ParamNameError(f"{name!r}: name one field, params.{table}.<id>.<field> (a pattern like ref* works for the field)")
        hits = fields_matching(table, pattern)
        for field in hits:
            value = check_value(table, field, raw)
            edit = CatalogEdit(table, int(row), field, value)
            if edit.key in edits:
                raise ParamNameError(f"{edit.name} is set twice")
            edits[edit.key] = edit
        if len(hits) > 1:
            notes.append(f"{name} matches {len(hits)} values: {', '.join(hits[:6])}" + (f", … ({len(hits)})" if len(hits) > 6 else ""))
        ids = [f for f in hits if looks_like_an_id(f)]
        if ids:
            notes.append(f"{', '.join(ids)}: looks like the id of another row; an id that matches nothing can crash the game")
    for name in resets:
        parts = name.strip().split(".")
        if len(parts) < 2 or len(parts) > 4 or parts[0].lower() != "params":
            raise ParamNameError(f"{name!r}: expected params.<Table>[.<id>[.<field>]]")
        prefix = ".".join(["params", table_name(parts[1]), *parts[2:]]).lower()
        wild = any(c in name for c in "*?[")
        hits = []
        for key in (snapshot.keys() if snapshot else []):
            path = f"params.{key}".lower()
            if (wild and fnmatchcase(path, prefix)) or (not wild and (path == prefix or path.startswith(prefix + "."))):
                hits.append(key)
        if not hits:
            raise ParamNameError(f"{name!r}: no value of it was changed in this game process, nothing to put back")
        for key in hits:
            t, r, f = key.split(".", 2)
            edit = CatalogEdit(t, int(r), f, None)
            if edit.key in edits:
                raise ParamNameError(f"{edit.name} is both in --set and --reset")
            edits[edit.key] = edit
    return list(edits.values()), notes

"""Param tables of the running game (SpEffectParam for now): find the file, find a row by id, read its fields.

A param is a table the game loads into memory as one file: a header, a table of row descriptors (id + where the row
data is) and the rows themselves, `row_size` bytes each. Where the file starts is found through a pointer chain from the
module (`offsets.json`, `params`); every call follows the chain again and nothing is cached (MW-2). Rows are found
by id, never by position, and the file is checked before a row is trusted: one failed check stops the whole read
(correct-or-silent), and the writer never writes to what these checks did not pass.

Read-only: this module only calls `mem.read`. The writing itself lives in writer/writer.py (MW-1).
Measurements and the reasoning: docs/experiments/params/sp-effect-params/.
"""
from __future__ import annotations

import difflib
import math
import struct
from dataclasses import dataclass
from fnmatch import fnmatchcase

from .memory import is_user_ptr, read_ptr
from .profile import PARAM_TYPES, ParamField, ParamsProfile, ParamTable, Profile

ROOT = "params"
NAME = "name"           # the first value of every row in the document: its text from the profile, never written
MAX_GAP = 1 << 20         # rows an extension put between the descriptors and the original data (64 spells: about 117 KB)
MAX_ROWS = 100_000      # a param file with more rows than this is not what we think it is (the largest has ~15,000)


class ParamError(RuntimeError):
    """Why a param could not be read or written right now (the message says what failed)."""


class ParamNameError(ValueError):
    """A `params....` name that matches nothing, or a value that does not fit the field."""


class ParamLockedError(ParamNameError):
    """A field the profile marks as read-only (`"writable": false`)."""


def shown(value: float) -> float:
    """What an f32 is worth in the document: `0.1` and not `0.10000000149011612`."""
    return float(f"{value:.7g}")


def decode(field: ParamField, raw: bytes) -> float | int:
    value = struct.unpack(PARAM_TYPES[field.type], raw)[0]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ParamError(f"{field.name} is not a number (the game holds {value})")
        return shown(value)
    return value


def encode(field: ParamField, value: float | int) -> bytes:
    return struct.pack(PARAM_TYPES[field.type], float(value) if field.type == "f32" else int(value))


def clamp(field: ParamField, value: float | int) -> float | int:
    return max(field.min, min(field.max, value))


def parse_value(field: ParamField, raw: str) -> float | int:
    """The number typed after `=` for this field: a float for f32, a whole number for s32."""
    text = raw.strip().replace("_", "")
    try:
        if field.type == "f32":
            value = float(text)
            if not math.isfinite(value):
                raise ValueError
            return value
        return int(text)
    except ValueError:
        kind = "a number" if field.type == "f32" else "a whole number"
        raise ParamNameError(f"{raw!r}: {field.name} takes {kind}") from None


@dataclass(frozen=True)
class Resolved:
    """One look at a table: where its file is and where each wanted row starts (valid for this moment only)."""
    head: int
    rows: dict[str, int]    # row key (its id as text) -> address of the row data

    def field_address(self, row: str, field: ParamField) -> int:
        return self.rows[row] + field.offset


class ParamStore:
    def __init__(self, mem, profile: Profile, module_base: int):
        if profile.params is None:
            raise ValueError("the profile has no params")
        self.mem, self.base = mem, module_base
        self.spec: ParamsProfile = profile.params

    # -- finding the file --------------------------------------------------------------------------------------
    def _follow(self, table: ParamTable, chain) -> tuple[int | None, str]:
        cur = read_ptr(self.mem, self.base + chain.rva)
        for off in chain.offsets:
            if cur is None or not is_user_ptr(cur):
                break
            cur = read_ptr(self.mem, cur + off)
        if cur is None:
            return None, "unreadable pointer"
        if cur == 0:
            return None, "null pointer"
        if not is_user_ptr(cur):
            return None, f"invalid pointer 0x{cur:X}"
        return cur, ""

    def _check_head(self, head: int) -> tuple[tuple[int, int] | None, str]:
        """((row count, data start), "") when `head` is a param file by the layout, else (None, why not)."""
        lay = self.spec.layout
        raw = self.mem.read(head, lay.descriptors)
        if raw is None:
            return None, "file header unreadable"
        count = struct.unpack_from("<H", raw, lay.row_count)[0]
        data_start = struct.unpack_from("<Q", raw, lay.data_start)[0]
        if not 0 < count <= MAX_ROWS:
            return None, f"row count {count} is not plausible"
        expected = lay.descriptors + count * lay.descriptor_size
        # The game's own file has its data right after the descriptors (gap 0). A file that an extension grew in place (rows
        # appended in the space in front of the old data) has a gap holding the new rows plus the padding that keeps the old data 8-aligned (measured on the
        # slot-1 build: Goods 184, Magic 168, Shop 56, SpEffect 1824), so the gap is a multiple of 4.
        gap = data_start - expected
        if gap < 0 or gap % 4 or gap > MAX_GAP:
            return None, f"data start {data_start} does not match {count} rows (expected {expected})"
        return (count, data_start), ""

    def find_head(self, table: ParamTable) -> tuple[int, int, int]:
        """(head, row count, data start) of the first chain that leads to a file that passes the checks."""
        why = []
        for i, chain in enumerate(table.chains, 1):
            head, reason = self._follow(table, chain)
            if head is None:
                why.append(f"chain {i}: {reason}")
                continue
            info, reason = self._check_head(head)
            if info is None:
                why.append(f"chain {i}: {reason}")
                continue
            return head, info[0], info[1]
        raise ParamError(f"{table.table} not found ({'; '.join(why)})")

    def resolve(self, key: str) -> Resolved:
        """Follow the chain, check the file and find the rows listed in the profile for table `key`."""
        table = self.spec.tables[key]
        lay = self.spec.layout
        head, count, data_start = self.find_head(table)
        raw = self.mem.read(head + lay.descriptors, count * lay.descriptor_size)
        if raw is None:
            raise ParamError(f"{table.table}: the row table is unreadable")
        want = {row.id: row for row in table.rows.values()}
        found: dict[int, int] = {}
        for i in range(count):
            rid = struct.unpack_from("<I", raw, i * lay.descriptor_size + lay.descriptor_id)[0]
            if rid in want:
                found[rid] = struct.unpack_from("<Q", raw, i * lay.descriptor_size + lay.descriptor_data_offset)[0]
                if len(found) == len(want):
                    break
        rows: dict[str, int] = {}
        end = data_start + count * table.row_size
        for row in table.rows.values():
            off = found.get(row.id)
            if off is None:
                raise ParamError(f"{table.table}: row {row.id} ({row.name}) is not in the file")
            if off < data_start or off + table.row_size > end or (off - data_start) % table.row_size:
                raise ParamError(f"{table.table}: row {row.id} ({row.name}) points outside the data (offset {off})")
            rows[row.key] = head + off
        return Resolved(head, rows)

    # -- reading -----------------------------------------------------------------------------------------------
    def read_row(self, table: ParamTable, resolved: Resolved, row: str) -> dict[str, float | int]:
        raw = self.mem.read(resolved.rows[row], table.row_size)
        if raw is None:
            raise ParamError(f"{table.table}: row {row} ({table.rows[row].name}) is unreadable")
        return {NAME: table.rows[row].name,
                **{name: decode(f, raw[f.offset:f.offset + 4]) for name, f in table.fields.items()}}

    def read_all(self) -> dict:
        """`{table key: {id: {name, field: value}}}`: the `params` block of the document. ParamError if anything fails."""
        out: dict = {}
        for key, table in self.spec.tables.items():
            resolved = self.resolve(key)
            out[key] = {name: self.read_row(table, resolved, name) for name in table.rows}
        return out


# -- names ------------------------------------------------------------------------------------------------------
def field_paths(spec: ParamsProfile) -> list[tuple[str, str, str, str]]:
    """[(path, table key, row key, field)] for every value of every table, e.g. `params.effects.1621000.vfxId`.
    The row's `name` is one of them (it is shown, and locked)."""
    return [(f"{ROOT}.{key}.{row}.{field}", key, row, field)
            for key, table in spec.tables.items() for row in table.rows for field in (NAME, *table.fields)]


def _writable(spec: ParamsProfile, key: str, field: str) -> bool:
    return field != NAME and spec.tables[key].fields[field].writable


def _group_paths(spec: ParamsProfile) -> list[str]:
    out = []
    for key, table in spec.tables.items():
        out.append(f"{ROOT}.{key}")
        out += [f"{ROOT}.{key}.{row}" for row in table.rows]
    return out


def _suggest(name: str, spec: ParamsProfile) -> str:
    paths = [p for p, *_ in field_paths(spec)] + _group_paths(spec)
    low = {p.lower(): p for p in paths}
    near = difflib.get_close_matches(name.lower(), list(low), n=3, cutoff=0.6)
    return f"; did you mean {', '.join(low[n] for n in near)}?" if near else ""


def match_names(spec: ParamsProfile, name: str, *, reset: bool) -> tuple[list[tuple[str, str, str]], list[str]]:
    """What `--set NAME=` (or `--reset NAME`) means: ([(table key, row, field)] to act on, [paths skipped as locked]).

    `name` is a path under `params.` in any letter case, or a pattern (`params.effects.*.effectEndurance`).
    `--set` needs fields; `--reset` also takes a row or a table (all its writable fields). A locked field named exactly
    is refused (ParamLockedError); in a pattern it is skipped and reported. ParamNameError for anything else.
    """
    path = name.strip()
    low = path.lower()
    leaves = field_paths(spec)
    skipped: list[str] = []
    hits: list[tuple[str, str, str]] = []
    names: list[str] = []

    def take(p, key, row, field):
        if _writable(spec, key, field):
            hits.append((key, row, field))
        elif field != NAME:         # `name` is never in the "skipped" list: it is not a game value
            skipped.append(p)
        else:
            names.append(p)

    if any(c in path for c in "*?["):
        matched = [x for x in leaves if fnmatchcase(x[0].lower(), low)]
        if not matched:
            raise ParamNameError(f"{name!r}: matches no value of params{_suggest(name, spec)}")
        for x in matched:
            take(*x)
    else:
        exact = [x for x in leaves if x[0].lower() == low]
        if exact:
            p, key, row, field = exact[0]
            if not _writable(spec, key, field):
                raise ParamLockedError(f"{p} is locked (read-only)")
            hits.append((key, row, field))
        elif reset and any(g.lower() == low for g in _group_paths(spec)):
            for x in leaves:
                if x[0].lower().startswith(low + "."):
                    take(*x)
        elif any(g.lower() == low for g in _group_paths(spec)):
            raise ParamNameError(f"{name!r} is a group: name one field, or use a pattern such as {path}.*")
        else:
            raise ParamNameError(f"unknown name {name!r}{_suggest(name, spec)}")
    if not hits:
        raise ParamLockedError(f"{name!r}: every matching value is locked (read-only): {', '.join(skipped or names)}")
    return list(dict.fromkeys(hits)), skipped

"""Gated memory writes for `eldendisk write` (spec 1.6.2, MW-1..MW-6 and FR-14).

This is the ONLY module that may call WriteProcessMemory.

Rules enforced here:
  * the write handle exists only for one `write` command (WritableProcessMemory is created and closed by that
    command, and only after the session record authorised it; the host, `read` and `vault` never import this)     MW-1
  * every write re-resolves the pointer chain through the Layout; no address is ever cached                       MW-2
  * a null/invalid pointer or unreadable field skips that write, it never raises                                  MW-3
  * only stored current values are written (level, runes, attributes, current HP/FP/stamina) and the fields the
    profile marks writable in a param row; derived values (maximums) are left to the game                        MW-4
  * writes run at a bounded rate and every value is clamped to a sane range                                       MW-5
  * offsets come from the profile that matched the exe hash (the Layout's profile)                                MW-6
  * nothing is written unless the WriteGate is open (session authorised, no anti-cheat, known exe)               FR-14
  * since 1.7.1 the one allocation: `alloc` gives `innovate-spells apply` room in the game for a text table (writer/text.py);
    the game's own memory is never freed or resized
  * since 1.7.1 `regions` lists the game's readable memory (VirtualQueryEx), so `innovate-spells apply` can find the game's copies
    of three effect files (writer/fxr.py)
"""
from __future__ import annotations

import ctypes
import struct
import time
from dataclasses import dataclass, replace
from typing import Callable

from ..game import _win
from ..game.layout import ATTR_NAMES, ATTR_RANGE, LEVEL_RANGE, RUNES_MAX, Layout, parse_vitals_block
from ..game.memory import ACCESS_MASK, ProcessMemory, is_user_ptr
from ..game.params import (ParamError, ParamNameError, ParamStore, clamp as clamp_param, encode as encode_param,
                           match_names, parse_value)
from ..game.paramlayouts import LAYOUTS
from ..game.paramtables import Tables
from ..game.profile import ParamsProfile
from .paramedit import CatalogEdit, Snapshot, field_value, is_catalog_name, plan_catalog, restore, unit_size, with_value
from ..game.values import is_param_name, write_targets

PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
MEM_COMMIT_RESERVE, PAGE_READWRITE = 0x3000, 0x04
WRITE_ACCESS_MASK = ACCESS_MASK | PROCESS_VM_WRITE | PROCESS_VM_OPERATION | _win.PROCESS_QUERY_INFORMATION
MEM_COMMIT, PAGE_NOACCESS, PAGE_GUARD = 0x1000, 0x01, 0x100
PAGE_NOCACHE, PAGE_WRITECOMBINE, MEM_PRIVATE = 0x200, 0x400, 0x20000      # a scan skips the first two (slow to read) and keeps private memory only

# vitals block (see disk.parse_vitals_block): byte offset of the CURRENT value, index of its (capped) maximum
VITAL_FIELDS = {"hp": (0, 1), "fp": (16, 5), "stamina": (28, 8)}
EDIT_NAMES = ("level", "runes", *ATTR_NAMES, *VITAL_FIELDS)
WRITE_HZ_RANGE = (1.0, 30.0)

if _win.IS_WINDOWS:
    from ctypes import wintypes

    _win.k32.WriteProcessMemory.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t),
    ]
    _win.k32.WriteProcessMemory.restype = wintypes.BOOL
    _win.k32.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    _win.k32.VirtualAllocEx.restype = ctypes.c_void_p


class WritableProcessMemory(ProcessMemory):
    """Read + write handle. Created by `write` after the session check, closed when the command ends."""

    def __init__(self, pid: int):
        super().__init__(pid, access=WRITE_ACCESS_MASK)

    def write(self, addr: int, data: bytes) -> bool:
        """True only if exactly len(data) bytes were written."""
        if not data or not is_user_ptr(addr):
            return False
        buf = ctypes.create_string_buffer(bytes(data), len(data))
        n = ctypes.c_size_t(0)
        ok = _win.k32.WriteProcessMemory(self._h, ctypes.c_void_p(addr), buf, len(data), ctypes.byref(n))
        return bool(ok) and n.value == len(data)

    def regions(self, strict: bool = False) -> list[tuple[int, int]]:
        """(base, size) of every committed region of the game that can be read (not no-access, not guard), user space only. `strict`
        (for a scan of the whole game) keeps only the game's own private memory (its heap) and leaves out what is slow or pointless to
        read: write-combined and uncached memory (shared with the graphics card), mapped files and the program's own image."""
        out, addr, mbi = [], 0, _win.MEMORY_BASIC_INFORMATION()
        while addr < 0x7FFFFFFF0000 and _win.k32.VirtualQueryEx(self._h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            size = mbi.RegionSize
            if mbi.State == MEM_COMMIT and mbi.Protect and not mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD):
                if not strict or (mbi.Type == MEM_PRIVATE and not mbi.Protect & (PAGE_NOCACHE | PAGE_WRITECOMBINE)):
                    out.append((mbi.BaseAddress or 0, size))
            addr = (mbi.BaseAddress or 0) + size
        return out

    def describe(self, addr: int) -> str:
        """What kind of memory `addr` is in (for the log): type, protection, the size of its region."""
        mbi = _win.MEMORY_BASIC_INFORMATION()
        if not _win.k32.VirtualQueryEx(self._h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            return "unknown"
        kind = {0x20000: "private", 0x40000: "mapped", 0x1000000: "image"}.get(mbi.Type, f"type {mbi.Type:#x}")
        return f"{kind}, protect {mbi.Protect:#x}, region {mbi.RegionSize >> 20} MB at {mbi.BaseAddress or 0:#x}"

    def alloc(self, size: int) -> int:
        """New read/write memory in the game, `size` bytes (0 on failure). Used once per text table by writer/text.py; the memory
        stays until the game closes."""
        if size <= 0:
            return 0
        return _win.k32.VirtualAllocEx(self._h, None, size, MEM_COMMIT_RESERVE, PAGE_READWRITE) or 0


class WriteGate:
    """Writes are possible only while the gate is open. `write` opens it after the session check."""

    def __init__(self) -> None:
        self._open = False
        self.reason = "gate never opened"

    @property
    def allowed(self) -> bool:
        return self._open

    def open(self) -> None:
        self._open, self.reason = True, "open"

    def close(self, reason: str) -> None:
        self._open, self.reason = False, reason


@dataclass(frozen=True)
class ParamEdit:
    """One field of one param row to change. `value` None: back to the game's own value (`--reset`)."""
    table: str
    row: str
    field: str
    value: float | int | None = None

    @property
    def name(self) -> str:
        return f"params.{self.table}.{self.row}.{self.field}"


@dataclass(frozen=True)
class EditPolicy:
    sets: tuple[tuple[str, int], ...] = ()   # (field, value): held at value
    refill: tuple[str, ...] = ()             # subset of hp / fp / stamina: held at their maximum
    param_sets: tuple[tuple[str, str], ...] = ()   # (`params...` name or pattern, value as typed), meaning known only
    param_resets: tuple[str, ...] = ()             # with the profile: see plan_params
    param_edits: tuple[ParamEdit, ...] = ()        # what the two above came to (plan_params), what the writer applies
    catalog_edits: tuple[CatalogEdit, ...] = ()    # the same for the names of the six workbench tables (paramedit.py)

    @property
    def empty(self) -> bool:
        return not (self.sets or self.refill or self.param_sets or self.param_resets or self.param_edits or self.catalog_edits)


def parse_policy(set_args: list[str] | None, refill: str | None, reset: list[str] | None = None) -> EditPolicy:
    """`write NAME=VALUE...` (`set_args`), a refill of hp, fp, stamina to their maximum (`refill`, "hp,fp"; no command gives it since
    1.8.0) and `write NAME=default` (`reset`: the names); ValueError on anything unknown.

    NAME is a name of `game.values` (full or short: `hp` / `hit_point`, `attrs.faith`), or a pattern naming a group
    (`attributes.*`). A name under `params.` is only checked for its shape here; which rows and fields exist is
    known once the game is found (plan_params). `reset` takes `params.…` names or `all`.
    """
    sets: dict[str, int] = {}
    param_sets: dict[str, str] = {}
    for item in set_args or []:
        name, sep, raw = item.partition("=")
        if not sep or not name.strip():
            raise ValueError(f"{item!r}: expected NAME=VALUE")
        if is_param_name(name):
            if not raw.strip():
                raise ValueError(f"{item!r}: expected NAME=VALUE")
            if name.strip().lower() in {n.lower() for n in param_sets}:
                raise ValueError(f"{name.strip()} is set twice")
            param_sets[name.strip()] = raw.strip()
            continue
        try:
            value = int(raw.strip().replace("_", ""))
        except ValueError:
            raise ValueError(f"{item!r}: value must be an integer") from None
        if value < 0:
            raise ValueError(f"{item!r}: value must not be negative")
        for key in write_targets(name):
            if key in sets:
                raise ValueError(f"{key} is set twice")
            sets[key] = value
    names: list[str] = []
    for n in (refill or "").split(","):
        if n.strip():
            keys = write_targets(n)
            if any(k not in VITAL_FIELDS for k in keys):
                raise ValueError(f"--refill {n.strip()!r}: choose from hp, fp, stamina")
            names += keys
    for n in names:
        if n in sets:
            raise ValueError(f"{n} is in both --set and --refill")
    resets: list[str] = []
    for n in reset or []:
        if "=" in n:
            raise ValueError(f"{n!r}: a name only, the game's own value goes back (no =VALUE)")
        if n.strip().lower() == "all":
            resets.append("all")
        elif is_param_name(n) and n.strip():
            resets.append(n.strip())
        else:
            raise ValueError(f"{n!r}=default: only params have a default of the game (a params.… name, or params)")
    return EditPolicy(tuple(sets.items()), tuple(dict.fromkeys(names)), tuple(param_sets.items()),
                      tuple(dict.fromkeys(resets)))


def plan_params(spec: ParamsProfile | None, policy: EditPolicy, snapshot: Snapshot | None = None
                ) -> tuple[EditPolicy, list[str]]:
    """Resolve the `params` names of `policy` against the profile: (policy with `param_edits` and `catalog_edits`, notes).

    Two kinds of names: `params.effects.…` (the rows the profile lists, with the game's values written in it) and
    `params.<Table>.<id>.<field>` (any row of the six workbench tables; `--reset` puts back what `snapshot` remembers).
    ParamLockedError (a read-only field named exactly) and ParamNameError (unknown name, bad value, a field set twice
    or both set and reset) mean nothing may be written. Nothing here touches the game.
    """
    if not (policy.param_sets or policy.param_resets):
        return policy, []
    if spec is None:
        raise ParamNameError("this game version has no params in offsets.json")
    keys = set(spec.tables)
    cat_sets = [(n, r) for n, r in policy.param_sets if is_catalog_name(n, keys)]
    cat_resets = [n for n in policy.param_resets if n != "all" and is_catalog_name(n, keys)]
    if "all" in policy.param_resets and snapshot is not None:
        cat_resets += [f"params.{k}" for k in snapshot.keys()]
    if (cat_sets or cat_resets) and not spec.catalog:
        raise ParamNameError("this game version has no params.catalog in offsets.json (run `probe`)")
    cat_edits, cat_notes = plan_catalog(cat_sets, cat_resets, snapshot) if (cat_sets or cat_resets) else ([], [])
    policy = replace(policy, param_sets=tuple(x for x in policy.param_sets if x not in cat_sets),
                     param_resets=tuple(n for n in policy.param_resets if n not in cat_resets or n == "all"),
                     catalog_edits=tuple(cat_edits))
    if not (policy.param_sets or policy.param_resets):
        return policy, cat_notes
    edits: dict[tuple[str, str, str], ParamEdit] = {}
    notes: list[str] = list(cat_notes)

    def short(hits) -> str:
        names = [f"{row}.{field}" for _t, row, field in hits]
        return ", ".join(names[:6]) + (f", … ({len(names)})" if len(names) > 6 else "")

    for name, raw in policy.param_sets:
        hits, skipped = match_names(spec, name, reset=False)
        for key, row, field in hits:
            value = parse_value(spec.tables[key].fields[field], raw)
            if (key, row, field) in edits:
                raise ParamNameError(f"params.{key}.{row}.{field} is set twice")
            edits[(key, row, field)] = ParamEdit(key, row, field, value)
        if len(hits) > 1 or skipped:
            notes.append(f"{name} matches {len(hits)} values: {short(hits)}")
        if skipped:
            notes.append(f"skipped (locked): {', '.join(s.removeprefix('params.') for s in skipped)}")
    for name in policy.param_resets:
        if name == "all":
            hits = [(k, r, f) for k, tb in spec.tables.items() for r in tb.rows
                    for f, fd in tb.fields.items() if fd.writable]
        else:
            hits, _skipped = match_names(spec, name, reset=True)
        for key, row, field in hits:
            if (key, row, field) in edits:
                raise ParamNameError(f"params.{key}.{row}.{field} is both in --set and --reset")
            edits[(key, row, field)] = ParamEdit(key, row, field, None)
    return replace(policy, param_edits=tuple(edits.values())), notes


def _clamp(name: str, value: int, maximum: int | None = None) -> int:
    if name == "level":
        lo, hi = LEVEL_RANGE
    elif name == "runes":
        lo, hi = 0, RUNES_MAX
    elif name in ATTR_NAMES:
        lo, hi = ATTR_RANGE
    else:  # current vitals: hp can never be set to 0 (that would kill the character), the others may
        lo, hi = (1 if name == "hp" else 0), maximum if maximum is not None else 0
    return max(lo, min(hi, value))


@dataclass(frozen=True)
class WriteResult:
    name: str
    value: float | int
    wrote: bool
    note: str | None = None


class MemoryWriter:
    def __init__(self, mem, layout: Layout, policy: EditPolicy, gate: WriteGate, *,
                 hz: float = 4.0, clock: Callable[[], float] = time.monotonic,
                 log: Callable[[str], None] | None = None, snapshot: Snapshot | None = None, tables: Tables | None = None):
        if not WRITE_HZ_RANGE[0] <= hz <= WRITE_HZ_RANGE[1]:
            raise ValueError(f"write rate must be between {WRITE_HZ_RANGE[0]:g} and {WRITE_HZ_RANGE[1]:g} Hz")
        self.mem, self.layout, self.policy, self.gate = mem, layout, policy, gate
        self.snapshot = snapshot
        self.tables = tables       # a Tables a long-lived caller keeps (its row index: the chain and the row are still checked each time)
        self._period, self._clock, self._log = 1.0 / hz, clock, log or (lambda _m: None)
        self._next = 0.0
        self._last_status: dict[str, str] = {}
        self.writes = 0
        self.skipped: list[str] = []   # why a requested edit could not even be attempted (last tick)

    def _skip(self, name: str, status: str, msg: str) -> None:
        self.skipped.append(f"{name}: {msg}")
        self._report(name, status, msg)

    def _report(self, name: str, status: str, msg: str) -> None:
        if self._last_status.get(name) != status:  # log transitions only, not every tick
            self._last_status[name] = status
            self._log(f"[write] {name}: {msg}")

    def _put(self, name: str, addr: int, raw: bytes, current: bytes, target, fmt: str,
             note: str | None = None) -> WriteResult | None:
        if raw == current:
            self._report(name, "held", f"holding {target}")
            return None
        if not self.mem.write(addr, raw) or self.mem.read(addr, len(raw)) != raw:
            self._report(name, "failed", "write failed or did not stick (will retry)")
            return WriteResult(name, target, False, "write failed")
        self.writes += 1
        self._report(name, "written", f"set to {target}")
        return WriteResult(name, target, True, note)

    def apply_once(self) -> list[WriteResult]:
        """Force an immediate single-pass write disregarding next rate limit tick."""
        self._next = 0.0
        return self.tick()

    def tick(self) -> list[WriteResult]:
        """Apply the policy once if the gate is open and the rate limit allows. Returns the writes attempted."""
        if self.policy.empty or not self.gate.allowed:
            return []
        now = self._clock()
        if now < self._next:
            return []
        self._next = now + self._period
        out: list[WriteResult] = []
        self.skipped = []

        stored = [(n, v) for n, v in self.policy.sets if not (n in VITAL_FIELDS)]
        if stored:
            gd, why = self.layout.locate_game_data()
            if gd is None:
                self._skip("game_data", f"skip:{why}", f"skipped, {why}")
            else:
                p = self.layout.profile
                for name, value in stored:
                    target = _clamp(name, value)
                    if target != value:
                        self._report(f"{name}:clamp", "c", f"{value} clamped to {target}")
                    if name == "level":
                        addr = gd + p.level
                    elif name == "runes":
                        addr = gd + p.runes
                    else:
                        addr = gd + p.attributes + 4 * ATTR_NAMES.index(name)
                    cur = self.mem.read(addr, 4)
                    if cur is None:
                        self._skip(name, "unreadable", "skipped, field unreadable")
                        continue
                    r = self._put(name, addr, struct.pack("<I", target), cur, target, "<I")
                    if r:
                        out.append(r)

        vital_targets = {n: v for n, v in self.policy.sets if n in VITAL_FIELDS}
        vital_targets.update({n: None for n in self.policy.refill})  # None = hold at maximum
        if vital_targets:
            base, why = self.layout.locate_vitals()
            raw = self.mem.read(base, 40) if base is not None else None
            if raw is None:
                self._skip("vitals", f"skip:{why}", f"skipped, {why or 'vitals unreadable'}")
            else:
                block, err = parse_vitals_block(raw)
                if block is None:
                    self._skip("vitals", f"skip:{err}", f"skipped, {err}")
                else:
                    for name, value in vital_targets.items():
                        off, max_idx = VITAL_FIELDS[name]
                        maximum = block[max_idx]
                        target = maximum if value is None else _clamp(name, value, maximum)
                        if value is not None and target != value:
                            self._report(f"{name}:clamp", "c", f"{value} clamped to {target}")
                        r = self._put(name, base + off, struct.pack("<i", target), raw[off:off + 4], target, "<i")
                        if r:
                            out.append(r)
        if self.policy.param_edits:
            out += self._tick_params()
        if self.policy.catalog_edits:
            out += self._tick_catalog()
        return out

    def _tick_catalog(self) -> list[WriteResult]:
        """The fields of the six workbench tables: the file and the row are found again for every pass (MW-2), the unit
        of bytes the field lives in is read, changed in its own bits only, written and read back. The game's own value is
        remembered before the first change (the snapshot), `--reset` puts it back and forgets it."""
        out: list[WriteResult] = []
        if self.snapshot is None:
            for edit in self.policy.catalog_edits:
                self._skip(edit.name, "nosnap", "skipped, no snapshot to keep the game's own value in")
            return out
        tables = self.tables or Tables(self.mem, self.layout.profile, self.layout.base)
        rows: dict[tuple[str, int], int | str] = {}
        for edit in self.policy.catalog_edits:
            if (edit.table, edit.row) not in rows:
                try:
                    rows[(edit.table, edit.row)] = tables.row_address(edit.table, edit.row)[0]
                except ParamError as exc:
                    rows[(edit.table, edit.row)] = str(exc)
            base = rows[(edit.table, edit.row)]
            if isinstance(base, str):
                self._skip(edit.name, f"skip:{base}", f"skipped, {base}")
                continue
            addr = base + LAYOUTS[edit.table]["fields"][edit.field][1]
            cur = self.mem.read(addr, unit_size(edit.table, edit.field))
            if cur is None:
                self._skip(edit.name, "unreadable", "skipped, field unreadable")
                continue
            if edit.value is None:
                original = self.snapshot.get(edit.key)
                if original is None:
                    self._skip(edit.name, "nosnap", "skipped, nothing remembered for it in this game process")
                    continue
                new = restore(edit.table, edit.field, cur, original)
            else:
                new = with_value(edit.table, edit.field, cur, edit.value)
                if new != cur:
                    self.snapshot.record(edit.key, cur)
            shown = field_value(edit.table, edit.field, new)
            r = self._put(edit.name, addr, new, cur, shown, "")
            if r:
                out.append(r)
            if edit.value is None and (r is None or r.wrote):
                self.snapshot.drop(edit.key)
        return out

    def _tick_params(self) -> list[WriteResult]:
        """The param fields of the policy: the file and the rows are found again, the file checked, then each field
        is written (clamped to the profile's range) and read back. Anything that cannot be checked is skipped."""
        out: list[WriteResult] = []
        profile = self.layout.profile
        store = ParamStore(self.mem, profile, self.layout.base)
        resolved: dict[str, object] = {}
        for edit in self.policy.param_edits:
            table = profile.params.tables[edit.table]
            field = table.fields[edit.field]
            if not field.writable:   # plan_params keeps these out; this is the last line
                self._skip(edit.name, "locked", "skipped, the field is read-only")
                continue
            if edit.table not in resolved:
                try:
                    resolved[edit.table] = store.resolve(edit.table)
                except ParamError as exc:
                    resolved[edit.table] = str(exc)
            res = resolved[edit.table]
            if isinstance(res, str):
                self._skip(edit.name, f"skip:{res}", f"skipped, {res}")
                continue
            addr = res.field_address(edit.row, field)
            cur = self.mem.read(addr, 4)
            if cur is None:
                self._skip(edit.name, "unreadable", "skipped, field unreadable")
                continue
            note = None
            if edit.value is None:
                target = table.rows[edit.row].defaults[edit.field]
            else:
                target = clamp_param(field, edit.value)
                if target != edit.value:
                    note = f"clamped from {edit.value:g} to the allowed {field.min:g}..{field.max:g}"
                    self._report(f"{edit.name}:clamp", "c", f"{edit.value} clamped to {target}")
            if field.type == "f32":
                target = float(target)
            r = self._put(edit.name, addr, encode_param(field, target), cur, target, "", note)
            if r:
                out.append(r)
        return out

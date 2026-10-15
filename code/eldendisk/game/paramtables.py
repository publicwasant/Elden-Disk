"""Every table of the game's params, any row, any field by name (`read params.NpcParam.10000000.hp`). Read-only.

1.8.0 part 4: every table of the game's regulation.bin, by the name the file gives it (paramnames.py). The field layouts are Paramdex's
(`paramlayouts.py`, generated against the game's own file); where a table's file is comes from `params.catalog` (six chains, measured)
and, for every other table, from walking `params.repository`, the list the game keeps every table in: each slot that ends in a valid
param file is named by the param type the file gives, its rows and, for tables of the same type, its first and last row id, the digest
of its rows or the name the game keeps next to the slot (`Tables.found`). The same decoder serves a row from the running game and a row
from a regulation.bin file (`decode_row` takes the row's bytes), so the two can be compared field for field.

Correct-or-silent, like `params.py`: the file header must pass the same checks, the row size found in the file must be the
layout's, and a row is read only when its descriptor points inside the file. One failed check stops the read.
"""
from __future__ import annotations

import hashlib
import re
import struct
import time
from collections import Counter
from dataclasses import dataclass, field
from fnmatch import fnmatchcase

from .memory import is_user_ptr, read_ptr
from .paramlayouts import LAYOUTS
from .paramnames import TABLES, canonical, has_fields  # noqa: F401  (TABLES: the names a person may type)
from .params import ParamError, ParamNameError, ParamStore, shown

ROOT = "params"
SAMPLE_ROWS = 512
READ_CHUNK = 1 << 20      # bytes per read of a whole table
MAX_BEHIND = 4 << 20      # how far behind the strings a row of a table grown at its end may lie
MAX_EXTRA = 200           # rows a build may add to a table (innovate-spells: Goods, Magic, SpEffect, Bullet, AtkParam_Pc, ShopLineup)
TYPE_AT = 0x10            # the u64 in a param file's header that says where its param type (a name) is
NAME_SPAN = 0x100         # bytes of a slot's object looked through for the table's name, when nothing else tells two tables apart
WALK_AGAIN_S = 5.0        # a walk that found no table (the game had not loaded them yet) is made again after this many seconds
_UTF16 = re.compile(rb"(?:[\x20-\x7e]\x00){4,}")      # a UTF-16 text of plain letters, as the game keeps resource names
UNIT_FORMATS = _FMT = {"s8": "<b", "u8": "<B", "s16": "<h", "u16": "<H", "s32": "<i", "u32": "<I", "f32": "<f", "b32": "<i"}


def table_name(text: str) -> str:
    """The game's name of a table as typed (`npcparam`, `NpcParam`, `Goods`, `MagicParam`)."""
    name = canonical(text)
    if name is None:
        raise ParamNameError(f"{text!r} is not a table of the game (`read params` lists them)")
    return name


def _row_part(text: str):
    if text == "*":
        return "*"
    if not text.isdigit():
        raise ParamNameError(f"the row id must be a number or *, got {text!r}")
    return int(text)


def parse_ref(text: str) -> tuple[str, int | str | None, str | None]:
    """`Magic.6230`, `params.Magic.6230.mp*`, `params.NpcParam` (every row), `params.NpcParam.*.hp` (a field of every row) ->
    (table, row id or "*" or None for every row, field name or pattern or None for every field)."""
    parts = text.strip().split(".")
    if parts and parts[0].lower() == ROOT:
        parts = parts[1:]
    if not 1 <= len(parts) <= 3 or not parts[0]:
        raise ParamNameError(f"{text!r}: write it as Table, Table.id or Table.id.field (for example Magic.6230.mp)")
    table = table_name(parts[0])
    if len(parts) == 1:
        return table, None, None
    row = _row_part(parts[1])
    return table, row, (parts[2] if len(parts) == 3 else None)


# ---- decoding a row ---------------------------------------------------------------------------------------------
def _one(ftype: str, raw: bytes, off: int, bpos: int, bits: int):
    value = struct.unpack_from(_FMT[ftype], raw, off)[0]
    if ftype == "f32":
        return shown(value)
    return (value >> bpos) & ((1 << bits) - 1) if bits else value


def decode_row(table: str, raw: bytes, fields: tuple[str, ...] | None = None) -> dict:
    """{field: value} in the order of the layout; a field that is an array is a list; padding is not listed. `fields`: only
    these (names of the layout, see `fields_like`)."""
    table = canonical(table) or table
    layout = LAYOUTS[table]
    if layout["fields"] is None:
        raise ParamError(f"{table}: its rows cannot be decoded ({layout['why']})")
    if len(raw) != layout["size"]:
        raise ParamError(f"{table}: a row is {layout['size']} bytes, got {len(raw)}")
    return _decoder(table, fields)(raw)


def fields_like(table: str, pattern: str) -> tuple[str, ...]:
    """The fields of `table` whose name matches `pattern` (letter case does not matter; `*` and `?` work), in the layout's order."""
    want = pattern.lower()
    return tuple(n for n in LAYOUTS[table]["fields"] or () if fnmatchcase(n.lower(), want))


def _decode_slow(table: str, raw: bytes, fields: tuple[str, ...] | None) -> dict:
    """The decoder field by field: what `_compile` makes quicker, and what it falls back to for a layout it cannot compile."""
    out: dict = {}
    layout = LAYOUTS[table]["fields"]
    for name in fields or layout:
        ftype, off, size, bpos, bits, arr = layout[name]
        if ftype in ("fixstr", "fixstrW"):
            out[name] = raw[off:off + size].decode("utf-16-le" if ftype == "fixstrW" else "ascii", "replace").split("\0")[0]
        elif arr > 1:
            width = size // arr
            out[name] = [_one(ftype, raw, off + i * width, 0, 0) for i in range(arr)]
        else:
            out[name] = _one(ftype, raw, off, bpos, bits)
    return out


# A row is decoded by a function made once per table (and per set of fields): one struct.unpack of the whole row, then the values
# placed in a dict. Field by field it took 100-160 us a row (SpEffectParam: 1.8 s for its 11,354 rows).
_DECODERS: dict = {}
_SHOWN: dict = {}           # f32 -> what the document shows; the tables repeat a few thousand values


def _f32(value: float) -> float:
    """`shown(value)`, remembered (the decoders look in `_SHOWN` first)."""
    if not value:
        return value                  # 0.0 and -0.0 as they are (equal, so never kept: one would come back as the other)
    out = shown(value)
    if value == value and len(_SHOWN) < 1 << 17:    # not NaN
        _SHOWN[value] = out
    return out


def _decoder(table: str, fields: tuple[str, ...] | None):
    key = (table, fields)
    fn = _DECODERS.get(key)
    if fn is None:
        fn = _DECODERS[key] = _compile(table, fields) or (lambda raw: _decode_slow(table, raw, fields))
    return fn


def _compile(table: str, fields: tuple[str, ...] | None):
    """A function `raw -> {field: value}`, the same as `_decode_slow`; None when the layout's numbers overlap in a way one
    struct format cannot read (never in the game's layouts, checked by a test)."""
    layout = LAYOUTS[table]
    names = list(fields or layout["fields"])
    units: dict[tuple[int, str], tuple[int, int]] = {}            # (offset, type) -> (count, bytes): what one unpack reads
    for name in names:
        ftype, off, size, _bpos, _bits, arr = layout["fields"][name]
        if ftype not in ("fixstr", "fixstrW"):
            units[(off, ftype)] = (arr if arr > 1 else 1, size if arr > 1 else struct.calcsize(_FMT[ftype]))
    fmt, pos, index, values = ["<"], 0, {}, 0
    for (off, ftype), (count, size) in sorted(units.items()):
        if off < pos:
            return None
        if off > pos:
            fmt.append(f"{off - pos}x")
        fmt.append(f"{count}{_FMT[ftype][1]}")
        index[(off, ftype)], values, pos = values, values + count, off + size
    if pos > layout["size"]:
        return None
    if pos < layout["size"]:
        fmt.append(f"{layout['size'] - pos}x")
    parts = []
    for name in names:
        ftype, off, size, bpos, bits, arr = layout["fields"][name]
        if ftype in ("fixstr", "fixstrW"):
            enc = "utf-16-le" if ftype == "fixstrW" else "ascii"
            expr = f"raw[{off}:{off + size}].decode({enc!r}, 'replace').split('\\0')[0]"
        else:
            i = index[(off, ftype)]
            one = (lambda j: f"(_s[x] if (x := v[{j}]) in _s else _f(x))") if ftype == "f32" else (lambda j: f"v[{j}]")
            if arr > 1:
                expr = "[" + ", ".join(one(i + k) for k in range(arr)) + "]"
            elif bits:
                expr = f"(v[{i}] >> {bpos}) & {(1 << bits) - 1}"
            else:
                expr = one(i)
        parts.append(f"{name!r}: {expr}")
    source = "def decode(raw):\n    v = _unpack(raw)\n    return {" + ", ".join(parts) + "}\n"
    scope = {"_unpack": struct.Struct("".join(fmt)).unpack, "_f": _f32, "_s": _SHOWN}
    exec(compile(source, f"<decoder of {table}>", "exec"), scope)      # the source is made from LAYOUTS only
    return scope["decode"]


def pick(row: dict, pattern: str | None) -> dict:
    """The fields of `row` whose name matches `pattern` (letter case does not matter; `*` and `?` work); all for None."""
    if pattern is None:
        return row
    want = pattern.lower()
    hits = {k: v for k, v in row.items() if fnmatchcase(k.lower(), want)}
    if not hits:
        raise ParamNameError(f"no field of this row matches {pattern!r}")
    return hits


def row_size_of(offsets: list[int]) -> int | None:
    """The row size: the most common gap between consecutive row data offsets (None if there are not enough rows).
    Not the gcd: a row a build added sits in front of the old data, and one such offset would break a gcd."""
    ordered = sorted(set(offsets))
    gaps = Counter(b - a for a, b in zip(ordered, ordered[1:]))
    return gaps.most_common(1)[0][0] if gaps else None


# ---- which table a file in memory is ----------------------------------------------------------------------------
@dataclass
class Seen:
    """A param file found at slot `slot` of the list: what it says of itself, and the table it was named as (or why not)."""
    slot: int
    head: int
    ptype: str
    rows: int
    stride: int | None
    first: int | None
    last: int | None
    table: str | None = None
    why: str = ""
    candidates: list[str] = field(default_factory=list)


def candidates_of(ptype: str, rows: int, stride: int | None, first: int | None, last: int | None) -> list[str]:
    """The tables a file of this type and these rows may be: the type, the rows (a build adds up to MAX_EXTRA), the row size, then
    the first and last row id when that narrows it down (a grown table has another last id)."""
    hits = [n for n, v in LAYOUTS.items() if v["type"] == ptype and 0 <= rows - v["rows"] <= MAX_EXTRA
            and (stride is None or rows < 2 or v["stride"] == stride)]
    if len(hits) > 1:
        same = [n for n in hits if LAYOUTS[n]["rows"] == rows and LAYOUTS[n]["first"] == first and LAYOUTS[n]["last"] == last]
        hits = same or hits
    return hits


# ---- the running game ---------------------------------------------------------------------------------------------
class Tables:
    def __init__(self, mem, profile, module_base: int):
        if profile.params is None or not (profile.params.catalog or profile.params.repository):
            raise ParamError("this exe version has no params.catalog or params.repository in offsets.json (run `probe`)")
        self.store = ParamStore(mem, profile, module_base)
        self.mem, self.base = mem, module_base
        self.catalog = dict(profile.params.catalog)
        self.repository = profile.params.repository
        self._seen: list[Seen] | None = None
        self._slot_of: dict[str, int] = {}     # table -> its slot of the list (from the walk)
        self._walked_at = -1e9
        self._index: dict = {}         # table -> (head, count, data start, {row id: descriptor number}): see row_address

    # -- every table ---------------------------------------------------------------------------------------------
    def found(self) -> list[Seen]:
        """Every slot of the list that ends in a param file, with the table it is (walked once per object; about 200 small reads)."""
        now = time.monotonic()
        if self._seen is None or (not self._seen and now - self._walked_at >= WALK_AGAIN_S):   # none yet, or none loaded at the last walk
            self._seen, self._walked_at = (self._walk() if self.repository is not None else []), now
            self._slot_of = {s.table: s.slot for s in self._seen if s.table}
        return self._seen

    def _walk(self) -> list[Seen]:
        lay = self.store.spec.layout
        out: list[Seen] = []
        for n in range(self.repository.slots):
            head, _why = self.store._follow(None, self.repository.chain(n))
            if head is None:
                continue
            info, _why = self.store._check_head(head)
            if info is None:
                continue
            count = info[0]
            ptype = self._type_of(head)
            if ptype is None:
                continue
            raw = self.mem.read(head + lay.descriptors, min(count, SAMPLE_ROWS) * lay.descriptor_size)
            last_raw = self.mem.read(head + lay.descriptors + (count - 1) * lay.descriptor_size, lay.descriptor_size)
            if raw is None or last_raw is None:
                continue
            n_read = len(raw) // lay.descriptor_size
            ids = [struct.unpack_from("<i", raw, i * lay.descriptor_size + lay.descriptor_id)[0] for i in range(n_read)]
            offs = [struct.unpack_from("<Q", raw, i * lay.descriptor_size + lay.descriptor_data_offset)[0] for i in range(n_read)]
            seen = Seen(n, head, ptype, count, row_size_of(offs), ids[0] if ids else None,
                        struct.unpack_from("<i", last_raw, lay.descriptor_id)[0])
            seen.candidates = candidates_of(ptype, count, seen.stride, seen.first, seen.last)
            out.append(seen)
        self._name(out)
        return out

    def _type_of(self, head: int) -> str | None:
        raw = self.mem.read(head + TYPE_AT, 8)
        if raw is None:
            return None
        off = struct.unpack("<Q", raw)[0]
        if not 0 < off < 1 << 26:
            return None
        text = self.mem.read(head + off, 64)
        if text is None or b"\0" not in text:
            return None
        name = text.split(b"\0", 1)[0]
        return name.decode("ascii") if name and all(32 < c < 127 for c in name) else None

    def _name(self, out: list[Seen]) -> None:
        """Give every file its table: alone of its kind; else by the digest of its rows; else by the name next to its slot."""
        for s in out:
            if len(s.candidates) == 1:
                s.table = s.candidates[0]
            elif not s.candidates:
                s.why = f"no table of type {s.ptype} with {s.rows} rows"
        for s in [s for s in out if len(s.candidates) > 1]:
            digest = self._digest(s)
            hits = [n for n in s.candidates if LAYOUTS[n].get("digest") and LAYOUTS[n]["digest"] == digest]
            if len(hits) != 1:
                hits = self._named_next_to_slot(s)
            if len(hits) == 1:
                s.table = hits[0]
            else:
                s.why = f"fits {', '.join(s.candidates)}: they cannot be told apart in memory"
        taken: dict[str, Seen] = {}
        for s in out:
            if s.table is None:
                continue
            if s.table in taken:                  # the same table twice: neither is trusted
                taken[s.table].why = s.why = f"two slots look like {s.table}"
                taken[s.table].table = None
                s.table = None
                continue
            taken[s.table] = s

    def _digest(self, s: Seen) -> str | None:
        if s.stride is None or s.rows < 2 or s.rows * s.stride > 1 << 16:
            return None
        lay = self.store.spec.layout
        raw = self.mem.read(s.head + lay.descriptors, s.rows * lay.descriptor_size)
        if raw is None:
            return None
        offs = [struct.unpack_from("<Q", raw, i * lay.descriptor_size + lay.descriptor_data_offset)[0] for i in range(s.rows)]
        lo, hi = min(offs), max(offs) + s.stride
        blob = self.mem.read(s.head + lo, hi - lo)
        if blob is None:
            return None
        return hashlib.sha256(b"".join(blob[o - lo:o - lo + s.stride] for o in offs)).hexdigest()[:16]

    def _near_slot(self, s: Seen) -> list[bytes]:
        """The bytes of the slot's object and of what each pointer in it points to (where the game may keep the table's name)."""
        obj = read_ptr(self.mem, self.base + self.repository.rva)
        slot = read_ptr(self.mem, obj + self.repository.first + s.slot * self.repository.stride) if obj else None
        if not slot or not is_user_ptr(slot):
            return []
        raw = self.mem.read(slot, NAME_SPAN) or b""
        texts = [raw]
        for i in range(0, len(raw) - 7, 8):
            p = struct.unpack_from("<Q", raw, i)[0]
            if is_user_ptr(p):
                texts.append(self.mem.read(p, 128) or b"")
        return texts

    def _named_next_to_slot(self, s: Seen) -> list[str]:
        """[the slot's own name] when it is one of the candidates: the first text next to the slot that is the name of a table of
        the game (UTF-16, as the game keeps resource names). The names of the slots around it come after it (the probe in the game,
        2026-10-15: slot 94 reads `..._ps4, ..., ..._ps5`, slot 95 `..._ps5, ..., ..._xb1`), so any name but the first is a
        neighbour's."""
        own = next((t for t in self.texts_next_to_slot(s) if t in LAYOUTS), None)
        return [own] if own in s.candidates else []

    def texts_next_to_slot(self, s: Seen) -> list[str]:
        """Every UTF-16 text of 4 letters or more next to the slot, in the order found (for `probe`: where the names are)."""
        out: list[str] = []
        for raw in self._near_slot(s):
            for m in _UTF16.finditer(raw):
                text = m.group().decode("utf-16-le")
                if text not in out:
                    out.append(text)
        return out

    def chain_of(self, table: str):
        """The chain to `table`'s file: the measured one of `catalog`, else the slot of the list it was found at."""
        table = table_name(table)
        chain = self.catalog.get(table)
        if chain is not None:
            return chain
        self.found()
        if table in self._slot_of:
            return self.repository.chain(self._slot_of[table])
        why = next((s.why for s in self.found() if table in s.candidates and s.why), None)
        if why is None and self.repository is None:
            why = "no params.repository in offsets.json"
        raise ParamError(f"{table} not found in the game's memory" + (f" ({why})" if why else ""))

    def index(self) -> dict[str, dict]:
        """{table: {"rows": n}} of every table found (the document's `params` before a table is named), in the order of the game's file."""
        out: dict[str, dict] = {}
        self.found()
        for table in LAYOUTS:
            if table not in self.catalog and table not in self._slot_of:
                continue
            try:
                _head, count, _data = self._head(table)
            except ParamError:
                continue
            out[table] = {"rows": count}
        return out

    # -- one table -----------------------------------------------------------------------------------------------
    def _head(self, table: str) -> tuple[int, int, int]:
        """(head, row count, data start) of `table`: the chain followed again and the file's header checked, every time."""
        chain = self.chain_of(table)
        head, reason = self.store._follow(None, chain)
        if head is None:
            raise ParamError(f"{table} not found ({reason})")
        info, reason = self.store._check_head(head)
        if info is None:
            raise ParamError(f"{table} not found ({reason})")
        return head, info[0], info[1]

    def locate(self, table: str) -> tuple[int, int, int, bytes]:
        """(head, row count, data start, the descriptor table) of `table`, after the file and row-size checks."""
        table = table_name(table)
        head, count, data_start = self._head(table)
        lay = self.store.spec.layout
        raw = self.mem.read(head + lay.descriptors, count * lay.descriptor_size)
        if raw is None:
            raise ParamError(f"{table}: the row table is unreadable")
        offs = [struct.unpack_from("<Q", raw, i * lay.descriptor_size + lay.descriptor_data_offset)[0]
                for i in range(min(count, SAMPLE_ROWS))]
        size = row_size_of(offs)
        if size is not None and size != LAYOUTS[table]["stride"]:
            raise ParamError(f"{table}: the file's rows are {size} bytes, the layout says {LAYOUTS[table]['stride']}: "
                             "wrong table or another game version")
        return head, count, data_start, raw

    def ids(self, table: str) -> list[int]:
        """The row ids of `table`, in the file's order."""
        _head, count, _data, raw = self.locate(table)
        lay = self.store.spec.layout
        return [struct.unpack_from("<I", raw, i * lay.descriptor_size + lay.descriptor_id)[0] for i in range(count)]

    def _check_offset(self, table: str, row_id: int, off: int, count: int, data_start: int, head: int = 0) -> None:
        """The descriptor of a row must point to a row-sized slot in the gap (a row a design added), in the old data, or, for a
        table a design grew at its END (AtkParam_Pc: the descriptors grew into the front of the data, the first rows were copied
        behind the strings), in the old data counted back from the strings or in the rows behind the strings."""
        lay, size = self.store.spec.layout, LAYOUTS[table]["stride"]
        first = lay.descriptors + count * lay.descriptor_size
        in_gap = first <= off and off + size <= data_start
        in_data = off >= data_start and (off - data_start) % size == 0 and off + size <= data_start + count * size
        strings = self._strings_off(head) if head and not (in_gap or in_data) else 0
        in_old = strings > first and first <= off and off + size <= strings and (strings - off) % size == 0
        behind = strings > first and strings <= off <= strings + MAX_BEHIND and off % 4 == 0
        if not (in_gap or in_data or in_old or behind):
            raise ParamError(f"{table}: row {row_id} points outside the data (offset {off})")

    def _strings_off(self, head: int) -> int:
        raw = self.mem.read(head, 4)
        return struct.unpack("<I", raw)[0] if raw else 0

    def _need_fields(self, table: str) -> int:
        if not has_fields(table):
            raise ParamError(f"{table}: its rows cannot be decoded ({LAYOUTS[table]['why']})")
        return LAYOUTS[table]["size"]

    def row_address(self, table: str, row_id: int) -> tuple[int, bytes]:
        """(address of the row, its bytes). The chain and the header are checked every time; the whole descriptor table (hundreds of
        KB for SpEffect) is read only the first time and when the table changed (another head, another row count): after that, ONE
        descriptor, the row's own, is read and must still name the row (1.7.2: the scripts read a few rows several times a second)."""
        table = table_name(table)
        size = self._need_fields(table)
        lay = self.store.spec.layout
        head, count, data_start = self._head(table)
        known = self._index.get(table)
        off = None
        if known is not None and known[:3] == (head, count, data_start) and row_id in known[3]:
            i = known[3][row_id]
            one = self.mem.read(head + lay.descriptors + i * lay.descriptor_size, lay.descriptor_size)
            if one is not None and struct.unpack_from("<I", one, lay.descriptor_id)[0] == row_id:
                off = struct.unpack_from("<Q", one, lay.descriptor_data_offset)[0]
        if off is None:
            head, count, data_start, raw = self.locate(table)
            ids = {}
            for i in range(count):
                rid = struct.unpack_from("<I", raw, i * lay.descriptor_size + lay.descriptor_id)[0]
                ids.setdefault(rid, i)
            self._index[table] = (head, count, data_start, ids)
            if row_id not in ids:
                raise ParamError(f"{table}: row {row_id} is not in the file")
            off = struct.unpack_from("<Q", raw, ids[row_id] * lay.descriptor_size + lay.descriptor_data_offset)[0]
        self._check_offset(table, row_id, off, count, data_start, head)
        data = self.mem.read(head + off, size)
        if data is None:
            raise ParamError(f"{table}: row {row_id} is unreadable")
        return head + off, data

    def all_rows(self, table: str, raw: bool = False) -> dict[int, bytes]:
        """{row id: the row's bytes} of the whole table, read in a few big pieces (checked like `row_address`). `raw`: the whole
        step of each row, for a table no layout decodes too (`export --params`)."""
        table = table_name(table)
        size = LAYOUTS[table]["stride"] if raw else self._need_fields(table)
        head, count, data_start, raw = self.locate(table)
        lay = self.store.spec.layout
        offs: dict[int, int] = {}
        for i in range(count):
            base = i * lay.descriptor_size
            rid = struct.unpack_from("<I", raw, base + lay.descriptor_id)[0]
            off = struct.unpack_from("<Q", raw, base + lay.descriptor_data_offset)[0]
            self._check_offset(table, rid, off, count, data_start, head)
            offs[rid] = off
        if not offs:
            return {}
        lo, hi = min(offs.values()), max(offs.values()) + size
        blob = bytearray()
        for start in range(lo, hi, READ_CHUNK):
            piece = self.mem.read(head + start, min(READ_CHUNK, hi - start))
            if piece is None:
                raise ParamError(f"{table}: the data is unreadable at offset {start}")
            blob += piece
        return {rid: bytes(blob[off - lo:off - lo + size]) for rid, off in offs.items()}

    def read_row(self, table: str, row_id: int) -> dict:
        return decode_row(table, self.row_address(table, row_id)[1])

    def read_table(self, table: str, pattern: str | None = None) -> dict[int, dict]:
        """{row id: {field: value}} of every row of `table`; with `pattern`, only the fields it matches (only they are decoded)."""
        table = table_name(table)
        fields = None
        if pattern is not None:
            self._need_fields(table)
            fields = fields_like(table, pattern)
            if not fields:
                raise ParamNameError(f"no field of {table} matches {pattern!r}")
        return {rid: decode_row(table, raw, fields) for rid, raw in self.all_rows(table).items()}

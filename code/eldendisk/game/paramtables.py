"""Any row of the six workbench tables, any field by name (`read --param Magic.6230`). Read-only.

The field layouts are Paramdex's (`paramlayouts.py`, generated); where a table's file is comes from `params.catalog` in
offsets.json (found with `probe`). The same decoder serves a row from the running game and a row from a
regulation.bin file (`decode_row` takes the row's bytes), so the two can be compared field for field.

Correct-or-silent, like `params.py`: the file header must pass the same checks, the row size found in the file must be the
layout's, and a row is read only when its descriptor points inside the file. One failed check stops the read.
"""
from __future__ import annotations

import struct
from fnmatch import fnmatchcase

from .paramlayouts import LAYOUTS
from .params import ParamError, ParamNameError, ParamStore, shown
from .probe import row_size_of

ROOT = "params"
SAMPLE_ROWS = 512
READ_CHUNK = 1 << 20      # bytes per read of a whole table
MAX_BEHIND = 4 << 20      # how far behind the strings a row of a table grown at its end may lie
UNIT_FORMATS = _FMT = {"s8": "<b", "u8": "<B", "s16": "<h", "u16": "<H", "s32": "<i", "u32": "<I", "f32": "<f", "b32": "<i"}

# what a person may type for a table: the workbench name, the game's own name, the Paramdex name (any letter case)
_ALIASES = {"equipparamgoods": "Goods", "magicparam": "Magic", "speffectparam": "SpEffect", "bulletparam": "Bullet",
            "atkparam": "AtkParam_Pc", "atkpc": "AtkParam_Pc", "shoplineupparam": "ShopLineup"}
TABLES = {**{name.lower(): name for name in LAYOUTS}, **_ALIASES, **{v["param"].lower(): k for k, v in LAYOUTS.items()}}


def table_name(text: str) -> str:
    """The workbench name of a table as typed (`magic`, `MagicParam`, `Magic`)."""
    name = TABLES.get(text.strip().lower())
    if name is None:
        raise ParamNameError(f"{text!r} is not a table of the workbench (one of {', '.join(LAYOUTS)})")
    return name


def parse_ref(text: str) -> tuple[str, int, str | None]:
    """`Magic.6230` or `params.Magic.6230.mp*` -> (table, row id, field name or pattern or None for every field)."""
    parts = text.strip().split(".")
    if parts and parts[0].lower() == ROOT:
        parts = parts[1:]
    if len(parts) < 2 or len(parts) > 3:
        raise ParamNameError(f"{text!r}: write it as Table.id or Table.id.field (for example Magic.6230.mp)")
    if not parts[1].isdigit():
        raise ParamNameError(f"{text!r}: the row id must be a number, got {parts[1]!r}")
    return table_name(parts[0]), int(parts[1]), (parts[2] if len(parts) == 3 else None)


# ---- decoding a row ---------------------------------------------------------------------------------------------
def _one(ftype: str, raw: bytes, off: int, bpos: int, bits: int):
    value = struct.unpack_from(_FMT[ftype], raw, off)[0]
    if ftype == "f32":
        return shown(value)
    return (value >> bpos) & ((1 << bits) - 1) if bits else value


def decode_row(table: str, raw: bytes) -> dict:
    """{field: value} in the order of the layout; a field that is an array is a list; padding is not listed."""
    layout = LAYOUTS[table]
    if len(raw) != layout["size"]:
        raise ParamError(f"{table}: a row is {layout['size']} bytes, got {len(raw)}")
    out: dict = {}
    for name, (ftype, off, size, bpos, bits, arr) in layout["fields"].items():
        if ftype in ("fixstr", "fixstrW"):
            out[name] = raw[off:off + size].decode("utf-16-le" if ftype == "fixstrW" else "ascii", "replace").split("\0")[0]
        elif arr > 1:
            width = size // arr
            out[name] = [_one(ftype, raw, off + i * width, 0, 0) for i in range(arr)]
        else:
            out[name] = _one(ftype, raw, off, bpos, bits)
    return out


def pick(row: dict, pattern: str | None) -> dict:
    """The fields of `row` whose name matches `pattern` (letter case does not matter; `*` and `?` work); all for None."""
    if pattern is None:
        return row
    want = pattern.lower()
    hits = {k: v for k, v in row.items() if fnmatchcase(k.lower(), want)}
    if not hits:
        raise ParamNameError(f"no field of this row matches {pattern!r}")
    return hits


# ---- the running game ---------------------------------------------------------------------------------------------
class Tables:
    def __init__(self, mem, profile, module_base: int):
        if profile.params is None or not profile.params.catalog:
            raise ParamError("this exe version has no params.catalog in offsets.json (run `probe`)")
        self.store = ParamStore(mem, profile, module_base)
        self.mem, self.catalog = mem, profile.params.catalog
        self._index: dict = {}         # table -> (head, count, data start, {row id: descriptor number}): see row_address

    def _head(self, table: str) -> tuple[int, int, int]:
        """(head, row count, data start) of `table`: the chain followed again and the file's header checked, every time."""
        chain = self.catalog.get(table)
        if chain is None:
            raise ParamError(f"{table}: no chain in params.catalog")
        head, reason = self.store._follow(None, chain)
        if head is None:
            raise ParamError(f"{table} not found ({reason})")
        info, reason = self.store._check_head(head)
        if info is None:
            raise ParamError(f"{table} not found ({reason})")
        return head, info[0], info[1]

    def locate(self, table: str) -> tuple[int, int, int, bytes]:
        """(head, row count, data start, the descriptor table) of `table`, after the file and row-size checks."""
        head, count, data_start = self._head(table)
        lay = self.store.spec.layout
        raw = self.mem.read(head + lay.descriptors, count * lay.descriptor_size)
        if raw is None:
            raise ParamError(f"{table}: the row table is unreadable")
        offs = [struct.unpack_from("<Q", raw, i * lay.descriptor_size + lay.descriptor_data_offset)[0]
                for i in range(min(count, SAMPLE_ROWS))]
        size = row_size_of(offs)
        if size is not None and size != LAYOUTS[table]["size"]:
            raise ParamError(f"{table}: the file's rows are {size} bytes, the layout says {LAYOUTS[table]['size']}: "
                             "wrong table or another game version")
        return head, count, data_start, raw

    def _check_offset(self, table: str, row_id: int, off: int, count: int, data_start: int, head: int = 0) -> None:
        """The descriptor of a row must point to a row-sized slot in the gap (a row a design added), in the old data, or, for a
        table a design grew at its END (AtkParam_Pc: the descriptors grew into the front of the data, the first rows were copied
        behind the strings), in the old data counted back from the strings or in the rows behind the strings."""
        lay, size = self.store.spec.layout, LAYOUTS[table]["size"]
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

    def row_address(self, table: str, row_id: int) -> tuple[int, bytes]:
        """(address of the row, its bytes). The chain and the header are checked every time; the whole descriptor table (hundreds of
        KB for SpEffect) is read only the first time and when the table changed (another head, another row count): after that, ONE
        descriptor, the row's own, is read and must still name the row (1.7.2: the scripts read a few rows several times a second)."""
        lay, size = self.store.spec.layout, LAYOUTS[table]["size"]
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

    def all_rows(self, table: str) -> dict[int, bytes]:
        """{row id: the row's bytes} of the whole table, read in a few big pieces (checked like `row_address`)."""
        head, count, data_start, raw = self.locate(table)
        lay, size = self.store.spec.layout, LAYOUTS[table]["size"]
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

"""`probe`: where are the param files of the other tables in the game's memory? (read-only)

The profile holds three pointer chains to SpEffectParam. Each is `exe + rva -> [selector] -> tail...`; the first step
after the global (the selector) is a slot in an object that holds one entry per table, the tail is the same for every
entry. This probe keeps the global and the tail of each known chain, tries every 8-byte slot of the object as the
selector, and keeps the ones that end in a valid param file (the same header check the reader uses). It then names a
file by its row size and row count when they match one of the tables we need, and prints a chain in the format of
`offsets.json` for every hit.

Nothing is written, nothing is cached; one failed read only means "not a hit". The result is a list to read, not a
setting: a chain goes into the profile only after the author has seen it work (spec 1.6.3).
"""
from __future__ import annotations

import struct
from collections import Counter
from dataclasses import dataclass, field

from .memory import is_user_ptr, read_ptr
from .params import MAX_ROWS, ParamStore

SCAN_SPAN = 0x4000       # bytes of the object that holds the entries, from its start
CHUNK = 0x1000
SAMPLE_ROWS = 512        # descriptors read to find the row size

# The tables Phase 1 needs: name -> (row size, rows in the original 1.17.1 file). A file that a design grew has up to
# MAX_EXTRA rows more.
WANTED = {
    "EquipParamGoods": (176, 2329), "Magic": (168, 317), "ShopLineupParam": (52, 1296),
    "SpEffectParam": (912, 11354), "BulletParam": (272, 15475), "AtkParam_Pc": (456, 11017),
}
MAX_EXTRA = 200


@dataclass
class Hit:
    root_rva: int
    slot: int                   # the selector: offset in the object that the global points to
    tail: tuple[int, ...]
    head: int
    count: int
    data_start: int
    gap: int
    first_ids: list[int]
    row_size: int | None
    table: str | None = None    # one of WANTED when row size and row count agree
    known: bool = False         # the slot of a chain that is already in the profile

    @property
    def chain(self) -> dict:
        return {"rva": f"0x{self.root_rva:X}", "offsets": [f"0x{o:X}" for o in (self.slot, *self.tail)]}


@dataclass
class ProbeResult:
    hits: list[Hit] = field(default_factory=list)
    roots: list[str] = field(default_factory=list)      # what happened with each root, one line each

    def of(self, table: str) -> list[Hit]:
        return [h for h in self.hits if h.table == table]


def row_size_of(offsets: list[int]) -> int | None:
    """The row size: the most common gap between consecutive row data offsets (None if there are not enough rows).
    Not the gcd: a row a design added sits in front of the old data, and one such offset would break a gcd (ShopLineup:
    its new rows have small ids, so they are among the first descriptors; the gcd came out as 4)."""
    ordered = sorted(set(offsets))
    gaps = Counter(b - a for a, b in zip(ordered, ordered[1:]))
    return gaps.most_common(1)[0][0] if gaps else None


def name_of(count: int, row_size: int | None) -> str | None:
    for name, (size, rows) in WANTED.items():
        if row_size == size and 0 <= count - rows <= MAX_EXTRA:
            return name
    return None


def _describe(store: ParamStore, head: int, info: tuple[int, int]) -> tuple[list[int], int | None]:
    lay = store.spec.layout
    count, _data_start = info
    take = min(count, SAMPLE_ROWS)
    raw = store.mem.read(head + lay.descriptors, take * lay.descriptor_size)
    if raw is None:
        return [], None
    ids, offs = [], []
    for i in range(take):
        base = i * lay.descriptor_size
        ids.append(struct.unpack_from("<I", raw, base + lay.descriptor_id)[0])
        offs.append(struct.unpack_from("<Q", raw, base + lay.descriptor_data_offset)[0])
    return ids, row_size_of(offs)


def _slots(mem, obj: int, span: int):
    """(offset, pointer value) for every 8-byte slot of `obj` that holds a user pointer; unreadable chunks are skipped."""
    for start in range(0, span, CHUNK):
        raw = mem.read(obj + start, min(CHUNK, span - start))
        if raw is None:
            continue
        for i in range(0, len(raw) - 7, 8):
            value = struct.unpack_from("<Q", raw, i)[0]
            if is_user_ptr(value):
                yield start + i, value


def probe(store: ParamStore, span: int = SCAN_SPAN) -> ProbeResult:
    """Try every slot of the object behind each known chain's global; see the module doc."""
    result = ProbeResult()
    seen: set[tuple[int, int, tuple[int, ...]]] = set()
    chains = [c for t in store.spec.tables.values() for c in t.chains]
    for chain in chains:
        if len(chain.offsets) < 2:
            result.roots.append(f"0x{chain.rva:X}: chain too short to probe")
            continue
        selector, tail = chain.offsets[0], tuple(chain.offsets[1:])
        key = (chain.rva, selector, tail)
        if key in seen:
            continue
        seen.add(key)
        obj = read_ptr(store.mem, store.base + chain.rva)
        label = f"0x{chain.rva:X} -> +0x{selector:X} -> " + " -> ".join(f"+0x{o:X}" for o in tail)
        if obj is None or not is_user_ptr(obj):
            result.roots.append(f"{label}: the global is empty or unreadable")
            continue
        found = 0
        for slot, entry in _slots(store.mem, obj, span):
            cur: int | None = entry
            for off in tail:
                if cur is None or not is_user_ptr(cur):
                    cur = None
                    break
                cur = read_ptr(store.mem, cur + off)
            if cur is None or not is_user_ptr(cur):
                continue
            info, _why = store._check_head(cur)
            if info is None:
                continue
            ids, size = _describe(store, cur, info)
            count, data_start = info
            gap = data_start - (store.spec.layout.descriptors + count * store.spec.layout.descriptor_size)
            result.hits.append(Hit(chain.rva, slot, tail, cur, count, data_start, gap, ids[:3], size,
                                   name_of(count, size), known=slot == selector))
            found += 1
        result.roots.append(f"{label}: {found} param file(s) in the first 0x{span:X} bytes of the object")
    return result


def as_json(result: ProbeResult) -> dict:
    return {"roots": result.roots,
            "hits": [{"table": h.table, "chain": h.chain, "known": h.known, "rows": h.count, "row_size": h.row_size,
                      "gap": h.gap, "first_ids": h.first_ids, "head": f"0x{h.head:X}"} for h in result.hits]}


def lines(result: ProbeResult) -> list[str]:
    """The text the author reads (and pastes back)."""
    out = ["probe: where the param files are (read-only)", ""]
    out += [f"  {r}" for r in result.roots]
    out += ["", "tables we need:"]
    for name, (size, rows) in WANTED.items():
        hits = result.of(name)
        if not hits:
            out.append(f"  {name:<16} not found (row size {size}, about {rows} rows)")
            continue
        for h in hits:
            tag = " (already in the profile)" if h.known else ""
            out.append(f"  {name:<16} {h.count} rows, row size {h.row_size}, gap {h.gap}, first ids {h.first_ids}{tag}")
            out.append(f"      chain: {h.chain}")
    others = [h for h in result.hits if h.table is None]
    out += ["", f"other param files found ({len(others)}), by slot:"]
    for h in sorted(others, key=lambda x: (x.root_rva, x.slot)):
        out.append(f"  0x{h.root_rva:X} +0x{h.slot:X}: {h.count} rows, row size {h.row_size}, first ids {h.first_ids}")
    return out

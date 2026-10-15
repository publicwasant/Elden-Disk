"""`probe inventory`: where is the inventory in the game's memory? (1.8.1, spec section 4; read-only)

The inventory lives in `PlayerGameData` (the object the magic slots are read from), inline or behind a pointer; the size of an entry and
where the item id and the quantity are in it are not known for 1.17.1. This probe reads `PlayerGameData` and the objects its pointers
lead to (two levels) and looks for runs of same-sized entries in which a 32-bit value is a goods item (the goods kind in its top four
bits, the rest the id of an `EquipParamGoods` row of the running game) and another is a plausible quantity. Each run is printed with
where it is, the entry size, the place of the id and of the quantity, and its first entries, for the author to compare with the
Inventory menu. Nothing is written; a read that fails only means "not here".
"""
from __future__ import annotations

import struct
from collections import Counter
from dataclasses import dataclass, field

from .memory import is_user_ptr

GD_SPAN = 0x8000           # bytes of PlayerGameData looked through (the first GD_PTRS of them for pointers to follow)
GD_PTRS = 0x2000
OBJ_SPAN = 0x10000         # bytes of an object a pointer of PlayerGameData leads to
INNER_SPAN = 0x8000        # bytes of an object one level further
INNER_PTRS = 0x100         # bytes of a level-1 object looked through for pointers to follow
CHUNK = 0x1000
BUDGET = 256 << 20         # bytes read at most
STRIDES = (8, 12, 16, 20, 24, 32)
MIN_RUN = 6                # goods entries in a row for a run to count
MAX_GAP = 4                # entries that are not goods (empty places, other kinds) a run may step over
QTY_MAX = 999

# The kind of an item, from the top four bits of its id as the game's item tables use them, and of a handle (the save file's form).
ID_KINDS = {0x0: "weapon", 0x1: "armor", 0x2: "talisman", 0x4: "goods", 0x8: "ash_of_war"}
HANDLE_KINDS = {0x8: "weapon", 0x9: "armor", 0xA: "talisman", 0xB: "goods", 0xC: "ash_of_war"}
GOODS_TOPS = {0x4: "item id", 0xB: "handle"}


@dataclass
class Run:
    where: str                 # how the place was reached: `PlayerGameData+0x5D0`, `[PlayerGameData+0x5D8]+0x40` ...
    address: int
    stride: int
    form: str                  # "item id" (0x4.......) or "handle" (0xB.......)
    qty_at: int | None
    entries: int               # entries from the first goods entry to the last
    goods: int                 # of them goods
    kinds: dict = field(default_factory=dict)     # top four bits -> entries, over the whole run
    first: list = field(default_factory=list)     # (id, quantity) of the first goods entries
    dump: list = field(default_factory=list)      # the bytes around the first goods entries, as 32-bit words (the id in [ ])


# The entry measured in the game (2026-10-15, the second probe): 24 bytes, the handle, the item id, the quantity, the place in the menu,
# then two words. The handle's kind (top four bits) and the id's agree; for goods and talismans the rest of the two is the same number.
ENTRY = 24
HANDLE_TO_ID = {0x8: 0x0, 0x9: 0x1, 0xA: 0x2, 0xB: 0x4, 0xC: 0x8}


def entry_ok(raw: bytes, o: int) -> bool:
    if o < 0 or o + 12 > len(raw):
        return False
    h, i, q = struct.unpack_from("<III", raw, o)
    kind = HANDLE_TO_ID.get(h >> 28)
    if kind is None or i >> 28 != kind or q > QTY_MAX:
        return False
    return kind not in (0x2, 0x4) or h & 0x0FFFFFFF == i & 0x0FFFFFFF


@dataclass
class Table:
    """A list of 24-byte entries (handle, id, quantity, place ...) found in memory."""
    where: str
    address: int                # of the first entry that passes
    first: int                  # its offset in the place `where` names
    entries: int                # entries that pass
    span: int                   # entries from the first that passes to the last
    kinds: dict
    head: str                   # the words in front of the first entry (a header: a pointer, a capacity ...)
    asked: list = field(default_factory=list)     # (id, quantity) of the ids `--find` asked for, in this list


@dataclass
class InventoryProbe:
    game_data: int | None
    why: str = ""
    runs: list[Run] = field(default_factory=list)
    read_bytes: int = 0
    found: list = field(default_factory=list)     # `--find`: (id, where, address, words around it) of every place an id is
    tables: list = field(default_factory=list)    # lists of 24-byte entries (Table)


class _Reader:
    def __init__(self, mem):
        self.mem, self.total = mem, 0

    def span(self, addr: int, size: int) -> bytes:
        """Up to `size` bytes from `addr`, stopping at the first chunk that cannot be read."""
        out = bytearray()
        for start in range(0, size, CHUNK):
            if self.total >= BUDGET:
                break
            raw = self.mem.read(addr + start, min(CHUNK, size - start))
            if raw is None:
                break
            out += raw
            self.total += len(raw)
        return bytes(out)


def _pointers(raw: bytes) -> list[tuple[int, int]]:
    return [(i, v) for i in range(0, len(raw) - 7, 8) for v in [struct.unpack_from("<Q", raw, i)[0]] if is_user_ptr(v)]


def regions(mem, game_data: int, reader: _Reader | None = None):
    """(label, address, bytes) of PlayerGameData, of what its pointers lead to, and one level further."""
    reader = reader or _Reader(mem)
    gd = reader.span(game_data, GD_SPAN)
    yield "PlayerGameData", game_data, gd
    seen = {game_data}
    for off, p in _pointers(gd[:GD_PTRS]):
        if p in seen:
            continue
        seen.add(p)
        raw = reader.span(p, OBJ_SPAN)
        if not raw:
            continue
        label = f"[PlayerGameData+0x{off:X}]"
        yield label, p, raw
        for off2, q in _pointers(raw[:INNER_PTRS]):
            if q in seen:
                continue
            seen.add(q)
            inner = reader.span(q, INNER_SPAN)
            if inner:
                yield f"[{label}+0x{off2:X}]", q, inner


def find_runs(raw: bytes, goods_ids: set[int]) -> list[tuple[int, int, int, str]]:
    """(start offset, stride, id offset, form) of every run of goods entries in `raw` (a goods id every `stride` bytes, gaps allowed)."""
    hits: dict[int, int] = {}
    for i in range(0, len(raw) - 3, 4):
        v = struct.unpack_from("<I", raw, i)[0]
        if v >> 28 in GOODS_TOPS and v & 0x0FFFFFFF in goods_ids:
            hits[i] = v >> 28
    out, used = [], set()
    for stride in STRIDES:
        for i in sorted(hits):
            if (i, stride) in used:
                continue
            j, n, gap, last = i, 0, 0, i
            while gap <= MAX_GAP and j < len(raw):
                if j in hits and hits[j] == hits[i]:
                    n, gap, last = n + 1, 0, j
                    used.add((j, stride))
                else:
                    gap += 1
                j += stride
            if n >= MIN_RUN:
                out.append((i, stride, last, GOODS_TOPS[hits[i]]))
    # a run inside another one (a stride that is a multiple of its stride, on the same entries) is the same list: dropped
    keep = []
    for run in sorted(out, key=lambda r: (r[1], r[0])):
        start, stride, last, _form = run
        if not any(s2 <= start and last <= l2 and stride % st2 == 0 and (start - s2) % st2 == 0 for s2, st2, l2, _f in keep):
            keep.append(run)
    return sorted(keep)


def describe(raw: bytes, start: int, stride: int, last: int, goods_ids: set[int]) -> tuple[int | None, int, Counter, list]:
    """(offset of the quantity in an entry, goods entries, kinds over the run, first goods entries) of a run whose id is at `start`."""
    entries = [start + k * stride for k in range((last - start) // stride + 1)]
    goods = [e for e in entries if struct.unpack_from("<I", raw, e)[0] >> 28 in GOODS_TOPS
             and struct.unpack_from("<I", raw, e)[0] & 0x0FFFFFFF in goods_ids]
    best, best_n = None, 0
    for d in range(-stride + 4, stride, 4):
        if d == 0:
            continue
        ok = 0
        for e in goods:
            if 0 <= e + d <= len(raw) - 4 and 1 <= struct.unpack_from("<I", raw, e + d)[0] <= QTY_MAX:
                ok += 1
        if ok > best_n:
            best, best_n = d, ok
    if best is not None and best_n < 0.9 * len(goods):
        best = None
    kinds = Counter(struct.unpack_from("<I", raw, e)[0] >> 28 for e in entries)
    first = [(struct.unpack_from("<I", raw, e)[0] & 0x0FFFFFFF,
              struct.unpack_from("<I", raw, e + best)[0] if best is not None else None) for e in goods[:12]]
    return best, len(goods), kinds, first


def words_around(raw: bytes, at: int, before: int = 4, after: int = 6) -> str:
    """The 32-bit words around offset `at` (the word at `at` in [ ]), for the author to see an entry's layout."""
    out = []
    for k in range(-before, after):
        o = at + 4 * k
        if 0 <= o <= len(raw) - 4:
            w = f"{struct.unpack_from('<I', raw, o)[0]:08X}"
            out.append(f"[{w}]" if k == 0 else w)
    return " ".join(out)


def find_tables(raw: bytes, label: str, base: int, find: tuple[int, ...] = ()) -> list[Table]:
    """Every run of entries that pass `entry_ok`, ENTRY bytes apart (empty places between them allowed), of 6 entries or more."""
    groups: dict[int, list[int]] = {}
    for o in range(0, len(raw) - 11, 4):
        if entry_ok(raw, o):
            groups.setdefault(o % ENTRY, []).append(o)
    out = []
    for offs in groups.values():
        if len(offs) < MIN_RUN:
            continue
        kinds = Counter(f"0x{struct.unpack_from('<I', raw, o + 4)[0] >> 28:X}" for o in offs)
        asked = [(struct.unpack_from("<I", raw, o + 4)[0] & 0x0FFFFFFF, struct.unpack_from("<I", raw, o + 8)[0]) for o in offs
                 if struct.unpack_from("<I", raw, o + 4)[0] & 0x0FFFFFFF in find]
        out.append(Table(label, base + offs[0], offs[0], len(offs), (offs[-1] - offs[0]) // ENTRY + 1, dict(sorted(kinds.items())),
                         words_around(raw, offs[0], before=8, after=6), asked))
    return out


def probe_inventory(mem, game_data: int | None, goods_ids: set[int], why: str = "", find: tuple[int, ...] = ()) -> InventoryProbe:
    result = InventoryProbe(game_data, why)
    if game_data is None:
        return result
    reader = _Reader(mem)
    for label, base, raw in regions(mem, game_data, reader):
        for start, stride, last, form in find_runs(raw, goods_ids):
            qty, goods, kinds, first = describe(raw, start, stride, last, goods_ids)
            where = f"{label}+0x{start:X}"        # the id of the first goods entry; the quantity's place is given relative to it
            dump = [words_around(raw, start + k * stride) for k in range(4) if start + k * stride < len(raw)]
            result.runs.append(Run(where, base + start, stride, form, qty, (last - start) // stride + 1, goods,
                                   {f"0x{k:X}": n for k, n in sorted(kinds.items())}, first, dump))
        for table in find_tables(raw, label, base, find):
            if all(t.address != table.address for t in result.tables):     # the same list reached another way
                result.tables.append(table)
        for want in find:
            for top in GOODS_TOPS:
                needle = struct.pack("<I", (top << 28) | want)
                i = raw.find(needle)
                while i != -1:
                    if i % 4 == 0:
                        result.found.append((want, f"{label}+0x{i:X}", base + i, words_around(raw, i)))
                    i = raw.find(needle, i + 1)
    result.read_bytes = reader.total
    result.runs.sort(key=lambda r: -r.goods)
    result.tables.sort(key=lambda t: -t.entries)
    return result


def lines(result: InventoryProbe, names: dict[int, str] | None = None) -> list[str]:
    names = names or {}
    out = ["probe inventory: where the inventory is (read-only)", ""]
    if result.game_data is None:
        return out + [f"  PlayerGameData not found: {result.why or 'no character in the world'}"]
    out.append(f"  PlayerGameData at 0x{result.game_data:X}; {result.read_bytes / 1048576:.1f} MB looked through")
    if not result.runs and not result.found and not result.tables:
        return out + ["  no list of goods entries found"]
    for n, r in enumerate(result.runs[:8], 1):
        qty = f"quantity at {r.qty_at:+d} from the id" if r.qty_at is not None else "no quantity found next to the id"
        out += ["", f"list {n}: {r.where} (0x{r.address:X})",
                f"  entry {r.stride} bytes, the id as {r.form}, {qty}",
                f"  {r.entries} entries from the first goods entry to the last, {r.goods} goods; kinds (top 4 bits): {r.kinds}"]
        for gid, q in r.first:
            out.append(f"    {gid:>10}  x{q if q is not None else '?':<5} {names.get(gid, '')}".rstrip())
        out.append("  bytes around the first entries (32-bit words, the id in [ ]):")
        out += [f"    {d}" for d in r.dump]
    if result.tables:
        out += ["", "lists of 24-byte entries (handle, id, quantity, place, ...), the largest first:"]
        for t in result.tables[:6]:
            out += [f"  {t.where}+0x{t.first:X} (0x{t.address:X}): {t.entries} entries over {t.span} places; kinds (top 4 bits of the id): {t.kinds}",
                    f"    in front of the first entry: {t.head}"]
            out += [f"    asked: {gid} x{q}" for gid, q in t.asked]
    if result.found:
        out += ["", "where the ids asked for are (32-bit words around them, the id in [ ]):"]
        for want, where, addr, words in result.found:
            out.append(f"  {want:>8}  {where} (0x{addr:X}):  {words}")
    return out


def as_json(result: InventoryProbe) -> dict:
    return {"game_data": None if result.game_data is None else f"0x{result.game_data:X}", "why": result.why or None,
            "read_bytes": result.read_bytes,
            "runs": [{"where": r.where, "address": f"0x{r.address:X}", "entry_size": r.stride, "form": r.form, "quantity_from_id": r.qty_at,
                      "entries": r.entries, "goods": r.goods, "kinds": r.kinds, "first": [list(f) for f in r.first], "dump": r.dump}
                     for r in result.runs],
            "found": [{"id": i, "where": w, "address": f"0x{a:X}", "words": d} for i, w, a, d in result.found],
            "tables": [{"where": t.where, "first": f"0x{t.first:X}", "address": f"0x{t.address:X}", "entries": t.entries, "span": t.span,
                        "kinds": t.kinds, "head": t.head, "asked": [list(a) for a in t.asked]} for t in result.tables]}

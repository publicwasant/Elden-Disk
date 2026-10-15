"""The game's text tables (FMG) in its memory, read-only (1.8.1: moved here from writer/text.py, which keeps the one write, `swap`).

How the tables and the array that points at them are found is written at the top of writer/text.py: a table by its shape and size,
the array by the pointers to three tables at the distances the profile's file numbers give. `item_names` reads the names of the items
from the tables the profile's `text.names` numbers say (spec 1.8.1 section 5).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

from . import scan
from .memory import is_user_ptr
from .profile import TextProfile

HEADER = 0x28
MAX_TABLE = 64 * 1024 * 1024        # a sanity bound for the size field of a table
MAGIC = b"\x00\x00\x02\x00"         # little endian, version 2: how every table starts


@dataclass(frozen=True)
class Table:
    """The table a text file's slot points at, as the game holds it."""
    name: str
    slot_at: int        # the address of the pointer that leads to the table
    base: int           # where the table is
    data: bytes         # its bytes as in the file (the address at 0x18 turned back into an offset)


def live_form(data: bytes, base: int) -> bytes:
    """The table as the game holds it at `base`: the same bytes, the offsets position (0x18) turned into an address."""
    offsets_at, = struct.unpack_from("<q", data, 0x18)
    return data[:0x18] + struct.pack("<Q", base + offsets_at) + data[0x20:]


def file_form(live: bytes, base: int) -> bytes | None:
    """The reverse of live_form; None when 0x18 does not hold an address inside the table (not a table of the game)."""
    if len(live) < HEADER:
        return None
    address, = struct.unpack_from("<Q", live, 0x18)
    offsets_at = address - base
    if not HEADER <= offsets_at < len(live):
        return None
    return live[:0x18] + struct.pack("<q", offsets_at) + live[0x20:]


def table_size(data: bytes, i: int, addr: int) -> int:
    """If `data` holds, at `i`, the start of a text table of the game that lies at the address `addr`: its size; otherwise 0."""
    if data[i:i + 4] != MAGIC or i + HEADER > len(data):
        return 0
    size, one, groups, strings = struct.unpack_from("<IIii", data, i + 4)
    offsets_at, zero = struct.unpack_from("<QQ", data, i + 0x18)
    if one != 1 or zero != 0 or groups < 0 or strings < 0 or offsets_at != addr + HEADER + 16 * groups:
        return 0
    if not HEADER + 16 * groups + 8 * strings <= size <= MAX_TABLE:
        return 0
    return size


@dataclass
class Seen:
    """What the look for the tables saw."""
    found: dict = field(default_factory=dict)      # table name -> bases of the tables of the size the profile says
    sizes: dict = field(default_factory=dict)      # size -> how many tables of the game have it (all that were seen)
    walked: scan.Walked | None = None


def find_tables(mem, text: TextProfile, everything: bool = False, budget: float = scan.BUDGET) -> Seen:
    """Look through the game's memory for the tables of the sizes the profile says. The look ends when every table has one, unless
    `everything` (then it goes through all the memory: there can be more than one copy of a table)."""
    want: dict[int, list[str]] = {}
    for name, size in text.sizes.items():
        want.setdefault(size, []).append(name)
    seen = Seen(found={n: [] for n in text.sizes})
    done: set[int] = set()

    def visit(addr: int, data: bytes, n: int) -> bool:
        i = data.find(MAGIC)
        while i != -1:
            if i < n and (addr + i) % 8 == 0 and addr + i not in done:
                size = table_size(data, i, addr + i)
                if size:
                    done.add(addr + i)
                    seen.sizes[size] = seen.sizes.get(size, 0) + 1
                    for name in want.get(size, ()):
                        seen.found[name].append(addr + i)
            i = data.find(MAGIC, i + 1)
        return not everything and all(seen.found.values())

    seen.walked = scan.walk(mem, visit, overlap=HEADER, budget=budget)
    return seen


@dataclass
class Arrays:
    """What the look for the array saw: where it is, and which table each of our files leads to there."""
    found: list = field(default_factory=list)      # [(address of the array, {table name: base of the table it points at})]
    pointers: int = 0                              # pointers to the first table seen (each one is checked for the other two)
    walked: scan.Walked | None = None


def find_arrays(mem, text: TextProfile, bases: dict, budget: float = scan.BUDGET) -> Arrays:
    """Look through the game's memory for the array that points at the tables `bases` (name -> list of bases) from the places the
    profile's file numbers say. Only the pointer to the FIRST table (GoodsName) is looked for; where one is seen, the other two slots
    are read and must hold the other tables: three pointers at exactly these distances do not happen by chance. The look starts
    around the tables (in the logs the array lay within 20 MB of them), ends at the first array that is whole, and goes on through the
    rest of the memory only if there is none. Three runs of the whole memory saw exactly one array, so one is what is taken."""
    first = min(text.files, key=text.files.get)
    anchors = {struct.pack("<Q", base): base for base in bases.get(first, ())}
    out = Arrays()
    seen: set[int] = set()

    def whole(array: int, base: int) -> dict | None:
        tables = {first: base}
        for name, number in text.files.items():
            if name == first:
                continue
            raw = mem.read(array + 8 * number, 8) if array > 0 else None
            point = struct.unpack("<Q", raw)[0] if raw else 0
            if point not in bases.get(name, ()):
                return None
            tables[name] = point
        return tables

    def visit(addr: int, data: bytes, n: int) -> bool:
        for pattern, base in anchors.items():
            i = data.find(pattern)
            while i != -1:
                at = addr + i
                if i < n and at % 8 == 0 and at not in seen:
                    seen.add(at)
                    tables = whole(at - 8 * text.files[first], base)
                    if tables:
                        out.found.append((at - 8 * text.files[first], tables))
                        return True
                i = data.find(pattern, i + 1)
        return False

    near = [b for bs in bases.values() for b in bs]
    out.walked = scan.walk(mem, visit, overlap=7, budget=budget, near=near) if anchors else scan.Walked(False, True, 0, 0.0, "near")
    out.pointers = len(seen)
    return out


def read_table(mem, name: str, slot_at: int) -> tuple[Table | None, str]:
    """The table the pointer at `slot_at` leads to. -> (the table, "") or (None, why it is not one)."""
    raw = mem.read(slot_at, 8) if is_user_ptr(slot_at) else None
    base = struct.unpack("<Q", raw)[0] if raw else 0
    if not is_user_ptr(base):
        return None, f"the pointer at {slot_at:#x} holds {base:#x}, not an address"
    head = mem.read(base, HEADER)
    if head is None:
        return None, f"the table at {base:#x} cannot be read"
    size = table_size(head, 0, base)
    if not size:
        return None, f"the bytes at {base:#x} do not start like a text table (header {head[:4].hex()})"
    live = mem.read(base, size)
    data = file_form(live, base) if live else None
    if not data:
        return None, f"the table at {base:#x} ({size} bytes) cannot be read whole or points inside itself wrongly"
    return Table(name, slot_at, base, data), ""


def fmg_entries(data: bytes) -> dict[int, str]:
    """{id: text} of a table in its file form (version 2); an id with no text is left out. {} when it does not add up."""
    if len(data) < HEADER or data[:4] != MAGIC:
        return {}
    groups, = struct.unpack_from("<i", data, 0x0C)
    offsets_at, = struct.unpack_from("<q", data, 0x18)
    out: dict[int, str] = {}
    try:
        for g in range(groups):
            first_index, first, last, _ = struct.unpack_from("<iiii", data, HEADER + g * 16)
            for k in range(last - first + 1):
                at, = struct.unpack_from("<q", data, offsets_at + (first_index + k) * 8)
                if at <= 0 or at >= len(data):
                    continue
                end = data.find(b"\0\0", at)
                while end != -1 and (end - at) % 2:
                    end = data.find(b"\0\0", end + 1)
                if end == -1:
                    return {}
                if end > at:
                    out[first + k] = data[at:end].decode("utf-16le", "replace")
    except struct.error:
        return {}
    return out


def item_names(mem, text: TextProfile, budget: float = scan.BUDGET) -> tuple[dict[tuple[str, int], str], str]:
    """({(param table, row id): the game's name of the item}, "") from the tables `text.names` lists (later numbers win: the DLC's), or
    ({}, why not). One look for the tables and the array (about a second), then a few tables read."""
    if not text.names:
        return {}, "the profile's text block has no names"
    if text.name_files:          # found by tables a build never replaces (the game in the log of 2026-10-15: GoodsName replaced)
        text = TextProfile(text.name_files, text.name_sizes, text.names)
    seen = find_tables(mem, text, budget=budget)
    if not all(seen.found.values()):
        return {}, "the game's text tables were not found (another language than the profile's sizes?)"
    arrays = find_arrays(mem, text, seen.found, budget=budget)
    if not arrays.found:
        return {}, "the array of the text tables was not found"
    array = arrays.found[0][0]
    out: dict[tuple[str, int], str] = {}
    for table, numbers in text.names.items():
        for number in numbers:
            found, _why = read_table(mem, f"{table}:{number}", array + 8 * number)
            if found is None:
                continue
            for iid, name in fmg_entries(found.data).items():
                if name.strip():
                    out[(table, iid)] = name
    return out, ""

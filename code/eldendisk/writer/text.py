"""`write --text`: give the running game a rebuilt text table (spec 1.7.1). Memory only; the table's contents are not read here.

What tools/probe_text.py and the logs of 1.17.1 showed: the game keeps each text table (FMG) in memory as it is in its file, except
that the 8 bytes at 0x18 (where the string offsets are) hold an ADDRESS (the table's base + the offset), and ONE pointer, in an array
of pointers (the pointer to the table of text file N sits at `array + N * 8`), leads to the table of text file N. So the whole change
is: copy the new table into memory allocated in the game, then change that one pointer (a single aligned 8-byte write). The game's own
table is not touched, and the change disappears when the game closes.

Where the array is cannot be had from a fixed chain from the exe: the pointer that was thought to lead to it (exe + 0x3D61FB8) held,
in runs of the same game, the right object once and memory that had been given back and used for something else the other times. So
the tables and the array are FOUND, by what they are (writer/scan.py does the looking):
 1. A table of the game is recognised by its shape: the header (version 2, the 1 at 0x08), and the address at 0x18 being exactly the
    table's base + 0x28 + 16 * the number of groups. The tables wanted are the ones of the size the profile says (`text.sizes`: the
    size of the game's own file of that table, in the language the game is played in).
 2. The array is where those tables are pointed at from the places the profile's text file numbers give: the pointer to GoodsName at
    A + 10 * 8, to GoodsInfo at A + 20 * 8, to GoodsCaption at A + 24 * 8. Three pointers at exactly these distances do not happen
    by chance. Only the first is searched for; the other two slots are read where one is seen. The search starts around the tables
    (scan.py `near`) and ends at the first whole array.

This module knows bytes only. Building the new table (ids -> text) is done by the command with extension/innovate_items/fmg.py:
the writer package may not import the extension package, and the extension knows nothing of the game.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

from ..game.memory import is_user_ptr
from ..game.profile import TextProfile
from . import scan

HEADER = 0x28
MAX_TABLE = 64 * 1024 * 1024        # a sanity bound for the size field of a table
MAGIC = b"\x00\x00\x02\x00"         # little endian, version 2: how every table starts


class TextError(Exception):
    pass


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


def swap(mem, gate, table: Table, new: bytes) -> int:
    """Put `new` (a table in its file form) into the game in place of `table`. Returns the new base; 0 when the game already
    holds exactly this text (nothing is allocated then, so applying the same text twice costs nothing). TextError when the gate
    is closed, the memory cannot be had, or the pointer does not stick. The order matters: the whole table is written before the
    pointer, so the game never sees a half table."""
    if not gate.allowed:
        raise TextError(f"{table.name}: writes are not allowed ({gate.reason})")
    if new == table.data:
        return 0
    base = mem.alloc(len(new))
    if not base:
        raise TextError(f"{table.name}: the game gave no memory for {len(new)} bytes")
    if not mem.write(base, live_form(new, base)):
        raise TextError(f"{table.name}: could not write the new table at {base:#x}; the game still uses its own")
    now = mem.read(table.slot_at, 8)
    if now is None or struct.unpack("<Q", now)[0] != table.base:
        raise TextError(f"{table.name}: the pointer changed while the table was prepared; nothing was switched")
    if not mem.write(table.slot_at, struct.pack("<Q", base)):
        raise TextError(f"{table.name}: could not change the pointer at {table.slot_at:#x}")
    back = mem.read(table.slot_at, 8)
    if back is None or struct.unpack("<Q", back)[0] != base:
        raise TextError(f"{table.name}: the pointer did not stick")
    return base

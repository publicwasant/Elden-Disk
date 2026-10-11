"""`write --text`: give the running game a rebuilt text table (spec 1.7.1). Memory only; the table's contents are not read here.

What tools/probe_text.py and tools/probe_chain.py showed on 1.17.1: the game keeps each text table (FMG) in memory as it is in
its file, except that the 8 bytes at 0x18 (where the string offsets are) hold an ADDRESS (the table's base + the offset), and
ONE pointer, at `object + array + N * 8` (the profile's `text` block), leads to the table of text file N. So the whole change is:
copy the new table into memory allocated in the game, then change that one pointer (a single aligned 8-byte write). The game's
own table is not touched, and the change disappears when the game closes.

This module knows bytes only. Building the new table (ids -> text) is done by the command with extension/innovate_items/fmg.py:
the writer package may not import the extension package, and the extension knows nothing of the game.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

from ..game.memory import is_user_ptr
from ..game.profile import TextProfile

HEADER = 0x28
MAX_TABLE = 64 * 1024 * 1024        # a sanity bound for the size field of a table


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


def _u64(mem, addr: int) -> int:
    raw = mem.read(addr, 8) if is_user_ptr(addr) else None
    return struct.unpack("<Q", raw)[0] if raw else 0


def locate(mem, exe_base: int, text: TextProfile, name: str) -> Table | None:
    """Follow the chain from the exe to the slot of this table and read the table. None while it is not there yet (the game is
    still starting) or does not look like a text table of the game. Never raises on unreadable memory."""
    if name not in text.files:
        raise TextError(f"{name}: not a text table of this profile ({', '.join(text.files)})")
    obj = _u64(mem, exe_base + text.rva)
    if not is_user_ptr(obj):
        return None
    slot_at = obj + text.array + text.files[name] * 8
    base = _u64(mem, slot_at)
    if not is_user_ptr(base):
        return None
    head = mem.read(base, HEADER)
    if head is None or head[0] != 0 or head[1] != 0 or head[2] != 2:           # little endian, version 2
        return None
    size, = struct.unpack_from("<I", head, 4)
    if not HEADER <= size <= MAX_TABLE:
        return None
    live = mem.read(base, size)
    data = file_form(live, base) if live else None
    return Table(name, slot_at, base, data) if data else None


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

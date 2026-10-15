"""`innovate-spells apply`: give the running game a rebuilt text table (spec 1.7.1). Memory only; the table's contents are not read here.

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

This module knows bytes only. Building the new table (ids -> text) is done by the command with creative/innovate_spells/fmg.py:
the writer package may not import the creative package, and the creative package knows nothing of the game.
"""
from __future__ import annotations

import struct

from ..game.textmem import (HEADER, MAGIC, MAX_TABLE, Arrays, Seen, Table, file_form, find_arrays,  # noqa: F401
                            find_tables, live_form, read_table, table_size)


class TextError(Exception):
    pass


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

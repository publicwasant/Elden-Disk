"""tools/dump_menu.py: reading the header file (BHF4) of a split binder and finding an icon by number. Synthetic data, no game files."""
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import dump_menu as dm  # noqa: E402


def bhf4(entries, unicode_names=True):
    """entries = [(name, size, unpacked, offset, id)] -> a BHF4 with the 36-byte file headers of this game's binders."""
    head = bytearray(b"BHF4" + bytes([0, 0, 0, 0]) + struct.pack("<ii", 0x10000, len(entries)) + struct.pack("<q", 0x40))
    head += b"07D7R6\0\0" + struct.pack("<q", dm.ENTRY) + struct.pack("<q", 0)
    head += bytes([1 if unicode_names else 0, 0x74, 4, 0]) + struct.pack("<i", 0) + struct.pack("<q", 0)
    assert len(head) == 0x40
    names_at = 0x40 + dm.ENTRY * len(entries)
    body, names = bytearray(), bytearray()
    for name, csize, usize, off, fid in entries:
        raw = (name.encode("utf-16le") + b"\0\0") if unicode_names else name.encode("ascii") + b"\0"
        body += struct.pack("<Bxxxiqq", 0x40, -1, csize, usize) + struct.pack("<Iii", off, fid, names_at + len(names))
        names += raw
    return bytes(head + body + names)


ENTRIES = [("N:\\GR\\data\\Menu\\ScaleForm\\Tex\\MENU_ItemIcon_02134.dds", 5000, 20000, 0, 0),
           ("N:\\GR\\data\\Menu\\ScaleForm\\Tex\\MENU_ItemIcon_12134.dds", 5100, 20000, 5000, 1),
           ("N:\\GR\\data\\Menu\\ScaleForm\\Tex\\MENU_Knowledge_00005.dds", 900, 4000, 10100, 2)]


def test_items_are_read():
    items = dm.bhf4_items(bhf4(ENTRIES))
    assert [i.name for i in items] == [e[0] for e in ENTRIES]
    assert items[1].size == 5100 and items[1].offset == 5000 and items[1].unpacked == 20000
    assert items[2].id == 2


def test_a_high_index_does_not_leak_into_the_offset():
    """The index sits right after the 4-byte offset: read as one 8-byte offset it would make a huge number (this was a bug)."""
    items = dm.bhf4_items(bhf4([("a.fxr", 10, 10, 78719040, 3553)]))
    assert items[0].offset == 78719040 and items[0].id == 3553


def test_every_file_of_a_real_binder_is_where_the_reader_says():
    """regulation.bin's own BND4 is built by container.Bnd4; the reader here must find each file at the same place."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from design_helpers import bnd4_blob
    blob = bnd4_blob([("A.param", b"x" * 40), ("B.param", b"y" * 55), ("C.param", b"z" * 9)])
    items = dm.bhf4_items(blob, (b"BND4",))
    assert [blob[i.offset:i.offset + i.size] for i in items] == [b"x" * 40, b"y" * 55, b"z" * 9]


def test_ascii_names():
    items = dm.bhf4_items(bhf4(ENTRIES, unicode_names=False))
    assert dm.short(items[0].name) == "MENU_ItemIcon_02134.dds"


def test_find_icon_matches_the_whole_number_only():
    items = dm.bhf4_items(bhf4(ENTRIES))
    assert [i.index for i in dm.find_icon(items, 2134)] == [0]
    assert [i.index for i in dm.find_icon(items, 12134)] == [1]
    assert dm.find_icon(items, 134) == []
    assert [i.index for i in dm.find_icon(items, 5)] == [2]


def test_families_group_by_the_digits():
    items = dm.bhf4_items(bhf4(ENTRIES))
    assert dm.families(items) == [("MENU_ItemIcon_#.dds", 2), ("MENU_Knowledge_#.dds", 1)]


def test_a_layout_it_does_not_know_is_refused_with_the_header():
    blob = bytearray(bhf4(ENTRIES))
    blob[0x20] = 0x30                            # the entry size no longer agrees with the format
    with pytest.raises(dm.MenuError, match="unexpected binder layout"):
        dm.bhf4_items(bytes(blob))
    with pytest.raises(dm.MenuError, match="not a BHF4"):
        dm.bhf4_items(b"BND4" + bytes(100))


def test_a_bnd4_can_be_read_with_the_same_reader():
    blob = bhf4(ENTRIES).replace(b"BHF4", b"BND4", 1)
    assert [i.index for i in dm.bhf4_items(blob, (b"BND4",))] == [0, 1, 2]
    with pytest.raises(dm.MenuError, match="not a BHF4"):
        dm.bhf4_items(blob)


def test_sfx_matching_takes_the_whole_number():
    import dump_sfx
    items = dm.bhf4_items(bhf4([("f000524402.fxr", 10, 10, 0, 0), ("f000524403.fxr", 10, 10, 10, 1), ("f005244020.fxr", 10, 10, 20, 2)]))
    assert [i.index for i in dump_sfx.matching(items, [524402])] == [0]
    assert dump_sfx.matching(items, [52440]) == []

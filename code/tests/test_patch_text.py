"""tools/patch_text.py against a fake game memory: find the live table, its one pointer, replace it, undo."""
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import patch_text as px  # noqa: E402

from eldendisk.extension.innovate_items.fmg import Fmg  # noqa: E402


class Game:
    """Regions of bytes; alloc hands out new regions; write works inside one region."""
    def __init__(self):
        self.mem, self.next = {}, 0x50000

    def regions(self):
        return [(b, len(d), "private", 4) for b, d in self.mem.items()]

    def read(self, addr, size):
        for b, d in self.mem.items():
            if b <= addr and addr + size <= b + len(d):
                return bytes(d[addr - b:addr - b + size])
        return None

    def write(self, addr, data):
        for b, d in self.mem.items():
            if b <= addr and addr + len(data) <= b + len(d):
                d[addr - b:addr - b + len(data)] = data
                return
        raise OSError("bad write")

    def alloc(self, size):
        base, self.next = self.next, self.next + ((size + 0xFFF) & ~0xFFF) + 0x1000
        self.mem[base] = bytearray(size)
        return base


def make(n_pointers=1):
    blob = Fmg({6050: "Flame, Grant Me Strength", 10: "Dagger", 11: "Sword"}).write()
    g = Game()
    base = 0x10000
    g.mem[base] = bytearray(px.live_form(blob, base))
    holder = bytearray(256)
    for i in range(n_pointers):
        struct.pack_into("<Q", holder, i * 16, base)
    g.mem[0x20000] = holder
    return g, blob, base


def test_the_live_form_changes_only_the_offsets_position():
    blob = Fmg({1: "a"}).write()
    live = px.live_form(blob, 0x7000)
    assert live[:0x18] == blob[:0x18] and live[0x20:] == blob[0x20:]
    assert struct.unpack_from("<Q", live, 0x18)[0] == 0x7000 + struct.unpack_from("<q", blob, 0x18)[0]


def test_plan_apply_and_undo():
    g, blob, base = make()
    step = px.plan(g, "GoodsName", blob, {6050: "Flame (test)", 2230000: "Reverse Curse Technique"})
    assert step["old_base"] == base and step["pointer_at"] == 0x20000
    new_base = px.apply(g, step)
    assert struct.unpack("<Q", g.read(0x20000, 8))[0] == new_base
    live = g.read(new_base, len(step["new"]))
    assert live == px.live_form(step["new"], new_base)
    back = Fmg.read(step["new"])
    assert back.entries[6050] == "Flame (test)" and back.entries[2230000] == "Reverse Curse Technique"
    assert g.read(base, len(blob)) == px.live_form(blob, base)                 # the old table is untouched
    rec = {"pointer_at": 0x20000, "old_base": base, "new_base": new_base}
    assert px.undo(g, rec) is True
    assert struct.unpack("<Q", g.read(0x20000, 8))[0] == base
    assert px.undo(g, rec) is False                                             # the pointer no longer holds our value


def test_plan_refuses_when_the_pointer_is_not_unique_or_the_table_is_missing():
    g, blob, _ = make(n_pointers=2)
    with pytest.raises(ValueError):
        px.plan(g, "GoodsName", blob, {})
    g2, blob2, _ = make()
    other = Fmg({1: "x"}).write()
    with pytest.raises(ValueError):
        px.plan(g2, "GoodsName", other, {})


def test_plan_chain_follows_the_exe_pointer_without_searching():
    blob = Fmg({6050: "Flame, Grant Me Strength", 10: "Dagger"}).write()
    g = Game()
    exe, obj, tbl = 0x7FF600000000, 0x30000, 0x10000
    g.mem[exe + px.CHAIN_RVA - 0x100] = bytearray(0x400)                       # a piece of the exe's data
    g.mem[tbl] = bytearray(px.live_form(blob, tbl))
    g.mem[obj] = bytearray(0x2000)
    struct.pack_into("<Q", g.mem[exe + px.CHAIN_RVA - 0x100], 0x100, obj)
    struct.pack_into("<Q", g.mem[obj], px.CHAIN_ARRAY + 10 * 8, tbl)
    step = px.plan_chain(g, exe, "GoodsName", blob, {2230000: "Reverse Curse Technique"})
    assert step["old_base"] == tbl and step["pointer_at"] == obj + px.CHAIN_ARRAY + 80
    new_base = px.apply(g, step)
    assert struct.unpack_from("<Q", g.mem[obj], px.CHAIN_ARRAY + 80)[0] == new_base
    with pytest.raises(ValueError):                                              # already patched: not the game's own table
        px.plan_chain(g, exe, "GoodsName", blob, {})
    g2 = Game()
    with pytest.raises(ValueError):
        px.plan_chain(g2, exe, "GoodsName", blob, {})

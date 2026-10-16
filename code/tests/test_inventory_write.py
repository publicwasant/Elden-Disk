"""`write inventory....quantity.held|stored=N` (1.8.1 part 2): the count of an item the character already has, through the portal.
The rig of tests/test_write_command.py (a session, the gate) with the inventory lists of tests/test_inventory.py and an EquipParamGoods
table that gives each item its caps (`maxNum` held, `maxRepositoryNum` stored)."""
import struct
from dataclasses import replace

import pytest

import eldendisk.commands.write as wcmd
from eldendisk.game.attach import EXIT_NO_SESSION, Target
from eldendisk.game.memory import Module
from eldendisk.game.profile import TextProfile
from eldendisk.writer import inventoryedit as ie
from tests import paramfile as pf
from tests.test_disk import BASE, GD
from tests.test_inventory import CHEST1, CHEST2, CARRIED, EMPTY, ITEMS, KEYS, LAY, STORED, entry
from tests.test_param_tables import encode, put_table
from tests.test_write_command import EXE_SHA, GAME_PID, GAME_STARTED, rig  # noqa: F401  (the fixture)

CAPS = {1200: (99, 600), 10100: (999, 999), 8000: (99, 600), 2900: (99, 600)}


@pytest.fixture
def inv(rig, tmp_path):   # noqa: F811
    vault, mem, box, open_session, args = rig
    mem.u64(GD + 0x418, ITEMS)
    mem.put(ITEMS, b"".join(EMPTY if e is None else entry(*e, n=n) for n, e in enumerate(CARRIED)) + EMPTY * (32 - len(CARRIED)))
    mem.put(GD + 0xB10, b"".join(entry(*e, n=n) for n, e in enumerate(KEYS)) + EMPTY * (8 - len(KEYS)))
    mem.u64(GD + 0x5F0, CHEST1)
    mem.u64(CHEST1 + 0x8, CHEST2)
    mem.put(CHEST2 + 0x20, b"".join(entry(*e, n=n) for n, e in enumerate(STORED)) + EMPTY * (8 - len(STORED)))
    put_table(mem, "EquipParamGoods", {g: encode("EquipParamGoods", maxNum=h, maxRepositoryNum=s) for g, (h, s) in CAPS.items()})
    prof = replace(pf.params_profile(), inventory=LAY)
    box["locate"] = lambda offsets: Target(GAME_PID, GAME_STARTED, Module("eldenring.exe", BASE, str(tmp_path / "eldenring.exe")),
                                           EXE_SHA, prof)
    return vault, mem, box, open_session, args


def held(mem, n):
    return struct.unpack("<I", mem.read(ITEMS + n * 24 + 8, 4))[0]


def stored(mem, n):
    return struct.unpack("<I", mem.read(CHEST2 + 0x20 + n * 24 + 8, 4))[0]


def key(mem, n):
    return struct.unpack("<I", mem.read(GD + 0xB10 + n * 24 + 8, 4))[0]


def test_a_held_and_a_stored_count_are_written_and_put_back(inv, capsys):
    vault, mem, box, open_session, args = inv
    open_session()
    assert wcmd.cmd_write(args("inventory.goods.1200.quantity.held=20", "disk.character.inventory.goods.1200.quantity.stored=600",
                               "inventory.key_items.8000.quantity=9")) == 0
    assert (held(mem, 0), stored(mem, 0), key(mem, 0)) == (20, 600, 9)
    out = capsys.readouterr().err
    assert "inventory.goods.1200.quantity.held = 20" in out
    assert wcmd.cmd_write(args("inventory.goods.1200.quantity.held=default")) == 0 and held(mem, 0) == 10
    assert wcmd.cmd_write(args("inventory=default")) == 0 and (stored(mem, 0), key(mem, 0)) == (552, 6)


def test_only_the_quantity_is_written_four_bytes_and_nothing_else(inv):
    vault, mem, box, open_session, args = inv
    open_session()
    before = mem.read(ITEMS, 32 * 24)
    mem.log.clear()
    assert wcmd.cmd_write(args("inventory.goods.1200.quantity.held=11")) == 0
    after = mem.read(ITEMS, 32 * 24)
    assert [i for i in range(len(before)) if before[i] != after[i]] == [8] and mem.log == [ITEMS + 8]


@pytest.mark.parametrize("item,why", [
    ("inventory.goods.1200.quantity.held=100", "at most 99"),
    ("inventory.goods.1200.quantity.stored=601", "at most 600"),
    ("inventory.goods.1200.quantity.held=0", "1 or more"),
    ("inventory.goods.1200.quantity.total=20", "computed"),
    ("inventory.goods.1200.name=x", "only the quantity"),
    ("inventory.talismans.1150.quantity.held=2", "cannot be written"),
    ("inventory.weapons.9000000.quantity.held=2", "cannot be written"),
    ("inventory.key_items.8000.quantity.stored=3", "not kept in the storage chest"),
    ("inventory.goods.810.quantity.held=5", "has no goods 810"),
    ("inventory.goods.2900.quantity.held=5", "has no goods 2900 held"),          # only in the chest: adding it held is not in 1.8.1
    ("inventory.goods.1200.quantity.held=ten", "whole number"),
    ("inventory.rowa_raisin.quantity=5", "no item of that name"),
])
def test_what_cannot_be_written_is_refused_with_the_reason_and_nothing_is_written(inv, item, why, capsys):
    vault, mem, box, open_session, args = inv
    open_session()
    mem.log.clear()
    assert wcmd.cmd_write(args(item)) == 1 and mem.log == []
    assert why in capsys.readouterr().err


def test_an_item_is_written_by_its_name(inv, monkeypatch):
    vault, mem, box, open_session, args = inv
    open_session()
    prof = replace(pf.params_profile(), inventory=LAY, text=TextProfile({"GoodsName": 10}, {"GoodsName": 40}))
    box["locate"] = lambda offsets: Target(GAME_PID, GAME_STARTED, Module("eldenring.exe", BASE, "x"), EXE_SHA, prof)
    monkeypatch.setattr(ie, "item_names", lambda mem, text, **kw: ({("EquipParamGoods", 1200): "Gold-Pickled Fowl Foot"}, ""))
    assert wcmd.cmd_write(args("inventory.gold_pickled_fowl_foot.quantity.held=33")) == 0 and held(mem, 0) == 33


def test_an_entry_that_changed_while_the_write_was_prepared_is_not_written(inv, monkeypatch, capsys):
    vault, mem, box, open_session, args = inv
    open_session()
    real = ie.find_entry

    def moved(*a, **k):
        at, head = real(*a, **k)
        mem.put(at + 8, struct.pack("<I", 3))          # the game used some in that moment
        return at, head
    monkeypatch.setattr(ie, "find_entry", moved)
    mem.log.clear()
    assert wcmd.cmd_write(args("inventory.goods.1200.quantity.held=20")) == 1 and mem.log == []
    assert "changed while the write was prepared" in capsys.readouterr().err


def test_no_session_no_write(inv, capsys):
    vault, mem, box, open_session, args = inv
    assert wcmd.cmd_write(args("inventory.goods.1200.quantity.held=20")) == EXIT_NO_SESSION and held(mem, 0) == 10


def test_a_script_writes_a_count_through_tools_write(inv, tmp_path):
    from eldendisk.creative.scripts.backend import Refused, write_values
    from eldendisk.writer.paramedit import Snapshot
    from eldendisk.writer.writer import WriteGate
    vault, mem, box, open_session, args = inv
    target = box["locate"](None)
    gate = WriteGate()
    gate.open()
    snap = Snapshot(tmp_path / "snap.json", GAME_PID, GAME_STARTED)
    got = write_values(mem, target, gate, snap, {"character.inventory.goods.1200.quantity.held": 15}, lambda level, msg: None)
    assert got == {"character.inventory.goods.1200.quantity.held": 15} and held(mem, 0) == 15
    with pytest.raises(Refused, match="cannot be written"):
        write_values(mem, target, gate, snap, {"character.inventory.talismans.1150.quantity.held": 2}, lambda level, msg: None)

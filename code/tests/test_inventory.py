"""`character.inventory` (1.8.1): the two lists of PlayerGameData as `probe inventory` measured them on 1.17.1 (24-byte entries: the
handle, the id, the quantity, the place, two more words; the items behind the pointer at +0x418, the key items inline at +0xB10)."""
import dataclasses
import struct
from datetime import timedelta

import jsonschema
import pytest

from eldendisk.game import inventory as INV
from eldendisk.game.profile import InventoryLayout, InventoryList, load_profile
from eldendisk.reader import view
from eldendisk.reader import sampler as S
from eldendisk.reader.export import build_document
from tests import paramfile as pf
from tests.test_disk import BASE, GD, NOW, SCHEMA, full_world, state_ids
from tests.test_param_tables import encode, put_table

ITEMS = 0x510000000
CHEST1, CHEST2 = 0x520000000, 0x530000000           # [[PlayerGameData + 0x5F0] + 0x8] + 0x20: the storage chest
LAY = InventoryLayout(24, 0, 4, 8, InventoryList((0x418,), 0, 32), InventoryList((), 0xB10, 8), InventoryList((0x5F0, 0x8), 0x20, 8))


def entry(top, iid, qty, n=0):
    handle = {0x0: 0x8, 0x1: 0x9, 0x2: 0xA, 0x4: 0xB, 0x8: 0xC}[top] << 28
    handle |= iid if top in (0x2, 0x4) else 0x10000 + n
    return struct.pack("<IIIIII", handle, (top << 28) | iid, qty, 0x100 + n, 0, 0xFFFFFFFF)


EMPTY = struct.pack("<IIIIII", 0, 0xFFFFFFFF, 0, 0, 0, 0xFFFFFFFF)
CARRIED = [(0x4, 1200, 10), (0x0, 9000110, 1), (0x4, 10100, 16), None, (0x2, 1150, 1), (0x1, 50000, 1), (0x8, 10000, 1),
           (0x4, 10100, 1), (0x0, 9000000, 1)]
KEYS = [(0x4, 8000, 6), (0x4, 8158, 1)]
STORED = [(0x4, 1200, 552), (0x0, 9000000, 1), (0x4, 2900, 4)]       # Gold-Pickled Fowl Foot 552 in the chest, as in the game


def game(items=CARRIED, keys=KEYS, stored=STORED):
    m = full_world()
    m.u64(GD + 0x418, ITEMS)
    m.put(ITEMS, b"".join(EMPTY if e is None else entry(*e, n=n) for n, e in enumerate(items)) + EMPTY * (32 - len(items)))
    m.put(GD + 0xB10, b"".join(entry(*e, n=n) for n, e in enumerate(keys)) + EMPTY * (8 - len(keys)))
    m.u64(GD + 0x5F0, CHEST1)
    m.u64(CHEST1 + 0x8, CHEST2)
    m.put(CHEST2 + 0x20, b"".join(entry(*e, n=n) for n, e in enumerate(stored)) + EMPTY * (8 - len(stored)))
    return m


def q(total, held, stored):
    return {"total": total, "held": held, "stored": stored}


def test_both_lists_are_read_by_kind_with_names_types_levels_and_added_quantities():
    inv = INV.read_inventory(game(), GD, LAY, goods_types={1200: 0, 10100: 14, 8000: 1, 8158: 1},
                             names={("EquipParamGoods", 1200): "Gold-Pickled Fowl Foot", ("EquipParamWeapon", 9000100): "Heavy Uchigatana"})
    assert inv["goods"] == {"1200": {"name": "Gold-Pickled Fowl Foot", "type": "consumable", "quantity": q(562, 10, 552)},
                            "10100": {"name": None, "type": "upgrade material", "quantity": q(17, 17, 0)},   # two places: added
                            "2900": {"name": None, "type": None, "quantity": q(4, 0, 4)}}                   # only in the chest
    assert inv["key_items"]["8000"] == {"name": None, "type": "key item", "quantity": q(6, 6, 0)}
    assert inv["weapons"]["9000110"] == {"name": "Heavy Uchigatana", "upgrade": 10, "quantity": q(1, 1, 0)}
    assert inv["weapons"]["9000000"]["upgrade"] == 0 and inv["weapons"]["9000000"]["quantity"] == q(2, 1, 1)
    assert inv["talismans"] == {"1150": {"name": None, "quantity": q(1, 1, 0)}} and list(inv["armor"]) == ["50000"]
    assert list(inv["ashes_of_war"]) == ["10000"]


def test_an_entry_that_does_not_add_up_is_left_out_never_guessed():
    bad = [(0x4, 1200, 10)]
    m = game(bad, stored=[])
    raw = bytearray(entry(0x4, 810, 3))
    struct.pack_into("<I", raw, 0, 0xB0000999)                  # the handle names another goods than the id
    m.put(ITEMS + 24, bytes(raw))
    m.put(ITEMS + 48, entry(0x4, 2900, 0))                       # a quantity of 0
    raw = bytearray(entry(0x0, 9000000, 1))
    struct.pack_into("<I", raw, 4, 0x40000001)                   # a weapon's handle with a goods id
    m.put(ITEMS + 72, bytes(raw))
    assert list(INV.read_inventory(m, GD, LAY)["goods"]) == ["1200"]


def test_an_unreadable_list_is_an_error_not_an_empty_inventory():
    m = game()
    m.u64(GD + 0x418, 0)
    with pytest.raises(INV.InventoryError, match="pointer"):
        INV.read_inventory(m, GD, LAY)


def profile():
    return dataclasses.replace(pf.params_profile(), inventory=LAY)


def test_the_sample_has_the_inventory_read_about_once_a_second():
    m = game()
    put_table(m, "EquipParamGoods", {g: encode("EquipParamGoods", goodsType=t) for g, t in ((1200, 0), (10100, 14), (8000, 1), (8158, 1))})
    sp = S.Sampler(m, profile(), state_ids(), BASE)
    s = sp.sample(NOW)
    assert s.character["inventory"]["goods"]["1200"] == {"name": None, "type": "consumable", "quantity": q(562, 10, 552)}
    m.put(ITEMS + 8, struct.pack("<I", 9))                       # one eaten
    later = sp.sample(NOW + timedelta(seconds=S.INVENTORY_EVERY_S / 2)).character["inventory"]["goods"]["1200"]["quantity"]
    assert later["held"] == 10
    later = sp.sample(NOW + timedelta(seconds=S.INVENTORY_EVERY_S)).character["inventory"]["goods"]["1200"]["quantity"]
    assert later == q(561, 9, 552)
    doc = build_document(state="CONNECTED", pid=1, anti_cheat="DISABLED_OFFLINE", exe_sha256="ab" * 32, profile_label="x", sample=s)
    jsonschema.validate(doc, SCHEMA)


def test_without_the_profile_block_there_is_no_inventory_and_a_broken_list_is_null():
    m = game()
    assert "inventory" not in S.Sampler(m, pf.params_profile(), state_ids(), BASE).sample(NOW).character
    m.u64(GD + 0x418, 0)
    sp = S.Sampler(m, profile(), state_ids(), BASE)
    s = sp.sample(NOW)
    assert s.character["inventory"] is None and "pointer" in sp.inventory_error and s.character["level"] == 386


def test_an_item_is_found_by_its_name_in_any_kind():
    inv = INV.build([("goods", 1200, 10), ("goods", 10100, 16)], [("goods", 8000, 6)],
                    names={("EquipParamGoods", 1200): "Gold-Pickled Fowl Foot", ("EquipParamGoods", 10100): "Smithing Stone [1]",
                           ("EquipParamGoods", 8000): "Stonesword Key"})
    doc = {"systems": {}, "character": {"level": 1, "inventory": inv}}
    assert view.select(doc, "inventory.gold_pickled_fowl_foot.quantity.held") == [("character.inventory.goods.1200.quantity.held", 10)]
    assert view.select(doc, "disk.character.inventory.smithing_stone_1") == \
        [("disk.character.inventory.goods.10100", {"name": "Smithing Stone [1]", "quantity": q(None, 16, None)})]     # no chest read
    assert view.select(doc, "inventory.stonesword_key.quantity.held") == [("character.inventory.key_items.8000.quantity.held", 6)]
    assert view.select(doc, "inventory.goods.1200.quantity.held") == [("character.inventory.goods.1200.quantity.held", 10)]


def test_the_profile_block_is_read_and_a_bad_one_refused(tmp_path):
    import json
    data = json.loads(pf.OFFSETS.read_text())
    prof, why = load_profile(pf.OFFSETS, pf.EXE_SHA)
    assert why is None and prof.inventory == InventoryLayout(24, 0, 4, 8, InventoryList((0x418,), 0, 2688), InventoryList((), 0xB10, 384),
                                                    InventoryList((0x5F0, 0x8), 0x6020, 1920))
    data["profiles"][pf.EXE_SHA]["inventory"]["entry_size"] = "0x8"
    p = tmp_path / "o.json"
    p.write_text(json.dumps(data))
    prof, why = load_profile(p, pf.EXE_SHA)
    assert prof is None and "entry_size" in why


@pytest.mark.parametrize("query,export,wanted", [
    (None, False, True), (["inventory"], False, True), (["disk.character.inventory.goods"], False, True), (["character"], False, True),
    (["*"], False, True), (["disk"], False, True), (["inventory.gold_pickled_fowl_foot"], False, True),
    (["hp"], False, False), (["level", "runes"], False, False), (["disk.character.level"], False, False), (None, True, True),
])
def test_the_inventory_and_its_names_are_read_only_when_the_command_shows_them(query, export, wanted):
    from types import SimpleNamespace
    from eldendisk.commands.read import _wants_inventory
    assert _wants_inventory(SimpleNamespace(query=query, export=export, live_buffs=False, live_animations=False)) is wanted


def test_the_names_come_from_the_name_tables_the_profile_lists():
    from eldendisk.game import textmem
    fmg = __import__("eldendisk.creative.innovate_spells.fmg", fromlist=["Fmg"]).Fmg
    data = fmg({1200: "Gold-Pickled Fowl Foot", 10100: "Smithing Stone [1]", 999: None}).write()
    assert textmem.fmg_entries(data) == {1200: "Gold-Pickled Fowl Foot", 10100: "Smithing Stone [1]"}
    assert textmem.fmg_entries(b"not a table") == {}


def test_item_names_are_read_from_the_game_text_the_profile_names():
    """A fake game of tests/test_write_text.py: the three tables, the array; GoodsName (10) is the goods' name table here, and a
    second name table (a DLC's, 28) wins for the ids it has."""
    import struct as st
    from eldendisk.game import textmem
    from eldendisk.game.profile import TextProfile
    from tests.test_write_text import ARRAY, FILES, OBJ, SIZES, game_with_tables
    from eldendisk.creative.innovate_spells.fmg import Fmg
    g = game_with_tables()
    dlc = Fmg({1001: "Sword of the DLC", 2000: "Only in the DLC"}).write()
    g.mem[0x39000000] = bytearray(textmem.live_form(dlc, 0x39000000))
    st.pack_into("<Q", g.mem[OBJ], ARRAY + 28 * 8, 0x39000000)
    text = TextProfile(FILES, SIZES, {"EquipParamGoods": (10, 28)})
    names, why = textmem.item_names(g, text)
    assert why == "" and names == {("EquipParamGoods", 1000): "Dagger", ("EquipParamGoods", 1001): "Sword of the DLC",
                                   ("EquipParamGoods", 2000): "Only in the DLC"}
    assert textmem.item_names(g, TextProfile(FILES, SIZES)) == ({}, "the profile's text block has no names")


def test_the_read_handle_can_list_the_regions_a_scan_reads_and_a_failed_look_never_stops_the_read():
    """In the game (2026-10-15): the read handle had no `regions`, and the look for the names raised out of `read inventory`."""
    from eldendisk.game.memory import ACCESS_MASK, ProcessMemory
    from eldendisk.game import _win
    assert hasattr(ProcessMemory, "regions") and ACCESS_MASK & _win.PROCESS_QUERY_INFORMATION
    m = game()
    put_table(m, "EquipParamGoods", {g: encode("EquipParamGoods") for g in (1200, 10100, 8000, 8158)})
    real, _why = load_profile(pf.OFFSETS, pf.EXE_SHA)
    sp = S.Sampler(m, dataclasses.replace(profile(), text=real.text), state_ids(), BASE)      # FakeMem has no regions: the look fails
    s = sp.sample(NOW)
    assert s.character["inventory"]["goods"]["1200"]["name"] is None and sp.names_error


def test_the_names_are_found_by_tables_a_build_never_replaces():
    """In the game (2026-10-15) every name was null: `innovate-spells apply` had replaced GoodsName/Info/Caption, so the array no longer
    pointed at the game's own ones and was not found by them. The names' look finds it by other tables (text.name_files)."""
    import struct as st
    from eldendisk.game import textmem
    from eldendisk.game.profile import TextProfile
    from tests.test_write_text import ARRAY, FILES, OBJ, SIZES, game_with_tables
    g = game_with_tables()
    st.pack_into("<Q", g.mem[OBJ], ARRAY + FILES["GoodsName"] * 8, 0x3F000000)        # GoodsName replaced by a build's table
    from eldendisk.creative.innovate_spells.fmg import Fmg
    built = Fmg({1000: "Dagger", 2230000: "Reverse Cursed Technique"}).write()
    g.mem[0x3F000000] = bytearray(textmem.live_form(built, 0x3F000000))
    assert textmem.item_names(g, TextProfile(FILES, SIZES, {"EquipParamGoods": (10,)}))[0] == {}         # by GoodsName: not found
    anchors = {"GoodsInfo": FILES["GoodsInfo"], "GoodsCaption": FILES["GoodsCaption"]}
    text = TextProfile(FILES, SIZES, {"EquipParamGoods": (10,)}, anchors, {n: SIZES[n] for n in anchors})
    names, why = textmem.item_names(g, text)
    assert why == "" and names[("EquipParamGoods", 2230000)] == "Reverse Cursed Technique"


def test_a_chest_that_cannot_be_read_leaves_stored_and_total_null_and_the_rest_is_read():
    m = game()
    m.u64(GD + 0x5F0, 0)
    inv = INV.read_inventory(m, GD, LAY)
    assert inv["goods"]["1200"]["quantity"] == q(None, 10, None) and "2900" not in inv["goods"]


def test_the_array_of_the_text_is_remembered_for_the_game_and_only_checked_after(tmp_path, monkeypatch):
    """1.8.1 part 3: the look for the array (about a second in the game) is made once per game process."""
    from eldendisk.game import textmem
    from eldendisk.game.profile import TextProfile
    from tests.test_write_text import FILES, SIZES, game_with_tables
    g = game_with_tables()
    text = TextProfile(FILES, SIZES, {"EquipParamGoods": (10,)})
    cache = tmp_path / "text-array.json"
    looks = []
    real = textmem.find_tables
    monkeypatch.setattr(textmem, "find_tables", lambda *a, **k: looks.append(1) or real(*a, **k))
    first = textmem.find_array(g, text, game=(7, 1.5), cache=cache)
    assert first[0] and first[2] is False and len(looks) == 1
    assert textmem.find_array(g, text, game=(7, 1.5), cache=cache) == (first[0], "", True) and len(looks) == 1
    assert textmem.find_array(g, text, game=(8, 2.5), cache=cache)[2] is False and len(looks) == 2     # another game process
    struct.pack_into("<Q", g.mem[0x20000000], 0x100 + FILES["GoodsName"] * 8, 0)                       # the array no longer holds
    assert textmem.find_array(g, text, game=(8, 2.5), cache=cache)[0] is None and len(looks) == 3


def test_the_quick_parse_of_a_list_gives_what_the_entry_checks_give():
    m = game()
    lay24 = LAY
    odd = InventoryLayout(24, 0, 4, 8, InventoryList((0x418,), 0, 32), InventoryList((), 0xB10, 8))
    quick = INV.read_list(m, GD, lay24, lay24.items)
    slow = [e for n in range(32) if (e := INV.entry(m.read(ITEMS, 32 * 24), n * 24, odd)) is not None]
    assert quick == slow and len(quick) == 8

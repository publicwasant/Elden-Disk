"""`character.buffs` (1.8.2): a buff is named by the held item that gives it. The item's object of `character.inventory` is the buff's,
with `reference` (the paths of the held items that give it) and `times` for a timed buff; an effect no held item gives is counted."""
from datetime import timedelta

import jsonschema

from eldendisk.game.params import ParamError
from eldendisk.reader import sampler as S
from eldendisk.reader.buffitems import AGAIN_S, ItemEffects, build_index, row_refs
from eldendisk.reader.export import build_document
from tests.test_disk import BASE, NOW, SCHEMA, state_ids
from tests.test_inventory import game, profile, q
from tests.test_param_tables import encode, put_table

# The character of tests/test_inventory.py holds goods 1200 and 10100, the weapon 9000110 (row 9000100, +10), the talisman 1150, the
# armor 50000, the ash of war 10000, the weapon 9000000 and the key items 8000 / 8158; the goods 2900 is only in the chest.
ROWS = {
    "EquipParamGoods": {1200: {"refCategory": 2, "refId_default": 100}, 10100: {}, 2900: {"refCategory": 2, "refId_default": 900},
                        8000: {"refCategory": 2, "refId_1": 1000}, 8158: {}},
    "Magic": {10100: {"refCategory1": 0, "refId1": 55, "refCategory3": 2, "refId3": 700}},      # a spell's goods id is its Magic id
    "EquipParamWeapon": {9000100: {"residentSpEffectId": 200, "residentSpEffectId1": -1}, 9000000: {"residentSpEffectId": 800}},
    "EquipParamAccessory": {1150: {"refCategory": 1, "refId": 7, "residentSpEffectId1": 300}},
    "Bullet": {7: {"spEffectIDForShooter": 400, "spEffectId0": 0}},
    "EquipParamProtector": {50000: {"residentSpEffectId": 0, "residentSpEffectId2": 500, "residentSpEffectId3": 100}},
    "EquipParamGem": {10000: {"spEffectId0": 600}},
}


def effects(rows=ROWS, reads=None, clock=None):
    def read(table, fields):
        if reads is not None:
            reads.append(table)
        if table not in rows:
            raise ParamError(f"{table}: not in memory")
        return {rid: dict(row) for rid, row in rows[table].items()}
    return ItemEffects(read, **({"clock": clock} if clock else {}))


def sampler(m=None, rows=ROWS):
    sp = S.Sampler(m or game(), profile(), state_ids(), BASE)
    sp.item_effects = effects(rows)
    return sp


def test_each_kind_of_item_gives_its_effects_and_a_bullet_is_followed_one_step():
    assert row_refs("EquipParamGoods", {"refCategory": 2, "refId_default": 3971, "refId_1": -1}) == ([3971], [])
    assert row_refs("Magic", {"refCategory1": 1, "refId1": 10660000, "refCategory2": 2, "refId2": 5}) == ([5], [10660000])
    inv = sampler().sample(NOW).character["inventory"]
    index = build_index(inv, effects())
    assert index == {100: [("goods", "1200"), ("armor", "50000")], 1000: [("key_items", "8000")], 700: [("goods", "10100")],
                     300: [("talismans", "1150")], 400: [("talismans", "1150")], 200: [("weapons", "9000110")],
                     500: [("armor", "50000")], 600: [("ashes_of_war", "10000")], 800: [("weapons", "9000000")]}
    assert 900 not in index and 55 not in index       # the chest gives no buff; a refCategory 0 is an attack


def test_a_buff_is_the_items_object_with_its_references_and_times():
    sp = sampler()
    s = sp.sample(NOW)
    b = s.character["buffs"]
    assert b["100"] == {**s.character["inventory"]["goods"]["1200"],
                        "reference": ["character.inventory.goods.1200", "character.inventory.armor.50000"],
                        "times": {"buff_duration": 45.0, "max_duration": 80.0, "last_activated_at": "2026-09-30 11:59:25.000000+00:00"}}
    assert b["100"]["quantity"] == q(562, 10, 552)
    assert b["200"] == {"name": None, "upgrade": 10, "quantity": q(1, 1, 0), "reference": ["character.inventory.weapons.9000110"]}
    assert "999" not in b and s.ignored_buffs == 1                  # no held item gives 999
    doc = build_document(state="CONNECTED", pid=1, anti_cheat="DISABLED_OFFLINE", exe_sha256="ab" * 32, profile_label="x", sample=s)
    jsonschema.validate(doc, SCHEMA)


def test_the_index_is_made_again_only_when_the_held_items_change():
    m = game()
    sp = sampler(m)
    made = []
    real = S.build_index
    S.build_index = lambda *a: made.append(1) or real(*a)
    try:
        for n in range(5):
            sp.sample(NOW + timedelta(seconds=n * 0.4))
        assert len(made) == 1                                    # the counts change nothing; the inventory is read again each second
        sp._inventory["goods"]["1200"]["quantity"]["held"] = 0   # as if the last one was eaten
        sp._index_of = None
        sp.buff_index(sp._inventory)
        assert len(made) == 2 and 100 in sp._index and ("goods", "1200") not in sp._index[100]
    finally:
        S.build_index = real


def test_a_table_is_read_once_and_again_only_for_a_row_it_lacks_after_a_while():
    reads, clock = [], [0.0]
    eff = effects(reads=reads, clock=lambda: clock[0])
    assert eff.of_item("goods", 1200) == (100,) and eff.of_item("goods", 1200) == (100,)
    assert reads == ["EquipParamGoods", "Magic"]
    assert eff.of_item("goods", 5555) == () and reads == ["EquipParamGoods", "Magic"]     # read a moment ago: not again
    clock[0] = AGAIN_S
    eff.of_item("goods", 5555)
    assert reads[2:] == ["EquipParamGoods", "Magic"]                                        # a build may have added the row
    assert eff.of_item("weapons", 9000110) == (200,)


def test_without_the_tables_every_buff_is_unmapped_and_the_rest_is_read():
    sp = sampler(rows={})
    s = sp.sample(NOW)
    assert s.state == "CONNECTED" and s.character["buffs"] == {} and s.ignored_buffs == 3 and s.character["inventory"]
    assert "EquipParamGoods" in sp.item_effects.errors


def test_a_buff_of_the_designs_spell_is_given_by_its_held_goods_item():
    inv = sampler().sample(NOW).character["inventory"]
    assert build_index(inv, effects(), {999: 10100, 4242: 777})[999] == [("goods", "10100")]
    assert 4242 not in build_index(inv, effects(), {4242: 777})                              # the spell's goods item is not held


def test_the_game_tables_name_a_buff_end_to_end():
    m = game()
    put_table(m, "EquipParamGoods", {1200: encode("EquipParamGoods", refCategory=2, refId_default=100, goodsType=0)})
    s = S.Sampler(m, profile(), state_ids(), BASE).sample(NOW)
    assert s.character["buffs"]["100"]["reference"] == ["character.inventory.goods.1200"]
    assert s.character["buffs"]["100"]["type"] == "consumable" and s.ignored_buffs == 2

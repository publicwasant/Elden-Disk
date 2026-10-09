"""Phase 2.2, kinds `enchant` and `buff` with `from`: a copy of the template's Goods and Magic rows AND of the template's own
SpEffect rows (the rows no more than 3 spells of the game reach), pointing at each other, tuned with `set` on SpEffect rows.

Part 1 needs no game data: the design file. Part 2: the recipe on small synthetic tables. Part 3 needs the pristine
regulation.bin (ELDENDISK_REGULATION_ORIG) and is skipped without it."""
import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from eldendisk.extension.innovate_spells import bases, build, chain as chainmod, container, gate, recipes, spec
from eldendisk.extension.innovate_spells.defs import TABLE_FILES, Def
from tests.ext_helpers import param_blob
from tests.z4 import ID as Z4_ID, SPELL as Z4_SPELL, file_of

PKG = Path(spec.__file__).parent
BFB = {"kind": "enchant", "from": 6250}      # Black Flame Blade


def design(**kw):
    return file_of({"black_flame_blade_copy": {**copy.deepcopy(BFB), **kw}})


def problems(d):
    with pytest.raises(spec.SpecError) as e:
        spec.normalise(d)
    return e.value.problems


# ---------------------------------------------------------------- the design file
def test_an_enchant_holds_only_what_the_design_names():
    s = spec.normalise(design())["spells"][0]
    assert s == {"slot": 1, "id": "black_flame_blade_copy", "kind": "enchant", "from": 6250, "name": "", "description": "", "requires": {}}


def test_set_takes_speffect_keys_for_an_enchant_and_a_buff_with_from():
    key = "SpEffect.1626000.effectEndurance"
    s = spec.normalise(design(set={key: 600}))["spells"][0]
    assert s["set"] == {key: 600.0} and isinstance(s["set"][key], float)
    b = spec.normalise(file_of({"b": {"kind": "buff", "from": 6050, "set": {"SpEffect.1605000.effectEndurance": 30}}}))["spells"][0]
    assert b["set"] == {"SpEffect.1605000.effectEndurance": 30.0}


def test_a_clone_refuses_speffect_keys_and_says_why():
    d = file_of({"c": {"kind": "clone", "from": 6210, "set": {"SpEffect.1621000.effectEndurance": 30}}})
    assert any("does not copy them" in p for p in problems(d))


@pytest.mark.parametrize("name", ["replaceSpEffectId", "cycleOccurrenceSpEffectId", "atkOccurrenceSpEffectId", "applyIdOnGetSoul",
                                  "accumuOverFireId", "accumuUnderFireId"])
def test_speffect_link_fields_are_refused(name):
    assert any("links rows" in p for p in problems(design(set={"SpEffect.1626000." + name: 5})))


@pytest.mark.parametrize("key, value, why", [
    ("SpEffect.1626000.nope", 1, "no field 'nope'"),
    ("SpEffect.1626000.effectEndurance", "7", "needs a number"),
    ("SpEffect.1626000", 1, "a key looks like"),
    ("Magic.6230.mp", 1, "row id must be this spell's `from`"),
])
def test_bad_set_keys_on_an_enchant_are_refused(key, value, why):
    assert any(why in p for p in problems(design(set={key: value})))


def test_an_enchant_takes_cost_requirements_shop_and_type():
    s = spec.normalise(design(fp_cost=12, stamina_cost=3, requires={"arcane": 20}, shop={"price": 900}, type="incantation"))["spells"][0]
    assert s["fp_cost"] == 12 and s["requires"] == {"arcane": 20} and s["shop"] == {"price": 900, "stock": 1} and s["type"] == "incantation"


def test_the_heal_over_time_buff_is_untouched_by_the_new_kinds():
    z4 = spec.normalise(file_of({Z4_ID: copy.deepcopy(Z4_SPELL)}))["spells"][0]
    assert "kind" not in z4 and "from" not in z4 and z4["effect"]["heal_hp_per_tick"] == 60
    assert not recipes.is_template(z4) and not recipes.needs_chain(z4)


def test_what_needs_the_chain_reader():
    for kind, need in (("clone", False), ("enchant", True), ("buff", True)):
        assert recipes.needs_chain({"kind": kind, "from": 1}) is need


def test_the_schema_and_the_validator_agree_on_enchants():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((PKG / "spells.schema.json").read_text(encoding="utf-8"))
    cases = [design(), design(fp_cost=5, shop={"price": 10}), design(set={"SpEffect.1626000.effectEndurance": 600}),
             design(set={"SpEffect.1626000.effectEndurance": "600"}), design(set={"SpEffect.1626000": 6}),
             design(set={"Bullet.1.life": 1}), design(effect={}), design(**{"from": 0}),
             file_of({"b": {"kind": "buff", "from": 6050}}), file_of({"b": {"kind": "buff", "from": 6050, "set": {"SpEffect.1605000.effectEndurance": 9}}}),
             file_of({"b": {"kind": "buff", "from": 6050, "cast_motion": "black-flame-blade"}}), file_of({"b": {"kind": "enchant"}})]
    for d in cases:
        ok_schema = jsonschema.Draft202012Validator(schema).is_valid(d)
        try:
            spec.normalise(d)
            ok_code = True
        except spec.SpecError:
            ok_code = False
        assert ok_schema == ok_code, d


# ---------------------------------------------------------------- the recipe on small synthetic tables
def _row(D, key, **kw):
    r = bytearray(D[key].size)
    for k, v in kw.items():
        D[key].set(r, k, v)
    return bytes(r)


def _tables(enchant=1, refs=((2, 1000),), extra_sp=()):
    """Magic 6210 (+ Goods) calls `refs`; SpEffect 1000 -> (cycle) 1001 -> (atk) 500; 500 is reached by five other Magic rows, so it
    is generic. `extra_sp`: more own rows, each linked from the previous one."""
    D = {k: Def(k) for k in TABLE_FILES}
    m = {"mp": 40, "isEnchant": enchant, "castSfxId": 3}
    for n, (cat, rid) in enumerate(refs, 1):
        m["refCategory%d" % n], m["refId%d" % n] = cat, rid
    magic = [(6210, _row(D, "magic", **m))] + [(7000 + i, _row(D, "magic", refCategory1=2, refId1=500)) for i in range(5)]
    sp = [(1000, _row(D, "sp", effectEndurance=7.0, cycleOccurrenceSpEffectId=1001, iconId=11)),
          (1001, _row(D, "sp", effectEndurance=5.0, atkOccurrenceSpEffectId=500)), (500, _row(D, "sp", effectEndurance=1.0))]
    prev = 1001
    for new in extra_sp:
        sp.append((new, _row(D, "sp", effectEndurance=2.0)))
        row = dict(sp)[prev]
        r = bytearray(row)
        D["sp"].set(r, "replaceSpEffectId", new)
        sp[[i for i, x in enumerate(sp) if x[0] == prev][0]] = (prev, bytes(r))
        prev = new
    P = {"magic": container.Param(param_blob(sorted(magic), D["magic"].size)),
         "goods": container.Param(param_blob([(6210, _row(D, "goods", goodsType=18, sortId=9))], D["goods"].size)),
         "sp": container.Param(param_blob(sorted(sp), D["sp"].size)),
         "shop": container.Param(param_blob([(recipes.SHOP_CLONE, bytes(D["shop"].size))], D["shop"].size))}
    bullet = container.Param(param_blob([(1, bytes(chainmod.BULLET["size"]))], chainmod.BULLET["size"]))
    atk = container.Param(param_blob([(1, bytes(chainmod.ATK["size"]))], chainmod.ATK["size"]))
    return P, D, chainmod.Chain(P, D, bullet, atk)


def _spell(**kw):
    return {"slot": 2, "id": "e", "kind": "enchant", "from": 6210, "requires": {}, **kw}


def test_the_chain_reader_finds_own_and_generic_rows():
    _P, _D, C = _tables()
    assert C.refs(6210) == [(1, "sp", 1000)] and C.closure(6210)["sp"] == {1000, 1001, 500}
    assert C.reach("sp", 1000) == 1 and C.reach("sp", 500) == 6


def test_an_enchant_copies_its_own_rows_into_the_slots_block_and_leaves_the_generic_row_shared():
    P, D, C = _tables()
    b = recipes.template_rows(P, D, _spell(), C)
    base = recipes.slot_rows(2)["sp_copy_base"]
    assert b.own == {1000: base, 1001: base + 1} and [i for i, _ in b.sp] == [base, base + 1]
    assert D["magic"].get(b.magic, "refId1") == base and D["magic"].get(b.magic, "refCategory1") == 2
    first, second = (D["sp"].get(b.sp[0][1], "cycleOccurrenceSpEffectId"), D["sp"].get(b.sp[1][1], "atkOccurrenceSpEffectId"))
    assert first == base + 1 and second == 500            # the link between the copies is remapped, the generic row is not copied


def test_the_copies_equal_the_templates_rows_except_the_remapped_links_and_the_set_fields():
    P, D, C = _tables()
    b = recipes.template_rows(P, D, _spell(set={"SpEffect.1000.effectEndurance": 600.0}), C)
    old, new = bytes(P["sp"].find(1000)[2]), b.sp[0][1]
    diff = sorted(n for n in D["sp"].order if D["sp"].fields[n][5] == 1 and D["sp"].get(old, n) != D["sp"].get(new, n))
    assert diff == ["cycleOccurrenceSpEffectId", "effectEndurance"] and D["sp"].get(new, "effectEndurance") == 600.0
    assert D["sp"].get(b.sp[1][1], "effectEndurance") == 5.0


def test_set_on_a_row_that_is_not_copied_says_why():
    P, D, C = _tables()
    with pytest.raises(recipes.RecipeError, match="shared with 6 spells of the game and is not copied"):
        recipes.template_rows(P, D, _spell(set={"SpEffect.500.effectEndurance": 9.0}), C)
    with pytest.raises(recipes.RecipeError, match="not part of the chain of 6210"):
        recipes.template_rows(P, D, _spell(set={"SpEffect.4242.effectEndurance": 9.0}), C)


def test_magic_and_goods_set_keys_still_work_on_an_enchant():
    P, D, C = _tables()
    b = recipes.template_rows(P, D, _spell(fp_cost=11, set={"Magic.6210.castSfxId": 8, "Goods.6210.sortId": 4}), C)
    assert D["magic"].get(b.magic, "castSfxId") == 8 and D["magic"].get(b.magic, "mp") == 11 and D["goods"].get(b.goods, "sortId") == 4


def test_the_kind_must_match_what_the_template_is():
    P, D, C = _tables(enchant=0)
    with pytest.raises(recipes.RecipeError, match="not a weapon or shield enchant"):
        recipes.template_rows(P, D, _spell(), C)
    recipes.template_rows(P, D, _spell(kind="buff"), C)
    P, D, C = _tables(enchant=1)
    with pytest.raises(recipes.RecipeError, match="is an enchant: use kind enchant"):
        recipes.template_rows(P, D, _spell(kind="buff"), C)


def test_a_shield_enchant_counts_as_an_enchant():
    P, D, C = _tables(enchant=0)
    m = bytearray(P["magic"].find(6210)[2])
    D["magic"].set(m, "isShieldEnchant", 1)
    P["magic"] = container.Param(param_blob([(r[0], bytes(m) if r[0] == 6210 else bytes(r[2])) for r in P["magic"].rows], D["magic"].size))
    C = chainmod.Chain(P, D, container.Param(param_blob([(1, bytes(272))], 272)), container.Param(param_blob([(1, bytes(456))], 456)))
    recipes.template_rows(P, D, _spell(), C)


def test_a_template_that_calls_more_than_effects_is_refused_with_the_table_names():
    P, D, C = _tables(refs=((2, 1000), (1, 5)))
    C.rows["bullet"][5] = bytes(272)
    with pytest.raises(recipes.RecipeError, match="not only SpEffect rows"):
        recipes.template_rows(P, D, _spell(), C)


def test_a_chain_longer_than_the_slots_block_is_refused():
    P, D, C = _tables(extra_sp=range(3000, 3000 + recipes.COPY_SP_BLOCK))
    with pytest.raises(recipes.RecipeError, match="room for 8"):
        recipes.template_rows(P, D, _spell(), C)
    P, D, C = _tables(extra_sp=range(3000, 3000 + recipes.COPY_SP_BLOCK - 2))
    assert len(recipes.template_rows(P, D, _spell(), C).sp) == recipes.COPY_SP_BLOCK


def test_blocks_of_different_slots_do_not_overlap_the_other_pools():
    seen = set()
    for n in range(1, 65):
        block = set(range(recipes.slot_rows(n)["sp_copy_base"], recipes.slot_rows(n)["sp_copy_base"] + recipes.COPY_SP_BLOCK))
        assert not block & seen
        seen |= block
    assert min(seen) > recipes.POISE_BASE + 64 and max(seen) < 21960000


def test_an_enchant_adds_goods_magic_speffect_and_shop_rows_only():
    P, D, C = _tables()
    jobs, fp = recipes.make_rows(P, D, [_spell(slot=1, shop={"price": 10, "stock": 1})], C)
    ids = recipes.slot_rows(1)
    assert sorted(jobs) == ["EquipParamGoods", "Magic", "ShopLineupParam", "SpEffectParam"]
    assert fp.added == {"goods": {ids["goods"]}, "magic": {ids["magic"]}, "sp": {ids["sp_copy_base"], ids["sp_copy_base"] + 1},
                        "shop": {ids["shop_line"]}}
    assert not any(fp.removed.values()) and not any(fp.modified.values())


def test_a_buff_next_to_the_heal_over_time_spell_keeps_both_slots_rows():
    P, D, C = _tables(enchant=0)
    z4 = spec.normalise(file_of({Z4_ID: copy.deepcopy(Z4_SPELL)}))["spells"][0]
    P["sp"] = container.Param(param_blob(sorted([(r[0], bytes(r[2])) for r in P["sp"].rows] + [(recipes.HEAL_SP, bytes(D["sp"].size)),
                                                    (recipes.FLAME_SP, bytes(D["sp"].size)), (recipes.ENDURE_SP, bytes(D["sp"].size))]),
                                         D["sp"].size))
    P["magic"] = container.Param(param_blob(sorted([(r[0], bytes(r[2])) for r in P["magic"].rows] + [(recipes.CAST_FROM, bytes(D["magic"].size))]),
                                            D["magic"].size))
    P["goods"] = container.Param(param_blob(sorted([(r[0], bytes(r[2])) for r in P["goods"].rows] + [(recipes.HEAL_GOODS, bytes(D["goods"].size)),
                                                    (recipes.ICON_GOODS, bytes(D["goods"].size))]), D["goods"].size))
    jobs, fp = recipes.make_rows(P, D, [z4, _spell(kind="buff")], C)
    one = recipes.slot_rows(1)
    assert one["sp_effect"] in fp.added["sp"] and recipes.slot_rows(2)["sp_copy_base"] in fp.added["sp"]
    assert one["sp_effect"] not in range(recipes.slot_rows(2)["sp_copy_base"], recipes.slot_rows(2)["sp_copy_base"] + 8)


# ---------------------------------------------------------------- the real thing
ORIG = os.environ.get("ELDENDISK_REGULATION_ORIG")
golden = pytest.mark.skipif(not ORIG or not Path(ORIG).is_file(), reason="set ELDENDISK_REGULATION_ORIG to the pristine regulation.bin")


@pytest.fixture(scope="module")
def base():
    data = Path(ORIG).read_bytes()
    assert hashlib.sha256(data).hexdigest() == bases.BASES[bases.CURRENT_BASE]
    return data


@pytest.fixture(scope="module")
def src(base):
    return build.prepare(base)


def _orig(src):
    bnd = container.Bnd4(src.body)
    D = {k: Def(k) for k in TABLE_FILES}
    P = {k: container.Param(bnd.get(f).data) for k, f in TABLE_FILES.items()}
    return P, D, chainmod.load(bnd, P, D)


def _file_tables(data):
    import struct
    from eldendisk.extension.innovate_spells import zstd
    dcx = container.decrypt(data)
    body = zstd.decode_frame(dcx[0x4C:0x4C + struct.unpack(">I", dcx[0x20:0x24])[0]])
    bnd = container.Bnd4(body)
    D = {k: Def(k) for k in TABLE_FILES}
    return {k: container.ParamView(bnd.get(f).data, D[k].size) for k, f in TABLE_FILES.items()}, D


def _spells(*items):
    return spec.normalise(file_of({"spell_%d" % i: it for i, it in enumerate(items, 1)}))["spells"]


@pytest.fixture(scope="module")
def blade(base, src):
    sp = _spells({**BFB, "fp_cost": 20, "shop": {"price": 1000, "stock": -1}, "set": {"SpEffect.1626000.effectEndurance": 600}})
    return sp, build.build(base, sp, src)


@golden
def test_the_chain_of_the_real_templates(src):
    P, D, C = _orig(src)
    assert C.closure(6250)["sp"] == {1626000, 1626001} and C.closure(6740)["sp"] == {1674000, 1674001, 1674002}
    assert C.closure(6050)["sp"] == {1605000, 1605001, 1605002}
    assert 500 in C.closure(6320)["sp"] and C.reach("sp", 500) > recipes.SHARED_ABOVE


@golden
def test_a_black_flame_blade_copy_builds_and_passes_the_gate(blade, src):
    sp, res = blade
    assert gate.verify(res.data, src, sp).ok and res.changed_blocks <= 13


@golden
def test_the_copy_lasts_ten_minutes_and_the_original_is_unchanged(blade, src):
    P, D = _file_tables(blade[1].data)
    O, OD, _C = _orig(src)
    ids = recipes.slot_rows(1)
    a, b = ids["sp_copy_base"], ids["sp_copy_base"] + 1
    assert D["sp"].get(P["sp"].find(a)[2], "effectEndurance") == 600.0 and D["sp"].get(O["sp"].find(1626000)[2], "effectEndurance") == 7.0
    assert D["sp"].get(P["sp"].find(1626000)[2], "effectEndurance") == 7.0       # the game's own row is untouched
    m = P["magic"].find(ids["magic"])[2]
    assert D["magic"].get(m, "refId1") == a
    for new in (a, b):
        assert not {D["sp"].get(P["sp"].find(new)[2], n) for n in chainmod.SP_LINKS} & {1626000, 1626001}      # no pointer back at the template


@golden
def test_the_copies_equal_the_templates_except_remapped_ids_and_set_fields(blade, src):
    P, D = _file_tables(blade[1].data)
    O, _OD, _C = _orig(src)
    ids = recipes.slot_rows(1)
    for old, new in ((1626000, ids["sp_copy_base"]), (1626001, ids["sp_copy_base"] + 1)):
        d = sorted(n for n in D["sp"].order if D["sp"].fields[n][5] == 1 and D["sp"].get(P["sp"].find(new)[2], n) != D["sp"].get(O["sp"].find(old)[2], n))
        assert set(d) <= {"effectEndurance", "cycleOccurrenceSpEffectId", "atkOccurrenceSpEffectId", "replaceSpEffectId"}, d
    assert D["sp"].get(P["sp"].find(ids["sp_copy_base"] + 1)[2], "effectEndurance") == D["sp"].get(O["sp"].find(1626001)[2], "effectEndurance")


@golden
def test_nothing_that_exists_is_changed_and_the_rows_added_are_exactly_the_footprint(blade, src):
    P, _ = _file_tables(blade[1].data)
    O, _OD, _C = _orig(src)
    for k, extra in (("goods", 1), ("magic", 1), ("shop", 1), ("sp", 2)):
        old = {r[0]: bytes(r[2]) for r in O[k].rows}
        new = {r[0]: bytes(r[2]) for r in P[k].rows}
        assert all(new[i] == b for i, b in old.items()) and len(new) - len(old) == extra


@golden
def test_a_shield_enchant_and_a_buff_build_and_pass_the_gate(base, src):
    sp = _spells({"kind": "enchant", "from": 6740, "fp_cost": 15}, {"kind": "buff", "from": 6050, "fp_cost": 9})
    res = build.build(base, sp, src)
    assert gate.verify(res.data, src, sp).ok and res.changed_blocks <= 13
    P, D = _file_tables(res.data)
    assert len([r for r in P["sp"].rows if recipes.COPY_SP_BASE <= r[0] < 21960000]) == 3 + 3


@golden
def test_every_enchant_and_buff_template_of_the_game_builds_and_passes_the_gate_in_a_slot(base, src):
    P, D, C = _orig(src)
    done = 0
    for r in P["magic"].rows:
        mid = r[0]
        g = P["goods"].find(mid)
        refs = C.refs(mid)
        if g is None or not refs or any(t != "sp" for _n, t, _i in refs) or D["goods"].get(g[2], "goodsType") not in recipes.GOODS_TYPES:
            continue
        kind = "enchant" if D["magic"].get(r[2], "isEnchant") or D["magic"].get(r[2], "isShieldEnchant") else "buff"
        own = [i for i in C.closure(mid)["sp"] if C.reach("sp", i) <= recipes.SHARED_ABOVE]
        if len(own) > recipes.COPY_SP_BLOCK:
            continue
        recipes.template_rows(P, D, {"slot": 3, "id": "x", "kind": kind, "from": mid, "requires": {}}, C)
        done += 1
    assert done >= 20


@golden
def test_a_non_enchant_is_refused_by_kind_enchant_and_the_other_way_round(src):
    with pytest.raises(build.BuildError, match="not a weapon or shield enchant"):
        build.plan(src, _spells({"kind": "enchant", "from": 6050}))
    with pytest.raises(build.BuildError, match="is an enchant"):
        build.plan(src, _spells({"kind": "buff", "from": 6250}))
    with pytest.raises(build.BuildError, match="not only SpEffect rows"):
        build.plan(src, _spells({"kind": "buff", "from": 6210}))


@golden
def test_a_set_on_a_generic_row_is_refused_with_a_reason(src):
    with pytest.raises(build.BuildError, match="is shared with .* spells of the game and is not copied"):
        build.plan(src, _spells({"kind": "enchant", "from": 6320, "set": {"SpEffect.500.effectEndurance": 9}}))


@golden
def test_the_heal_over_time_spell_in_slot_1_is_the_same_next_to_an_enchant(base, src):
    z4 = copy.deepcopy(Z4_SPELL)
    both = spec.normalise(file_of({Z4_ID: z4, "e": copy.deepcopy(BFB)}))["spells"]
    alone = both[:1]
    a, b = build.build(base, both, src), build.build(base, alone, src)
    Pa, _ = _file_tables(a.data)
    Pb, _ = _file_tables(b.data)
    ids = recipes.slot_rows(1)
    for k, rid in (("sp", ids["sp_effect"]), ("sp", ids["poise_sp_effect"]), ("magic", ids["magic"]), ("goods", ids["goods"]), ("shop", ids["shop_line"])):
        assert bytes(Pa[k].find(rid)[2]) == bytes(Pb[k].find(rid)[2])
    assert gate.verify(a.data, src, both).ok


@golden
def test_the_gate_notices_a_copy_that_points_back_at_the_template(blade, src):
    sp, res = blade
    P, D = _file_tables(res.data)
    O, _OD, C = _orig(src)
    ids = recipes.slot_rows(1)
    D["magic"].set(P["magic"].find(ids["magic"])[2], "refId1", 1626000)
    bad = recipes.check_template(P, D, sp[0], O, C)
    assert any("still calls the template's SpEffect 1626000" in p for p in bad)


@golden
def test_the_gate_notices_a_copy_that_is_no_longer_the_template_with_only_the_design_fields(blade, src):
    sp, res = blade
    P, D = _file_tables(res.data)
    O, _OD, C = _orig(src)
    row = P["sp"].find(recipes.slot_rows(1)["sp_copy_base"] + 1)[2]
    D["sp"].set(row, "effectEndurance", D["sp"].get(row, "effectEndurance") + 1)
    assert any("effectEndurance" in p and p.startswith("G11") for p in recipes.check_template(P, D, sp[0], O, C))
    row = P["sp"].find(recipes.slot_rows(1)["sp_copy_base"])[2]
    D["sp"].set(row, "effectEndurance", 7.0)
    assert any("effectEndurance" in p for p in recipes.check_template(P, D, sp[0], O, C))


@golden
def test_the_whole_gate_stops_a_flipped_byte_in_an_enchant_file(blade, src):
    sp, res = blade
    bad = bytearray(res.data)
    bad[len(bad) // 2] ^= 1
    assert not gate.verify(bytes(bad), src, sp).ok

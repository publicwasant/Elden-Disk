"""Phase 2.1, kind `clone`: a copy of a game spell's Goods and Magic rows (it keeps the template's chain).

Part 1 needs no game data: the design file (kind, from, set), the recipe on small synthetic tables.
Part 2 needs the pristine regulation.bin (ELDENDISK_REGULATION_ORIG) and is skipped without it: a clone of real spells builds,
passes the gate, equals the template except the fields the design names, and the gate notices a tampered copy."""
import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from eldendisk.extension.innovate_spells import bases, build, container, gate, recipes, spec
from eldendisk.extension.innovate_spells.defs import TABLE_FILES, Def
from tests.ext_helpers import param_blob
from tests.z4 import ID as Z4_ID, SPELL as Z4_SPELL, file_of

PKG = Path(spec.__file__).parent
CLONE = {"kind": "clone", "from": 6210}


def design(**kw):
    s = {**copy.deepcopy(CLONE), **kw}
    return file_of({"copy_of_black_flame": s})


def spell_of(d):
    return d["innovate_spells"]["slots"]["copy_of_black_flame"]


def problems(d):
    with pytest.raises(spec.SpecError) as e:
        spec.normalise(d)
    return e.value.problems


# ---------------------------------------------------------------- the design file
def test_a_clone_holds_only_what_the_design_names():
    s = spec.normalise(design())["spells"][0]
    assert s == {"slot": 1, "id": "copy_of_black_flame", "kind": "clone", "name": "", "description": "", "from": 6210, "requires": {}}


def test_a_clone_takes_cost_requirements_shop_and_set():
    d = design(fp_cost=25, stamina_cost=3, requires={"arcane": 12}, type="incantation", shop={"price": 500},
               set={"Magic.6210.castSfxId": 7, "Goods.6210.maxNum": 3})
    s = spec.normalise(d)["spells"][0]
    assert (s["fp_cost"], s["stamina_cost"], s["requires"], s["type"], s["shop"]) == (25, 3, {"arcane": 12}, "incantation", {"price": 500, "stock": 1})
    assert s["set"] == {"Magic.6210.castSfxId": 7, "Goods.6210.maxNum": 3}


def test_the_canonical_form_is_a_fixed_point_of_the_file_form():
    d = design(fp_cost=25, requires={"faith": 9}, set={"Magic.6210.castSfxId": 7})
    once = spec.normalise(d)
    assert spec.normalise(spec.as_file(once)) == once


def test_a_buff_without_kind_is_unchanged_and_an_explicit_buff_is_the_same_design():
    plain = spec.normalise(file_of({Z4_ID: Z4_SPELL}))
    explicit = spec.normalise(file_of({Z4_ID: {**Z4_SPELL, "kind": "buff"}}))
    assert plain == explicit and "kind" not in plain["spells"][0]
    assert spec.build_view(plain) == spec.build_view(explicit)


def test_a_clone_and_a_buff_can_share_one_file():
    d = file_of({Z4_ID: Z4_SPELL, "copy_of_black_flame": copy.deepcopy(CLONE)})
    kinds = [s.get("kind", "buff") for s in spec.normalise(d)["spells"]]
    assert kinds == ["buff", "clone"]


@pytest.mark.parametrize("kind", ["projectile", "attack"])
def test_the_kinds_that_are_planned_are_refused_by_name(kind):
    assert any("planned but not built yet" in p for p in problems(design(kind=kind)))


def test_an_unknown_kind_is_refused():
    assert any(".kind" in p and "must be one of" in p for p in problems(design(kind="spell")))


@pytest.mark.parametrize("change, where", [
    (lambda s: s.pop("from"), ".from: missing"),
    (lambda s: s.update({"from": "6210"}), ".from"),
    (lambda s: s.update({"from": 0}), ".from"),
    (lambda s: s.update({"from": True}), ".from"),
    (lambda s: s.update(type="spell"), ".type"),
    (lambda s: s.update(fp_cost=1000), ".fp_cost"),
    (lambda s: s.update(requires={"strength": 5}), ".requires.strength"),
    (lambda s: s.update(requires={"faith": 100}), ".requires.faith"),
    (lambda s: s.update(effect={}), ".effect: unknown field"),
    (lambda s: s.update(cast_motion="x"), ".cast_motion: unknown field"),
    (lambda s: s.update(shop={"price": 0}), ".shop.price"),
    (lambda s: s.update(icon_file="a.png"), "Level 3"),
    (lambda s: s.update(set=[1]), ".set: must be an object"),
])
def test_a_bad_clone_is_refused_with_the_path_of_the_problem(change, where):
    s = copy.deepcopy(CLONE)
    change(s)
    assert any(where in p for p in problems(file_of({"copy_of_black_flame": s})))


def test_a_buff_without_from_does_not_take_set():
    s = copy.deepcopy(Z4_SPELL)
    s["set"] = {}
    assert any(".set: unknown field" in p for p in problems(file_of({Z4_ID: s})))


def test_a_buff_with_from_is_a_template_spell_and_cannot_mix_with_the_heal_over_time_fields():
    ok = spec.normalise(file_of({"b": {"kind": "buff", "from": 6050, "fp_cost": 5}}))["spells"][0]
    assert ok["kind"] == "buff" and ok["from"] == 6050 and "effect" not in ok
    bad = problems(file_of({"b": {"kind": "buff", "from": 6050, "effect": {}, "cast_motion": "black-flame-blade"}}))
    assert any(".effect: unknown field" in p for p in bad) and any(".cast_motion: unknown field" in p for p in bad)


@pytest.mark.parametrize("key, value, why", [
    ("Magic.6210", 1, "a key looks like"),
    ("Bullet.10621000.life", 3.0, "a key looks like"),
    ("Magic.6230.mp", 1, "row id must be this spell's `from`"),
    ("Magic.6210.nope", 1, "no field 'nope'"),
    ("Magic.6210.castSfxId", "7", "needs a number"),
    ("Magic.6210.castSfxId", 2.5, "whole-number field"),
    ("Magic.6210.requirementFaith", 300, "must be from 0 to 255"),
    ("Magic.6210.isEnchant", 2, "must be from 0 to 1"),
    ("Magic.6210.refId1", 5, "links rows"),
    ("Magic.6210.refCategory1", 1, "links rows"),
    ("Goods.6210.goodsType", 5, "links rows"),
    ("Goods.6210.refId_default", 5, "links rows"),
    ("Magic.6210.mp", 5, "friendly field"),
    ("Magic.6210.requirementLuck", 5, "requires.arcane"),
])
def test_set_refuses_what_it_should(key, value, why):
    assert any(why in p for p in problems(design(set={key: value})))


def test_set_floats_stay_floats_and_whole_numbers_given_as_floats_become_whole():
    s = spec.normalise(design(set={"Magic.6210.castSfxId": 7.0, "Goods.6210.weight": 2}))["spells"][0]
    assert s["set"]["Magic.6210.castSfxId"] == 7 and isinstance(s["set"]["Magic.6210.castSfxId"], int)
    assert isinstance(s["set"]["Goods.6210.weight"], float)


def test_the_schema_and_the_validator_agree_on_clones():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((PKG / "spells.schema.json").read_text(encoding="utf-8"))
    cases = [design(), design(fp_cost=25, requires={"arcane": 12}, shop={"price": 500}, type="sorcery"),
             design(set={"Magic.6210.castSfxId": 7}), design(kind="projectile"), design(kind="enchant"), design(kind="buff"),
             design(fp_cost=1000), design(requires={"faith": 100}), design(type="spell"), design(surprise=1), design(**{"from": 0}),
             design(set={"Bullet.1.life": 1}), design(set={"Magic.6210.castSfxId": "7"}), design(effect={}),
             file_of({"x": {"kind": "clone"}}), file_of({Z4_ID: {**Z4_SPELL, "from": 6050}}), file_of({Z4_ID: {**Z4_SPELL, "kind": "buff"}})]
    for d in cases:
        ok_schema = jsonschema.Draft202012Validator(schema).is_valid(d)
        try:
            spec.normalise(d)
            ok_code = True
        except spec.SpecError:
            ok_code = False
        assert ok_schema == ok_code, d


def test_a_changed_clone_changes_what_decides_the_build():
    a = spec.build_view(spec.normalise(design(fp_cost=25)))
    b = spec.build_view(spec.normalise(design(fp_cost=26)))
    c = spec.build_view(spec.normalise(design(fp_cost=25, name="Another name")))
    assert a != b and a == c


# ---------------------------------------------------------------- the recipe on small synthetic tables
def _tables(goods_type=18, with_goods=True, magic_id=6210):
    D = {k: Def(k) for k in TABLE_FILES}
    magic = bytearray(D["magic"].size)
    D["magic"].set(magic, "mp", 40)
    D["magic"].set(magic, "stamina", 5)
    D["magic"].set(magic, "requirementIntellect", 20)
    D["magic"].set(magic, "requirementLuck", 7)
    D["magic"].set(magic, "refCategory1", 1)
    D["magic"].set(magic, "refId1", 10621000)
    D["magic"].set(magic, "castSfxId", 3)
    goods = bytearray(D["goods"].size)
    D["goods"].set(goods, "goodsType", goods_type)
    D["goods"].set(goods, "sortId", 77)
    D["goods"].set(goods, "refId_default", -1)
    other = bytearray(D["magic"].size)
    P = {"magic": container.Param(param_blob([(magic_id, bytes(magic)), (magic_id + 10, bytes(other))], D["magic"].size)),
         "goods": container.Param(param_blob(([(magic_id, bytes(goods))] if with_goods else []) + [(magic_id + 10, bytes(D["goods"].size))],
                                              D["goods"].size))}
    return P, D


def _spell(**kw):
    return {"slot": 2, "id": "c", "kind": "clone", "from": 6210, "requires": {}, **kw}


def test_nothing_named_means_both_rows_are_the_templates_rows():
    P, D = _tables()
    g, m = recipes.template_rows(P, D, _spell())[:2]
    assert g == bytes(P["goods"].find(6210)[2]) and m == bytes(P["magic"].find(6210)[2])


def test_the_named_fields_are_written_and_nothing_else_changes():
    P, D = _tables()
    before_g, before_m = bytes(P["goods"].find(6210)[2]), bytes(P["magic"].find(6210)[2])
    sp = _spell(fp_cost=25, stamina_cost=0, requires={"intelligence": 5, "faith": 6, "arcane": 8},
                set={"Magic.6210.castSfxId": 9, "Goods.6210.sortId": 5})
    g, m = recipes.template_rows(P, D, sp)[:2]
    assert [D["magic"].get(m, n) for n in ("mp", "stamina", "requirementIntellect", "requirementFaith", "requirementLuck", "castSfxId")] == [25, 0, 5, 6, 8, 9]
    assert D["goods"].get(g, "sortId") == 5
    assert D["magic"].get(m, "refId1") == 10621000 and D["magic"].get(m, "refCategory1") == 1       # still the template's chain
    changed = [n for n in D["magic"].order if D["magic"].fields[n][5] == 1 and D["magic"].get(m, n) != D["magic"].get(before_m, n)]
    assert sorted(changed) == sorted(["mp", "stamina", "requirementIntellect", "requirementFaith", "requirementLuck", "castSfxId"])
    assert [n for n in D["goods"].order if D["goods"].fields[n][5] == 1 and D["goods"].get(g, n) != D["goods"].get(before_g, n)] == ["sortId"]


def test_the_template_in_the_tables_is_not_changed():
    P, D = _tables()
    snap = {k: [(r[0], bytes(r[2])) for r in P[k].rows] for k in P}
    recipes.template_rows(P, D, _spell(fp_cost=1, set={"Goods.6210.sortId": 1}))
    assert snap == {k: [(r[0], bytes(r[2])) for r in P[k].rows] for k in P}


def test_a_magic_row_that_does_not_exist_is_refused():
    P, D = _tables()
    with pytest.raises(recipes.RecipeError, match="not a Magic row"):
        recipes.template_rows(P, D, _spell(**{"from": 1234}))


def test_a_spell_without_a_goods_row_is_refused_as_an_npc_spell():
    P, D = _tables(with_goods=False)
    with pytest.raises(recipes.RecipeError, match="no Goods row"):
        recipes.template_rows(P, D, _spell())


def test_a_goods_row_that_is_not_a_spell_is_refused():
    P, D = _tables(goods_type=0)
    with pytest.raises(recipes.RecipeError, match="not a spell"):
        recipes.template_rows(P, D, _spell())


@pytest.mark.parametrize("goods_type, ok, bad", [(5, "sorcery", "incantation"), (17, "sorcery", "incantation"),
                                                  (16, "incantation", "sorcery"), (18, "incantation", "sorcery")])
def test_the_type_follows_the_template_and_cannot_be_changed(goods_type, ok, bad):
    P, D = _tables(goods_type=goods_type)
    recipes.template_rows(P, D, _spell(type=ok))
    with pytest.raises(recipes.RecipeError, match="cannot change `type`"):
        recipes.template_rows(P, D, _spell(type=bad))


def test_a_clone_adds_goods_magic_and_a_shop_line_only():
    P, D = _tables()
    P["shop"] = container.Param(param_blob([(recipes.SHOP_CLONE, bytes(D["shop"].size))], D["shop"].size))
    jobs, fp = recipes.make_rows(P, D, [_spell(slot=1, shop={"price": 10, "stock": 1})])
    assert sorted(jobs) == ["EquipParamGoods", "Magic", "ShopLineupParam"]
    ids = recipes.slot_rows(1)
    assert fp.added == {"goods": {ids["goods"]}, "magic": {ids["magic"]}, "sp": set(), "shop": {ids["shop_line"]}}
    assert not any(fp.removed.values()) and not any(fp.modified.values())


def test_a_clone_without_a_shop_adds_no_shop_row_and_a_shop_above_slot_7_is_refused():
    P, D = _tables()
    P["shop"] = container.Param(param_blob([(recipes.SHOP_CLONE, bytes(D["shop"].size))], D["shop"].size))
    jobs, _ = recipes.make_rows(P, D, [_spell(slot=8)])
    assert "ShopLineupParam" not in jobs
    with pytest.raises(recipes.RecipeError, match="no shop line"):
        recipes.make_rows(P, D, [_spell(slot=8, shop={"price": 10, "stock": 1})])


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
    return {k: container.Param(bnd.get(f).data) for k, f in TABLE_FILES.items()}, D


def _file_tables(data):
    import struct
    from eldendisk.extension.innovate_spells import zstd
    dcx = container.decrypt(data)
    body = zstd.decode_frame(dcx[0x4C:0x4C + struct.unpack(">I", dcx[0x20:0x24])[0]])
    bnd = container.Bnd4(body)
    D = {k: Def(k) for k in TABLE_FILES}
    return {k: container.ParamView(bnd.get(f).data, D[k].size) for k, f in TABLE_FILES.items()}, D


def _spells(*items, maximum=64):
    slots = {}
    for i, it in enumerate(items, 1):
        slots["spell_%d" % i] = it
    return spec.normalise(file_of(slots, maximum))["spells"]


@pytest.fixture(scope="module")
def black_flame(base, src):
    sp = _spells({**CLONE, "fp_cost": 20, "requires": {"intelligence": 10, "faith": 10}, "shop": {"price": 1000, "stock": -1},
                  "set": {"Goods.6210.sortId": 1234}})
    return sp, build.build(base, sp, src)


@golden
def test_a_clone_of_black_flame_builds_and_passes_the_gate(black_flame, src):
    sp, res = black_flame
    assert gate.verify(res.data, src, sp).ok and res.changed_blocks <= 13


@golden
def test_the_clone_rows_are_the_templates_rows_with_only_the_named_fields_changed(black_flame, src):
    P, D = _file_tables(black_flame[1].data)
    O, _ = _orig(src)
    ids = recipes.slot_rows(1)
    m, tm = bytes(P["magic"].find(ids["magic"])[2]), bytes(O["magic"].find(6210)[2])
    g, tg = bytes(P["goods"].find(ids["goods"])[2]), bytes(O["goods"].find(6210)[2])
    diff = lambda d, a, b: sorted(n for n in d.order if d.fields[n][5] == 1 and d.get(a, n) != d.get(b, n))
    assert diff(D["magic"], m, tm) == sorted(["mp", "requirementIntellect", "requirementFaith"])
    assert diff(D["goods"], g, tg) == ["sortId"] and D["goods"].get(g, "sortId") == 1234
    for i in range(1, 11):       # the chain is the template's own: the clone calls the game's Black Flame rows
        assert D["magic"].get(m, "refId%d" % i) == D["magic"].get(tm, "refId%d" % i)
    assert D["magic"].get(m, "refCategory1") == 1 and D["magic"].get(m, "refId1") == D["magic"].get(tm, "refId1") != ids["magic"]


@golden
def test_a_clone_adds_exactly_one_goods_one_magic_and_one_shop_row_and_touches_nothing_else(black_flame, src):
    P, _ = _file_tables(black_flame[1].data)
    O, _ = _orig(src)
    for k, extra in (("goods", 1), ("magic", 1), ("shop", 1), ("sp", 0)):
        old = {r[0]: bytes(r[2]) for r in O[k].rows}
        new = {r[0]: bytes(r[2]) for r in P[k].rows}
        assert all(new[i] == b for i, b in old.items()) and len(new) - len(old) == extra


@golden
def test_a_clone_of_a_sorcery_is_a_sorcery_and_its_type_cannot_be_changed(base, src):
    P, D = _orig(src)
    assert D["goods"].get(P["goods"].find(4000)[2], "goodsType") in (5, 17)
    res = build.build(base, _spells({"kind": "clone", "from": 4000, "type": "sorcery", "fp_cost": 3}), src)
    assert res.changed_blocks <= 13
    with pytest.raises(build.BuildError, match="cannot change `type`"):
        build.plan(src, _spells({"kind": "clone", "from": 4000, "type": "incantation"}))


@golden
def test_a_magic_row_of_an_npc_has_no_goods_and_is_refused(src):
    P, D = _orig(src)
    npc = next(r[0] for r in P["magic"].rows if P["goods"].find(r[0]) is None)
    with pytest.raises(build.BuildError, match="no Goods row"):
        build.plan(src, _spells({"kind": "clone", "from": npc}))


@golden
def test_a_clone_in_slot_8_builds_without_a_shop(base, src):
    items = [None] * 7 + [{**CLONE, "fp_cost": 5}]
    sp = _spells(*items)
    assert sp[0]["slot"] == 8
    assert gate.verify(build.make(src, sp).data, src, sp).ok


@golden
def test_a_buff_and_a_clone_side_by_side_keep_their_own_rows(base, src):
    z4 = copy.deepcopy(Z4_SPELL)
    sp = spec.normalise(file_of({Z4_ID: z4, "copy": {**CLONE, "shop": {"price": 5}}}))["spells"]
    res = build.build(base, sp, src)
    P, D = _file_tables(res.data)
    assert {1, 2} == {s["slot"] for s in sp}
    assert P["sp"].find(recipes.slot_rows(1)["sp_effect"]) is not None and P["goods"].find(recipes.slot_rows(2)["goods"]) is not None
    assert gate.verify(res.data, src, sp).ok
    alone = build.build(base, sp[:1], src)
    assert P["sp"].find(recipes.slot_rows(1)["sp_effect"])[2] == _file_tables(alone.data)[0]["sp"].find(recipes.slot_rows(1)["sp_effect"])[2]


@golden
def test_a_design_for_a_different_template_is_noticed_by_the_gate(black_flame, src):
    sp, res = black_flame
    other = copy.deepcopy(sp)
    other[0]["from"] = 6230
    v = gate.verify(res.data, src, other)
    assert not v.ok


@golden
def test_check_clone_is_quiet_on_the_real_build(black_flame, src):
    sp, res = black_flame
    P, D = _file_tables(res.data)
    O, _ = _orig(src)
    assert recipes.check_template(P, D, sp[0], O) == []


@golden
def test_check_clone_notices_a_changed_byte_in_the_copy(black_flame, src):
    sp, res = black_flame
    P, D = _file_tables(res.data)
    O, _ = _orig(src)
    row = P["magic"].find(recipes.slot_rows(1)["magic"])[2]
    D["magic"].set(row, "castSfxId", D["magic"].get(row, "castSfxId") + 1)
    bad = recipes.check_template(P, D, sp[0], O)
    assert any("castSfxId" in p and p.startswith("G11") for p in bad)


@golden
def test_check_clone_notices_a_wrong_cost_and_a_wrong_goods_row(black_flame, src):
    sp, res = black_flame
    P, D = _file_tables(res.data)
    O, _ = _orig(src)
    D["magic"].set(P["magic"].find(recipes.slot_rows(1)["magic"])[2], "mp", 21)
    D["goods"].set(P["goods"].find(recipes.slot_rows(1)["goods"])[2], "goodsType", 5)
    bad = recipes.check_template(P, D, sp[0], O)
    assert any(p.startswith("G5") and "mp" in p for p in bad) and any("Goods" in p and "goodsType" in p for p in bad)


@golden
def test_check_clone_notices_a_reused_stock_flag_and_a_missing_shop_line(black_flame, src):
    sp, res = black_flame
    P, D = _file_tables(res.data)
    O, _ = _orig(src)
    other = next(r for r in P["shop"].rows if r[0] != recipes.slot_rows(1)["shop_line"])
    D["shop"].set(other[2], "eventFlag_forStock", recipes.slot_rows(1)["shop_flag"])
    assert any(p.startswith("G12") and "used by shop lines" in p for p in recipes.check_template(P, D, sp[0], O))
    nosp = copy.deepcopy(sp[0])
    nosp.pop("shop")
    assert any("has no shop" in p for p in recipes.check_template(P, D, nosp, O))


@golden
def test_the_whole_gate_stops_a_flipped_byte_in_a_clone_file(black_flame, src):
    sp, res = black_flame
    bad = bytearray(res.data)
    bad[len(bad) // 2] ^= 1
    assert not gate.verify(bytes(bad), src, sp).ok

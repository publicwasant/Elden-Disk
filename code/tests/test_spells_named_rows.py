"""1.8.4: a field of a copied row that calls another row may name a row of the game ("Bullet.<id>.spEffectId0": "SpEffect.474"):
the builder copies that row into the slot's own block, after the chain's own rows, and points the field at the copy; keys of the named
row (`SpEffect.474.<field>`) change the copy. The game's row stays as it is (other spells use it).

Part 1: the design file. Part 2: the recipe on the small synthetic tables of test_spells_projectile."""
import pytest

from eldendisk.creative.innovate_spells import recipes, spec
from tests.test_spells_projectile import _spell, _tables, design, problems


# ---------------------------------------------------------------- the design file
def test_a_link_field_takes_the_name_of_a_row_and_keeps_it_as_text():
    s = spec.normalise(design(set={"Bullet.10621000.spEffectId0": " SpEffect.474", "Bullet.10621000.HitBulletID": "Bullet.0010621001",
                                   "SpEffect.474.changeHpRate": 15}))["spells"][0]
    assert s["set"]["Bullet.10621000.spEffectId0"] == "SpEffect.474"
    assert s["set"]["Bullet.10621000.HitBulletID"] == "Bullet.10621001"
    assert s["set"]["SpEffect.474.changeHpRate"] == 15.0


@pytest.mark.parametrize("key, value, why", [
    ("Bullet.10621000.spEffectId0", "Bullet.474", "spEffectId0 calls a SpEffect row, not a Bullet row"),
    ("Bullet.10621000.atkId_Bullet", "SpEffect.68000", "atkId_Bullet calls a AtkParam_Pc row, not a SpEffect row"),
    ("Bullet.10621000.spEffectId0", "474", "links rows (it calls a SpEffect row): name a row of the game, \"SpEffect.<id>\""),
    ("Bullet.10621000.spEffectId0", "Magic.6000", "links rows"),
    ("Bullet.10621000.life", "SpEffect.474", "life is not a field that calls another row"),
    ("Bullet.10621000.spEffectId0", 474, "links rows"),
])
def test_wrong_names_of_rows_are_refused(key, value, why):
    assert any(why in p for p in problems(design(set={key: value})))


def test_magic_and_goods_fields_never_take_a_name():
    assert any("refId1 needs a number" in p for p in problems(design(set={"Magic.6210.refId1": "Bullet.100"})))


def test_the_design_shows_the_name_back():
    d = design(set={"Bullet.10621000.spEffectId0": "SpEffect.474"})
    s = spec.normalise(d)["spells"][0]
    assert spec.design_of(s)["customs"]["basic"]["Bullet.10621000.spEffectId0"] == "SpEffect.474"


# ---------------------------------------------------------------- the recipe
def _with_sp(P, D, extra):
    """The synthetic tables plus SpEffect rows `extra` (id -> fields)."""
    from eldendisk.creative.innovate_spells import chain as chainmod, container
    from tests.spells_helpers import param_blob
    rows = {r[0]: bytes(r[2]) for r in P["sp"].rows}
    for rid, kw in extra.items():
        r = bytearray(D["sp"].size)
        for k, v in kw.items():
            D["sp"].set(r, k, v)
        rows[rid] = bytes(r)
    P["sp"] = container.Param(param_blob(sorted(rows.items()), D["sp"].size))
    return chainmod.Chain(P, D, P["bullet"], P["atk"])


def test_a_named_row_is_copied_after_the_chains_own_and_the_field_points_at_the_copy():
    P, D, _C = _tables()
    C = _with_sp(P, D, {474: {"changeHpRate": 50.0, "changeHpPoint": 300}, 1625: {"bloodAttackPower": 60}})
    b = recipes.template_rows(P, D, _spell(set={"Bullet.100.spEffectId0": "SpEffect.474", "Bullet.100.spEffectId1": "SpEffect.1625",
                                                "SpEffect.474.changeHpRate": 15.0, "SpEffect.474.changeHpPoint": 0}), C)
    ids = recipes.slot_rows(2)
    sb, bb = ids["sp_copy_base"], ids["bullet_copy_base"]
    assert b.own["sp"] == {1000: sb, 474: sb + 1, 1625: sb + 2}
    rows, sps = dict(b.bullet), dict(b.sp)
    assert D["bullet"].get(rows[bb], "spEffectId0") == sb + 1 and D["bullet"].get(rows[bb], "spEffectId1") == sb + 2
    assert D["sp"].get(sps[sb + 1], "changeHpRate") == 15.0 and D["sp"].get(sps[sb + 1], "changeHpPoint") == 0
    assert D["sp"].get(sps[sb + 2], "bloodAttackPower") == 60
    assert D["sp"].get(P["sp"].find(474)[2], "changeHpRate") == 50.0          # the game's row is untouched
    assert D["bullet"].get(rows[bb + 1], "spEffectId0") == sb                  # the chain's own link is still remapped


def test_a_row_the_chain_copies_already_is_not_copied_twice():
    P, D, C = _tables()
    b = recipes.template_rows(P, D, _spell(set={"Bullet.100.spEffectId0": "SpEffect.1000"}), C)
    sb, bb = recipes.slot_rows(2)["sp_copy_base"], recipes.slot_rows(2)["bullet_copy_base"]
    assert b.own["sp"] == {1000: sb} and D["bullet"].get(dict(b.bullet)[bb], "spEffectId0") == sb


def test_a_named_bullet_is_copied_into_the_bullet_block():
    P, D, C = _tables()
    b = recipes.template_rows(P, D, _spell(set={"Bullet.101.HitBulletID": "Bullet.7777", "Bullet.7777.life": 0.5}), C)
    bb = recipes.slot_rows(2)["bullet_copy_base"]
    assert b.own["bullet"] == {100: bb, 101: bb + 1, 200: bb + 2, 7777: bb + 3}
    rows = dict(b.bullet)
    assert D["bullet"].get(rows[bb + 1], "HitBulletID") == bb + 3 and D["bullet"].get(rows[bb + 3], "life") == 0.5
    assert D["bullet"].get(rows[bb + 2], "HitBulletID") == bb + 3          # every copy that called it now calls its copy


def test_two_spells_naming_the_same_row_get_a_copy_each():
    P, D, _C = _tables()
    C = _with_sp(P, D, {474: {"changeHpRate": 50.0}})
    one = recipes.template_rows(P, D, _spell(slot=2, set={"Bullet.100.spEffectId0": "SpEffect.474"}), C)
    two = recipes.template_rows(P, D, _spell(slot=3, set={"Bullet.100.spEffectId0": "SpEffect.474"}), C)
    assert one.own["sp"][474] == recipes.slot_rows(2)["sp_copy_base"] + 1
    assert two.own["sp"][474] == recipes.slot_rows(3)["sp_copy_base"] + 1


def test_a_name_that_is_not_a_row_and_a_full_block_are_refused():
    P, D, C = _tables()
    with pytest.raises(recipes.RecipeError, match="set Bullet.100.spEffectId0: SpEffect.4242 is not a row of this game"):
        recipes.template_rows(P, D, _spell(set={"Bullet.100.spEffectId0": "SpEffect.4242"}), C)
    extra = {5000 + k: {"changeHpRate": 1.0} for k in range(recipes.COPY_SP_BLOCK)}
    C = _with_sp(P, D, extra)
    names = {"Bullet.%d.spEffectId%d" % (b, n): "SpEffect.%d" % (5000 + k)
             for k, (b, n) in enumerate([(100, 0), (100, 1), (100, 2), (100, 3), (100, 4), (200, 0), (200, 1), (200, 2)])}
    with pytest.raises(recipes.RecipeError, match="the slot has room for 8 SpEffect rows"):
        recipes.template_rows(P, D, _spell(set=names), C)


def test_a_key_of_a_row_outside_the_chain_says_how_to_name_it():
    P, D, _C = _tables()
    C = _with_sp(P, D, {474: {"changeHpRate": 50.0}})
    with pytest.raises(recipes.RecipeError, match='a row of the game outside it is copied when a field of a copied row names it.*"SpEffect.474"'):
        recipes.template_rows(P, D, _spell(set={"SpEffect.474.changeHpRate": 15.0}), C)


def test_the_gate_reads_the_named_copies_like_the_others():
    P, D, _C = _tables()
    C = _with_sp(P, D, {474: {"changeHpRate": 50.0}})
    sp = _spell(set={"Bullet.100.spEffectId0": "SpEffect.474", "SpEffect.474.changeHpRate": 15.0})
    a, b = recipes.template_rows(P, D, sp, C), recipes.template_rows(P, D, sp, C)
    assert a.sp == b.sp and a.bullet == b.bullet          # the same rows every time (the gate builds them again to compare)


# ---------------------------------------------------------------- the real thing: Dismantle of creative.json (1.8.4 part 1)
from tests.test_spells_projectile import _file_tables, _orig, base, golden, src  # noqa: E402,F401  (fixtures)


@pytest.fixture(scope="module")
def built(base, src):
    import json
    from pathlib import Path
    from eldendisk.creative.innovate_spells import build
    sp = spec.normalise(json.loads((Path(__file__).parents[1] / "creative.json").read_text(encoding="utf-8")))["spells"]
    return sp, build.build(base, sp, src)


@golden
def test_the_spells_of_creative_json_build_and_pass_the_gate(built, src):
    from eldendisk.creative.innovate_spells import gate, preflight
    sp, res = built
    assert [s["id"] for s in sp] == ["reverse_cursed_technique", "dismantle"] and sp[1]["slot"] == 2
    assert gate.verify(res.data, src, sp).ok and res.changed_blocks <= preflight.MAX_CHANGED_BLOCKS


@golden
def test_dismantle_is_a_fan_of_38_invisible_cuts_100_m_deep_cast_like_catch_flame(built, src):
    P, D = _file_tables(built[1].data)
    ids = recipes.slot_rows(2)
    m = P["magic"].find(ids["magic"])[2]
    fan = P["bullet"].find(D["magic"].get(m, "refId1"))[2]
    assert [D["bullet"].get(fan, n) for n in ("numShoot", "shootAngle", "shootAngleInterval", "sfxId_Bullet", "isPenetrateMap")] == [31, -60, 4, -1, 1]   # 120 degrees
    assert D["bullet"].get(fan, "maxVellocity") * D["bullet"].get(fan, "life") == pytest.approx(100.8, abs=0.01)
    assert (D["bullet"].get(fan, "hitRadius"), D["bullet"].get(fan, "hitRadiusMax")) == (1.5, 3.5)
    assert D["bullet"].get(fan, "sfxId_Hit") == -1            # nothing where a cut ends ...
    blood = P["sp"].find(D["bullet"].get(fan, "spEffectId1"))[2]      # ... the blood is on the ones hit
    assert (D["sp"].get(blood, "vfxId"), D["sp"].get(blood, "changeHpRate"), D["sp"].get(blood, "changeHpPoint"),
            D["sp"].get(blood, "invocationConditionsStateChange1")) == (6, 0.0, 0, 0)
    assert [D["bullet"].get(fan, n) for n in ("lifeRandomRange", "gravityInRange", "gravityOutRange", "accelTime", "damageDamp")] == [0.0] * 4 + [0]
    assert D["sp"].get(P["sp"].find(D["bullet"].get(fan, "spEffectId0"))[2], "bloodAttackPower") == 60
    want = built[0][1]["requires"]                     # the author's balance in creative.json, as written
    assert (D["magic"].get(m, "requirementFaith"), D["magic"].get(m, "requirementLuck"), D["magic"].get(m, "requirementIntellect")) == (
        want.get("faith", 0), want.get("arcane", 0), want.get("intelligence", 0))
    assert D["magic"].get(m, "refType") == 106
    a = P["atk"].find(D["bullet"].get(fan, "atkId_Bullet"))[2]
    assert (D["atk"].get(a, "atkPhys"), D["atk"].get(a, "atkAttribute"), D["atk"].get(a, "atkMaterial")) == (
        built[0][1]["set"]["AtkParam_Pc.68000.atkPhys"], 0, 0)     # the author's number in creative.json; slash; a sword's metal: blood
    assert D["magic"].get(m, "castSfxId") == 4122
    g = P["goods"].find(ids["goods"])[2]
    O, _OD, _C = _orig(src)
    assert D["goods"].get(g, "iconId") == D["goods"].get(O["goods"].find(6310)[2], "iconId") == 6254        # Bloodboon's icon


def test_the_schema_takes_a_named_row_where_the_validator_does():
    import json
    jsonschema = pytest.importorskip("jsonschema")
    from tests.test_spells_projectile import PKG
    schema = json.loads((PKG / "spells.schema.json").read_text(encoding="utf-8"))
    for d, ok in ((design(set={"Bullet.10621000.spEffectId0": "SpEffect.474"}), True),
                  (design(set={"Bullet.10621000.spEffectId0": "Magic.474"}), False),
                  (design(set={"Bullet.10621000.spEffectId0": "474"}), False)):
        assert jsonschema.Draft202012Validator(schema).is_valid(d) is ok
        assert (not problems(d)) is ok if not ok else spec.normalise(d) is not None

"""Phase 2.3, kind `projectile`: a copy of the template's Goods and Magic rows AND of the template's own Bullet and SpEffect rows
(rows no more than 3 spells of the game reach), pointing at each other, tuned with `set` on Bullet and SpEffect rows. The attack
rows (AtkParam_Pc) are not copied yet: the copies keep calling the game's (Phase 2.4).

Part 1 needs no game data: the design file. Part 2: the recipe on small synthetic tables. Part 3 needs the pristine
regulation.bin (ELDENDISK_REGULATION_ORIG) and is skipped without it."""
import copy
import hashlib
import json
import os
import struct
from pathlib import Path

import pytest

from eldendisk.extension.innovate_spells import bases, build, chain as chainmod, container, gate, recipes, spec
from eldendisk.extension.innovate_spells.defs import TABLE_FILES, Def
from tests.ext_helpers import param_blob
from tests.z4 import ID as Z4_ID, SPELL as Z4_SPELL, file_of

PKG = Path(spec.__file__).parent
BF = {"kind": "projectile", "from": 6210}      # Black Flame


def design(**kw):
    return file_of({"black_flame_heal": {**copy.deepcopy(BF), **kw}})


def problems(d):
    with pytest.raises(spec.SpecError) as e:
        spec.normalise(d)
    return e.value.problems


# ---------------------------------------------------------------- the design file
def test_a_projectile_holds_only_what_the_design_names():
    s = spec.normalise(design())["spells"][0]
    assert s == {"slot": 1, "id": "black_flame_heal", "kind": "projectile", "from": 6210, "name": "", "description": "", "requires": {}}


def test_set_takes_bullet_and_speffect_keys_for_a_projectile():
    d = design(set={"Bullet.10621000.life": 5, "SpEffect.1621000.changeHpRate": -0.1, "Magic.6210.slotLength": 1})
    s = spec.normalise(d)["spells"][0]
    assert s["set"]["Bullet.10621000.life"] == 5.0 and isinstance(s["set"]["Bullet.10621000.life"], float)
    assert s["set"]["SpEffect.1621000.changeHpRate"] == pytest.approx(-0.1)


@pytest.mark.parametrize("kind, extra", [("clone", {}), ("enchant", {}), ("buff", {})])
def test_bullet_keys_are_refused_outside_projectile(kind, extra):
    d = file_of({"x": {"kind": kind, "from": 6250, "set": {"Bullet.10621000.life": 5}}})
    assert any(("does not copy them" if kind == "clone" else "only kind projectile copies Bullet rows") in p for p in problems(d))


@pytest.mark.parametrize("name", ["HitBulletID", "intervalCreateBulletId", "atkId_Bullet", "spEffectIDForShooter", "spEffectId0",
                                  "spEffectId1", "spEffectId2", "spEffectId3", "spEffectId4"])
def test_bullet_link_fields_are_refused(name):
    assert any("links rows" in p for p in problems(design(set={"Bullet.10621000." + name: 5})))


@pytest.mark.parametrize("key, value, why", [
    ("Bullet.10621000.nope", 1, "no field 'nope'"),
    ("Bullet.10621000.life", "7", "needs a number"),
    ("Bullet.10621000.sfxId_Hit", 2.5, "whole-number field"),
])
def test_bad_bullet_values_are_refused(key, value, why):
    assert any(why in p for p in problems(design(set={key: value})))


def test_attack_is_still_planned_and_projectile_is_built():
    assert "projectile" in spec.KINDS and spec.PLANNED_KINDS == ("attack",)
    assert any("planned but not built yet" in p for p in problems(design(kind="attack")))


def test_the_schema_and_the_validator_agree_on_projectiles():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((PKG / "spells.schema.json").read_text(encoding="utf-8"))
    cases = [design(), design(fp_cost=9, shop={"price": 10}), design(set={"Bullet.10621000.life": 5}),
             design(set={"Bullet.10621000.life": "5"}), design(set={"Bullets.1.life": 5}), design(kind="attack"),
             design(effect={}), design(**{"from": 0}), file_of({"p": {"kind": "projectile"}})]
    for d in cases:
        ok_schema = jsonschema.Draft202012Validator(schema).is_valid(d)
        try:
            spec.normalise(d)
            ok_code = True
        except spec.SpecError:
            ok_code = False
        assert ok_schema == ok_code, d


def test_the_offsets_the_chain_reader_uses_are_the_fields_the_builder_remaps():
    d = Def("bullet")
    assert d.size == chainmod.BULLET["size"]
    assert [d.fields[n][1] for t, n in chainmod.BULLET_LINKS if t == "bullet"] == list(chainmod.BULLET["bullet"])
    assert sorted(d.fields[n][1] for t, n in chainmod.BULLET_LINKS if t == "sp") == sorted(chainmod.BULLET["sp"])
    assert d.fields["atkId_Bullet"][1] == chainmod.BULLET["atk"][0]
    assert [Def("sp").fields[n][0] for n in chainmod.SP_LINKS] == ["s32"] * 3


# ---------------------------------------------------------------- the recipe on small synthetic tables
def _row(D, key, **kw):
    r = bytearray(D[key].size)
    for k, v in kw.items():
        D[key].set(r, k, v)
    return bytes(r)


def _tables(chain_len=2, refs=None):
    """Magic 6210 (+ Goods) calls Bullet 100 -> (HitBulletID) 101 -> SpEffect 1000 and atk 62101, plus Bullet 200 -> generic Bullet 7777
    (reached by five other Magic rows). `chain_len` > 2: more own Bullets, each called by the previous one."""
    D = {k: Def(k) for k in TABLE_FILES}
    refs = refs or [(1, 100), (1, 200)]
    m = {"mp": 40, "isEnchant": 0}
    for n, (cat, rid) in enumerate(refs, 1):
        m["refCategory%d" % n], m["refId%d" % n] = cat, rid
    magic = [(6210, _row(D, "magic", **m))] + [(7000 + i, _row(D, "magic", refCategory1=1, refId1=7777)) for i in range(5)]
    ids = [100] + list(range(300, 300 + chain_len - 2)) + [101]
    bullets = []
    for a, b in zip(ids, ids[1:]):
        bullets.append((a, _row(D, "bullet", life=3.0, HitBulletID=b, atkId_Bullet=62101)))
    bullets.append((101, _row(D, "bullet", life=1.0, spEffectId0=1000, atkId_Bullet=62101, intervalCreateBulletId=-1)))
    bullets += [(200, _row(D, "bullet", life=9.0, HitBulletID=7777)), (7777, _row(D, "bullet", life=2.0))]
    P = {"magic": container.Param(param_blob(sorted(magic), D["magic"].size)),
         "goods": container.Param(param_blob([(6210, _row(D, "goods", goodsType=18, sortId=9))], D["goods"].size)),
         "sp": container.Param(param_blob([(1000, _row(D, "sp", effectEndurance=7.0))], D["sp"].size)),
         "shop": container.Param(param_blob([(recipes.SHOP_CLONE, bytes(D["shop"].size))], D["shop"].size)),
         "bullet": container.Param(param_blob(sorted(dict(bullets).items()), D["bullet"].size))}
    atk = container.Param(param_blob([(62101, bytes(chainmod.ATK["size"]))], chainmod.ATK["size"]))
    return P, D, chainmod.Chain(P, D, P["bullet"], atk)


def _spell(**kw):
    return {"slot": 2, "id": "p", "kind": "projectile", "from": 6210, "requires": {}, **kw}


def test_the_copy_set_takes_own_rows_and_stops_at_generic_ones():
    _P, _D, C = _tables()
    assert C.copy_set(6210) == {"bullet": {100, 101, 200}, "sp": {1000}}
    assert C.reach("bullet", 7777) == 6 and C.reach("bullet", 100) == 1


def test_a_projectile_copies_its_bullets_and_effects_into_the_slots_blocks_and_remaps_every_link():
    P, D, C = _tables()
    b = recipes.template_rows(P, D, _spell(), C)
    ids = recipes.slot_rows(2)
    bb, sb = ids["bullet_copy_base"], ids["sp_copy_base"]
    assert b.own["bullet"] == {100: bb, 101: bb + 1, 200: bb + 2} and b.own["sp"] == {1000: sb}
    assert [i for i, _ in b.bullet] == [bb, bb + 1, bb + 2] and [i for i, _ in b.sp] == [sb]
    assert [D["magic"].get(b.magic, "refId%d" % n) for n in (1, 2)] == [bb, bb + 2]
    rows = dict(b.bullet)
    assert D["bullet"].get(rows[bb], "HitBulletID") == bb + 1                          # copy -> copy
    assert D["bullet"].get(rows[bb + 1], "spEffectId0") == sb                           # copy -> copied SpEffect
    assert D["bullet"].get(rows[bb + 2], "HitBulletID") == 7777                         # a generic Bullet stays the game's
    assert D["bullet"].get(rows[bb], "atkId_Bullet") == 62101 and D["bullet"].get(rows[bb + 1], "atkId_Bullet") == 62101   # attack rows are shared


def test_the_copies_equal_the_templates_except_the_remapped_links_and_the_set_fields():
    P, D, C = _tables()
    b = recipes.template_rows(P, D, _spell(set={"Bullet.100.life": 30.0, "SpEffect.1000.effectEndurance": 600.0}), C)
    old, new = bytes(P["bullet"].find(100)[2]), dict(b.bullet)[recipes.slot_rows(2)["bullet_copy_base"]]
    diff = sorted(n for n in D["bullet"].order if D["bullet"].fields[n][5] == 1 and D["bullet"].get(old, n) != D["bullet"].get(new, n))
    assert diff == ["HitBulletID", "life"]
    assert D["sp"].get(b.sp[0][1], "effectEndurance") == 600.0


def test_set_on_a_generic_or_foreign_bullet_says_why():
    P, D, C = _tables()
    with pytest.raises(recipes.RecipeError, match="Bullet 7777 is shared with 6 spells of the game and is not copied"):
        recipes.template_rows(P, D, _spell(set={"Bullet.7777.life": 1.0}), C)
    with pytest.raises(recipes.RecipeError, match="Bullet 4242 is not part of the chain of 6210"):
        recipes.template_rows(P, D, _spell(set={"Bullet.4242.life": 1.0}), C)


def test_the_kinds_check_what_the_template_calls():
    P, D, C = _tables()
    with pytest.raises(recipes.RecipeError, match="calls Bullet, not only SpEffect rows.*kind projectile"):
        recipes.template_rows(P, D, _spell(kind="buff"), C)
    with pytest.raises(recipes.RecipeError, match="not a weapon or shield enchant \\(use kind projectile\\)"):
        recipes.template_rows(P, D, _spell(kind="enchant"), C)
    P, D, C = _tables(refs=[(2, 1000)])
    with pytest.raises(recipes.RecipeError, match="no Bullet row"):
        recipes.template_rows(P, D, _spell(), C)
    P, D, C = _tables(refs=[(0, 62101)])
    with pytest.raises(recipes.RecipeError, match="calls attack and no Bullet row.*kind clone"):
        recipes.template_rows(P, D, _spell(), C)


def test_attack_rows_called_next_to_a_bullet_stay_shared():
    P, D, C = _tables(refs=[(1, 100), (0, 62101)])
    b = recipes.template_rows(P, D, _spell(), C)
    assert D["magic"].get(b.magic, "refCategory2") == 0 and D["magic"].get(b.magic, "refId2") == 62101


def test_a_chain_longer_than_the_slots_block_is_refused():
    P, D, C = _tables(chain_len=recipes.COPY_BULLET_BLOCK + 1 - 1)      # 100 + 14 + 101 + the second branch 200 = 17 own Bullets
    with pytest.raises(recipes.RecipeError, match="17 Bullet rows of its own; a slot has room for 16"):
        recipes.template_rows(P, D, _spell(), C)
    P, D, C = _tables(chain_len=recipes.COPY_BULLET_BLOCK - 1)
    assert len(recipes.template_rows(P, D, _spell(), C).bullet) == recipes.COPY_BULLET_BLOCK


def test_bullet_blocks_of_the_slots_do_not_overlap_and_stay_in_the_range_t7_loaded():
    seen = set()
    for n in range(1, 65):
        base = recipes.slot_rows(n)["bullet_copy_base"]
        block = set(range(base, base + recipes.COPY_BULLET_BLOCK))
        assert not block & seen
        seen |= block
    assert min(seen) == 500000000 and max(seen) < 999999998


def test_a_projectile_adds_goods_magic_bullet_speffect_and_shop_rows_only():
    P, D, C = _tables()
    jobs, fp = recipes.make_rows(P, D, [_spell(slot=1, shop={"price": 10, "stock": 1})], C)
    ids = recipes.slot_rows(1)
    assert sorted(jobs) == ["Bullet", "EquipParamGoods", "Magic", "ShopLineupParam", "SpEffectParam"]
    assert fp.added["bullet"] == {ids["bullet_copy_base"] + k for k in range(3)} and fp.added["sp"] == {ids["sp_copy_base"]}
    assert not any(fp.removed.values()) and not any(fp.modified.values())


def test_what_needs_the_chain_reader():
    assert recipes.needs_chain({"kind": "projectile", "from": 1}) and not recipes.needs_chain({"kind": "clone", "from": 1})


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
    from eldendisk.extension.innovate_spells import zstd
    dcx = container.decrypt(data)
    body = zstd.decode_frame(dcx[0x4C:0x4C + struct.unpack(">I", dcx[0x20:0x24])[0]])
    bnd = container.Bnd4(body)
    D = {k: Def(k) for k in TABLE_FILES}
    return {k: container.ParamView(bnd.get(f).data, D[k].size) for k, f in TABLE_FILES.items()}, D


def _spells(*items):
    return spec.normalise(file_of({"spell_%d" % i: it for i, it in enumerate(items, 1)}))["spells"]


@pytest.fixture(scope="module")
def heal(base, src):
    sp = _spells({**BF, "fp_cost": 20, "shop": {"price": 1000, "stock": -1},
                  "set": {"SpEffect.1621000.changeHpRate": -0.1, "Bullet.10621000.life": 6}})
    return sp, build.build(base, sp, src)


@golden
def test_the_chain_of_black_flame(src):
    P, D, C = _orig(src)
    assert C.refs(6210) == [(1, "bullet", 10621000), (2, "bullet", 10621050)]
    assert C.copy_set(6210) == {"bullet": {10621000, 10621001, 10621050, 10621051}, "sp": {1621000}}
    assert C.reach("atk", 79980) > recipes.SHARED_ABOVE and C.reach("atk", 62101) == 1
    assert D["bullet"].get(P["bullet"].find(10621001)[2], "spEffectId0") == 1621000


@golden
def test_a_projectile_of_black_flame_builds_and_passes_the_gate(heal, src):
    sp, res = heal
    assert gate.verify(res.data, src, sp).ok and res.changed_blocks <= 20


@golden
def test_the_copies_of_black_flame_point_at_each_other_and_the_burn_heals(heal, src):
    P, D = _file_tables(heal[1].data)
    O, _OD, _C = _orig(src)
    ids = recipes.slot_rows(1)
    bb, sb = ids["bullet_copy_base"], ids["sp_copy_base"]
    m = P["magic"].find(ids["magic"])[2]
    assert [D["magic"].get(m, "refId%d" % n) for n in (1, 2)] == [bb, bb + 2] and D["magic"].get(m, "refCategory1") == 1
    get = lambda t, i: P[t].find(i)[2]
    assert D["bullet"].get(get("bullet", bb), "HitBulletID") == bb + 1
    assert D["bullet"].get(get("bullet", bb + 1), "spEffectId0") == sb and D["bullet"].get(get("bullet", bb + 3), "spEffectId0") == sb
    assert D["sp"].get(get("sp", sb), "changeHpRate") == pytest.approx(-0.1)
    assert D["sp"].get(O["sp"].find(1621000)[2], "changeHpRate") == pytest.approx(0.1)          # the game's burn is untouched
    assert D["bullet"].get(get("bullet", bb), "life") == 6.0
    # the attack rows are the game's: 62101 and 62106 are called by the copies, and the generic 79980 / 79990 too
    assert D["bullet"].get(get("bullet", bb + 1), "atkId_Bullet") == 62101 and D["bullet"].get(get("bullet", bb), "atkId_Bullet") == 79980


@golden
def test_nothing_that_exists_is_changed_and_the_rows_added_are_exactly_the_footprint(heal, src):
    P, _ = _file_tables(heal[1].data)
    O, _OD, _C = _orig(src)
    for k, extra in (("goods", 1), ("magic", 1), ("shop", 1), ("sp", 1), ("bullet", 4)):
        old = {r[0]: bytes(r[2]) for r in O[k].rows}
        new = {r[0]: bytes(r[2]) for r in P[k].rows}
        assert all(new[i] == b for i, b in old.items()) and len(new) - len(old) == extra


@golden
def test_no_bullet_id_of_the_game_lies_in_the_slot_blocks(src):
    P, _D, _C = _orig(src)
    lo, hi = recipes.slot_rows(1)["bullet_copy_base"], recipes.slot_rows(64)["bullet_copy_base"] + recipes.COPY_BULLET_BLOCK
    assert [r[0] for r in P["bullet"].rows if lo <= r[0] < hi] == []
    lo, hi = recipes.COPY_SP_BASE, recipes.slot_rows(64)["sp_copy_base"] + recipes.COPY_SP_BLOCK
    assert [r[0] for r in P["sp"].rows if lo <= r[0] < hi] == []


@golden
def test_every_projectile_template_of_the_game_builds_or_says_it_is_too_big(src):
    P, D, C = _orig(src)
    built = big = 0
    for r in P["magic"].rows:
        g = P["goods"].find(r[0])
        if g is None or D["goods"].get(g[2], "goodsType") not in recipes.GOODS_TYPES or not any(t == "bullet" for _n, t, _i in C.refs(r[0])):
            continue
        try:
            b = recipes.template_rows(P, D, {"slot": 3, "id": "x", "kind": "projectile", "from": r[0], "requires": {}}, C)
        except recipes.RecipeError as e:
            assert "of its own; a slot has room for" in str(e), e
            big += 1
            continue
        built += 1
        assert len(b.bullet) <= recipes.COPY_BULLET_BLOCK and len(b.sp) <= recipes.COPY_SP_BLOCK
    assert built >= 150 and 0 < big <= 40


@golden
def test_a_projectile_next_to_an_enchant_and_the_heal_over_time_spell_builds_and_passes_the_gate(base, src):
    sp = spec.normalise(file_of({Z4_ID: copy.deepcopy(Z4_SPELL), "enchant": {"kind": "enchant", "from": 6250},
                                 "proj": {**BF, "fp_cost": 7}}))["spells"]
    res = build.build(base, sp, src)
    assert gate.verify(res.data, src, sp).ok and res.changed_blocks <= 20
    P, _ = _file_tables(res.data)
    assert P["bullet"].find(recipes.slot_rows(3)["bullet_copy_base"]) is not None and P["bullet"].find(recipes.slot_rows(2)["bullet_copy_base"]) is None


@golden
def test_a_set_on_a_generic_attack_or_a_generic_bullet_is_refused(src):
    with pytest.raises(build.BuildError, match="is not part of the chain of 6210"):
        build.plan(src, _spells({**BF, "set": {"Bullet.10400000.life": 1}}))


@golden
def test_the_gate_notices_a_copy_that_points_back_at_the_template(heal, src):
    sp, res = heal
    P, D = _file_tables(res.data)
    O, _OD, C = _orig(src)
    ids = recipes.slot_rows(1)
    D["magic"].set(P["magic"].find(ids["magic"])[2], "refId1", 10621000)
    assert any("still calls the template's Bullet 10621000" in p for p in recipes.check_template(P, D, sp[0], O, C))


@golden
def test_the_gate_notices_a_bullet_copy_that_is_changed_or_points_back(heal, src):
    sp, res = heal
    P, D = _file_tables(res.data)
    O, _OD, C = _orig(src)
    bb = recipes.slot_rows(1)["bullet_copy_base"]
    row = P["bullet"].find(bb + 1)[2]
    D["bullet"].set(row, "spEffectId0", 1621000)
    bad = recipes.check_template(P, D, sp[0], O, C)
    assert any("Bullet %d" % (bb + 1) in p and "spEffectId0" in p for p in bad) and any("still points at the template's row 1621000" in p for p in bad)
    D["bullet"].set(row, "spEffectId0", recipes.slot_rows(1)["sp_copy_base"])
    D["bullet"].set(row, "life", D["bullet"].get(row, "life") + 1)
    assert any("life" in p and p.startswith("G11") for p in recipes.check_template(P, D, sp[0], O, C))


@golden
def test_the_whole_gate_stops_a_flipped_byte_in_a_projectile_file(heal, src):
    sp, res = heal
    bad = bytearray(res.data)
    bad[len(bad) // 2] ^= 1
    assert not gate.verify(bytes(bad), src, sp).ok

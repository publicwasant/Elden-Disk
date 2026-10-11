"""The real thing: the game's own regulation.bin 1.17.1 -> spells as NEW rows appended to the four tables (grow.py).

Needs the pristine file (not in the repository): set ELDENDISK_REGULATION_ORIG to it, or the test is skipped.

What is anchored here, and how firmly:
* the rows of slot 1 are field for field the rows of the Z4 spell that passed in the game (SHA-256 of each row below; the only
  difference is where the row lives and that the poise buff has a row of its own instead of overwriting 102006) -- FIRM;
* the SHA-256 of the whole file built from slot 1 is a regression anchor: it says the build is deterministic and unchanged, NOT
  that the game accepts it. The old Z4 file (dummy rows, hash 1aa16ee0...) is no longer built. -- the game's verdict: pending."""
import copy
import hashlib
import json
import os
import struct
from pathlib import Path

import pytest

from eldendisk.extension.innovate_items import bases, container, grow, preflight, reblock, zstd
from eldendisk.extension.innovate_items.spells import build, recipes, spec
from eldendisk.extension.innovate_items.container import Bnd4, ParamView
from eldendisk.extension.innovate_items.defs import TABLE_FILES, Def
from eldendisk.extension.innovate_items.spells.service import Spells

ORIG = os.environ.get("ELDENDISK_REGULATION_ORIG")
pytestmark = pytest.mark.skipif(not ORIG or not Path(ORIG).is_file(), reason="set ELDENDISK_REGULATION_ORIG to the pristine regulation.bin")
SLOT1_DECRYPTED_SHA256 = "0ef6b8519eca2fba8de16f3d3a76742606fcad9c9c280a43fb05953d12a1a9ac"
# SHA-256 of the data of each row of the Z4 spell as it was in the file that passed in the game
Z4_ROW_SHA256 = {
    "goods": "765d4326d327e38f8b292aeb056bf8855a65cfacebe67a69ab131a0c9105fd9a",
    "sp": "ecfe86a0e6d33fac671336dbb9f249fc71a9b9626a8818e4cc053d863f1a078b",          # the heal over time
    "poise": "c0ba94568a92fc83fd02498ce8ca342ff6c91fb66e20448f325ba2618d38b7a4",       # was row 102006, now a row of its own
    "shop": "9de65f45fd091ce9169b41e1a578c2d6167744bb3ca4829a5446592e57cb12b0",
    "magic_with_refId2_102006": "ddefca4c8f92b0d1fe89aecd98224860ccb9ec9677eb01c561750503d1dd4b70",
}
from tests.z4 import ID as Z4_ID, SPELL as Z4_SPELL, Z4 as _Z4_RAW, file_of   # noqa: E402
Z4 = spec.normalise(_Z4_RAW)               # a fixed copy, not the user's extension.json
SLOT1 = recipes.slot_rows(1)


def _spells(*slots, poise=True):
    """Z4-like spells in these slots (1-based positions of extension.json); slots above 7 have no shop."""
    d = {}
    for s in range(1, max(slots) + 1):
        if s in slots:
            sp = copy.deepcopy(Z4_SPELL)
            if not poise:
                sp.pop("poise_while_casting_seconds")
            if s > len(recipes.SHOP_LINES):
                sp.pop("shop")
            d["spell_%d" % s] = sp
        else:
            d["<empty-%d>" % s] = None
    return spec.normalise(file_of(d))["spells"]


def _tables(data_or_body, is_body=False):
    body = data_or_body
    if not is_body:
        dcx = container.decrypt(data_or_body)
        csize = struct.unpack(">I", dcx[0x20:0x24])[0]
        body = zstd.decode_frame(dcx[0x4C:0x4C + csize])
    bnd = Bnd4(body)
    D = {k: Def(k) for k in TABLE_FILES}
    return {k: ParamView(bnd.get(f).data, D[k].size) for k, f in TABLE_FILES.items()}, D


@pytest.fixture(scope="module")
def base():
    data = Path(ORIG).read_bytes()
    assert hashlib.sha256(data).hexdigest() == bases.BASES[bases.CURRENT_BASE], "ELDENDISK_REGULATION_ORIG is not the 1.17.1 original"
    return data


@pytest.fixture(scope="module")
def src(base):
    return build.prepare(base)


@pytest.fixture(scope="module")
def built(base, src):
    return build.build(base, Z4["spells"], src)


def test_slot_1_comes_out_as_the_anchored_file(built):
    assert built.decrypted_sha256 == SLOT1_DECRYPTED_SHA256 and built.changed_blocks == 13
    dcx = container.decrypt(built.data)
    assert len(dcx) == 2143376 and len(built.data) == 2143392 and (len(built.data) - 16) % 16 == 0


def test_the_rows_of_slot_1_are_the_rows_of_the_spell_tested_in_the_game(built):
    P, D = _tables(built.data)
    sha = lambda b: hashlib.sha256(bytes(b)).hexdigest()
    assert sha(P["goods"].find(SLOT1["goods"])[2]) == Z4_ROW_SHA256["goods"]
    assert sha(P["sp"].find(SLOT1["sp_effect"])[2]) == Z4_ROW_SHA256["sp"]
    assert sha(P["sp"].find(SLOT1["poise_sp_effect"])[2]) == Z4_ROW_SHA256["poise"]
    assert sha(P["shop"].find(SLOT1["shop_line"])[2]) == Z4_ROW_SHA256["shop"]
    magic = bytearray(P["magic"].find(SLOT1["magic"])[2])
    assert D["magic"].get(magic, "refId2") == SLOT1["poise_sp_effect"]
    D["magic"].set(magic, "refId2", 102006)                      # the old spell pointed at Endure's own row; here it has one of its own
    assert sha(magic) == Z4_ROW_SHA256["magic_with_refId2_102006"]


def test_every_row_of_the_game_is_still_there_unchanged(built, src):
    new, _ = _tables(built.data)
    old, _ = _tables(src.body, True)
    for k in new:
        o, n = {r[0]: bytes(r[2]) for r in old[k].rows}, {r[0]: bytes(r[2]) for r in new[k].rows}
        assert all(n[i] == b for i, b in o.items())
        assert len(n) - len(o) == {"goods": 1, "magic": 1, "sp": 2, "shop": 1, "bullet": 0, "atk": 0}[k]


def test_the_result_is_a_deterministic_function_of_the_input(base, src, built):
    again = build.build(base, copy.deepcopy(Z4["spells"]), src)
    assert again.data == built.data


def test_the_result_passes_every_preflight_rule_and_an_independent_decoder(built, src):
    dcx = container.decrypt(built.data)
    csize = struct.unpack(">I", dcx[0x20:0x24])[0]
    frame = dcx[0x4C:0x4C + csize]
    zs = pytest.importorskip("zstandard")
    body = zs.ZstdDecompressor().decompressobj().decompress(frame)
    assert body == zstd.decode_frame(frame) and len(body) == len(src.body) + 65504
    newbody, fp = build.plan(src, Z4["spells"])
    problems, warns, stats = preflight.check(src, dcx, newbody, fp)
    assert body == newbody and problems == [] and warns == []
    assert stats["body_growth"] == 65504 and stats["changed_blocks"] == 13


def test_untouched_blocks_are_the_games_own_bytes(built, src, parts):
    """Blocks whose decoded bytes did not change are the game's own bytes, except the literal-size-header form of raw-literal
    blocks (used to steer the repeat-offset state; preflight R3 allows only that, and it checks it)."""
    dcx = container.decrypt(built.data)
    csize = struct.unpack(">I", dcx[0x20:0x24])[0]
    frame = dcx[0x4C:0x4C + csize]
    blocks, _ = zstd.split_blocks(frame)
    newbody = parts[1]
    n = len(src.blocks) - 1                                                     # blocks that hold data in the original
    assert len(blocks) == 828
    edited = identical = reshaped = 0
    for i in range(n):
        p, t, s, l = blocks[i]
        q = src.blocks[i]
        if newbody[i * reblock.BS:(i + 1) * reblock.BS] != src.body[i * reblock.BS:(i + 1) * reblock.BS]:
            edited += 1
        elif frame[p:p + 3 + s] == src.frame[q[0]:q[0] + 3 + q[2]]:
            identical += 1
        else:
            reshaped += 1
    assert edited == 11 and identical + reshaped + edited == n and identical >= 780


# ---- the preflight must notice damage (each case breaks one rule) ----
@pytest.fixture(scope="module")
def parts(built, src):
    dcx = bytearray(container.decrypt(built.data))
    newbody, fp = build.plan(src, Z4["spells"])
    return dcx, newbody, fp


def rules(src, dcx, body, fp):
    return " ".join(preflight.check(src, bytes(dcx), body, fp)[0])


def test_preflight_notices_a_wrong_header_size(parts, src):
    dcx, body, fp = parts
    bad = bytearray(dcx)
    struct.pack_into(">I", bad, 0x1C, len(body) + 1)
    assert "R4" in rules(src, bad, body, fp)


def test_preflight_notices_a_changed_header_field(parts, src):
    dcx, body, fp = parts
    bad = bytearray(dcx)
    bad[0x10] ^= 1
    assert "R4" in rules(src, bad, body, fp)


def test_preflight_notices_a_tail_of_the_wrong_shape(parts, src):
    dcx, body, fp = parts
    assert "R4" in rules(src, bytes(dcx) + b"\0" * 16, body, fp)
    assert "R4" in rules(src, bytes(dcx[:-1]), body, fp)


def test_preflight_notices_a_frame_that_decodes_to_something_else(parts, src):
    dcx, body, fp = parts
    other = bytearray(body)
    other[10] ^= 1
    assert "R1" in rules(src, dcx, bytes(other), fp)


def test_preflight_notices_a_stored_block(parts, src):
    dcx, body, fp = parts
    csize = struct.unpack(">I", dcx[0x20:0x24])[0]
    frame = bytes(dcx[0x4C:0x4C + csize])
    blocks, _ = zstd.split_blocks(frame)
    p, ty, size, last = blocks[1]
    raw = body[reblock.BS:2 * reblock.BS]
    hdr = struct.pack("<I", (len(raw) << 3) | (0 << 1) | last)[:3]
    bad_frame = frame[:p] + hdr + raw + frame[p + 3 + size:]
    bad = bytearray(dcx[:0x4C]) + bad_frame
    struct.pack_into(">I", bad, 0x20, len(bad_frame))
    bad += b"\0" * ((-len(bad)) % 16)
    assert "stored/RLE" in rules(src, bad, body, fp)


def test_preflight_notices_an_appended_block_that_is_stored(parts, src):
    dcx, body, fp = parts
    csize = struct.unpack(">I", dcx[0x20:0x24])[0]
    frame = bytes(dcx[0x4C:0x4C + csize])
    blocks, _ = zstd.split_blocks(frame)
    p, ty, size, last = blocks[len(src.blocks) - 1]          # the first appended block (the original's empty last block comes after)
    raw = body[(len(src.blocks) - 1) * reblock.BS:][:reblock.BS]
    hdr = struct.pack("<I", (len(raw) << 3) | last)[:3]
    bad_frame = frame[:p] + hdr + raw + frame[p + 3 + size:]
    bad = bytearray(dcx[:0x4C]) + bad_frame
    struct.pack_into(">I", bad, 0x20, len(bad_frame))
    bad += b"\0" * ((-len(bad)) % 16)
    assert "R2" in rules(src, bad, body, fp)


def test_preflight_notices_rows_outside_the_footprint(parts, src):
    dcx, body, fp = parts
    smaller = copy.deepcopy(fp)
    smaller.added["sp"].discard(SLOT1["poise_sp_effect"])               # forgets the poise row
    assert "R6" in rules(src, dcx, body, smaller)
    bigger = copy.deepcopy(fp)
    bigger.added["goods"].add(SLOT1["goods"] + 1)
    assert "R6" in rules(src, dcx, body, bigger)


def _entry_offset(body, name_end):
    """(offset in the body, size) of the BND4 entry whose name ends with `name_end`."""
    e = next(x for x in container.Bnd4(body).entries if x.name.endswith(name_end))
    return struct.unpack_from("<I", e.hdr, 0x18)[0], len(e.data)


def test_preflight_notices_a_changed_table_that_is_not_ours(parts, src):
    dcx, body, fp = parts
    ours = ("Magic.param", "EquipParamGoods.param", "SpEffectParam.param", "ShopLineupParam.param")
    e = next(x for x in container.Bnd4(body).entries if not x.name.endswith(ours))
    off = struct.unpack_from("<I", e.hdr, 0x18)[0] + len(e.data) - 1
    bad = bytearray(body)
    bad[off] ^= 1
    assert "R5" in rules(src, dcx, bytes(bad), fp)


def test_preflight_notices_an_old_row_that_was_changed(parts, src):
    dcx, body, fp = parts
    start, size = _entry_offset(body, "EquipParamGoods.param")
    V = ParamView(body[start:start + size], Def("goods").size)
    row_off = V.offsets()[V.rows[0][0]][0]
    bad = bytearray(body)
    bad[start + row_off] ^= 1
    assert "R6" in rules(src, dcx, bytes(bad), fp)


def test_preflight_stops_a_growth_beyond_what_the_game_was_seen_to_accept(parts, src, monkeypatch):
    dcx, body, fp = parts
    monkeypatch.setattr(preflight, "MAX_BODY_GROWTH", 1000)
    monkeypatch.setattr(preflight, "MAX_FRAME_GROWTH", 1000)
    monkeypatch.setattr(preflight, "MAX_CHANGED_BLOCKS", 3)
    warns = " ".join(preflight.check(src, bytes(dcx), body, fp)[1])
    assert "R7" in warns and "R2" in warns


# ---- the recipe refuses a file that is not the original ----
def _orig_tables(src):
    bnd = container.Bnd4(src.body)
    D = {k: Def(k) for k in TABLE_FILES}
    return {k: container.Param(bnd.get(f).data) for k, f in TABLE_FILES.items()}, D


def test_the_recipe_refuses_a_base_where_a_row_it_needs_is_missing(src):
    P, D = _orig_tables(src)
    P["magic"].rows = [r for r in P["magic"].rows if r[0] != recipes.CAST_FROM]
    with pytest.raises(recipes.RecipeError):
        recipes.make_rows(P, D, Z4["spells"])


def test_the_recipe_refuses_a_shop_in_a_slot_without_a_shop_line(src):
    P, D = _orig_tables(src)
    sp = _spells(8)
    sp[0]["shop"] = {"price": 100, "stock": 1}
    with pytest.raises(recipes.RecipeError, match="no shop line"):
        recipes.make_rows(P, D, sp)
    with pytest.raises(build.BuildError, match="no shop line"):
        build.plan(src, sp)


def test_the_recipe_refuses_two_spells_in_one_slot(src):
    P, D = _orig_tables(src)
    with pytest.raises(recipes.RecipeError, match="two spells"):
        recipes.make_rows(P, D, Z4["spells"] + copy.deepcopy(Z4["spells"]))


def test_the_ids_of_every_slot_are_free_in_the_game_and_do_not_collide(src):
    P, _ = _orig_tables(src)
    seen = {"goods": set(), "magic": set(), "sp": set(), "shop": set()}
    for slot in range(1, spec.MAX_SLOTS + 1):
        ids = recipes.slot_rows(slot)
        for key, rid in (("goods", ids["goods"]), ("magic", ids["magic"]), ("sp", ids["sp_effect"]), ("sp", ids["poise_sp_effect"]),
                         ("shop", ids["shop_line"])):
            if rid is None:
                assert slot > len(recipes.SHOP_LINES)
                continue
            assert rid not in seen[key]
            seen[key].add(rid)
    for key in seen:
        assert not any(P[key].find(r) for r in seen[key]) or key == "shop" and all(P[key].find(r) is None for r in seen[key])


# ---- more than one spell ----
@pytest.mark.parametrize("slots", [(2,), (1, 2, 7), (8,), (1, 3, 5, 8)])
def test_other_slots_build_pass_the_gate_and_take_their_own_ids(base, src, slots):
    spells = _spells(*slots)
    res = build.build(base, spells, src)                     # build.build runs the gate
    P, D = _tables(res.data)
    for s in spells:
        ids = recipes.slot_rows(s["slot"])
        assert P["goods"].find(ids["goods"]) and P["magic"].find(ids["magic"]) and P["sp"].find(ids["sp_effect"])
        if ids["shop_line"] is not None:
            assert P["shop"].find(ids["shop_line"]) is not None
    again = build.build(base, copy.deepcopy(spells), src)
    assert again.data == res.data


@pytest.mark.parametrize("kind, frm, slot", [("projectile", 6210, 4), ("attack", 4440, 6), ("enchant", 6250, 3)])
def test_a_template_spell_alone_in_a_late_slot_builds_and_passes_the_gate(base, src, kind, frm, slot):
    """`--add spells.slots.<id>` can build one spell without the slots before it (Phase 2.7): its rows sit at its own ids."""
    slots = {"<id-%d>" % n: None for n in range(1, slot)}
    slots["late"] = {"kind": kind, "from": frm, "fp_cost": 5, "shop": {"price": 1000 + slot, "stock": -1}}
    spells = spec.select(spec.normalise(file_of(slots, maximum=7)), ["spells.slots.late"])
    assert [s["slot"] for s in spells] == [slot]
    res = build.build(base, spells, src)                     # build.build runs the gate
    P, _ = _tables(res.data)
    ids = recipes.slot_rows(slot)
    assert P["goods"].find(ids["goods"]) and P["magic"].find(ids["magic"]) and P["shop"].find(ids["shop_line"]) is not None
    assert build.build(base, copy.deepcopy(spells), src).data == res.data


def test_a_spell_keeps_its_rows_when_another_one_is_added(base, src):
    one = _tables(build.build(base, _spells(2), src).data)[0]
    two = _tables(build.build(base, _spells(2, 3), src).data)[0]
    ids = recipes.slot_rows(2)
    for key, rid in (("goods", ids["goods"]), ("magic", ids["magic"]), ("sp", ids["sp_effect"]), ("shop", ids["shop_line"])):
        assert bytes(one[key].find(rid)[2]) == bytes(two[key].find(rid)[2])


def test_a_spell_without_poise_or_without_shop_builds_and_adds_only_what_it_needs(base, src):
    sp = _spells(1, poise=False)
    sp[0].pop("shop")
    res = build.build(base, sp, src)
    new, _ = _tables(res.data)
    old, _ = _tables(src.body, True)
    assert [new[k].count - old[k].count for k in ("goods", "magic", "sp", "shop")] == [1, 1, 1, 0]


def test_64_spells_with_poise_build_but_the_gate_stops_them(base, src):
    """The encoder used to fail here ("repeat-offset state not reachable"); now a block that cannot end in the expected state
    hands its state to the next one (reblock.rewrite_grow). Growth beyond what the game was seen to accept is still a stop."""
    spells = _spells(*range(1, 65))
    for s in spells:
        if s["slot"] > len(recipes.SHOP_LINES):
            s.pop("shop", None)
    res = build.make(src, spells)
    dcx = container.decrypt(res.data)
    newbody, fp = build.plan(src, spells)
    bad, warn, stats = preflight.check(src, dcx, newbody, fp)
    assert bad == [] and any(w.startswith("R7") for w in warn)      # R2 (blocks) was raised to 20 by T7 and 64 spells stay within it
    with pytest.raises(build.PreflightError):
        build.build(base, spells, src)


def test_16_spells_pass_since_t7_raised_the_blocks_and_64_are_stopped_by_the_growth(base, src):
    res = build.build(base, _spells(*range(1, 17)), src)         # 14 blocks: more than 13 (T6), within the 20 of T7
    assert 13 < res.changed_blocks <= preflight.MAX_CHANGED_BLOCKS
    with pytest.raises(build.PreflightError) as e:
        build.build(base, _spells(*range(1, 65)), src)
    assert "R7" in str(e.value) and "warning counts as a stop" in str(e.value)


# ---- the whole flow through the service, with the real build ----
def _z4_file(tmp_path):
    p = tmp_path / "extension.json"
    p.write_text(json.dumps(_Z4_RAW), encoding="utf-8")
    return p


def test_service_builds_on_the_game_file(tmp_path, base):
    game = tmp_path / "game.bin"
    game.write_bytes(base)
    ci = Spells(tmp_path / "ext", _z4_file(tmp_path))
    data, _ = ci.read_base(game)
    rep = ci.build(ci.items("all"), data)
    assert rep.built and rep.decrypted_sha256 == SLOT1_DECRYPTED_SHA256 and rep.changed_blocks == 13
    assert game.read_bytes() == base and ci.output_path.is_file()


def test_service_refuses_a_shop_in_a_slot_without_a_shop_line(tmp_path):
    f = file_of({"s%d" % i: (copy.deepcopy(Z4_SPELL) if i < 8 else copy.deepcopy(Z4_SPELL)) for i in range(1, 9)})
    p = tmp_path / "extension.json"
    p.write_text(json.dumps(f), encoding="utf-8")
    ci = Spells(tmp_path / "ext", p)
    with pytest.raises(Exception, match="shop"):
        ci.items("all")


# ---- the gate: the slot-1 file passes, and every kind of damage is noticed ----
from eldendisk.extension.innovate_items.spells import gate     # noqa: E402


def test_the_gate_passes_the_slot_1_file(built, src):
    v = gate.verify(built.data, src, Z4["spells"])
    assert v.ok, v.problems
    assert v.decrypted_sha256 == SLOT1_DECRYPTED_SHA256 and v.stats["changed_blocks"] == 13 and v.stats["body_growth"] == 65504


@pytest.mark.parametrize("visual,vfx", [("flask", 5030), ("none", -1)])
def test_the_other_visuals_build_pass_the_gate_and_set_only_the_body_effect(base, src, built, visual, vfx):
    spells = copy.deepcopy(Z4["spells"])
    spells[0]["effect"]["visual"] = visual
    res = build.build(base, spells, src)
    def look(data):
        P, D = _tables(data)
        return (D["sp"].get(P["sp"].find(SLOT1["sp_effect"])[2], "vfxId"), D["magic"].get(P["magic"].find(SLOT1["magic"])[2], "castSfxId"))
    assert res.data != built.data and look(res.data)[0] == vfx
    assert look(built.data) == (1605000, 524400) and look(res.data)[1] == 524400      # the cast flash of Flame! Grant Me Strength stays


def test_the_gate_notices_a_draft_that_is_not_what_the_file_was_built_from(built, src):
    other = copy.deepcopy(Z4["spells"])
    other[0]["shop"]["price"] += 1
    v = gate.verify(built.data, src, other)
    assert not v.ok and any(p.startswith("R1") for p in v.problems)


def test_the_gate_notices_a_flipped_byte_in_the_file(built, src):
    bad = bytearray(built.data)
    bad[len(bad) // 2] ^= 1
    assert not gate.verify(bytes(bad), src, Z4["spells"]).ok


def test_the_gate_notices_a_body_effect_that_is_not_the_one_in_the_draft(built, src):
    spells = copy.deepcopy(Z4["spells"])
    spells[0]["effect"]["visual"] = "none"                    # the file has the burning body (flame)
    v = gate.verify(built.data, src, spells)
    assert not v.ok and any("vfxId" in p for p in v.problems)


def test_the_gate_notices_that_the_file_is_the_original(base, src):
    assert not gate.verify(base, src, Z4["spells"]).ok


def test_the_gate_notices_a_file_built_for_another_slot(base, src, built):
    v = gate.verify(built.data, src, _spells(2))
    assert not v.ok


def _views(src, spells):
    newbody, _ = build.plan(src, spells)
    return _tables(newbody, True)


def test_check_incantation_is_quiet_on_the_real_slot_1(src):
    P, D = _views(src, Z4["spells"])
    assert recipes.check_incantation(P, D, Z4["spells"][0]) == []


def test_check_incantation_is_quiet_on_a_slot_without_shop(src):
    sp = _spells(8)
    P, D = _views(src, sp)
    assert recipes.check_incantation(P, D, sp[0]) == []


def test_check_incantation_notices_a_heal_with_the_wrong_sign(src):
    P, D = _views(src, Z4["spells"])
    D["sp"].set(P["sp"].find(SLOT1["sp_effect"])[2], "changeHpPoint", 60)
    bad = recipes.check_incantation(P, D, Z4["spells"][0])
    assert any(p.startswith("G13") and "drains the player" in p for p in bad)


def test_check_incantation_notices_a_reused_stock_flag(src):
    P, D = _views(src, Z4["spells"])
    other = next(r for r in P["shop"].rows if r[0] != SLOT1["shop_line"])
    D["shop"].set(other[2], "eventFlag_forStock", SLOT1["shop_flag"])
    assert any(p.startswith("G12") and "used by shop lines" in p for p in recipes.check_incantation(P, D, Z4["spells"][0]))


def test_check_incantation_notices_a_shop_line_outside_the_merchants_range(src, monkeypatch):
    P, D = _views(src, Z4["spells"])
    monkeypatch.setattr(recipes, "SHOP_RANGE", (100509, 100524))
    assert any("outside the merchant's range" in p for p in recipes.check_incantation(P, D, Z4["spells"][0]))


def test_check_incantation_notices_a_shop_line_that_should_not_exist(src):
    sp = copy.deepcopy(Z4["spells"])
    P, D = _views(src, sp)
    sp[0].pop("shop")
    assert any(p.startswith("G12") and "has no shop" in p for p in recipes.check_incantation(P, D, sp[0]))


def test_check_incantation_notices_a_broken_id_chain(src):
    P, D = _views(src, Z4["spells"])
    D["magic"].set(P["magic"].find(SLOT1["magic"])[2], "refId1", SLOT1["sp_effect"] + 1)
    assert any("refId1" in p for p in recipes.check_incantation(P, D, Z4["spells"][0]))
    D["magic"].set(P["magic"].find(SLOT1["magic"])[2], "refId1", SLOT1["sp_effect"])
    D["magic"].set(P["magic"].find(SLOT1["magic"])[2], "refId2", 102006)
    assert any("refId2" in p for p in recipes.check_incantation(P, D, Z4["spells"][0]))


def test_the_gate_stops_on_a_second_decoder_that_disagrees(built, src, monkeypatch):
    monkeypatch.setattr(gate, "second_decode", lambda frame: ("ok", b"different"))
    assert any(p.startswith("G16") for p in gate.verify(built.data, src, Z4["spells"]).problems)
    monkeypatch.setattr(gate, "second_decode", lambda frame: ("error", "bad frame"))
    assert any(p.startswith("G16") and "bad frame" in p for p in gate.verify(built.data, src, Z4["spells"]).problems)
    monkeypatch.setattr(gate, "second_decode", lambda frame: ("unavailable", None))
    v = gate.verify(built.data, src, Z4["spells"])
    assert v.ok and any("not available" in n for n in v.notes)


def test_the_whole_service_flow_with_the_real_build_and_gate(tmp_path, base):
    game = tmp_path / "game.bin"
    game.write_bytes(base)
    ci = Spells(tmp_path / "ext", _z4_file(tmp_path))
    spells = ci.items("all")
    data, sha = ci.read_base(game)
    assert not ci.decide(spells, sha).use_secured
    ci.build(spells, data)
    rep = ci.secure(spells, game)
    assert rep.decrypted_sha256 == SLOT1_DECRYPTED_SHA256
    assert ci.decide(spells, sha).use_secured
    assert game.read_bytes() == base


# ---- the envelope test tool (T7): beyond the gate on purpose, but checked in every other way ----
def test_the_envelope_test_tool_builds_a_file_beyond_the_gate_that_an_independent_decoder_reads(tmp_path, base):
    import importlib.util
    spec_ = importlib.util.spec_from_file_location("envelope_test", Path(__file__).resolve().parent.parent / "tools" / "envelope_test.py")
    tool = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(tool)
    game, out, design = tmp_path / "game.bin", tmp_path / "t7.bin", tmp_path / "extension.json"
    game.write_bytes(base)
    design.write_text(json.dumps(_Z4_RAW), encoding="utf-8")
    assert tool.main(["--source", str(game), "--out", str(out), "--spec", str(design)]) == 0
    dcx = container.decrypt(out.read_bytes())
    csize = struct.unpack(">I", dcx[0x20:0x24])[0]
    zs = pytest.importorskip("zstandard")
    body = zs.ZstdDecompressor().decompressobj().decompress(dcx[0x4C:0x4C + csize])
    P, D = _tables(body, True)
    for new, old in tool.COPIES.items():
        assert bytes(P["bullet"].find(new)[2]) == bytes(P["bullet"].find(old)[2])
    assert P["bullet"].count == 15475 + 4 and P["sp"].count == 11354 + 2
    other = tmp_path / "other.bin"
    other.write_bytes(base + b"x")
    assert tool.main(["--source", str(other), "--out", str(tmp_path / "no.bin"), "--spec", str(design)]) == 2 and not (tmp_path / "no.bin").exists()


def test_the_envelope_test_tool_with_no_copies_builds_exactly_the_design(tmp_path, base):
    import importlib.util
    spec_ = importlib.util.spec_from_file_location("envelope_test", Path(__file__).resolve().parent.parent / "tools" / "envelope_test.py")
    tool = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(tool)
    game, out, design = tmp_path / "game.bin", tmp_path / "t10.bin", tmp_path / "extension.json"
    game.write_bytes(base)
    design.write_text(json.dumps(_Z4_RAW), encoding="utf-8")
    assert tool.main(["--source", str(game), "--out", str(out), "--spec", str(design), "--no-copies"]) == 0
    dcx = container.decrypt(out.read_bytes())
    csize = struct.unpack(">I", dcx[0x20:0x24])[0]
    zs = pytest.importorskip("zstandard")
    P, D = _tables(zs.ZstdDecompressor().decompressobj().decompress(dcx[0x4C:0x4C + csize]), True)
    assert P["bullet"].count == 15475 and P["atk"].count == 11017 and P["sp"].count == 11354 + 2      # no unreferenced Bullet / Atk rows

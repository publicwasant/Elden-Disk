"""1.8.3. Part 1: the sparks Reverse Cursed Technique carries (effect 4271 on its second bullet) and their plan. Part 2: `colors` as the
game holds them, a colour per place of an effect file: the values, the look of `run`, the writes of a script, `code/creative.json`."""
import copy
import json
import struct

import pytest

import eldendisk.commands.write as wcmd
from eldendisk.creative.innovate_spells import live, service, spec
from eldendisk.creative.scripts import backend
from eldendisk.writer import fxr
from eldendisk.writer.cache import CACHE_NAME, MemoryCache
from eldendisk.writer.fxr_plans import SPARK_PLANS
from tests.test_spells_service import ci, write_spec  # noqa: F401  (the fixture)
from tests.test_write_flame import BASES, BLUE, Game, open_gate, quiet_where  # noqa: F401  (the fixture)

MAIN = (0x90 / 255, 0xD5 / 255, 1.0)
WHITE = (0xE0 / 255, 0xF3 / 255, 1.0)
KEY = "Bullet.10642101.sfxId_Bullet"
FIRE = "Magic.6421.castSfxId"


def f4(*v):
    return struct.pack("<4f", *v)


def design():
    return json.loads((service.CODE_DIR / "creative.json").read_text(encoding="utf-8"))


def rct(d):
    return d["innovate_spells"]["slots"]["reverse_cursed_technique"]


# ---- part 1: the plan of the sparks ----------------------------------------------------------------------------------------------
def test_the_plan_of_the_sparks_is_sane():
    assert tuple(SPARK_PLANS) == ("4271",) == fxr.spark_ids()
    plan = SPARK_PLANS["4271"]
    ats = [c[0] for c in plan["colours"]]
    assert len(ats) == 39 and ats == sorted(set(ats)) and all(b - a >= 16 for a, b in zip(ats, ats[1:]))
    assert all(0 <= a and a + 16 <= plan["size"] and len(h) == 32 for a, h, _ in plan["colours"])


def test_white_takes_its_own_colour_when_one_is_given():
    assert fxr.recolor(f4(1, 1, 1, 0.5), MAIN) == f4(1, 1, 1, 0.5)                          # without `white`: white stays white
    assert struct.unpack("<4f", fxr.recolor(f4(1, 1, 1, 0.5), MAIN, white=WHITE)) == pytest.approx((*WHITE, 0.5))
    assert struct.unpack("<4f", fxr.recolor(f4(0, 0, 1, 1), MAIN, white=WHITE)) == pytest.approx((*MAIN, 1))


# ---- part 2: a colour per place -------------------------------------------------------------------------------------------------
def test_a_value_is_the_bytes_as_given_or_a_hex_colour_with_the_places_own_brightness_and_alpha():
    own = f4(2.0, 1.0, 0.5, 0.25)
    assert fxr.value_bytes(own, (0.1, 0.2, 0.3, 0.4)) == f4(0.1, 0.2, 0.3, 0.4)
    assert struct.unpack("<4f", fxr.value_bytes(own, MAIN)) == pytest.approx((2 * MAIN[0], 2 * MAIN[1], 2.0, 0.25))
    assert fxr.value_bytes(own, None) == own
    assert struct.unpack("<4f", fxr.value_bytes(f4(0, 0, 0, 1), MAIN)) == pytest.approx((*MAIN, 1))      # black: brightness 1


def test_every_place_of_a_plan_and_only_the_given_ones_change():
    places = fxr.places_of("524400")
    assert len(places) == 22 and list(places) == sorted(places)                          # the colours and the accent places
    st = fxr.place_states("524400", {0x4290: (1, 0, 0, 1)})
    assert len(st) == 22 and [at for at, own, new in st if own != new] == [0x4290]


def test_run_paints_the_places_of_a_design_in_the_same_look_and_keeps_them_in_the_cache(monkeypatch, quiet_where, tmp_path):
    g = Game(effects=("524400", "524401", "4271"))
    ok = []
    monkeypatch.setattr(wcmd.book, "ok", lambda tag, msg: ok.append(msg))
    cache = MemoryCache(tmp_path / CACHE_NAME, 10, 20)
    places = {"4271": {"key": KEY, "values": {0x55cc: (0.1, 0.2, 0.3, 1.0)}},
              "524400": {"key": FIRE, "values": {0x4290: MAIN}}}
    assert wcmd._put_flame(g, open_gate(), None, places=places, cache=cache) == 0
    assert g.passes == 1                                                                     # one look for all of them
    assert g.read(BASES["4271"] + 0x55cc, 16) == f4(0.1, 0.2, 0.3, 1.0)
    own = dict(fxr.places_of("524400"))[0x4290][0]
    assert g.read(BASES["524400"] + 0x4290, 16) == fxr.value_bytes(own, MAIN)
    assert all(g.read(BASES["4271"] + at, 16) == b for at, (b, _bl) in fxr.places_of("4271").items() if at != 0x55cc)
    assert bytes(g.mem[BASES["524401"]]) == bytes(Game().mem[BASES["524401"]])             # not in the design: untouched
    assert cache.effect("4271")["places"] == {0x55cc: f4(0.1, 0.2, 0.3, 1.0)} and cache.effect("4271")["bases"] == [BASES["4271"]]
    assert any(m.startswith(f"colours: {KEY} (effect 4271) has the design's colours, 1 of its 39 places given") for m in ok)
    again = Game(effects=("524400", "524401", "4271"))
    wcmd._put_flame(again, open_gate(), None, places=places)
    assert wcmd._put_flame(again, open_gate(), None, places=places) == 0                    # a second run finds its own work


def test_sparks_the_game_does_not_hold_and_places_that_change_nothing_are_no_error(monkeypatch, quiet_where):
    debug = []
    monkeypatch.setattr(wcmd.book, "d", lambda tag, msg: debug.append(msg))
    assert wcmd._put_flame(Game(), open_gate(), BLUE, places={"4271": {"key": KEY, "values": {0x55cc: MAIN}}}) == 0
    assert any("does not hold 4271 (the sparks)" in m for m in debug)
    assert wcmd._put_flame(Game(), open_gate(), None, places={"524400": {"key": FIRE, "values": {}}}) == 0
    assert any("every place is the game's own colour" in m for m in debug)


def test_an_effect_or_a_place_without_a_plan_is_named_before_anything():
    assert wcmd.check_places({"680035": {"key": KEY, "values": {}}})[0].startswith(f"colors.{KEY}: the effect 680035 has no colour plan")
    got = wcmd.check_places({"524400": {"key": FIRE, "values": {0x10: MAIN, 0x4290: MAIN}}})
    assert got == [f"colors.{FIRE}: the effect 524400 has no colour at 0x10 (22 places: 0x4290 ... 0x4a74)"]
    assert wcmd.check_places({"524400": {"key": FIRE, "values": {0x4290: MAIN}}}) == []


def test_a_few_places_are_changed_and_put_back_without_a_look():
    g = Game(effects=("4271",))
    own = {at: b for at, (b, _bl) in fxr.places_of("4271").items()}
    red = {0x55cc: f4(1, 0, 0, 1), 0x56c8: f4(0, 1, 0, 1)}
    n, good = fxr.repaint_places(g, open_gate(), "4271", [BASES["4271"]], {at: own[at] for at in red}, red)
    assert n == 2 and good == [BASES["4271"]] and all(g.read(BASES["4271"] + at, 16) == b for at, b in red.items())
    fxr.repaint_places(g, open_gate(), "4271", good, red, {at: own[at] for at in red})
    assert bytes(g.mem[BASES["4271"]]) == bytes(Game(effects=("4271",)).mem[BASES["4271"]])
    with pytest.raises(fxr.Stale):
        fxr.repaint_places(g, open_gate(), "4271", good, red, {at: own[at] for at in red})


# ---- part 2: the design -------------------------------------------------------------------------------------------------------
def part1(eid, main, accent=None, white=None):
    """The bytes the colours of part 1 (main / accent / one colour) gave each place."""
    plan = fxr._ALL[eid]
    out = {at: fxr.recolor(bytes.fromhex(h), main, b, white) for at, h, b in plan["colours"]}
    out.update({at: fxr.recolor(bytes.fromhex(h), accent, b) if accent else bytes.fromhex(h) for at, h, b in plan.get("accent", ())})
    return out


def test_the_shipped_design_gives_the_game_the_colours_of_part_1_to_half_a_step_of_hex(ci):  # noqa: F811
    write_spec(ci, design())
    places, note = ci.colours("all")
    assert note is None and {e: d["key"] for e, d in places.items()} == {
        "524400": FIRE, "524401": "Magic.6421.fireSfxId", "515000": "Sfx.515000", "515001": "Sfx.515001",
        "4866": "SpEffectVfx.20090050.midstSfxId", "4271": KEY}
    want = {"524400": part1("524400", MAIN, WHITE), "524401": part1("524401", MAIN, WHITE), "515000": part1("515000", WHITE),
            "515001": part1("515001", WHITE), "4866": part1("4866", MAIN), "4271": part1("4271", MAIN, white=WHITE)}
    for eid, d in places.items():
        assert wcmd.check_places({eid: d}) == []
        for at, own, new in fxr.place_states(eid, d["values"]):           # hex: each channel within half a step of 1/255
            got, exp, o = struct.unpack("<4f", new), struct.unpack("<4f", want[eid][at]), struct.unpack("<4f", own)
            v = max(o[:3]) or 1.0
            assert got[3] == exp[3] and all(abs(g - e) <= v * 0.5 / 255 + 1e-6 for g, e in zip(got[:3], exp[:3])), (eid, hex(at))


def test_a_hex_place_reaches_the_service_as_a_colour_and_the_first_spell_paints_a_shared_effect(ci):  # noqa: F811
    d = design()
    rct(d)["customs"]["advanced"]["colors"][FIRE]["0x4290"] = "#FF0000"
    other = copy.deepcopy(rct(d))
    other["customs"]["advanced"]["colors"] = {FIRE: {"0x4290": "#00FF00"}}
    d["innovate_spells"]["slots"].pop(next(k for k, v in d["innovate_spells"]["slots"].items() if v is None))   # room for one more
    d["innovate_spells"]["slots"] = {"reverse_cursed_technique": rct(d), "other": other,
                                     **{k: v for k, v in d["innovate_spells"]["slots"].items() if k != "reverse_cursed_technique"}}
    write_spec(ci, d)
    places, note = ci.colours("all")
    assert places["524400"]["values"][0x4290] == (1.0, 0.0, 0.0) and "other" in note
    assert places["524400"]["values"][0x4334] == (0xAC / 255, 0xE0 / 255, 1.0)


# ---- part 2: live writes (a script, `write`) ---------------------------------------------------------------------------------
REC = {"id": "reverse_cursed_technique", "slot": 1,
       "rows": {"goods": 2230000, "magic": 2230000, "sp_effect": [21951000], "bullet": [500000001], "atk": [], "shop": 100508,
                "copies": {"Bullet": {"10642101": 500000001}}},
       "design": {"kind": "projectile", "from": 6421,
                  "customs": {"basic": {FIRE: 524400, KEY: 4271},
                              "advanced": {"colors": {KEY: {"0x55cc": [0.1, 0.2, 0.3, 1.0]}}}}}}


def live_on(g, tmp_path, setup):
    from types import SimpleNamespace
    resolved = tmp_path / "spells.resolved.json"
    resolved.write_text(json.dumps({"spells": {"2230000": REC}}), encoding="utf-8")
    cache = MemoryCache(tmp_path / CACHE_NAME, 10, 20)
    setup(cache)
    cache.save()
    target = SimpleNamespace(pid=10, started=20, profile=None, base=0)
    return backend.CreativeLive(g, target, tmp_path, resolved, gate=open_gate(), say=lambda l, m: None)


def test_a_name_of_colors_is_a_place_or_a_whole_key():
    path = ["design", "customs", "advanced", "colors"]
    assert live.target("2230000", REC, path + [KEY]) == ("colours", KEY, None)
    assert live.target("2230000", REC, path + [KEY, "0x55CC"]) == ("colours", KEY, "0x55cc")
    assert live.target("2230000", REC, "design.customs.advanced.colors.Sfx.515000.0x10".split(".")) == ("colours", "Sfx.515000", "0x10")
    assert live.target("2230000", REC, "design.customs.advanced.colors.SpEffectVfx.20090050.midstSfxId".split(".")) == (
        "colours", "SpEffectVfx.20090050.midstSfxId", None)


def test_a_place_and_a_whole_key_are_written_where_run_painted_and_read_back(tmp_path):
    g = Game(effects=("4271",))
    st = fxr.place_states("4271", {0x55cc: (0.1, 0.2, 0.3, 1.0)})
    fxr.paint_many(g, open_gate(), ["4271"], {"4271": None}, states={"4271": st}, everything=True)
    ext = live_on(g, tmp_path, lambda c: c.set_effect("4271", [BASES["4271"]], places={0x55cc: f4(0.1, 0.2, 0.3, 1.0)}))
    path = "design.customs.advanced.colors.Bullet.10642101.sfxId_Bullet"
    assert ext.apply("2230000", (path + ".0x56c8").split("."), "[0.5, 0.5, 0.5, 1]") == {f"colour.{KEY}.0x56c8": "[0.5, 0.5, 0.5, 1.0]"}
    assert g.read(BASES["4271"] + 0x56c8, 16) == f4(0.5, 0.5, 0.5, 1)
    shown = ext.block()["innovate_spells"]["2230000"]["design"]["customs"]["advanced"]["colors"][KEY]
    assert len(shown) == 39 and shown["0x56c8"] == [0.5, 0.5, 0.5, 1.0]             # another alpha than the place's: numbers
    assert shown["0x55cc"] == "#1A334D" and shown["0x5788"] == "#FFFFFF"            # the place's own alpha and brightness: hex
    assert ext.apply("2230000", path.split("."), None) == {f"colour.{KEY}": "the game's own"}           # every place back
    assert bytes(g.mem[BASES["4271"]]) == bytes(Game(effects=("4271",)).mem[BASES["4271"]])
    assert ext.apply("2230000", path.split("."), {"0x55cc": "#90D5FF"}) == {f"colour.{KEY}": "1 of 39 places the design's"}
    with pytest.raises(backend.Refused, match="no colour at this place"):
        ext.apply("2230000", (path + ".0x10").split("."), "#90D5FF")
    with pytest.raises(backend.Refused, match="is not a colour"):
        ext.apply("2230000", (path + ".0x55cc").split("."), "#90D5")


# ---- part 2: the script --------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("folder", ["tests", "defaults"])
def test_every_key_but_the_eyes_follows_the_spell_that_is_selected(folder):
    from eldendisk.creative.scripts import edstdlib as ed
    from eldendisk.creative.scripts import host
    from tests.fake_tools import DOC, FakeBackend
    from tests.test_scripts import EXAMPLES_DIR
    where = EXAMPLES_DIR if folder == "tests" else service.CODE_DIR / "eldendisk" / "creative" / "scripts" / "defaults"
    found = host.load_file(where / "rct_colours_follow_the_spell.py")
    assert found.error is None, found.error
    s = found.scripts[0]
    doc = copy.deepcopy(DOC)
    colors = doc["creative"]["innovate_spells"]["2230000"]["design"]["customs"]["advanced"]["colors"]
    colors[KEY] = {"0x55cc": [0.1, 0.2, 0.3, 1.0]}
    base = "creative.innovate_spells.2230000.design.customs.advanced.colors."
    with FakeBackend(doc) as b:
        ed._set_current(s)
        s.setup()
        b.doc["character"]["equipment"]["magic"]["selected"] = {"slot": 2, "id": 6420}
        s.loop()
        b.doc["character"]["equipment"]["magic"]["selected"] = {"slot": 1, "id": 2230000}
        s.loop()
        ed._set_current(None)
    fire = {"0x4290": [0.5647, 0.8353, 1.0, 0.075], "0x4334": "#90D5FF"}
    assert b.writes == [(base + FIRE, None), (base + KEY, None), (base + FIRE, fire), (base + KEY, {"0x55cc": [0.1, 0.2, 0.3, 1.0]})]


def test_a_build_used_again_gets_the_designs_colours_as_they_are_now(ci):  # noqa: F811
    write_spec(ci, design())
    spells = ci.items("all")
    old = {"kind": service.RESOLVED_KIND, "format": service.RESOLVED_FORMAT, "spells": {"2230000": {
        "id": "reverse_cursed_technique", "slot": 1, "rows": {"goods": 2230000},
        "design": {"customs": {"advanced": {"colors": {FIRE: {"main": "#90D5FF"}}}}}}}}
    ci.resolved_path.parent.mkdir(parents=True, exist_ok=True)
    ci.resolved_path.write_text(json.dumps(old), encoding="utf-8")
    assert ci.refresh_designs(spells) is True
    node = ci.read_resolved()["spells"]["2230000"]
    assert node["rows"] == {"goods": 2230000} and node["design"] == spec.design_of(spells[0])        # the rows stay the build's
    assert len(node["design"]["customs"]["advanced"]["colors"][FIRE]) == 22
    assert ci.refresh_designs(spells) is False                                                       # nothing new: not written again


def test_a_place_is_shown_as_hex_when_a_hex_colour_gives_it():
    own = f4(2.0, 1.0, 0.5, 0.25)
    assert backend.shown_place(own, own) == "#FF8040"
    assert backend.shown_place(fxr.value_bytes(own, (0x90 / 255, 0xD5 / 255, 1.0)), own) == "#90D5FF"
    assert backend.shown_place(f4(3.0, 1.0, 0.5, 0.25), own) == [3.0, 1.0, 0.5, 0.25]          # brighter than the place
    assert backend.shown_place(f4(1.0, 1.0, 0.5, 1.0), own) == [1.0, 1.0, 0.5, 1.0]            # another alpha

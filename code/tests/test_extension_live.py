"""1.7.2: the `extension` block of read / write: what each name is in the game (live.py), the memory cache, a repaint and a rewrite of
the text without a look through the memory, and the routing of a snapshot's changes (backend.py)."""
import json
from types import SimpleNamespace

import pytest

import eldendisk.commands.write as wcmd
from eldendisk.extension.external_scripts import backend
from eldendisk.extension.innovate_items.fmg import Fmg
from eldendisk.extension.innovate_items.spells import live, recipes
from eldendisk.writer import fxr
from eldendisk.writer.cache import CACHE_NAME, MemoryCache
from tests import test_write_flame as tf
from tests import test_write_text as tt

PINK, BLUE = [1.0, 0x90 / 255, 0x9E / 255], [0x90 / 255, 0xD5 / 255, 1.0]
REC = {"id": "reverse_cursed_technique", "slot": 1,
       "rows": {"goods": 2230000, "magic": 2230000, "sp_effect": [21951000, 21951001], "bullet": [500000000], "atk": [], "shop": 100508,
                "copies": {"SpEffect": {"1642100": 21951000, "1642101": 21951001}, "Bullet": {"10642100": 500000000}}},
       "design": {"kind": "projectile", "from": 6421, "requires": {"status": {"faith": 60}, "cost": {"focus_point": 120}},
                  "locations": {"kale": {"price": 34590, "stock": 1}},
                  "customs": {"basic": {"SpEffect.1642100.effectEndurance": 20.0, "Goods.6421.iconId": 6806},
                              "advanced": {"texts": {"goods_name": "RCT"},
                                           "colors": {"Magic.6421.castSfxId": {"main": "#90D5FF", "accent": "#FF909E"},
                                                      "SpEffect.1642100": "#90D5FF"}}}}}


# ------------------------------------------------------------------------------------------------------------------------ live.py
@pytest.mark.parametrize("path, want", [
    ("customs.basic.SpEffect.1642100.effectEndurance", ("param", "params.SpEffect.21951000.effectEndurance")),
    ("customs.basic.Bullet.10642100.life", ("param", "params.Bullet.500000000.life")),
    ("customs.basic.Goods.6421.iconId", ("param", "params.Goods.2230000.iconId")),
    ("customs.basic.Magic.6421.castSfxId", ("param", "params.Magic.2230000.castSfxId")),
    ("requires.status.faith", ("param", "params.Magic.2230000.requirementFaith")),
    ("requires.status.arcane", ("param", "params.Magic.2230000.requirementLuck")),
    ("requires.cost.focus_point", ("param", "params.Magic.2230000.mp")),
    ("locations.kale.price", ("param", "params.ShopLineup.100508.value")),
    ("locations.kale.stock", ("param", "params.ShopLineup.100508.sellQuantity")),
    ("customs.advanced.texts.goods_caption", ("text", 2230000, "goods_captions")),
    ("customs.advanced.colors.Magic.6421.castSfxId.main", ("colour", "main")),
    ("customs.advanced.colors.Magic.6421.castSfxId.accent", ("colour", "accent")),
    ("customs.advanced.colors.Magic.6421.castSfxId", ("colour", "main")),
    ("customs.advanced.colors.SpEffect.1642100", ("colour", "eyes")),
])
def test_each_name_of_a_spell_is_a_value_of_the_game(path, want):
    assert live.target("2230000", REC, path.split(".")) == want


def test_a_dotted_key_may_also_come_whole():
    assert live.target("2230000", REC, ["customs", "advanced", "colors", "SpEffect.1642100"]) == ("colour", "eyes")
    assert live.target("2230000", REC, ["customs", "basic", "SpEffect.1642100.effectEndurance"])[1] == "params.SpEffect.21951000.effectEndurance"


@pytest.mark.parametrize("path, why", [
    ("id", "made by the build"), ("rows.goods", "made by the build"), ("from", "made by the build"),
    ("customs.basic.SpEffect.9999.effectEndurance", "not a row this spell copied"),
    ("customs.basic.Magic.7000.mp", "not the row this spell is made from"),
    ("customs.basic.Weapon.1.x", "not a table a spell is made of"),
    ("customs.advanced.colors.Magic.6421.fireSfxId", "not a value of the game"),
    ("customs.advanced.texts.goods_title", "not a value of the game"),
])
def test_what_is_not_a_value_of_the_game_is_refused_with_why(path, why):
    with pytest.raises(live.Locked, match=why):
        live.target("2230000", REC, path.split("."))


def test_a_build_without_the_copies_says_build_again():
    old = json.loads(json.dumps(REC))
    del old["rows"]["copies"]
    with pytest.raises(live.Locked, match="build again"):
        live.target("2230000", old, "customs.basic.SpEffect.1642100.effectEndurance".split("."))


def test_the_node_is_the_design_flattened_under_the_spell_and_its_game_values_are_known():
    n = live.node("2230000", REC)
    assert n["id"] == "reverse_cursed_technique" and n["customs"]["basic"]["Goods.6421.iconId"] == 6806 and "design" not in n
    reads = live.reads("2230000", REC)
    assert reads[("requires", "status", "faith")] == "params.Magic.2230000.requirementFaith"
    assert reads[("customs", "basic", "SpEffect.1642100.effectEndurance")] == "params.SpEffect.21951000.effectEndurance"
    assert not any(p[:3] == ("customs", "advanced", "colors") for p in reads)


def test_the_build_record_keeps_the_copies_of_each_template_row():
    rows = recipes.spell_rows(1, {"sp": {21951000}}, {"sp": {1642100: 21951000}, "bullet": {}, "atk": {}})
    assert rows["copies"] == {"SpEffect": {"1642100": 21951000}}


# ------------------------------------------------------------------------------------------------------------------------ the cache
def test_the_cache_belongs_to_one_game_process(tmp_path):
    c = MemoryCache(tmp_path / CACHE_NAME, 10, 20)
    c.set_text({"GoodsName": 0x1000}, {2230000: {"goods_name": "RCT"}})
    c.set_effect("4866", [0x30000000, 0x31000000], BLUE, None)
    c.save()
    same = MemoryCache(tmp_path / CACHE_NAME, 10, 20).load()
    assert same.text_slots() == {"GoodsName": 0x1000} and same.texts(2230000) == {"goods_name": "RCT"}
    assert same.effect("4866") == {"bases": [0x30000000, 0x31000000], "main": BLUE, "accent": None}
    other = MemoryCache(tmp_path / CACHE_NAME, 10, 21).load()                      # another start of the game: nothing known
    assert other.text_slots() == {} and other.effect("4866") is None


# ------------------------------------------------------------------------------------------------------------------------ repaint
def painted(eids, main, accent=None):
    g = tf.Game(effects=eids)
    gate = tf.open_gate()
    got, _ = fxr.paint_many(g, gate, list(eids), main, everything=True, accent=accent)
    return g, gate, {e: list(p.bases) for e, p in got.items()}


def colour_at(g, eid, plan_index=0, accent=False):
    at = fxr._ALL[eid]["accent" if accent else "colours"][plan_index][0]
    return g.read(tf.BASES[eid] + at, 16)


def test_a_repaint_changes_the_colours_without_a_look(monkeypatch):
    g, gate, bases = painted(("524400",), BLUE, PINK)
    monkeypatch.setattr(fxr, "find_all", lambda *a, **k: pytest.fail("no look through the memory"))
    plan = fxr._ALL["524400"]
    n, good = fxr.repaint(g, gate, "524400", bases["524400"], {"main": BLUE, "accent": PINK}, {"main": PINK, "accent": PINK})
    assert n > 0 and good == bases["524400"]
    at, hexa, bloom = next(c for c in plan["colours"] if fxr.recolor(bytes.fromhex(c[1]), PINK, c[2]) != bytes.fromhex(c[1]))
    assert g.read(tf.BASES["524400"] + at, 16) == fxr.recolor(bytes.fromhex(hexa), PINK, bloom)
    fxr.repaint(g, gate, "524400", good, {"main": PINK, "accent": PINK}, {"main": None, "accent": None})     # the game's own back
    assert g.read(tf.BASES["524400"] + at, 16) == bytes.fromhex(hexa)


def test_a_repaint_from_colours_the_copy_does_not_carry_is_stale():
    g, gate, bases = painted(("4866",), BLUE)
    with pytest.raises(fxr.Stale):
        fxr.repaint(g, gate, "4866", bases["4866"], {"main": PINK, "accent": None}, {"main": BLUE, "accent": None})


# ------------------------------------------------------------------------------------------------------------------------ the block's writes
def live_on(mem, tmp_path, cache_setup):
    target = SimpleNamespace(pid=10, started=20, profile=None, base=0)
    resolved = tmp_path / "spells.resolved.json"
    resolved.write_text(json.dumps({"spells": {"2230000": REC}}), encoding="utf-8")
    cache = MemoryCache(tmp_path / CACHE_NAME, 10, 20)
    cache_setup(cache)
    cache.save()
    said = []
    ext = backend.ExtensionLive(mem, target, tmp_path, resolved, gate=tf.open_gate(), say=lambda l, m: said.append((l, m)))
    return ext, said


def test_a_colour_of_the_block_repaints_what_run_painted(tmp_path):
    g, _gate, bases = painted(("524400", "524401", "4866"), BLUE, PINK)

    def setup(c):
        for e in ("524400", "524401"):
            c.set_effect(e, bases[e], BLUE, PINK)
        c.set_effect("4866", bases["4866"], BLUE, None)
    ext, _said = live_on(g, tmp_path, setup)
    assert ext.apply("2230000", "customs.advanced.colors.SpEffect.1642100".split("."), "#FF909E") == {"colour.eyes": "#FF909E"}
    assert MemoryCache(tmp_path / CACHE_NAME, 10, 20).load().effect("4866")["main"] == pytest.approx(PINK)
    ext.apply("2230000", "customs.advanced.colors.Magic.6421.castSfxId.main".split("."), "#FF909E")
    assert MemoryCache(tmp_path / CACHE_NAME, 10, 20).load().effect("524400") == {"bases": bases["524400"], "main": pytest.approx(PINK),
                                                                                 "accent": pytest.approx(PINK)}
    block = ext.block()["innovate_items"]["spells"]["2230000"]
    assert block["customs"]["advanced"]["colors"] == {"Magic.6421.castSfxId": {"main": "#FF909E", "accent": "#FF909E"},
                                                      "SpEffect.1642100": "#FF909E"}


def test_a_colour_before_run_painted_anything_says_so(tmp_path):
    ext, _ = live_on(tf.Game(effects=()), tmp_path, lambda c: None)
    with pytest.raises(backend.Refused, match="not painted yet"):
        ext.apply("2230000", "customs.advanced.colors.SpEffect.1642100".split("."), "#FF909E")
    with pytest.raises(backend.Refused, match="is not a colour"):
        ext.apply("2230000", "customs.advanced.colors.SpEffect.1642100".split("."), "#FF90")


def test_a_text_of_the_block_rebuilds_its_table_at_the_pointer_write_text_switched(tmp_path):
    g = tt.game_with_tables()
    ext, _ = live_on(g, tmp_path, lambda c: c.set_text({n: tt.slot_at(n) for n in tt.FILES}, {}))
    assert ext.apply("2230000", "customs.advanced.texts.goods_name".split("."), "Reverse") == {"GoodsName.2230000": "Reverse"}
    assert tt.entries(g, "GoodsName")[2230000] == "Reverse" and tt.entries(g, "GoodsName")[1000] == "Dagger"
    assert MemoryCache(tmp_path / CACHE_NAME, 10, 20).load().texts(2230000) == {"goods_name": "Reverse"}
    assert ext.block()["innovate_items"]["spells"]["2230000"]["customs"]["advanced"]["texts"]["goods_name"] == "Reverse"


def test_a_text_before_run_set_any_says_so_and_names_that_are_not_values_are_refused(tmp_path):
    ext, _ = live_on(tt.game_with_tables(), tmp_path, lambda c: None)
    with pytest.raises(backend.Refused, match="was not set yet"):
        ext.apply("2230000", "customs.advanced.texts.goods_name".split("."), "Reverse")
    with pytest.raises(backend.Refused, match="made by the build"):
        ext.apply("2230000", ["slot"], 3)
    with pytest.raises(backend.Refused, match="no such spell"):
        ext.apply("2230001", ["slot"], 3)
    with pytest.raises(backend.Refused, match="a number is needed"):
        ext.apply("2230000", "requires.status.faith".split("."), "sixty")


def test_a_field_of_the_block_is_written_as_the_param_of_the_spells_own_row(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(backend, "write_values", lambda mem, t, gate, snap, values, say, *rest: seen.append(values) or dict(values))
    ext, _ = live_on(tf.Game(effects=()), tmp_path, lambda c: None)
    ext.apply("2230000", "customs.basic.SpEffect.1642100.effectEndurance".split("."), 30.0)
    ext.apply("2230000", "locations.kale.price".split("."), 40000)
    assert seen == [{"params.SpEffect.21951000.effectEndurance": 30.0}, {"params.ShopLineup.100508.value": 40000}]


def test_a_snapshots_changes_go_where_they_belong(monkeypatch, tmp_path):
    b = object.__new__(backend.LiveBackend)
    b.mem = b.target = b.snapshot = None
    b.gate, b.say, b._write_lock, b._read_lock, b._doc = tf.open_gate(), (lambda l, m: None), __import__("threading").Lock(), \
        __import__("threading").Lock(), None
    b._checked_at, b._clock = 0.0, (lambda: 0.5)
    applied, plain = [], []
    b.extension = SimpleNamespace(apply=lambda goods, parts, value: applied.append((goods, parts, value)) or {"x": value},
                                  table_index=lambda: None)
    monkeypatch.setattr(backend, "write_values", lambda mem, t, gate, snap, values, say, *rest: plain.append(values) or dict(values))
    done, problems = b.write({("character", "attributes", "vigor"): 60, ("systems", "status", "pid"): 3,
                              ("extension", "innovate_items", "spells", "2230000", "customs", "advanced", "colors", "SpEffect.1642100"): "#FF909E",
                              ("params", "effects", "1621000", "effectEndurance"): 5.0})
    assert plain == [{"character.attributes.vigor": 60}, {"params.effects.1621000.effectEndurance": 5.0}]
    assert applied == [("2230000", ["customs", "advanced", "colors", "SpEffect.1642100"], "#FF909E")]
    assert len(problems) == 1 and "systems.status.pid" in problems[0]


# ------------------------------------------------------------------------------------------------------------------------ write --set
@pytest.mark.parametrize("raw, value", [('"#90D5FF"', "#90D5FF"), ("#90D5FF", "#90D5FF"), ("30", 30), ("0.5", 0.5), ("null", None),
                                        ("'Reverse Cursed'", "Reverse Cursed"), ("1_000", 1000)])
def test_the_value_of_an_extension_name_is_read_as_typed(raw, value):
    assert wcmd.ext_value(raw) == value


def test_a_wrong_extension_name_is_refused_before_anything(monkeypatch):
    monkeypatch.setattr(wcmd, "require_windows_x64", lambda: None)
    args = SimpleNamespace(text=False, flame_color=False, set=["extension.innovate_items.spells=3"], refill=None, reset=None)
    assert wcmd.cmd_write(args) == 1


# ------------------------------------------------------------------------------------------------------------------------ read --query
def test_extension_names_are_typed_in_full_and_in_any_case_and_keys_with_dots_are_found():
    from eldendisk.game.values import normalize
    from eldendisk.reader import view
    from tests.fake_tools import DOC
    assert normalize("extension.*") == "extension.*"                                # not character.extension
    assert view.select(DOC, "extension.*")[0] == ("extension.innovate_items.spells.2230000.id", "reverse_cursed_technique")
    got = view.select(DOC, "extension.innovate_items.spells.2230000.customs.basic.spEffect.1642100.EFFECTENDURANCE")
    assert got == [("extension.innovate_items.spells.2230000.customs.basic.SpEffect.1642100.effectEndurance", 20.0)]
    both = view.select(DOC, "extension.innovate_items.spells.2230000.customs.advanced.colors.Magic.6421.castSfxId")
    assert [v for _p, v in both] == ["#90D5FF", "#FF909E"]
    assert view.fmt("goods", 2230000, "extension.innovate_items.spells.2230000.rows.goods") == "2230000"      # an id: no commas


def test_read_names_a_spell_by_its_label_too_and_ids_in_a_list_have_no_commas():
    from eldendisk.reader import view
    from tests.fake_tools import DOC
    assert view.select(DOC, "extension.innovate_items.spells.reverse_cursed_technique.slot") == [
        ("extension.innovate_items.spells.2230000.slot", 1)]
    rows = view.rows(view.select(DOC, "extension.innovate_items.spells.2230000.rows.sp_effect"))
    assert any(r.value == "21951000" for r in rows)


def test_write_names_a_spell_by_its_label_too(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(backend, "write_values", lambda mem, t, gate, snap, values, say, *rest: seen.append(values) or dict(values))
    ext, _ = live_on(tf.Game(effects=()), tmp_path, lambda c: None)
    ext.apply("reverse_cursed_technique", "requires.status.faith".split("."), 40)
    assert seen == [{"params.Magic.2230000.requirementFaith": 40}]


def test_read_names_are_the_document_as_it_is_and_star_is_all_of_it():
    from eldendisk.game.values import UnknownName, normalize
    from eldendisk.reader import view
    from tests.fake_tools import DOC
    assert normalize("*") == "*" and normalize("extension.*") == "extension.*" and normalize("foo.bar") == "foo.bar"
    assert normalize("hp") == "character.vitals.hit_point" and normalize("vigor") == "character.attributes.vigor"   # the short forms stay
    roots = {p.split(".")[0] for p, _v in view.select(DOC, "*")}
    assert roots == {"systems", "character", "params", "extension"}
    with pytest.raises(UnknownName):
        view.select(DOC, "nothing.here")

"""Section 1b: a spell written in the structure `requires.status/cost`, `locations`, `customs.basic/advanced` (and `__info__`) is the same
spell as one written with the earlier fields; what the design says reaches the build, the diff, the vault and the console in its own words."""
import copy
import json

import pytest

import eldendisk.__main__ as cli
from eldendisk.extension.innovate_items.spells import recipes, service, spec
from tests.test_extension_command import args_for, world  # noqa: F401  (fixture)
from tests.z4 import file_of

BLUE, PURPLE = [0.2, 0.65, 1.0], [0.54, 0.4, 0.8]
SET = {"SpEffect.1642100.effectEndurance": 20, "SpEffect.1642100.vfxId": -1, "Magic.6421.castSfxId": 524400, "Goods.6421.iconId": 6806}

V2 = {
    "__info__": "a comment about the whole spell", "kind": "projectile", "from": 6421,
    "requires": {"__info__": "x", "status": {"intelligence": 0, "faith": 60, "arcane": 10}, "cost": {"focus_point": 120}},
    "locations": {"__info__": "x", "kale": {"price": 34590, "stock": 1}},
    "customs": {
        "basic": {"__info__": "numbers of the game's rows", **SET},
        "advanced": {"__info__": "put into the running game",
                     "texts": {"goods_name": "N", "goods_info": "I", "goods_caption": "C"},
                     "colors": {"Magic.6421.castSfxId": {"main": BLUE, "accent": PURPLE}, "SpEffect.1642100": BLUE}}},
}
LEGACY = {
    "kind": "projectile", "from": 6421, "requires": {"intelligence": 0, "faith": 60, "arcane": 10}, "fp_cost": 120,
    "shop": {"price": 34590, "stock": 1}, "set": dict(SET), "text": {"goods_name": "N", "goods_info": "I", "goods_captions": "C"},
    "flame_color": BLUE, "flame_accent_color": PURPLE, "positive_curse_energy_eyes": {"on": "SpEffect.1642100", "color": BLUE},
}


def one(spell, **kw):
    return spec.normalise(file_of({"p": spell}, maximum=7, **kw))["spells"][0]


def problems(spell):
    with pytest.raises(spec.SpecError) as e:
        one(spell)
    return e.value.problems


def mutate(fn):
    s = copy.deepcopy(V2)
    fn(s)
    return s


def test_the_new_structure_is_the_same_spell_as_the_earlier_fields():
    assert one(V2) == one(LEGACY)
    assert spec.build_view(spec.normalise(file_of({"p": V2}, maximum=7))) == spec.build_view(spec.normalise(file_of({"p": LEGACY}, maximum=7)))


def test_design_of_gives_the_new_structure_back_and_it_reads_the_same():
    canon = one(V2)
    d = spec.design_of(canon)
    assert d["requires"] == {"status": {"intelligence": 0, "faith": 60, "arcane": 10}, "cost": {"focus_point": 120}}
    assert d["locations"] == {"kale": {"price": 34590, "stock": 1}}
    assert d["customs"]["advanced"]["colors"] == {"Magic.6421.castSfxId": {"main": BLUE, "accent": PURPLE}, "SpEffect.1642100": BLUE}
    assert d["customs"]["advanced"]["texts"]["goods_caption"] == "C"
    assert one(d) == canon


def test_every_comment_is_left_out_and_a_comment_alone_on_an_earlier_spell_is_fine():
    assert "__info__" not in json.dumps(one(V2))
    old = dict(LEGACY, __info__="a comment")
    assert one(old) == one(LEGACY)


def test_the_long_description_is_goods_caption_or_goods_captions_and_the_eyes_may_keep_the_games_colour():
    s = mutate(lambda s: s["customs"]["advanced"]["texts"].update(goods_captions=s["customs"]["advanced"]["texts"].pop("goods_caption")))
    assert one(s)["text"]["goods_captions"] == "C"
    gold = mutate(lambda s: s["customs"]["advanced"]["colors"].update({"SpEffect.1642100": None}))
    assert one(gold)["positive_curse_energy_eyes"] == {"on": "SpEffect.1642100"}
    plain = mutate(lambda s: s["customs"]["advanced"]["colors"].update({"Magic.6421.castSfxId": BLUE}))
    got = one(plain)
    assert got["flame_color"] == BLUE and "flame_accent_color" not in got


@pytest.mark.parametrize("fn, where, why", [
    (lambda s: s["customs"].update(extra={}), "customs.extra", "unknown field"),
    (lambda s: s["requires"]["status"].update(strength=1), "requires.status.strength", "unknown field"),
    (lambda s: s["requires"]["status"].update(faith=100), "requires.status.faith", "0 to 99"),
    (lambda s: s["requires"]["cost"].update(focus_point=1000), "requires.cost.focus_point", "0 to 999"),
    (lambda s: s["requires"].update(mana=1), "requires.mana", "unknown field"),
    (lambda s: s["locations"].update(limgrave={"price": 1}), "locations.limgrave", "only at Kale"),
    (lambda s: s["locations"]["kale"].update(stock=0), "locations.kale.stock", "-1 (unlimited) or 1 to 99"),
    (lambda s: s["locations"]["kale"].update(price=0), "locations.kale.price", "1 to 99999999"),
    (lambda s: s["customs"]["basic"].update({"Magic.6422.mp": 1}), "customs.basic", "must be this spell's `from`"),
    (lambda s: s["customs"]["basic"].update({"Nothing": 1}), "customs.basic", "a key looks like"),
    (lambda s: s["customs"]["advanced"]["texts"].update(goods_name="x" * 81), "texts", "at most 80 characters"),
    (lambda s: s["customs"]["advanced"]["colors"].update({"Magic.6421.fireSfxId": BLUE}), "colors.Magic.6421.fireSfxId", "castSfxId"),
    (lambda s: s["customs"]["advanced"]["colors"].update({"Magic.6422.castSfxId": BLUE}), "colors.Magic.6422.castSfxId", "`from` (6421)"),
    (lambda s: s["customs"]["advanced"]["colors"].update({"SpEffect.1642100": [3, 0, 0]}), "colors.SpEffect.1642100", "null"),
    (lambda s: s["customs"]["advanced"]["colors"].update({"Magic.6421.castSfxId": {"main": BLUE, "accent": [1, 1]}}), "castSfxId.accent", "three numbers"),
    (lambda s: s["customs"]["advanced"]["colors"].update({"Magic.6421.castSfxId": {"mian": BLUE}}), "castSfxId.mian", "unknown field"),
    (lambda s: s["customs"]["basic"].update({"Magic.6421.castSfxId": 525000}), "colors.Magic.6421.castSfxId", "no colour plan"),
])
def test_a_mistake_is_named_where_the_user_wrote_it(fn, where, why):
    got = problems(mutate(fn))
    assert any(where in p and why in p for p in got), got


def test_the_new_structure_is_for_a_spell_made_from_a_game_spell():
    got = problems({"type": "incantation", "requires": {"faith": 1}, "fp_cost": 5, "locations": {"kale": {"price": 5}}})
    assert any("made from a game spell" in p for p in got)


def test_the_diff_names_the_places_the_user_edits():
    a, b = spec.normalise(file_of({"p": V2}, maximum=7)), spec.normalise(file_of({"p": mutate(lambda s: (
        s["locations"]["kale"].update(price=40000), s["customs"]["basic"].update({"SpEffect.1642100.effectEndurance": 30})))}, maximum=7))
    lines = service.diff_specs(spec.design_view(a), spec.design_view(b))
    assert lines == ["p.customs.basic.SpEffect.1642100.effectEndurance  20.0 -> 30.0", "p.locations.kale.price  34590 -> 40000"]
    c = spec.normalise(file_of({"p": mutate(lambda s: s["customs"]["advanced"]["colors"].update({"Magic.6421.castSfxId": [1, 0, 0]}))}, maximum=7))
    assert service.diff_specs(spec.design_view(a), spec.design_view(c)) == []                     # a colour is no reason to build


def test_the_shipped_design_is_written_in_the_new_structure_and_holds_the_blue_purple_design():
    doc = json.loads((service.CODE_DIR / "extension.json").read_text(encoding="utf-8"))
    raw = doc["innovate_items"]["spells"]["slots"]["reverse_cursed_technique"]
    assert {"__info__", "requires", "locations", "customs"} <= set(raw) and {"basic", "advanced"} == set(raw["customs"])
    got = spec.normalise(doc)["spells"][0]
    assert got["flame_color"] == BLUE and got["flame_accent_color"] == [1.0, 1.0, 1.0] and got["positive_curse_energy_eyes"] == {"on": "SpEffect.1642100", "color": BLUE}
    assert got["requires"] == {"intelligence": 0, "faith": 60, "arcane": 10} and got["fp_cost"] == 120 and got["shop"] == {"price": 34590, "stock": 1}


def test_the_schema_and_the_validator_agree_on_the_new_structure():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((service.PKG_DIR / "spells.schema.json").read_text(encoding="utf-8"))
    cases = [V2, LEGACY]
    for fn in (lambda s: s["requires"]["status"].update(faith=100), lambda s: s["locations"].update(limgrave={"price": 1}),
               lambda s: s["customs"].update(extra={}), lambda s: s["customs"]["basic"].update({"Nothing": 1}),
               lambda s: s["customs"]["advanced"]["colors"].update({"SpEffect.1642100": None}),
               lambda s: s["customs"]["advanced"]["colors"].update({"SpEffect.1642100": [3, 0, 0]}),
               lambda s: s["customs"]["advanced"]["colors"].update({"Magic.6421.castSfxId": {"accent": BLUE}}),
               lambda s: s["customs"]["advanced"]["texts"].update(goods_name="x" * 81),
               lambda s: s.pop("from"), lambda s: s["locations"]["kale"].update(stock=0)):
        cases.append(mutate(fn))
    for spell in cases:
        d = file_of({"p": spell}, maximum=7)
        ok_schema = jsonschema.Draft202012Validator(schema).is_valid(d)
        try:
            spec.normalise(d)
            ok_code = True
        except spec.SpecError:
            ok_code = False
        assert ok_schema == ok_code, spell
    assert jsonschema.Draft202012Validator(schema).is_valid(json.loads((service.CODE_DIR / "extension.json").read_text(encoding="utf-8")))


def test_the_ids_the_game_uses_are_those_of_the_slot_and_only_what_the_build_added():
    added = {"goods": {2230000}, "magic": {2230000}, "sp": {21951000, 21951001, 21950111}, "bullet": {500000000}, "atk": set(), "shop": {100508}}
    got = recipes.spell_rows(1, added)
    assert got == {"goods": 2230000, "magic": 2230000, "sp_effect": [21950111, 21951000, 21951001], "bullet": [500000000], "atk": [], "shop": 100508}
    assert recipes.spell_rows(2, added)["sp_effect"] == [] and recipes.spell_rows(1, {})["shop"] is None


# ---------------------------------------------------------------- the build, the vault and the console, through the CLI
def write_design(w, spell):
    w.spec.write_text(json.dumps(file_of({"reverse_cursed_technique": spell}, maximum=7)), encoding="utf-8")


def test_a_build_leaves_spells_resolved_json_with_the_real_ids(world):
    write_design(world, V2)
    assert cli.main(args_for(world, "--add", "all")) == 0
    rec = json.loads((world.ext / "innovate-items" / "spells" / "spells.resolved.json").read_text(encoding="utf-8"))
    assert rec["kind"] == "innovate-items.spells resolved" and list(rec["spells"]) == ["2230000"]
    got = rec["spells"]["2230000"]
    assert got["id"] == "reverse_cursed_technique" and got["slot"] == 1 and got["rows"]["goods"] == got["rows"]["magic"] == 2230000
    assert got["design"]["locations"] == {"kale": {"price": 34590, "stock": 1}} and got["design"]["requires"]["cost"] == {"focus_point": 120}
    ci = service.Spells(world.ext, world.spec)
    assert ci.read_resolved()["spells"] == rec["spells"]
    dry = cli.main(args_for(world, "--add", "all", "--dry-run"))
    assert dry == 0 and ci.read_resolved()["built_at"] == rec["built_at"]                    # a dry run writes nothing


def test_the_whole_process_is_one_block_on_the_console(world, capsys):
    write_design(world, V2)
    assert cli.main(args_for(world, "--add", "all")) == 0
    lines = capsys.readouterr().err.splitlines()
    top = [i for i, l in enumerate(lines) if l.startswith(" ╭─ design")]
    bottom = [i for i, l in enumerate(lines) if l.startswith(" ╰─")]
    assert len(top) == len(bottom) == 1 and top[0] < bottom[0]
    inside = lines[top[0] + 1:bottom[0]]
    assert inside and all(l.startswith(" │") for l in inside), inside
    text = " ".join("\n".join(inside).split())
    assert "built, gate passed" in text and "reverse_cursed_technique slot 1 · projectile of 6421" in text
    assert "game goods 2230000 · magic 2230000" in text and "sold Kalé · 34590 runes, stock 1" in text
    assert "wrote" in lines[bottom[0]] and "sha256" in text and "--secure" in text


def test_a_mistake_in_the_design_is_in_the_block_once_and_stops_the_command(world, capsys):
    write_design(world, mutate(lambda s: s["customs"].update(extra={})))
    assert cli.main(args_for(world, "--add", "all")) == 1
    err = capsys.readouterr().err
    assert err.count("customs.extra") == 1 and "unknown field" in err and "╰─ ✖  stopped" in err
    assert not any((world.ext / "innovate-items").rglob("regulation.bin")) if (world.ext / "innovate-items").exists() else True


def test_with_v_the_console_shows_the_log_and_no_block(world, capsys):
    write_design(world, V2)
    assert cli.main(args_for(world, "--add", "all", "-v")) == 0
    err = capsys.readouterr().err
    assert "╭" not in err and "╰" not in err and " I design   : " in err and "built, gate passed" in err


def test_golden_eyes_is_now_positive_curse_energy_eyes_and_an_old_record_builds_nothing_new():
    old = dict(LEGACY)
    old["golden_eyes"] = old.pop("positive_curse_energy_eyes")
    assert any("golden_eyes" in p and "use positive_curse_energy_eyes" in p for p in problems(old))
    now = spec.normalise(file_of({"p": LEGACY}, maximum=7))
    record = {"format": now["format"], "spells": [{("golden_eyes" if k == "positive_curse_energy_eyes" else k): v
                                                   for k, v in now["spells"][0].items()}]}
    assert spec.build_view(record) == spec.build_view(now)

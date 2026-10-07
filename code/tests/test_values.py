"""Names for `read --query` and `write --set` (game/values.py), and the lookup / change helpers of reader/view.py."""
import pytest

from eldendisk.game.values import POLICY_KEY, UnknownName, normalize, write_targets
from eldendisk.reader import view
from eldendisk.writer.writer import parse_policy

DOC = {
    "systems": {"status": {"pid": 8812, "game_connected": True}},
    "character": {
        "level": 150,
        "runes": {"total": 40_402_709, "baseline": 40_401_505, "delta": 1204},
        "attributes": {"vigor": 80, "faith": 60},
        "vitals": {"hit_point": {"current": 1460, "maximum": 1460, "base": 1400}},
        "effects": {"311100": {"name": "x", "times": {"buff_duration": 45.2, "max_duration": 80.0}}},
    },
}


# ---- normalize ----
@pytest.mark.parametrize("name,path", [
    ("level", "character.level"), ("CHARACTER.LEVEL", "character.level"), (" level ", "character.level"),
    ("runes", "character.runes"), ("rune", "character.runes"), ("character.rune", "character.runes"),
    ("vigor", "character.attributes.vigor"), ("attrs.faith", "character.attributes.faith"),
    ("attributes.faith", "character.attributes.faith"),
    ("hp", "character.vitals.hit_point"), ("hit_point", "character.vitals.hit_point"),
    ("hp.max", "character.vitals.hit_point.maximum"), ("fp.base", "character.vitals.focus_point.base"),
    ("focus_point.current", "character.vitals.focus_point.current"), ("stamina", "character.vitals.stamina"),
    ("vitals.hit_point.current", "character.vitals.hit_point.current"),
    ("effects", "character.effects"), ("animation", "character.animations"), ("systems.status.pid", "systems.status.pid"),
    ("attrs.*", "character.attributes.*"),
])
def test_normalize(name, path):
    assert normalize(name) == path


# ---- write_targets ----
@pytest.mark.parametrize("name,keys", [
    ("level", ["level"]), ("runes", ["runes"]), ("rune", ["runes"]), ("runes.total", ["runes"]),
    ("vigor", ["vigor"]), ("attrs.faith", ["faith"]),
    ("hp", ["hp"]), ("hit_point", ["hp"]), ("hp.current", ["hp"]), ("fp", ["fp"]), ("focus_point", ["fp"]),
    ("stamina", ["stamina"]), ("vitals.stamina.current", ["stamina"]),
    ("character.attributes.vigor", ["vigor"]),
])
def test_write_targets(name, keys):
    assert write_targets(name) == keys


def test_a_group_pattern_expands_to_every_settable_value_in_it():
    assert write_targets("attrs.*") == ["vigor", "mind", "endurance", "strength", "dexterity", "intelligence", "faith", "arcane"]
    assert write_targets("vitals.*.current") == ["hp", "fp", "stamina"]
    assert write_targets("attributes.v*") == ["vigor"]


@pytest.mark.parametrize("name,why", [
    ("*", "pattern must name a group"), ("character.*", "pattern must name a group"), ("ALL", "unknown name"),
    ("hp.max", "computed by the game"), ("hit_point.base", "computed by the game"),
    ("runes.delta", "computed by the tool"), ("runes.baseline", "computed by the tool"),
    ("effects", "not a stored character value"), ("effects.311100.times.buff_duration", "not a stored character value"),
    ("systems.status.pid", "not a stored character value"), ("animations", "not a stored character value"),
    ("attributes", "is a group"), ("vitals", "is a group"), ("character", "is a group"),
    ("vitals.*.maximum", "matches no value you can set"), ("vigr", "did you mean character.attributes.vigor"),
])
def test_write_targets_refuses_what_cannot_be_set_and_says_why(name, why):
    with pytest.raises(ValueError, match=why):
        write_targets(name)


def test_every_settable_value_has_a_distinct_policy_key():
    assert len(set(POLICY_KEY.values())) == len(POLICY_KEY) == 13


# ---- parse_policy with names ----
def test_parse_policy_takes_full_short_and_pattern_names():
    p = parse_policy(["hit_point=1", "attrs.*=50", "level=10"], "fp, stamina")
    sets = dict(p.sets)
    assert sets["hp"] == 1 and sets["vigor"] == sets["arcane"] == 50 and sets["level"] == 10 and len(sets) == 10
    assert p.refill == ("fp", "stamina")


@pytest.mark.parametrize("sets,refill,why", [
    (["hp=1", "hit_point=2"], None, "set twice"), (["attrs.*=50", "vigor=60"], None, "set twice"),
    (["hp=1"], "hp", "both --set and --refill"), ([], "vigor", "choose from hp, fp, stamina"),
    (["bogus=1"], None, "unknown name"), (["level"], None, "expected NAME=VALUE"), (["level=x"], None, "integer"),
    (["level=-1"], None, "negative"), (["hp.max=1"], None, "computed by the game"),
])
def test_parse_policy_errors(sets, refill, why):
    with pytest.raises(ValueError, match=why):
        parse_policy(sets, refill)


# ---- view.select / rows ----
def test_select_by_alias_group_leaf_and_pattern():
    assert view.select(DOC, "level") == [("character.level", 150)]
    assert view.select(DOC, "runes")[0][0] == "character.runes"
    assert view.select(DOC, "hp.max") == [("character.vitals.hit_point.maximum", 1460)]
    assert view.select(DOC, "attrs.*") == [("character.attributes.vigor", 80), ("character.attributes.faith", 60)]
    assert view.select(DOC, None) == [("", DOC)]


def test_select_unknown_name_suggests():
    with pytest.raises(UnknownName) as e:
        view.select(DOC, "vigr")
    assert "character.attributes.vigor" in str(e.value)
    with pytest.raises(UnknownName):
        view.select(DOC, "attrs.nothing*")


def test_rows_group_and_leaf_formatting():
    rows = view.rows(view.select(DOC, "runes"))
    assert rows[:2] == [view.Row(0, "character", None, "character"), view.Row(1, "runes", None, "character.runes")]
    assert rows[2:] == [view.Row(2, "total", "40,402,709", "character.runes.total"),
                        view.Row(2, "baseline", "40,401,505", "character.runes.baseline"),
                        view.Row(2, "delta", "+1,204", "character.runes.delta")]
    assert view.rows(view.select(DOC, "level")) == [view.Row(0, "character.level", "150", "character.level")]
    assert view.rows(view.select(DOC, "systems.status.pid")) == [
        view.Row(0, "systems.status.pid", "8812", "systems.status.pid")]
    assert view.fmt("game_connected", True) == "yes" and view.fmt("x", None) == "-" and view.fmt("t", 45.2) == "45.20"


def test_changes_ignore_buff_countdowns_and_report_appearing_values():
    a = view.flatten(DOC)
    b = view.flatten({"character": {**DOC["character"], "level": 151,
                                    "effects": {"311100": {"name": "x", "times": {"buff_duration": 44.9, "max_duration": 80.0}},
                                                "100": {"name": "y"}}},
                      "systems": DOC["systems"]})
    assert view.changes(a, b) == [("character.effects.100.name", None, "y"), ("character.level", 150, 151)]
    assert view.changes(a, a) == []


def test_as_json_for_one_selection_and_for_the_whole_document():
    import json
    assert json.loads(view.as_json(view.select(DOC, "hp"))) == {"character.vitals.hit_point": DOC["character"]["vitals"]["hit_point"]}
    assert json.loads(view.as_json(view.select(DOC, None))) == DOC


# ---- effects and animations are part of the document, like in disk-state.json ----
def test_the_whole_view_includes_effects_and_animations():
    doc = {**DOC, "character": {**DOC["character"], "animations": {"7": {"name": "roll"}}}}
    paths = {r.path for r in view.rows(view.select(doc, None))}
    assert "character.effects.311100.name" in paths and "character.animations.7.name" in paths


def test_effects_and_animations_are_selected_like_any_other_name():
    doc = {**DOC, "character": {**DOC["character"], "animations": {"7": {"name": "roll"}}}}
    assert view.select(doc, "effects") == [("character.effects", doc["character"]["effects"])]
    assert view.select(doc, "character.animations.7.name") == [("character.animations.7.name", "roll")]
    hits = dict(view.select(doc, "character.effects.*"))
    assert hits["character.effects.311100.name"] == "x" and "character.level" not in hits
    assert dict(view.select(doc, "character.*"))["character.effects.311100.name"] == "x"
    assert view.select(doc, "effects.999") == []         # not active now; the lists come and go
    with pytest.raises(UnknownName):
        view.select(doc, "character.effectz.999")


# ---- several names, and the tree ----
def test_several_names_are_one_selection_in_the_order_asked_without_repeats():
    got = view.select(DOC, ["attrs.*", "level", "character.attributes.vigor"])
    assert [p for p, _ in got] == ["character.attributes.vigor", "character.attributes.faith", "character.level"]
    with pytest.raises(UnknownName):
        view.select(DOC, ["level", "vigr"])
    assert view.select(DOC, []) == [("", DOC)] and view.select(DOC, ["", " "]) == [("", DOC)]
    assert view.label(["runes", "hp"]) == "runes hp" and view.label(None) == "all values"


def test_a_wildcard_and_several_names_print_as_one_tree():
    doc = {**DOC, "character": {**DOC["character"], "animations": {"7": {"name": "roll"}}}}
    rows = view.rows(view.select(doc, ["character.runes.*", "character.effects.*", "animations.*"]))
    shape = [(r.indent, r.key, r.value) for r in rows]
    assert shape[:6] == [(0, "character", None), (1, "runes", None), (2, "total", "40,402,709"),
                         (2, "baseline", "40,401,505"), (2, "delta", "+1,204"), (1, "effects", None)]
    assert (2, "311100", None) in shape and (3, "name", "x") in shape
    assert (1, "animations", None) in shape and (3, "name", "roll") in shape
    assert shape.count((0, "character", None)) == 1            # one `character` heading, not one per name
    assert [r.path for r in rows][-1] == "character.animations.7.name"


def test_one_value_stays_one_row():
    assert view.rows(view.select(DOC, ["level"])) == [view.Row(0, "character.level", "150", "character.level")]

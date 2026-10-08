"""items.draft.json: strict validation, canonical form, and agreement with the JSON schema."""
import copy
import json
from pathlib import Path

import pytest

from eldendisk.extension.customize_items import spec

PKG = Path(spec.__file__).parent
from tests.z4 import Z4


def mutated(fn):
    d = copy.deepcopy(Z4)
    fn(d["items"][0])
    return d


def test_the_shipped_draft_is_valid_whatever_the_user_made_of_it():
    n = spec.normalise(json.loads((PKG / "items.draft.json").read_text(encoding="utf-8")))
    assert n["items"] and all(i["effect"]["visual"] in spec.VISUALS for i in n["items"])


def test_the_z4_example_is_valid_and_normalises_to_itself_plus_defaults():
    n = spec.normalise(Z4)
    it = n["items"][0]
    assert it["requires"] == {"intelligence": 45, "faith": 15, "arcane": 10} and it["stamina_cost"] == 0
    assert it["effect"]["visual"] == "flame" and it["poise_while_casting_seconds"] == 2.0
    assert spec.normalise(json.loads(spec.dumps(n))) == n                      # canonical form is a fixed point


def test_missing_optional_parts_get_the_documented_defaults():
    d = mutated(lambda i: [i.pop(k) for k in ("effect", "cast_motion", "poise_while_casting_seconds", "name", "description")])
    it = spec.normalise(d)["items"][0]
    assert it["cast_motion"] == "flame-grant-me-strength" and it["effect"]["heal_hp_per_tick"] == 60
    assert "poise_while_casting_seconds" not in it and it["name"] == ""


@pytest.mark.parametrize("fn,where", [
    (lambda i: i.update(fp_cost=-1), "fp_cost"),
    (lambda i: i.update(fp_cost=True), "fp_cost"),
    (lambda i: i.update(fp_cost=1.5), "fp_cost"),
    (lambda i: i["requires"].update(faith=100), "requires.faith"),
    (lambda i: i["requires"].update(strength=10), "requires.strength"),
    (lambda i: i.update(cast_motion="fireball"), "cast_motion"),
    (lambda i: i.update(type="sorcery"), "type"),
    (lambda i: i.update(id="Bad Id"), "id"),
    (lambda i: i["shop"].update(stock=0), "shop.stock"),
    (lambda i: i["shop"].update(price=0), "shop.price"),
    (lambda i: i["effect"].update(visual="rainbow"), "effect.visual"),
    (lambda i: i["effect"].update(tick_seconds=0), "effect.tick_seconds"),
    (lambda i: i.update(poise_while_casting_seconds=99), "poise_while_casting_seconds"),
    (lambda i: i.update(surprise=1), "surprise"),
    (lambda i: i.pop("shop"), "shop"),
])
def test_invalid_specs_are_refused_with_the_path_of_the_problem(fn, where):
    with pytest.raises(spec.SpecError) as e:
        spec.normalise(mutated(fn))
    assert any(where in p for p in e.value.problems)


@pytest.mark.parametrize("visual", ["flame", "flask", "none"])
def test_every_visual_is_accepted(visual):
    d = mutated(lambda i: i["effect"].update(visual=visual))
    assert spec.normalise(d)["items"][0]["effect"]["visual"] == visual


def test_an_explicit_null_visual_means_none_but_a_missing_one_means_flame():
    assert spec.normalise(mutated(lambda i: i["effect"].update(visual=None)))["items"][0]["effect"]["visual"] == "none"
    assert spec.normalise(mutated(lambda i: i["effect"].pop("visual")))["items"][0]["effect"]["visual"] == "flame"
    a = spec.normalise(mutated(lambda i: i["effect"].update(visual=None)))
    b = spec.normalise(mutated(lambda i: i["effect"].update(visual="none")))
    assert spec.build_view(a) == spec.build_view(b)          # null and "none" are the same draft (no rebuild between them)


@pytest.mark.parametrize("key", ["icon_file", "colour", "color", "icon", "text", "flame_color"])
def test_level_3_fields_are_refused_by_name(key):
    with pytest.raises(spec.SpecError) as e:
        spec.normalise(mutated(lambda i: i.update({key: "x"})))
    assert any("Level 3" in p for p in e.value.problems)


def test_all_problems_are_listed_not_just_the_first():
    d = mutated(lambda i: i.update(fp_cost=-1, type="x"))
    with pytest.raises(spec.SpecError) as e:
        spec.normalise(d)
    assert len(e.value.problems) >= 2


def test_duplicate_ids_and_wrong_shapes_are_refused():
    d = copy.deepcopy(Z4)
    d["items"].append(copy.deepcopy(d["items"][0]))
    with pytest.raises(spec.SpecError):
        spec.normalise(d)
    assert spec.normalise({"items": []}) == {"format": 1, "items": []}         # "no items yet" is a valid spec
    with pytest.raises(spec.SpecError):
        spec.normalise({"items": {}})
    with pytest.raises(spec.SpecError):
        spec.parse("{not json")
    with pytest.raises(spec.SpecError):
        spec.normalise([])


def test_text_fields_do_not_change_what_decides_the_build():
    a = spec.normalise(Z4)
    b = copy.deepcopy(a)
    b["items"][0]["name"], b["items"][0]["description"] = "Other name", "Other text"
    assert spec.build_view(a) == spec.build_view(b)
    b["items"][0]["fp_cost"] += 1
    assert spec.build_view(a) != spec.build_view(b)


def test_select_all_or_one_id():
    n = spec.normalise(Z4)
    assert spec.select(n, "all") == n["items"] and spec.select(n, "reverse-curse-technique") == n["items"]
    with pytest.raises(spec.SpecError):
        spec.select(n, "nope")


# ---- the JSON schema (dev check only: the tool itself does not need jsonschema) ----
def test_the_schema_and_the_validator_agree():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((PKG / "items.schema.json").read_text(encoding="utf-8"))
    cases = [Z4] + [mutated(f) for f in (
        lambda i: i.update(fp_cost=-1), lambda i: i["requires"].update(faith=100), lambda i: i.update(cast_motion="x"),
        lambda i: i["shop"].update(stock=0), lambda i: i.update(surprise=1), lambda i: i.pop("shop"),
        lambda i: i.update(id="Bad Id"), lambda i: i["effect"].update(tick_seconds=0), lambda i: i.update(icon_file="a.png"),
        lambda i: i["shop"].update(stock=-1), lambda i: i["shop"].update(price=99999999),
        lambda i: i.update(poise_while_casting_seconds=0.1))]
    for d in cases:
        ok_schema = jsonschema.Draft202012Validator(schema).is_valid(d)
        try:
            spec.normalise(d)
            ok_code = True
        except spec.SpecError:
            ok_code = False
        assert ok_schema == ok_code, d



def test_what_the_first_run_writes_is_a_valid_empty_spec():
    assert spec.parse(spec.EMPTY_SPEC) == {"format": 1, "items": []}

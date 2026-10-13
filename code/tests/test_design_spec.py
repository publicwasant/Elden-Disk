"""design.json (innovate_items.spells): strict validation, canonical form, and agreement with the JSON schema."""
import copy
import json
from pathlib import Path

import pytest

from eldendisk.design.innovate_items.spells import spec

PKG = Path(spec.__file__).parent
CODE = PKG.parents[3]
from tests.z4 import ID, SPELL, Z4, file_of, spell_of


def mutated(fn):
    d = copy.deepcopy(Z4)
    fn(spell_of(d))
    return d


def test_the_shipped_design_is_valid_whatever_the_user_made_of_it():
    n = spec.normalise(json.loads((CODE / "design.json").read_text(encoding="utf-8")))
    assert n["spells"] and all(i["effect"]["visual"] in spec.VISUALS for i in n["spells"] if i.get("kind", "buff") == "buff")


def test_the_z4_example_is_valid_and_normalises_to_itself_plus_defaults():
    n = spec.normalise(Z4)
    it = n["spells"][0]
    assert it["requires"] == {"intelligence": 45, "faith": 15, "arcane": 10} and it["stamina_cost"] == 0
    assert it["effect"]["visual"] == "flame" and it["poise_while_casting_seconds"] == 2.0
    assert spec.normalise(spec.as_file(n)) == n                                # canonical form <-> file form round trip
    assert it["slot"] == 1 and it["id"] == ID and n["maximum"] == 64


def test_a_cast_motion_is_a_name_or_a_number_and_is_kept_as_written():
    for cm in ("black-flame-blade", 32, 0, 999):
        assert spec.normalise(mutated(lambda i: i.update(cast_motion=cm)))["spells"][0]["cast_motion"] == cm
    assert spec.motion_number("black-flame-blade") == 32 and spec.motion_number(7) == 7


def test_missing_optional_parts_get_the_documented_defaults():
    d = mutated(lambda i: [i.pop(k) for k in ("effect", "cast_motion", "poise_while_casting_seconds", "text")])
    it = spec.normalise(d)["spells"][0]
    assert it["cast_motion"] == "flame-grant-me-strength" and it["effect"]["heal_hp_per_tick"] == 60
    assert "poise_while_casting_seconds" not in it and it["text"] == {"goods_name": "", "goods_info": "", "goods_captions": ""}


@pytest.mark.parametrize("fn,where", [
    (lambda i: i.update(fp_cost=-1), "fp_cost"),
    (lambda i: i.update(fp_cost=True), "fp_cost"),
    (lambda i: i.update(fp_cost=1.5), "fp_cost"),
    (lambda i: i["requires"].update(faith=100), "requires.faith"),
    (lambda i: i["requires"].update(strength=10), "requires.strength"),
    (lambda i: i.update(cast_motion="fireball"), "cast_motion"),
    (lambda i: i.update(cast_motion=1000), "cast_motion"),
    (lambda i: i.update(cast_motion=-1), "cast_motion"),
    (lambda i: i.update(cast_motion=True), "cast_motion"),
    (lambda i: i.update(cast_motion="31"), "cast_motion"),
    (lambda i: i.update(cast_motion=32.0), "cast_motion"),
    (lambda i: i.update(type="sorcery"), "type"),
    (lambda i: i.update(id="Bad Id"), "id"),
    (lambda i: i["shop"].update(stock=0), "shop.stock"),
    (lambda i: i["shop"].update(price=0), "shop.price"),
    (lambda i: i["effect"].update(visual="rainbow"), "effect.visual"),
    (lambda i: i["effect"].update(visual=-2), "effect.visual"),
    (lambda i: i["effect"].update(visual=100000000), "effect.visual"),
    (lambda i: i["effect"].update(visual=True), "effect.visual"),
    (lambda i: i["effect"].update(visual="1605000"), "effect.visual"),
    (lambda i: i["effect"].update(visual=1.5), "effect.visual"),
    (lambda i: i["effect"].update(tick_seconds=0), "effect.tick_seconds"),
    (lambda i: i.update(poise_while_casting_seconds=99), "poise_while_casting_seconds"),
    (lambda i: i.update(surprise=1), "surprise"),
    (lambda i: i["shop"].pop("price"), "shop.price"),
])
def test_invalid_specs_are_refused_with_the_path_of_the_problem(fn, where):
    with pytest.raises(spec.SpecError) as e:
        spec.normalise(mutated(fn))
    assert any(where in p for p in e.value.problems)


@pytest.mark.parametrize("visual", ["flame", "flask", "none"])
def test_every_visual_is_accepted(visual):
    d = mutated(lambda i: i["effect"].update(visual=visual))
    assert spec.normalise(d)["spells"][0]["effect"]["visual"] == visual


def test_a_visual_is_a_name_or_a_number_and_is_kept_as_written():
    for v in ("flame", 1605000, -1, 9010):
        assert spec.normalise(mutated(lambda i: i["effect"].update(visual=v)))["spells"][0]["effect"]["visual"] == v
    assert spec.visual_number("flask") == 5030 and spec.visual_number(9010) == 9010


def test_an_explicit_null_visual_means_none_but_a_missing_one_means_flame():
    assert spec.normalise(mutated(lambda i: i["effect"].update(visual=None)))["spells"][0]["effect"]["visual"] == "none"
    assert spec.normalise(mutated(lambda i: i["effect"].pop("visual")))["spells"][0]["effect"]["visual"] == "flame"
    a = spec.normalise(mutated(lambda i: i["effect"].update(visual=None)))
    b = spec.normalise(mutated(lambda i: i["effect"].update(visual="none")))
    assert spec.build_view(a) == spec.build_view(b)          # null and "none" are the same design (no rebuild between them)


@pytest.mark.parametrize("key", ["icon_file", "colour", "color", "icon", "model"])
def test_level_3_fields_are_refused_by_name(key):
    with pytest.raises(spec.SpecError) as e:
        spec.normalise(mutated(lambda i: i.update({key: "x"})))
    assert any("Level 3" in p for p in e.value.problems)


def test_text_is_an_object_with_three_fields_all_kept_and_none_required():
    it = spec.normalise(mutated(lambda i: i.update(text={"goods_name": "A", "goods_captions": "Line 1\nLine 2"})))["spells"][0]
    assert it["text"] == {"goods_name": "A", "goods_info": "", "goods_captions": "Line 1\nLine 2"}
    assert list(it).index("text") < list(it).index("requires")       # the object sits before the numbers (and before `set` in a template)


@pytest.mark.parametrize("text,where", [
    ("x", "text"), ({"goods_name": 5}, "goods_name"), ({"goods_name": "x" * 81}, "goods_name"),
    ({"goods_info": "x" * 301}, "goods_info"), ({"goods_captions": "x" * 3001}, "goods_captions"),
    ({"goods_caption": "x"}, "goods_caption"), ({"name": "x"}, "text.name")])
def test_a_bad_text_is_refused(text, where):
    with pytest.raises(spec.SpecError) as e:
        spec.normalise(mutated(lambda i: i.update(text=text)))
    assert any(where in p for p in e.value.problems)


@pytest.mark.parametrize("old,new", [("name", "text.goods_name"), ("description", "text.goods_info")])
def test_the_old_name_and_description_say_what_replaced_them(old, new):
    with pytest.raises(spec.SpecError) as e:
        spec.normalise(mutated(lambda i: i.update({old: "x"})))
    assert any(old in p and "renamed in 1.7.1" in p and new in p for p in e.value.problems)


def test_all_problems_are_listed_not_just_the_first():
    d = mutated(lambda i: i.update(fp_cost=-1, type="x"))
    with pytest.raises(spec.SpecError) as e:
        spec.normalise(d)
    assert len(e.value.problems) >= 2


def test_wrong_shapes_are_refused():
    for bad in ({}, {"innovate_items": {"spells": []}}, {"innovate_items": []}, {"innovate_items": {"spells": {"maximum": 64}}}, {"innovate_items": {"spells": {"slots": {}}}},
                {"innovate_items": {"spells": {"maximum": 65, "slots": {}}}}, {"innovate_items": {"spells": {"maximum": 0, "slots": {}}}},
                {"innovate_items": {"spells": {"maximum": True, "slots": {}}}},
                {"innovate_items": {"spells": {"maximum": 2, "slots": {"<id-1>": None, "<id-2>": None}, "surprise": 1}}},
                {"innovate_items": {"spells": {"maximum": 2, "slots": []}}}):
        with pytest.raises(spec.SpecError):
            spec.normalise(bad)
    with pytest.raises(spec.SpecError):
        spec.parse("{not json")
    with pytest.raises(spec.SpecError):
        spec.normalise([])


def test_other_sections_of_the_design_are_left_alone():
    d = copy.deepcopy(Z4)
    d["some_other_section"] = {"anything": [1, 2, 3]}
    assert spec.normalise(d) == spec.normalise(Z4)


def test_slots_are_numbered_by_position_and_empty_slots_are_skipped():
    d = file_of({"<id-1>": None, "first": copy.deepcopy(SPELL), "<id-3>": None, "second": copy.deepcopy(SPELL)}, maximum=5)
    n = spec.normalise(d)
    assert [(s["slot"], s["id"]) for s in n["spells"]] == [(2, "first"), (4, "second")] and n["maximum"] == 5
    assert spec.normalise(spec.as_file(n)) == n
    assert list(spec.as_file(n)["innovate_items"]["spells"]["slots"]) == ["<id-1>", "first", "<id-3>", "second", "<id-5>"]


def test_the_slot_count_must_equal_maximum():
    for count in (3, 5):
        d = file_of({ID: copy.deepcopy(SPELL)}, maximum=count)
        d["innovate_items"]["spells"]["maximum"] = 4
        with pytest.raises(spec.SpecError) as e:
            spec.normalise(d)
        assert any("maximum is 4" in p for p in e.value.problems)


def test_a_filled_slot_key_is_the_id_and_must_be_a_valid_one():
    d = file_of({"Bad Id": copy.deepcopy(SPELL)})
    with pytest.raises(spec.SpecError) as e:
        spec.normalise(d)
    assert any("Bad Id" in p and "id" in p for p in e.value.problems)
    d = mutated(lambda i: i.update(id="x"))               # the id is the key now, not a field
    with pytest.raises(spec.SpecError) as e:
        spec.normalise(d)
    assert any(".id" in p and "unknown field" in p for p in e.value.problems)
    # an empty slot may have any key
    assert spec.normalise(file_of({ID: copy.deepcopy(SPELL), "<anything goes>": None}))["spells"][0]["slot"] == 1


@pytest.mark.parametrize("good", ["reverse_curse_technique", "reverse-curse-technique", "a1", "x_2-y", "0day"])
def test_ids_may_use_underscore_or_hyphen(good):
    assert spec.normalise(file_of({good: copy.deepcopy(SPELL)}))["spells"][0]["id"] == good


@pytest.mark.parametrize("bad", ["_x", "-x", "Upper", "has space", "a.b", "a" * 41, "ก"])
def test_ids_that_are_not_safe_names_are_refused(bad):
    with pytest.raises(spec.SpecError):
        spec.normalise(file_of({bad: copy.deepcopy(SPELL)}))


def test_a_key_that_appears_twice_is_refused_instead_of_silently_replaced():
    text = json.dumps(Z4).replace('"<id-2>": null', '"<id-3>": null', 1)        # now <id-3> is twice in the object
    with pytest.raises(spec.SpecError) as e:
        spec.parse(text)
    assert "twice" in str(e.value)


def test_moving_a_spell_to_another_slot_is_a_change_of_what_decides_the_build():
    a = spec.normalise(file_of({ID: copy.deepcopy(SPELL)}))
    b = spec.normalise(file_of({"<id-1>": None, ID: copy.deepcopy(SPELL)}))
    assert b["spells"][0]["slot"] == 2 and spec.build_view(a) != spec.build_view(b)


def test_text_fields_do_not_change_what_decides_the_build():
    a = spec.normalise(Z4)
    b = copy.deepcopy(a)
    b["spells"][0]["text"] = {"goods_name": "Other name", "goods_info": "x", "goods_captions": "Other text"}
    assert spec.build_view(a) == spec.build_view(b)
    b["spells"][0]["fp_cost"] += 1
    assert spec.build_view(a) != spec.build_view(b)


def test_select_all_or_one_id():
    n = spec.normalise(Z4)
    assert spec.select(n, "all") == n["spells"] and spec.select(n, "reverse_curse_technique") == n["spells"]
    with pytest.raises(spec.SpecError):
        spec.select(n, "nope")


# ---- the JSON schema (dev check only: the tool itself does not need jsonschema) ----
def test_the_schema_and_the_validator_agree():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((PKG / "spells.schema.json").read_text(encoding="utf-8"))
    cases = [Z4] + [mutated(f) for f in (
        lambda i: i.update(fp_cost=-1), lambda i: i["requires"].update(faith=100), lambda i: i.update(cast_motion="x"), lambda i: i.update(cast_motion=32), lambda i: i.update(cast_motion=1000),
        lambda i: i["shop"].update(stock=0), lambda i: i.update(surprise=1), lambda i: i.pop("shop"),
        lambda i: i["effect"].update(tick_seconds=0), lambda i: i.update(icon_file="a.png"),
        lambda i: i["shop"].update(stock=-1), lambda i: i["shop"].update(price=99999999),
        lambda i: i.update(poise_while_casting_seconds=0.1))]
    cases += [file_of({"Bad Id": copy.deepcopy(SPELL)}), file_of({"Bad Id": None}), file_of({ID: None}), file_of({}, maximum=64),
              {"innovate_items": {"spells": {"maximum": 65, "slots": {}}}}, {}]
    for d in cases:
        ok_schema = jsonschema.Draft202012Validator(schema).is_valid(d)
        try:
            spec.normalise(d)
            ok_code = True
        except spec.SpecError:
            ok_code = False
        assert ok_schema == ok_code, d



def test_the_empty_file_is_a_valid_design_with_nothing_to_build():
    assert spec.parse(spec.empty_text()) == {"format": 1, "maximum": 64, "spells": []}
    assert spec.parse(spec.empty_text(3)) == {"format": 1, "maximum": 3, "spells": []}


def test_a_spell_without_a_shop_is_valid():
    f = copy.deepcopy(Z4)
    spell_of(f).pop("shop")
    assert spec.normalise(f)["spells"][0].get("shop") is None


def test_flame_color_is_three_numbers_kept_in_the_design_and_out_of_the_build():
    it = spec.normalise(mutated(lambda i: i.update(flame_color=[0.2, 0.65, 1])))["spells"][0]
    assert it["flame_color"] == [0.2, 0.65, 1.0] and all(isinstance(x, float) for x in it["flame_color"])
    assert "flame_color" not in spec.normalise(Z4)["spells"][0]                      # not named: not in the canonical form
    a = spec.normalise(mutated(lambda i: i.update(flame_color=[0.2, 0.65, 1])))
    b = spec.normalise(mutated(lambda i: i.update(flame_color=[1, 0, 0])))
    assert spec.build_view(a) == spec.build_view(b) == spec.build_view(spec.normalise(Z4))     # a colour is no reason to rebuild
    assert spec.normalise(spec.as_file(a)) == a


@pytest.mark.parametrize("bad", [[1, 1], [1, 1, 1, 1], "blue", [0, 0, "1"], [-0.1, 0, 0], [0, 2.1, 0], [True, 0, 0], None])
def test_flame_color_must_be_three_numbers_from_0_to_2(bad):
    with pytest.raises(spec.SpecError) as e:
        spec.normalise(mutated(lambda i: i.update(flame_color=bad)))
    assert any("flame_color" in p for p in e.value.problems)


# ---- positive_curse_energy_eyes (1.7.1 section 1a) ----
PROJECTILE = {"kind": "projectile", "from": 6421, "set": {"SpEffect.1642100.effectEndurance": 20}}


def test_positive_curse_energy_eyes_on_a_spell_made_from_a_game_spell_names_the_buff_row_and_may_have_a_colour():
    it = spec.normalise(file_of({"p": dict(PROJECTILE, positive_curse_energy_eyes={"on": "SpEffect.1642100", "color": [0.2, 0.65, 1]})}))["spells"][0]
    assert it["positive_curse_energy_eyes"] == {"on": "SpEffect.1642100", "color": [0.2, 0.65, 1.0]}
    gold = spec.normalise(file_of({"p": dict(PROJECTILE, positive_curse_energy_eyes={"on": "SpEffect.1642100"})}))["spells"][0]
    assert gold["positive_curse_energy_eyes"] == {"on": "SpEffect.1642100"}                     # no colour: the game's gold
    assert "positive_curse_energy_eyes" not in spec.normalise(file_of({"p": PROJECTILE}))["spells"][0]


def test_positive_curse_energy_eyes_on_a_heal_over_time_buff_has_no_on():
    assert spec.normalise(mutated(lambda i: i.update(positive_curse_energy_eyes={})))["spells"][0]["positive_curse_energy_eyes"] == {}
    assert spec.normalise(mutated(lambda i: i.update(positive_curse_energy_eyes={"color": [1, 0, 0]})))["spells"][0]["positive_curse_energy_eyes"] == {"color": [1.0, 0.0, 0.0]}
    with pytest.raises(spec.SpecError) as e:
        spec.normalise(mutated(lambda i: i.update(positive_curse_energy_eyes={"on": "SpEffect.1642100"})))
    assert any("positive_curse_energy_eyes.on" in p and "leave `on` out" in p for p in e.value.problems)


@pytest.mark.parametrize("bad,where", [
    ({"color": [0.2, 0.65, 1]}, "positive_curse_energy_eyes.on"), ({"on": "Magic.6421"}, "positive_curse_energy_eyes.on"), ({"on": 1642100}, "positive_curse_energy_eyes.on"),
    ({"on": "SpEffect.1642100", "color": [3, 0, 0]}, "positive_curse_energy_eyes.color"), ({"on": "SpEffect.1642100", "colour": [1, 1, 1]}, "positive_curse_energy_eyes.colour"),
    (True, "positive_curse_energy_eyes"), ([0.2, 0.65, 1], "positive_curse_energy_eyes")])
def test_positive_curse_energy_eyes_must_name_the_buff_row_and_a_colour_from_0_to_2(bad, where):
    with pytest.raises(spec.SpecError) as e:
        spec.normalise(file_of({"p": dict(PROJECTILE, positive_curse_energy_eyes=bad)}))
    assert any(where + ":" in p for p in e.value.problems), e.value.problems


def test_a_clone_cannot_have_positive_curse_energy_eyes():
    with pytest.raises(spec.SpecError) as e:
        spec.normalise(file_of({"c": {"kind": "clone", "from": 6421, "positive_curse_energy_eyes": {"on": "SpEffect.1642100"}}}))
    assert any("positive_curse_energy_eyes" in p and "clone" in p for p in e.value.problems)


def test_the_eyes_are_built_but_their_colour_is_not():
    def view(eyes):
        return spec.build_view(spec.normalise(file_of({"p": dict(PROJECTILE, **({"positive_curse_energy_eyes": eyes} if eyes else {}))})))
    blue = view({"on": "SpEffect.1642100", "color": [0.2, 0.65, 1]})
    assert blue == view({"on": "SpEffect.1642100", "color": [1, 0, 0]}) == view({"on": "SpEffect.1642100"})
    assert blue != view(None) and blue != view({"on": "SpEffect.1642101"})
    n = spec.normalise(file_of({"p": dict(PROJECTILE, positive_curse_energy_eyes={"on": "SpEffect.1642100", "color": [0.2, 0.65, 1]})}))
    assert spec.normalise(spec.as_file(n)) == n


def test_the_schema_and_the_validator_agree_on_positive_curse_energy_eyes():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((PKG / "spells.schema.json").read_text(encoding="utf-8"))
    cases = [mutated(lambda i, v=v: i.update(positive_curse_energy_eyes=v)) for v in ({}, {"color": [0.2, 0.65, 1]}, {"color": [3, 0, 0]},
                                                                      {"on": "SpEffect.1"}, {"x": 1}, True)]
    cases += [file_of({"p": dict(PROJECTILE, positive_curse_energy_eyes=v)}) for v in ({"on": "SpEffect.1642100"}, {"on": "SpEffect.1642100", "color": [1, 1, 1]},
                                                                      {"color": [1, 1, 1]}, {"on": "Magic.1"}, {"on": "SpEffect.1", "color": [1, 1]}, [])]
    for d in cases:
        ok_schema = jsonschema.Draft202012Validator(schema).is_valid(d)
        try:
            spec.normalise(d)
            ok_code = True
        except spec.SpecError:
            ok_code = False
        assert ok_schema == ok_code, d


# ---- flame_accent_color: the second colour of the fire ----
def test_a_flame_accent_colour_goes_with_a_flame_colour_and_is_not_part_of_the_build():
    it = spec.normalise(mutated(lambda i: i.update(flame_color=[0.2, 0.65, 1], flame_accent_color=[0.55, 0.2, 1])))["spells"][0]
    assert it["flame_accent_color"] == [0.55, 0.2, 1.0]
    a = spec.normalise(mutated(lambda i: i.update(flame_color=[0.2, 0.65, 1], flame_accent_color=[0.55, 0.2, 1])))
    assert spec.build_view(a) == spec.build_view(spec.normalise(Z4)) and spec.normalise(spec.as_file(a)) == a
    for bad, where in (({"flame_accent_color": [1, 0, 0]}, "goes with flame_color"),
                       ({"flame_color": [1, 1, 1], "flame_accent_color": [3, 0, 0]}, "three numbers")):
        with pytest.raises(spec.SpecError) as e:
            spec.normalise(mutated(lambda i, b=bad: i.update(b)))
        assert any("flame_accent_color" in p and where in p for p in e.value.problems)


def test_the_schema_and_the_validator_agree_on_the_flame_accent_colour():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((PKG / "spells.schema.json").read_text(encoding="utf-8"))
    for extra in ({"flame_color": [1, 1, 1], "flame_accent_color": [0.5, 0.2, 1]}, {"flame_accent_color": [0.5, 0.2, 1]},
                  {"flame_color": [1, 1, 1], "flame_accent_color": [0.5, 0.2]}):
        for d in (mutated(lambda i, x=extra: i.update(x)), file_of({"p": dict(PROJECTILE, **extra)})):
            ok_schema = jsonschema.Draft202012Validator(schema).is_valid(d)
            try:
                spec.normalise(d)
                ok_code = True
            except spec.SpecError:
                ok_code = False
            assert ok_schema == ok_code, d


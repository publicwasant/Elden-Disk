"""Profiles are pinned to one exe: nothing is borrowed from another version's layout."""
import copy
import json
from pathlib import Path

import pytest

from eldendisk.game.profile import load_profile

OFFSETS = Path(__file__).resolve().parent.parent / "offsets.json"
SHA, RAW = next(iter(json.loads(OFFSETS.read_text())["profiles"].items()))


def _load(tmp_path, mutate):
    raw = copy.deepcopy(RAW)
    mutate(raw)
    f = tmp_path / "offsets.json"
    f.write_text(json.dumps({"profiles": {SHA: raw}}))
    return load_profile(f, SHA)


def test_shipped_profile_loads(tmp_path):
    p, why = _load(tmp_path, lambda r: None)
    assert why is None and p.vitals.data_to_vitals == 0x138 and p.at_grace.equals == (0x109AB,)


def test_missing_vitals_is_rejected_not_defaulted(tmp_path):
    p, why = _load(tmp_path, lambda r: r.pop("vitals"))
    assert p is None and "vitals" in why


def test_incomplete_vitals_is_rejected(tmp_path):
    p, why = _load(tmp_path, lambda r: r["vitals"].pop("data_to_vitals"))
    assert p is None and "data_to_vitals" in why


@pytest.mark.parametrize("bad", [True, "yes", 7, {"source": "anim"}, {"source": "anim", "equals": []}])
def test_bad_at_grace_is_rejected_not_defaulted_to_68011(tmp_path, bad):
    p, why = _load(tmp_path, lambda r: r.__setitem__("at_grace", bad))
    assert p is None and "at_grace" in why


def test_at_grace_null_turns_feature_off(tmp_path):
    p, why = _load(tmp_path, lambda r: r.__setitem__("at_grace", None))
    assert why is None and p.at_grace is None


# ---- 1.7.1: where the game keeps its text tables ----
def test_the_shipped_profile_says_where_the_text_tables_are():
    p, why = _load_default()
    assert why is None and p.text.files == {"GoodsName": 10, "GoodsInfo": 20, "GoodsCaption": 24}
    assert p.text.sizes == {"GoodsName": 114880, "GoodsInfo": 164208, "GoodsCaption": 975296}


def _load_default():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        return _load(Path(d), lambda r: None)


def test_a_profile_without_text_just_has_no_text(tmp_path):
    p, why = _load(tmp_path, lambda r: r.pop("text"))
    assert why is None and p.text is None


@pytest.mark.parametrize("bad", [True, "x", {"files": {"GoodsName": 10}}, {"sizes": {"GoodsName": 100}}, {"files": {}, "sizes": {}},
                                 {"files": {"GoodsName": 10}, "sizes": {}}, {"files": {"GoodsName": 10}, "sizes": {"GoodsInfo": 100}},
                                 {"files": {"GoodsName": -1}, "sizes": {"GoodsName": 100}}, {"files": {"GoodsName": 10}, "sizes": {"GoodsName": 3}},
                                 {"files": {"GoodsName": 10}, "sizes": {"GoodsName": None}}])
def test_a_text_block_that_is_there_must_be_complete(tmp_path, bad):
    p, why = _load(tmp_path, lambda r: r.__setitem__("text", bad))
    assert p is None and "text" in why


# ---- 1.7.2: the equipment (the magic slots) ----
def test_the_shipped_profile_says_where_the_magic_slots_are(tmp_path):
    p, why = _load(tmp_path, lambda r: None)
    e = p.equipment
    assert why is None and (e.game_data_to_magic, e.magic_slots, e.magic_slot_size, e.magic_slot_count, e.magic_selected) == \
        (0x530, 0x10, 8, 14, 0x80)


def test_a_profile_without_equipment_just_has_none(tmp_path):
    p, why = _load(tmp_path, lambda r: r.pop("equipment"))
    assert why is None and p.equipment is None


@pytest.mark.parametrize("bad", [True, {"game_data_to_magic": "0x530"},
                                 {"game_data_to_magic": "0x530", "magic_slots": "0x10", "magic_slot_size": "0x2", "magic_slot_count": 14,
                                  "magic_selected": "0x80"}])
def test_an_equipment_block_that_is_there_must_be_complete(tmp_path, bad):
    p, why = _load(tmp_path, lambda r: r.__setitem__("equipment", bad))
    assert p is None and "equipment" in why


# ---- 1.8.0: the event flags (resurrect)
def test_the_shipped_profile_says_where_the_event_flags_are(tmp_path):
    p, why = _load(tmp_path, lambda r: None)
    assert why is None and (p.event_flags.man_rva, p.event_flags.divisor, p.event_flags.holder_size) == (0x3D6C4B8, 1000, 125)


def test_a_profile_without_event_flags_just_has_none(tmp_path):
    p, why = _load(tmp_path, lambda r: r.pop("event_flags"))
    assert why is None and p.event_flags is None


@pytest.mark.parametrize("bad", [True, {"man_rva": "0x3D6C4B8"}, {"man_rva": "0x3D6C4B8", "divisor": 1000, "holder_size": 10}])
def test_an_event_flags_block_that_is_there_must_be_complete(tmp_path, bad):
    p, why = _load(tmp_path, lambda r: r.__setitem__("event_flags", bad))
    assert p is None and "event_flags" in why

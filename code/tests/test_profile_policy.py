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

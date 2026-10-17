"""1.8.4 part 2: `character.lock_on` (true while the player is locked on to something: PlayerIns + player_to_lock_on holds the game's
handle of the target) and the default script that makes Dismantle follow it (one target locked on, the fan not)."""
import copy
import dataclasses
import json
from pathlib import Path

import pytest

from eldendisk.creative.scripts import edstdlib as ed
from eldendisk.creative.scripts import host
from eldendisk.game import profile as profmod
from eldendisk.game.values import normalize
from eldendisk.reader.sampler import is_handle
from tests.fake_tools import DOC, FakeBackend
from tests.test_disk import BASE, NOW, PLAYER, Sampler, doc_for, full_world, make_profile, state_ids, valid

CODE = Path(__file__).parents[1]
HANDLE = 0x3C2A2500_17300018           # seen in the game while locked on (the probes of 2026-10-17)


# ---------------------------------------------------------------- character.lock_on
@pytest.mark.parametrize("v, locked", [(HANDLE, True), (0x00000001_00000002, True), (0, False), (0xFFFFFFFF_FFFFFFFF, False),
                                       (0x00000000_17300018, False), (0xFFFFFFFF_17300018, False), (0x3C2A2500_FFFFFFFF, False),
                                       (0x3C2A2500_00000000, False)])
def test_a_handle_is_neither_half_zero_nor_all_ones(v, locked):
    assert is_handle(v) is locked


def _sampler(value=None, field=0x6B0):
    m = full_world()
    if value is not None:
        m.u64(PLAYER + 0x6B0, value)
    p = dataclasses.replace(make_profile(), player_to_lock_on=field)
    return Sampler(m, p, state_ids(), BASE)


@pytest.mark.parametrize("value, locked", [(HANDLE, True), (0xFFFFFFFF_FFFFFFFF, False), (0, False)])
def test_lock_on_is_read_every_sample_and_is_in_the_disk(value, locked):
    s = _sampler(value)
    r = s.sample(NOW)
    assert r.character["lock_on"] is locked and s.lock_on_raw == value
    doc = doc_for(s, r)
    valid(doc)
    assert doc["character"]["lock_on"] is locked


def test_without_the_profile_field_or_the_memory_lock_on_is_left_out():
    r = _sampler(HANDLE, field=None).sample(NOW)
    assert "lock_on" not in r.character
    s = _sampler(None)                                  # +0x6B0 cannot be read
    r = s.sample(NOW)
    assert r.state == "CONNECTED" and "lock_on" not in r.character and s.lock_on_raw is None


def test_the_profile_of_1_17_1_has_the_field_and_a_profile_without_it_loads(tmp_path):
    raw = json.loads((CODE / "offsets.json").read_text(encoding="utf-8"))
    sha, prof = next(iter(raw["profiles"].items()))
    p, err = profmod.load_profile(CODE / "offsets.json", sha)
    assert err is None and p.player_to_lock_on == 0x6B0
    without = tmp_path / "offsets.json"
    without.write_text(json.dumps({"profiles": {sha: {k: v for k, v in prof.items() if k != "player_to_lock_on"}}}), encoding="utf-8")
    p, err = profmod.load_profile(without, sha)
    assert err is None and p.player_to_lock_on is None


def test_read_lock_on_is_a_name_of_the_character():
    assert normalize("lock_on") == "character.lock_on"


# ---------------------------------------------------------------- the script
SCRIPT = CODE / "eldendisk" / "creative" / "scripts" / "defaults" / "dismantle_follows_the_lock_on.py"
MAGIC, BULLET = 2230001, 500000016
BUILT = {"Magic.6800.refType": 106, "Bullet.10680000.shootAngle": -92, "Bullet.10680000.shootAngleInterval": 5,
         "Bullet.10680000.hitRadius": 1.5, "Bullet.10680000.hitRadiusMax": 4.5}
GAME_BULLET = {"shootAngle": -92, "shootAngleInterval": 5, "homingAngle": 0, "lockShootLimitAng": 30, "hitRadius": 1.5,
               "hitRadiusMax": 4.5, "isUseSharedHitList": 1}


def _doc(lock_on=False, with_spell=True):
    doc = copy.deepcopy(DOC)
    doc["character"]["lock_on"] = lock_on
    doc["params"] = {"Magic": {str(MAGIC): {"refType": 106, "mp": 60}}, "Bullet": {str(BULLET): dict(GAME_BULLET)}}
    if with_spell:
        doc["creative"]["innovate_spells"]["2230001"] = {
            "id": "dismantle", "slot": 2,
            "rows": {"goods": MAGIC, "magic": MAGIC, "sp_effect": [21951008, 21951009], "bullet": [BULLET, BULLET + 1],
                     "atk": [710000008], "shop": 100509, "copies": {"Bullet": {"10680000": BULLET, "10680001": BULLET + 1}}},
            "design": {"kind": "projectile", "from": 6800, "requires": {"cost": {"focus_point": 60}},
                       "customs": {"basic": dict(BUILT)}}}
    return doc


def _script():
    found = host.load_file(SCRIPT)
    assert found.error is None, found.error
    return found.scripts[0]


def _written(b):
    return {k: v for k, v in b.writes}


# locked on: O, Flame!'s motion, 60 FP x 2.5, the 38 cuts at the target
LOCKED = {f"params.Magic.{MAGIC}.refType": 25, f"params.Magic.{MAGIC}.mp": 150, **{f"params.Bullet.{BULLET}.{k}": v for k, v in
          {"shootAngle": 0, "shootAngleInterval": 0, "homingAngle": 720, "lockShootLimitAng": 180, "hitRadius": 0.5,
           "hitRadiusMax": 0.5, "isUseSharedHitList": 0}.items()}}
FAN = {f"params.Magic.{MAGIC}.refType": 106, f"params.Magic.{MAGIC}.mp": 60, **{f"params.Bullet.{BULLET}.{k}": v for k, v in GAME_BULLET.items()}}
AS_BUILT = FAN                         # not locked on is the build: Catch Flame's motion and the fan


def test_setup_writes_the_mode_of_the_lock_on_now_and_nothing_while_it_stays():
    s = _script()
    with FakeBackend(_doc(lock_on=False)) as b:
        ed._set_current(s)
        s.setup()
        assert _written(b) == FAN and len(b.writes) == len(FAN)
        s.loop(); s.loop()
        assert len(b.writes) == len(FAN)                                  # nothing more while it stays
        ed._set_current(None)


def test_a_change_of_the_lock_on_writes_the_other_mode_once_and_teardown_puts_the_build_back():
    s = _script()
    with FakeBackend(_doc(lock_on=False)) as b:
        ed._set_current(s)
        s.setup()
        b.writes.clear()
        b.doc["character"]["lock_on"] = True
        s.loop(); s.loop()
        assert _written(b) == LOCKED and len(b.writes) == len(LOCKED)
        b.writes.clear()
        b.doc["character"]["lock_on"] = False
        s.loop()
        assert _written(b) == FAN
        b.writes.clear()
        s.teardown()
        assert _written(b) == AS_BUILT
        ed._set_current(None)


def test_locked_on_at_the_start_and_the_build_read_from_the_design_and_the_game():
    s = _script()
    with FakeBackend(_doc(lock_on=True)) as b:
        ed._set_current(s)
        s.setup()
        assert _written(b) == LOCKED
        assert s.built[("Bullet", "homingAngle")] == 0 and s.built[("Bullet", "shootAngle")] == -92     # the game's / the design's
        ed._set_current(None)


def test_no_dismantle_in_the_build_or_no_lock_on_ends_the_script():
    s = _script()
    with FakeBackend(_doc(with_spell=False)) as b:
        ed._set_current(s)
        with pytest.raises(ed._Dead):
            s.setup()
        ed._set_current(None)
    assert b.writes == [] and any("not in the last build" in m for _l, m in b.lines)
    doc = _doc()
    del doc["character"]["lock_on"]
    s = _script()
    with FakeBackend(doc) as b:
        ed._set_current(s)
        with pytest.raises(ed._Dead):
            s.setup()
        ed._set_current(None)
    assert b.writes == [] and any("no character.lock_on" in m for _l, m in b.lines)


def test_out_of_the_world_the_loop_waits():
    s = _script()
    with FakeBackend(_doc()) as b:
        ed._set_current(s)
        s.setup()
        n = len(b.writes)
        b.doc["character"] = None
        with pytest.raises(ed._NotInWorld):
            s.loop()
        assert len(b.writes) == n
        ed._set_current(None)


def test_the_fp_locked_on_comes_from_the_design_even_when_the_game_holds_the_locked_one():
    doc = _doc(lock_on=True)
    doc["params"]["Magic"][str(MAGIC)]["mp"] = 150          # the script stopped while locked on, and started again
    s = _script()
    with FakeBackend(doc) as b:
        ed._set_current(s)
        s.setup()
        assert _written(b)[f"params.Magic.{MAGIC}.mp"] == 150 and s.built[("Magic", "mp")] == 60
        b.doc["character"]["lock_on"] = False
        s.loop()
        assert _written(b)[f"params.Magic.{MAGIC}.mp"] == 60
        ed._set_current(None)
    doc = _doc()
    del doc["creative"]["innovate_spells"]["2230001"]["design"]["requires"]      # no cost in the design: the game's, as built
    s = _script()
    with FakeBackend(doc) as b:
        ed._set_current(s)
        s.setup()
        assert s.built[("Magic", "mp")] == 60
        ed._set_current(None)

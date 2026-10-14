"""`write params.<Table>.<id>.<field>=…` and `=default` for the six workbench tables (Phase 1, step 1.3): range-checked, bit-exact,
the game's own value remembered before the first change and put back by `NAME=default`."""
import json
import struct

import pytest

import eldendisk.commands.write as wcmd
from eldendisk.game.params import ParamNameError
from eldendisk.writer import paramedit as PE
from eldendisk.writer.paramedit import SNAPSHOT_NAME
from tests.test_param_tables import MAGIC, encode, put_table, tables
from tests.test_write_command import GAME_PID, GAME_STARTED, rig  # noqa: F401  (the rig fixture)


@pytest.fixture
def world(rig):
    vault, mem, box, open_session, args = rig
    put_table(mem, "Magic", {**MAGIC, 6240: encode("Magic", mp=5, isEnchant=1, isShieldEnchant=1, refId1=777)})
    put_table(mem, "SpEffect", {1621000: encode("SpEffect", changeHpRate=0.1, effectEndurance=2.0)}, index=1)
    open_session()
    return vault, mem, args


def row(mem, table, rid):
    return tables(mem).read_row(table, rid)


def snap(vault):
    return json.loads((vault.root / SNAPSHOT_NAME).read_text())


# ---- writing ----
def test_a_number_field_is_set_and_the_game_value_is_remembered(world, capsys):
    vault, mem, args = world
    assert wcmd.cmd_write(args("params.Magic.6230.mp=10")) == 0
    assert row(mem, "Magic", 6230)["mp"] == 10 and row(mem, "Magic", 6210)["mp"] == 18   # only that row
    assert "params.Magic.6230.mp = 10" in capsys.readouterr().err
    doc = snap(vault)
    assert doc["game_pid"] == GAME_PID and doc["game_started"] == GAME_STARTED
    assert doc["values"] == {"Magic.6230.mp": struct.pack("<h", 21).hex()}


def test_names_and_fields_are_not_case_sensitive_and_other_fields_stay_untouched(world):
    vault, mem, args = world
    before = row(mem, "Magic", 6230)
    assert wcmd.cmd_write(args("params.magic.6230.MP=7")) == 0
    after = row(mem, "Magic", 6230)
    assert after.pop("mp") == 7 and before.pop("mp") == 21 and after == before


def test_a_float_field_and_a_negative_value(world):
    vault, mem, args = world
    assert wcmd.cmd_write(args("params.SpEffect.1621000.changeHpRate=-0.1", "params.SpEffect.1621000.effectEndurance=-1")) == 0
    r = row(mem, "SpEffect", 1621000)
    assert r["changeHpRate"] == -0.1 and r["effectEndurance"] == -1.0


def test_the_first_value_is_kept_when_a_field_is_set_again(world):
    vault, mem, args = world
    wcmd.cmd_write(args("params.Magic.6230.mp=10"))
    wcmd.cmd_write(args("params.Magic.6230.mp=3"))
    assert row(mem, "Magic", 6230)["mp"] == 3
    assert snap(vault)["values"]["Magic.6230.mp"] == struct.pack("<h", 21).hex()


def test_a_bit_field_changes_only_its_own_bit(world):
    vault, mem, args = world
    assert wcmd.cmd_write(args("params.Magic.6230.isShieldEnchant=1")) == 0
    r = row(mem, "Magic", 6230)
    assert r["isShieldEnchant"] == 1 and r["isEnchant"] == 1 and r["mp"] == 21      # the same byte holds isEnchant


def test_a_pattern_sets_several_fields_and_an_id_field_gets_a_note(world, capsys):
    vault, mem, args = world
    assert wcmd.cmd_write(args("params.Magic.6230.refId*=-1")) == 0
    r = row(mem, "Magic", 6230)
    assert r["refId1"] == -1 and r["refId4"] == -1 and r["refCategory1"] == 1
    err = capsys.readouterr().err
    assert "matches" in err and "id of another row" in err


@pytest.mark.parametrize("assign,why", [
    ("params.Magic.6230.refCategory1=300", "0..255"),          # u8
    ("params.Magic.6230.mp=40000", "-32768..32767"),           # s16
    ("params.Magic.6230.mp=1.5", "whole number"),
    ("params.Magic.6230.isEnchant=2", "1 bit"),
    ("params.SpEffect.1621000.changeHpRate=nan", "does not fit"),
    ("params.Magic.6230.mpp=1", "did you mean mp"),
    ("params.Magic.6230=1", "name one field"),
    ("params.Magic.x.mp=1", "one number"),
    ("params.Nothing.1.mp=1", "not a table of the game"),
    ("params.Magic.6230.mp=1", None),                          # control: this one is fine
])
def test_a_value_that_does_not_fit_or_a_wrong_name_writes_nothing(world, capsys, assign, why):
    vault, mem, args = world
    mem.log.clear()
    rc = wcmd.cmd_write(args(assign))
    if why is None:
        assert rc == 0
        return
    assert rc == 1 and why in capsys.readouterr().err and mem.log == []
    assert not (vault.root / SNAPSHOT_NAME).exists()


def test_a_row_that_is_not_in_the_game_is_not_applied(world, capsys):
    vault, mem, args = world
    mem.log.clear()
    assert wcmd.cmd_write(args("params.Magic.99999.mp=1")) == 1
    assert "not in the file" in capsys.readouterr().err and mem.log == []


def test_the_short_and_the_games_names_of_a_table_work_in_one_command_and_effects_is_gone(world, capsys):
    vault, mem, args = world
    assert wcmd.cmd_write(args("params.SpEffect.1621000.effectEndurance=-1", "params.Magic.6230.mp=10", "level=150")) == 0
    assert row(mem, "Magic", 6230)["mp"] == 10 and row(mem, "SpEffectParam", 1621000)["effectEndurance"] == -1.0
    mem.log.clear()
    assert wcmd.cmd_write(args("params.effects.1621000.effectEndurance=-1")) == 1 and mem.log == []
    assert "params.SpEffectParam.1621000.effectEndurance" in capsys.readouterr().err       # where the rows went (1.8.0)


# ---- resetting ----
def test_reset_puts_the_game_value_back_and_forgets_it(world, capsys):
    vault, mem, args = world
    wcmd.cmd_write(args("params.Magic.6230.mp=10", "params.Magic.6230.isEnchant=0", "params.Magic.6210.mp=1"))
    assert wcmd.cmd_write(args(set=[], reset=["params.Magic.6230.mp"])) == 0
    assert row(mem, "Magic", 6230)["mp"] == 21 and row(mem, "Magic", 6210)["mp"] == 1
    assert "Magic.6230.mp" not in snap(vault)["values"] and "Magic.6210.mp" in snap(vault)["values"]
    capsys.readouterr()
    assert wcmd.cmd_write(args(set=[], reset=["params.Magic.6230.mp"])) == 1               # nothing is left to put back
    assert "nothing to put back" in capsys.readouterr().err


def test_reset_of_a_row_a_table_a_pattern_and_all(world):
    vault, mem, args = world
    wcmd.cmd_write(args("params.Magic.6230.mp=1", "params.Magic.6230.stamina=1", "params.Magic.6210.mp=1",
                        "params.SpEffect.1621000.effectEndurance=-1"))
    assert wcmd.cmd_write(args(set=[], reset=["params.Magic.6230"])) == 0
    r = row(mem, "Magic", 6230)
    assert (r["mp"], r["stamina"], row(mem, "Magic", 6210)["mp"]) == (21, 0, 1)
    assert wcmd.cmd_write(args(set=[], reset=["params.Magic.*.mp"])) == 0
    assert row(mem, "Magic", 6210)["mp"] == 18
    assert wcmd.cmd_write(args(set=[], reset=["all"])) == 0
    assert row(mem, "SpEffect", 1621000)["effectEndurance"] == 2.0
    assert snap(vault)["values"] == {}


def test_reset_of_a_bit_leaves_the_other_bits_as_they_are_now(world):
    vault, mem, args = world
    wcmd.cmd_write(args("params.Magic.6230.isEnchant=0", "params.Magic.6230.isShieldEnchant=1"))
    wcmd.cmd_write(args(set=[], reset=["params.Magic.6230.isEnchant"]))
    r = row(mem, "Magic", 6230)
    assert r["isEnchant"] == 1 and r["isShieldEnchant"] == 1                 # the shield bit was changed on purpose


def test_a_new_game_process_starts_without_memory_of_the_old_one(world, rig, capsys):
    vault, mem, args = world
    wcmd.cmd_write(args("params.Magic.6230.mp=10"))
    doc = snap(vault)
    doc["game_pid"] += 1                                                       # the file now belongs to another process
    (vault.root / SNAPSHOT_NAME).write_text(json.dumps(doc))
    assert wcmd.cmd_write(args(set=[], reset=["params.Magic.6230.mp"])) == 1
    assert row(mem, "Magic", 6230)["mp"] == 10


def test_a_broken_snapshot_file_is_not_fatal(world):
    vault, mem, args = world
    (vault.root / SNAPSHOT_NAME).write_text("{ not json")
    assert wcmd.cmd_write(args("params.Magic.6230.mp=10")) == 0
    assert snap(vault)["values"]


def test_no_session_means_no_snapshot_and_no_write(rig):
    vault, mem, box, open_session, args = rig
    put_table(mem, "Magic", MAGIC)
    mem.log.clear()
    assert wcmd.cmd_write(args("params.Magic.6230.mp=10")) != 0
    assert mem.log == [] and not (vault.root / SNAPSHOT_NAME).exists()


# ---- the helpers ----
def test_values_are_checked_by_type():
    assert PE.check_value("Magic", "mp", "-5") == -5
    assert PE.check_value("Bullet", "life", "0.5") == 0.5
    with pytest.raises(ParamNameError):
        PE.check_value("Magic", "refCategory1", "-1")


def test_a_unit_is_changed_in_its_own_bits_and_restored_from_the_original():
    unit = bytes([0b0000_1100])
    new = PE.with_value("Magic", "isEnchant", unit, 0)           # bit 2 of byte 49
    assert new == bytes([0b0000_1000])
    assert PE.restore("Magic", "isEnchant", bytes([0b0000_1010]), unit) == bytes([0b0000_1110])


def test_id_like_names():
    assert all(PE.looks_like_an_id(f) for f in ("refId1", "spEffectId0", "HitBulletID", "sfxId_Bullet", "atkId_Bullet"))
    assert not any(PE.looks_like_an_id(f) for f in ("mp", "sortId", "iconId", "life", "weight"))

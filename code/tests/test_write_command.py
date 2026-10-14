"""`write NAME=VALUE | NAME=default`: only inside a session the record authorises (spec 1.6.2 section 3), never otherwise."""
import argparse
import struct
from dataclasses import replace

import pytest

import eldendisk.__main__ as cli
import eldendisk.commands.write as wcmd
from eldendisk.game.attach import EXIT_EAC, EXIT_NO_SESSION, AttachError, Target
from eldendisk.game.memory import Module
from eldendisk.vault import SaveVault, SessionState
from eldendisk.vault import session as sess
from tests import paramfile as pf
from tests.test_disk import BASE, DATA_MOD, GD, full_world
from tests.test_memory_writer import WMem

EXE_SHA = "ab" * 32
HOST_PID, HOST_STARTED, GAME_PID, GAME_STARTED = 100, 555, 4242, 777


@pytest.fixture
def rig(tmp_path, monkeypatch):
    live = tmp_path / "Users" / "me" / "EldenRing" / "1"
    live.mkdir(parents=True)
    (live / "ER0000.sl2").write_bytes(b"save")
    vault = SaveVault(tmp_path / "vault")
    mem = WMem()
    mem.b = full_world().b
    pf.build_file(mem, pf.small_ids(), rows={1622000: pf.row_bytes(effect_endurance=7.5, vfx=1)})   # the game's params
    pf.wire(mem, 0)
    box = {"opened": 0, "closed": 0, "host_started": HOST_STARTED, "locate": None}
    mem.close = lambda: box.__setitem__("closed", box["closed"] + 1)
    target = Target(GAME_PID, GAME_STARTED, Module("eldenring.exe", BASE, str(tmp_path / "eldenring.exe")), EXE_SHA, pf.params_profile())
    box["locate"] = lambda offsets: target

    def open_handle(pid):
        box["opened"] += 1
        return mem

    monkeypatch.setattr(wcmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(wcmd, "locate", lambda offsets: box["locate"](offsets))
    monkeypatch.setattr(wcmd, "process_started", lambda pid: box["host_started"] if pid == HOST_PID else None)
    monkeypatch.setattr(wcmd, "WritableProcessMemory", open_handle)

    def open_session(**changes):
        vault.write_session(vault.new_record(vault.snapshot(live), live, exe_sha256=EXE_SHA,
                                             host_pid=HOST_PID, host_started=HOST_STARTED))
        vault.update_session(**{"state": SessionState.RUNNING, "game_pid": GAME_PID, "game_started": GAME_STARTED, **changes})

    def args(*assignments, **kw):
        """`write` as the command line gives it: NAME=VALUE pairs; `reset` names become NAME=default (`all`: params=default)."""
        sets = list(kw.pop("set")) if "set" in kw else (list(assignments) or ["level=150"])
        pairs = sets + [("params" if r == "all" else r) + "=default" for r in kw.pop("reset", [])]
        d = dict(pairs=pairs, verbose=False, vault=str(vault.root), offsets="x")
        return argparse.Namespace(**{**d, **kw})

    return vault, mem, box, open_session, args


def level(mem):
    return struct.unpack("<I", mem.read(GD + 0x68, 4))[0]


def refused(box, mem, code, rc):
    assert rc == code and box["opened"] == 0 and mem.log == []


def test_no_session_no_write_and_no_write_handle(rig, capsys):
    vault, mem, box, open_session, args = rig
    refused(box, mem, EXIT_NO_SESSION, wcmd.cmd_write(args()))
    assert "eldendisk run" in capsys.readouterr().err


def test_an_unreadable_record_means_no_write(rig):
    vault, mem, box, open_session, args = rig
    vault.root.mkdir(parents=True, exist_ok=True)
    (vault.root / sess.SESSION_NAME).write_text("{ not json")
    refused(box, mem, EXIT_NO_SESSION, wcmd.cmd_write(args()))


def test_an_authorised_edit_is_applied_and_the_handle_is_closed(rig, capsys):
    vault, mem, box, open_session, args = rig
    open_session()
    assert wcmd.cmd_write(args(verbose=True)) == 0
    assert level(mem) == 150 and box["opened"] == 1 and box["closed"] == 1 and "level = 150" in capsys.readouterr().err


def test_a_vital_above_its_maximum_fills_it_through_the_same_authorisation(rig):
    vault, mem, box, open_session, args = rig          # 1.8.0: `write hp=<a big number>` is what `--refill hp` was
    open_session()
    mem.put(DATA_MOD + 0x138, struct.pack("<i", 5))
    assert wcmd.cmd_write(args("hp=999999")) == 0
    assert struct.unpack("<i", mem.read(DATA_MOD + 0x138, 4))[0] == struct.unpack("<i", mem.read(DATA_MOD + 0x138 + 4, 4))[0]


def test_write_alone_lists_the_names_and_their_ranges_and_writes_nothing(rig, capsys):
    vault, mem, box, open_session, args = rig
    assert wcmd.cmd_write(args(set=[])) == 0 and box["opened"] == 0
    out = capsys.readouterr()
    text = out.out + out.err
    for name in ("level", "vigor", "params.<Table>.<id>.<field>", "creative.resurrect.great_enemies", "default"):
        assert name in text


@pytest.mark.parametrize("changes", [
    {"state": SessionState.READY},                # the game has not been started by the host yet
    {"state": SessionState.RESTORING},
    {"state": SessionState.RESTORE_PENDING},      # a console close / second Ctrl+C / crash left it pending
    {"snapshot_verified": False},
    {"game_pid": GAME_PID + 1},                   # not the game the host started
    {"game_started": GAME_STARTED + 1},           # same pid, different process (pid reuse)
    {"game_pid": None, "game_started": None},
    {"exe_sha256": "cd" * 32},                    # a different eldenring.exe than the one that was snapshotted
    {"host_pid": HOST_PID + 1},                   # the host is gone
])
def test_every_unmet_condition_refuses(rig, changes, capsys):
    vault, mem, box, open_session, args = rig
    open_session(**changes)
    refused(box, mem, EXIT_NO_SESSION, wcmd.cmd_write(args()))
    assert "refused, no edit was made" in capsys.readouterr().err


def test_a_host_that_died_and_whose_pid_was_reused_does_not_authorise(rig):
    vault, mem, box, open_session, args = rig
    open_session()
    box["host_started"] = HOST_STARTED + 1        # same pid, another process
    refused(box, mem, EXIT_NO_SESSION, wcmd.cmd_write(args()))


def test_reasons_are_all_listed(rig, capsys):
    vault, mem, box, open_session, args = rig
    open_session(state=SessionState.READY, snapshot_verified=False, host_pid=HOST_PID + 1)
    wcmd.cmd_write(args())
    err = capsys.readouterr().err
    assert "READY" in err and "not verified" in err and "host" in err


def test_eac_and_a_missing_game_never_open_a_handle(rig, capsys):
    vault, mem, box, open_session, args = rig
    open_session()

    def eac(offsets):
        raise AttachError("EasyAntiCheat is loaded", EXIT_EAC)

    def missing(offsets):
        raise AttachError("eldenring.exe is not running")

    box["locate"] = eac
    refused(box, mem, EXIT_EAC, wcmd.cmd_write(args()))
    box["locate"] = missing
    refused(box, mem, 1, wcmd.cmd_write(args()))


def test_an_edit_that_could_not_be_applied_is_an_error_not_silence(rig, capsys):
    vault, mem, box, open_session, args = rig
    open_session()
    mem.b = type(mem.b)()                         # not in a world (title screen): nothing to write to
    assert wcmd.cmd_write(args()) == 1 and mem.log == [] and box["closed"] == 1
    assert "not applied" in capsys.readouterr().err


def test_a_bad_policy_is_reported_before_anything_is_looked_at(rig, capsys):
    vault, mem, box, open_session, args = rig
    assert cli.main(["write", "bogus=1", "--vault", str(vault.root)]) == 1
    assert "bogus" in capsys.readouterr().err and box["opened"] == 0


# ---- game params (spec 1.6.3): `write params...=VALUE`, `=default`, the same authorisation as every other edit ----
from eldendisk.game.params import ParamStore   # noqa: E402

BF = "params.effects.1621000"


def rows_of(mem):
    res = ParamStore(mem, pf.params_profile(), BASE).resolve("effects").rows
    return {name: res[str(rid)] for name, rid in pf.ROWS.items()}      # the tests call the rows by their short names


def snapshot(mem):
    return {n: mem.read(a, pf.ROW) for n, a in rows_of(mem).items()}


def f32(mem, row, offset=0x8):
    return struct.unpack("<f", mem.read(rows_of(mem)[row] + offset, 4))[0]


def s32(mem, row, offset):
    return struct.unpack("<i", mem.read(rows_of(mem)[row] + offset, 4))[0]


def changed_bytes(before, after):
    """{row: sorted offsets of the bytes that differ}"""
    return {n: [i for i in range(pf.ROW) if before[n][i] != after[n][i]] for n in before if before[n] != after[n]}


def test_a_param_edit_changes_that_field_and_nothing_else(rig, capsys):
    vault, mem, box, open_session, args = rig
    open_session()
    before = snapshot(mem)
    other = mem.read(rows_of(mem)["black_flame"] + pf.ROW, pf.ROW)    # the next row in the file
    assert wcmd.cmd_write(args(f"{BF}.effectEndurance=-1")) == 0
    assert f32(mem, "black_flame") == -1.0
    diff = changed_bytes(before, snapshot(mem))
    assert set(diff) == {"black_flame"} and set(diff["black_flame"]) <= {8, 9, 10, 11}   # inside the four bytes of one field
    assert mem.read(rows_of(mem)["black_flame"] + pf.ROW, pf.ROW) == other
    assert f32(mem, "scouring_black_flame") == 2.0 and level(mem) == 386
    assert f"{BF}.effectEndurance = -1.0" in capsys.readouterr().err
    assert box["opened"] == 1 and box["closed"] == 1


def test_params_and_character_values_are_edited_in_one_command(rig):
    vault, mem, box, open_session, args = rig
    open_session()
    assert wcmd.cmd_write(args("level=150", f"{BF}.changeHpPoint=5", f"{BF}.changeHpRate=0.5")) == 0
    assert level(mem) == 150 and s32(mem, "black_flame", 0xA0) == 5
    assert f32(mem, "black_flame", 0x9C) == pytest.approx(0.5)


def test_a_pattern_edits_every_row_it_matches_and_says_so(rig, capsys):
    vault, mem, box, open_session, args = rig
    open_session()
    assert wcmd.cmd_write(args("params.effects.*.effectEndurance=-1")) == 0
    assert [f32(mem, r) for r in pf.ROWS] == [-1.0] * 4
    assert "matches 4 values" in capsys.readouterr().err


def test_locked_fields_are_skipped_by_a_pattern_and_never_written(rig, capsys):
    vault, mem, box, open_session, args = rig
    open_session()
    before = snapshot(mem)
    assert wcmd.cmd_write(args(f"{BF}.*=1")) == 0
    err = capsys.readouterr().err
    assert "skipped (locked)" in err and "vfxId" in err and "atkOccurrenceSpEffectId" in err
    after = snapshot(mem)
    assert s32(mem, "black_flame", 0x170) == 9010 and s32(mem, "black_flame", 0x12C) == -1
    assert set(changed_bytes(before, after)) == {"black_flame"}
    assert all(i < 0xA4 for i in changed_bytes(before, after)["black_flame"])      # only the four writable fields


@pytest.mark.parametrize("field", ["vfxId", "atkOccurrenceSpEffectId", "VFXID", "name"])
@pytest.mark.parametrize("session", [True, False])
def test_a_locked_field_is_refused_with_exit_2_whatever_the_session(rig, field, session, capsys):
    vault, mem, box, open_session, args = rig
    if session:
        open_session()
    refused(box, mem, 2, wcmd.cmd_write(args(f"{BF}.{field}=1")))
    assert "locked" in capsys.readouterr().err
    assert wcmd.cmd_write(args(set=[], reset=[f"{BF}.{field}"])) == 2


def test_a_locked_name_stops_the_whole_command(rig):
    vault, mem, box, open_session, args = rig
    open_session()
    refused(box, mem, 2, wcmd.cmd_write(args("level=150", f"{BF}.effectEndurance=-1", f"{BF}.vfxId=1")))
    assert level(mem) == 386 and f32(mem, "black_flame") == 2.0


def test_a_param_edit_without_a_session_writes_nothing(rig, capsys):
    vault, mem, box, open_session, args = rig
    refused(box, mem, EXIT_NO_SESSION, wcmd.cmd_write(args(f"{BF}.effectEndurance=-1")))
    refused(box, mem, EXIT_NO_SESSION, wcmd.cmd_write(args(set=[], reset=["all"])))
    assert "eldendisk run" in capsys.readouterr().err
    open_session(snapshot_verified=False)         # a `run --vault-off` has no record at all: the same refusal as any write
    refused(box, mem, EXIT_NO_SESSION, wcmd.cmd_write(args(f"{BF}.effectEndurance=-1")))


@pytest.mark.parametrize("bad,why", [
    (f"{BF}.effectEndurance=abc", "takes a number"),
    (f"{BF}.changeHpPoint=1.5", "whole number"),
    (f"{BF}.changeHpPoint=", "NAME=VALUE"),
    ("params.effects.black_flam.effectEndurance=-1", "did you mean"),
    ("params.effects.1621000=1", "is a group"),
])
def test_a_bad_param_edit_is_an_error_and_nothing_is_written(rig, bad, why, capsys):
    vault, mem, box, open_session, args = rig
    open_session()
    assert wcmd.cmd_write(args(bad)) == 1 and mem.log == [] and f32(mem, "black_flame") == 2.0
    assert why in capsys.readouterr().err


def test_a_value_outside_the_range_is_clamped_and_the_user_is_told(rig, capsys):
    vault, mem, box, open_session, args = rig
    open_session()
    assert wcmd.cmd_write(args(f"{BF}.effectEndurance=-5", f"{BF}.motionInterval=0", f"{BF}.changeHpPoint=100000")) == 0
    err = capsys.readouterr().err
    assert f32(mem, "black_flame") == -1.0 and f32(mem, "black_flame", 0xC) == pytest.approx(0.01)
    assert s32(mem, "black_flame", 0xA0) == 999 and err.count("clamped") == 3


def test_reset_puts_the_games_own_values_back_at_three_levels(rig):
    vault, mem, box, open_session, args = rig
    open_session()
    original = snapshot(mem)
    everything = [f"{BF}.effectEndurance=-1", f"{BF}.motionInterval=5", f"{BF}.changeHpRate=-3", f"{BF}.changeHpPoint=7",
                  "params.effects.1623000.effectEndurance=-1", "level=150"]
    assert wcmd.cmd_write(args(*everything)) == 0
    assert wcmd.cmd_write(args(set=[], reset=[f"{BF}.effectEndurance"])) == 0         # one field
    assert f32(mem, "black_flame") == 2.0 and f32(mem, "black_flame", 0xC) == 5.0
    assert wcmd.cmd_write(args(set=[], reset=[BF])) == 0                               # one row
    assert snapshot(mem)["black_flame"] == original["black_flame"]
    assert f32(mem, "scouring_black_flame") == -1.0
    assert wcmd.cmd_write(args(set=[], reset=["all"])) == 0                            # everything
    assert snapshot(mem) == original
    assert level(mem) == 150                                                           # `all` is params only


def test_reset_with_nothing_to_reset_says_so_and_is_not_an_error(rig, capsys):
    vault, mem, box, open_session, args = rig
    open_session()
    assert wcmd.cmd_write(args(set=[], reset=["all"])) == 0 and mem.log == []
    assert "values already match" in capsys.readouterr().err


@pytest.mark.parametrize("reset", [["level"], ["hp"], ["params.effects.1621000.effectEndurance=2"], ["bogus"]])
def test_only_params_can_be_reset(rig, reset, capsys):
    vault, mem, box, open_session, args = rig
    open_session()
    assert wcmd.cmd_write(args(set=[], reset=reset)) == 1 and mem.log == []
    assert "default" in capsys.readouterr().err


def test_the_same_field_cannot_be_set_twice_or_set_and_reset(rig):
    vault, mem, box, open_session, args = rig
    open_session()
    assert wcmd.cmd_write(args(f"{BF}.effectEndurance=-1", "params.effects.*.effectEndurance=3")) == 1
    assert wcmd.cmd_write(args(f"{BF}.effectEndurance=-1", reset=[BF])) == 1
    assert wcmd.cmd_write(args(f"{BF}.effectEndurance=-1", f"{BF}.effectEndurance=2")) == 1
    assert mem.log == [] and f32(mem, "black_flame") == 2.0


def test_a_file_that_fails_its_checks_is_never_written_to_and_the_reason_is_shown(rig, capsys):
    vault, mem, box, open_session, args = rig
    open_session()
    mem.put(pf.HEAD + 0x30, struct.pack("<Q", 12345))          # the header no longer adds up
    assert wcmd.cmd_write(args(f"{BF}.effectEndurance=-1")) == 1 and mem.log == []
    err = capsys.readouterr().err
    assert "not applied" in err and "data start 12345" in err


def test_a_game_version_without_params_cannot_edit_them(rig, capsys):
    vault, mem, box, open_session, args = rig
    open_session()
    bare = replace(pf.params_profile(), params=None)
    box["locate"] = lambda offsets: Target(GAME_PID, GAME_STARTED, Module("eldenring.exe", BASE, "x"), EXE_SHA, bare)
    assert wcmd.cmd_write(args(f"{BF}.effectEndurance=-1")) == 1 and mem.log == []
    assert "no params" in capsys.readouterr().err
    assert wcmd.cmd_write(args("level=150")) == 0           # everything else still works


def test_the_game_not_being_in_a_world_does_not_matter_to_params(rig):
    vault, mem, box, open_session, args = rig
    open_session()
    mem.put(BASE + 0x1000, struct.pack("<Q", 0))            # title screen: no WorldChrMan, the param tables are still there
    assert wcmd.cmd_write(args(f"{BF}.effectEndurance=-1")) == 0 and f32(mem, "black_flame") == -1.0


def test_the_cli_takes_name_value_pairs(rig):
    vault, mem, box, open_session, args = rig
    ns = cli.build_parser().parse_args(["write", f"{BF}.effectEndurance=-1", "params=default", f"{BF}=default"])
    assert ns.pairs == [f"{BF}.effectEndurance=-1", "params=default", f"{BF}=default"]
    assert cli.build_parser().parse_args(["write"]).pairs == []
    for gone in (["write", "--set", "level=1"], ["write", "--reset", "all"], ["write", "--refill", "hp"], ["write", "--text"]):
        with pytest.raises(SystemExit):
            cli.build_parser().parse_args(gone)

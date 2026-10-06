"""`write set|refill`: only inside a session the record authorises (spec 1.6.2 section 3), never otherwise."""
import argparse
import struct

import pytest

import eldendisk.__main__ as cli
import eldendisk.commands.write as wcmd
from eldendisk.game.attach import EXIT_EAC, EXIT_NO_SESSION, AttachError, Target
from eldendisk.game.memory import Module
from eldendisk.vault import SaveVault, SessionState
from eldendisk.vault import session as sess
from tests.test_disk import BASE, DATA_MOD, GD, full_world, make_profile
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
    box = {"opened": 0, "closed": 0, "host_started": HOST_STARTED, "locate": None}
    mem.close = lambda: box.__setitem__("closed", box["closed"] + 1)
    target = Target(GAME_PID, GAME_STARTED, Module("eldenring.exe", BASE, str(tmp_path / "eldenring.exe")), EXE_SHA, make_profile())
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
        d = dict(set=list(assignments) or ["level=150"], refill=None, verbose=False,
                 vault=str(vault.root), offsets="x")
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


def test_refill_goes_through_the_same_authorisation(rig):
    vault, mem, box, open_session, args = rig
    open_session()
    mem.put(DATA_MOD + 0x138, struct.pack("<i", 5))
    assert wcmd.cmd_write(args(set=[], refill="hp")) == 0
    assert struct.unpack("<i", mem.read(DATA_MOD + 0x138, 4))[0] == struct.unpack("<i", mem.read(DATA_MOD + 0x138 + 4, 4))[0]


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
    assert cli.main(["write", "--set", "bogus=1", "--vault", str(vault.root)]) == 1
    assert "bogus" in capsys.readouterr().err and box["opened"] == 0

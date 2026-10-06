"""`sandbox --set/--refill` client (1.6.1): only inside a session that holds a restore marker; argparse keeps --vault."""
import struct
from pathlib import Path

import pytest

import eldendisk.__main__ as cli
from eldendisk.memory_reader import Module
from eldendisk.save_vault import SaveVault
from tests.test_disk import BASE, GD, full_world, make_profile
from tests.test_memory_writer import WMem

EXE_SHA = "ab" * 32


@pytest.fixture
def rig(tmp_path, monkeypatch):
    import argparse
    import eldendisk.memory_reader as mr
    import eldendisk.memory_writer as mw

    live = tmp_path / "Users" / "me" / "EldenRing" / "1"
    live.mkdir(parents=True)
    (live / "ER0000.sl2").write_bytes(b"save")
    vault = SaveVault(tmp_path / "vault")
    exe = tmp_path / "eldenring.exe"
    exe.write_bytes(b"EXE")
    mem = WMem()
    mem.b = full_world().b
    state = {"modules": ["eldenring.exe", "kernel32.dll"], "closed": False}
    mem.close = lambda: state.__setitem__("closed", True)
    monkeypatch.setattr(cli, "_require_windows_x64", lambda: None)
    monkeypatch.setattr(cli.gl, "sha256_file", lambda p: EXE_SHA)
    monkeypatch.setattr(cli, "load_profile", lambda p, h: (make_profile(), None))
    monkeypatch.setattr(mr, "find_pid", lambda name: 1234)
    monkeypatch.setattr(mr, "list_modules", lambda pid: [Module(n, BASE, str(exe)) for n in state["modules"]])
    monkeypatch.setattr(mw, "WritableProcessMemory", lambda pid: mem)

    def args(**kw):
        d = dict(set=["level=150"], refill=None, verbose=False, vault=str(vault.root), offsets="x",
                 effects=str(tmp_path / "none.json"))
        return argparse.Namespace(**{**d, **kw})

    def open_session(sha=EXE_SHA):
        vault.write_marker(vault.snapshot(live), live, exe_sha256=sha)

    return vault, mem, state, args, open_session


def level(mem):
    return struct.unpack("<I", mem.read(GD + 0x68, 4))[0]


def test_no_session_no_write(rig, capsys):
    vault, mem, state, args, _ = rig
    assert cli.cmd_sandbox_edit(args()) == cli.EXIT_NO_SESSION
    assert mem.log == [] and not state["closed"] and "eldendisk run" in capsys.readouterr().err


def test_unreadable_marker_means_no_write(rig):
    vault, mem, state, args, _ = rig
    vault.root.mkdir(parents=True, exist_ok=True)
    vault.marker_path.write_text("{ not json")
    assert cli.cmd_sandbox_edit(args()) == cli.EXIT_NO_SESSION and mem.log == []


def test_edit_is_applied_inside_a_session_and_the_handle_is_closed(rig, capsys):
    vault, mem, state, args, open_session = rig
    open_session()
    assert cli.cmd_sandbox_edit(args(verbose=True)) == 0
    assert level(mem) == 150 and state["closed"] and "Applied 1 edit(s)" in capsys.readouterr().err


def test_a_different_exe_than_the_session_was_started_for_is_refused(rig):
    vault, mem, state, args, open_session = rig
    open_session(sha="cd" * 32)
    assert cli.cmd_sandbox_edit(args()) == cli.EXIT_NO_SESSION and mem.log == []


def test_eac_is_refused_even_with_a_session(rig):
    vault, mem, state, args, open_session = rig
    open_session()
    state["modules"].append("EasyAntiCheat_EOS.dll")
    assert cli.cmd_sandbox_edit(args()) == cli.EXIT_EAC and mem.log == []


def test_an_edit_that_could_not_be_applied_is_an_error_not_silence(rig, monkeypatch, capsys):
    vault, mem, state, args, open_session = rig
    open_session()
    mem.b = type(mem.b)()                    # not in a world (title screen): nothing to write to
    assert cli.cmd_sandbox_edit(args()) == 1 and mem.log == []
    assert "not applied" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [
    ["sandbox", "--vault", "VAULT", "status"],
    ["sandbox", "status", "--vault", "VAULT"],
])
def test_vault_option_is_kept_before_or_after_the_subcommand(monkeypatch, argv):
    seen = {}
    monkeypatch.setattr(cli, "_sb_status", lambda a: seen.update(vault=a.vault) or 0)
    assert cli.main([("X" if a == "VAULT" else a) for a in argv]) == 0 and seen["vault"] == "X"


def test_vault_defaults_when_not_given(monkeypatch):
    seen = {}
    monkeypatch.setattr(cli, "_sb_restore", lambda a: seen.update(vault=a.vault) or 0)
    assert cli.main(["sandbox", "restore"]) == 0 and seen["vault"] == cli.DEFAULT_VAULT

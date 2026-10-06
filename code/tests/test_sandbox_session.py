"""SandboxSession lifecycle + CLI surface (spec 1.6.0 sections 8, 12; tests T1, T4-T9, T11)."""
import os
from pathlib import Path

import pytest

import eldendisk.__main__ as cli
from eldendisk.game_launcher import GameFolderGuard, anticheat_processes, cleanup_recorded, listing
from eldendisk.sandbox import EXIT_RESTORE_PENDING, Hooks, SandboxSession, State, restore_pending
from eldendisk.save_vault import SaveVault, SessionLog, VaultError


@pytest.fixture
def env(tmp_path):
    live = tmp_path / "AppData" / "EldenRing" / "76561198000000000"
    live.mkdir(parents=True)
    (live / "ER0000.sl2").write_bytes(b"SAVE-DATA" * 1000)
    (live / "ER0000.sl2.bak").write_bytes(b"BACKUP" * 500)
    game = tmp_path / "Game"
    game.mkdir()
    (game / "eldenring.exe").write_bytes(b"EXE")
    vault = SaveVault(tmp_path / "vault", sleep=lambda s: None)
    return tmp_path, live, game, vault


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in Path(root).rglob("*") if p.is_file()}


def contaminate(live):
    (live / "ER0000.sl2").write_bytes(b"LEVEL 713 " * 2000)
    (live / "stray.dat").write_bytes(b"x")


def hooks(game, run=lambda: 0, running=False, ac=False, wait=lambda: True, extra=None, guard=True):
    return Hooks(game_running=lambda: running, anticheat_running=lambda: ac, run_game=run, wait_game_exit=wait,
                 extra_preflight=(lambda: extra) if extra else (lambda: []),
                 game_guard=GameFolderGuard(game) if guard else None, game_dir=game, exe_sha256="abc")


def session(env, **kw):
    _, live, game, vault = env
    return SandboxSession(vault, live, hooks(game, **kw.pop("h", {})), **kw)


# ---- T1 / T2: the normal flow ----
def test_full_flow_contaminates_then_restores_byte_for_byte(env):
    _, live, game, vault = env
    before, seen = tree(live), {}

    def run():
        seen["marker"] = vault.read_marker()
        seen["snapshot_ok"] = vault.verify_snapshot(Path(seen["marker"]["snapshot_dir"])) == []
        contaminate(live)                      # "memory edits got autosaved"
        return 0

    s = SandboxSession(vault, live, hooks(game, run=run))
    assert s.run() == 0
    assert seen["snapshot_ok"] and seen["marker"]["live_save_dir"] == str(live)
    assert tree(live) == before                # G1
    assert vault.read_marker() is None
    assert s.history == [State.IDLE, State.PREFLIGHT, State.SNAPSHOTTING, State.RUNNING, State.RESTORING,
                         State.VERIFYING, State.CLEANUP, State.IDLE]
    snap_dir = vault.root / vault.list_snapshots()[0]["name"]
    assert "verification passed" in (snap_dir / "session.log").read_text()


def test_exit_code_of_the_game_phase_is_returned(env):
    assert session(env, h={"run": lambda: 3}).run() == 3


def test_archive_contaminated_keeps_the_modified_save(env):
    _, live, game, vault = env
    s = SandboxSession(vault, live, hooks(game, run=lambda: contaminate(live) or 0), archive_contaminated=True)
    s.run()
    snap = vault.root / vault.list_snapshots()[0]["name"]
    assert (snap / "contaminated" / "ER0000.sl2").read_bytes().startswith(b"LEVEL 713")


# ---- T8 / preflight refusals: nothing changes ----
@pytest.mark.parametrize("kw", [{"running": True}, {"ac": True}, {"extra": ["no profile"]}])
def test_preflight_refusal_changes_nothing(env, kw):
    _, live, game, vault = env
    before, called = tree(live), []
    s = SandboxSession(vault, live, hooks(game, run=lambda: called.append(1) or 0, **kw))
    assert s.run() == 1
    assert called == [] and tree(live) == before and vault.read_marker() is None
    assert not vault.root.exists() or not any(vault.root.iterdir())
    assert s.history == [State.IDLE, State.PREFLIGHT, State.IDLE]


# ---- T4: crash recovery ----
def test_unresolved_marker_blocks_a_new_session_until_restore(env):
    _, live, game, vault = env
    before = tree(live)
    snap = vault.snapshot(live)
    vault.write_marker(snap, live, exe_sha256=None)       # as if the tool was killed mid-session
    contaminate(live)
    called = []
    assert SandboxSession(vault, live, hooks(game, run=lambda: called.append(1) or 0)).run() == 1 and not called
    log = SessionLog()
    assert restore_pending(vault, game_running=lambda: False, log=log) == 0
    assert tree(live) == before and vault.read_marker() is None
    assert SandboxSession(vault, live, hooks(game)).run() == 0   # a new session is now allowed


# ---- T5: game crash == run phase simply ends; tool crash == exception ----
def test_exception_and_interrupt_in_the_running_phase_still_restore(env):
    _, live, game, vault = env
    before = tree(live)

    def boom():
        contaminate(live)
        raise RuntimeError("tool bug")
    assert session(env, h={"run": boom}).run() == 1 and tree(live) == before and vault.read_marker() is None

    def ctrl_c():
        contaminate(live)
        raise KeyboardInterrupt
    assert session(env, h={"run": ctrl_c}).run() == 130 and tree(live) == before and vault.read_marker() is None


# ---- T6: power loss right after the marker ----
def test_power_loss_after_marker_is_recoverable(env):
    _, live, game, vault = env
    before = tree(live)
    vault.write_marker(vault.snapshot(live), live, exe_sha256=None)
    contaminate(live)
    assert restore_pending(vault, game_running=lambda: False, log=SessionLog()) == 0
    assert tree(live) == before


# ---- failure paths keep the marker and the snapshot ----
def test_game_still_running_or_second_interrupt_leaves_restore_pending(env):
    _, live, game, vault = env
    for wait in (lambda: False, lambda: (_ for _ in ()).throw(KeyboardInterrupt())):
        v = SaveVault(env[0] / f"vault-{id(wait)}", sleep=lambda s: None)
        s = SandboxSession(v, live, hooks(game, run=lambda: contaminate(live) or 0, wait=wait))
        assert s.run() == EXIT_RESTORE_PENDING and s.state is State.RESTORE_PENDING
        assert v.read_marker() is not None and v.verify_snapshot(Path(v.read_marker()["snapshot_dir"])) == []
        assert restore_pending(v, game_running=lambda: True, log=SessionLog()) == 1   # game still open: refused
        assert restore_pending(v, game_running=lambda: False, log=SessionLog()) == 0
        assert v.read_marker() is None


def test_restore_failure_keeps_marker_and_snapshot(env, monkeypatch):
    _, live, game, vault = env
    monkeypatch.setattr(vault, "restore", lambda *a, **k: (_ for _ in ()).throw(VaultError("locked")))
    s = SandboxSession(vault, live, hooks(game, run=lambda: contaminate(live) or 0))
    assert s.run() == EXIT_RESTORE_PENDING
    assert vault.read_marker() is not None and vault.verify_snapshot(Path(vault.read_marker()["snapshot_dir"])) == []


# ---- T7: verification failure never clears the marker ----
def test_failed_verification_keeps_the_marker(env, monkeypatch):
    _, live, game, vault = env
    monkeypatch.setattr(vault, "verify_live", lambda *a, **k: ["hash mismatch: ER0000.sl2"])
    s = SandboxSession(vault, live, hooks(game))
    assert s.run() == EXIT_RESTORE_PENDING and vault.read_marker() is not None and s.history[-1] is State.RESTORE_PENDING


# ---- T9: idempotence ----
def test_restore_twice_second_is_a_noop(env):
    _, live, game, vault = env
    vault.write_marker(vault.snapshot(live), live, exe_sha256=None)
    contaminate(live)
    log = SessionLog()
    assert restore_pending(vault, game_running=lambda: False, log=log) == 0
    after = tree(live)
    assert restore_pending(vault, game_running=lambda: False, log=log) == 0 and tree(live) == after


# ---- T11 / FR-11: game folder hygiene ----
def test_files_created_in_the_game_folder_are_removed_and_recorded(env):
    _, live, game, vault = env
    before, seen = listing(game), {}

    def run():
        guard.create_file("steam_appid.txt", b"1245620")
        seen["marker_files"] = vault.read_marker()["game_folder_files_created"]
        return 0

    guard = GameFolderGuard(game)
    h = Hooks(game_running=lambda: False, anticheat_running=lambda: False, run_game=run, wait_game_exit=lambda: True,
              game_guard=guard, game_dir=game)
    assert SandboxSession(vault, live, h).run() == 0
    assert seen["marker_files"] == ["steam_appid.txt"] and listing(game) == before and guard.diff() == []


def test_crash_recovery_also_cleans_the_game_folder(env):
    _, live, game, vault = env
    snap = vault.snapshot(live)
    vault.write_marker(snap, live, exe_sha256=None, game_dir=game, game_files=["steam_appid.txt"])
    (game / "steam_appid.txt").write_text("1245620")
    assert restore_pending(vault, game_running=lambda: False, log=SessionLog()) == 0
    assert not (game / "steam_appid.txt").exists() and (game / "eldenring.exe").exists()


def test_guard_never_touches_existing_files_or_paths_outside(env):
    _, live, game, vault = env
    g = GameFolderGuard(game)
    with pytest.raises(FileExistsError):
        g.create_file("eldenring.exe", b"x")
    with pytest.raises(ValueError):
        g.create_file("../escape.txt", b"x")
    assert (game / "eldenring.exe").read_bytes() == b"EXE"
    (game.parent / "victim.txt").write_text("keep")
    assert cleanup_recorded(game, ["../victim.txt"]) == [] and (game.parent / "victim.txt").exists()


def test_guard_diff_reports_changes(env):
    _, _, game, _ = env
    g = GameFolderGuard(game); g.take_listing()
    (game / "new.log").write_text("x"); (game / "eldenring.exe").write_bytes(b"EXEEXE")
    assert g.diff() == ["added: new.log", "size changed: eldenring.exe"]


def test_anticheat_process_detection():
    assert anticheat_processes(["explorer.exe", "EasyAntiCheat_EOS.exe", "start_protected_game.exe"]) == \
        ["EasyAntiCheat_EOS.exe", "start_protected_game.exe"]
    assert anticheat_processes(["eldenring.exe", "steam.exe"]) == []


# ---- ordering guarantee (8.2): marker only after a verified snapshot, before the game ----
def test_marker_is_written_after_snapshot_and_before_launch(env):
    _, live, game, vault = env
    order = []
    real_snapshot, real_marker = vault.snapshot, vault.write_marker
    vault.snapshot = lambda *a, **k: order.append("snapshot") or real_snapshot(*a, **k)
    vault.write_marker = lambda *a, **k: order.append("marker") or real_marker(*a, **k)
    SandboxSession(vault, live, hooks(game, run=lambda: order.append("game") or 0)).run()
    assert order == ["snapshot", "marker", "game"]


# ---- CLI surface ----
@pytest.fixture
def cli_env(env, monkeypatch):
    tmp, live, game, vault = env
    monkeypatch.setattr(cli, "_require_windows_x64", lambda: None)
    import eldendisk.memory_reader as mr
    monkeypatch.setattr(mr, "find_pid", lambda name: None)
    return tmp, live, vault


def test_status_list_verify_prune(cli_env, capsys):
    tmp, live, vault = cli_env
    v = ["--vault", str(vault.root)]
    assert cli.main(["sandbox", "status", *v]) == 0 and "live save trusted" in capsys.readouterr().out
    snaps = [vault.snapshot(live) for _ in range(3)]
    assert cli.main(["sandbox", "list", *v]) == 0 and capsys.readouterr().out.count("verified") == 3
    assert cli.main(["sandbox", "verify", snaps[0].dir.name, *v]) == 0
    (snaps[0].save_dir / "ER0000.sl2").write_bytes(b"bad")
    assert cli.main(["sandbox", "verify", snaps[0].dir.name, *v]) == 1
    vault.write_marker(snaps[1], live, exe_sha256=None)
    assert cli.main(["sandbox", "status", *v]) == 4 and "NOT trusted" in capsys.readouterr().out
    assert cli.main(["sandbox", "prune", "--keep", "1", *v]) == 1    # marker present: refused
    assert "unresolved session" in capsys.readouterr().err and len(vault.list_snapshots(verify=False)) == 3
    vault.clear_marker()
    assert cli.main(["sandbox", "prune", "--keep", "1", *v]) == 0 and len(vault.list_snapshots(verify=False)) == 1


def test_restore_command_and_named_snapshot_keeps_the_current_save(cli_env):
    tmp, live, vault = cli_env
    v, original = ["--vault", str(vault.root), "--save-dir", str(live)], tree(live)
    assert cli.main(["sandbox", "restore", *v]) == 0                      # nothing to restore
    snap = vault.snapshot(live)
    contaminate(live)
    modified = tree(live)
    assert cli.main(["sandbox", "restore", "--snapshot", snap.dir.name, *v]) == 0
    assert tree(live) == original
    pre = [s for s in vault.list_snapshots(verify=False) if s["name"].endswith("-pre-restore")]
    assert len(pre) == 1 and tree(pre[0]["path"] / "save") == modified    # what was there before is still recoverable


def test_sandbox_flags_parse_and_are_validated(monkeypatch):
    seen = {}
    monkeypatch.setattr(cli, "cmd_sandbox_edit", lambda a: seen.update(vars(a)) or 0)
    monkeypatch.setattr(cli, "cmd_sandbox", cli.cmd_sandbox)
    assert cli.main(["sandbox", "--set", "level=150", "--set", "vigor=40", "--refill", "hp,fp",
                     "-v"]) == 0
    assert seen["set"] == ["level=150", "vigor=40"] and seen["refill"] == "hp,fp" and seen["verbose"] is True
    assert seen["vault"] == cli.DEFAULT_VAULT
    with pytest.raises(SystemExit):
        cli.main(["sandbox", "--write-hz", "10"])           # removed in 1.6.1: edits are applied once


def test_bad_edit_policy_is_reported_and_nothing_starts(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "_require_windows_x64", lambda: None)
    assert cli.main(["sandbox", "--set", "bogus=1", "--vault", str(tmp_path / "v")]) == 1
    assert "bogus" in capsys.readouterr().err and not (tmp_path / "v").exists()


def test_document_reports_a_sandbox_session_but_stays_read_only():
    import argparse
    from eldendisk.disk import Sample
    from tests.test_disk import SCHEMA
    import jsonschema
    mon = cli.Monitor(argparse.Namespace(verbose=False, timer_interval=0.5), type("L", (), {"write": lambda s, d: True})())
    assert mon.mode == "telemetry" and mon.read_only is True and mon.sandbox is False
    docs = []
    mon.logger = type("L", (), {"write": lambda s, d: docs.append(d) or True})()
    mon.emit("WAITING_FOR_WORLD", Sample("WAITING_FOR_WORLD"))
    mon.mode = "sandbox"
    mon.sandbox = True
    mon.emit("IDLE", Sample("WAITING_FOR_WORLD"))
    assert [d["systems"]["session"] for d in docs] == [
        {"mode": "telemetry", "read_only": True, "sandbox": False},
        {"mode": "sandbox", "read_only": True, "sandbox": True},
    ]
    for d in docs:
        jsonschema.validate(d, SCHEMA)


# ---- integration: cmd_run inside a sandbox session (fake Win32 layer) ----
def _run_rig(tmp_path, monkeypatch, modules, alive_polls=2):
    import argparse
    import json
    import eldendisk.memory_reader as mr
    from eldendisk.memory_reader import Module
    from tests.test_disk import BASE, make_profile
    from tests.test_memory_writer import WMem
    from tests.test_disk import full_world

    game = tmp_path / "Game"; game.mkdir(exist_ok=True)
    exe = game / "eldenring.exe"; exe.write_bytes(b"EXE")
    mem = WMem(); mem.b = full_world().b
    state = {"alive": alive_polls, "closed": False}
    mem.alive = lambda: (state.__setitem__("alive", state["alive"] - 1) or state["alive"] >= 0)
    mem.close = lambda: state.__setitem__("closed", True)
    monkeypatch.setattr(cli, "_require_windows_x64", lambda: None)
    monkeypatch.setattr(cli.gl, "find_game_dir", lambda d: game)
    monkeypatch.setattr(cli.gl, "launch", lambda d: type("P", (), {"pid": 1234})())
    monkeypatch.setattr(cli.gl, "sha256_file", lambda p: "ab" * 32)
    monkeypatch.setattr(cli, "load_profile", lambda p, h: (make_profile(), None))
    monkeypatch.setattr(cli, "is_window_active", lambda pid: True)
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    monkeypatch.setattr(mr, "list_modules", lambda pid: [Module(n, BASE, str(exe)) for n in modules])
    monkeypatch.setattr(mr, "find_pid", lambda name: 1234 if state["alive"] >= 0 else None)
    monkeypatch.setattr(cli, "_wait_game_exit", lambda: True)
    monkeypatch.setattr("eldendisk.save_vault.load_registry_save_dir", lambda: None)
    monkeypatch.setattr("eldendisk.save_vault.save_registry_save_dir", lambda p: None)
    monkeypatch.setattr(mr, "ProcessMemory", lambda pid: mem)
    args = argparse.Namespace(attach=False, game_dir=None, out=str(tmp_path / "out"), offsets="x", effects=str(tmp_path / "none.json"),
                              hz=60.0, timer_interval=0.5, no_idle=True, verbose=False)
    return args, mem, state, json


def test_run_in_a_sandbox_session_is_labelled_but_never_writes(tmp_path, monkeypatch):
    import struct
    from tests.test_disk import GD
    args, mem, state, json = _run_rig(tmp_path, monkeypatch, ["eldenring.exe", "kernel32.dll"])
    assert cli.cmd_run(args, sandbox=True) == 0
    assert mem.log == [] and struct.unpack("<I", mem.read(GD + 0x68, 4))[0] == 386 and state["closed"]
    doc = json.loads((tmp_path / "out" / "disk-state.json").read_text())
    assert doc["systems"]["session"] == {"mode": "sandbox", "read_only": True, "sandbox": True}


def test_run_without_a_gate_never_writes_and_stays_read_only(tmp_path, monkeypatch):
    import struct
    from tests.test_disk import GD
    args, mem, state, json = _run_rig(tmp_path, monkeypatch, ["eldenring.exe"])
    args.attach = True
    assert cli.cmd_run(args) == 0
    assert mem.log == [] and struct.unpack("<I", mem.read(GD + 0x68, 4))[0] == 386
    assert json.loads((tmp_path / "out" / "disk-state.json").read_text())["systems"]["session"] == {"mode": "telemetry", "read_only": True, "sandbox": False}


def test_eac_loaded_stops_the_host_and_nothing_is_written(tmp_path, monkeypatch):
    args, mem, state, json = _run_rig(tmp_path, monkeypatch, ["eldenring.exe", "EasyAntiCheat_EOS.dll"])
    assert cli.cmd_run(args, sandbox=True) == cli.EXIT_EAC and mem.log == []

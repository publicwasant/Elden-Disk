"""`vault status | list | verify | restore | prune` (CLI surface)."""
from pathlib import Path

import pytest

import eldendisk.__main__ as cli
import eldendisk.commands.vault as vcmd
from eldendisk.vault import SaveVault, SessionState


@pytest.fixture
def env(tmp_path, monkeypatch):
    live = tmp_path / "AppData" / "EldenRing" / "76561198000000000"
    live.mkdir(parents=True)
    (live / "ER0000.sl2").write_bytes(b"SAVE-DATA" * 1000)
    (live / "ER0000.sl2.bak").write_bytes(b"BACKUP" * 500)
    vault = SaveVault(tmp_path / "vault", sleep=lambda s: None)
    monkeypatch.setattr(vcmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(vcmd, "find_pid", lambda name: None)
    return tmp_path, live, vault


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in Path(root).rglob("*") if p.is_file()}


def contaminate(live):
    (live / "ER0000.sl2").write_bytes(b"LEVEL 713 " * 2000)
    (live / "stray.dat").write_bytes(b"x")


def test_status_list_verify_prune(env, capsys):
    tmp, live, vault = env
    v = ["--vault", str(vault.root)]
    assert cli.main(["vault", "status", *v]) == 0 and "live save is trusted" in capsys.readouterr().out
    snaps = [vault.snapshot(live) for _ in range(3)]
    assert cli.main(["vault", "list", *v]) == 0 and capsys.readouterr().out.count("verified") == 3
    assert cli.main(["vault", "verify", snaps[0].dir.name, *v]) == 0
    (snaps[0].save_dir / "ER0000.sl2").write_bytes(b"bad")
    assert cli.main(["vault", "verify", snaps[0].dir.name, *v]) == 1
    vault.write_session(vault.new_record(snaps[1], live, exe_sha256=None))
    assert cli.main(["vault", "status", *v]) == 4 and "NOT trusted" in capsys.readouterr().out
    assert cli.main(["vault", "prune", "--keep", "1", *v]) == 1       # record present: refused
    assert "unresolved session" in capsys.readouterr().err and len(vault.list_snapshots(verify=False)) == 3
    vault.clear_session()
    assert cli.main(["vault", "prune", "--keep", "1", *v]) == 0 and len(vault.list_snapshots(verify=False)) == 1


def test_status_names_the_state_and_pids_of_a_running_session(env, capsys):
    tmp, live, vault = env
    vault.write_session(vault.new_record(vault.snapshot(live), live, exe_sha256="x", host_pid=7, host_started=1))
    vault.update_session(state=SessionState.RUNNING, game_pid=42, game_started=2)
    assert cli.main(["vault", "status", "--vault", str(vault.root)]) == 4
    out = capsys.readouterr().out
    assert "session RUNNING" in out and "host pid 7" in out and "game pid 42" in out


def test_restore_command_brings_back_the_save_and_archives_what_it_replaces(env, capsys):
    tmp, live, vault = env
    original = tree(live)
    v = ["--vault", str(vault.root), "--save-dir", str(live)]
    assert cli.main(["vault", "restore", *v]) == 0 and "nothing to restore" in capsys.readouterr().err
    vault.write_session(vault.new_record(vault.snapshot(live), live, exe_sha256=None))
    contaminate(live)
    assert cli.main(["vault", "restore", *v]) == 0
    assert tree(live) == original and vault.read_session() is None
    arch = vault.root / vault.list_snapshots()[0]["name"] / "contaminated"
    assert (arch / "stray.dat").exists()


def test_restore_without_archiving_and_while_the_game_runs(env, monkeypatch):
    tmp, live, vault = env
    v = ["--vault", str(vault.root), "--save-dir", str(live)]
    vault.write_session(vault.new_record(vault.snapshot(live), live, exe_sha256=None))
    contaminate(live)
    monkeypatch.setattr(vcmd, "find_pid", lambda name: 1234)
    assert cli.main(["vault", "restore", *v]) == 1 and (live / "stray.dat").exists()      # game open: refused
    monkeypatch.setattr(vcmd, "find_pid", lambda name: None)
    assert cli.main(["vault", "restore", "--no-archive-contaminated", *v]) == 0
    assert not (vault.root / vault.list_snapshots()[0]["name"] / "contaminated").exists()


def test_named_snapshot_restore_keeps_the_current_save(env):
    tmp, live, vault = env
    v, original = ["--vault", str(vault.root), "--save-dir", str(live)], tree(live)
    snap = vault.snapshot(live)
    contaminate(live)
    modified = tree(live)
    assert cli.main(["vault", "restore", "--snapshot", snap.dir.name, *v]) == 0
    assert tree(live) == original
    pre = [s for s in vault.list_snapshots(verify=False) if s["name"].endswith("-pre-restore")]
    assert len(pre) == 1 and tree(pre[0]["path"] / "save") == modified


def test_named_snapshot_restore_is_refused_while_a_session_is_owed(env, capsys):
    tmp, live, vault = env
    snap = vault.snapshot(live)
    vault.write_session(vault.new_record(snap, live, exe_sha256=None))
    contaminate(live)
    modified = tree(live)
    assert cli.main(["vault", "restore", "--snapshot", snap.dir.name, "--vault", str(vault.root), "--save-dir", str(live)]) == 1
    assert tree(live) == modified


@pytest.mark.parametrize("argv", [
    ["vault", "--vault", "VAULT", "status"], ["vault", "status", "--vault", "VAULT"],
    ["vault", "--vault", "VAULT", "restore"], ["vault", "restore", "--vault", "VAULT"],
])
def test_vault_option_is_kept_before_or_after_the_subcommand(monkeypatch, argv):
    seen = {}
    monkeypatch.setattr(cli, "cmd_vault", lambda a: seen.update(vault=a.vault, cmd=a.vault_cmd) or 0)
    assert cli.main(["X" if a == "VAULT" else a for a in argv]) == 0 and seen["vault"] == "X"


def test_vault_defaults_when_not_given(monkeypatch):
    seen = {}
    monkeypatch.setattr(cli, "cmd_vault", lambda a: seen.update(vault=a.vault) or 0)
    assert cli.main(["vault", "restore"]) == 0 and seen["vault"] is None


def test_the_restore_hint_names_the_vault(tmp_path):
    from eldendisk.vault import SaveVault
    assert f'--vault "{tmp_path / "v"}"' in SaveVault(tmp_path / "v").restore_hint()


# ---------- vault keep ----------
def open_session(vault, live, host_pid=7, host_started=1):
    vault.write_session(vault.new_record(vault.snapshot(live), live, exe_sha256="x", host_pid=host_pid, host_started=host_started))


def test_keep_without_a_session_does_nothing(env, capsys):
    tmp, live, vault = env
    assert cli.main(["vault", "keep", "--yes", "--vault", str(vault.root)]) == 0
    assert "nothing to keep" in capsys.readouterr().err


def test_keep_explains_and_changes_nothing_without_yes(env, monkeypatch, capsys):
    tmp, live, vault = env
    monkeypatch.setattr(vcmd, "process_started", lambda pid: None)   # host dead
    open_session(vault, live)
    contaminate(live)
    before = tree(live)
    assert cli.main(["vault", "keep", "--vault", str(vault.root)]) == 1
    assert "--yes" in capsys.readouterr().out and vault.read_session() is not None and tree(live) == before


def test_keep_adopts_the_current_save_and_keeps_the_old_snapshot(env, monkeypatch):
    tmp, live, vault = env
    monkeypatch.setattr(vcmd, "process_started", lambda pid: None)
    open_session(vault, live)
    old = vault.read_session().snapshot_dir
    contaminate(live)
    adopted = tree(live)
    assert cli.main(["vault", "keep", "--yes", "--vault", str(vault.root)]) == 0
    assert tree(live) == adopted                                  # the save is untouched
    assert vault.read_session() is None and Path(old).is_dir()    # no record any more, old snapshot kept
    names = [s["name"] for s in vault.list_snapshots(verify=False)]
    kept = [n for n in names if n.endswith("-kept")]
    assert len(kept) == 1 and vault.verify_snapshot(vault.snapshot_path(kept[0])) == []
    assert tree(vault.snapshot_path(kept[0]) / "save")["ER0000.sl2"] == adopted["ER0000.sl2"]
    assert cli.main(["vault", "status", "--vault", str(vault.root)]) == 0   # trusted again


@pytest.mark.parametrize("why", ["game", "host", "restoring"])
def test_keep_refuses_while_it_would_be_unsafe(env, monkeypatch, capsys, why):
    tmp, live, vault = env
    monkeypatch.setattr(vcmd, "process_started", (lambda pid: 1) if why == "host" else (lambda pid: None))
    if why == "game":
        monkeypatch.setattr(vcmd, "find_pid", lambda name: 123)
    open_session(vault, live)
    if why == "restoring":
        vault.update_session(state=SessionState.RESTORING)
    assert cli.main(["vault", "keep", "--yes", "--vault", str(vault.root)]) == 1
    assert vault.read_session() is not None


def test_keep_failure_leaves_the_record(env, monkeypatch):
    tmp, live, vault = env
    monkeypatch.setattr(vcmd, "process_started", lambda pid: None)
    open_session(vault, live)
    monkeypatch.setattr(SaveVault, "snapshot", lambda self, *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    assert cli.main(["vault", "keep", "--yes", "--vault", str(vault.root)]) == 1
    assert vault.read_session() is not None

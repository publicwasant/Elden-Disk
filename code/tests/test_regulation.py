"""The regulation.bin swap (spec 1.6.4, since 1.7.0 the caller names the file): it replaces the game's file for one
session and the game's own file comes back with the save. Fault injection at every boundary, like the save itself."""
import json
from pathlib import Path

import pytest

import eldendisk.__main__ as cli
import eldendisk.commands.vault as vcmd
from eldendisk.host.host import State
from eldendisk.vault import (EXIT_RESTORE_PENDING, GameFolderGuard, SessionLog, SessionState, VaultError, listing,
                             recover, restore_from_record)
from eldendisk.vault import session as sess
from eldendisk.vault.recover import keep_from_record
from tests.test_host import GAME_PID, Killed, World, contaminate, env, tree   # noqa: F401  (env is a fixture)
from tests.test_host import make as _make

ORIGINAL = b"GAME-REGULATION-" * 4000
WORLD = b"MY-OTHER-WORLD-" * 5000
TMP = "regulation.bin.eldendisk-tmp"


@pytest.fixture
def renv(env):
    """The host fixture plus the game's own regulation.bin and the user's file in the vault."""
    _, live, game, vault = env
    (game / "regulation.bin").write_bytes(ORIGINAL)
    put_world(vault, WORLD)
    return env


def world_path(vault):
    """Where the tests keep 'the user's file': anywhere outside the vault (the caller of the host names it)."""
    return vault.root.parent / "mine" / "regulation.bin"


def put_world(vault, data):
    world_path(vault).parent.mkdir(parents=True, exist_ok=True)
    world_path(vault).write_bytes(data)


def make(env, world=None, **kw):
    """The host with the user's file named, when the test has put one down."""
    if "regulation_world" not in kw and world_path(env[3]).is_file():
        kw["regulation_world"] = world_path(env[3])
    return _make(env, world, **kw)


def game_file(env):
    return env[2] / "regulation.bin"


# ---- the normal flow ----
def test_the_game_runs_with_the_users_file_and_gets_its_own_back(renv):
    _, live, game, vault = renv
    before, seen = listing(game), {}

    def on_tick(w, n):
        if n == 1:
            seen["during"] = game_file(renv).read_bytes()
            seen["record"] = vault.read_session()
            contaminate(live)

    s, _ = make(renv, World(on_tick=on_tick), guard=True)
    assert s.run() == 0
    assert seen["during"] == WORLD                                              # the game saw the other world
    reg = seen["record"].regulation
    assert reg["original_sha256"] != reg["world_sha256"] and reg["game_file"] == str(game_file(renv))
    assert game_file(renv).read_bytes() == ORIGINAL and vault.read_session() is None
    assert listing(game) == before and not (game / TMP).exists()                # nothing else changed in the game folder
    snap = vault.root / vault.list_snapshots()[0]["name"]
    assert (snap / "bin" / "regulation.bin").read_bytes() == ORIGINAL           # the vault keeps the original
    assert world_path(vault).read_bytes() == WORLD  # and never touches the user's file
    assert json.loads((snap / "manifest.json").read_text())["regulation"]["original_sha256"] == reg["original_sha256"]
    assert vault.verify_snapshot(snap) == []
    log = (snap / "session.log").read_text()
    assert "your file replaces the game's" in log and "regulation.bin restored, byte-identical" in log


def test_the_games_own_file_as_the_users_file_is_a_clean_dry_run(renv):
    """The first real test: put an unmodified copy of the game's regulation.bin in the vault and run."""
    _, live, game, vault = renv
    put_world(vault, ORIGINAL)
    seen = {}

    def on_tick(w, n):
        if n == 1:
            seen["during"] = game_file(renv).read_bytes()
            seen["record"] = vault.read_session()

    s, _ = make(renv, World(on_tick=on_tick), guard=True)
    assert s.run() == 0
    reg = seen["record"].regulation
    assert reg["original_sha256"] == reg["world_sha256"] and seen["during"] == ORIGINAL
    assert game_file(renv).read_bytes() == ORIGINAL and vault.read_session() is None and not (game / TMP).exists()
    snap = vault.root / vault.list_snapshots()[0]["name"]
    assert (snap / "bin" / "regulation.bin").read_bytes() == ORIGINAL and vault.verify_snapshot(snap) == []


def test_without_a_file_in_the_vault_nothing_about_regulation_happens(env):
    _, live, game, vault = env
    (game / "regulation.bin").write_bytes(ORIGINAL)
    seen = {}
    s, _ = make(env, World(on_tick=lambda w, n: seen.update(rec=vault.read_session(), data=game_file(env).read_bytes())))
    assert s.run() == 0
    assert seen["rec"].regulation is None and seen["data"] == ORIGINAL
    snap = vault.root / vault.list_snapshots()[0]["name"]
    assert not (snap / "bin").exists() and "regulation" not in json.loads((snap / "manifest.json").read_text())


def test_a_game_folder_without_regulation_bin_and_no_user_file_is_fine(env):
    assert make(env)[0].run() == 0          # the fixtures of every older test look like this


def test_with_the_vault_off_the_users_file_is_never_used(renv):
    seen = {}
    s, world = make(renv, World(on_tick=lambda w, n: seen.update(data=game_file(renv).read_bytes())), protect=False)
    assert s.run() == 0 and seen["data"] == ORIGINAL and game_file(renv).read_bytes() == ORIGINAL


def test_backup_then_record_then_swap_then_launch(renv):
    _, live, game, vault = renv
    order = []
    for name in ("backup_regulation", "install_regulation"):
        real = getattr(vault, name)
        setattr(vault, name, lambda *a, _r=real, _n=name, **k: order.append(_n) or _r(*a, **k))
    real_write = vault.write_session
    vault.write_session = lambda r: order.append(f"record:{r.state.value}") or real_write(r)
    world = World()
    world.launch = lambda orig=world.launch: order.append("launch") or orig()
    make(renv, world)[0].run()
    assert order == ["backup_regulation", "record:READY", "install_regulation", "launch"]


def test_history_has_no_extra_states(renv):
    s, _ = make(renv)
    assert s.run() == 0
    assert s.history == [State.IDLE, State.PREFLIGHT, State.SNAPSHOTTING, State.READY, State.RUNNING,
                         State.RESTORING, State.IDLE]


# ---- preflight: refusals change nothing ----
@pytest.mark.parametrize("what", ["empty file", "no game file"])
def test_preflight_refuses_a_swap_that_cannot_work(renv, what):
    _, live, game, vault = renv
    if what == "empty file":
        put_world(vault, b"")
    else:
        game_file(renv).unlink()
    before = tree(live)
    s, world = make(renv)
    assert s.run() == 1 and world.launched == 0 and tree(live) == before and vault.read_session() is None
    assert not vault.list_snapshots()


# ---- failures before the swap: the game folder is untouched ----
def test_a_failed_backup_discards_the_snapshot_and_starts_nothing(renv, monkeypatch):
    _, live, game, vault = renv
    monkeypatch.setattr(vault, "backup_regulation", lambda *a, **k: (_ for _ in ()).throw(VaultError("disk full")))
    s, world = make(renv)
    assert s.run() == 1 and world.launched == 0
    assert vault.read_session() is None and not vault.list_snapshots()
    assert game_file(renv).read_bytes() == ORIGINAL


def test_ctrl_c_during_the_backup_changes_nothing(renv, monkeypatch):
    _, live, game, vault = renv
    monkeypatch.setattr(vault, "backup_regulation", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    s, world = make(renv)
    assert s.run() == 130 and world.launched == 0 and vault.read_session() is None and not vault.list_snapshots()


def test_the_users_file_changing_during_preparation_swaps_nothing(renv, monkeypatch):
    _, live, game, vault = renv
    real = vault.backup_regulation

    def backup(*a, **k):
        info = real(*a, **k)
        put_world(vault, b"EDITED AFTER THE HASH")
        return info

    monkeypatch.setattr(vault, "backup_regulation", backup)
    s, world = make(renv)
    assert s.run() == 1 and world.launched == 0
    assert game_file(renv).read_bytes() == ORIGINAL and vault.read_session() is None


# ---- failures after the record exists: always the restore path ----
def test_a_failed_swap_restores_and_starts_nothing(renv, monkeypatch):
    _, live, game, vault = renv
    before = tree(live)
    monkeypatch.setattr(vault, "install_regulation", lambda info: (_ for _ in ()).throw(VaultError("locked")))
    s, world = make(renv)
    assert s.run() == 1 and world.launched == 0
    assert tree(live) == before and game_file(renv).read_bytes() == ORIGINAL and vault.read_session() is None


def test_ctrl_c_during_the_swap_restores(renv, monkeypatch):
    _, live, game, vault = renv

    def install(info):
        game_file(renv).write_bytes(b"HALF")                  # the interrupt came mid-copy
        raise KeyboardInterrupt

    monkeypatch.setattr(vault, "install_regulation", install)
    s, world = make(renv)
    assert s.run() == 130 and world.launched == 0
    assert game_file(renv).read_bytes() == ORIGINAL and vault.read_session() is None


def test_the_tool_dying_before_the_swap_leaves_a_record_that_restores_to_a_noop(renv, monkeypatch):
    _, live, game, vault = renv
    monkeypatch.setattr(vault, "install_regulation", lambda info: (_ for _ in ()).throw(Killed()))
    with pytest.raises(Killed):
        make(renv)[0].run()
    record = vault.read_session()
    assert record.regulation and game_file(renv).read_bytes() == ORIGINAL
    assert vault.restore_regulation(record) is False                            # already the original
    assert recover(vault, game_running=lambda: False, log=SessionLog()) == 0 and vault.read_session() is None


def test_the_tool_dying_while_the_game_runs_is_repaired_by_vault_restore(renv):
    _, live, game, vault = renv
    before = tree(live)

    def on_tick(w, n):
        contaminate(live)
        raise Killed

    with pytest.raises(Killed):
        make(renv, World(on_tick=on_tick))[0].run()
    assert game_file(renv).read_bytes() == WORLD and vault.read_session().state == SessionState.RUNNING
    (game / TMP).write_bytes(b"left by an interrupted copy")
    assert recover(vault, game_running=lambda: False, log=SessionLog()) == 0
    assert tree(live) == before and game_file(renv).read_bytes() == ORIGINAL
    assert not (game / TMP).exists() and vault.read_session() is None


# ---- the restore of the file fails or cannot be trusted ----
def test_a_failed_regulation_restore_stays_owed_and_a_later_restore_finishes_it(renv, monkeypatch):
    _, live, game, vault = renv
    before = tree(live)
    real = vault.restore_regulation
    monkeypatch.setattr(vault, "restore_regulation", lambda rec: (_ for _ in ()).throw(VaultError("locked")))
    s, _ = make(renv, World(on_tick=lambda w, n: contaminate(live) if n == 1 else None))
    assert s.run() == EXIT_RESTORE_PENDING
    record = vault.read_session()
    assert record.state == SessionState.RESTORE_PENDING and game_file(renv).read_bytes() == WORLD
    assert tree(live) == before                                                  # the save was restored anyway
    assert make(renv)[0].run() == EXIT_RESTORE_PENDING                           # and a new run is refused
    monkeypatch.setattr(vault, "restore_regulation", real)
    assert recover(vault, game_running=lambda: False, log=SessionLog()) == 0
    assert game_file(renv).read_bytes() == ORIGINAL and vault.read_session() is None


def test_a_failed_save_restore_still_puts_the_games_regulation_back(renv, monkeypatch):
    """The swapped file must never wait in the game folder for a save that could not be restored."""
    _, live, game, vault = renv
    real = vault.restore
    monkeypatch.setattr(vault, "restore", lambda snap, dst: (_ for _ in ()).throw(VaultError("save is locked")))
    s, _ = make(renv, World(on_tick=lambda w, n: contaminate(live) if n == 1 else None))
    assert s.run() == EXIT_RESTORE_PENDING
    assert vault.read_session().state == SessionState.RESTORE_PENDING            # the save is still owed
    assert game_file(renv).read_bytes() == ORIGINAL and not (game / TMP).exists()  # but the game has its own file again
    assert make(renv)[0].run() == EXIT_RESTORE_PENDING                           # and a new run is refused
    monkeypatch.setattr(vault, "restore", real)
    assert recover(vault, game_running=lambda: False, log=SessionLog()) == 0
    assert vault.read_session() is None and game_file(renv).read_bytes() == ORIGINAL


def test_a_failed_save_restore_and_a_failed_regulation_restore_are_both_reported(renv, monkeypatch):
    _, live, game, vault = renv
    monkeypatch.setattr(vault, "restore", lambda snap, dst: (_ for _ in ()).throw(VaultError("save is locked")))
    monkeypatch.setattr(vault, "restore_regulation", lambda rec: (_ for _ in ()).throw(VaultError("bin is locked")))
    s, _ = make(renv, World(on_tick=lambda w, n: contaminate(live) if n == 1 else None))
    assert s.run() == EXIT_RESTORE_PENDING
    assert vault.read_session().state == SessionState.RESTORE_PENDING and game_file(renv).read_bytes() == WORLD
    log = (Path(vault.read_session().snapshot_dir) / "session.log").read_text()
    assert "save is locked" in log and "bin is locked" in log


def test_a_damaged_backup_is_never_copied_back_and_never_blocks_the_save(renv):
    _, live, game, vault = renv
    before = tree(live)

    def on_tick(w, n):
        contaminate(live)
        raise Killed

    with pytest.raises(Killed):
        make(renv, World(on_tick=on_tick))[0].run()
    record = vault.read_session()
    snap = Path(record.snapshot_dir)
    (snap / "bin" / "regulation.bin").write_bytes(b"damaged")
    assert any("hash mismatch: bin/regulation.bin" in p for p in vault.verify_snapshot(snap))
    assert recover(vault, game_running=lambda: False, log=SessionLog()) == EXIT_RESTORE_PENDING
    assert tree(live) == before                                                  # the save came back
    assert game_file(renv).read_bytes() == WORLD                                 # the damaged copy was not used
    assert vault.read_session().state == SessionState.RESTORE_PENDING
    game_file(renv).write_bytes(ORIGINAL)                                        # the user put the original back by hand
    assert recover(vault, game_running=lambda: False, log=SessionLog()) == 0     # the record's hash is enough
    assert vault.read_session() is None and game_file(renv).read_bytes() == ORIGINAL


def test_save_only_restore_does_not_depend_on_the_bin_folder(renv):
    _, live, game, vault = renv
    snap = vault.snapshot(live)
    info = vault.backup_regulation(snap, game, world_path(vault))
    (snap.dir / "bin" / "regulation.bin").write_bytes(b"damaged")
    contaminate(live)
    vault.restore(snap.dir, live)                                                # `vault restore --snapshot` style
    assert vault.verify_live(live, vault.load_manifest(snap.dir)["files"]) == [] and info


# ---- vault keep ----
def test_keep_puts_the_games_file_back_first(renv):
    _, live, game, vault = renv

    def on_tick(w, n):
        contaminate(live)
        raise Killed

    with pytest.raises(Killed):
        make(renv, World(on_tick=on_tick))[0].run()
    assert keep_from_record(vault, vault.read_session(), log=SessionLog()) == 0
    assert game_file(renv).read_bytes() == ORIGINAL and vault.read_session() is None
    assert (live / "stray.dat").exists()                                         # the modified save was kept
    assert any(s["name"].endswith("-kept") for s in vault.list_snapshots(verify=False))


def test_keep_changes_nothing_when_the_games_file_cannot_come_back(renv):
    _, live, game, vault = renv

    def on_tick(w, n):
        raise Killed

    with pytest.raises(Killed):
        make(renv, World(on_tick=on_tick))[0].run()
    record = vault.read_session()
    (Path(record.snapshot_dir) / "bin" / "regulation.bin").write_bytes(b"damaged")
    assert keep_from_record(vault, record, log=SessionLog()) == 1
    assert vault.read_session() is not None and game_file(renv).read_bytes() == WORLD
    assert not any(s["name"].endswith("-kept") for s in vault.list_snapshots(verify=False))


# ---- snapshots on disk ----
def test_list_status_and_prune_know_about_bin(renv):
    _, live, game, vault = renv
    assert make(renv)[0].run() == 0
    row = vault.list_snapshots()[0]
    assert row["verified"] is True and row["size"] > len(ORIGINAL)               # save + bin
    info = vault.world_info(world_path(vault))
    assert info["size"] == len(WORLD) and len(info["sha256"]) == 64 and vault.world_info(None) is None
    assert vault.prune(0 + 1) == [] and make(renv)[0].run() == 0
    assert len(vault.prune(1)) == 1
    assert world_path(vault).is_file()                                           # prune never touches the user's file
    assert [s["name"] for s in vault.list_snapshots(verify=False)] == [vault.status()["last"]]


def test_the_regulation_folder_is_not_a_snapshot(renv):
    _, live, game, vault = renv
    assert vault.list_snapshots() == [] and vault.status()["snapshots"] == 0


def test_status_knows_the_legacy_file_of_1_6_4_but_never_reads_it(env):
    vault = env[3]
    assert vault.status()["legacy_world"] is None
    (vault.root / "regulation").mkdir(parents=True)
    (vault.root / "regulation" / "regulation.bin").write_bytes(b"old")
    assert vault.status()["legacy_world"] == vault.root / "regulation" / "regulation.bin"
    assert vault.regulation_problems(env[2], None) == []                         # no file named -> nothing to swap


def test_vault_status_reports_the_legacy_file_as_not_read(env, monkeypatch, capsys):
    vault = env[3]
    monkeypatch.setattr(vcmd, "require_windows_x64", lambda: None)
    assert cli.main(["vault", "status", "--vault", str(vault.root)]) == 0
    assert "regulation" not in capsys.readouterr().out
    (vault.root / "regulation").mkdir(parents=True)
    (vault.root / "regulation" / "regulation.bin").write_bytes(b"old")
    assert cli.main(["vault", "status", "--vault", str(vault.root)]) == 0
    assert "no longer read" in " ".join(capsys.readouterr().out.split())


# ---- the session record ----
def test_the_record_roundtrips_and_an_older_record_reads_as_no_swap(renv, tmp_path):
    _, live, game, vault = renv
    snap = vault.snapshot(live)
    info = vault.backup_regulation(snap, game, world_path(vault))
    vault.write_session(vault.new_record(snap, live, exe_sha256="abc", regulation=info))
    assert vault.read_session().regulation == info
    raw = json.loads((vault.root / sess.SESSION_NAME).read_text())
    del raw["regulation"]                                                        # a 1.6.3 record has no such key
    (vault.root / sess.SESSION_NAME).write_text(json.dumps(raw))
    assert vault.read_session().regulation is None and vault.restore_regulation(vault.read_session()) is False


# ---- command surface ----
def test_vault_status_names_a_pending_swap(renv, monkeypatch, capsys):
    _, live, game, vault = renv
    monkeypatch.setattr(vcmd, "require_windows_x64", lambda: None)
    v = ["--vault", str(vault.root)]
    assert cli.main(["vault", "status", *v]) == 0
    assert "restore puts the original back" not in capsys.readouterr().out

    def on_tick(w, n):
        raise Killed

    with pytest.raises(Killed):
        make(renv, World(on_tick=on_tick))[0].run()
    assert cli.main(["vault", "status", *v]) == 4
    assert "restore puts the original back" in capsys.readouterr().out


def test_vault_keep_without_yes_mentions_the_file(renv, monkeypatch, capsys):
    _, live, game, vault = renv
    monkeypatch.setattr(vcmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(vcmd, "find_pid", lambda name: None)
    monkeypatch.setattr(vcmd, "host_alive", lambda *a: False)

    def on_tick(w, n):
        raise Killed

    with pytest.raises(Killed):
        make(renv, World(on_tick=on_tick))[0].run()
    assert cli.main(["vault", "keep", "--vault", str(vault.root)]) == 1
    assert "regulation.bin is put back first" in capsys.readouterr().out

"""Host session lifecycle (spec 1.6.2 section 4): invariants I1-I3, interrupts, and fault injection at every boundary."""
from pathlib import Path

import pytest

from eldendisk.host.host import Hooks, Session, State
from eldendisk.vault import (EXIT_RESTORE_PENDING, GameFolderGuard, SaveVault, SessionLog, SessionState, VaultError,
                             listing, recover)

HOST_PID, HOST_STARTED, GAME_PID, GAME_STARTED = 100, 555, 4242, 777


class Killed(BaseException):
    """The tool process is gone (power loss, kill): nothing after this point in the tool runs."""


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


class World:
    """A fake game: launch() starts it, every sleep() is one poll, it exits after `lifetime` polls."""

    def __init__(self, lifetime=3, on_tick=None, starts=True):
        self.lifetime, self.on_tick, self.starts = lifetime, on_tick, starts
        self.pid, self.ticks, self.launched, self.clock = None, 0, 0, 0.0

    def launch(self):
        self.launched += 1
        if self.starts:
            self.pid, self.ticks = GAME_PID, 0

    def find(self):
        return self.pid

    def started(self, pid):
        return {HOST_PID: HOST_STARTED, GAME_PID: GAME_STARTED}.get(pid)

    def sleep(self, s):
        self.clock += s
        if self.pid is not None:
            self.ticks += 1
            if self.on_tick:
                self.on_tick(self, self.ticks)
            if self.ticks >= self.lifetime:
                self.pid = None

    def now(self):
        return self.clock


def make(env, world=None, *, running=False, ac=False, extra=None, guard=False, started=None, regulation_world=None, **kw):
    _, live, game, vault = env
    world = world or World()
    h = Hooks(find_game_pid=(lambda: GAME_PID) if running else world.find,
              process_started=started or world.started, anticheat_running=lambda: ac, launch=world.launch,
              exe_sha256="abc", game_dir=game, game_guard=GameFolderGuard(game) if guard else None, regulation_world=regulation_world,
              extra_preflight=(lambda: extra) if extra else (lambda: []), sleep=world.sleep, clock=world.now,
              launch_timeout=10.0, exit_settle=1.0, install_close_handler=lambda cb: (lambda: None))
    return Session(vault, live, h, pid=HOST_PID, **kw), world


# ---- the normal flow ----
def test_full_flow_contaminates_then_restores_byte_for_byte(env):
    _, live, game, vault = env
    before, seen = tree(live), {}

    def on_tick(w, n):
        if n == 1:
            seen["record"] = vault.read_session()
            seen["snapshot_ok"] = vault.verify_snapshot(Path(seen["record"].snapshot_dir)) == []
            contaminate(live)           # "memory edits got autosaved"

    s, _ = make(env, World(on_tick=on_tick))
    assert s.run() == 0
    r = seen["record"]
    assert seen["snapshot_ok"] and r.state == SessionState.RUNNING and r.snapshot_verified
    assert (r.host_pid, r.host_started, r.game_pid, r.game_started) == (HOST_PID, HOST_STARTED, GAME_PID, GAME_STARTED)
    assert r.live_save_dir == str(live) and r.exe_sha256 == "abc"
    assert tree(live) == before and vault.read_session() is None          # G1
    assert s.history == [State.IDLE, State.PREFLIGHT, State.SNAPSHOTTING, State.READY, State.RUNNING,
                         State.RESTORING, State.IDLE]
    snap_dir = vault.root / vault.list_snapshots()[0]["name"]
    assert "byte-identical" in (snap_dir / "session.log").read_text()


def test_record_is_written_after_the_snapshot_and_before_the_launch(env):
    _, live, game, vault = env
    order = []
    real_snapshot, real_write = vault.snapshot, vault.write_session
    vault.snapshot = lambda *a, **k: order.append("snapshot") or real_snapshot(*a, **k)
    vault.write_session = lambda r: order.append(f"record:{r.state.value}") or real_write(r)
    world = World()
    world.launch = lambda orig=world.launch: order.append("launch") or orig()
    make(env, world)[0].run()
    assert order == ["snapshot", "record:READY", "launch"]


def test_the_game_is_launched_exactly_once(env):
    s, world = make(env, World())
    assert s.run() == 0 and world.launched == 1


# ---- I3: nothing is overwritten without being archived ----
def test_a_modified_save_is_archived_by_default(env):
    _, live, game, vault = env
    s, _ = make(env, World(on_tick=lambda w, n: contaminate(live) if n == 1 else None))
    assert s.run() == 0
    snap = vault.root / vault.list_snapshots()[0]["name"]
    assert (snap / "contaminated" / "ER0000.sl2").read_bytes().startswith(b"LEVEL 713")
    assert (snap / "contaminated" / "stray.dat").exists()


def test_an_unmodified_save_is_not_archived(env):
    _, live, game, vault = env
    assert make(env)[0].run() == 0
    assert not (vault.root / vault.list_snapshots()[0]["name"] / "contaminated").exists()


def test_archiving_can_be_switched_off(env):
    _, live, game, vault = env
    s, _ = make(env, World(on_tick=lambda w, n: contaminate(live) if n == 1 else None), archive_contaminated=False)
    assert s.run() == 0
    assert not (vault.root / vault.list_snapshots()[0]["name"] / "contaminated").exists()


# ---- H1: preflight refusals change nothing ----
@pytest.mark.parametrize("kw", [{"running": True}, {"ac": True}, {"extra": ["no profile"]},
                                {"started": lambda pid: None}])
def test_preflight_refusal_changes_nothing(env, kw):
    _, live, game, vault = env
    before = tree(live)
    s, world = make(env, **kw)
    assert s.run() == 1
    assert world.launched == 0 and tree(live) == before and vault.read_session() is None
    assert not vault.root.exists() or not any(vault.root.iterdir())
    assert s.history == [State.IDLE, State.PREFLIGHT, State.IDLE]


def test_an_unresolved_record_blocks_a_new_run_until_vault_restore(env):
    _, live, game, vault = env
    before = tree(live)
    vault.write_session(vault.new_record(vault.snapshot(live), live, exe_sha256=None))   # as if the tool was killed
    contaminate(live)
    s, world = make(env)
    assert s.run() == EXIT_RESTORE_PENDING and world.launched == 0
    assert recover(vault, game_running=lambda: False, log=SessionLog()) == 0
    assert tree(live) == before and vault.read_session() is None
    assert make(env)[0].run() == 0          # a new session is allowed now


def test_an_unreadable_record_blocks_a_new_run(env):
    _, live, game, vault = env
    vault.root.mkdir(parents=True)
    (vault.root / "session.json").write_text("{ nope")
    s, world = make(env)
    assert s.run() == EXIT_RESTORE_PENDING and world.launched == 0


# ---- H4/H5: the game never appears ----
def test_a_game_that_never_starts_ends_the_session_and_restores(env):
    _, live, game, vault = env
    before = tree(live)
    s, world = make(env, World(starts=False))
    assert s.run() == 1 and tree(live) == before and vault.read_session() is None
    assert world.clock >= 10.0


# ---- interrupts ----
def test_one_ctrl_c_is_absorbed_and_the_game_keeps_running(env):
    _, live, game, vault = env
    before = tree(live)

    def on_tick(w, n):
        if n == 1:
            contaminate(live)
            raise KeyboardInterrupt

    s, world = make(env, World(lifetime=3, on_tick=on_tick))
    assert s.run() == 0 and world.ticks == 3 and tree(live) == before and vault.read_session() is None


def test_ctrl_c_inside_launch_does_not_launch_twice(env):
    world = World()
    real = world.launch

    def launch():
        real()
        raise KeyboardInterrupt

    world.launch = launch
    s, _ = make(env, world)
    assert s.run() == 0 and world.launched == 1


def test_second_ctrl_c_leaves_the_restore_owed_and_recoverable(env):
    _, live, game, vault = env
    before = tree(live)

    def on_tick(w, n):
        if n == 1:
            contaminate(live)
        if n in (1, 2):
            raise KeyboardInterrupt

    s, world = make(env, World(lifetime=5, on_tick=on_tick))
    assert s.run() == EXIT_RESTORE_PENDING and s.state is State.RESTORE_PENDING
    r = vault.read_session()
    assert r.state == SessionState.RESTORE_PENDING and vault.verify_snapshot(Path(r.snapshot_dir)) == []
    assert recover(vault, game_running=lambda: True, log=SessionLog()) == 1      # the game is still open: refused
    assert tree(live) != before
    assert recover(vault, game_running=lambda: False, log=SessionLog()) == 0
    assert tree(live) == before and vault.read_session() is None


def test_ctrl_c_during_the_snapshot_changes_nothing(env, monkeypatch):
    _, live, game, vault = env
    before = tree(live)
    monkeypatch.setattr(vault, "snapshot", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    s, world = make(env)
    assert s.run() == 130 and world.launched == 0 and tree(live) == before and vault.read_session() is None


def test_ctrl_c_during_the_restore_is_pending_not_lost(env, monkeypatch):
    _, live, game, vault = env
    before = tree(live)
    real = vault.restore
    monkeypatch.setattr(vault, "restore", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    s, _ = make(env, World(on_tick=lambda w, n: contaminate(live) if n == 1 else None))
    assert s.run() == EXIT_RESTORE_PENDING
    assert vault.read_session().state == SessionState.RESTORE_PENDING
    monkeypatch.setattr(vault, "restore", real)
    assert recover(vault, game_running=lambda: False, log=SessionLog()) == 0 and tree(live) == before


def test_an_error_while_waiting_still_restores(env):
    _, live, game, vault = env
    before = tree(live)

    def on_tick(w, n):
        contaminate(live)
        raise RuntimeError("tool bug")

    s, _ = make(env, World(on_tick=on_tick))
    assert s.run() == 1 and tree(live) == before and vault.read_session() is None


def test_console_close_marks_restore_pending_and_authorises_nothing(env):
    from eldendisk.vault import authorise
    _, live, game, vault = env
    box = {}

    def on_tick(w, n):
        if n == 1:
            contaminate(live)
            box["session"].hooks.install_close_handler  # (the real handler thread calls the line below)
            box["session"]._on_console_close()
            box["record"] = vault.read_session()
            raise Killed

    s, world = make(env, World(on_tick=on_tick))
    box["session"] = s
    with pytest.raises(Killed):
        s.run()
    r = vault.read_session()
    assert r.state == SessionState.RESTORE_PENDING
    problems = authorise(r, game_pid=GAME_PID, game_started=GAME_STARTED, exe_sha256="abc", started_of=world.started)
    assert any("RESTORE_PENDING" in p for p in problems)


# ---- failures keep the record and the snapshot ----
def test_restore_failure_keeps_the_record_and_the_snapshot(env, monkeypatch):
    _, live, game, vault = env
    monkeypatch.setattr(vault, "restore", lambda *a, **k: (_ for _ in ()).throw(VaultError("locked")))
    s, _ = make(env, World(on_tick=lambda w, n: contaminate(live) if n == 1 else None))
    assert s.run() == EXIT_RESTORE_PENDING
    r = vault.read_session()
    assert r.state == SessionState.RESTORE_PENDING and vault.verify_snapshot(Path(r.snapshot_dir)) == []


def test_failed_verification_keeps_the_record(env, monkeypatch):
    _, live, game, vault = env
    monkeypatch.setattr(vault, "verify_live", lambda *a, **k: ["hash mismatch: ER0000.sl2"])
    s, _ = make(env)
    assert s.run() == EXIT_RESTORE_PENDING and vault.read_session() is not None
    assert s.history[-1] is State.RESTORE_PENDING


def test_restore_twice_second_is_a_noop(env):
    _, live, game, vault = env
    vault.write_session(vault.new_record(vault.snapshot(live), live, exe_sha256=None))
    contaminate(live)
    log = SessionLog()
    assert recover(vault, game_running=lambda: False, log=log) == 0
    after = tree(live)
    assert recover(vault, game_running=lambda: False, log=log) == 0 and tree(live) == after


def test_recover_refuses_while_the_game_runs_and_without_a_snapshot_it_does_not_touch_live(env):
    _, live, game, vault = env
    snap = vault.snapshot(live)
    vault.write_session(vault.new_record(snap, live, exe_sha256=None))
    contaminate(live)
    modified = tree(live)
    assert recover(vault, game_running=lambda: True, log=SessionLog()) == 1 and tree(live) == modified
    (snap.save_dir / "ER0000.sl2").write_bytes(b"damaged")          # the snapshot is bad: never used
    assert recover(vault, game_running=lambda: False, log=SessionLog()) == EXIT_RESTORE_PENDING
    assert tree(live) == modified and vault.read_session().state == SessionState.RESTORE_PENDING


# ---- game folder hygiene ----
def test_files_created_in_the_game_folder_are_removed_and_recorded(env):
    _, live, game, vault = env
    before, seen = listing(game), {}
    world = World()
    s, _ = make(env, world, guard=True)

    def on_tick(w, n):
        if n == 1:
            s.hooks.game_guard.create_file("steam_appid.txt", b"1245620")
            seen["files"] = vault.read_session().game_folder_files_created

    world.on_tick = on_tick
    assert s.run() == 0
    assert seen["files"] == ["steam_appid.txt"] and listing(game) == before and s.hooks.game_guard.diff() == []


def test_recovery_also_cleans_the_game_folder(env):
    _, live, game, vault = env
    snap = vault.snapshot(live)
    vault.write_session(vault.new_record(snap, live, exe_sha256=None, game_dir=game))
    vault.update_session(game_folder_files_created=["steam_appid.txt"])
    (game / "steam_appid.txt").write_text("1245620")
    assert recover(vault, game_running=lambda: False, log=SessionLog()) == 0
    assert not (game / "steam_appid.txt").exists() and (game / "eldenring.exe").exists()


# ---- fault injection: kill the tool at every boundary of the cycle ----
def _kill_at(point, env, world, session):
    """Arrange for `Killed` to be raised at one boundary of the cycle."""
    _, live, game, vault = env

    def boom(*a, **k):
        raise Killed

    if point == "before_snapshot":
        vault.snapshot = boom
    elif point == "after_snapshot":                      # snapshot verified, record not written yet
        vault.write_session = boom
    elif point == "at_launch":                           # record READY written, game not started
        session.hooks.launch = boom
    elif point == "game_running":
        world.on_tick = lambda w, n: (contaminate(live), boom())[1] if n == 1 else None
    elif point == "game_running_after_exit_settle":
        world.lifetime = 1
        world.on_tick = lambda w, n: contaminate(live)
        real = world.sleep
        session.hooks.sleep = lambda s: boom() if world.pid is None and world.ticks >= 1 and s == 1.0 else real(s)
    elif point == "restore_midway":                      # one file rewritten, then the tool dies
        world.on_tick = lambda w, n: contaminate(live)
        real = vault.restore

        def partial(snap_dir, live_dir):
            (Path(live_dir) / "ER0000.sl2").write_bytes(b"half-written")
            raise Killed
        vault.restore = partial
    elif point == "after_restore_before_verify":
        world.on_tick = lambda w, n: contaminate(live)
        vault.verify_live = boom
    elif point == "before_record_removed":
        world.on_tick = lambda w, n: contaminate(live)
        vault.clear_session = boom
    else:
        raise AssertionError(point)


POINTS = ["before_snapshot", "after_snapshot", "at_launch", "game_running", "game_running_after_exit_settle",
          "restore_midway", "after_restore_before_verify", "before_record_removed"]


@pytest.mark.parametrize("point", POINTS)
def test_killing_the_tool_anywhere_leaves_a_recoverable_save(env, point):
    """I1 after the kill, then `vault restore` returns the save folder byte-identical."""
    _, live, game, vault = env
    before = tree(live)
    world = World()
    s, _ = make(env, world)
    _kill_at(point, env, world, s)
    with pytest.raises(Killed):
        s.run()

    record = SaveVault(vault.root).read_session()                 # a new process looks at the vault
    if record is None:
        assert tree(live) == before, "no record means the live save must already be the original"
    else:
        assert record.snapshot_verified and SaveVault(vault.root).verify_snapshot(Path(record.snapshot_dir)) == []

    fresh = SaveVault(vault.root, sleep=lambda s: None)
    assert recover(fresh, game_running=lambda: False, log=SessionLog()) == 0
    assert tree(live) == before and fresh.read_session() is None


# ---- vault OFF: the game runs, the save is left alone ----
def test_vault_off_launches_and_waits_but_never_backs_up_or_restores(env):
    _, live, game, vault = env
    seen = {}

    def on_tick(w, n):
        if n == 1:
            seen["record"] = vault.read_session()
            seen["snapshots"] = vault.list_snapshots(verify=False)
            contaminate(live)            # progress made while farming

    logs = []
    s, world = make(env, World(on_tick=on_tick), protect=False, log=SessionLog(emit=lambda *a, **k: logs.append(a)))
    assert s.run() == 0
    assert seen["record"] is None and seen["snapshots"] == []         # no record (so `write` is refused), no snapshot
    assert (live / "stray.dat").exists() and (live / "ER0000.sl2").read_bytes().startswith(b"LEVEL 713")   # kept
    assert vault.read_session() is None and world.launched == 1
    assert s.history == [State.IDLE, State.PREFLIGHT, State.RUNNING, State.IDLE]
    text = " | ".join(" ".join(str(x) for x in a) for a in logs)
    assert "status OFF" in text and "not allowed" in text and "left as the game wrote it" in text


def test_vault_on_logs_its_status_too(env):
    logs = []
    s, _ = make(env, log=SessionLog(emit=lambda *a, **k: logs.append(a)))
    assert s.run() == 0
    assert any("status ON" in " ".join(str(x) for x in a) for a in logs)


def test_vault_off_still_refuses_while_a_restore_is_owed(env):
    _, live, game, vault = env
    vault.write_session(vault.new_record(vault.snapshot(live), live, exe_sha256="abc"))
    s, world = make(env, protect=False)
    assert s.run() == EXIT_RESTORE_PENDING and world.launched == 0


@pytest.mark.parametrize("kw,why", [(dict(running=True), "already running"), (dict(ac=True), "anti-cheat")])
def test_vault_off_keeps_the_game_checks(env, kw, why):
    logs = []
    s, world = make(env, protect=False, log=SessionLog(emit=lambda *a, **k: logs.append(a)), **kw)
    assert s.run() == 1 and world.launched == 0
    assert any(why in " ".join(str(x) for x in a) for a in logs)


def test_ctrl_c_in_a_vault_off_session_just_stops_waiting(env):
    _, live, game, vault = env

    def on_tick(w, n):
        if n == 1:
            raise KeyboardInterrupt

    s, world = make(env, World(lifetime=50, on_tick=on_tick), protect=False)
    assert s.run() == 130
    assert vault.read_session() is None and s.history[-1] == State.IDLE


def test_a_record_that_cannot_be_written_discards_the_snapshot_without_tripping_over_its_log(env, monkeypatch):
    """The snapshot's session.log is deleted with it; the host must not write there afterwards (found in 1.6.4)."""
    _, live, game, vault = env
    before = tree(live)
    monkeypatch.setattr(vault, "write_session", lambda r: (_ for _ in ()).throw(OSError("disk full")))
    s, world = make(env)
    assert s.run() == 1 and world.launched == 0
    assert tree(live) == before and not vault.list_snapshots() and vault.read_session() is None

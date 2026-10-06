"""SaveVault: the one guarantee is byte-identical restore (spec 1.6.0 G1, G4, NFR-1..3; tests T6-T9)."""
import os
import shutil
from pathlib import Path

import pytest

from eldendisk.vault import SaveVault, SessionLog, SessionState, VaultError, saves
from eldendisk.vault import session as sess
from eldendisk.vault import vault as sv


@pytest.fixture
def env(tmp_path):
    live = tmp_path / "AppData" / "EldenRing" / "76561198000000000"
    live.mkdir(parents=True)
    (live / "ER0000.sl2").write_bytes(b"SAVE-DATA" * 1000)
    (live / "ER0000.sl2.bak").write_bytes(b"BACKUP" * 500)
    vault = SaveVault(tmp_path / "vault", sleep=lambda s: None)
    return tmp_path, live, vault


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in Path(root).rglob("*") if p.is_file()}


# ---- discovery ----
def test_find_save_dir_exactly_one(tmp_path):
    base = tmp_path / "EldenRing"
    with pytest.raises(VaultError):
        saves.find_save_dir(base)                               # no root
    for sid in ("111", "222"):
        (base / sid).mkdir(parents=True)
        (base / sid / "ER0000.sl2").write_bytes(b"x")
    with pytest.raises(VaultError, match="exactly one"):
        saves.find_save_dir(base)                               # two candidates: never guess
    shutil.rmtree(base / "222")
    assert saves.find_save_dir(base) == base / "111"


def test_find_save_dir_ignores_folders_without_saves(tmp_path):
    (tmp_path / "EldenRing" / "999").mkdir(parents=True)
    with pytest.raises(VaultError):
        saves.find_save_dir(tmp_path / "EldenRing")


# ---- snapshot ----
def test_snapshot_copies_hashes_and_preserves_times(env):
    _, live, vault = env
    snap = vault.snapshot(live)
    assert tree(snap.save_dir) == tree(live)
    assert set(snap.files) == {"ER0000.sl2", "ER0000.sl2.bak"}
    assert vault.verify_snapshot(snap.dir) == []
    assert (snap.save_dir / "ER0000.sl2").stat().st_mtime_ns == (live / "ER0000.sl2").stat().st_mtime_ns
    assert vault.load_manifest(snap.dir)["files"]["ER0000.sl2"]["sha256"] == snap.files["ER0000.sl2"]["sha256"]


def test_snapshot_names_never_collide(env):
    _, live, vault = env
    names = {vault.snapshot(live).dir.name for _ in range(3)}
    assert len(names) == 3


def test_snapshot_of_empty_folder_is_refused(env):
    tmp, _, vault = env
    empty = tmp / "empty"; empty.mkdir()
    with pytest.raises(VaultError):
        vault.snapshot(empty)


def test_failed_snapshot_leaves_nothing_behind(env, monkeypatch):
    _, live, vault = env
    real = shutil.copy2

    def corrupting(src, dst, **kw):
        real(src, dst, **kw)
        Path(dst).write_bytes(b"corrupt")
    monkeypatch.setattr(shutil, "copy2", corrupting)
    with pytest.raises(VaultError):
        vault.snapshot(live)
    assert not [p for p in vault.root.iterdir()] and vault.read_session() is None


def test_snapshot_detects_live_save_changing_during_copy(env, monkeypatch):
    _, live, vault = env
    real = shutil.copy2

    def racing(src, dst, **kw):
        real(src, dst, **kw)
        (live / "ER0000.sl2.bak").write_bytes(b"changed meanwhile")
    monkeypatch.setattr(shutil, "copy2", racing)
    with pytest.raises(VaultError, match="changed while|does not match"):
        vault.snapshot(live)
    assert list(vault.root.iterdir()) == []


# ---- restore (T1, T2, T9) ----
def contaminate(live):
    (live / "ER0000.sl2").write_bytes(b"LEVEL 713 " * 2000)
    (live / "ER0000.sl2.bak").unlink()
    (live / "stray.tmp").write_bytes(b"x")
    (live / "sub").mkdir(); (live / "sub" / "deep.dat").write_bytes(b"y")


def test_restore_makes_the_folder_byte_identical(env):
    _, live, vault = env
    before = tree(live)
    mtime = (live / "ER0000.sl2").stat().st_mtime_ns
    snap = vault.snapshot(live)
    contaminate(live)
    vault.restore(snap.dir, live)
    assert tree(live) == before and not (live / "sub").exists()
    assert vault.verify_live(live, snap.files) == []
    assert (live / "ER0000.sl2").stat().st_mtime_ns == mtime


def test_restore_twice_is_harmless(env):
    _, live, vault = env
    before = tree(live)
    snap = vault.snapshot(live)
    contaminate(live)
    vault.restore(snap.dir, live)
    vault.restore(snap.dir, live)
    assert tree(live) == before


def test_restore_without_any_change_touches_nothing_but_times(env):
    _, live, vault = env
    snap = vault.snapshot(live)
    vault.restore(snap.dir, live)
    assert vault.verify_live(live, snap.files) == []


def test_damaged_snapshot_is_never_restored(env):
    _, live, vault = env
    snap = vault.snapshot(live)
    contaminate(live)
    contaminated = tree(live)
    (snap.save_dir / "ER0000.sl2").write_bytes(b"rotten")
    with pytest.raises(VaultError, match="damaged"):
        vault.restore(snap.dir, live)
    assert tree(live) == contaminated                         # nothing was touched


def test_missing_manifest_refuses_restore(env):
    _, live, vault = env
    snap = vault.snapshot(live)
    (snap.dir / sv.MANIFEST_NAME).unlink()
    with pytest.raises(VaultError):
        vault.restore(snap.dir, live)


# ---- locks (FR-7) ----
class Clock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t
    def sleep(self, s): self.t += s


def test_restore_retries_through_a_temporary_lock(env, monkeypatch):
    tmp, live, _ = env
    clock = Clock()
    vault = SaveVault(tmp / "vault2", sleep=clock.sleep, clock=clock)
    snap = vault.snapshot(live)
    contaminate(live)
    real, n = os.replace, {"n": 0}

    def flaky(a, b):
        n["n"] += 1
        if n["n"] <= 3:
            raise PermissionError("locked by the game")
        return real(a, b)
    monkeypatch.setattr(os, "replace", flaky)
    vault.restore(snap.dir, live)
    assert n["n"] > 3 and vault.verify_live(live, snap.files) == []


def test_restore_gives_up_after_the_timeout_and_keeps_the_snapshot(env, monkeypatch):
    tmp, live, _ = env
    clock = Clock()
    vault = SaveVault(tmp / "vault3", timeout=30, sleep=clock.sleep, clock=clock)
    snap = vault.snapshot(live)
    contaminate(live)
    monkeypatch.setattr(os, "replace", lambda a, b: (_ for _ in ()).throw(PermissionError("locked")))
    with pytest.raises(VaultError, match="still locked"):
        vault.restore(snap.dir, live)
    assert 30 <= clock.t < 40 and vault.verify_snapshot(snap.dir) == []


# ---- verify_live (T7) ----
def test_verify_live_reports_every_kind_of_difference(env):
    _, live, vault = env
    snap = vault.snapshot(live)
    assert vault.verify_live(live, snap.files) == []
    contaminate(live)
    problems = vault.verify_live(live, snap.files)
    assert "hash mismatch: ER0000.sl2" in problems and "missing: ER0000.sl2.bak" in problems
    assert "extra file: stray.tmp" in problems and "extra file: sub/deep.dat" in problems


# ---- session record & preflight ----
def test_session_roundtrip_update_and_clear(env):
    _, live, vault = env
    snap = vault.snapshot(live)
    assert vault.read_session() is None
    vault.write_session(vault.new_record(snap, live, exe_sha256="abc", game_dir=Path("G"), host_pid=7, host_started=99))
    r = vault.read_session()
    assert r.snapshot_dir == str(snap.dir) and r.live_save_dir == str(live) and r.exe_sha256 == "abc"
    assert r.hashes["ER0000.sl2"] == snap.files["ER0000.sl2"]["sha256"]
    assert r.state == SessionState.READY and r.snapshot_verified and (r.host_pid, r.host_started) == (7, 99)
    vault.update_session(state=SessionState.RUNNING, game_pid=42, game_started=1234, game_folder_files_created=["a.txt"])
    r = vault.read_session()
    assert r.state == SessionState.RUNNING and (r.game_pid, r.game_started) == (42, 1234) and r.game_folder_files_created == ["a.txt"]
    vault.clear_session(); vault.clear_session()
    assert vault.read_session() is None and vault.update_session(state=SessionState.RUNNING) is None
    assert not (vault.root / sess.SESSION_NAME).exists()


def test_unreadable_session_is_an_error_not_silence(env):
    _, live, vault = env
    vault.root.mkdir(parents=True)
    (vault.root / sess.SESSION_NAME).write_text("{ not json")
    with pytest.raises(VaultError, match="cannot be trusted"):
        vault.read_session()
    assert "cannot be trusted" in vault.preflight(live)[0]


def test_a_legacy_v1_marker_is_read_as_restore_pending(env):
    import json
    _, live, vault = env
    snap = vault.snapshot(live)
    (vault.root / sess.LEGACY_MARKER_NAME).write_text(json.dumps({
        "version": 1, "created": "2026-10-04T21:30:00+07:00", "snapshot_dir": str(snap.dir), "live_save_dir": str(live),
        "hashes": {}, "game_dir": None, "game_folder_files_created": [], "exe_sha256": "abc"}))
    r = vault.read_session()
    assert r.state == SessionState.RESTORE_PENDING and r.snapshot_dir == str(snap.dir) and r.version == 1
    assert any("unresolved session" in p for p in vault.preflight(live))
    vault.clear_session()
    assert vault.read_session() is None and not (vault.root / sess.LEGACY_MARKER_NAME).exists()


def test_unknown_record_version_is_an_error(env):
    import json
    _, live, vault = env
    vault.root.mkdir(parents=True)
    (vault.root / sess.SESSION_NAME).write_text(json.dumps({"version": 9}))
    with pytest.raises(VaultError, match="cannot be trusted"):
        vault.read_session()


def test_preflight_ok_then_refuses_with_a_record(env):
    _, live, vault = env
    assert vault.preflight(live) == []
    vault.write_session(vault.new_record(vault.snapshot(live), live, exe_sha256=None))
    assert any("unresolved session" in p and "vault restore" in p for p in vault.preflight(live))


def test_preflight_checks_free_space(env, monkeypatch):
    _, live, vault = env
    size = sv.dir_size(live)
    monkeypatch.setattr(shutil, "disk_usage", lambda p: shutil._ntuple_diskusage(10**9, 10**9 - 1, 3 * size - 1))
    assert any("free" in p for p in vault.preflight(live))
    monkeypatch.setattr(shutil, "disk_usage", lambda p: shutil._ntuple_diskusage(10**9, 0, 3 * size))
    assert vault.preflight(live) == []


def test_vault_may_not_overlap_the_save_folder(env):
    _, live, _ = env
    assert any("must not contain" in p for p in SaveVault(live / "vault").preflight(live))


def test_check_live_dir_refuses_dangerous_folders(tmp_path):
    for bad in (Path(tmp_path.anchor), Path.home(), tmp_path / "nope"):
        with pytest.raises(VaultError):
            saves.check_live_dir(bad)


# ---- housekeeping (FR-12, section 12) ----
def test_list_verify_and_prune(env):
    _, live, vault = env
    snaps = [vault.snapshot(live) for _ in range(3)]
    rows = vault.list_snapshots()
    assert [r["name"] for r in rows] == sorted(s.dir.name for s in snaps) and all(r["verified"] for r in rows)
    (snaps[0].save_dir / "ER0000.sl2").write_bytes(b"bad")
    assert vault.list_snapshots()[0]["verified"] is False and vault.verify_snapshot(snaps[0].dir)
    assert [r["verified"] for r in vault.list_snapshots(verify=False)] == [None, None, None]
    gone = vault.prune(2)
    assert gone == [rows[0]["name"]] and len(vault.list_snapshots(verify=False)) == 2


def test_prune_is_refused_while_a_session_record_exists_and_needs_keep(env):
    _, live, vault = env
    snap = vault.snapshot(live)
    vault.write_session(vault.new_record(snap, live, exe_sha256=None))
    with pytest.raises(VaultError, match="unresolved"):
        vault.prune(1)
    assert snap.dir.exists()
    vault.clear_session()
    with pytest.raises(VaultError):
        vault.prune(0)


def test_snapshot_names_cannot_escape_the_vault(env):
    _, live, vault = env
    vault.snapshot(live)
    for bad in ("..", "../x", "20261004-213015/../..", "C:\\Windows"):
        with pytest.raises(VaultError):
            vault.snapshot_path(bad)


def test_status_and_archive(env):
    _, live, vault = env
    assert vault.status()["snapshots"] == 0
    snap = vault.snapshot(live)
    contaminate(live)
    arch = vault.archive_contaminated(live, snap.dir)
    assert (arch / "ER0000.sl2").read_bytes().startswith(b"LEVEL 713")
    vault.restore(snap.dir, live)
    st = vault.status()
    assert st["snapshots"] == 1 and st["last"] == snap.dir.name and st["last_problems"] == [] and st["session"] is None


def test_session_log_buffers_then_flushes(tmp_path):
    emitted = []
    log = SessionLog(emit=lambda level, tag, msg, ok=False: emitted.append((level, tag, msg, ok)))
    log.i("host", "first")
    log.attach(tmp_path / "snap" / "session.log")
    log.ok("vault", "second")
    log.e("vault", "line one\nline two")
    lines = (tmp_path / "snap" / "session.log").read_text().splitlines()
    assert [l.split(" ", 1)[1] for l in lines] == ["I host  : first", "I vault : second", "E vault : line one", "E vault : line two"]
    assert emitted == [("I", "host", "first", False), ("I", "vault", "second", True), ("E", "vault", "line one\nline two", False)]

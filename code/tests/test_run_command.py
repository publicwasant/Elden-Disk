"""Pieces of `run` around the host session: pruning after a finished session and the Steam Cloud note."""
import pytest

import eldendisk.commands.run as run_cmd
from eldendisk.vault import SaveVault


@pytest.fixture
def vault(tmp_path):
    live = tmp_path / "live" / "1"
    live.mkdir(parents=True)
    (live / "ER0000.sl2").write_bytes(b"save")
    v = SaveVault(tmp_path / "vault", sleep=lambda s: None)
    return v, live


def snaps(v):
    return [s["name"] for s in v.list_snapshots(verify=False)]


def test_auto_prune_keeps_the_newest_n(vault, capsys):
    v, live = vault
    for _ in range(4):
        v.snapshot(live)
    run_cmd.auto_prune(v, 2)
    assert len(snaps(v)) == 2 and "pruned 2" in capsys.readouterr().err


def test_auto_prune_zero_never_prunes(vault):
    v, live = vault
    for _ in range(3):
        v.snapshot(live)
    run_cmd.auto_prune(v, 0)
    assert len(snaps(v)) == 3


def test_auto_prune_never_touches_a_vault_that_owes_a_restore(vault):
    v, live = vault
    for _ in range(3):
        v.snapshot(live)
    v.write_session(v.new_record(v.snapshot(live), live, exe_sha256=None))
    run_cmd.auto_prune(v, 1)
    assert len(snaps(v)) == 4


def test_a_prune_failure_is_only_a_warning(vault, monkeypatch, capsys):
    v, live = vault
    v.snapshot(live); v.snapshot(live)
    monkeypatch.setattr(SaveVault, "prune", lambda self, keep: (_ for _ in ()).throw(OSError("locked")))
    run_cmd.auto_prune(v, 1)
    assert "could not prune" in capsys.readouterr().err


def test_run_v_shows_the_lines_other_terminals_log(tmp_path, monkeypatch, capsys):
    """`run -v` tails the shared log: lines of other commands appear, its own are not repeated."""
    import argparse
    from eldendisk.logbook import Event, book, format_line
    from datetime import datetime

    log = tmp_path / "vault" / "eldendisk.log"
    book.configure(file=log)
    seen = {}

    class FakeSession:
        history = []

        def __init__(self, *a, **k): pass

        def run(self):
            line = format_line(Event(datetime.now(), 99999, "D", "cli", "eldendisk 1.6.2 write --set level=150"))
            with open(log, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            book.i("host", "own line")
            seen["ran"] = True
            return 0

    monkeypatch.setattr(run_cmd, "Session", FakeSession)
    monkeypatch.setattr(run_cmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(run_cmd.launcher, "find_game_dir", lambda d: tmp_path / "game")
    monkeypatch.setattr(run_cmd, "sha256_file", lambda p: "ab" * 32)
    monkeypatch.setattr(run_cmd, "live_dir", lambda d: tmp_path / "live")
    monkeypatch.setattr(run_cmd, "list_process_names", lambda: [])
    monkeypatch.setattr(run_cmd, "session_log", lambda: None)
    monkeypatch.setattr(run_cmd, "_regulation", lambda *a: (None, "none"))       # not what this test is about (it would build)
    args = argparse.Namespace(vault=str(tmp_path / "vault"), save_dir=None, game_dir=None, offsets="x",
                              no_archive_contaminated=False, keep=0, launch_timeout=1.0, verbose=True)
    assert run_cmd.cmd_run(args) == 0 and seen["ran"]
    err = capsys.readouterr().err
    assert "write --set level=150" in err and err.count("write --set level=150") == 1
    book.close()


# ---- the regulation.bin swap (spec 1.6.4) ----
def _run_with_world(tmp_path, monkeypatch, capsys, *, protect):
    import argparse
    from eldendisk.logbook import book

    (tmp_path / "mine").mkdir()
    (tmp_path / "mine" / "regulation.bin").write_bytes(b"mine")

    class FakeSession:
        history = []

        def __init__(self, *a, **k): pass

        def run(self): return 0

    monkeypatch.setattr(run_cmd, "Session", FakeSession)
    monkeypatch.setattr(run_cmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(run_cmd.launcher, "find_game_dir", lambda d: tmp_path / "game")
    monkeypatch.setattr(run_cmd, "sha256_file", lambda p: "ab" * 32)
    monkeypatch.setattr(run_cmd, "live_dir", lambda d: tmp_path / "live")
    monkeypatch.setattr(run_cmd, "list_process_names", lambda: [])
    monkeypatch.setattr(run_cmd, "session_log", lambda: None)
    args = argparse.Namespace(vault=str(tmp_path / "vault"), save_dir=None, game_dir=None, offsets="x",
                              no_archive_contaminated=False, keep=0, launch_timeout=1.0, verbose=False, protect=protect,
                              regulation=str(tmp_path / "mine" / "regulation.bin"), extension_dir=str(tmp_path / "ext"))
    assert run_cmd.cmd_run(args) == 0
    captured = capsys.readouterr()
    book.close()
    return captured.out + captured.err


def test_run_header_names_the_file_that_will_replace_the_games(tmp_path, monkeypatch, capsys):
    out = _run_with_world(tmp_path, monkeypatch, capsys, protect=True)
    assert "replaces the game's regulation.bin for this session" in out and "is ignored" not in out


def test_run_with_the_vault_off_warns_that_the_file_is_ignored(tmp_path, monkeypatch, capsys):
    out = _run_with_world(tmp_path, monkeypatch, capsys, protect=False)
    assert "is ignored: with the vault OFF" in out and "replaces the game's" not in out


def test_run_ignores_the_1_6_4_folder_and_says_so(tmp_path, monkeypatch, capsys):
    (tmp_path / "vault" / "regulation").mkdir(parents=True)
    (tmp_path / "vault" / "regulation" / "regulation.bin").write_bytes(b"old")
    out = _run_with_world(tmp_path, monkeypatch, capsys, protect=True)
    assert "is no longer read" in " ".join(out.split())


# ---- the hint to secure a new build ----
@pytest.mark.parametrize("mode,history,hint", [("built", ["RESTORING"], True), ("secured", ["RESTORING"], False),
                                               ("built", [], False), ("file", ["RESTORING"], False)])
def test_run_hints_at_secure_only_after_a_session_that_ran_a_new_build(tmp_path, monkeypatch, capsys, mode, history, hint):
    import argparse
    from eldendisk.host.host import State
    from eldendisk.logbook import book

    class FakeSession:
        def __init__(self, *a, **k):
            self.history = [State.RESTORING] if history else []

        def run(self): return 0

    monkeypatch.setattr(run_cmd, "Session", FakeSession)
    monkeypatch.setattr(run_cmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(run_cmd.launcher, "find_game_dir", lambda d: tmp_path / "game")
    monkeypatch.setattr(run_cmd, "sha256_file", lambda p: "ab" * 32)
    monkeypatch.setattr(run_cmd, "live_dir", lambda d: tmp_path / "live")
    monkeypatch.setattr(run_cmd, "list_process_names", lambda: [])
    monkeypatch.setattr(run_cmd, "session_log", lambda: None)
    monkeypatch.setattr(run_cmd, "_regulation", lambda *a: (tmp_path / "r.bin", mode))
    args = argparse.Namespace(vault=str(tmp_path / "vault"), save_dir=None, game_dir=None, offsets="x", no_archive_contaminated=False,
                              keep=0, launch_timeout=1.0, verbose=False, protect=True, regulation=None, extension_dir=None, spec=None)
    assert run_cmd.cmd_run(args) == 0
    out = capsys.readouterr()
    book.close()
    assert ("extension innovate-items spells --secure" in out.out + out.err) is hint


# ---- 1.7.1: the text step ----
def _args(tmp_path, **kw):
    import argparse
    d = dict(vault=str(tmp_path / "vault"), offsets="offsets.json", spec=None, extension_dir=None, verbose=False)
    return argparse.Namespace(**{**d, **kw})


def test_the_text_command_is_write_text_wait_with_the_same_vault_offsets_and_design(tmp_path, monkeypatch):
    monkeypatch.setattr(run_cmd.sys, "frozen", False, raising=False)
    cmd, cwd = run_cmd.text_command(_args(tmp_path, spec="my.json", extension_dir="ext"), tmp_path / "vault")
    assert cmd[:3] == [run_cmd.sys.executable, "-m", "eldendisk"] and cmd[3:6] == ["write", "--text", "--wait"]
    assert cmd[cmd.index("--vault") + 1] == str(tmp_path / "vault") and cmd[cmd.index("--offsets") + 1] == "offsets.json"
    assert cmd[cmd.index("--spec") + 1] == "my.json" and cmd[cmd.index("--extension-dir") + 1] == "ext"
    assert cwd and (run_cmd.Path(cwd) / "eldendisk").is_dir()
    plain, _ = run_cmd.text_command(_args(tmp_path), tmp_path / "vault")
    assert "--spec" not in plain and "--extension-dir" not in plain


def test_the_frozen_exe_runs_itself(tmp_path, monkeypatch):
    monkeypatch.setattr(run_cmd.sys, "frozen", True, raising=False)
    cmd, cwd = run_cmd.text_command(_args(tmp_path), tmp_path / "vault")
    assert cmd[:2] == [run_cmd.sys.executable, "write"] and cwd is None


def test_start_text_spawns_in_its_own_process_group_and_stays_quiet_only_under_v(tmp_path):
    calls = []
    run_cmd.start_text(_args(tmp_path), tmp_path / "vault", spawn=lambda cmd, **kw: calls.append(kw))
    run_cmd.start_text(_args(tmp_path, verbose=True), tmp_path / "vault", spawn=lambda cmd, **kw: calls.append(kw))
    assert "stdout" not in calls[0] and calls[1]["stdout"] is run_cmd.subprocess.DEVNULL
    assert all("creationflags" in c for c in calls)


def _run_hooks(tmp_path, monkeypatch, *, protect, world, mode, text):
    """cmd_run with a fake Session that keeps the hooks it was given -> (hooks, spawned commands)."""
    import argparse
    from eldendisk.logbook import book
    box = {}

    class FakeSession:
        history = []

        def __init__(self, vault, live, hooks, **k): box["hooks"] = hooks

        def run(self):
            box["hooks"].on_running(4242)
            return 0

    spawned = []
    monkeypatch.setattr(run_cmd, "Session", FakeSession)
    monkeypatch.setattr(run_cmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(run_cmd.launcher, "find_game_dir", lambda d: tmp_path / "game")
    monkeypatch.setattr(run_cmd, "sha256_file", lambda p: "ab" * 32)
    monkeypatch.setattr(run_cmd, "live_dir", lambda d: tmp_path / "live")
    monkeypatch.setattr(run_cmd, "list_process_names", lambda: [])
    monkeypatch.setattr(run_cmd, "session_log", lambda: None)
    monkeypatch.setattr(run_cmd, "_regulation", lambda *a: (world, mode))
    monkeypatch.setattr(run_cmd, "design_has_text", lambda a, v: text)
    monkeypatch.setattr(run_cmd, "start_text", lambda a, v: spawned.append("text") or type("P", (), {"poll": lambda s: 0})())
    args = argparse.Namespace(vault=str(tmp_path / "vault"), save_dir=None, game_dir=None, offsets="x", protect=protect,
                              no_archive_contaminated=False, keep=0, launch_timeout=1.0, verbose=False)
    assert run_cmd.cmd_run(args) == 0
    book.close()
    return spawned


@pytest.mark.parametrize("protect,world,mode,text,expect", [
    (True, "w.bin", "built", True, ["text"]), (True, "w.bin", "secured", True, ["text"]), (True, "w.bin", "last", True, ["text"]),
    (True, "w.bin", "built", False, []),             # no text in the design: nothing to start
    (True, "w.bin", "file", True, []),               # `--regulation FILE` is not the extension's build
    (True, None, "none", True, []),                  # nothing was swapped
    (False, "w.bin", "built", True, [])])            # vault OFF: `write` is not allowed at all
def test_run_starts_the_text_step_only_when_it_has_something_to_give(tmp_path, monkeypatch, protect, world, mode, text, expect):
    assert _run_hooks(tmp_path, monkeypatch, protect=protect, world=world, mode=mode, text=text) == expect


def test_a_text_step_still_running_when_the_session_ends_is_stopped(tmp_path, monkeypatch):
    import argparse
    from eldendisk.logbook import book
    stopped = []

    class Child:
        def poll(self): return None
        def terminate(self): stopped.append(1)

    class FakeSession:
        history = []
        def __init__(self, vault, live, hooks, **k): self.h = hooks
        def run(self):
            self.h.on_running(1)
            return 0

    monkeypatch.setattr(run_cmd, "Session", FakeSession)
    monkeypatch.setattr(run_cmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(run_cmd.launcher, "find_game_dir", lambda d: tmp_path / "game")
    monkeypatch.setattr(run_cmd, "sha256_file", lambda p: "ab" * 32)
    monkeypatch.setattr(run_cmd, "live_dir", lambda d: tmp_path / "live")
    monkeypatch.setattr(run_cmd, "list_process_names", lambda: [])
    monkeypatch.setattr(run_cmd, "session_log", lambda: None)
    monkeypatch.setattr(run_cmd, "_regulation", lambda *a: ("w.bin", "built"))
    monkeypatch.setattr(run_cmd, "design_has_text", lambda a, v: True)
    monkeypatch.setattr(run_cmd, "start_text", lambda a, v: Child())
    args = argparse.Namespace(vault=str(tmp_path / "vault"), save_dir=None, game_dir=None, offsets="x", protect=True,
                              no_archive_contaminated=False, keep=0, launch_timeout=1.0, verbose=False)
    assert run_cmd.cmd_run(args) == 0 and stopped == [1]
    book.close()

"""The CLI front: log file next to the vault, concise view by default, `-v` = the log itself, results without `-v`."""
import re

import pytest

import os

import eldendisk.__main__ as cli
import eldendisk.commands.vault as vcmd
from eldendisk.logbook import LOG_NAME
from eldendisk.vault import SaveVault

LOGCAT = re.compile(r"^\d\d-\d\d \d\d:\d\d:\d\d\.\d{3} +\d+ [VDIWE] \S+ *: ")


@pytest.fixture
def env(tmp_path, monkeypatch):
    live = tmp_path / "AppData" / "EldenRing" / "76561198000000000"
    live.mkdir(parents=True)
    (live / "ER0000.sl2").write_bytes(b"SAVE-DATA" * 100)
    vault = SaveVault(tmp_path / "vault", sleep=lambda s: None)
    monkeypatch.setattr(vcmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(vcmd, "find_pid", lambda name: None)
    monkeypatch.setattr(vcmd, "process_started", lambda pid: None)
    return live, vault


def test_every_command_writes_the_logcat_file_next_to_the_vault(env, capsys):
    live, vault = env
    vault.snapshot(live)
    assert cli.main(["vault", "verify", vault.list_snapshots(verify=False)[0]["name"], "--vault", str(vault.root)]) == 0
    text = (vault.root / LOG_NAME).read_text(encoding="utf-8")
    lines = text.splitlines()
    assert all(LOGCAT.match(l) for l in lines), lines
    assert "D client   : run: " in lines[0] and "vault verify" in lines[0]          # the command line itself
    assert not any("version " in l for l in lines)                                   # the version is `--version`, not every log
    assert any(" I vault" in l and "matches its manifest" in l for l in lines)
    assert lines[-1].endswith("exit 0")


def test_the_log_file_keeps_debug_events_the_console_hides(env, capsys):
    live, vault = env
    assert cli.main(["vault", "status", "--vault", str(vault.root)]) == 0
    captured = capsys.readouterr()
    assert " D client" in (vault.root / LOG_NAME).read_text(encoding="utf-8")
    assert "D client" not in captured.err + captured.out and "exit 0" not in captured.err


def test_without_v_the_console_is_concise_and_with_v_it_is_the_log(env, capsys):
    live, vault = env
    snap = vault.snapshot(live)
    base = ["vault", "verify", snap.dir.name, "--vault", str(vault.root)]
    assert cli.main(base) == 0
    concise = capsys.readouterr().err
    assert " \u2713  vault     snapshot" in concise and not LOGCAT.search(concise)

    assert cli.main([*base, "-v"]) == 0
    raw = capsys.readouterr().err
    lines = raw.splitlines()
    assert lines and all(LOGCAT.match(l) for l in lines)                # nothing but log lines
    assert any(" D client" in l for l in lines) and "\u2713" not in raw


def test_v_is_accepted_on_the_group_on_the_verb_and_on_every_command(env, capsys):
    live, vault = env
    v = str(vault.root)
    for argv in (["vault", "-v", "status", "--vault", v], ["vault", "status", "-v", "--vault", v],
                 ["vault", "list", "--fast", "-v", "--vault", v]):
        cli.main(argv)
        assert " D client" in capsys.readouterr().err, argv
    parser = cli.build_parser()
    for argv in (["run", "-v"], ["read", "monitor-buffs", "-v"], ["write", "-v", "hp=1"], ["write", "hp=1", "-v"], ["hash", "-v"],
                 ["scripts", "status", "-v"], ["innovate-spells", "build", "-v"], ["resurrect", "-v", "margit"], ["export", "-v"],
                 ["reset", "-v"], ["check", "-v"], ["probe", "-v"]):
        assert parser.parse_args(argv).verbose is True, argv
    assert parser.parse_args(["vault", "status"]).verbose is False


def test_results_print_without_v(env, capsys):
    live, vault = env
    vault.snapshot(live)
    assert cli.main(["vault", "list", "--vault", str(vault.root)]) == 0
    out = capsys.readouterr().out
    assert "snapshot" in out and "verified" in out and "MiB" in out
    assert cli.main(["vault", "prune", "--keep", "1", "--vault", str(vault.root)]) == 0
    assert "deleted 0 snapshot(s)" in capsys.readouterr().err


def test_keep_without_yes_explains_in_the_new_layout(env, capsys):
    live, vault = env
    vault.write_session(vault.new_record(vault.snapshot(live), live, exe_sha256="x", host_pid=1, host_started=1))
    assert cli.main(["vault", "keep", "--vault", str(vault.root)]) == 1
    out = capsys.readouterr().out
    assert "CURRENT save" in out and "--yes" in out and "save " in out


def test_an_unavailable_remembered_vault_still_reports_the_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("eldendisk.vault.location.load_registry_vault_dir", lambda: str(tmp_path / "gone" / "vault"))
    monkeypatch.setattr(vcmd, "require_windows_x64", lambda: None)
    assert cli.main(["vault", "status"]) == 1
    assert "not available" in capsys.readouterr().err
    assert not (tmp_path / "gone").exists()                              # no log file, no stray folders


def test_a_host_session_reports_concise_events_in_order(tmp_path):
    from eldendisk.logbook import book
    from eldendisk.vault import SessionLog
    from tests.test_host import World, make
    live = tmp_path / "AppData" / "EldenRing" / "1"
    live.mkdir(parents=True)
    (live / "ER0000.sl2").write_bytes(b"SAVE")
    game = tmp_path / "Game"
    game.mkdir()
    (game / "eldenring.exe").write_bytes(b"EXE")
    vault = SaveVault(tmp_path / "vault", sleep=lambda s: None)
    events = []
    book.configure(file=tmp_path / "vault" / LOG_NAME, console=events.append)
    session, _ = make((tmp_path, live, game, vault), World(), log=SessionLog(emit=book.emit))
    assert session.run() == 0
    book.close()
    shown = [(e.level, e.tag, e.msg, e.ok) for e in events if e.level not in "VD"]
    assert [m for _l, _t, m, _o in shown] == [
        shown[0][2], "launching eldenring.exe offline", f"running, pid {4242}; `read` allowed, `write` allowed", "exited",
        "`ER0000.sl2` restored, byte-identical to the snapshot"]
    assert shown[0][2].startswith("snapshot ") and shown[0][3] is True and shown[-1][3] is True
    assert not any(ch in e.msg for e in events for ch in "\u2713\u2716")      # glyphs belong to the view, not the message
    assert any(e.level == "D" and e.msg == "state RUNNING" for e in events)
    text = (tmp_path / "vault" / LOG_NAME).read_text(encoding="utf-8")
    assert "state RESTORING" in text and "byte-identical" in text


def test_command_line_is_the_command_as_typed(tmp_path):
    from eldendisk import logsetup
    exe = tmp_path / "eldendisk.exe"
    assert logsetup.command_line(["run", "-v"]) == "eldendisk run -v"                      # from code: no process to look at
    orig = [str(exe), "run", "-v"]
    assert logsetup.command_line(["run", "-v"], orig) == "eldendisk.exe run -v"
    assert logsetup.command_line(["run", "-v"], ["python", "-m", "eldendisk", "run", "-v"]) == "python -m eldendisk run -v"
    assert logsetup.command_line(["write", "--set", "a b=1"], ["x", "write", "--set", "a b=1"]) == 'x write --set "a b=1"'
    assert logsetup.command_line(["run"], ["other", "args"]) == "eldendisk run"   # orig does not end with argv: ignore it


def test_a_step_run_started_does_not_log_its_command_line_again(env, monkeypatch):
    from eldendisk.logsetup import STARTED_BY
    live, vault = env
    monkeypatch.setenv(STARTED_BY, "run")
    assert cli.main(["vault", "status", "--vault", str(vault.root)]) == 0
    text = (vault.root / LOG_NAME).read_text(encoding="utf-8")
    assert "client   : run: " not in text and text.splitlines()[-1].endswith("exit 0")


def test_run_marks_the_steps_it_starts(tmp_path):
    import eldendisk.commands.run as run_cmd
    from eldendisk.logsetup import STARTED_BY
    args = cli.build_parser().parse_args(["run"])
    seen = []
    for start in (run_cmd.start_apply, run_cmd.start_enemies, run_cmd.start_scripts):
        start(args, tmp_path, spawn=lambda c, **kw: seen.append(kw))
    assert [s["env"][STARTED_BY] for s in seen] == ["run"] * 3



def test_the_built_in_config_files_are_not_logged_every_time(monkeypatch):
    from eldendisk.commands import common
    from eldendisk import paths
    seen = []
    monkeypatch.setattr(common.book, "d", lambda tag, msg: seen.append((tag, msg)))
    monkeypatch.setattr(paths, "describe_resource", lambda p: "embedded")
    common.log_config("offsets", "X:/_MEI/offsets.json")
    monkeypatch.setattr(paths, "describe_resource", lambda p: "external")
    common.log_config("offsets", "D:/dist/offsets.json")
    assert seen == [("config", "offsets: D:/dist/offsets.json (external)")]

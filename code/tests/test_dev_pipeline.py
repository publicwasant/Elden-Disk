import argparse
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import dev_pipeline  # noqa: E402


@pytest.fixture
def steps(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(dev_pipeline, "run_precheck", lambda: calls.append("tests") or True)
    monkeypatch.setattr(dev_pipeline, "run_build", lambda **kw: calls.append("build") or True)
    monkeypatch.setattr(dev_pipeline, "status_lines", lambda **kw: calls.append("status") or ["  exe  x"])
    monkeypatch.setattr(dev_pipeline, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(dev_pipeline.subprocess, "run", lambda *a, **k: pytest.fail("the pipeline must not start anything"))
    return calls


def test_the_cycle_is_tests_then_build_then_status_and_nothing_else(steps):
    assert dev_pipeline.main([]) == 0
    assert steps == ["tests", "build", "status"]


def test_the_game_is_never_started(steps):
    assert dev_pipeline.main(["--skip-tests"]) == 0          # subprocess.run is a failing stub in the fixture
    assert steps == ["build", "status"]


def test_options_the_pipeline_does_not_know_are_refused(steps, capsys):
    for bad in (["--vault-off"], ["--dry-run"], ["--no-such-flag"]):
        with pytest.raises(SystemExit) as e:
            dev_pipeline.main(bad)
        assert e.value.code == 2
    assert steps == [] and "unrecognized arguments" in capsys.readouterr().err


def test_a_failed_test_run_stops_before_the_build(monkeypatch):
    got = []
    monkeypatch.setattr(dev_pipeline, "run_precheck", lambda: got.append("tests") or False)
    monkeypatch.setattr(dev_pipeline, "run_build", lambda **kw: got.append("build") or True)
    assert dev_pipeline.main([]) == 1 and got == ["tests"]


def test_a_failed_build_gives_exit_1_and_no_status(monkeypatch, capsys):
    monkeypatch.setattr(dev_pipeline, "run_precheck", lambda: True)
    monkeypatch.setattr(dev_pipeline, "run_build", lambda **kw: False)
    assert dev_pipeline.main([]) == 1 and "Done" not in capsys.readouterr().out


def test_the_status_says_where_the_exe_is_how_big_and_how_long(project, monkeypatch):
    exe = project / "build" / "dist" / "eldendisk.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ" * 1024)
    (exe.parent / "README.md").write_text("x")
    layout = dev_pipeline.build_layout()
    text = "\n".join(dev_pipeline.status_lines(layout=layout, engine="pyinstaller", embed=True,
                                              configs=dev_pipeline.config_files(layout), tests_s=75.0, build_s=42.5, total_s=130.0))
    assert str(exe) in text and "2,048 bytes" in text and "1 min 15.0 s" in text and "42.5 s" in text and "2 min 10.0 s" in text
    assert "offsets.json, chr_state_ids.json, design.json embedded in the exe" in text
    assert dev_pipeline._sha256(exe) in text and dev_pipeline.__version__ in text
    assert "build\\dist\\eldendisk.exe run -v" in text and "EldenDisk" in text
    assert "skipped" in "\n".join(dev_pipeline.status_lines(layout=layout, engine="nuitka", embed=False, configs=[],
                                                          tests_s=None, build_s=1.0, total_s=1.0))


def _built(project):
    exe = project / "build" / "dist" / "eldendisk.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ" * 8)
    (exe.parent / "README.md").write_text("x")
    return exe


def _status(project, **kw):
    layout = dev_pipeline.build_layout()
    return "\n".join(dev_pipeline.status_lines(layout=layout, engine="pyinstaller", embed=True, configs=[], tests_s=1.0,
                                               build_s=2.0, total_s=3.0, **kw))


def test_the_status_is_plain_text_unless_colour_or_links_are_asked_for(project):
    _built(project)
    assert "\x1b" not in _status(project)


def test_the_status_has_the_console_colours_and_clickable_paths(project, monkeypatch):
    exe = _built(project)
    linked = []
    # ui.linkify only knows Windows paths (it is tested in test_ui); here it is checked that the status hands it the three paths
    monkeypatch.setattr(dev_pipeline.ui, "linkify", lambda text, color=False, **kw: linked.append((text, color)) or f"<link>{text}</link>")
    text = _status(project, color=True, links=True)
    assert [t.split(" (")[0] for t, c in linked if c] == [str(exe), str(exe.parent / "README.md"), str(dev_pipeline.app_data_dir())]
    assert text.count("<link>") == 3
    assert "\x1b[36m" in text and "\x1b[2m" in text                      # the start command is cyan, labels and sha256 dim
    only_colour = _status(project, color=True)
    assert "<link>" not in only_colour and "\x1b[38;5;208meldendisk.exe" in only_colour    # the file name at the end of the path is orange


def test_log_words_are_tinted_like_the_console(monkeypatch, capsys):
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)
    dev_pipeline.log("SUCCESS: tests passed.")
    dev_pipeline.log("ERROR: boom")
    dev_pipeline.log("Step 1/2: Running the tests")
    out = capsys.readouterr().out
    assert "\x1b[32mSUCCESS\x1b[0m: tests passed." in out and "\x1b[31mERROR\x1b[0m: boom" in out and "\x1b[1mStep 1/2\x1b[0m" in out
    monkeypatch.setenv("NO_COLOR", "1")
    dev_pipeline.log("SUCCESS: x")
    assert capsys.readouterr().out == "[E2E Pipeline] SUCCESS: x\n"


def test_the_build_always_cleans_and_embeds_unless_told_not_to(monkeypatch, tmp_path):
    got = []
    monkeypatch.setattr(dev_pipeline, "run_precheck", lambda: True)
    monkeypatch.setattr(dev_pipeline, "run_build", lambda **kw: got.append(kw) or False)
    dev_pipeline.main([])
    dev_pipeline.main(["--no-embed", "--engine", "nuitka"])
    dev_pipeline.main(["--keep-app-data"])
    assert got == [dict(clean=True, embed=True, engine="pyinstaller", icon=None, app_data=True),
                   dict(clean=True, embed=False, engine="nuitka", icon=None, app_data=True),
                   dict(clean=True, embed=True, engine="pyinstaller", icon=None, app_data=False)]


# ---------- the build itself (the compiler is faked) ----------
@pytest.fixture
def project(tmp_path, monkeypatch):
    code = tmp_path / "code"
    (code / "eldendisk").mkdir(parents=True)
    (code / "offsets.json").write_text("{}")
    (code / "chr_state_ids.json").write_text("{}")
    (code / "eldendisk" / "__main__.py").write_text("")
    (code / "design.json").write_text('{"innovate_items": {"spells": {"maximum": 1, "slots": {"<id-1>": null}}}}')
    monkeypatch.setattr(dev_pipeline, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(dev_pipeline, "CODE_DIR", code)
    return tmp_path


def build(monkeypatch, rc=0, **kw):
    calls = []

    def fake_run(cmd, check=False):
        calls.append(cmd)
        return argparse.Namespace(returncode=rc)

    monkeypatch.setattr("subprocess.run", fake_run)
    return dev_pipeline.run_build(**kw), calls


def test_pyinstaller_puts_the_exe_in_build_dist_and_embeds_the_configs(project, monkeypatch):
    ok, calls = build(monkeypatch)
    cmd = calls[0]
    assert ok and "PyInstaller" in cmd and "--onefile" in cmd and f"--distpath={project / 'build' / 'dist'}" in cmd
    adds = [c for c in cmd if c.startswith("--add-data=")]
    assert len(adds) == 3 and not any("schema" in a for a in adds)
    assert any(a.endswith("design.json;.") or a.endswith("design.json:.") for a in adds)
    assert not (project / "build" / "dist" / "offsets.json").exists()          # embedded: nothing copied


def test_nuitka_embeds_and_names_the_exe(project, monkeypatch):
    ok, calls = build(monkeypatch, engine="nuitka")
    inc = [c for c in calls[0] if c.startswith("--include-data-files=")]
    assert ok and len(inc) == 3 and inc[0].endswith("=offsets.json") and inc[-1].endswith("=design.json")
    assert "--output-filename=eldendisk.exe" in calls[0] and f"--output-dir={project / 'build' / 'dist'}" in calls[0]


@pytest.mark.parametrize("engine", ["pyinstaller", "nuitka"])
def test_without_embedding_the_editable_configs_go_next_to_the_exe(project, monkeypatch, engine):
    ok, calls = build(monkeypatch, embed=False, engine=engine)
    out = project / "build" / "dist"
    assert ok and (out / "offsets.json").exists() and (out / "chr_state_ids.json").exists() and (out / "design.json").exists()
    assert not any(c.startswith(("--add-data=", "--include-data-files=")) for c in calls[0])


def test_a_failed_build_returns_false_and_copies_nothing(project, monkeypatch):
    ok, _ = build(monkeypatch, rc=2, embed=False)
    assert not ok and not (project / "build" / "dist" / "offsets.json").exists()


def test_clean_removes_old_artifacts(project, monkeypatch):
    stale = project / "build" / "work" / "stale.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("x")
    build(monkeypatch)
    assert not stale.exists()
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("x")
    build(monkeypatch, clean=False)
    assert stale.exists()


def test_unknown_engine_and_missing_icon(project, monkeypatch, capsys):
    ok, calls = build(monkeypatch, engine="cx_freeze")
    assert not ok and not calls and "unsupported build engine" in capsys.readouterr().out
    _ok, calls = build(monkeypatch, icon="nope.ico")
    assert not any(c.startswith("--icon=") for c in calls[0]) and "icon file not found" in capsys.readouterr().out


def test_clean_refuses_to_destroy_an_unresolved_session(project, monkeypatch):
    v = project / "build" / "dist" / "x" / "backup" / "vault"
    v.mkdir(parents=True)
    (v / "session.json").write_text("{}")
    ok, calls = build(monkeypatch)
    assert not ok and not calls and (v / "session.json").exists()


def test_clean_with_a_resolved_vault_still_cleans(project, monkeypatch):
    v = project / "build" / "dist" / "x" / "backup" / "vault"
    (v / "20261006-000000").mkdir(parents=True)
    ok, _ = build(monkeypatch)
    assert ok and not v.exists()


# ---------- README next to the exe ----------
def _docs(project, intro="# Elden-Disk {version}\n\nQuick start\n\n# Command reference\n",
          reference="# Reference title\n\nComplete reference.\n\n## 1. `run`\n"):
    (project / "docs" / "guilde").mkdir(parents=True)
    (project / "docs" / "guilde" / "README-exe.md").write_text(intro, encoding="utf-8")
    (project / "docs" / "guilde" / "cli-commands-exe.md").write_text(reference, encoding="utf-8")


def test_build_writes_a_readme_next_to_the_exe(project, monkeypatch):
    _docs(project)
    ok, _ = build(monkeypatch)
    text = (project / "build" / "dist" / "README.md").read_text(encoding="utf-8")
    assert ok
    assert text.startswith(f"# Elden-Disk {dev_pipeline.__version__}\n") and "{version}" not in text
    assert "# Command reference\n\nComplete reference." in text       # the reference follows, without its own title
    assert "Reference title" not in text and "## 1. `run`" in text and text.endswith("\n")


def test_build_without_docs_still_succeeds_and_warns(project, monkeypatch, capsys):
    ok, _ = build(monkeypatch)
    assert ok and not (project / "build" / "dist" / "README.md").exists()
    assert "no README.md" in capsys.readouterr().out


def test_a_failed_build_writes_no_readme(project, monkeypatch):
    _docs(project)
    ok, _ = build(monkeypatch, rc=2)
    assert not ok and not (project / "build" / "dist" / "README.md").exists()


def test_the_real_docs_make_a_readme():
    root = Path(__file__).resolve().parents[2]
    text = dev_pipeline.exe_readme({"project_root": root})
    assert text and "# Command reference" in text and "## 1. `run` (host)" in text and "{version}" not in text
    assert "Standalone Executable CLI Commands Reference" not in text    # the reference's own title is replaced
    assert "`build`" not in text.split("# Command reference", 1)[1].split("## 1.")[0]


def test_the_tests_run_with_a_temporary_folder_of_their_own_outside_the_build(monkeypatch, tmp_path):
    """No numbered folders and no `pytest-current` link in %TEMP% (Windows may refuse to remove that link when pytest ends), and not
    inside ./build: the tests leave vaults that owe a restore, which the build's clean must refuse to remove."""
    seen = []
    monkeypatch.setattr(dev_pipeline, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(dev_pipeline.subprocess, "run", lambda cmd, cwd=None: seen.append(cmd) or type("R", (), {"returncode": 0})())
    assert dev_pipeline.run_precheck()
    temp = dev_pipeline.tests_temp_dir()
    assert seen[0][1:3] == ["-m", "pytest"] and f"--basetemp={temp}" in seen[0]
    assert temp.name == "eldendisk-pytest" and dev_pipeline.build_layout()["build_root"] not in temp.parents


# ---------- %LOCALAPPDATA%\EldenDisk (LOCALAPPDATA points into tmp_path in every test: conftest) ----------
@pytest.fixture
def app_data(monkeypatch):
    monkeypatch.setattr(dev_pipeline, "find_pid", lambda exe: None)
    d = dev_pipeline.app_data_dir()
    (d / "vault" / "20261012-185726").mkdir(parents=True)
    (d / "vault" / "eldendisk.log").write_text("x")
    (d / "output" / "disk-state.json").parent.mkdir(parents=True)
    (d / "output" / "disk-state.json").write_text("{}")
    return d


def test_the_tools_own_folder_is_removed_before_the_build(project, monkeypatch, app_data):
    ok, calls = build(monkeypatch, app_data=True)
    assert ok and calls and not app_data.exists()
    assert app_data.parent.exists()                                              # only EldenDisk, not %LOCALAPPDATA%


def test_without_app_data_the_tools_folder_stays(project, monkeypatch, app_data):
    ok, _ = build(monkeypatch)
    assert ok and (app_data / "vault" / "eldendisk.log").exists()


def test_a_vault_that_owes_a_restore_stops_the_build_and_nothing_is_removed(project, monkeypatch, app_data, capsys):
    (app_data / "vault" / "session.json").write_text("{}")
    stale = project / "build" / "work" / "stale.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("x")
    ok, calls = build(monkeypatch, app_data=True)
    out = capsys.readouterr().out
    assert not ok and not calls and (app_data / "vault" / "session.json").exists() and stale.exists()
    assert "vault restore" in out and "--keep-app-data" in out


@pytest.mark.parametrize("running", ["eldenring.exe", "eldendisk.exe"])
def test_nothing_is_removed_while_the_game_or_the_tool_runs(project, monkeypatch, app_data, capsys, running):
    monkeypatch.setattr(dev_pipeline, "find_pid", lambda exe: 4242 if exe == running else None)
    ok, calls = build(monkeypatch, app_data=True)
    assert not ok and not calls and (app_data / "vault" / "eldendisk.log").exists()
    assert running + " is running" in capsys.readouterr().out


def test_only_the_exact_folder_may_be_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(dev_pipeline, "find_pid", lambda exe: None)
    assert dev_pipeline.app_data_problems(dev_pipeline.app_data_dir()) == []
    for other in (tmp_path / "EldenDisk", dev_pipeline.app_data_dir() / "vault", dev_pipeline.app_data_dir().parent):
        assert dev_pipeline.app_data_problems(other)



# ---------- the external scripts of external_scripts/defaults travel with the exe (1.7.2) ----------
def _defaults(project, *names):
    defaults = project / "code" / "eldendisk" / "design" / "external_scripts" / "defaults"
    defaults.mkdir(parents=True, exist_ok=True)
    for n in names:
        (defaults / n).write_text("# a script\n")
    (defaults / "README.md").write_text("not a script")
    return defaults


def test_the_default_scripts_are_embedded_in_the_exe(project, monkeypatch):
    _defaults(project, "heartbeat.py", "_helper.py")
    ok, calls = build(monkeypatch)
    adds = [c for c in calls[0] if c.startswith("--add-data=")]
    assert ok and len(adds) == 4 and any(a.endswith(("heartbeat.py;external-scripts", "heartbeat.py:external-scripts")) for a in adds)
    assert not any("_helper" in a or "README" in a for a in adds)


def test_nuitka_embeds_the_scripts_in_the_same_folder(project, monkeypatch):
    _defaults(project, "heartbeat.py")
    ok, calls = build(monkeypatch, engine="nuitka")
    assert any(c.endswith("=external-scripts/heartbeat.py") for c in calls[0] if c.startswith("--include-data-files="))


def test_without_embedding_the_scripts_go_next_to_the_exe(project, monkeypatch):
    _defaults(project, "heartbeat.py")
    ok, _calls = build(monkeypatch, embed=False)
    assert ok and (project / "build" / "dist" / "external-scripts" / "heartbeat.py").is_file()


def test_no_scripts_no_folder_embedded(project, monkeypatch):
    ok, calls = build(monkeypatch)
    assert ok and not any("external-scripts" in c for c in calls[0])

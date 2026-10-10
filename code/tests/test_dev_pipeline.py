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
    assert "offsets.json, chr_state_ids.json, extension.json embedded in the exe" in text
    assert dev_pipeline._sha256(exe) in text and dev_pipeline.__version__ in text
    assert "build\\dist\\eldendisk.exe run -v" in text and "EldenDisk" in text
    assert "skipped" in "\n".join(dev_pipeline.status_lines(layout=layout, engine="nuitka", embed=False, configs=[],
                                                          tests_s=None, build_s=1.0, total_s=1.0))


def test_the_build_always_cleans_and_embeds_unless_told_not_to(monkeypatch, tmp_path):
    got = []
    monkeypatch.setattr(dev_pipeline, "run_precheck", lambda: True)
    monkeypatch.setattr(dev_pipeline, "run_build", lambda **kw: got.append(kw) or False)
    dev_pipeline.main([])
    dev_pipeline.main(["--no-embed", "--engine", "nuitka"])
    assert got == [dict(clean=True, embed=True, engine="pyinstaller", icon=None),
                   dict(clean=True, embed=False, engine="nuitka", icon=None)]


# ---------- the build itself (the compiler is faked) ----------
@pytest.fixture
def project(tmp_path, monkeypatch):
    code = tmp_path / "code"
    (code / "eldendisk").mkdir(parents=True)
    (code / "offsets.json").write_text("{}")
    (code / "chr_state_ids.json").write_text("{}")
    (code / "eldendisk" / "__main__.py").write_text("")
    (code / "extension.json").write_text('{"innovate_items": {"spells": {"maximum": 1, "slots": {"<id-1>": null}}}}')
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
    assert any(a.endswith("extension.json;.") or a.endswith("extension.json:.") for a in adds)
    assert not (project / "build" / "dist" / "offsets.json").exists()          # embedded: nothing copied


def test_nuitka_embeds_and_names_the_exe(project, monkeypatch):
    ok, calls = build(monkeypatch, engine="nuitka")
    inc = [c for c in calls[0] if c.startswith("--include-data-files=")]
    assert ok and len(inc) == 3 and inc[0].endswith("=offsets.json") and inc[-1].endswith("=extension.json")
    assert "--output-filename=eldendisk.exe" in calls[0] and f"--output-dir={project / 'build' / 'dist'}" in calls[0]


@pytest.mark.parametrize("engine", ["pyinstaller", "nuitka"])
def test_without_embedding_the_editable_configs_go_next_to_the_exe(project, monkeypatch, engine):
    ok, calls = build(monkeypatch, embed=False, engine=engine)
    out = project / "build" / "dist"
    assert ok and (out / "offsets.json").exists() and (out / "chr_state_ids.json").exists() and (out / "extension.json").exists()
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

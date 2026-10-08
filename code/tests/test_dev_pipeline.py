import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import dev_pipeline  # noqa: E402


@pytest.fixture
def steps(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(dev_pipeline, "run_precheck", lambda: calls.append("tests") or True)
    monkeypatch.setattr(dev_pipeline, "run_build", lambda clean=True, embed=True: calls.append("build") or True)
    monkeypatch.setattr(dev_pipeline, "_run_exe", lambda cmd, **kw: calls.append(cmd) or 0)
    exe = tmp_path / "build" / "dist" / "eldendisk" / "eldendisk.exe"
    exe.parent.mkdir(parents=True)
    exe.touch()
    monkeypatch.setattr(dev_pipeline, "ROOT_DIR", tmp_path)
    return calls


def exe_cmds(calls):
    return [c[1:] for c in calls if isinstance(c, list)]


def test_unknown_options_go_to_run(steps):
    assert dev_pipeline.main(["--vault-off", "--keep", "1"]) == 0
    assert steps[:2] == ["tests", "build"]
    assert exe_cmds(steps) == [["run", "-v", "--vault-off", "--keep", "1"]]


def test_own_options_are_not_forwarded(steps):
    assert dev_pipeline.main(["--skip-tests", "--no-embed", "--vault-on"]) == 0
    assert "tests" not in steps
    assert exe_cmds(steps) == [["run", "-v", "--vault-on"]]


def test_the_extension_is_built_by_run_itself_not_by_a_step_of_its_own(steps):
    assert dev_pipeline.main([]) == 0
    assert exe_cmds(steps) == [["run", "-v"]]


def test_dry_run_only_asks_for_help(steps):
    assert dev_pipeline.main(["--dry-run", "--vault-off"]) == 0
    assert exe_cmds(steps) == [["--help"]]


def test_bad_run_options_stop_before_tests_and_build(steps, capsys):
    assert dev_pipeline.main(["--vault-off", "--vault-on"]) == 2
    assert dev_pipeline.main(["--no-such-flag"]) == 2
    assert steps == []
    assert "usage" in capsys.readouterr().err


def test_extension_options_go_to_run(steps, tmp_path):
    other = str(tmp_path / "other")
    assert dev_pipeline.main(["--extension-dir", other, "--spec", "x.json"]) == 0
    assert exe_cmds(steps) == [["run", "-v", "--extension-dir", other, "--spec", "x.json"]]

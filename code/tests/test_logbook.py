"""logcat-style log: format, levels, rotation, resilience."""
import re

import eldendisk.logbook as lb
from eldendisk.logbook import Logbook, format_line


def lines(path):
    return path.read_text(encoding="utf-8").splitlines()


def test_line_format_is_logcat_like(tmp_path):
    b = Logbook()
    b.configure(file=tmp_path / "x.log")
    b.i("host", "game running")
    b.close()
    assert re.fullmatch(r"\d\d-\d\d \d\d:\d\d:\d\d\.\d{3} +\d+ I host  : game running", lines(tmp_path / "x.log")[0])


def test_the_file_gets_every_level_and_the_console_gets_the_events(tmp_path):
    b, seen = Logbook(), []
    b.configure(file=tmp_path / "x.log", console=seen.append)
    for fn, lvl in ((b.v, "V"), (b.d, "D"), (b.i, "I"), (b.ok, "I"), (b.w, "W"), (b.e, "E")):
        fn("t", "m")
    b.close()
    assert [l.split()[3] for l in lines(tmp_path / "x.log")] == list("VDIIWE")
    assert [e.level for e in seen] == list("VDIIWE") and [e.ok for e in seen] == [False] * 3 + [True] + [False] * 2


def test_a_multiline_message_becomes_one_event_per_line(tmp_path):
    b = Logbook()
    b.configure(file=tmp_path / "x.log")
    b.i("t", "a\nb")
    b.close()
    assert len(lines(tmp_path / "x.log")) == 2


def test_the_file_is_appended_not_overwritten(tmp_path):
    for _ in range(2):
        b = Logbook()
        b.configure(file=tmp_path / "x.log")
        b.i("t", "run")
        b.close()
    assert len(lines(tmp_path / "x.log")) == 2


def test_rotation_keeps_three_files_and_loses_nothing_recent(tmp_path, monkeypatch):
    monkeypatch.setattr(lb, "MAX_BYTES", 400)
    b = Logbook()
    b.configure(file=tmp_path / "x.log")
    for n in range(60):
        b.i("t", f"event {n:03d}")
    b.close()
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["x.log", "x.log.1", "x.log.2"]
    assert "event 059" in (tmp_path / "x.log").read_text() and all((tmp_path / n).stat().st_size <= 450 for n in names)


def test_an_unwritable_log_file_never_breaks_the_tool(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    b, seen = Logbook(), []
    b.configure(file=blocker / "sub" / "x.log", console=seen.append)   # parent is a file: cannot be created
    b.i("t", "still works")
    assert len(seen) == 1 and b.path is None


def test_a_failing_console_sink_is_dropped(tmp_path):
    b = Logbook()
    def boom(e): raise RuntimeError("x")
    b.configure(file=tmp_path / "x.log", console=boom)
    b.i("t", "one"); b.i("t", "two")
    b.close()
    assert len(lines(tmp_path / "x.log")) == 2


def test_unknown_levels_become_info():
    b, seen = Logbook(), []
    b.configure(console=seen.append)
    b.emit("?", "t", "m")
    assert seen[0].level == "I"
    assert "I t" in format_line(seen[0])

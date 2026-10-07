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


# ---- several terminals, one file ----
def line_of(pid, level, tag, msg):
    from datetime import datetime
    from eldendisk.logbook import Event
    return format_line(Event(datetime(2026, 10, 7, 13, 53, 7, 306000), pid, level, tag, msg))


def test_parse_line():
    assert lb.parse_line(line_of(14004, "D", "cli", "x")) == (14004, "D")
    assert lb.parse_line("not a log line") is None


def test_tail_shows_other_processes_from_the_end_of_the_file_and_not_its_own(tmp_path):
    path, got = tmp_path / "x.log", []
    path.write_text(line_of(1, "D", "cli", "history") + "\n", encoding="utf-8")
    t = lb.Tail(path, got.append, own_pid=100, poll=0.01)
    t.start()
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line_of(200, "D", "cli", "eldendisk 1.6.2 read --live") + "\n")
        fh.write(line_of(100, "I", "host", "mine") + "\n")
        fh.write(line_of(300, "I", "write", "level = 150") + "\n")
    t.stop()
    assert [l.split(" : ")[-1] for l in got] == ["eldendisk 1.6.2 read --live", "level = 150"]


def test_tail_waits_for_the_end_of_a_line_and_survives_a_rotation(tmp_path):
    path, got = tmp_path / "x.log", []
    path.write_text("", encoding="utf-8")
    t = lb.Tail(path, got.append, own_pid=1, poll=10)   # polled by hand
    t.start()
    whole = line_of(2, "I", "read", "attached")
    with open(path, "ab") as fh:
        fh.write(whole[:20].encode())
    t.poll_once()
    assert got == []                                  # half a line is not shown
    with open(path, "ab") as fh:
        fh.write((whole[20:] + "\n").encode())
    t.poll_once()
    assert got == [whole]
    fresh = tmp_path / "new.log"                      # rotation: a different, even bigger, file takes the name
    fresh.write_text(line_of(3, "E", "read", "after rotation, longer than before") + "\n" + whole + "\n", encoding="utf-8")
    lb.os.replace(fresh, path)
    t.poll_once()
    assert got[-2].endswith("after rotation, longer than before")
    path.write_text(line_of(4, "W", "read", "emptied") + "\n", encoding="utf-8")   # the same file, smaller
    t.poll_once()
    assert got[-1].endswith("emptied")
    t.stop()


def test_a_log_another_process_holds_is_not_rotated_but_keeps_working(tmp_path, monkeypatch):
    monkeypatch.setattr(lb, "MAX_BYTES", 300)
    real = lb.os.replace
    monkeypatch.setattr(lb.os, "replace", lambda a, b: (_ for _ in ()).throw(PermissionError("in use")))
    b = Logbook()
    b.configure(file=tmp_path / "x.log")
    for n in range(30):
        b.i("t", f"event {n:03d}")
    b.close()
    monkeypatch.setattr(lb.os, "replace", real)
    text = (tmp_path / "x.log").read_text()
    assert "event 000" in text and "event 029" in text

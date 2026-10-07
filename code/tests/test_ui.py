"""Console layout: concise lines, symbols with ASCII fallback, colour switches, `-v` raw view."""
import io
from datetime import datetime

import pytest

from eldendisk import ui
from eldendisk.logbook import Event, Logbook

WHEN = datetime(2026, 10, 7, 23, 41, 2, 123000)


def ev(level="I", tag="vault", msg="snapshot ready", ok=False):
    return Event(WHEN, 4242, level, tag, msg, ok)


class Stream(io.StringIO):
    encoding = "utf-8"

    def isatty(self):
        return False


@pytest.fixture
def err(monkeypatch):
    buf = Stream()
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    return buf


def test_pretty_line_with_time_symbol_and_tag(err):
    ui.pretty_sink(show_time=True, stream=err)(ev(ok=True))
    assert err.getvalue() == " 23:41:02  \u2713  vault  snapshot ready\n"


def test_short_commands_have_no_time_column(err):
    ui.pretty_sink(stream=err)(ev(level="E", tag="write", msg="not applied"))
    assert err.getvalue() == " \u2716  write  not applied\n"


def test_debug_and_verbose_events_are_hidden_in_the_concise_view(err):
    sink = ui.pretty_sink(stream=err)
    sink(ev(level="D")); sink(ev(level="V"))
    assert err.getvalue() == ""


def test_symbols_fall_back_to_ascii_on_legacy_code_pages(err):
    err.encoding = "cp874"
    sink = ui.pretty_sink(stream=err)
    sink(ev(ok=True)); sink(ev(level="W")); sink(ev(level="E")); sink(ev())
    assert [l.split()[0] for l in err.getvalue().splitlines()] == ["+", "!", "x", "-"]


def test_colour_only_when_asked_and_never_with_no_color(err, monkeypatch):
    ui.pretty_sink(stream=err)(ev(level="E"))
    assert "\x1b[" not in err.getvalue()               # not a terminal
    monkeypatch.setenv("FORCE_COLOR", "1")
    ui.pretty_sink(stream=err)(ev(level="E"))
    assert "\x1b[31m" in err.getvalue()                 # errors in red
    err.truncate(0); err.seek(0)
    monkeypatch.setenv("NO_COLOR", "1")
    ui.pretty_sink(stream=err)(ev(level="E"))
    assert "\x1b[" not in err.getvalue()


def test_raw_view_prints_the_log_lines_including_debug(err):
    ui.raw_sink(err)(ev(level="D", msg="state PREFLIGHT"))
    line = err.getvalue()
    assert line.startswith("10-07 23:41:02.123  4242 D vault : state PREFLIGHT")


def test_header_shows_title_rule_and_aligned_rows(err):
    ui.header("run", [("vault", "C:\\v"), ("game", "D:\\g")], stream=err)
    out = err.getvalue().splitlines()
    assert out[0].startswith(" Elden-Disk ") and out[0].endswith("\u00b7 run")
    assert set(out[1].strip()) == {"\u2500"} and out[2] == "   vault  C:\\v" and out[3] == "   game   D:\\g"


def test_the_logbook_drives_the_sink(err, tmp_path):
    b = Logbook()
    b.configure(file=tmp_path / "x.log", console=ui.pretty_sink(stream=err))
    b.d("host", "state PREFLIGHT"); b.ok("host", "session ended")
    assert err.getvalue().count("\n") == 1 and "session ended" in err.getvalue()
    assert len((tmp_path / "x.log").read_text().splitlines()) == 2   # the file keeps the debug event


# ---- tree lines and the in-place screen ----
from eldendisk.reader.view import Row

TREE = [Row(0, "character", None, "character"), Row(1, "level", "386", "character.level"),
        Row(1, "hp", "1,914", "character.hp"), Row(0, "sha", "x" * 90, "sha")]


def test_format_rows_aligns_highlights_and_cuts_to_the_window():
    plain = ui.format_rows(TREE, color=False)
    assert plain[0] == " character" and plain[1].startswith("   level  ") and plain[2].startswith("   hp     ")
    marked = ui.format_rows(TREE, color=True, hot={"character.level"})
    assert "\x1b[1;33m386\x1b[0m" in marked[1] and "\x1b[1;33m" not in marked[2]
    cut = ui.format_rows(TREE, columns=40)
    assert all(len(l) <= 39 for l in cut) and cut[3].endswith("…")


class Term(Stream):
    def isatty(self):
        return True


def test_screen_rewrites_in_place_and_clears_what_is_left(monkeypatch):
    monkeypatch.setattr(ui.shutil, "get_terminal_size", lambda fallback=None: __import__("os").terminal_size((80, 30)))
    t = Term()
    s = ui.Screen(t)
    s.show(["a", "b", "c"])
    assert t.getvalue() == "\x1b[?25l\x1b[2Ka\n\x1b[2Kb\n\x1b[2Kc\n"
    t.truncate(0), t.seek(0)
    s.show(["a2", "b2"])
    assert t.getvalue() == "\x1b[3A\r\x1b[2Ka2\n\x1b[2Kb2\n\x1b[2K\n\x1b[1A"
    s.close()
    assert t.getvalue().endswith("\x1b[?25h")


def test_screen_shows_no_more_lines_than_fit_the_window(monkeypatch):
    monkeypatch.setattr(ui.shutil, "get_terminal_size", lambda fallback=None: __import__("os").terminal_size((80, 6)))
    t = Term()
    s = ui.Screen(t)
    s.show([f"line {i}" for i in range(20)])
    out = t.getvalue()
    assert out.count("\n") == 5 and "line 3" in out and "line 4" not in out and "16 more lines" in out
    assert s.height == 5


def test_screen_detach_starts_a_new_block_below(monkeypatch):
    monkeypatch.setattr(ui.shutil, "get_terminal_size", lambda fallback=None: __import__("os").terminal_size((80, 30)))
    t = Term()
    s = ui.Screen(t)
    s.show(["a"])
    s.detach()
    t.truncate(0), t.seek(0)
    s.show(["b"])
    assert "A" not in t.getvalue().replace("\x1b[2K", "")


def test_can_redraw_needs_a_terminal(monkeypatch):
    monkeypatch.setenv("TERM", "xterm")
    assert not ui.can_redraw(Stream())
    monkeypatch.setattr(ui, "_enable_windows_ansi", lambda s: True)
    assert ui.can_redraw(Term())
    monkeypatch.setenv("TERM", "dumb")
    assert not ui.can_redraw(Term())


def test_countdowns_have_their_own_colour_and_a_change_still_wins():
    from eldendisk.ui import format_rows
    from eldendisk.reader.view import Row
    rows = [Row(0, "buff_duration", "44.90", "a.buff_duration"), Row(0, "max_duration", "80.00", "a.max_duration"),
            Row(0, "level", "150", "character.level")]
    out = format_rows(rows, color=True, ticking=frozenset({"a.buff_duration"}), hot=frozenset({"character.level"}))
    assert "\x1b[35m44.90\x1b[0m" in out[0]                  # the countdown
    assert "\x1b[" not in out[1].split("  ", 1)[1]            # a constant next to it is plain
    assert "\x1b[1;33m150\x1b[0m" in out[2]
    both = format_rows(rows[:1], color=True, ticking=frozenset({"a.buff_duration"}), hot=frozenset({"a.buff_duration"}))
    assert "\x1b[1;33m44.90" in both[0] and "\x1b[35m" not in both[0]
    assert "\x1b[" not in format_rows(rows, color=False, ticking=frozenset({"a.buff_duration"}))[0]

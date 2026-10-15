"""Console layout: concise lines, symbols with ASCII fallback, colour switches, `-v` raw view."""
import io
from datetime import datetime

import pytest

from eldendisk import ui
from eldendisk.logbook import CREATIVE_TAG, Event, Logbook, format_line

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
    assert err.getvalue() == " 23:41:02  \u2713  vault     snapshot ready\n"


def test_short_commands_have_no_time_column(err):
    ui.pretty_sink(stream=err)(ev(level="E", tag="write", msg="not applied"))
    assert err.getvalue() == " \u2716  write     not applied\n"


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
    assert line.startswith("10-07 23:41:02.123  4242 D vault    : state PREFLIGHT")


def test_raw_view_colours_the_command_line_only_on_the_console(err, monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    cmd = ev(level="D", tag="client", msg="run: eldendisk.exe run -v")
    ui.raw_sink(err)(cmd)
    out = err.getvalue()
    assert "run: \x1b[0m\x1b[36meldendisk.exe run -v\x1b[0m" in out and out.startswith("\x1b[2m10-07 23:41:02.123")   # prefix dim, command cyan
    assert "\x1b[" not in format_line(cmd)                                      # the log file line is plain
    err.truncate(0); err.seek(0)
    ui.raw_sink(err)(ev(level="D", tag="client", msg="exit 0"))
    ui.raw_sink(err)(ev(level="D", tag="client", msg="version 1.7.0"))
    ui.raw_sink(err)(ev(level="D", tag="client", msg="clickable paths off: output is not a terminal"))
    assert "\x1b[36m" not in err.getvalue()                                     # exit and version stay dim
    err.truncate(0); err.seek(0)
    ui.raw_line(format_line(cmd), err)                                         # a line tailed from another terminal
    assert "\x1b[36meldendisk.exe run -v" in err.getvalue()
    monkeypatch.setenv("NO_COLOR", "1")
    err.truncate(0); err.seek(0)
    ui.raw_sink(err)(cmd)
    assert "\x1b[" not in err.getvalue()


def test_backticked_words_are_cyan_on_a_colour_console_and_stay_plain_otherwise(err, monkeypatch):
    e = ev(tag="game", msg="running, pid 7; `read` allowed, `write` allowed")
    ui.pretty_sink(stream=err)(e)
    assert "`read`" in err.getvalue() and "\x1b[" not in err.getvalue()
    monkeypatch.setenv("FORCE_COLOR", "1")
    err.truncate(0); err.seek(0)
    ui.pretty_sink(stream=err)(e)
    out = err.getvalue()
    assert "\x1b[36mread\x1b[0m allowed, \x1b[36mwrite\x1b[0m allowed" in out and "`" not in out
    err.truncate(0); err.seek(0)
    ui.raw_sink(err)(e)
    assert "\x1b[36mwrite\x1b[0m" in err.getvalue()
    assert "`write`" in format_line(e)                       # the log file keeps the backticks


ORANGE = "\x1b[38;5;208m{}\x1b[0m"


def test_a_bare_file_name_is_orange(err, monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    ui.pretty_sink(stream=err)(ev(msg="regulation.bin restored, byte-identical to the game's own file"))
    assert err.getvalue().count(ORANGE.format("regulation.bin")) == 1


def test_the_file_name_at_the_end_of_a_path_is_orange_and_the_folders_are_not(err, monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    ui.pretty_sink(stream=err)(ev(tag=CREATIVE_TAG, msg="building x on D:\\SteamLibrary\\ELDEN RING\\Game\\regulation.bin and checking"))
    assert "D:\\SteamLibrary\\ELDEN RING\\Game\\" + ORANGE.format("regulation.bin") + " and checking" in err.getvalue()
    err.truncate(0); err.seek(0)
    ui.pretty_sink(stream=err)(ev(msg="folder C:\\Users\\x\\EldenDisk\\vault and C:\\a\\b.v2"))
    assert "\x1b[38;5;208m" not in err.getvalue()


def test_a_clickable_path_keeps_a_clean_url_and_colours_only_the_visible_name(monkeypatch):
    monkeypatch.setenv("ELDENDISK_LINKS", "1")
    out = ui.linkify("on D:\\SteamLibrary\\ELDEN RING\\Game\\regulation.bin ok", exists=lambda p: p.endswith("regulation.bin"), color=True)
    assert "file:///D:/SteamLibrary/ELDEN%20RING/Game/regulation.bin\x1b\\" in out and "\x1b[38;5;208m" not in out.split("\x1b\\")[0]
    assert "Game\\" + ORANGE.format("regulation.bin") + "\x1b]8;;\x1b\\ ok" in out
    assert ui.linkify("D:\\g\\regulation.bin", exists=lambda p: True).count("\x1b[38;5;208m") == 0      # no colour asked: unchanged


def test_a_warning_stays_yellow_around_an_orange_file_name(err, monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    ui.pretty_sink(stream=err)(ev(level="W", msg="`ER0000.sl2` is odd in D:\\s\\ER0000.sl2 today"))
    out = err.getvalue()
    assert "`ER0000.sl2` is odd" in out                      # a warning keeps its backticks, as before
    assert out.count("\x1b[38;5;208m") == 1 and "\x1b[0m\x1b[33m today\x1b[0m" in out


def test_a_debug_line_stays_dim_around_an_orange_file_name(err, monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    ui.raw_sink(err)(ev(level="D", tag="config", msg="regulation: C:\\x\\regulation.bin replaces regulation.bin"))
    out = err.getvalue()
    assert out.count("\x1b[38;5;208m") == 2 and out.count("\x1b[0m\x1b[2m") == 2


@pytest.mark.parametrize("name", ["regulation.bin", "ER0000.err", "ER0000.err.bak", "ER0000.sl2", "ER0000.sl2.bak", "steam_autocloud.vdf",
                                  "spells.commit.json", "eldendisk.exe", "eldendisk.log"])
def test_every_file_name_with_an_extension_is_orange_with_or_without_backticks(err, monkeypatch, name):
    monkeypatch.setenv("FORCE_COLOR", "1")
    sink = ui.pretty_sink(stream=err)
    sink(ev(msg="saved %s, then `%s` again." % (name, name)))
    out = err.getvalue()
    assert out.count(ORANGE.format(name)) == 2 and "`" not in out and "\x1b[36m" not in out


def test_things_that_only_look_like_files_are_left_alone(err, monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    ui.pretty_sink(stream=err)(ev(msg="version 1.7.0 on Python 3.14.5, black_flame_copy.shop.price 1.5 -> 2.5, e.g. ok. file.docx x.bin2"))
    assert "\x1b[38;5;208m" not in err.getvalue()


def test_other_backticked_words_stay_cyan_and_the_log_file_keeps_the_backticks(err, monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    e = ev(msg="`write` allowed, `ER0000.sl2` restored")
    ui.pretty_sink(stream=err)(e)
    out = err.getvalue()
    assert "\x1b[36mwrite\x1b[0m" in out and ORANGE.format("ER0000.sl2") in out
    assert "`ER0000.sl2`" in format_line(e)


def test_the_raw_view_colours_file_names_too(err, monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    ui.raw_sink(err)(ev(msg="restored ER0000.sl2.bak"))
    assert ORANGE.format("ER0000.sl2.bak") in err.getvalue()


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


# ---- clickable paths (OSC 8) ----
GAME = r"D:\SteamLibrary\steamapps\common\ELDEN RING\Game\regulation.bin"
LINK = "\x1b]8;;file:///D:/SteamLibrary/steamapps/common/ELDEN%20RING/Game/regulation.bin\x1b\\" + GAME + "\x1b]8;;\x1b\\"


def test_an_existing_path_with_spaces_becomes_one_link_and_the_text_after_it_stays():
    got = ui.linkify(f"backed up {GAME} (sha256 766521f9508d)", exists=lambda p: p == GAME)
    assert got == f"backed up {LINK} (sha256 766521f9508d)"


def test_a_path_that_does_not_exist_is_left_alone_and_so_is_trailing_punctuation():
    assert ui.linkify(f"see {GAME}", exists=lambda p: False) == f"see {GAME}"
    assert ui.linkify(f"({GAME}).", exists=lambda p: p == GAME).endswith(").")
    assert ui.linkify("no path here, only 12:30", exists=lambda p: True) == "no path here, only 12:30"


def test_colour_codes_after_a_path_are_not_swallowed():
    got = ui.linkify(f"\x1b[33mfile {GAME}\x1b[0m", exists=lambda p: p == GAME)
    assert got == f"\x1b[33mfile {LINK}\x1b[0m"


def test_two_paths_in_one_line_are_both_linked():
    a, b = r"C:\a\x.bin", r"C:\b\y.bin"
    got = ui.linkify(f"{a} -> {b}", exists=lambda p: p in (a, b))
    assert got.count("\x1b]8;;file:///") == 2 and got.count("\x1b]8;;\x1b\\") == 2


class Tty(Stream):
    def isatty(self):
        return True


@pytest.fixture
def clean_env(monkeypatch):
    for k in ("ELDENDISK_LINKS", "NO_COLOR", "FORCE_COLOR", "WT_SESSION", "VTE_VERSION", "KITTY_WINDOW_ID", "WEZTERM_EXECUTABLE", "TERM_PROGRAM"):
        monkeypatch.delenv(k, raising=False)


def test_links_only_in_a_terminal_known_to_understand_them(clean_env, monkeypatch):
    assert not ui.use_links(Tty())                                   # a tty we know nothing about
    monkeypatch.setenv("WT_SESSION", "x")
    assert ui.use_links(Tty()) and not ui.use_links(Stream())        # Windows Terminal, but not a pipe or a file
    monkeypatch.setenv("NO_COLOR", "1")
    assert not ui.use_links(Tty())
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setenv("ELDENDISK_LINKS", "0")
    assert not ui.use_links(Tty())


def test_links_status_says_why(clean_env, monkeypatch):
    assert ui.links_status(Stream()) == (False, "output is not a terminal")
    assert ui.links_status(Tty())[0] is False and "ELDENDISK_LINKS=1" in ui.links_status(Tty())[1]
    monkeypatch.setenv("WT_SESSION", "x")
    assert ui.links_status(Tty()) == (True, "WT_SESSION is set")
    monkeypatch.setenv("ELDENDISK_LINKS", "0")
    assert ui.links_status(Tty()) == (False, "ELDENDISK_LINKS=0")


def test_the_switch_can_force_links_on_and_ide_run_windows_do_not_get_them_by_themselves(clean_env, monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert not ui.use_links(Stream())                                # colour yes, links no
    monkeypatch.setenv("ELDENDISK_LINKS", "1")
    assert ui.use_links(Stream())


def test_emit_links_real_paths_and_a_log_line_stays_plain(clean_env, monkeypatch):
    monkeypatch.setenv("ELDENDISK_LINKS", "1")
    monkeypatch.setattr(ui.os.path, "exists", lambda p: p == GAME)
    out = Stream()
    ui._emit(f"x {GAME}", out)
    assert "\x1b]8;;file:///D:/" in out.getvalue()
    assert "\x1b" not in format_line(ev(msg=f"x {GAME}"))            # the log file never gets escapes


# ---- spell ids in purple (lines of the `ext` tag) ----
PURPLE = "\x1b[35m{}\x1b[0m"


@pytest.fixture
def spells(monkeypatch):
    ui.mark_spell_ids(["reverse_curse_technique", "black_flame_copy"])
    yield
    ui.mark_spell_ids([])


def colour(monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)


def test_spell_ids_are_purple_in_an_ext_line(spells, monkeypatch):
    colour(monkeypatch)
    buf = Stream()
    ui.pretty_sink(stream=buf)(ev(tag=CREATIVE_TAG, msg="innovate-items spells: building reverse_curse_technique, black_flame_copy on D:\\x"))
    out = buf.getvalue()
    assert PURPLE.format("reverse_curse_technique") in out and PURPLE.format("black_flame_copy") in out


def test_a_diff_line_colours_only_the_id_part(spells, monkeypatch):
    colour(monkeypatch)
    buf = Stream()
    ui.pretty_sink(stream=buf)(ev(tag=CREATIVE_TAG, msg="  black_flame_copy.shop.price  1000 -> 2000"))
    assert PURPLE.format("black_flame_copy") + ".shop.price  " in buf.getvalue()           # the id of the spell is purple, the rest is not
    assert "[38;5;179m1000[0m -> [38;5;179m2000[0m" in buf.getvalue()      # numbers of 4 digits or more: their own colour


def test_other_tags_paths_and_longer_words_are_left_alone(spells, monkeypatch):
    colour(monkeypatch)
    buf = Stream()
    sink = ui.pretty_sink(stream=buf)
    sink(ev(tag="vault", msg="black_flame_copy"))
    sink(ev(tag=CREATIVE_TAG, msg="in D:\\x\\black_flame_copy\\a.json and black_flame_copy2 and my-black_flame_copy"))
    assert "\x1b[35m" not in buf.getvalue()


def test_no_colour_no_change_and_the_log_file_line_stays_plain(spells, monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    buf = Stream()
    ui.pretty_sink(stream=buf)(ev(tag=CREATIVE_TAG, msg="built black_flame_copy"))
    assert "\x1b" not in buf.getvalue() and "built black_flame_copy" in buf.getvalue()
    assert "\x1b" not in format_line(ev(tag=CREATIVE_TAG, msg="built black_flame_copy"))


def test_the_raw_view_colours_the_message_not_the_prefix(spells, monkeypatch):
    colour(monkeypatch)
    buf = Stream()
    ui.raw_sink(stream=buf)(ev(tag=CREATIVE_TAG, msg="building black_flame_copy"))
    line = buf.getvalue()
    assert line.startswith("10-07 23:41:02.123  4242 I creative : building ") and PURPLE.format("black_flame_copy") in line
    buf2 = Stream()
    ui.raw_line("10-07 23:41:02.123  4242 I creative : built black_flame_copy", buf2)
    assert PURPLE.format("black_flame_copy") in buf2.getvalue() and buf2.getvalue().startswith("10-07 23:41:02.123  4242 I creative : built ")


def test_an_error_stays_red_and_clearing_the_ids_stops_the_colour(spells, monkeypatch):
    colour(monkeypatch)
    buf = Stream()
    ui.pretty_sink(stream=buf)(ev(level="E", tag=CREATIVE_TAG, msg="black_flame_copy failed"))
    assert "\x1b[35m" not in buf.getvalue()
    ui.mark_spell_ids([])
    buf = Stream()
    ui.pretty_sink(stream=buf)(ev(tag=CREATIVE_TAG, msg="built black_flame_copy"))
    assert "\x1b[35m" not in buf.getvalue()


# ---- ids and addresses, and the block of `innovate-items spells` ----
ID, ADDR = "\x1b[38;5;179m{}\x1b[0m", "\x1b[38;5;75m{}\x1b[0m"


def test_ids_and_addresses_have_their_own_colours_and_nothing_else_does(monkeypatch):
    colour(monkeypatch)
    text = r"GoodsName: 114880 -> 114952 bytes, now at 0x7ff3cbbb0000 (20261012-185726, 10,008,626, ER0000.sl2, 23:41:02, 1.7.1, C:\x\2230000)"
    got = ui.paint_numbers(text, True)
    assert ID.format("114880") in got and ID.format("114952") in got and ADDR.format("0x7ff3cbbb0000") in got
    assert got.count("\x1b[38;5;") == 3                                     # three painted: not the date, the time, the version, the path
    assert ui.paint_numbers(text, False) == text


def test_a_colour_in_a_line_gets_a_square_of_that_colour_and_its_text_and_digits_stay_plain():
    """1.8.0: a small square in the colour (one cell, one colour: not an emoji); `#90D5FF` itself stays in the colour of its line."""
    got = ui.paint_numbers("main colour -> #90D5FF: 68 places in 524400; #900000", True, "\x1b[2m")
    assert "\x1b[22;38;2;144;213;255m\u25a0\x1b[0m\x1b[2m #90D5FF:" in got         # a bright square, then back to the dim line
    assert "\x1b[22;38;2;144;0;0m\u25a0\x1b[0m\x1b[2m #900000" in got and ID.format("900000") not in got
    assert ui.printable("\u25a0 #90D5FF", "cp874") == "# #90D5FF"                     # a legacy code page
    assert ID.format("524400") in got
    assert ui.paint_numbers("#90D5FF", False) == "#90D5FF" and ui.paint_hex("a#90D5FF, #90D5FFF, &#123456", True).count("38;2") == 0


def test_a_number_inside_a_warning_goes_back_to_the_colour_of_the_warning(monkeypatch):
    colour(monkeypatch)
    buf = Stream()
    ui.pretty_sink(stream=buf)(ev(level="W", tag="write", msg="the game moved 114880 bytes"))
    assert ID.format("114880") + "\x1b[33m" in buf.getvalue()


def test_the_raw_view_colours_the_message_and_not_the_pid(monkeypatch):
    colour(monkeypatch)
    buf = Stream()
    ui.raw_sink(stream=buf)(ev(level="D", tag="write", msg="table at 0x7ff3cbbb0000 is 114880 bytes"))
    out = buf.getvalue()
    assert ADDR.format("0x7ff3cbbb0000") in out and ID.format("114880") in out and ID.format("4242") not in out


def test_a_block_draws_the_lines_of_the_creative_tag_inside_it(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    err = Stream()
    sink = ui.pretty_sink(stream=err)
    clock = iter([0.0, 5.8])
    with ui.Block("design", stream=err, clock=lambda: next(clock)) as blk:
        sink(ev(tag=CREATIVE_TAG, msg="building because the design changed"))
        sink(ev(tag="vault", msg="other tag stays as it is"))
        blk.rows([("name", "Reverse"), ("game", "goods 2230000")])
        sink(ev(level="E", tag=CREATIVE_TAG, msg="  $.a.b: unknown field"))
        blk.close("regulation.bin written")
    lines = err.getvalue().splitlines()
    assert lines[0] == " \u256d\u2500 design"
    assert lines[1] == " \u2502  \u00b7  building because the design changed"
    assert lines[2].endswith("other tag stays as it is") and "\u2502" not in lines[2] and "vault" in lines[2]
    assert lines[3] == " \u2502    name  Reverse" and lines[4] == " \u2502    game  goods 2230000"
    assert lines[5].startswith(" \u2502  \u2716    $.a.b: unknown field")
    assert lines[6] == " \u2570\u2500 \u2713  regulation.bin written  (5.8 s)"
    sink(ev(tag=CREATIVE_TAG, msg="after the block"))
    assert "creative" in err.getvalue().splitlines()[-1] and "\u2502" not in err.getvalue().splitlines()[-1]


def test_a_block_that_is_not_active_draws_nothing_and_leaves_the_lines_alone(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    err = Stream()
    sink = ui.pretty_sink(stream=err)
    with ui.block("design", verbose=True, stream=err) as blk:
        blk.note("x")
        blk.rows([("a", "b")])
        sink(ev(tag=CREATIVE_TAG, msg="m"))
    assert err.getvalue().splitlines() == [" \u00b7  creative  m"]


def test_a_problem_of_the_design_has_its_place_in_cyan(monkeypatch):
    colour(monkeypatch)
    err = Stream()
    with ui.Block("design", stream=err):
        ui.pretty_sink(stream=err)(ev(level="E", tag=CREATIVE_TAG, msg="  $.innovate_items.spells.slots[x].customs.basic: unknown field"))
    assert "\x1b[36m$.innovate_items.spells.slots[x].customs.basic\x1b[0m\x1b[31m: unknown field" in err.getvalue()


def test_many_rows_go_out_in_chunks_exactly_as_one_line_each(capsys, monkeypatch):
    """1.8.0 part 4: a whole table of the game is millions of rows; they are written in chunks, the text unchanged."""
    from eldendisk.reader.view import Row
    monkeypatch.setattr(ui, "EMIT_CHUNK", 3)
    items = [Row(0, "params", None, "params")] + [Row(1, f"k{i}", str(i), f"params.k{i}") for i in range(7)]
    ui.rows(items)
    assert capsys.readouterr().out.splitlines() == ui.format_rows(items)

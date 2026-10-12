"""The look of a step that takes a while (ui.Working), the card of a spell, the tree of a diff, and the progress of the other processes
of a `run` (ui.child_line)."""
import io
import re
import time
from datetime import datetime

import pytest

from eldendisk import ui
from eldendisk.commands import extension as ext
from eldendisk.logbook import EXT_TAG, book, format_line


class Stream(io.StringIO):
    encoding = "utf-8"

    def isatty(self):
        return True


@pytest.fixture
def lines(monkeypatch):
    """Everything the log would show on the console, as plain lines."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    got = []
    book.configure(console=lambda e: got.append(f"{e.level}{'+' if e.ok else ' '}{e.tag}: {e.msg}"))
    yield got
    book.configure()


def test_without_animation_a_step_is_a_start_line_and_an_end_line_with_the_time(lines):
    with ui.working(EXT_TAG, "building", animate=False) as w:
        w.done("built")
    assert lines[0] == "I design: building" and re.fullmatch(r"I\+design: built  \(\d+\.\d s\)", lines[1])


def test_a_step_that_fails_leaves_no_end_line_and_no_status_line(lines):
    err = Stream()
    with pytest.raises(ValueError):
        with ui.working(EXT_TAG, "building", stream=err, animate=True):
            raise ValueError("boom")
    assert ui._live is None and lines == ["D design: building"]          # only the file line; no end line
    assert err.getvalue().endswith("\r\x1b[2K")                    # the status line is wiped


def test_the_status_line_spins_counts_the_seconds_and_lets_other_lines_through_above_it(lines, monkeypatch):
    err = Stream()
    clock = [0.0]
    with ui.working(EXT_TAG, "the long text goes to the log", short="building x", stream=err, animate=True, clock=lambda: clock[0],
                    interval=0.01) as w:
        clock[0] = 12.3
        time.sleep(0.05)
        ui._emit(" other line", err)                              # a line of another event while the step runs
        out = err.getvalue()
        assert "building x" in out and "12.3 s" in out
        i = out.index(" other line")
        assert out[:i].endswith("\r\x1b[2K") and out[i:].count("building x") >= 1      # wiped, the line, then the status line again
        w.done("built")
    assert ui._live is None and lines[0] == "D design: the long text goes to the log"      # the file has the long text; not on the console
    assert lines[-1].startswith("I+design: built  (12.3 s)")


def test_only_one_status_line_at_a_time(lines):
    err = Stream()
    with ui.working(EXT_TAG, "first", stream=err, animate=True):
        with ui.working(EXT_TAG, "second", stream=err, animate=True) as inner:
            assert not inner.animated
    assert ui._live is None


def test_the_spinner_uses_ascii_on_a_legacy_code_page(lines):
    err = Stream()
    err.encoding = "cp874"
    with ui.working(EXT_TAG, "building", stream=err, animate=True):
        pass
    assert "|" in err.getvalue() and "⠋" not in err.getvalue()


def test_a_card_shows_the_rows_and_has_an_ascii_fallback(monkeypatch):
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    err = Stream()
    ui.card("spell_a", [("name", "A"), ("cost", "FP 1")], err)
    assert err.getvalue().splitlines() == [" ╭ spell_a", " │ name  A", " │ cost  FP 1", " ╰"]
    err = Stream()
    err.encoding = "cp874"
    ui.card("spell_a", [("name", "A")], err)
    assert err.getvalue().splitlines() == [" + spell_a", " | name  A", " +"]


def test_the_diff_is_a_tree_and_says_how_many_more(lines, monkeypatch):
    ext._show_diff(["a  1 -> 2", "b  3 -> 4"])
    assert lines == ["I design:   ├─ a  1 -> 2", "I design:   └─ b  3 -> 4"]
    lines.clear()
    monkeypatch.setattr(ext, "MAX_DIFF_LINES", 1)
    ext._show_diff(["a  1 -> 2", "b  3 -> 4", "c  5 -> 6"])
    assert lines[0] == "I design:   ├─ a  1 -> 2" and lines[1].startswith("I design:   └─ … and 2 more")


def test_the_rows_of_a_spell_hold_only_what_the_design_says_in_its_own_words():
    sp = {"id": "x", "slot": 3, "text": {"goods_name": "X"}, "fp_cost": 90, "requires": {"faith": 15, "arcane": 0},
          "shop": {"price": 100, "stock": 1}, "flame_color": [0.2, 0.65, 1], "flame_accent_color": [0.55, 0.2, 1],
          "positive_curse_energy_eyes": {"on": "SpEffect.1", "color": [0.2, 0.65, 1]}}
    rows = dict(ext._facts(sp))
    assert rows == {"name": "X", "status": "faith 15", "cost": "focus point 90", "sold": "Kal\u00e9 \u00b7 100 runes, stock 1",
                    "fire": "\u25a0 0.2 0.65 1   accent \u25a0 0.55 0.2 1", "eyes": "\u25a0 0.2 0.65 1", "slot": "3"}
    assert dict(ext._facts({"id": "y", "slot": 1, "positive_curse_energy_eyes": {"on": "SpEffect.1"}})) == {"eyes": "the game's own", "slot": "1"}
    assert dict(ext._facts({"id": "y", "slot": 1})) == {"slot": "1"}


def test_the_rows_name_the_ids_the_game_really_uses_once_the_spell_is_built():
    rows = {"goods": 2230000, "magic": 2230000, "sp_effect": [21951000, 21951001], "bullet": [500000000], "atk": [], "shop": 100508}
    got = dict(ext._facts({"id": "x", "slot": 1}, rows))
    assert got["game"] == "goods 2230000 \u00b7 magic 2230000 \u00b7 SpEffect 21951000, 21951001 \u00b7 Bullet 500000000 \u00b7 shop line 100508"



def test_a_colour_swatch_is_a_square_in_the_colour_of_the_design(monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert ui.swatch([0.2, 0.65, 2], True) == "\x1b[38;2;51;166;255m\u25a0\x1b[0m"           # above 1 is shown as the full colour
    assert ui.swatch([0.2, 0.65, 1], False) == "\u25a0"


# ---- the progress of the other processes of a run ----
def line(level, tag, msg):
    return format_line(ui.Event(datetime(2026, 10, 12, 1, 2, 3), 4242, level, tag, msg))


def test_a_child_step_shows_its_progress_and_marks_what_it_finished():
    err = Stream()
    ui.child_line(line("I", "write", "goods text: waiting for a character to be in the world"), err)
    ui.child_line(line("I", "write", f"goods text: 1 spell named in the game; {ui.CHILD_DONE}"), err)
    ui.child_line(line("W", "write", "goods text: slow"), err)
    ui.child_line(line("D", "write", "goods text: looked for the tables"), err)           # debug stays in the file
    ui.child_line(line("I", "vault", "something else"), err)                        # so does every other tag
    ui.child_line("not a log line", err)
    assert err.getvalue().splitlines() == [" 01:02:03  ·  write     goods text: waiting for a character to be in the world",
                                           f" 01:02:03  ✓  write     goods text: 1 spell named in the game; {ui.CHILD_DONE}",
                                           " 01:02:03  !  write     goods text: slow"]


def test_the_closing_words_are_what_both_write_steps_really_say():
    from pathlib import Path
    src = (Path(ui.__file__).parent / "commands" / "write.py").read_text(encoding="utf-8")
    assert src.count(ui.CHILD_DONE) == 4             # the text step, the fire, the ring and the eyes: if one is reworded the check mark is lost

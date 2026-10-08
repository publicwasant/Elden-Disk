"""The id ledger behind --live-buffs / --live-animations, and the monitors' lines."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from eldendisk import ui
from eldendisk.game.profile import StateConfig, StateIds
from eldendisk.reader.animations import AnimationsMonitor
from eldendisk.reader.buffs import BuffsMonitor
from eldendisk.reader.ledger import HOLD_S, SETTLE_S, Ledger, Line, stamp

T0 = datetime(2026, 10, 7, 4, 6, 12, 750218, tzinfo=timezone(timedelta(hours=7)))


def at(sec):
    return T0 + timedelta(seconds=sec)


def test_stamp_is_human_readable():
    assert stamp(T0) == "04:06:12.750"


def test_an_id_is_one_row_however_often_it_comes_back():
    led = Ledger()
    assert [(k, e.id) for k, e in led.update({5: None}, at(0))] == [("+", 5)]
    assert led.update({5: None}, at(0.1)) == []                       # still there: no event
    assert [(k, e.id) for k, e in led.update({}, at(2))] == [("-", 5)]
    assert [(k, e.id) for k, e in led.update({5: None}, at(3))] == [("+", 5)]
    assert len(led.entries) == 1


def test_an_id_that_flips_every_frame_does_not_blink():
    led = Ledger()
    events = []
    for i in range(20):   # 2020110 and 2022100 alternate every 16 ms
        events += led.update({2020110 if i % 2 == 0 else 2022100: None}, at(i * 0.016))
    assert sorted(k + str(e.id) for k, e in events) == ["+2020110", "+2022100"]      # two appearances, no disappearances
    assert all(e.active for e in led.entries.values())
    events = led.update({}, at(20 * 0.016 + SETTLE_S + 0.01))
    assert sorted(e.id for _, e in events) == [2020110, 2022100] and all(k == "-" for k, _ in events)


def test_order_is_active_first_then_latest_and_steady_within_a_second():
    led = Ledger()
    led.update({1: None}, at(0))
    led.update({2: None}, at(5))               # 1 is gone for good
    led.update({2: None, 3: None}, at(10))
    led.update({2: None, 3: None, 4: None}, at(10.2))
    assert [e.id for e in led.ordered()] == [3, 4, 2, 1]    # newest activation (second 10) first, 2 (second 5) next
    led.update({3: None, 4: None}, at(12))
    assert [e.id for e in led.ordered()] == [3, 4, 2, 1]    # 3 and 4 are active (3 came a moment first, same second)
    led.update({4: None}, at(13))
    assert [e.id for e in led.ordered()] == [4, 3, 2, 1]    # 3 left at 12, 2 at 10, 1 at 0


def test_the_highlight_lasts_a_second_after_a_change():
    led = Ledger()
    (_, e), = led.update({1: None}, at(0))
    assert led.is_hot(e, at(HOLD_S - 0.01)) and not led.is_hot(e, at(HOLD_S + 0.01))


def table():
    return StateIds(buffs={100: StateConfig("Golden Vow")},
                    animations={2020110: StateConfig("Running"), 300: StateConfig("An animation id")})


class Fake(SimpleNamespace):
    pass


def monitor(cls, out, **kw):
    sampler = Fake(state_ids=table(), profile=Fake(sp_effect=Fake(entry=Fake(timer_mode="remaining"))))
    return cls(sampler, out, now=lambda: monitor.clock[0], **kw), sampler


monitor.clock = [T0]


def test_animation_monitor_names_known_ids_and_marks_the_rest_unknown():
    got = []
    m, sampler = monitor(AnimationsMonitor, got.append)
    sampler.locate_player = lambda: (1, None)
    for aid in (2020110, 7):
        sampler.read_animation_id = lambda p, a=aid: a
        m.tick()
    assert got[0].startswith("+   2020110  Running") and got[0].endswith("04:06:12.750")
    assert got[1].startswith("+         7  Unknown")
    assert [l.name for l in m.lines(T0)] == ["Running", None] or [l.name for l in m.lines(T0)] == [None, "Running"]
    assert m.summary() == "2 active · 2 seen · 1 unmapped"


def test_an_animation_id_of_zero_changes_nothing():
    got = []
    m, sampler = monitor(AnimationsMonitor, got.append)
    sampler.locate_player = lambda: (1, None)
    sampler.read_animation_id = lambda p: 0
    m.tick()
    assert got == [] and m.ledger.entries == {} and m.waiting is None


def test_waiting_is_said_once_and_kept_for_the_table():
    got = []
    m, sampler = monitor(AnimationsMonitor, got.append)
    sampler.locate_player = lambda: (None, "no player")
    m.tick(), m.tick()
    assert got == ["[waiting] no player"] and m.waiting == "no player"


def test_buffs_monitor_shows_timer_and_treats_animation_rows_as_unmapped():
    got = []
    m, sampler = monitor(BuffsMonitor, got.append)
    sampler.raw_buffs = lambda: ([(100, 80.0, 45.0), (200, -1.0, 0.0), (300, 10.0, 5.0)], None)
    m.tick()
    assert "45.0 / 80.0 s" in got[0] and "permanent" in got[1] and "Unknown" in got[2]
    assert m.summary() == "3 active · 3 seen · 2 unmapped"
    m.show = "unmapped"
    assert [l.id for l in m.lines(T0)] == [200, 300] and m.summary().endswith("showing unmapped")


def test_quiet_hides_short_internal_buffs():
    got = []
    m, sampler = monitor(BuffsMonitor, got.append, quiet=True)
    sampler.raw_buffs = lambda: ([(1, 0.5, 0.2), (2, 5.0, 2.0), (3, -1.0, 0.0)], None)
    m.tick()
    assert sorted(e for e in m.ledger.entries) == [2, 3]


def test_the_table_draws_a_row_per_id_highlight_and_unknown():
    lines = [Line(True, 311100, "Gold Scarab", "permanent", "04:06:12.750", False),
             Line(True, 3971, None, "141.2 / 180.0 s", "04:06:12.750", True),
             Line(False, 2000000, "Standing", "", "04:06:07.512", False)]
    plain = ui.format_ledger("buffs", "2 active", lines, columns=80)
    assert plain[0] == " buffs   2 active" and plain[1].split() == ["id", "name", "timer", "time"]
    assert plain[2].split()[:3] == ["+", "311100", "Gold"] and plain[4].startswith(" -  ")
    assert "Unknown" in plain[3] and "141.2 / 180.0 s" in plain[3]
    colored = ui.format_ledger("buffs", "2 active", lines, color=True, columns=80)
    assert colored[3].count("\x1b[1;33m") >= 4 and "\x1b[1;33m" not in colored[2]   # only the row that just changed
    assert "\x1b[32m+" in colored[2] and "\x1b[2m-" in colored[4]    # active green, gone dim
    cut = ui.format_ledger("buffs", "x", lines * 5, columns=80, max_rows=6)
    assert len(cut) == 6 and "more (make the window taller" in cut[-1]
    assert ui.format_ledger("a", "x", [], waiting="no player")[0].endswith("waiting: no player")
    assert all(len(l) <= 40 for l in ui.format_ledger("e", "x", lines, columns=40)[2:])

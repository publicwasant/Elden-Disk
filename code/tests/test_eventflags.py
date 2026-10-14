"""1.8.0: the game's event flags, read (game/eventflags.py) and turned off (writer/eventflags.py), on a fake memory built like the game's."""
import pytest

from eldendisk.game.eventflags import EventFlagError, EventFlags
from eldendisk.writer.eventflags import FlagRefused, turn_off
from tests.eventflag_fakes import BASE, LAYOUT, ClosedGate, FlagMemory, OpenGate

MARGIT = (10000850, 10000851, 9100, 60510)


def flags_on(m, *ids):
    for f in ids:
        m.set(f)
    return m


def test_a_flag_is_read_through_the_tree_with_the_highest_bit_first():
    m = flags_on(FlagMemory([9, 60, 10000, 12050]), 10000850, 9100)
    ef = EventFlags(m, BASE, LAYOUT)
    assert ef.get(10000850) is True and ef.get(10000851) is False and ef.get(9100) is True and ef.get(60510) is False
    addr, mask = ef.where(10000850)
    assert mask == 1 << (7 - 850 % 8) and addr == m.block_addr(10000) + 850 // 8


def test_a_group_the_game_does_not_hold_is_none_and_many_flags_read_each_group_once():
    m = flags_on(FlagMemory([10000, 12050]), 10000850)
    ef = EventFlags(m, BASE, LAYOUT)
    assert ef.get(30000800) is None
    reads = []
    real = m.read
    m.read = lambda a, s: reads.append(s) or real(a, s)
    assert ef.get_many([10000800, 10000850, 10000851]) == {10000800: False, 10000850: True, 10000851: False}
    assert reads.count(125) == 1                                                     # one block for the three


def test_a_block_of_its_own_place_mode_2_is_read_too():
    m = flags_on(FlagMemory([10000], external=[2054390]), 2054390800)
    assert EventFlags(m, BASE, LAYOUT).get(2054390800) is True


def test_a_manager_that_holds_other_values_is_refused_as_moved():
    m = FlagMemory([10000], divisor=100, holder=13)
    with pytest.raises(EventFlagError, match="moved it"):
        EventFlags(m, BASE, LAYOUT).get(10000850)


def test_no_manager_yet_is_said():
    m = FlagMemory([10000])
    m.mem[BASE + LAYOUT.man_rva] = bytearray(8)
    with pytest.raises(EventFlagError, match="not there"):
        EventFlags(m, BASE, LAYOUT).get(10000850)


def test_the_blocks_found_are_dropped_when_the_game_rebuilds_its_tree():
    m = flags_on(FlagMemory([10000]), 10000850)
    ef = EventFlags(m, BASE, LAYOUT)
    assert ef.get(10000850) is True
    m2 = FlagMemory([10000, 11000])                                                 # a save loaded again: another tree
    m.mem.update(m2.mem)
    assert ef.get(10000850) is False


def test_turn_off_writes_only_the_table_flags_reads_back_and_never_turns_on():
    m = flags_on(FlagMemory([9, 60, 10000]), 10000850, 10000851, 9100, 60510)
    got = turn_off(m, OpenGate(), EventFlags(m, BASE, LAYOUT), MARGIT, set(MARGIT))
    assert got == dict.fromkeys(MARGIT, "off") and not any(m.get(f) for f in MARGIT)
    got = turn_off(m, OpenGate(), EventFlags(m, BASE, LAYOUT), MARGIT, set(MARGIT))
    assert got == dict.fromkeys(MARGIT, "was off") and len(m.writes) == 4            # nothing written the second time


def test_a_flag_outside_the_table_or_a_closed_gate_writes_nothing():
    m = flags_on(FlagMemory([10000, 61]), 10000850, 61100)
    with pytest.raises(FlagRefused, match="61100"):
        turn_off(m, OpenGate(), EventFlags(m, BASE, LAYOUT), [10000850, 61100], {10000850})
    with pytest.raises(FlagRefused, match="not allowed"):
        turn_off(m, ClosedGate(), EventFlags(m, BASE, LAYOUT), [10000850], {10000850})
    assert m.writes == [] and m.get(10000850) and m.get(61100)


def test_a_flag_that_does_not_stick_is_said_and_a_group_not_held_too():
    m = flags_on(FlagMemory([10000]), 10000850)
    m.fail_writes = True
    got = turn_off(m, OpenGate(), EventFlags(m, BASE, LAYOUT), [10000850, 30000800], {10000850, 30000800})
    assert got == {10000850: "did not stick", 30000800: "not held"}

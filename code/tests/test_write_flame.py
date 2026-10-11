"""`write --flame-color` (1.7.1): the writer's fxr module against a fake game memory, and the command step around it."""
import struct

import pytest

import eldendisk.commands.write as wcmd
from eldendisk.writer import fxr, scan
from eldendisk.writer.fxr_plans import PLANS
from eldendisk.writer.writer import WriteGate

BLUE = (0.2, 0.65, 1.0)
BASES = {"524400": 0x10000000, "524401": 0x20000000}


class Game:
    """Regions of bytes with the two effect files in them (as the game's file bytes: the colours at the plan's places). `reads` lists
    every read, `holes` are address ranges that cannot be read, `tick` is what a read costs on the clock of the test."""
    def __init__(self, effects=("524400", "524401")):
        self.mem, self.fail_writes, self.passes, self.reads, self.holes, self.tick = {}, False, 0, [], [], 0.0
        self.clock = None
        for eid in effects:
            plan = PLANS[eid]
            buf = bytearray(plan["size"])
            for at, hexa, _bloom in plan["colours"]:
                buf[at:at + 16] = bytes.fromhex(hexa)
            self.mem[BASES[eid]] = buf

    def regions(self, strict=False):
        self.passes += 1
        return [(b, len(d)) for b, d in self.mem.items()]

    def close(self):
        pass

    def alive(self):
        return True

    def read(self, addr, size):
        self.reads.append((addr, size))
        if self.clock is not None:
            self.clock[0] += self.tick
        if any(addr < h1 and h0 < addr + size for h0, h1 in self.holes):
            return None
        for b, d in self.mem.items():
            if b <= addr and addr + size <= b + len(d):
                return bytes(d[addr - b:addr - b + size])
        return None

    def write(self, addr, data):
        if self.fail_writes:
            return False
        for b, d in self.mem.items():
            if b <= addr and addr + len(data) <= b + len(d):
                d[addr - b:addr - b + len(data)] = data
                return True
        return False


@pytest.fixture(autouse=True)
def no_rests(monkeypatch):
    """The scan rests a moment after every piece and the command rests between looks: not in a test (the rests only move a fake clock)."""
    clock = [0.0]
    for mod in (scan, wcmd):
        monkeypatch.setattr(mod, "_sleep", lambda s, c=clock: c.__setitem__(0, c[0] + s))
        monkeypatch.setattr(mod, "_clock", lambda c=clock: c[0])
    return clock


def open_gate():
    g = WriteGate()
    g.open()
    return g


def f4(*v):
    return struct.pack("<4f", *v)


def painted(g, eid):
    return fxr.find_all(g, [eid], BLUE).changed[eid]


# ------------------------------------------------------------------------------------------------------ the pure parts
def test_white_and_black_stay_alpha_is_never_touched_and_a_bloom_colour_takes_the_brightness():
    assert fxr.recolor(f4(1, 1, 1, 0.3), BLUE) == f4(1, 1, 1, 0.3) and fxr.recolor(f4(0, 0, 0, 0), BLUE) == f4(0, 0, 0, 0)
    r, g, b, a = struct.unpack("<4f", fxr.recolor(f4(1, 0.5, 0.5, 0.7), (0, 0.25, 1)))
    assert (r, g, b) == pytest.approx((0.5, 0.5 + 0.5 * 0.25, 1.0)) and a == pytest.approx(0.7)
    assert struct.unpack("<4f", fxr.recolor(f4(2, 1, 0.5, 1), (0, 0.25, 1), bloom=True)) == pytest.approx((0, 0.5, 2, 1))


def test_a_bright_colour_keeps_its_brightness():
    r, g, b, _ = struct.unpack("<4f", fxr.recolor(f4(1.875, 1.125, 1.5, 1), BLUE))
    assert max(r, g, b) == pytest.approx(1.875) and b > r


def test_the_plans_are_sane_and_the_body_fire_is_not_one_of_them():
    assert tuple(PLANS) == ("524400", "524401") == fxr.effect_ids()
    for eid, plan in PLANS.items():
        ats = [c[0] for c in plan["colours"]]
        assert ats == sorted(set(ats)) and all(b - a >= 16 for a, b in zip(ats, ats[1:])), eid
        assert all(0 <= a and a + 16 <= plan["size"] and len(h) == 32 for a, h, _ in plan["colours"]), eid
    assert len(PLANS["524400"]["colours"]) == 18 and len(PLANS["524401"]["colours"]) == 54


def test_plan_writes_only_where_something_changes():
    w = fxr.plan_writes(PLANS["524401"], BLUE)
    assert w and all(old != new and len(old) == len(new) == 16 for old, new in w.values())
    assert len(w) < len(PLANS["524401"]["colours"])                                      # white and black places stay


def test_a_plan_that_changes_nothing_has_no_signature():
    plan = {"size": 64, "colours": [(0, f4(1, 1, 1, 1).hex(), False)]}
    with pytest.raises(fxr.FlameError):
        fxr._signature(plan, BLUE)


# ------------------------------------------------------------------------------------------------------ painting
def test_paint_many_changes_every_place_of_the_copy_and_nothing_else():
    g = Game()
    before = bytes(g.mem[BASES["524400"]])
    got, found = fxr.paint_many(g, open_gate(), ["524400"], BLUE)
    assert got["524400"].copies == 1 and got["524400"].places == len(fxr.plan_writes(PLANS["524400"], BLUE)) and got["524400"].already == 0
    assert found.walked.complete
    after = bytes(g.mem[BASES["524400"]])
    writes = fxr.plan_writes(PLANS["524400"], BLUE)
    for off, (old, new) in writes.items():
        assert after[off:off + len(new)] == new and before[off:off + len(old)] == old
    changed = {i for i in range(len(before)) if before[i] != after[i]}
    assert changed <= {i for off, (old, new) in writes.items() for i in range(off, off + len(new))}
    assert bytes(g.mem[BASES["524401"]]) == bytes(Game().mem[BASES["524401"]])           # an effect not asked for is untouched


def test_both_effects_are_found_and_changed_in_one_pass():
    g = Game()
    got, _ = fxr.paint_many(g, open_gate(), list(PLANS), BLUE)
    assert set(got) == set(PLANS) and g.passes == 1                                    # one look for both
    assert all(painted(g, e) == [BASES[e]] for e in PLANS)


def test_painting_twice_is_harmless_and_says_it_was_already_done():
    g = Game()
    fxr.paint_many(g, open_gate(), ["524401"], BLUE)
    once = bytes(g.mem[BASES["524401"]])
    got, _ = fxr.paint_many(g, open_gate(), ["524401"], BLUE)
    assert got["524401"].copies == 0 and got["524401"].already == 1 and got["524401"].places == 0 and bytes(g.mem[BASES["524401"]]) == once


def test_an_effect_the_game_does_not_hold_yet_is_left_out():
    got, found = fxr.paint_many(Game(effects=("524401",)), open_gate(), list(PLANS), BLUE)
    assert set(got) == {"524401"} and found.own["524400"] == [] and found.changed["524400"] == []


def test_a_copy_with_one_colour_off_is_not_taken_for_the_effect():
    g = Game()
    at = PLANS["524401"]["colours"][1][0]
    g.mem[BASES["524401"]][at + 4] ^= 0xFF
    got, _ = fxr.paint_many(g, open_gate(), ["524401"], BLUE)
    assert got == {}


def test_two_copies_in_one_piece_are_both_changed_and_the_look_ends_there():
    g = Game(effects=())
    one = Game(effects=("524401",)).mem[BASES["524401"]]
    both = bytearray(300_000)
    both[1000:1000 + len(one)] = one
    both[200_000:200_000 + len(one)] = one
    g.mem[0x50000000] = both
    g.mem[0x60000000] = bytearray(one)                                                     # a third copy, in a piece that is never read
    got, found = fxr.paint_many(g, open_gate(), ["524401"], BLUE)
    assert got["524401"].copies == 2 and got["524401"].places == 2 * len(fxr.plan_writes(PLANS["524401"], BLUE))
    assert found.walked.stopped and bytes(g.mem[0x60000000]) == bytes(one)


def test_a_copy_the_game_gave_its_own_colours_back_is_painted_again():
    g = Game()
    fxr.paint_many(g, open_gate(), ["524401"], BLUE)
    g.mem[BASES["524401"]][:] = Game().mem[BASES["524401"]]
    got, _ = fxr.paint_many(g, open_gate(), ["524401"], BLUE)
    assert got["524401"].copies == 1 and got["524401"].bases == (BASES["524401"],)


def test_a_closed_gate_writes_nothing():
    g, gate = Game(), WriteGate()
    with pytest.raises(fxr.FlameError, match="not allowed"):
        fxr.paint_many(g, gate, ["524400"], BLUE)
    assert bytes(g.mem[BASES["524400"]]) == bytes(Game().mem[BASES["524400"]])


def test_a_write_that_does_not_stick_is_an_error():
    g = Game()
    g.fail_writes = True
    with pytest.raises(fxr.FlameError, match="could not write"):
        fxr.paint_many(g, open_gate(), ["524400"], BLUE)


# ------------------------------------------------------------------------------------------------------ the scan
def finder(patterns, align=1):
    hits = []

    def visit(addr, data, n):
        for key, pattern in patterns.items():
            i = data.find(pattern)
            while i != -1:
                if i < n and (addr + i) % align == 0:
                    hits.append((key, addr + i))
                i = data.find(pattern, i + 1)
        return False
    return hits, visit


def test_walk_sees_what_lies_on_the_border_of_two_pieces_once(monkeypatch):
    monkeypatch.setattr(scan, "CHUNK", 40)
    g = Game(effects=())
    g.mem[0x60000000] = bytearray(100)
    g.mem[0x60000000][38:42] = b"ABCD"                                                    # begins in the first piece, ends in the second
    g.mem[0x60000000][60:62] = b"XY"
    hits, visit = finder({"a": b"ABCD", "b": b"XY"})
    walked = scan.walk(g, visit, overlap=3)
    assert walked.complete and not walked.stopped and sorted(hits) == [("a", 0x60000000 + 38), ("b", 0x60000000 + 60)]


def test_walk_rests_in_proportion_to_the_time_a_piece_took_and_stops_when_it_takes_too_long(monkeypatch, no_rests):
    monkeypatch.setattr(scan, "CHUNK", 100)
    g = Game(effects=())
    g.mem[0x60000000] = bytearray(1000)
    g.clock, g.tick = no_rests, 1.0                                                      # a read costs one second
    _hits, visit = finder({"a": b"ABCD"})
    walked = scan.walk(g, visit, overlap=3, budget=3.5)
    assert not walked.complete and not walked.stopped
    assert no_rests[0] == 3 * 1.0 + 2 * 0.5                                              # three reads; a rest of half a second after two of them
    g2 = Game(effects=())
    g2.mem[0x60000000] = bytearray(1000)
    g2.clock, g2.tick = no_rests, 1.0
    no_rests[0] = 0.0
    assert scan.walk(g2, visit, overlap=3, budget=100).complete and no_rests[0] == 10 * 1.5


def test_walk_reads_the_start_of_the_big_blocks_first_and_ends_when_visit_says_so(monkeypatch):
    monkeypatch.setattr(scan, "BIG", 100_000)
    monkeypatch.setattr(scan, "HEAD", 30_000)
    g = Game(effects=())
    g.mem[0x70000000] = bytearray(200_000)
    g.mem[0x80000000] = bytearray(5_000)
    g.mem[0x70000000][1000:1004] = b"NEAR"
    g.mem[0x70000000][120_000:120_004] = b"FAR_"
    order = []

    def visit(addr, data, n):
        order.append(addr)
        return b"NEAR" in data[:n]
    walked = scan.walk(g, visit, overlap=3)
    assert walked.stopped and walked.tier == "head" and order == [0x70000000]               # the small block was never read
    seen = []

    def far(addr, data, n):
        seen.append(addr)
        return b"FAR_" in data[:n]
    walked = scan.walk(g, far, overlap=3)
    assert walked.stopped and walked.tier == "rest" and seen[0] == 0x70000000 and 0x80000000 not in seen


def test_a_piece_that_cannot_be_read_whole_is_read_in_parts(monkeypatch):
    monkeypatch.setattr(scan, "SPLIT", 1000)
    g = Game(effects=())
    g.mem[0x60000000] = bytearray(5000)
    g.mem[0x60000000][4200:4204] = b"ABCD"
    g.holes = [(0x60000000 + 1000, 0x60000000 + 1500)]                                    # one page that is gone
    hits, visit = finder({"a": b"ABCD"})
    walked = scan.walk(g, visit, overlap=3)
    assert walked.complete and hits == [("a", 0x60000000 + 4200)]


def test_where_says_how_far_into_its_block_an_address_is():
    g = Game(effects=())
    g.mem[0x60000000] = bytearray(3 * 1024 * 1024)
    assert "2 MB" in scan.where(g, 0x60000000 + 2 * 1024 * 1024 + 5) and "3 MB at 0x60000000" in scan.where(g, 0x60000000 + 2 * 1024 * 1024 + 5)
    assert scan.where(g, 0x1000) == "outside the private blocks"


def test_find_all_asks_only_for_the_private_memory_and_stops_when_every_effect_has_a_copy():
    g = Game()
    found = fxr.find_all(g, list(PLANS), BLUE)
    assert found.walked.stopped and found.own["524400"] == [BASES["524400"]] and found.own["524401"] == [BASES["524401"]]
    lonely = Game(effects=("524400",))
    found = fxr.find_all(lonely, list(PLANS), BLUE)
    assert found.walked.complete and not found.walked.stopped and found.own["524401"] == []


def test_find_all_can_leave_the_already_changed_copies_out():
    g = Game()
    fxr.paint_many(g, open_gate(), ["524401"], BLUE)
    assert fxr.find_all(g, ["524401"], BLUE, painted=False).walked.complete                  # not found as changed: looked through everything
    assert fxr.find_all(g, ["524401"], BLUE).changed["524401"] == [BASES["524401"]]


# ------------------------------------------------------------------------------------------------------ the command step
@pytest.fixture
def quiet_where(monkeypatch):
    monkeypatch.setattr(wcmd.wscan, "where", lambda mem, addr: "somewhere")


def test_put_flame_paints_both_effects_in_one_look_and_says_where_they_were(monkeypatch, quiet_where):
    g = Game()
    seen = []
    monkeypatch.setattr(wcmd.book, "d", lambda tag, msg: seen.append(msg))
    assert wcmd._put_flame(g, open_gate(), BLUE) == 0 and g.passes == 1
    assert all(painted(g, e) == [BASES[e]] for e in PLANS)
    assert any("look 1/1" in m and "all found" in m for m in seen) and any("somewhere" in m for m in seen)


def test_put_flame_looks_again_for_an_effect_the_game_has_not_loaded_yet(monkeypatch, no_rests, quiet_where):
    g = Game(effects=("524400",))
    gaps = []

    def rest(sec):
        gaps.append(sec)
        no_rests[0] += sec
        if sec == 10.0:
            g.mem[BASES["524401"]] = Game().mem[BASES["524401"]]                          # the game loads the second file meanwhile
    monkeypatch.setattr(wcmd, "_sleep", rest)
    assert wcmd._put_flame(g, open_gate(), BLUE, wcmd.LOOKS) == 0
    assert gaps == [10.0] and painted(g, "524401") == [BASES["524401"]]


def test_put_flame_gives_up_after_its_looks_and_says_which_effect_is_missing(monkeypatch, quiet_where):
    g = Game(effects=("524400",))
    seen = []
    monkeypatch.setattr(wcmd.book, "e", lambda tag, msg: seen.append(msg))
    assert wcmd._put_flame(g, open_gate(), BLUE, wcmd.LOOKS) == 1
    assert "524401" in seen[-1] and "5 look" in seen[-1]
    assert wcmd._put_flame(Game(effects=("524400",)), open_gate(), BLUE) == 1             # by hand: one look


def test_a_flame_error_is_reported_and_stops():
    g = Game()
    g.fail_writes = True
    assert wcmd._put_flame(g, open_gate(), BLUE) == 1

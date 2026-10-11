"""tools/fxr_recolor.py: the pure parts, the plans file, and a fake memory built from the plans. The Windows part needs the game."""
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import fxr_recolor as fr  # noqa: E402

BLUE = (0, 0.25, 1)


def f4(*v):
    return struct.pack("<4f", *v)


def test_white_and_black_stay_and_alpha_is_never_touched():
    assert fr.recolor(f4(1, 1, 1, 0.3), BLUE) == f4(1, 1, 1, 0.3)
    assert fr.recolor(f4(0, 0, 0, 0), BLUE) == f4(0, 0, 0, 0)
    r, g, b, a = struct.unpack("<4f", fr.recolor(f4(1, 0.5, 0.5, 0.7), BLUE))
    assert (r, g, b) == pytest.approx((0.5, 0.5 + 0.5 * 0.25, 1.0)) and a == pytest.approx(0.7)


def test_a_bright_colour_keeps_its_brightness():
    r, g, b, _ = struct.unpack("<4f", fr.recolor(f4(1.875, 1.125, 1.5, 1), (0.2, 0.65, 1)))
    w = 1 - (1.875 - 1.125) / 1.875
    assert (r, g, b) == pytest.approx(tuple(1.875 * (w + (1 - w) * t) for t in (0.2, 0.65, 1)))
    assert max(r, g, b) == pytest.approx(1.875)


def test_pure_red_becomes_the_target_and_a_bloom_colour_too():
    assert struct.unpack("<4f", fr.recolor(f4(1, 0, 0, 1), BLUE)) == pytest.approx((0, 0.25, 1, 1))
    assert struct.unpack("<4f", fr.recolor(f4(1, 0.25, 0.25, 0.25), BLUE, bloom=True)) == pytest.approx((0, 0.25, 1, 0.25))
    assert struct.unpack("<4f", fr.recolor(f4(2, 1, 0.5, 1), BLUE, bloom=True)) == pytest.approx((0, 0.5, 2, 1))


def test_the_gradient_of_the_body_fire_is_what_the_first_tool_made():
    # the numbers of f000524402 (checked in the game): keyframe 4 (1, .12549, .12549, 0) with target (0, .25, 1)
    r, g, b, a = struct.unpack("<4f", fr.recolor(f4(1, .12549, .12549, 0), BLUE))
    assert (r, g, b, a) == pytest.approx((.12549, .12549 + .87451 * .25, 1, 0))


def small_plan():
    return {"size": 0x400, "colours": [{"at": 0x100, "old": f4(1, .5, .25, 1).hex(), "bloom": False},
                                         {"at": 0x120, "old": f4(1, .25, .25, .25).hex(), "bloom": True},
                                         {"at": 0x140, "old": f4(1, 1, 1, 1).hex(), "bloom": False}],
            "blend": [{"at": 0x200, "old": 2, "add": 4}]}


def test_plan_writes_skip_what_does_not_change_and_add_the_blend_on_request():
    plan = small_plan()
    w = fr.plan_writes(plan, BLUE)
    assert sorted(w) == [0x100, 0x120]                       # the white one stays
    w = fr.plan_writes(plan, BLUE, "add")
    assert w[0x200] == (struct.pack("<i", 2), struct.pack("<i", 4))
    assert fr.plan_writes(plan, BLUE, "normal")[0x200][1] == struct.pack("<i", 2)
    with pytest.raises(fr.TintError, match="blend"):
        fr.plan_writes(plan, BLUE, "multiply")


class Fake:
    def __init__(self, regions):
        self.mem = {base: bytearray(data) for base, data in regions}

    def regions(self):
        return [(b, len(d), "private", 4) for b, d in self.mem.items()]

    def read(self, addr, size):
        for b, d in self.mem.items():
            if b <= addr and addr + size <= b + len(d):
                return bytes(d[addr - b:addr - b + size])
        return None

    def write(self, addr, data):
        for b, d in self.mem.items():
            if b <= addr and addr + len(data) <= b + len(d):
                d[addr - b:addr - b + len(data)] = data
                return
        raise OSError("bad address")


def put(heap, base_at, plan):
    for c in plan["colours"]:
        heap[base_at + c["at"]:base_at + c["at"] + 16] = bytes.fromhex(c["old"])
    for b in plan["blend"]:
        struct.pack_into("<i", heap, base_at + b["at"], b["old"])


def test_find_apply_undo_roundtrip():
    plan = small_plan()
    heap = bytearray(0x4000)
    put(heap, 0x1000, plan)
    other = bytearray(0x4000)                               # one colour only: not a full copy
    other[0x100:0x110] = bytes.fromhex(plan["colours"][0]["old"])
    mem = Fake([(0x10000, heap), (0x80000, other)])
    bases, nearly = fr.find_copies(mem, plan)
    assert bases == [0x10000 + 0x1000] and nearly == []
    rec = fr.apply(mem, plan, bases, BLUE, "add")
    assert len(rec) == 3
    assert mem.read(0x11000 + 0x120, 16) == f4(0, .25, 1, .25) and mem.read(0x11000 + 0x200, 4) == struct.pack("<i", 4)
    assert mem.read(0x11000 + 0x140, 16) == f4(1, 1, 1, 1)
    assert fr.undo(mem, rec) == 3
    assert mem.read(0x11000 + 0x120, 16) == f4(1, .25, .25, .25) and mem.read(0x11000 + 0x200, 4) == struct.pack("<i", 2)


def test_a_copy_where_most_colours_match_is_reported_but_not_used():
    plan = small_plan()
    heap = bytearray(0x4000)
    put(heap, 0x1000, plan)
    heap[0x1000 + 0x120:0x1000 + 0x130] = f4(9, 9, 9, 9)
    mem = Fake([(0x10000, heap)])
    bases, nearly = fr.find_copies(mem, plan)
    assert bases == [] and [n for _b, n in nearly] == [2]


def test_apply_writes_nothing_when_a_place_is_not_the_game_s():
    plan = small_plan()
    heap = bytearray(0x4000)
    put(heap, 0x1000, plan)
    mem = Fake([(0x10000, heap)])
    mem.write(0x11000 + 0x120, f4(5, 5, 5, 5))
    with pytest.raises(fr.TintError):
        fr.apply(mem, plan, [0x11000], BLUE)
    assert mem.read(0x11000 + 0x100, 16) == bytes.fromhex(plan["colours"][0]["old"])      # not even the first was written


def test_undo_leaves_what_changed_since():
    plan = small_plan()
    heap = bytearray(0x4000)
    put(heap, 0, plan)
    mem = Fake([(0x10000, heap)])
    rec = fr.apply(mem, plan, [0x10000], BLUE)
    mem.write(0x10000 + 0x120, f4(5, 5, 5, 5))
    assert fr.undo(mem, rec) == 1
    assert mem.read(0x10000 + 0x120, 16) == f4(5, 5, 5, 5)


def test_the_plans_file_is_sane():
    plans = fr.load_plans()
    assert set(plans) == {"524400", "524401", "524402"}
    for eid, plan in plans.items():
        ats = [c["at"] for c in plan["colours"]]
        assert ats == sorted(set(ats)) and all(b - a >= 16 for a, b in zip(ats, ats[1:])), eid
        assert all(0 <= a and a + 16 <= plan["size"] and len(c["old"]) == 32 for a, c in zip(ats, plan["colours"])), eid
        assert fr.signature(plan) in plan["colours"]
    assert [c["at"] for c in plans["524402"]["colours"]] == [0x173C, 0x1874, 0x1884, 0x1894, 0x18A4]   # as proven in the game
    assert plans["524402"]["blend"] == [{"at": 0x17E8, "old": 2, "add": 4}]
    assert len(plans["524400"]["colours"]) == 18 and len(plans["524401"]["colours"]) == 54   # constants too (v1 had 10 and 39)


@pytest.mark.parametrize("eid", ["524400", "524401", "524402"])
def test_the_plan_matches_the_real_file_when_present(eid):
    p = Path(__file__).resolve().parent.parent / "sfxdump" / f"f000{eid}.fxr"
    if not p.is_file():
        pytest.skip("run tools/dump_sfx.py --sfx 524400 --sfx 524401 --sfx 524402 first")
    blob, plan = p.read_bytes(), fr.load_plans()[eid]
    assert len(blob) == plan["size"]
    for c in plan["colours"]:
        assert blob[c["at"]:c["at"] + 16] == bytes.fromhex(c["old"])
    for b in plan["blend"]:
        assert struct.unpack_from("<i", blob, b["at"])[0] == b["old"]

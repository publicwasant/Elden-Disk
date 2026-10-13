import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import capacity  # noqa: E402

from eldendisk.design.innovate_items import preflight                      # noqa: E402
from eldendisk.design.innovate_items.spells import build, spec             # noqa: E402

ORIG = os.environ.get("ELDENDISK_REGULATION_ORIG")


def test_a_mix_is_kinds_and_counts_in_order():
    assert capacity.parse_mix("projectile=4, attack=2,buff=1") == [("projectile", 4), ("attack", 2), ("buff", 1)]


@pytest.mark.parametrize("bad", ["", "dragon=2", "buff", "buff=0", "buff=x", "buff=40,clone=40"])
def test_a_bad_mix_is_refused(bad):
    with pytest.raises(ValueError):
        capacity.parse_mix(bad)


def test_the_design_has_the_slots_in_order_and_a_shop_on_the_first_seven():
    d = capacity.design([("attack", 2), ("buff", 6)])
    slots = d["innovate_items"]["spells"]["slots"]
    filled = [(k, v) for k, v in slots.items() if v]
    assert len(slots) == 64 and len(filled) == 8
    assert [v.get("kind", "buff") for _, v in filled] == ["attack"] * 2 + ["buff"] * 6
    assert [("shop" in v) for _, v in filled] == [True] * 7 + [False]
    assert filled[0][1]["from"] == 4440
    assert [v["shop"]["price"] for _, v in filled[:7]] == [1001, 1002, 1003, 1004, 1005, 1006, 1007]      # the price tells the slot
    spells = spec.normalise(d)["spells"]            # the design is valid for the real validator
    assert len(spells) == 8


def test_buffs_do_not_share_their_dicts():
    d = capacity.design([("buff", 2)])["innovate_items"]["spells"]["slots"]
    a, b = [v for v in d.values() if v]
    assert a is not b and a["effect"] is not b["effect"] and a["requires"] is not b["requires"]


def test_the_limits_broken_are_named():
    ok = {"blocks": 5, "body": 1, "frame": 1}
    assert capacity.limits_broken(ok) == ""
    bad = {"blocks": preflight.MAX_CHANGED_BLOCKS + 1, "body": preflight.MAX_BODY_GROWTH + 1, "frame": preflight.MAX_FRAME_GROWTH}
    assert capacity.limits_broken(bad) == "blocks,body"


def test_a_row_says_ok_or_stop():
    mix = [("buff", 2)]
    good = {"slots": 2, "blocks": 13, "body": 68464, "frame": 102624, "problems": [], "ok": True}
    stop = dict(good, ok=False, frame=300000, problems=["R7: the frame grew by 300000 bytes"])
    assert capacity.row(mix, good).endswith("ok") and "2 buff" in capacity.row(mix, good)
    assert "STOP: frame" in capacity.row(mix, stop)


def test_the_tool_refuses_a_file_that_is_not_the_original(tmp_path, capsys):
    f = tmp_path / "regulation.bin"
    f.write_bytes(b"x" * 64)
    assert capacity.main(["--source", str(f), "--mix", "buff=1"]) == 2
    assert "not the original" in capsys.readouterr().err
    assert capacity.main(["--source", str(f)]) == 2


@pytest.mark.skipif(not ORIG or not Path(ORIG).is_file(), reason="set ELDENDISK_REGULATION_ORIG to the pristine regulation.bin")
def test_the_numbers_of_the_real_file_are_the_measured_ones():
    src = build.prepare(Path(ORIG).read_bytes())
    r = capacity.measure(src, [("attack", 1)])
    assert (r["blocks"], r["body"], r["frame"], r["ok"]) == (19, 93888, 160704, True)
    r = capacity.measure(src, [("projectile", 1)])
    assert (r["blocks"], r["body"]) == (26, 121600) and r["ok"]
    r = capacity.measure(src, [("projectile", 2), ("attack", 2), ("buff", 16)])          # T10: the 20-slot design that passed in the game
    assert (r["blocks"], r["body"], r["frame"], r["ok"]) == (27, 159712, 291040, True)
    assert not capacity.measure(src, [("buff", 64)])["ok"]          # the frame (399,712) is beyond the gate

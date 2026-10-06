"""MemoryWriter: gated, validated, clamped, never cached (MW-1..MW-6, FR-14)."""
import struct

import pytest

from eldendisk.reader.sampler import Sampler
from eldendisk.writer.writer import (EDIT_NAMES, EditPolicy, MemoryWriter, WriteGate, WritableProcessMemory,
                                     parse_policy)
from tests.test_disk import BASE, DATA_MOD, GD, PLAYER, FakeMem, effects, full_world, make_profile


class WMem(FakeMem):
    def __init__(self):
        super().__init__()
        self.fail = False
        self.log = []

    def write(self, addr, data):
        if self.fail:
            return False
        self.log.append(addr)
        self.put(addr, data)
        return True


def rig(policy, *, open_gate=True, hz=4.0):
    m = WMem()
    m.b = full_world().b
    clock = {"t": 0.0}
    gate = WriteGate()
    if open_gate:
        gate.open()
    s = Sampler(m, make_profile(), effects(), BASE)
    w = MemoryWriter(m, s, policy, gate, hz=hz, clock=lambda: clock["t"])
    return m, w, gate, clock


def u32(m, a): return struct.unpack("<I", m.read(a, 4))[0]
def i32(m, a): return struct.unpack("<i", m.read(a, 4))[0]


# ---- policy parsing ----
def test_parse_policy_ok():
    p = parse_policy(["level=150", "VIGOR=40", "runes=1_000_000"], "hp, fp")
    assert dict(p.sets) == {"level": 150, "vigor": 40, "runes": 1_000_000} and p.refill == ("hp", "fp")
    assert parse_policy(None, None).empty


@pytest.mark.parametrize("sets,refill", [
    (["bogus=1"], None), (["level"], None), (["level=abc"], None), (["level=-5"], None),
    (["level=1", "level=2"], None), ([], "mana"), (["hp=5"], "hp"),
])
def test_parse_policy_rejects(sets, refill):
    with pytest.raises(ValueError):
        parse_policy(sets, refill)


def test_every_edit_name_is_accepted():
    for n in EDIT_NAMES:
        assert parse_policy([f"{n}=1"], None).sets == ((n, 1),)


# ---- gating ----
def test_closed_gate_writes_nothing():
    m, w, gate, _ = rig(parse_policy(["level=150"], None), open_gate=False)
    assert w.tick() == [] and m.log == [] and u32(m, GD + 0x68) == 386
    gate.open()
    assert [r.name for r in w.tick()] == ["level"]
    gate.close("session ended")
    m.log.clear()
    assert w.tick() == [] and m.log == []


def test_empty_policy_never_writes():
    m, w, _, _ = rig(EditPolicy())
    assert w.tick() == [] and m.log == []


def test_writable_handle_is_a_distinct_type():
    from eldendisk.game.memory import ProcessMemory
    assert issubclass(WritableProcessMemory, ProcessMemory)
    assert not hasattr(ProcessMemory, "write")


# ---- writes ----
def test_stored_fields_and_vitals_are_written():
    m, w, _, _ = rig(parse_policy(["level=150", "runes=1000000", "vigor=40", "arcane=99", "hp=1000", "stamina=100"], None))
    res = w.tick()
    assert all(r.wrote for r in res) and len(res) == 6
    assert u32(m, GD + 0x68) == 150 and u32(m, GD + 0x6C) == 1_000_000
    assert u32(m, GD + 0x3C) == 40 and u32(m, GD + 0x3C + 4 * 7) == 99
    assert i32(m, DATA_MOD + 0x138) == 1000 and i32(m, DATA_MOD + 0x138 + 28) == 100
    assert i32(m, DATA_MOD + 0x138 + 4) == 1914  # maximum untouched (MW-4)


def test_values_are_clamped():
    m, w, _, _ = rig(parse_policy(["level=9999", "vigor=500", "runes=99999999999", "hp=999999", "fp=0"], None))
    w.tick()
    assert u32(m, GD + 0x68) == 713 and u32(m, GD + 0x3C) == 99 and u32(m, GD + 0x6C) == 999_999_999
    assert i32(m, DATA_MOD + 0x138) == 1914 and i32(m, DATA_MOD + 0x138 + 16) == 0
    m2, w2, _, _ = rig(parse_policy(["hp=0"], None))
    w2.tick()
    assert i32(m2, DATA_MOD + 0x138) == 1  # hp is never set to 0


def test_refill_holds_current_at_maximum():
    m, w, _, c = rig(parse_policy([], "hp,fp,stamina"))
    w.tick()
    assert (i32(m, DATA_MOD + 0x138), i32(m, DATA_MOD + 0x138 + 16), i32(m, DATA_MOD + 0x138 + 28)) == (1914, 350, 178)
    m.put(DATA_MOD + 0x138, struct.pack("<i", 10))  # the player is hit
    c["t"] = 1.0
    assert [r.name for r in w.tick()] == ["hp"] and i32(m, DATA_MOD + 0x138) == 1914


def test_no_write_when_already_at_target_and_rate_limit():
    m, w, _, c = rig(parse_policy(["level=150"], None), hz=2.0)
    assert len(w.tick()) == 1
    c["t"] = 0.1
    m.log.clear()
    assert w.tick() == [] and m.log == []          # inside the 0.5 s period
    c["t"] = 0.6
    assert w.tick() == [] and m.log == []          # period elapsed but value already correct
    m.put(GD + 0x68, struct.pack("<I", 1))         # the game overwrites it
    c["t"] = 1.2
    assert len(w.tick()) == 1 and u32(m, GD + 0x68) == 150


@pytest.mark.parametrize("hz", [0.5, 31])
def test_write_rate_is_bounded(hz):
    with pytest.raises(ValueError):
        rig(parse_policy(["level=5"], None), hz=hz)


def test_pointers_are_resolved_on_every_write():
    m, w, _, c = rig(parse_policy(["level=150"], None))
    w.tick()
    GD2 = 0x228000000
    m.u32(GD2 + 0x68, 5)
    m.u64(PLAYER + 0x580, GD2)                     # map load: PlayerGameData was recreated elsewhere
    c["t"] = 1.0
    w.tick()
    assert u32(m, GD2 + 0x68) == 150 and u32(m, GD + 0x68) == 150  # old object untouched after the move


def test_null_and_invalid_pointers_skip_without_error():
    m, w, _, c = rig(parse_policy(["level=150", "hp=900"], None))
    m.u64(BASE + 0x1000, 0)                        # title screen
    assert w.tick() == [] and m.log == []
    m.u64(BASE + 0x1000, 0x200000000)
    m.u64(0x200000000 + 0x10, 0x10)                # garbage player pointer
    c["t"] = 1.0
    assert w.tick() == [] and m.log == []


def test_invalid_vitals_block_is_not_written():
    m, w, _, _ = rig(parse_policy(["hp=900"], None))
    m.put(DATA_MOD + 0x138, struct.pack("<10i", -5, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    assert w.tick() == [] and m.log == []


def test_failed_write_is_reported_not_raised():
    m, w, _, _ = rig(parse_policy(["level=150"], None))
    m.fail = True
    res = w.tick()
    assert len(res) == 1 and res[0].wrote is False and u32(m, GD + 0x68) == 386


def test_transitions_are_logged_once():
    lines = []
    m = WMem(); m.b = full_world().b
    gate = WriteGate(); gate.open()
    clock = {"t": 0.0}
    w = MemoryWriter(m, Sampler(m, make_profile(), effects(), BASE), parse_policy(["level=150"], None), gate,
                     clock=lambda: clock["t"], log=lines.append)
    for i in range(5):
        clock["t"] = i
        w.tick()
    assert len([l for l in lines if "level" in l]) == 2  # "set to 150" once, then "holding 150" once

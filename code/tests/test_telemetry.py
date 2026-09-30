import json
import struct
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
import pytest

from elden_telemetry import memory_reader
from elden_telemetry.json_logger import JsonLogger
from elden_telemetry.profile_loader import (ActiveEffect, EntryLayout, Effects, PassiveEffect, Profile,
                                            SpEffectLayout, load_effects, load_profile)
from elden_telemetry.telemetry import Sampler, build_document

PKG = Path(memory_reader.__file__).parent
SCHEMA = json.loads((PKG / "telemetry.schema.json").read_text())

BASE, WCM, PLAYER, GD, SP = 0x140000000, 0x200000000, 0x210000000, 0x220000000, 0x230000000
E1, E2, E3 = 0x240000000, 0x240001000, 0x240002000
NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)


class FakeMem:
    def __init__(self):
        self.b = {}

    def put(self, addr, data):
        for i, v in enumerate(data):
            self.b[addr + i] = v

    def u32(self, a, v): self.put(a, struct.pack("<I", v))
    def u64(self, a, v): self.put(a, struct.pack("<Q", v))
    def f32(self, a, v): self.put(a, struct.pack("<f", v))

    def read(self, addr, size):
        if size <= 0 or not memory_reader.is_user_ptr(addr):
            return None
        try:
            return bytes(self.b[addr + i] for i in range(size))
        except KeyError:
            return None


def make_profile(mode="remaining", sp=True):
    lay = SpEffectLayout(0x178, 0x8, EntryLayout(0x08, 0x30, 0x14, 0x10, mode)) if sp else None
    return Profile("ab" * 32, "test", 0x1000, 0x10, 0x580, 0x68, 0x6C, 0x3C, lay)


def effects():
    return Effects(
        active={100: ActiveEffect("Golden Vow")},
        passive={200: PassiveEffect("Gold Scarab", "TALISMAN", "Gold Scarab Talisman")},
    )


def entry(m, addr, eid, dur, timer, nxt):
    m.put(addr, b"\0" * 0x60)  # real entries are contiguous memory
    m.u32(addr + 0x08, eid); m.f32(addr + 0x14, dur); m.f32(addr + 0x10, timer); m.u64(addr + 0x30, nxt)


def world(m, runes=10_008_626, level=386, attrs=(80, 60, 60, 90, 90, 15, 60, 10), head=E1):
    m.u64(BASE + 0x1000, WCM)
    m.u64(WCM + 0x10, PLAYER)
    m.u64(PLAYER + 0x580, GD)
    m.u64(PLAYER + 0x178, SP)
    m.u64(SP + 0x8, head)
    m.u32(GD + 0x68, level); m.u32(GD + 0x6C, runes)
    m.put(GD + 0x3C, struct.pack("<8I", *attrs))


def full_world(mode="remaining"):
    m = FakeMem()
    world(m)
    if mode == "remaining":
        entry(m, E1, 100, 80.0, 45.0, E2)
    else:
        entry(m, E1, 100, 80.0, 35.0, E2)
    entry(m, E2, 200, -1.0, 0.0, E3)
    entry(m, E3, 999, 10.0, 5.0, 0)
    return m


def valid(doc):
    jsonschema.validate(doc, SCHEMA, format_checker=jsonschema.FormatChecker())


def doc_for(sampler, sample, state=None):
    return build_document(now=NOW, state=state or sample.state, pid=1, anti_cheat="DISABLED_OFFLINE",
                          exe_sha256="x", profile_label="test", buffs_supported=True, sample=sample,
                          session_start_runes=sampler.session_start_runes)


@pytest.mark.parametrize("mode", ["remaining", "elapsed"])
def test_connected_sample(mode):
    m = full_world(mode)
    s = Sampler(m, make_profile(mode), effects(), BASE)
    r = s.sample(NOW)
    assert r.state == "CONNECTED"
    c = r.character
    assert (c["level"], c["runes"]) == (386, 10_008_626)
    assert c["attributes"]["strength"] == 90 and c["attributes"]["arcane"] == 10
    assert [b["id"] for b in c["active_buffs"]] == [100]
    b = c["active_buffs"][0]
    assert b["remaining_seconds"] == 45.0 and b["max_duration_seconds"] == 80.0
    assert b["activation_timestamp_iso"] == "2026-09-30T11:59:25.000Z"  # now - (80-45)
    assert c["passive_buffs"] == [{"id": 200, "name": "Gold Scarab", "category": "TALISMAN",
                                   "source_name": "Gold Scarab Talisman"}]
    assert r.ignored_effects == 1  # id 999 not in tables
    valid(doc_for(s, r))


def test_rune_delta_and_session_start():
    m = full_world()
    s = Sampler(m, make_profile(), effects(), BASE)
    s.sample(NOW)
    m.u32(GD + 0x6C, 10_508_626)
    r = s.sample(NOW)
    d = doc_for(s, r)
    assert d["telemetry"] == {"session_start_runes": 10_008_626, "rune_delta": 500_000}
    valid(d)


def test_null_world_is_silent_waiting():
    m = full_world()
    m.u64(BASE + 0x1000, 0)
    s = Sampler(m, make_profile(), effects(), BASE)
    r = s.sample(NOW)
    assert r.state == "WAITING_FOR_WORLD" and r.error is None and r.character is None
    d = doc_for(s, r)
    assert d["character"] is None and d["system_status"]["game_connected"] is False
    valid(d)


@pytest.mark.parametrize("addr,val,frag", [
    (GD + 0x68, 0, "level"),
    (GD + 0x68, 714, "level"),
    (GD + 0x6C, 1_000_000_000, "runes"),
    (GD + 0x3C, 100, "vigor"),
])
def test_range_failures_discard_sample(addr, val, frag):
    m = full_world()
    m.u32(addr, val)
    r = Sampler(m, make_profile(), effects(), BASE).sample(NOW)
    assert r.state == "WAITING_FOR_WORLD" and r.character is None and frag in r.error


def test_unreadable_memory_is_not_zero():
    m = full_world()
    for i in range(4):
        del m.b[GD + 0x6C + i]
    r = Sampler(m, make_profile(), effects(), BASE).sample(NOW)
    assert r.state == "WAITING_FOR_WORLD" and "read failed" in r.error


def test_cycle_and_bad_pointer_discard():
    m = full_world()
    entry(m, E3, 999, 10.0, 5.0, E1)
    assert "cycle" in Sampler(m, make_profile(), effects(), BASE).sample(NOW).error
    m = full_world()
    entry(m, E3, 999, 10.0, 5.0, 0x1234)
    assert "invalid SpEffect entry pointer" in Sampler(m, make_profile(), effects(), BASE).sample(NOW).error


def test_list_length_cap():
    m = FakeMem()
    world(m)
    for i in range(513):
        a = 0x300000000 + i * 0x100
        entry(m, a, 5, 1.0, 1.0, a + 0x100)
    m.u64(SP + 0x8, 0x300000000)
    r = Sampler(m, make_profile(), effects(), BASE).sample(NOW)
    assert r.state == "WAITING_FOR_WORLD" and "longer than" in r.error


def test_expired_or_bad_timer_ignored():
    m = full_world()
    entry(m, E1, 100, 80.0, 0.0, E2)  # remaining 0 -> not active
    r = Sampler(m, make_profile(), effects(), BASE).sample(NOW)
    assert r.character["active_buffs"] == []


def test_buffs_disabled_when_sp_layout_missing():
    m = full_world()
    r = Sampler(m, make_profile(sp=False), effects(), BASE).sample(NOW)
    assert r.state == "CONNECTED" and r.character["active_buffs"] == [] and r.ignored_effects == 0


def test_non_connected_states_validate():
    for state in ["WAITING_FOR_PROCESS", "EAC_ACTIVE", "EAC_DETECTED", "UNSUPPORTED_VERSION", "DISCONNECTED"]:
        d = build_document(now=NOW, state=state, pid=None, anti_cheat="UNKNOWN", exe_sha256=None,
                           profile_label=None, buffs_supported=False, sample=None,
                           session_start_runes=None, note="x")
        valid(d)


# ---- profile loading ----
def write_json(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj))
    return p


FULL = {
    "label": "t", "world_chr_man_rva": "0x3D5E700", "world_chr_man_to_player": "0x10EF8",
    "player_to_game_data": "0x580", "player_to_sp_effect": "0x178",
    "game_data": {"level": "0x68", "runes": "0x6C", "attributes": "0x3C"},
    "sp_effect": {"head": "0x8", "entry": {"id": "0x8", "next": "0x30", "duration": "0x14",
                                           "timer": "0x10", "timer_mode": "elapsed"}},
}


def test_profile_ok_and_hex(tmp_path):
    p = write_json(tmp_path, "o.json", {"profiles": {"AB" * 32: FULL}})
    prof, why = load_profile(p, "ab" * 32)
    assert why is None and prof.world_chr_man_rva == 0x3D5E700 and prof.runes == 0x6C
    assert prof.sp_effect.entry.timer_mode == "elapsed"


def test_profile_unknown_hash_and_incomplete(tmp_path):
    p = write_json(tmp_path, "o.json", {"profiles": {"cd" * 32: FULL}})
    assert load_profile(p, "ab" * 32)[0] is None
    bad = dict(FULL, world_chr_man_rva=None)
    p = write_json(tmp_path, "o2.json", {"profiles": {"ab" * 32: bad}})
    prof, why = load_profile(p, "ab" * 32)
    assert prof is None and "world_chr_man_rva" in why


def test_profile_partial_buffs_disables_only_buffs(tmp_path):
    part = json.loads(json.dumps(FULL))
    part["sp_effect"]["entry"]["id"] = None
    p = write_json(tmp_path, "o.json", {"profiles": {"ab" * 32: part}})
    prof, why = load_profile(p, "ab" * 32)
    assert why is None and prof.sp_effect is None and "buffs disabled" in prof.buffs_note


def test_effects_loader(tmp_path):
    assert load_effects(tmp_path / "missing.json") == Effects({}, {})
    p = write_json(tmp_path, "e.json", {"_readme": "x", "active": {"100": {"name": "A"}},
                                        "passive": {"200": {"name": "P", "category": "TALISMAN"}}})
    e = load_effects(p)
    assert e.active[100].name == "A" and e.passive[200].source_name == "P"
    p = write_json(tmp_path, "e2.json", {"passive": {"1": {"name": "P", "category": "NOPE"}}})
    with pytest.raises(ValueError):
        load_effects(p)


# ---- safety ----
def test_read_only_access_mask_and_no_write_apis():
    assert memory_reader.ACCESS_MASK == 0x1010
    forbidden = ["WriteProcessMemory", "VirtualAllocEx", "CreateRemoteThread", "VirtualProtectEx",
                 "NtWriteVirtualMemory", "SetThreadContext"]
    for f in PKG.glob("*.py"):
        text = f.read_text()
        for name in forbidden:
            assert name not in text, f"{name} found in {f.name}"


def test_logger_refuses_game_dir_and_writes_atomically(tmp_path):
    game = tmp_path / "Game"
    (game / "out").mkdir(parents=True)
    with pytest.raises(ValueError):
        JsonLogger(game / "out", game)
    lg = JsonLogger(tmp_path / "out", game)
    assert lg.write({"a": 1}) and json.loads(lg.path.read_text()) == {"a": 1}
    assert not (tmp_path / "out" / "telemetry-state.json.tmp").exists()

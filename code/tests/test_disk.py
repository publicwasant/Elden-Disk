import json
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jsonschema
import pytest

import eldendisk
from eldendisk.game import memory as memory_reader
from eldendisk.game.profile import (EntryLayout, Profile, SpEffectLayout, StateConfig, StateIds, VitalsLayout,
                                    load_profile, load_state_ids)
from eldendisk.reader.export import JsonLogger, build_document
from eldendisk.reader.sampler import Sampler

PKG = Path(eldendisk.__file__).parent
SCHEMA = json.loads((PKG / "reader" / "disk.schema.json").read_text())

BASE, WCM, PLAYER, GD, SP = 0x140000000, 0x200000000, 0x210000000, 0x220000000, 0x230000000
MODULES, DATA_MOD = 0x250000000, 0x260000000
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
    return Profile("ab" * 32, "test", 0x1000, 0x10, 0x580, 0x68, 0x6C, 0x3C, lay,
                   vitals=VitalsLayout(0x190, 0x0, 0x138))


def state_ids():
    return StateIds(
        buffs={
            100: StateConfig("Golden Vow", categories="INCANTATIONS", abilities="Buff"),
            200: StateConfig("Gold Scarab", categories="TALISMANS", abilities="More runes"),
        },
        animations={
            2020210: StateConfig("Sprint", categories="MANNER"),
            68011: StateConfig("Resting", categories="MANNER", abilities="Resets: HP, FP, Stamina, etc."),
        },
    )


def entry(m, addr, eid, dur, timer, nxt):
    m.put(addr, b"\0" * 0x60)  # real entries are contiguous memory
    m.u32(addr + 0x08, eid); m.f32(addr + 0x14, dur); m.f32(addr + 0x10, timer); m.u64(addr + 0x30, nxt)


def world(m, runes=10_008_626, level=386, attrs=(80, 60, 60, 90, 90, 15, 60, 10), head=E1):
    m.u64(BASE + 0x1000, WCM)
    m.u64(WCM + 0x10, PLAYER)
    m.u64(PLAYER + 0x580, GD)
    m.u64(PLAYER + 0x178, SP)
    m.u64(PLAYER + 0x190, MODULES)
    m.u64(MODULES + 0x0, DATA_MOD)
    m.u64(SP + 0x8, head)
    m.u32(GD + 0x68, level); m.u32(GD + 0x6C, runes)
    m.put(GD + 0x3C, struct.pack("<8I", *attrs))

    # hp=890, max_hp=1914, max_uncapped_hp=1914, base_hp=2015
    # fp=350, max_fp=350, base_fp=350
    # stamina=178, max_stamina=178, base_stamina=158
    m.put(DATA_MOD + 0x138, struct.pack("<10i", 890, 1914, 1914, 2015, 350, 350, 350, 178, 178, 158))


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
                          exe_sha256="x", profile_label="test", sample=sample)


@pytest.mark.parametrize("mode", ["remaining", "elapsed"])
def test_connected_sample(mode):
    m = full_world(mode)
    s = Sampler(m, make_profile(mode), state_ids(), BASE)
    r = s.sample(NOW)
    assert r.state == "CONNECTED"
    c = r.character
    assert c["level"] == 386
    assert c["vitals"] == {
        "hit_point": {"current": 890, "maximum": 1914, "base": 2015},
        "focus_point": {"current": 350, "maximum": 350, "base": 350},
        "stamina": {"current": 178, "maximum": 178, "base": 158},
    }
    assert c["runes"] == {
        "total": 10_008_626,
        "baseline": 10_008_626,
        "delta": 0,
    }
    assert c["attributes"]["strength"] == 90 and c["attributes"]["arcane"] == 10
    assert "100" in c["buffs"]
    b = c["buffs"]["100"]
    assert b["name"] == "Golden Vow"
    assert "kind" not in b
    assert b["categories"] == "INCANTATIONS"
    assert b["abilities"] == "Buff"
    assert b["times"]["buff_duration"] == 45.0 and b["times"]["max_duration"] == 80.0
    assert b["times"]["last_activated_at"] == "2026-09-30 11:59:25.000000+00:00"  # now - (80-45), UTC offset always present
    assert "200" in c["buffs"]
    p = c["buffs"]["200"]
    assert p["name"] == "Gold Scarab"
    assert "kind" not in p
    assert p["categories"] == "TALISMANS"
    assert p["abilities"] == "More runes"
    assert "times" not in p
    assert r.ignored_buffs == 1  # id 999 not in tables
    valid(doc_for(s, r))


def test_idle_state_retains_character_data():
    m = full_world()
    s = Sampler(m, make_profile(), state_ids(), BASE)
    r = s.sample(NOW)
    assert r.state == "CONNECTED"
    d = build_document(now=NOW, state="IDLE", pid=1, anti_cheat="DISABLED_OFFLINE",
                       exe_sha256="x", profile_label="test", sample=r)
    assert d["systems"]["status"]["tool_state"] == "IDLE"
    assert d["systems"]["status"]["game_connected"] is True
    assert d["character"] is not None
    assert d["character"]["level"] == 386
    valid(d)


def test_disconnected_state_retains_character_data():
    m = full_world()
    s = Sampler(m, make_profile(), state_ids(), BASE)
    r = s.sample(NOW)
    assert r.state == "CONNECTED"
    d = build_document(now=NOW, state="DISCONNECTED", pid=1, anti_cheat="DISABLED_OFFLINE",
                       exe_sha256="x", profile_label="test", sample=r)
    assert d["systems"]["status"]["tool_state"] == "DISCONNECTED"
    assert d["systems"]["status"]["game_connected"] is False
    assert d["character"] is not None
    assert d["character"]["level"] == 386
    valid(d)


def test_character_retained_across_all_states():
    m = full_world()
    s = Sampler(m, make_profile(), state_ids(), BASE)
    r = s.sample(NOW)
    assert r.state == "CONNECTED"
    cached_char = r.character
    assert cached_char is not None

    for state in ["WAITING_FOR_PROCESS", "EAC_ACTIVE", "EAC_DETECTED", "UNSUPPORTED_VERSION", "WAITING_FOR_WORLD", "DISCONNECTED", "IDLE"]:
        d = build_document(now=NOW, state=state, pid=1, anti_cheat="DISABLED_OFFLINE",
                           exe_sha256="x", profile_label="test",
                           sample=None, last_character=cached_char)
        assert d["systems"]["status"]["tool_state"] == state
        assert d["character"] is not None
        assert d["character"]["level"] == 386
        valid(d)


def test_cold_boot_character_is_null():
    for state in ["WAITING_FOR_PROCESS", "EAC_ACTIVE", "EAC_DETECTED", "UNSUPPORTED_VERSION", "WAITING_FOR_WORLD", "DISCONNECTED"]:
        d = build_document(now=NOW, state=state, pid=None, anti_cheat="UNKNOWN",
                           exe_sha256=None, profile_label=None, buffs_supported=False,
                           sample=None, last_character=None)
        assert d["systems"]["status"]["tool_state"] == state
        assert d["character"] is None
        valid(d)


def test_rune_delta_and_baseline():
    m = full_world()
    s = Sampler(m, make_profile(), state_ids(), BASE)
    s.sample(NOW)  # baseline set to 10_008_626 at NOW

    later = NOW + timedelta(seconds=150)
    m.u32(GD + 0x6C, 10_558_626)  # total: 10_558_626, delta: 550_000
    r = s.sample(later)
    d = doc_for(s, r)
    runes = d["character"]["runes"]
    assert runes["total"] == 10_558_626
    assert runes["baseline"] == 10_008_626
    assert runes["delta"] == 550_000
    valid(d)


def test_grace_reset_baseline():
    from eldendisk.game.profile import AnimLayout, AtGraceConfig
    m = full_world()
    ANIM_MOD, ANIM_SUB = 0x250000000, 0x270000000
    m.u64(PLAYER + 0x190, ANIM_MOD)
    m.u64(ANIM_MOD + 0x18, ANIM_SUB)
    m.u32(ANIM_SUB + 0xC4, 7)  # read_idx = 7
    m.u32(ANIM_SUB + 0x20 + 7 * 0x10, 2020210)  # Sprint animation

    anim_lay = AnimLayout(0x190, 0x18, 0xC4, 0x20, 0x10)
    at_grace_lay = AtGraceConfig("anim", (68011,))
    p = Profile("ab" * 32, "test", 0x1000, 0x10, 0x580, 0x68, 0x6C, 0x3C,
                SpEffectLayout(0x178, 0x8, EntryLayout(0x08, 0x30, 0x14, 0x10, "remaining")),
                anim=anim_lay, vitals=VitalsLayout(0x190, 0x0, 0x138), at_grace=at_grace_lay)
    s = Sampler(m, p, state_ids(), BASE)
    r0 = s.sample(NOW)  # Initial Connect: baseline = 10_008_626
    assert r0.character["animations"] == {"2020210": {"name": "Sprint", "categories": "MANNER"}}
    valid(doc_for(s, r0))

    # Player gains runes in-world (baseline stays frozen)
    m.u32(GD + 0x6C, 10_050_000)
    r1 = s.sample(NOW)
    assert r1.character["runes"]["baseline"] == 10_008_626
    assert r1.character["runes"]["delta"] == 41_374

    # Player sits at Site of Grace (anim_id = 68011) -> triggers baseline reset & freeze
    m.u32(ANIM_SUB + 0x20 + 7 * 0x10, 68011)  # Enter Grace animation!
    m.u32(GD + 0x6C, 10_050_000)
    r2 = s.sample(NOW)
    assert r2.character["runes"]["total"] == 10_050_000
    assert r2.character["runes"]["baseline"] == 10_050_000  # reset to total!
    assert r2.character["runes"]["delta"] == 0
    assert r2.character["animations"] == {"68011": {"name": "Resting", "categories": "MANNER", "abilities": "Resets: HP, FP, Stamina, etc."}}
    valid(doc_for(s, r2))

    # Player exits Grace (anim_id = 0, loading/transitioning) -> animation state remains frozen at Resting (68011)
    m.u32(ANIM_SUB + 0x20 + 7 * 0x10, 0)
    m.u32(GD + 0x6C, 10_070_000)
    r3 = s.sample(NOW)
    assert r3.character["animations"] == {"68011": {"name": "Resting", "categories": "MANNER", "abilities": "Resets: HP, FP, Stamina, etc."}}
    valid(doc_for(s, r3))


def test_null_world_is_silent_waiting():
    m = full_world()
    m.u64(BASE + 0x1000, 0)
    s = Sampler(m, make_profile(), state_ids(), BASE)
    r = s.sample(NOW)
    assert r.state == "WAITING_FOR_WORLD" and r.error is None and r.character is None
    d = doc_for(s, r)
    assert d["character"] is None and d["systems"]["status"]["game_connected"] is False
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
    r = Sampler(m, make_profile(), state_ids(), BASE).sample(NOW)
    assert r.state == "WAITING_FOR_WORLD" and r.character is None and frag in r.error


def test_unreadable_memory_is_not_zero():
    m = full_world()
    for i in range(4):
        del m.b[GD + 0x6C + i]
    r = Sampler(m, make_profile(), state_ids(), BASE).sample(NOW)
    assert r.state == "WAITING_FOR_WORLD" and "read failed" in r.error


def test_cycle_and_bad_pointer_discard():
    m = full_world()
    entry(m, E3, 999, 10.0, 5.0, E1)
    assert "cycle" in Sampler(m, make_profile(), state_ids(), BASE).sample(NOW).error
    m = full_world()
    entry(m, E3, 999, 10.0, 5.0, 0x1234)
    assert "invalid SpEffect entry pointer" in Sampler(m, make_profile(), state_ids(), BASE).sample(NOW).error


def test_list_length_cap():
    m = FakeMem()
    world(m)
    for i in range(513):
        a = 0x300000000 + i * 0x100
        entry(m, a, 5, 1.0, 1.0, a + 0x100)
    m.u64(SP + 0x8, 0x300000000)
    r = Sampler(m, make_profile(), state_ids(), BASE).sample(NOW)
    assert r.state == "WAITING_FOR_WORLD" and "longer than" in r.error


def test_expired_or_bad_timer_ignored():
    m = full_world()
    entry(m, E1, 100, 80.0, 0.0, E2)  # remaining 0 -> not active
    r = Sampler(m, make_profile(), state_ids(), BASE).sample(NOW)
    assert "100" not in r.character["buffs"]


def test_buffs_disabled_when_sp_layout_missing():
    m = full_world()
    r = Sampler(m, make_profile(sp=False), state_ids(), BASE).sample(NOW)
    assert r.state == "CONNECTED" and r.character["buffs"] == {} and r.ignored_buffs == 0


def test_non_connected_states_validate():
    for state in ["WAITING_FOR_PROCESS", "EAC_ACTIVE", "EAC_DETECTED", "UNSUPPORTED_VERSION", "DISCONNECTED", "IDLE"]:
        d = build_document(now=NOW, state=state, pid=None, anti_cheat="UNKNOWN", exe_sha256=None,
                           profile_label=None, buffs_supported=False, sample=None, note="x")
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
    "vitals": {"player_to_modules": "0x190", "modules_to_data": "0x0", "data_to_vitals": "0x138"},
}


def test_profile_ok_and_hex(tmp_path):
    p = write_json(tmp_path, "o.json", {"profiles": {"AB" * 32: FULL}})
    prof, why = load_profile(p, "ab" * 32)
    assert why is None and prof.world_chr_man_rva == 0x3D5E700 and prof.runes == 0x6C
    assert prof.sp_effect.entry.timer_mode == "elapsed"
    assert prof.vitals.player_to_modules == 0x190 and prof.vitals.data_to_vitals == 0x138


def test_vitals_invalid_memory_discards_sample():
    m = full_world()
    m.put(DATA_MOD + 0x138, struct.pack("<10i", 890, 0, 1914, 2015, 350, 350, 350, 178, 178, 158))
    r = Sampler(m, make_profile(), state_ids(), BASE).sample(NOW)
    assert r.state == "WAITING_FOR_WORLD" and "invalid HP vitals" in r.error


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


def test_state_ids_loader(tmp_path):
    assert load_state_ids(tmp_path / "missing.json") == StateIds({}, {})
    p = write_json(tmp_path, "e.json", {"buffs": {"_readme": "x", "100": {"name": "A", "categories": "CONSUMABLES"},
                                                  "200": {"name": "P", "categories": "TALISMANS", "abilities": "up"}},
                                        "animations": {"100": {"name": "Same number, another table"}}})
    e = load_state_ids(p)
    assert e.buffs[100].name == "A" and e.buffs[200].categories == "TALISMANS" and e.buffs[200].abilities == "up"
    assert e.animations[100].name == "Same number, another table" and 100 in e.buffs      # two tables: no clash
    only = write_json(tmp_path, "only.json", {"buffs": {"1": {"name": "B"}}})
    assert load_state_ids(only).animations == {}


@pytest.mark.parametrize("content", [
    {"1": {"name": "x", "sources": "EFFECTS"}},                  # the 1.6.2 flat shape: not read as if it were new
    {"buffs": {"1": "NOT_AN_OBJECT"}}, {"buffs": {"1": {"abilities": "no name"}}}, {"buffs": [1]}, [],
])
def test_a_malformed_state_ids_file_is_an_error(tmp_path, content):
    with pytest.raises(ValueError, match="malformed"):
        load_state_ids(write_json(tmp_path, "bad.json", content))


def test_the_flat_file_error_says_how_to_convert_it(tmp_path):
    with pytest.raises(ValueError, match="convert_state_ids"):
        load_state_ids(write_json(tmp_path, "old.json", {"100": {"name": "A", "sources": "EFFECTS"}}))


def test_the_shipped_chr_state_ids_json_loads_and_has_no_sources():
    path = Path(eldendisk.__file__).parent.parent / "chr_state_ids.json"
    ids = load_state_ids(path)
    assert ids.buffs and ids.animations
    assert "sources" not in path.read_text(encoding="utf-8")


# ---- safety ----
def test_write_capability_is_confined_to_the_writer_package():
    """game/memory.py stays read-only; WriteProcessMemory / PROCESS_VM_WRITE exist in one module (writer/writer.py)."""
    assert memory_reader.ACCESS_MASK == 0x1010
    never = ["VirtualAllocEx", "CreateRemoteThread", "VirtualProtectEx", "NtWriteVirtualMemory", "SetThreadContext"]
    writer_py = PKG / "writer" / "writer.py"
    for f in PKG.rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        rel = f.relative_to(PKG).as_posix()
        for name in never:
            assert name not in text, f"{name} found in {rel}"
        if f != writer_py:
            assert "WriteProcessMemory" not in text, f"WriteProcessMemory found in {rel}"
            assert "PROCESS_VM_WRITE" not in text, f"PROCESS_VM_WRITE found in {rel}"
        if rel not in ("writer/writer.py", "commands/write.py"):
            assert "WritableProcessMemory" not in text, f"{rel} must not use the write handle"


def test_logger_refuses_game_dir_and_writes_atomically(tmp_path):
    game = tmp_path / "Game"
    (game / "out").mkdir(parents=True)
    with pytest.raises(ValueError):
        JsonLogger(game / "out", game)
    lg = JsonLogger(tmp_path / "out", game)
    assert lg.write({"a": 1}) and json.loads(lg.path.read_text()) == {"a": 1}
    assert not (tmp_path / "out" / "disk-state.json.tmp").exists()


def test_raw_buffs_lists_everything_unclassified():
    m = full_world()
    entries, err = Sampler(m, make_profile(), state_ids(), BASE).raw_buffs()
    assert err is None and [e[0] for e in entries] == [100, 200, 999]
    m.u64(BASE + 0x1000, 0)  # title screen
    entries, err = Sampler(m, make_profile(), state_ids(), BASE).raw_buffs()
    assert entries is None
    entries, err = Sampler(m, make_profile(sp=False), state_ids(), BASE).raw_buffs()
    assert entries is None and "sp_effect" in err

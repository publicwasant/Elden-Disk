"""`read` (the whole document or names), `export`, once or --live; read-only (spec 1.6.2 section 5; 1.8.0 part 2 names)."""
import argparse
import dataclasses
import json
import re

import pytest

import eldendisk.commands.read as rcmd
from eldendisk.game.attach import EXIT_EAC, AttachError, Target
from eldendisk.game.memory import Module
from eldendisk.game.profile import AnimLayout
from eldendisk.vault import SaveVault, SessionState
from tests.test_disk import BASE, GD, state_ids, full_world, make_profile

EXE_SHA = "ab" * 32
HOST_PID, HOST_STARTED, GAME_PID, GAME_STARTED = 100, 555, 4242, 777


class LiveMem:
    """FakeMem that stays alive for `ticks` liveness checks, then reports the game gone."""
    def __init__(self, ticks=3):
        self.m, self.ticks, self.closed = full_world(), ticks, 0
        self.m.u64(0x250000000 + 0x18, 0x270000000)         # animation sub-module
        self.m.u32(0x270000000 + 0xC4, 7)                    # read index
        self.m.u32(0x270000000 + 0x20 + 7 * 0x10, 2020210)   # Sprint

    def read(self, addr, size): return self.m.read(addr, size)

    def alive(self):
        self.ticks -= 1
        return self.ticks >= 0

    def close(self): self.closed += 1


@pytest.fixture
def rig(tmp_path, monkeypatch):
    mem = LiveMem()
    target = Target(GAME_PID, GAME_STARTED, Module("eldenring.exe", BASE, str(tmp_path / "game" / "eldenring.exe")),
                    EXE_SHA, dataclasses.replace(make_profile(), anim=AnimLayout(0x190, 0x18, 0xC4, 0x20, 0x10)))
    box = {"locate": lambda offsets: target, "eac": False, "active": True, "sleeps": 0}

    def fake_sleep(s): box["sleeps"] += 1

    monkeypatch.setattr(rcmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(rcmd, "locate", lambda offsets: box["locate"](offsets))
    monkeypatch.setattr(rcmd, "open_read", lambda t: mem)
    monkeypatch.setattr(rcmd, "load_state_ids", lambda p: state_ids())
    monkeypatch.setattr(rcmd, "eac_loaded", lambda pid: box["eac"])
    monkeypatch.setattr(rcmd, "is_window_active", lambda pid: box["active"])
    monkeypatch.setattr(rcmd, "process_started",
                        lambda pid: {HOST_PID: HOST_STARTED, GAME_PID: GAME_STARTED}.get(pid))
    monkeypatch.setattr(rcmd.time, "sleep", fake_sleep)

    def args(**kw):
        d = dict(query=None, export=False, live=False, live_buffs=False, live_animations=False, json=False,
                 timeout=1.0, offsets="x", state_ids="y", vault=str(tmp_path / "vault"), hz=60.0, quiet=False,
                 mapped=False, unmapped=False, flat=False, probe_params=False, param=None, param_check=None, no_idle=True, out=str(tmp_path / "out"), export_interval=0.0, timer_interval=0.0, verbose=False)
        return argparse.Namespace(**{**d, **kw})

    return tmp_path, mem, target, box, args


def doc(tmp_path):
    return json.loads((tmp_path / "out" / "disk.json").read_text())


# ---- one-shot: print and --query ----
def test_no_flag_prints_every_value_once_and_exits(rig, capsys):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args()) == 0
    out = capsys.readouterr().out
    assert "character" in out and "level" in out and "386" in out and "10,008,626" in out
    assert "hit_point" in out and "systems" in out
    assert mem.closed == 1 and box["sleeps"] == 0 and not (tmp / "out").exists()   # nothing written, no loop


def test_query_a_group_a_value_and_a_pattern(rig, capsys):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(query="runes")) == 0
    out = capsys.readouterr().out
    assert [l.strip() for l in out.splitlines()[:2]] == ["character", "runes"] and "10,008,626" in out
    assert rcmd.cmd_read(args(query="hp")) == 0
    out = capsys.readouterr().out
    assert "hit_point" in out and "1,914" in out and "2,015" in out   # current, maximum, base
    assert rcmd.cmd_read(args(query="character.attributes.strength")) == 0
    assert capsys.readouterr().out.split() == ["character.attributes.strength", "90"]
    assert rcmd.cmd_read(args(query="attrs.*")) == 0
    out = capsys.readouterr().out
    assert [l.strip() for l in out.splitlines()[:2]] == ["character", "attributes"]      # the same tree as `read`
    assert re.search(r"\barcane\s+10\n", out) and "character." not in out
    assert rcmd.cmd_read(args(query=["runes", "attrs.vigor", "level"])) == 0
    out = capsys.readouterr().out
    assert out.count("character\n") == 1 and "runes" in out and "vigor" in out and "level" in out and "hit_point" not in out


def test_query_json_is_the_value_alone(rig, capsys):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(query="runes", json=True)) == 0
    got = json.loads(capsys.readouterr().out)
    assert got == {"character.runes": {"total": 10_008_626, "baseline": 10_008_626, "delta": 0}}
    assert rcmd.cmd_read(args(json=True)) == 0
    assert json.loads(capsys.readouterr().out)["character"]["level"] == 386


def test_an_unknown_name_is_an_error_with_a_suggestion(rig, capsys):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(query="vigr")) == 1
    err = capsys.readouterr().err
    assert "unknown name 'vigr'" in err and "character.attributes.vigor" in err
    assert mem.closed == 1


def test_one_shot_gives_up_after_the_timeout_when_there_is_no_world(rig, capsys):
    tmp, mem, target, box, args = rig
    mem.m = type(mem.m)()            # title screen: the pointer chain ends in nothing
    mem.ticks = 10**6
    assert rcmd.cmd_read(args(timeout=0.05)) == 1
    assert "no loaded world after 0.05 s" in capsys.readouterr().err and mem.closed == 1


def test_one_shot_does_not_wait_for_ever_for_the_game(rig, capsys):
    tmp, mem, target, box, args = rig

    def locate(offsets):
        raise AttachError("eldenring.exe is not running")

    box["locate"] = locate
    assert rcmd.cmd_read(args(timeout=0.05)) == 1
    assert "not running" in capsys.readouterr().err


# ---- --export ----
def test_export_writes_one_document_and_stops(rig, capsys):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(export=True)) == 0
    d = doc(tmp)
    assert d["systems"]["status"]["tool_state"] == "CONNECTED" and d["character"]["level"] == 386
    assert d["systems"]["session"] == {"mode": "telemetry", "read_only": True, "creative": False}
    err = capsys.readouterr().err
    assert "disk.json" in err and "KB" in err and "written to" in err
    assert mem.closed == 1 and box["sleeps"] == 0                     # no loop


def test_export_is_labelled_while_a_valid_session_covers_this_game(rig):
    tmp, mem, target, box, args = rig
    live = tmp / "live" / "1"
    live.mkdir(parents=True)
    (live / "ER0000.sl2").write_bytes(b"save")
    vault = SaveVault(tmp / "vault")
    vault.write_session(vault.new_record(vault.snapshot(live), live, exe_sha256=EXE_SHA,
                                         host_pid=HOST_PID, host_started=HOST_STARTED))
    assert rcmd._in_session(vault.root, target) is False              # READY: the game has not been recorded yet
    vault.update_session(state=SessionState.RUNNING, game_pid=GAME_PID, game_started=GAME_STARTED)
    assert rcmd._in_session(vault.root, target) is True
    assert rcmd.cmd_read(args(export=True)) == 0
    assert doc(tmp)["systems"]["session"]["creative"] is True
    vault.update_session(game_pid=1)                                  # another game process: no longer this session
    assert rcmd._in_session(vault.root, target) is False


def test_export_never_lands_in_the_game_folder(rig):
    tmp, mem, target, box, args = rig
    (tmp / "game").mkdir()
    with pytest.raises(Exception):
        rcmd.cmd_read(args(export=True, out=str(tmp / "game")))


def test_an_unavailable_vault_stops_the_export_but_not_a_query(rig, monkeypatch, capsys):
    from eldendisk.vault import VaultError

    def gone(explicit, **kw):
        raise VaultError("the remembered vault is not available")

    tmp, mem, target, box, args = rig
    monkeypatch.setattr(rcmd, "resolve_vault", gone)
    assert rcmd.cmd_read(args(export=True)) == 1
    assert rcmd.cmd_read(args(query="level")) == 0
    err = capsys.readouterr().err
    assert err.count("not available") == 2


def test_live_export_keeps_writing_and_ends_with_the_last_state(rig):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(export=True, live=True)) == 0
    assert doc(tmp)["systems"]["status"]["tool_state"] == "DISCONNECTED"
    assert box["sleeps"] >= 2 and mem.closed == 1


def test_idle_window_emits_idle_in_a_live_export(rig):
    tmp, mem, target, box, args = rig
    box["active"] = False
    mem.ticks = 2
    rcmd.cmd_read(args(export=True, live=True, no_idle=False))
    assert doc(tmp)["systems"]["status"]["tool_state"] in ("IDLE", "DISCONNECTED")


def test_eac_appearing_stops_reading(rig, monkeypatch, capsys):
    tmp, mem, target, box, args = rig
    monkeypatch.setattr(rcmd, "RESCAN_S", 0.0)
    box["eac"] = True
    mem.ticks = 10**6
    assert rcmd.cmd_read(args(export=True, live=True)) == EXIT_EAC
    assert doc(tmp)["systems"]["status"]["tool_state"] == "EAC_DETECTED"
    assert "EasyAntiCheat" in capsys.readouterr().err


def test_ctrl_c_leaves_the_game_alone_and_still_writes_the_final_document(rig, monkeypatch):
    tmp, mem, target, box, args = rig
    mem.ticks = 10**6
    n = {"i": 0}

    def sleep(s):
        n["i"] += 1
        if n["i"] == 3:
            raise KeyboardInterrupt

    monkeypatch.setattr(rcmd.time, "sleep", sleep)
    assert rcmd.cmd_read(args(export=True, live=True)) == 130
    assert doc(tmp)["systems"]["status"]["tool_state"] in ("CONNECTED", "DISCONNECTED")
    assert mem.closed == 1


# ---- --live ----
def test_live_query_prints_once_then_only_what_changed(rig, monkeypatch, capsys):
    tmp, mem, target, box, args = rig
    mem.ticks = 6
    n = {"i": 0}

    def sleep(s):
        n["i"] += 1
        if n["i"] == 2:
            mem.m.u32(GD + 0x68, 387)         # the player levels up

    monkeypatch.setattr(rcmd.time, "sleep", sleep)
    assert rcmd.cmd_read(args(query="level", live=True)) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].split() == ["character.level", "386"]
    changes = [l for l in out[1:] if "character.level" in l]
    assert len(changes) == 1 and "386 \u2192 387" in changes[0]
    assert mem.closed == 1


def test_live_without_a_name_follows_every_value(rig, capsys):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(live=True)) == 0
    out = capsys.readouterr().out
    assert "character" in out and "hit_point" in out and "10,008,626" in out


def test_the_whole_views_show_buffs_and_animations_like_the_export(rig, capsys):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(export=True)) == 0
    lists = doc(tmp)["character"]
    assert lists["buffs"] and "animations" in lists
    ids = list(lists["buffs"])
    for kw in (dict(), dict(live=True)):
        capsys.readouterr()
        assert rcmd.cmd_read(args(**kw)) == 0
        out = capsys.readouterr().out
        assert "hit_point" in out and "buffs" in out and "animations" in out
        assert all(i in out.split() for i in ids)


def test_live_on_a_terminal_redraws_in_place_and_highlights_what_changed(rig, monkeypatch, capsys):
    import os
    monkeypatch.setattr(rcmd.ui, "can_redraw", lambda stream=None: True)
    monkeypatch.setattr(rcmd.ui.shutil, "get_terminal_size", lambda fallback=None: os.terminal_size((100, 60)))
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)
    tmp, mem, target, box, args = rig
    mem.ticks = 8
    clock = {"t": 100.0}
    monkeypatch.setattr(rcmd.time, "monotonic", lambda: clock["t"])
    n = {"i": 0}

    def sleep(s):
        clock["t"] += 0.05
        n["i"] += 1
        if n["i"] == 2:
            mem.m.u32(GD + 0x68, 387)

    monkeypatch.setattr(rcmd.time, "sleep", sleep)
    assert rcmd.cmd_read(args(live=True)) == 0
    out = capsys.readouterr().out
    assert out.startswith("\x1b[?25l") and out.endswith("\x1b[?25h")
    assert "\x1b[1;33m387\x1b[0m" in out                      # the new level, highlighted
    assert "386 \u2192 387" not in out                        # no change stream on a terminal
    assert out.count("level") >= 2 and "A\r" in out           # drawn again, in place (cursor up, carriage return)


def test_the_lists_can_be_queried_by_name(rig, capsys):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(export=True)) == 0
    ids = list(doc(tmp)["character"]["buffs"])
    capsys.readouterr()
    assert rcmd.cmd_read(args(query="character.buffs.*")) == 0
    out = capsys.readouterr().out
    assert any(i in out for i in ids) and "level" not in out
    assert rcmd.cmd_read(args(query="animations")) == 0
    assert capsys.readouterr().out.strip()
    assert rcmd.cmd_read(args(query="buffs", live=True)) == 0
    assert any(i in capsys.readouterr().out for i in ids)


def test_live_with_an_unknown_name_stops_before_the_loop(rig, capsys):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(query="nonsense", live=True)) == 1
    assert "unknown name" in capsys.readouterr().err and box["sleeps"] == 0


# ---- --live-buffs / --live-animations ----
def _lines(out, prefix):
    return [l for l in out.splitlines() if l.startswith(prefix)]


def test_live_buffs_without_a_terminal_prints_each_id_once_with_its_name(rig, capsys):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(live_buffs=True)) == 0
    out = capsys.readouterr().out
    plus = _lines(out, "+")
    assert [l.split()[1] for l in plus] == ["100", "200", "999"]
    assert "Golden Vow" in plus[0] and "45.0 / 80.0 s" in plus[0] and "permanent" in plus[1]
    assert "Unknown" in plus[2] and re.search(r"\d\d:\d\d:\d\d\.\d{3}$", plus[2]) and "+07" not in out
    assert mem.closed == 1


def test_mapped_and_unmapped_filter_the_ids(rig, capsys):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(live_buffs=True, unmapped=True)) == 0
    assert [l.split()[1] for l in _lines(capsys.readouterr().out, "+")] == ["999"]
    mem.ticks = 3
    assert rcmd.cmd_read(args(live_buffs=True, mapped=True)) == 0
    assert [l.split()[1] for l in _lines(capsys.readouterr().out, "+")] == ["100", "200"]


def test_both_monitors_share_one_process_and_are_prefixed(rig, capsys):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(live_buffs=True, live_animations=True)) == 0
    out = capsys.readouterr().out
    assert "[buffs] Format:" in out and "[animations] Format:" in out and out.count("[buffs] Format:") == 1
    assert any(l.startswith("[animations] + ") and "Sprint" in l for l in out.splitlines())
    assert any(l.startswith("[buffs] + ") and "Golden Vow" in l for l in out.splitlines())


def test_on_a_terminal_the_monitors_draw_one_table_each_in_place(rig, monkeypatch, capsys):
    import os
    monkeypatch.setattr(rcmd.ui, "can_redraw", lambda stream=None: True)
    monkeypatch.setattr(rcmd.ui.shutil, "get_terminal_size", lambda fallback=None: os.terminal_size((100, 40)))
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(live_buffs=True, live_animations=True)) == 0
    out = capsys.readouterr().out
    assert out.startswith("\x1b[?25l") and out.endswith("\x1b[?25h")
    assert "buffs   3 active \u00b7 3 seen \u00b7 1 unmapped" in out and "animations   1 active \u00b7 1 seen" in out
    assert "Golden Vow" in out and "Unknown" in out and "Sprint" in out
    assert not _lines(out, "+") and "Format:" not in out       # nothing is printed as a stream


def test_names_json_is_reloaded_when_it_changes(rig, monkeypatch, capsys):
    tmp, mem, target, box, args = rig
    names = tmp / "names.json"
    names.write_text(json.dumps({"buffs": {"100": {"name": "Golden Vow"}}}), encoding="utf-8")
    mem.ticks = 6
    from eldendisk.game.profile import load_state_ids as real_load
    monkeypatch.setattr(rcmd, "load_state_ids", real_load)   # the rig fakes it; this test reads real files
    clock = {"t": 100.0}
    monkeypatch.setattr(rcmd.time, "monotonic", lambda: clock["t"])
    n = {"i": 0}

    def sleep(s):
        clock["t"] += 2.5
        n["i"] += 1
        if n["i"] == 1:
            names.write_text(json.dumps({"buffs": {"100": {"name": "Golden Vow"}, "999": {"name": "Found It"}, "x": 1}}),
                             encoding="utf-8")
        if n["i"] == 2:
            names.write_text(json.dumps({"buffs": {"100": {"name": "Golden Vow"}, "999": {"name": "Found It"}},
                                         "animations": {"7": {"name": "Walk"}}}), encoding="utf-8")

    monkeypatch.setattr(rcmd.time, "sleep", sleep)
    assert rcmd.cmd_read(args(live_buffs=True, state_ids=str(names), unmapped=False)) == 0
    err = capsys.readouterr().err
    assert "changed but cannot be read" in err and "names.json reloaded (2 buffs, 1 animations)" in err


def test_an_old_flat_names_file_is_a_clear_error_before_the_game_is_looked_for(rig, monkeypatch, capsys):
    tmp, mem, target, box, args = rig
    names = tmp / "names.json"
    names.write_text(json.dumps({"100": {"name": "Golden Vow", "sources": "EFFECTS"}}), encoding="utf-8")
    from eldendisk.game.profile import load_state_ids as real_load
    monkeypatch.setattr(rcmd, "load_state_ids", real_load)
    box["locate"] = lambda offsets: pytest.fail("the game must not be looked for")
    for kw in ({}, {"live_buffs": True}):
        assert rcmd.cmd_read(args(state_ids=str(names), **kw)) == 1
        err = capsys.readouterr().err
        assert "malformed" in err and "convert_state_ids" in err


def test_waits_for_the_game_instead_of_failing_when_live(rig, capsys):
    tmp, mem, target, box, args = rig
    calls = {"n": 0}

    def locate(offsets):
        calls["n"] += 1
        if calls["n"] < 3:
            raise AttachError("eldenring.exe is not running")
        return target

    box["locate"] = locate
    assert rcmd.cmd_read(args(live_buffs=True)) == 0
    cap = capsys.readouterr()
    assert calls["n"] == 3 and cap.err.count("waiting for eldenring.exe") == 1 and box["sleeps"] >= 2


def test_other_attach_errors_end_the_command(rig, capsys):
    tmp, mem, target, box, args = rig

    def locate(offsets):
        raise AttachError("unsupported eldenring.exe", 2)

    box["locate"] = locate
    assert rcmd.cmd_read(args(export=True)) == 2


def test_an_unsupported_monitor_is_refused_before_any_output(rig, capsys):
    tmp, mem, target, box, args = rig
    box["locate"] = lambda offsets: dataclasses.replace(target, profile=make_profile())   # no anim layout
    assert rcmd.cmd_read(args(live_animations=True)) == 1
    assert "animations: anim layout incomplete" in capsys.readouterr().err
    assert mem.closed == 1


def test_read_never_opens_a_writable_handle():
    import inspect
    src = inspect.getsource(rcmd)
    assert "Writable" not in src and "write_process" not in src.lower()


# ---- a list that is empty right now is not a wrong name ----

def test_a_list_name_with_nothing_active_is_empty_not_unknown():
    from eldendisk.reader import view
    from eldendisk.game.values import UnknownName
    d = {"systems": {}, "character": {"level": 1, "buffs": {}, "animations": {}}}
    assert view.select(d, "character.buffs.*") == []
    assert view.select(d, "animations.*") == []
    assert view.select(d, "character.buffs.311100.name") == []
    with pytest.raises(UnknownName):
        view.select(d, "character.effectz.*")


def test_live_query_of_a_list_survives_the_last_effect_ending(rig, monkeypatch, capsys):
    tmp, mem, target, box, args = rig
    mem.ticks = 6
    gone = {"on": False}
    real = rcmd.ExportWriter.build

    def build(self, state, sample):
        d = real(self, state, sample)
        if gone["on"]:
            d["character"]["buffs"] = {}
        return d

    monkeypatch.setattr(rcmd.ExportWriter, "build", build)
    n = {"i": 0}

    def sleep(s):
        n["i"] += 1
        if n["i"] == 2:
            gone["on"] = True

    monkeypatch.setattr(rcmd.time, "sleep", sleep)
    assert rcmd.cmd_read(args(query="character.buffs.*", live=True)) == 0
    cap = capsys.readouterr()
    assert "unknown name" not in cap.err
    assert "→ -" in cap.out        # what was active is shown as gone, the loop kept running


def test_one_shot_query_of_an_empty_list_says_so_and_succeeds(rig, monkeypatch, capsys):
    tmp, mem, target, box, args = rig
    real = rcmd.ExportWriter.build

    def build(self, state, sample):
        d = real(self, state, sample)
        d["character"]["buffs"] = {}
        return d

    monkeypatch.setattr(rcmd.ExportWriter, "build", build)
    assert rcmd.cmd_read(args(query="character.buffs.*")) == 0
    assert "nothing matches" in capsys.readouterr().err


# ---- --flat ----

def test_flat_prints_one_full_path_row_per_value(rig, capsys):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(query=["character.runes.*", "attrs.vigor"], flat=True)) == 0
    lines = capsys.readouterr().out.splitlines()
    assert [l.split()[0] for l in lines] == ["character.runes.total", "character.runes.baseline", "character.runes.delta",
                                              "character.attributes.vigor"]
    assert all(re.match(r"^ character\.\S+\s{2,}\S", l) for l in lines)       # no headings, values aligned
    assert rcmd.cmd_read(args(flat=True)) == 0           # no name: every value of the document, flat
    out = capsys.readouterr().out
    assert " character.level " in out and not any(l.strip() in ("character", "systems") for l in out.splitlines())


def test_flat_live_without_a_terminal_prints_the_flat_rows_then_changes(rig, monkeypatch, capsys):
    tmp, mem, target, box, args = rig
    mem.ticks = 4
    n = {"i": 0}

    def sleep(s):
        n["i"] += 1
        if n["i"] == 2:
            mem.m.u32(GD + 0x68, 387)

    monkeypatch.setattr(rcmd.time, "sleep", sleep)
    assert rcmd.cmd_read(args(query=["level"], flat=True, live=True)) == 0
    out = capsys.readouterr().out
    assert "character.level" in out and "386 \u2192 387" in out


def test_flat_live_on_a_terminal_redraws_the_flat_rows(rig, monkeypatch, capsys):
    import os
    monkeypatch.setattr(rcmd.ui, "can_redraw", lambda stream=None: True)
    monkeypatch.setattr(rcmd.ui.shutil, "get_terminal_size", lambda fallback=None: os.terminal_size((100, 60)))
    monkeypatch.setenv("NO_COLOR", "1")
    tmp, mem, target, box, args = rig
    mem.ticks = 3
    assert rcmd.cmd_read(args(query=["runes.*"], flat=True, live=True)) == 0
    out = capsys.readouterr().out
    assert "character.runes.total" in out and "\n runes\n" not in out and "\n character\n" not in out


# ---- a loading screen in --live ----

def _loading_screen(rig, monkeypatch, gone_at=2, back_at=4, ticks=40):
    tmp, mem, target, box, args = rig
    mem.ticks = ticks
    world, n = mem.m, {"i": 0}

    def sleep(s):
        n["i"] += 1
        if n["i"] == gone_at:
            mem.m = type(world)()          # warp / death: the pointer chain ends in nothing
        elif n["i"] == back_at:
            mem.m = world

    monkeypatch.setattr(rcmd.time, "sleep", sleep)
    return args


def test_live_on_a_terminal_keeps_the_tree_in_place_over_a_loading_screen(rig, monkeypatch, capsys):
    import os
    monkeypatch.setattr(rcmd.ui, "can_redraw", lambda stream=None: True)
    monkeypatch.setattr(rcmd.ui.shutil, "get_terminal_size", lambda fallback=None: os.terminal_size((100, 60)))
    monkeypatch.setenv("NO_COLOR", "1")
    args = _loading_screen(rig, monkeypatch)
    clock = {"t": 100.0}
    monkeypatch.setattr(rcmd.time, "monotonic", lambda: clock["t"])
    real_sleep = rcmd.time.sleep
    monkeypatch.setattr(rcmd.time, "sleep", lambda s: (clock.__setitem__("t", clock["t"] + 0.05), real_sleep(s)))
    assert rcmd.cmd_read(args(query=["runes"], live=True)) == 0
    cap = capsys.readouterr()
    assert "waiting for a loaded world …" in cap.out and "total" in cap.out.split("waiting for a loaded world")[0]
    assert "total" in cap.out.rsplit("waiting for a loaded world", 1)[1]          # drawn again over it afterwards
    assert cap.out.count("\x1b[?25l") == 1                                        # one drawing session, never detached
    assert "waiting for a loaded world" not in cap.err and "world loaded" not in cap.err   # not printed as events


def test_live_without_a_terminal_still_reports_the_loading_screen_as_events(rig, monkeypatch, capsys):
    args = _loading_screen(rig, monkeypatch)
    assert rcmd.cmd_read(args(query=["level"], live=True)) == 0
    err = capsys.readouterr().err
    assert err.count("waiting for a loaded world") == 1 and err.count("world loaded") == 1


def test_live_on_a_terminal_paints_buff_countdowns_in_their_own_colour(rig, monkeypatch, capsys):
    import os
    monkeypatch.setattr(rcmd.ui, "can_redraw", lambda stream=None: True)
    monkeypatch.setattr(rcmd.ui.shutil, "get_terminal_size", lambda fallback=None: os.terminal_size((100, 200)))
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)
    tmp, mem, target, box, args = rig
    mem.ticks = 5
    assert rcmd.cmd_read(args(query=["character.buffs.*"], live=True)) == 0
    out = capsys.readouterr().out
    assert re.search(r"buff_duration\s*\x1b\[0m\s+\x1b\[35m45\.00\x1b\[0m", out)          # the countdown
    assert re.search(r"max_duration\s*\x1b\[0m\s+80\.00\n", out)                          # a constant beside it stays plain


# ---- game params (spec 1.6.3) ----
from tests import paramfile as pf   # noqa: E402
from tests.test_disk import valid   # noqa: E402

BF = "params.effects.1621000"


@pytest.fixture
def prig(rig):
    """The same rig, with a param file in the game's memory and a profile that knows about it."""
    tmp, mem, target, box, args = rig
    pf.build_file(mem.m, pf.small_ids(), rows={pf.ROWS["black_flame"]: pf.row_bytes(effect_endurance=-1.0)})
    pf.wire(mem.m, 0)
    prof = dataclasses.replace(target.profile, params=pf.params_profile().params)
    box["locate"] = lambda offsets: dataclasses.replace(target, profile=prof)
    return tmp, mem, target, box, args


def test_query_a_params_value_and_a_group(prig, capsys):
    tmp, mem, target, box, args = prig
    assert rcmd.cmd_read(args(query=f"{BF}.effectEndurance")) == 0
    assert capsys.readouterr().out.split() == [f"{BF}.effectEndurance", "-1.0"]
    assert rcmd.cmd_read(args(query=f"{BF}.vfxId")) == 0
    assert capsys.readouterr().out.split() == [f"{BF}.vfxId", "9010"]
    assert rcmd.cmd_read(args(query="PARAMS.effects.1625000")) == 0
    out = capsys.readouterr().out
    assert [l.strip() for l in out.splitlines()[:3]] == ["params", "effects", "1625000"]
    assert re.search(r"\bname\s+Black Flame Ritual\n", out) and re.search(r"\beffectEndurance\s+2\.0\n", out) and re.search(r"\bvfxId\s+9010\n", out)
    assert rcmd.cmd_read(args(query=[f"{BF}.effectEndurance", "level"])) == 0
    assert "level" in capsys.readouterr().out


def test_query_with_a_pattern_and_in_json(prig, capsys):
    tmp, mem, target, box, args = prig
    assert rcmd.cmd_read(args(query="params.effects.*.effectEndurance", flat=True)) == 0
    rows = [l.split() for l in capsys.readouterr().out.splitlines()]
    assert [r[0] for r in rows] == [f"params.effects.{i}.effectEndurance" for i in pf.ROWS.values()]
    assert [r[1] for r in rows] == ["-1.0", "2.0", "2.0", "2.0"]
    assert rcmd.cmd_read(args(query=f"{BF}", json=True)) == 0
    assert json.loads(capsys.readouterr().out)[BF]["effectEndurance"] == -1.0


def test_no_flag_prints_the_params_too_and_character_stars_do_not(prig, capsys):
    tmp, mem, target, box, args = prig
    assert rcmd.cmd_read(args()) == 0
    out = capsys.readouterr().out
    assert "params" in out and "1621000" in out and "Scouring Black Flame" in out
    assert rcmd.cmd_read(args(query="character.*")) == 0
    assert "params" not in capsys.readouterr().out


def test_the_export_has_the_params_block_and_it_is_valid(prig):
    tmp, mem, target, box, args = prig
    assert rcmd.cmd_read(args(export=True)) == 0
    d = doc(tmp)
    valid(d)
    assert list(d) == ["systems", "character", "params", "creative"] and d["creative"] is None      # no build, no host, no flags here
    assert d["params"]["effects"]["1621000"] == {"name": "Black Flame", "effectEndurance": -1.0, "motionInterval": 0.1, "changeHpRate": 0.1,
                                                      "changeHpPoint": 1, "atkOccurrenceSpEffectId": -1, "vfxId": 9010}
    assert d["params"]["effects"]["1623000"]["effectEndurance"] == 2.0


def test_params_that_cannot_be_read_are_a_clear_error_and_the_rest_still_works(prig, capsys):
    tmp, mem, target, box, args = prig
    mem.m.put(pf.HEAD + 0x30, b"\0" * 8)                   # the file no longer looks like a param file
    assert rcmd.cmd_read(args(query=f"{BF}.effectEndurance")) == 1
    err = capsys.readouterr().err
    assert "params cannot be read" in err and "data start" in err
    assert rcmd.cmd_read(args(query="level")) == 0
    assert rcmd.cmd_read(args(export=True)) == 0
    assert doc(tmp)["params"] is None and doc(tmp)["character"]["level"] == 386


def test_a_game_version_without_params_says_so(rig, capsys):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(query=f"{BF}.effectEndurance")) == 1
    assert "no params block in offsets.json" in capsys.readouterr().err
    assert rcmd.cmd_read(args(query="level")) == 0

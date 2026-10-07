"""`read`: print / --query / --export once, or --live; read-only (spec 1.6.2 section 5)."""
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
from tests.test_disk import BASE, GD, effects, full_world, make_profile

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
    monkeypatch.setattr(rcmd, "load_effects", lambda p: effects())
    monkeypatch.setattr(rcmd, "eac_loaded", lambda pid: box["eac"])
    monkeypatch.setattr(rcmd, "is_window_active", lambda pid: box["active"])
    monkeypatch.setattr(rcmd, "process_started",
                        lambda pid: {HOST_PID: HOST_STARTED, GAME_PID: GAME_STARTED}.get(pid))
    monkeypatch.setattr(rcmd.time, "sleep", fake_sleep)

    def args(**kw):
        d = dict(query=None, export=False, live=False, live_effects=False, live_animations=False, json=False,
                 timeout=1.0, offsets="x", effects="y", vault=str(tmp_path / "vault"), hz=60.0, quiet=False,
                 mapped=False, unmapped=False, flat=False, no_idle=True, out=str(tmp_path / "out"), export_interval=0.0, timer_interval=0.0, verbose=False)
        return argparse.Namespace(**{**d, **kw})

    return tmp_path, mem, target, box, args


def doc(tmp_path):
    return json.loads((tmp_path / "out" / "disk-state.json").read_text())


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
    assert d["systems"]["session"] == {**d["systems"]["session"], "read_only": True, "sandbox": False}
    err = capsys.readouterr().err
    assert "disk-state.json" in err and "KB" in err and "written to" in err
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
    assert doc(tmp)["systems"]["session"]["sandbox"] is True
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


def test_the_whole_views_show_effects_and_animations_like_the_export(rig, capsys):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(export=True)) == 0
    lists = doc(tmp)["character"]
    assert lists["effects"] and "animations" in lists
    ids = list(lists["effects"])
    for kw in (dict(), dict(live=True)):
        capsys.readouterr()
        assert rcmd.cmd_read(args(**kw)) == 0
        out = capsys.readouterr().out
        assert "hit_point" in out and "effects" in out and "animations" in out
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
    ids = list(doc(tmp)["character"]["effects"])
    capsys.readouterr()
    assert rcmd.cmd_read(args(query="character.effects.*")) == 0
    out = capsys.readouterr().out
    assert any(i in out for i in ids) and "level" not in out
    assert rcmd.cmd_read(args(query="animations")) == 0
    assert capsys.readouterr().out.strip()
    assert rcmd.cmd_read(args(query="effects", live=True)) == 0
    assert any(i in capsys.readouterr().out for i in ids)


def test_live_with_an_unknown_name_stops_before_the_loop(rig, capsys):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(query="nonsense", live=True)) == 1
    assert "unknown name" in capsys.readouterr().err and box["sleeps"] == 0


# ---- --live-effects / --live-animations ----
def _lines(out, prefix):
    return [l for l in out.splitlines() if l.startswith(prefix)]


def test_live_effects_without_a_terminal_prints_each_id_once_with_its_name(rig, capsys):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(live_effects=True)) == 0
    out = capsys.readouterr().out
    plus = _lines(out, "+")
    assert [l.split()[1] for l in plus] == ["100", "200", "999"]
    assert "Golden Vow" in plus[0] and "45.0 / 80.0 s" in plus[0] and "permanent" in plus[1]
    assert "Unknown" in plus[2] and re.search(r"\d\d:\d\d:\d\d\.\d{3}$", plus[2]) and "+07" not in out
    assert mem.closed == 1


def test_mapped_and_unmapped_filter_the_ids(rig, capsys):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(live_effects=True, unmapped=True)) == 0
    assert [l.split()[1] for l in _lines(capsys.readouterr().out, "+")] == ["999"]
    mem.ticks = 3
    assert rcmd.cmd_read(args(live_effects=True, mapped=True)) == 0
    assert [l.split()[1] for l in _lines(capsys.readouterr().out, "+")] == ["100", "200"]


def test_both_monitors_share_one_process_and_are_prefixed(rig, capsys):
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(live_effects=True, live_animations=True)) == 0
    out = capsys.readouterr().out
    assert "[effects] Format:" in out and "[animations] Format:" in out and out.count("[effects] Format:") == 1
    assert any(l.startswith("[animations] + ") and "Sprint" in l for l in out.splitlines())
    assert any(l.startswith("[effects] + ") and "Golden Vow" in l for l in out.splitlines())


def test_on_a_terminal_the_monitors_draw_one_table_each_in_place(rig, monkeypatch, capsys):
    import os
    monkeypatch.setattr(rcmd.ui, "can_redraw", lambda stream=None: True)
    monkeypatch.setattr(rcmd.ui.shutil, "get_terminal_size", lambda fallback=None: os.terminal_size((100, 40)))
    tmp, mem, target, box, args = rig
    assert rcmd.cmd_read(args(live_effects=True, live_animations=True)) == 0
    out = capsys.readouterr().out
    assert out.startswith("\x1b[?25l") and out.endswith("\x1b[?25h")
    assert "effects   3 active \u00b7 3 seen \u00b7 1 unmapped" in out and "animations   1 active \u00b7 1 seen" in out
    assert "Golden Vow" in out and "Unknown" in out and "Sprint" in out
    assert not _lines(out, "+") and "Format:" not in out       # nothing is printed as a stream


def test_chr_state_ids_is_reloaded_when_it_changes(rig, monkeypatch, capsys):
    tmp, mem, target, box, args = rig
    names = tmp / "chr_state_ids.json"
    names.write_text(json.dumps({"100": {"name": "Golden Vow", "sources": "EFFECTS"}}), encoding="utf-8")
    mem.ticks = 6
    from eldendisk.game.profile import load_effects as real_load
    monkeypatch.setattr(rcmd, "load_effects", real_load)   # the rig fakes it; this test reads real files
    clock = {"t": 100.0}
    monkeypatch.setattr(rcmd.time, "monotonic", lambda: clock["t"])
    n = {"i": 0}

    def sleep(s):
        clock["t"] += 2.5
        n["i"] += 1
        if n["i"] == 1:
            names.write_text(json.dumps({"100": {"name": "Golden Vow", "sources": "EFFECTS"},
                                         "999": {"name": "Found It", "sources": "EFFECTS"}, "x": 1}), encoding="utf-8")
        if n["i"] == 2:
            names.write_text(json.dumps({"100": {"name": "Golden Vow", "sources": "EFFECTS"},
                                         "999": {"name": "Found It", "sources": "EFFECTS"}}), encoding="utf-8")

    monkeypatch.setattr(rcmd.time, "sleep", sleep)
    assert rcmd.cmd_read(args(live_effects=True, effects=str(names), unmapped=False)) == 0
    err = capsys.readouterr().err
    assert "changed but cannot be read" in err and "chr_state_ids.json reloaded (2 ids)" in err


def test_waits_for_the_game_instead_of_failing_when_live(rig, capsys):
    tmp, mem, target, box, args = rig
    calls = {"n": 0}

    def locate(offsets):
        calls["n"] += 1
        if calls["n"] < 3:
            raise AttachError("eldenring.exe is not running")
        return target

    box["locate"] = locate
    assert rcmd.cmd_read(args(live_effects=True)) == 0
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
    d = {"systems": {}, "character": {"level": 1, "effects": {}, "animations": {}}}
    assert view.select(d, "character.effects.*") == []
    assert view.select(d, "animations.*") == []
    assert view.select(d, "character.effects.311100.name") == []
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
            d["character"]["effects"] = {}
        return d

    monkeypatch.setattr(rcmd.ExportWriter, "build", build)
    n = {"i": 0}

    def sleep(s):
        n["i"] += 1
        if n["i"] == 2:
            gone["on"] = True

    monkeypatch.setattr(rcmd.time, "sleep", sleep)
    assert rcmd.cmd_read(args(query="character.effects.*", live=True)) == 0
    cap = capsys.readouterr()
    assert "unknown name" not in cap.err
    assert "→ -" in cap.out        # what was active is shown as gone, the loop kept running


def test_one_shot_query_of_an_empty_list_says_so_and_succeeds(rig, monkeypatch, capsys):
    tmp, mem, target, box, args = rig
    real = rcmd.ExportWriter.build

    def build(self, state, sample):
        d = real(self, state, sample)
        d["character"]["effects"] = {}
        return d

    monkeypatch.setattr(rcmd.ExportWriter, "build", build)
    assert rcmd.cmd_read(args(query="character.effects.*")) == 0
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

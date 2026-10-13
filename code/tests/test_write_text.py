"""`write --text` (1.7.1): the writer's text module against a fake game memory, and the command around it. The tables and the array
that points at them are FOUND by looking through the memory (writer/scan.py); no fixed chain from the exe is used."""
import argparse
import struct
from dataclasses import replace
from types import SimpleNamespace

import pytest

import eldendisk.commands.write as wcmd
from eldendisk.design.innovate_items.fmg import Fmg
from eldendisk.game.attach import EXIT_NO_SESSION, EXIT_UNSUPPORTED, AttachError, Target
from eldendisk.game.memory import Module
from eldendisk.game.profile import TextProfile
from eldendisk.vault import SaveVault, SessionState
from eldendisk.writer import scan
from eldendisk.writer import text as wt
from eldendisk.writer.writer import WriteGate
from tests.test_disk import make_profile

BASE = 0x10000000
OBJ, ARRAY = 0x20000000, 0x100            # the object that holds the array of pointers; where the array lies in it
FILES = {"GoodsName": 10, "GoodsInfo": 20, "GoodsCaption": 24}
GAME_ENTRIES = {"GoodsName": {1000: "Dagger", 1001: "Sword"},
                "GoodsInfo": {1000: "A short dagger", 1001: "A plain sword", 1002: "A bow"},
                "GoodsCaption": {1000: "A dagger.\nIt cuts.", 1001: "A sword.\nIt cuts more.", 1002: "A bow.", 1003: "Arrows."}}
SIZES = {n: len(Fmg(e).write()) for n, e in GAME_ENTRIES.items()}
TEXT = TextProfile(FILES, SIZES)
G1, G2 = 2230000, 2230001
EXE_SHA = "ab" * 32
HOST_PID, HOST_STARTED, GAME_PID, GAME_STARTED = 100, 555, 4242, 777


class Game:
    """Regions of bytes. `alloc` hands out new ones; `write` works inside one region and can be made to fail."""
    def __init__(self):
        self.mem, self.next, self.fail_writes, self.allocs = {}, 0x40000000, False, 0

    def regions(self, strict=False):
        return [(b, len(d)) for b, d in self.mem.items()]

    def read(self, addr, size):
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

    def alloc(self, size):
        self.allocs += 1
        base, self.next = self.next, self.next + ((size + 0xFFF) & ~0xFFF) + 0x1000
        self.mem[base] = bytearray(size)
        return base

    def close(self):
        pass

    def pointer(self, at):
        return struct.unpack("<Q", self.read(at, 8))[0]


def slot_at(name, obj=OBJ):
    return obj + ARRAY + FILES[name] * 8


def table_base(i):
    return 0x30000000 + i * 0x100000


def game_with_tables(extra=None):
    """The three tables in a region each, an object whose array points at them, and a table of the game that is none of ours."""
    g = Game()
    g.mem[OBJ] = bytearray(ARRAY + 30 * 8)
    for i, name in enumerate(FILES):
        blob = Fmg({**GAME_ENTRIES[name], **(extra or {})} if extra else GAME_ENTRIES[name]).write()
        base = table_base(i)
        g.mem[base] = bytearray(wt.live_form(blob, base))
        struct.pack_into("<Q", g.mem[OBJ], ARRAY + FILES[name] * 8, base)
    other = Fmg({5: "Not ours"}).write()
    g.mem[0x38000000] = bytearray(wt.live_form(other, 0x38000000))
    return g


def entries(game, name, obj=OBJ):
    return Fmg.read(wt.read_table(game, name, slot_at(name, obj))[0].data).entries


def tables_of(g, obj=OBJ):
    return {n: wt.read_table(g, n, slot_at(n, obj))[0] for n in FILES}


def open_gate():
    gate = WriteGate()
    gate.open()
    return gate


# ---------------------------------------------------------------------------------------------------- writer/text.py
def test_live_form_and_file_form_are_each_others_reverse():
    blob = Fmg({1: "a", 5: "b"}).write()
    live = wt.live_form(blob, 0x7000)
    assert live[:0x18] == blob[:0x18] and live[0x20:] == blob[0x20:] and live != blob
    assert wt.file_form(live, 0x7000) == blob
    assert wt.file_form(live, 0x9000) is None                    # not the address this table has
    assert wt.file_form(b"short", 0x7000) is None


def test_a_table_is_known_by_its_shape_and_by_the_address_inside_it_pointing_at_its_own_offsets():
    live = wt.live_form(Fmg({1: "a", 5: "b", 7: "c"}).write(), 0x7000)
    assert wt.table_size(live, 0, 0x7000) == len(live)
    assert wt.table_size(live, 0, 0x7010) == 0                                         # at another address the 0x18 address is wrong
    for at, value in ((2, 3), (8, 2), (0x20, 1)):
        bad = bytearray(live)
        bad[at] = value
        assert wt.table_size(bytes(bad), 0, 0x7000) == 0, at
    bad = bytearray(live)
    struct.pack_into("<I", bad, 4, 0x30)                                               # too small to hold its own groups and offsets
    assert wt.table_size(bytes(bad), 0, 0x7000) == 0
    assert wt.table_size(live[:0x20], 0, 0x7000) == 0 and wt.table_size(b"\0" * 100, 0, 0x7000) == 0


def test_find_tables_finds_the_three_by_their_size_and_counts_the_others():
    g = game_with_tables()
    seen = wt.find_tables(g, TEXT, everything=True)
    assert seen.found == {n: [table_base(i)] for i, n in enumerate(FILES)}
    assert seen.sizes[len(Fmg({5: "Not ours"}).write())] == 1 and sum(seen.sizes.values()) == 4
    assert seen.walked.complete


def test_find_tables_ends_when_every_table_has_been_seen_unless_told_to_go_on():
    g = game_with_tables()
    assert wt.find_tables(g, TEXT).walked.stopped
    lonely = game_with_tables()
    del lonely.mem[table_base(1)]
    seen = wt.find_tables(lonely, TEXT)
    assert seen.found["GoodsInfo"] == [] and seen.walked.complete and not seen.walked.stopped


def test_a_table_with_the_right_size_but_a_broken_address_is_not_taken():
    g = game_with_tables()
    g.write(table_base(0) + 0x18, struct.pack("<Q", 5))
    assert wt.find_tables(g, TEXT, everything=True).found["GoodsName"] == []


def test_find_arrays_finds_the_pointers_that_lie_at_the_distances_of_the_file_numbers():
    g = game_with_tables()
    seen = wt.find_tables(g, TEXT)
    arrays = wt.find_arrays(g, TEXT, seen.found)
    assert arrays.found == [(OBJ + ARRAY, {n: table_base(i) for i, n in enumerate(FILES)})] and arrays.pointers == 1


def test_pointers_that_are_not_at_those_distances_are_no_array():
    g = game_with_tables()
    g.mem[0x50000000] = bytearray(0x400)
    for i, n in enumerate(FILES):                                     # the same three pointers, but with the wrong distances
        struct.pack_into("<Q", g.mem[0x50000000], 0x100 + i * 8 * 7, table_base(i))
    g.write(slot_at("GoodsInfo"), struct.pack("<Q", 0))               # and the real array is missing one of them
    seen = wt.find_tables(g, TEXT)
    assert wt.find_arrays(g, TEXT, seen.found).found == []


def test_the_look_for_the_array_ends_at_the_first_whole_one():
    g = game_with_tables()
    g.mem[0x50000000] = bytearray(g.mem[OBJ])
    seen = wt.find_tables(g, TEXT)
    arrays = wt.find_arrays(g, TEXT, seen.found)
    assert [a for a, _t in arrays.found] == [OBJ + ARRAY] and arrays.walked.stopped


def test_a_pointer_to_the_first_table_without_the_other_two_is_passed_by():
    g = game_with_tables()
    g.mem[0x50000000] = bytearray(0x200)
    struct.pack_into("<Q", g.mem[0x50000000], 0x40 + FILES["GoodsName"] * 8, table_base(0))     # right distance, but nothing else there
    g.mem[0x48000000] = bytearray(g.mem[OBJ])
    seen = wt.find_tables(g, TEXT)
    arrays = wt.find_arrays(g, TEXT, seen.found)
    assert [a for a, _t in arrays.found] == [OBJ + ARRAY] or [a for a, _t in arrays.found] == [0x48000000 + ARRAY]
    assert arrays.pointers >= 2


def test_the_array_is_looked_for_around_the_tables_first(monkeypatch):
    monkeypatch.setattr(scan, "NEAR", 0x2000)
    g = Game()
    base = 0x30000000
    g.mem[base] = bytearray(0x100000)                                    # a block with the three tables and the array inside it
    offsets = {}
    at = 0x1000
    for i, name in enumerate(FILES):
        blob = Fmg(GAME_ENTRIES[name]).write()
        offsets[name] = base + at
        g.mem[base][at:at + len(blob)] = wt.live_form(blob, base + at)
        at += (len(blob) + 15) & ~15
    array = base + at + 0x100
    for name, number in FILES.items():
        struct.pack_into("<Q", g.mem[base], array - base + 8 * number, offsets[name])
    g.mem[0x70000000] = bytearray(0x400000)                              # a block that must not be read at all
    reads = []
    real = g.read
    g.read = lambda a, s: (reads.append(a), real(a, s))[1]
    arrays = wt.find_arrays(g, TEXT, {n: [b] for n, b in offsets.items()})
    assert [a for a, _t in arrays.found] == [array] and arrays.walked.tier == "near"
    assert not any(a >= 0x70000000 for a in reads)


def test_the_look_goes_on_through_all_the_memory_when_the_array_is_not_near(monkeypatch):
    monkeypatch.setattr(scan, "NEAR", 0x2000)
    g = game_with_tables()
    seen = wt.find_tables(g, TEXT)
    arrays = wt.find_arrays(g, TEXT, seen.found)
    assert [a for a, _t in arrays.found] == [OBJ + ARRAY] and arrays.walked.tier != "near"


def test_read_table_gives_the_table_as_in_its_file_and_says_why_when_it_is_none():
    g = game_with_tables()
    t, why = wt.read_table(g, "GoodsCaption", slot_at("GoodsCaption"))
    assert why == "" and t.base == table_base(2) and Fmg.read(t.data).entries == GAME_ENTRIES["GoodsCaption"]
    assert wt.read_table(g, t.name, t.slot_at)[0].data == t.data
    g.write(slot_at("GoodsName"), struct.pack("<Q", 0))
    assert "not an address" in wt.read_table(g, "GoodsName", slot_at("GoodsName"))[1]
    g.write(slot_at("GoodsName"), struct.pack("<Q", 0x66000000))
    assert "cannot be read" in wt.read_table(g, "GoodsName", slot_at("GoodsName"))[1]
    g.write(slot_at("GoodsInfo"), struct.pack("<Q", table_base(2) + 2))
    assert "do not start like a text table" in wt.read_table(g, "GoodsInfo", slot_at("GoodsInfo"))[1]


def test_swap_writes_the_whole_table_then_changes_the_one_pointer_and_leaves_the_old_table():
    g = game_with_tables()
    old = tables_of(g)["GoodsName"]
    fmg = Fmg.read(old.data)
    fmg.entries[G1] = "Reverse Curse Technique"
    new_base = wt.swap(g, open_gate(), old, fmg.write())
    assert new_base and g.pointer(old.slot_at) == new_base
    now = wt.read_table(g, old.name, old.slot_at)[0]
    assert now.base == new_base and Fmg.read(now.data).entries[G1] == "Reverse Curse Technique"
    assert g.read(old.base, len(old.data)) == wt.live_form(old.data, old.base)          # the game's own table is untouched


def test_swap_with_the_text_the_game_has_allocates_nothing():
    g = game_with_tables()
    old = tables_of(g)["GoodsName"]
    assert wt.swap(g, open_gate(), old, old.data) == 0 and g.allocs == 0


def test_swap_refuses_a_closed_gate_and_reports_every_failure_without_switching_when_it_cannot():
    g = game_with_tables()
    old = tables_of(g)["GoodsName"]
    new = Fmg({1: "x"}).write()
    with pytest.raises(wt.TextError, match="not allowed"):
        wt.swap(g, WriteGate(), old, new)
    g.fail_writes = True
    with pytest.raises(wt.TextError, match="could not write the new table"):
        wt.swap(g, open_gate(), old, new)
    assert g.pointer(old.slot_at) == old.base
    g.fail_writes = False
    g.write(old.slot_at, struct.pack("<Q", 0x30500000))                                  # the game moved it meanwhile
    with pytest.raises(wt.TextError, match="pointer changed"):
        wt.swap(g, open_gate(), old, new)
    assert g.pointer(old.slot_at) == 0x30500000


def test_swap_fails_loudly_when_the_game_gives_no_memory():
    g = game_with_tables()
    old = tables_of(g)["GoodsName"]
    g.alloc = lambda size: 0
    with pytest.raises(wt.TextError, match="no memory"):
        wt.swap(g, open_gate(), old, Fmg({1: "x"}).write())


# ------------------------------------------------------------------------------------------------ new_table (command)
def test_new_table_adds_changes_and_removes_and_says_none_when_nothing_changes():
    old = tables_of(game_with_tables())["GoodsName"]
    assert wcmd.new_table(old, {G1: "", G2: ""}) is None                                 # nothing to say: the game's table stays
    new = wcmd.new_table(old, {G1: "A", G2: ""})
    assert Fmg.read(new).entries == {**GAME_ENTRIES["GoodsName"], G1: "A"}
    again = wt.Table("GoodsName", 0, 0, new)
    assert wcmd.new_table(again, {G1: "A", G2: ""}) is None                              # the same text again: nothing
    assert Fmg.read(wcmd.new_table(again, {G1: ""})).entries == GAME_ENTRIES["GoodsName"]   # an empty text takes it away


# --------------------------------------------------------------------------------------------------------- the command
@pytest.fixture
def rig(tmp_path, monkeypatch):
    live = tmp_path / "Users" / "me" / "EldenRing" / "1"
    live.mkdir(parents=True)
    (live / "ER0000.sl2").write_bytes(b"save")
    vault = SaveVault(tmp_path / "vault")
    game = game_with_tables()
    clock = {"t": 0.0}
    box = {"locate": None, "texts": {G1: {"goods_name": "Reverse Curse Technique", "goods_info": "Heals over time",
                                          "goods_captions": "Long text\nsecond line"},
                                     G2: {"goods_name": "", "goods_info": "", "goods_captions": ""}}}
    profile = replace(make_profile(), text=TEXT)
    target = Target(GAME_PID, GAME_STARTED, Module("eldenring.exe", BASE, str(tmp_path / "eldenring.exe")), EXE_SHA, profile)
    box["locate"] = lambda offsets: target
    design = SimpleNamespace(selection=lambda: ("all", None), texts=lambda sel: box["texts"], flame_color=lambda sel: box.get("flame", (None, None)),
                             eyes_color=lambda sel: box.get("eyes", (None, None)),
                             flame_accent_color=lambda sel: box.get("accent", (None, None)))

    def sleep(s):
        clock["t"] += s
        box.get("on_sleep", lambda: None)()

    monkeypatch.setattr(wcmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(wcmd, "locate", lambda offsets: box["locate"](offsets))
    monkeypatch.setattr(wcmd, "process_started", lambda pid: HOST_STARTED if pid == HOST_PID else None)
    monkeypatch.setattr(wcmd, "WritableProcessMemory", lambda pid: game)
    monkeypatch.setattr(wcmd, "design_folder", lambda args: tmp_path / "ext")
    monkeypatch.setattr(wcmd, "spec_file", lambda args: tmp_path / "design.json")
    monkeypatch.setattr(wcmd.design, "open_spells", lambda d, s: design)
    monkeypatch.setattr(wcmd, "_sleep", sleep)
    monkeypatch.setattr(wcmd, "_clock", lambda: clock["t"])
    monkeypatch.setattr(scan, "_sleep", lambda s: None)

    def open_session():
        vault.write_session(vault.new_record(vault.snapshot(live), live, exe_sha256=EXE_SHA,
                                             host_pid=HOST_PID, host_started=HOST_STARTED))
        vault.update_session(state=SessionState.RUNNING, game_pid=GAME_PID, game_started=GAME_STARTED)

    def args(**kw):
        d = dict(text=True, flame_color=False, wait=0, set=[], refill=None, reset=[], verbose=False, vault=str(vault.root), offsets="x",
                 spec=None, design_dir=None)
        return argparse.Namespace(**{**d, **kw})

    return SimpleNamespace(vault=vault, game=game, box=box, open_session=open_session, args=args, clock=clock)




def test_the_text_of_the_design_reaches_the_three_tables(rig):
    rig.open_session()
    assert wcmd.cmd_write(rig.args()) == 0
    assert entries(rig.game, "GoodsName")[G1] == "Reverse Curse Technique" and G2 not in entries(rig.game, "GoodsName")
    assert entries(rig.game, "GoodsInfo")[G1] == "Heals over time"
    assert entries(rig.game, "GoodsCaption")[G1] == "Long text\nsecond line"
    assert entries(rig.game, "GoodsName")[1000] == "Dagger"                                # the game's own text is kept
    assert rig.game.allocs == 3


def test_a_second_run_in_the_same_game_finds_no_array_that_points_at_the_game_tables_and_says_so(rig, monkeypatch):
    rig.open_session()
    assert wcmd.cmd_write(rig.args()) == 0
    seen = []
    monkeypatch.setattr(wcmd.book, "e", lambda tag, msg: seen.append(msg))
    assert wcmd.cmd_write(rig.args()) == 1 and rig.game.allocs == 3
    assert "set already in this session" in seen[-1]


def test_no_session_no_write(rig):
    assert wcmd.cmd_write(rig.args()) == EXIT_NO_SESSION
    assert rig.game.allocs == 0


def test_a_session_of_another_game_process_is_refused(rig):
    rig.open_session()
    rig.vault.update_session(game_pid=GAME_PID + 1)
    assert wcmd.cmd_write(rig.args()) == EXIT_NO_SESSION and rig.game.allocs == 0


def test_a_game_version_without_a_text_block_is_unsupported(rig):
    rig.open_session()
    t = rig.box["locate"](None)
    rig.box["locate"] = lambda o: replace(t, profile=replace(t.profile, text=None))
    assert wcmd.cmd_write(rig.args()) == EXIT_UNSUPPORTED


def test_without_wait_tables_that_are_not_there_yet_are_an_error(rig):
    rig.open_session()
    for i in range(3):
        del rig.game.mem[table_base(i)]
    assert wcmd.cmd_write(rig.args()) == 1 and rig.game.allocs == 0


def test_wait_looks_again_until_the_game_has_its_text(rig):
    rig.open_session()
    saved = {table_base(i): rig.game.mem.pop(table_base(i)) for i in range(3)}              # the game is still starting
    seen = {"n": 0}

    def later():
        seen["n"] += 1
        if seen["n"] == 2:
            rig.game.mem.update(saved)                                                    # now it has loaded its text

    rig.box["on_sleep"] = later
    assert wcmd.cmd_write(rig.args(wait=60)) == 0
    assert entries(rig.game, "GoodsName")[G1] == "Reverse Curse Technique"
    assert rig.clock["t"] >= 10.0 + 20.0                                                  # two rests of the schedule (LOOKS) before the third look


def test_wait_gives_up_after_the_looks_and_says_why_with_the_sizes_it_saw(rig, monkeypatch):
    rig.open_session()
    t = rig.box["locate"](None)
    rig.box["locate"] = lambda o: replace(t, profile=replace(t.profile, text=TextProfile(FILES, {**SIZES, "GoodsInfo": SIZES["GoodsInfo"] + 8})))
    seen = []
    monkeypatch.setattr(wcmd.book, "e", lambda tag, msg: seen.append(msg))
    assert wcmd.cmd_write(rig.args(wait=60)) == 1 and rig.game.allocs == 0
    assert "GoodsInfo" in seen[-1] and f"{SIZES['GoodsInfo'] + 8} bytes" in seen[-1] and "4 text tables of the game were seen" in seen[-1]
    assert rig.clock["t"] == sum(wcmd.LOOKS)


def test_a_copy_of_a_table_that_nothing_points_at_does_not_stop_the_command(rig):
    rig.open_session()
    decoy = bytearray(0x8000)                                                             # a bigger block, so it is read first
    blob = wt.live_form(Fmg(GAME_ENTRIES["GoodsName"]).write(), 0x58000100)
    decoy[0x100:0x100 + len(blob)] = blob
    rig.game.mem[0x58000000] = decoy
    assert wcmd.cmd_write(rig.args()) == 0
    assert entries(rig.game, "GoodsName")[G1] == "Reverse Curse Technique"


def test_a_second_copy_of_the_array_is_left_alone_when_the_first_one_is_whole(rig):
    rig.open_session()
    rig.game.mem[0x50000000] = bytearray(rig.game.mem[OBJ])
    assert wcmd.cmd_write(rig.args()) == 0
    assert entries(rig.game, "GoodsName", OBJ)[G1] == "Reverse Curse Technique"
    assert rig.game.allocs == 3


def test_the_log_says_what_each_look_did(rig, monkeypatch):
    rig.open_session()
    seen = []
    monkeypatch.setattr(wcmd.book, "d", lambda tag, msg: seen.append(msg))
    wcmd.cmd_write(rig.args())
    assert any(m.startswith("goods text: looked for the tables:") and "MB read" in m and f"{table_base(0):#x}" in m for m in seen)
    assert any(m.startswith("goods text: looked for the array") and "1 pointer(s)" in m and "1 array(s)" in m and "the slowest" in m for m in seen)
    assert any(m.startswith("goods text: array at") and "GoodsName ->" in m for m in seen)


def test_wait_retries_while_the_game_cannot_be_attached_yet_but_not_when_it_is_not_running(rig):
    rig.open_session()
    tries = {"n": 0}
    real = rig.box["locate"]

    def locate(o):
        tries["n"] += 1
        if tries["n"] < 3:
            raise AttachError("cannot list the modules of eldenring.exe (still starting)")
        return real(o)

    rig.box["locate"] = locate
    assert wcmd.cmd_write(rig.args(wait=30)) == 0 and tries["n"] == 3

    def gone(o):
        raise AttachError("eldenring.exe is not running")

    rig.box["locate"] = gone
    assert wcmd.cmd_write(rig.args(wait=30)) == 1


def test_if_the_game_puts_its_own_tables_back_the_text_is_set_once_more(rig):
    rig.open_session()
    originals = {n: rig.game.pointer(slot_at(n)) for n in FILES}
    state = {"done": False}

    def reset_once():
        if not state["done"] and rig.game.pointer(slot_at("GoodsName")) != originals["GoodsName"]:
            state["done"] = True
            for n, p in originals.items():
                rig.game.write(slot_at(n), struct.pack("<Q", p))

    rig.box["on_sleep"] = reset_once
    assert wcmd.cmd_write(rig.args(wait=30)) == 0 and state["done"]
    assert entries(rig.game, "GoodsName")[G1] == "Reverse Curse Technique"


def test_if_the_game_keeps_replacing_them_it_is_an_error(rig):
    rig.open_session()
    originals = {n: rig.game.pointer(slot_at(n)) for n in FILES}

    def always():
        for n, p in originals.items():
            rig.game.write(slot_at(n), struct.pack("<Q", p))

    rig.box["on_sleep"] = always
    assert wcmd.cmd_write(rig.args(wait=30)) == 1


def test_text_stands_alone_on_the_command_line():
    import eldendisk.__main__ as cli
    for bad in (["write", "--text", "--set", "level=1"], ["write", "--wait"], ["write", "--set", "level=1", "--spec", "x"]):
        with pytest.raises(SystemExit):
            cli.main(bad)


# ------------------------------------------------------------------------------------------------ write --flame-color
def _flame_rig(rig, monkeypatch, colour=(0.2, 0.65, 1.0), note=None):
    from tests.test_write_flame import Game as FlameGame
    fg = FlameGame()
    monkeypatch.setattr(wcmd, "WritableProcessMemory", lambda pid: fg)
    rig.box["flame"] = (colour, note)
    return fg, FlameGame()


def test_the_flame_colour_of_the_design_reaches_the_effects(rig, monkeypatch):
    rig.open_session()
    fg, untouched = _flame_rig(rig, monkeypatch)
    assert wcmd.cmd_write(rig.args(text=False, flame_color=True)) == 0
    assert any(fg.mem[b] != untouched.mem[b] for b in fg.mem) and rig.game.allocs == 0


def test_no_colour_in_the_design_means_nothing_is_touched(rig, monkeypatch):
    rig.open_session()
    fg, untouched = _flame_rig(rig, monkeypatch, colour=None)
    assert wcmd.cmd_write(rig.args(text=False, flame_color=True)) == 0
    assert all(fg.mem[b] == untouched.mem[b] for b in fg.mem)


def test_the_eyes_colour_of_the_design_reaches_the_positive_curse_energy_eyes_even_without_a_fire_colour(rig, monkeypatch):
    from tests.test_write_flame import BASES, Game as FlameGame
    from eldendisk.writer import fxr
    rig.open_session()
    fg = FlameGame(effects=("524400", "524401", "4866"))
    monkeypatch.setattr(wcmd, "WritableProcessMemory", lambda pid: fg)
    rig.box["flame"], rig.box["eyes"] = (None, None), ((0.2, 0.65, 1.0), None)
    assert wcmd.cmd_write(rig.args(text=False, flame_color=True)) == 0
    assert fxr.find_all(fg, ["4866"], (0.2, 0.65, 1.0)).changed["4866"] == [BASES["4866"]]
    assert bytes(fg.mem[BASES["524400"]]) == bytes(FlameGame().mem[BASES["524400"]])


def test_no_session_no_flame_colour(rig, monkeypatch):
    fg, untouched = _flame_rig(rig, monkeypatch)
    assert wcmd.cmd_write(rig.args(text=False, flame_color=True)) == EXIT_NO_SESSION
    assert all(fg.mem[b] == untouched.mem[b] for b in fg.mem)


def test_flame_colour_waits_for_the_game_to_have_its_effects(rig, monkeypatch):
    rig.open_session()
    fg, _ = _flame_rig(rig, monkeypatch)
    saved = fg.mem.pop(0x20000000)
    n = {"n": 0}

    def later():
        n["n"] += 1
        if n["n"] == 1:
            fg.mem[0x20000000] = saved
    rig.box["on_sleep"] = later
    assert wcmd.cmd_write(rig.args(text=False, flame_color=True, wait=60)) == 0 and n["n"] == 1      # one rest between two looks


def test_flame_colour_stands_alone_on_the_command_line():
    import eldendisk.__main__ as cli
    for bad in (["write", "--flame-color", "--set", "level=1"], ["write", "--flame-color", "--text"]):
        with pytest.raises(SystemExit):
            cli.main(bad)


# ------------------------------------------------------------------------------------------------ --when-loaded
def _world(rig, monkeypatch, script, game=None):
    """A world flag, a living flag and a tick of WORLD_POLL seconds per rest; `script(st)` runs after every rest."""
    st = {"world": False, "alive": True, "tick": 0, "said": [], "looks": 0}
    (game or rig.game).alive = lambda: st["alive"]

    def look(mem, target):
        st["looks"] += 1
        return st["world"], "" if st["world"] else "title screen"
    monkeypatch.setattr(wcmd, "world_loaded", look)
    monkeypatch.setattr(wcmd.book, "i", lambda tag, msg: st["said"].append(msg))

    def on_sleep():
        st["tick"] += 1
        script(st)
    rig.box["on_sleep"] = on_sleep
    return st


def test_the_world_must_stay_for_a_while_and_a_flicker_starts_the_count_again(rig, monkeypatch):
    seen = []

    def script(st):
        st["world"] = st["tick"] >= 3 and st["tick"] != 5            # in the world from tick 3, gone at tick 5 (a loading screen)
        seen.append(rig.clock["t"])
    st = _world(rig, monkeypatch, script)
    assert wcmd._wait_world(rig.game, None, "text") is True
    assert rig.clock["t"] >= 5 * wcmd.WORLD_POLL + wcmd.WORLD_STABLE                  # tick 6 starts the count, 5 s later it is done
    assert any("waiting for a character" in s for s in st["said"]) and sum("waiting for a character" in s for s in st["said"]) == 1


def test_a_world_already_checked_by_a_step_before_is_taken_at_the_first_look(rig, monkeypatch):
    _world(rig, monkeypatch, lambda st: st.update(world=True))
    t0 = rig.clock["t"]
    assert wcmd._wait_world(rig.game, None, "external scripts", stable=0.0) is True
    assert rig.clock["t"] - t0 < wcmd.WORLD_STABLE                                       # no second wait of 5 s


def test_the_wait_ends_when_the_game_closes(rig, monkeypatch):
    _world(rig, monkeypatch, lambda st: st.update(alive=st["tick"] < 4))
    assert wcmd._wait_world(rig.game, None, "text") is False


def test_the_text_is_written_once_after_the_world_is_there_and_the_step_ends(rig, monkeypatch):
    rig.open_session()
    seen = []

    def script(st):
        if st["tick"] == 3:
            seen.append(G1 in entries(rig.game, "GoodsName"))                      # the title screen: nothing written yet
            st["world"] = True
    st = _world(rig, monkeypatch, script)
    assert wcmd.cmd_write(rig.args(when_loaded=True)) == 0
    assert seen == [False] and entries(rig.game, "GoodsName")[G1] == "Reverse Curse Technique"
    allocs, looks = rig.game.allocs, st["looks"]
    assert allocs == 3 and looks < 20                                              # three tables, one write, a few looks and no more


def test_the_flame_colour_is_painted_once_after_the_world_is_there(rig, monkeypatch):
    rig.open_session()
    fg, untouched = _flame_rig(rig, monkeypatch)
    seen = []

    def script(st):
        if st["tick"] == 3:
            seen.append(all(fg.mem[b] == untouched.mem[b] for b in fg.mem))
            st["world"] = True
    _world(rig, monkeypatch, script, game=fg)
    assert wcmd.cmd_write(rig.args(text=False, flame_color=True, when_loaded=True)) == 0
    assert seen == [True] and all(fg.mem[b] != untouched.mem[b] for b in fg.mem)


def test_when_the_game_closes_before_a_character_is_there_nothing_is_written(rig, monkeypatch):
    rig.open_session()
    _world(rig, monkeypatch, lambda st: st.update(alive=st["tick"] < 6))
    assert wcmd.cmd_write(rig.args(when_loaded=True)) == 0 and rig.game.allocs == 0


def test_when_loaded_never_writes_without_a_session(rig, monkeypatch):
    _world(rig, monkeypatch, lambda st: st.update(world=True, alive=st["tick"] < 8))
    assert wcmd.cmd_write(rig.args(when_loaded=True)) == EXIT_NO_SESSION and rig.game.allocs == 0


def test_when_loaded_goes_with_text_or_flame_colour_only_and_not_with_wait():
    import eldendisk.__main__ as cli
    for bad in (["write", "--when-loaded"], ["write", "--when-loaded", "--set", "level=1"], ["write", "--text", "--when-loaded", "--wait", "5"]):
        with pytest.raises(SystemExit):
            cli.main(bad)


def test_the_second_fire_colour_reaches_the_places_the_first_leaves_out(rig, monkeypatch):
    from tests.test_write_flame import BASES, Game as FlameGame
    from eldendisk.writer import fxr
    from eldendisk.writer.fxr_plans import PLANS
    rig.open_session()
    fg = FlameGame()
    monkeypatch.setattr(wcmd, "WritableProcessMemory", lambda pid: fg)
    rig.box["flame"], rig.box["accent"] = ((0.2, 0.65, 1.0), None), ((0.55, 0.2, 1.0), None)
    assert wcmd.cmd_write(rig.args(text=False, flame_color=True)) == 0
    for eid in ("524400", "524401"):
        for at, (_old, new) in fxr.accent_writes(PLANS[eid], (0.55, 0.2, 1.0)).items():
            assert bytes(fg.mem[BASES[eid]][at:at + 16]) == new


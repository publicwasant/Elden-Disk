"""`write --text` (1.7.1): the writer's text module against a fake game memory, and the command around it."""
import argparse
import struct
from dataclasses import replace
from types import SimpleNamespace

import pytest

import eldendisk.commands.write as wcmd
from eldendisk.extension.innovate_items.fmg import Fmg
from eldendisk.game.attach import EXIT_NO_SESSION, EXIT_UNSUPPORTED, AttachError, Target
from eldendisk.game.memory import Module
from eldendisk.game.profile import TextProfile
from eldendisk.vault import SaveVault, SessionState
from eldendisk.writer import text as wt
from eldendisk.writer.writer import WriteGate
from tests.test_disk import make_profile

BASE, OBJ = 0x10000000, 0x20000000
RVA, ARRAY = 0x1000, 0x100
FILES = {"GoodsName": 10, "GoodsInfo": 20, "GoodsCaption": 24}
TEXT = TextProfile(RVA, ARRAY, FILES)
G1, G2 = 2230000, 2230001
EXE_SHA = "ab" * 32
HOST_PID, HOST_STARTED, GAME_PID, GAME_STARTED = 100, 555, 4242, 777


class Game:
    """Regions of bytes. `alloc` hands out new ones; `write` works inside one region and can be made to fail."""
    def __init__(self):
        self.mem, self.next, self.fail_writes, self.allocs = {}, 0x40000000, False, 0

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


def slot_at(name):
    return OBJ + ARRAY + FILES[name] * 8


def game_with_tables(extra=None):
    g = Game()
    g.mem[BASE + RVA] = bytearray(struct.pack("<Q", OBJ))
    g.mem[OBJ] = bytearray(ARRAY + 30 * 8)
    for i, name in enumerate(FILES):
        entries = {1000: "Dagger", 1001: "Sword", **(extra or {})}
        blob = Fmg(entries).write()
        base = 0x30000000 + i * 0x100000
        g.mem[base] = bytearray(wt.live_form(blob, base))
        struct.pack_into("<Q", g.mem[OBJ], ARRAY + FILES[name] * 8, base)
    return g


# ---------------------------------------------------------------------------------------------------- writer/text.py
def test_live_form_and_file_form_are_each_others_reverse():
    blob = Fmg({1: "a", 5: "b"}).write()
    live = wt.live_form(blob, 0x7000)
    assert live[:0x18] == blob[:0x18] and live[0x20:] == blob[0x20:] and live != blob
    assert wt.file_form(live, 0x7000) == blob
    assert wt.file_form(live, 0x9000) is None                    # not the address this table has
    assert wt.file_form(b"short", 0x7000) is None


def test_locate_follows_the_chain_and_gives_the_table_as_in_its_file():
    g = game_with_tables()
    t = wt.locate(g, BASE, TEXT, "GoodsCaption")
    assert t.slot_at == slot_at("GoodsCaption") and t.base == g.pointer(t.slot_at)
    assert Fmg.read(t.data).entries == {1000: "Dagger", 1001: "Sword"}


@pytest.mark.parametrize("damage", ["no_object", "no_table", "bad_version", "bad_size", "odd_address"])
def test_locate_says_not_yet_when_the_game_is_not_ready_or_it_is_not_a_table(damage):
    g = game_with_tables()
    base = g.pointer(slot_at("GoodsName"))
    if damage == "no_object":
        g.write(BASE + RVA, struct.pack("<Q", 0))
    elif damage == "no_table":
        g.write(slot_at("GoodsName"), struct.pack("<Q", 0))
    elif damage == "bad_version":
        g.write(base + 2, b"\x03")
    elif damage == "bad_size":
        g.write(base + 4, struct.pack("<I", 0x7FFFFFFF))
    else:
        g.write(base + 0x18, struct.pack("<Q", 5))
    assert wt.locate(g, BASE, TEXT, "GoodsName") is None


def test_locate_refuses_a_table_the_profile_does_not_know():
    with pytest.raises(wt.TextError):
        wt.locate(game_with_tables(), BASE, TEXT, "Nope")


def open_gate():
    gate = WriteGate()
    gate.open()
    return gate


def test_swap_writes_the_whole_table_then_changes_the_one_pointer_and_leaves_the_old_table():
    g = game_with_tables()
    old = wt.locate(g, BASE, TEXT, "GoodsName")
    fmg = Fmg.read(old.data)
    fmg.entries[G1] = "Reverse Curse Technique"
    new_base = wt.swap(g, open_gate(), old, fmg.write())
    assert new_base and g.pointer(old.slot_at) == new_base
    now = wt.locate(g, BASE, TEXT, "GoodsName")
    assert now.base == new_base and Fmg.read(now.data).entries[G1] == "Reverse Curse Technique"
    assert g.read(old.base, len(old.data)) == wt.live_form(old.data, old.base)          # the game's own table is untouched


def test_swap_with_the_text_the_game_has_allocates_nothing():
    g = game_with_tables()
    old = wt.locate(g, BASE, TEXT, "GoodsName")
    assert wt.swap(g, open_gate(), old, old.data) == 0 and g.allocs == 0


def test_swap_refuses_a_closed_gate_and_reports_every_failure_without_switching_when_it_cannot():
    g = game_with_tables()
    old = wt.locate(g, BASE, TEXT, "GoodsName")
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
    old = wt.locate(g, BASE, TEXT, "GoodsName")
    g.alloc = lambda size: 0
    with pytest.raises(wt.TextError, match="no memory"):
        wt.swap(g, open_gate(), old, Fmg({1: "x"}).write())


# ------------------------------------------------------------------------------------------------ new_table (command)
def test_new_table_adds_changes_and_removes_and_says_none_when_nothing_changes():
    old = wt.locate(game_with_tables(), BASE, TEXT, "GoodsName")
    assert wcmd.new_table(old, {G1: "", G2: ""}) is None                                 # nothing to say: the game's table stays
    new = wcmd.new_table(old, {G1: "A", G2: ""})
    assert Fmg.read(new).entries == {1000: "Dagger", 1001: "Sword", G1: "A"}
    again = wt.Table("GoodsName", 0, 0, new)
    assert wcmd.new_table(again, {G1: "A", G2: ""}) is None                              # the same text again: nothing
    assert Fmg.read(wcmd.new_table(again, {G1: ""})).entries == {1000: "Dagger", 1001: "Sword"}   # an empty text takes it away


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
    design = SimpleNamespace(selection=lambda: ("all", None), texts=lambda sel: box["texts"])

    def sleep(s):
        clock["t"] += s
        box.get("on_sleep", lambda: None)()

    monkeypatch.setattr(wcmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(wcmd, "locate", lambda offsets: box["locate"](offsets))
    monkeypatch.setattr(wcmd, "process_started", lambda pid: HOST_STARTED if pid == HOST_PID else None)
    monkeypatch.setattr(wcmd, "WritableProcessMemory", lambda pid: game)
    monkeypatch.setattr(wcmd, "ext_dir", lambda args: tmp_path / "ext")
    monkeypatch.setattr(wcmd, "spec_file", lambda args: tmp_path / "extension.json")
    monkeypatch.setattr(wcmd.extension, "open_spells", lambda d, s: design)
    monkeypatch.setattr(wcmd, "_sleep", sleep)
    monkeypatch.setattr(wcmd, "_clock", lambda: clock["t"])

    def open_session():
        vault.write_session(vault.new_record(vault.snapshot(live), live, exe_sha256=EXE_SHA,
                                             host_pid=HOST_PID, host_started=HOST_STARTED))
        vault.update_session(state=SessionState.RUNNING, game_pid=GAME_PID, game_started=GAME_STARTED)

    def args(**kw):
        d = dict(text=True, wait=0, set=[], refill=None, reset=[], verbose=False, vault=str(vault.root), offsets="x",
                 spec=None, extension_dir=None)
        return argparse.Namespace(**{**d, **kw})

    return SimpleNamespace(vault=vault, game=game, box=box, open_session=open_session, args=args, clock=clock)


def entries(game, name):
    return Fmg.read(wt.locate(game, BASE, TEXT, name).data).entries


def test_the_text_of_the_design_reaches_the_three_tables(rig):
    rig.open_session()
    assert wcmd.cmd_write(rig.args()) == 0
    assert entries(rig.game, "GoodsName")[G1] == "Reverse Curse Technique" and G2 not in entries(rig.game, "GoodsName")
    assert entries(rig.game, "GoodsInfo")[G1] == "Heals over time"
    assert entries(rig.game, "GoodsCaption")[G1] == "Long text\nsecond line"
    assert entries(rig.game, "GoodsName")[1000] == "Dagger"                                # the game's own text is kept


def test_doing_it_twice_allocates_nothing_the_second_time_and_a_changed_text_replaces_it(rig):
    rig.open_session()
    wcmd.cmd_write(rig.args())
    n = rig.game.allocs
    assert wcmd.cmd_write(rig.args()) == 0 and rig.game.allocs == n
    rig.box["texts"][G1]["goods_name"] = "New name"
    assert wcmd.cmd_write(rig.args()) == 0
    assert entries(rig.game, "GoodsName")[G1] == "New name" and entries(rig.game, "GoodsInfo")[G1] == "Heals over time"
    rig.box["texts"][G1]["goods_info"] = ""
    wcmd.cmd_write(rig.args())
    assert G1 not in entries(rig.game, "GoodsInfo")                                       # emptied in the design: gone in the game


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
    rig.game.write(BASE + RVA, struct.pack("<Q", 0))
    assert wcmd.cmd_write(rig.args()) == 1 and rig.game.allocs == 0


def test_wait_looks_again_until_the_game_has_its_text_and_it_stayed_the_same_twice(rig):
    rig.open_session()
    rig.game.write(BASE + RVA, struct.pack("<Q", 0))                                      # the game is still starting
    seen = {"n": 0}

    def later():
        seen["n"] += 1
        if seen["n"] == 3:
            rig.game.write(BASE + RVA, struct.pack("<Q", OBJ))                            # now it has loaded its text

    rig.box["on_sleep"] = later
    assert wcmd.cmd_write(rig.args(wait=60)) == 0
    assert entries(rig.game, "GoodsName")[G1] == "Reverse Curse Technique" and seen["n"] >= 4


def test_wait_gives_up_after_the_time(rig):
    rig.open_session()
    rig.game.write(BASE + RVA, struct.pack("<Q", 0))
    assert wcmd.cmd_write(rig.args(wait=5)) == 1 and rig.clock["t"] >= 5


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

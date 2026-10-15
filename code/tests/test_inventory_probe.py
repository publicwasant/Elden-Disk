"""`probe inventory` (1.8.1, spec section 4): finding the inventory in PlayerGameData. A fake game: PlayerGameData with a pointer to an
object that holds a list of entries (a handle, the item id with its kind in the top four bits, a quantity, a place), goods among
weapons and empty places, and an EquipParamGoods table to tell goods ids by."""
import json
import struct
from types import SimpleNamespace

from eldendisk.commands import read as read_cmd
from eldendisk.game import invprobe as IP
from eldendisk.game.layout import Layout
from tests import paramfile as pf
from tests.test_disk import BASE, GD, world
from tests.test_param_tables import encode, put_table

INV = 0x500000000
GOODS = [100, 130, 1090, 2919, 8000, 10010, 15000, 20651, 2230000]


class Mem(pf.Pages):
    def u32(self, a, v): self.put(a, struct.pack("<I", v))
    def u64(self, a, v): self.put(a, struct.pack("<Q", v))
    def f32(self, a, v): self.put(a, struct.pack("<f", v))


def game(entries, *, at=0x5D8, start=0x40, stride=16):
    """PlayerGameData + `at` -> INV; the list from INV + `start`: (kind, id, quantity) per entry, None for an empty place."""
    m = Mem()
    world(m)
    m.put(GD, b"\0" * 0x800 + struct.pack("<II", 386, 0))           # PlayerGameData has room to be looked through
    world(m)
    m.u64(GD + at, INV)
    raw = bytearray(start + len(entries) * stride + 0x100)
    for n, e in enumerate(entries):
        if e is None:
            struct.pack_into("<IIII", raw, start + n * stride, 0xFFFFFFFF, 0xFFFFFFFF, 0, 0)
        else:
            kind, iid, qty = e
            struct.pack_into("<IIII", raw, start + n * stride, 0x80000000 | n, (kind << 28) | iid, qty, n)
    m.put(INV, bytes(raw))
    put_table(m, "EquipParamGoods", {g: encode("EquipParamGoods") for g in GOODS})
    return m


ITEMS = [(4, 1090, 3), (4, 100, 99), (0, 1000003, 1), None, (4, 130, 12), (4, 2919, 1), (2, 1000, 1), (8, 10, 1), (4, 8000, 1),
         (4, 10010, 25), None, (4, 15000, 7), (4, 20651, 2)]


def run(m):
    gd, why = Layout(m, pf.params_profile(), BASE).locate_game_data()
    return IP.probe_inventory(m, gd, set(GOODS), why or "")


def test_the_list_is_found_with_its_entry_size_and_where_the_quantity_is():
    res = run(game(ITEMS))
    assert res.game_data == GD and res.runs
    r = res.runs[0]
    assert (r.where, r.address, r.stride, r.form, r.qty_at) == ("[PlayerGameData+0x5D8]+0x44", INV + 0x44, 16, "item id", 4)
    assert r.goods == 8 and r.first[:3] == [(1090, 3), (100, 99), (130, 12)]
    assert r.kinds["0x0"] == 1 and r.kinds["0x2"] == 1 and r.kinds["0x8"] == 1          # weapons and the rest are in the same list


def test_another_entry_size_and_an_inline_list_are_found_too():
    m = game([], at=0x5D8)
    raw = bytearray(12 * len(ITEMS))
    for n, e in enumerate(ITEMS):
        if e:
            struct.pack_into("<III", raw, n * 12, (e[0] << 28) | e[1], e[2], n)
    m.put(GD + 0x600, bytes(raw))
    r = next(r for r in run(m).runs if r.where.startswith("PlayerGameData"))
    assert (r.where, r.stride, r.qty_at, r.goods) == ("PlayerGameData+0x600", 12, 4, 8)


def test_too_few_goods_in_a_row_are_not_a_list():
    assert run(game(ITEMS[:4])).runs == []


def test_no_character_says_so():
    m = Mem()
    res = IP.probe_inventory(m, None, set(GOODS), "world not loaded")
    assert res.runs == [] and "world not loaded" in "\n".join(IP.lines(res))


def test_the_command_prints_the_lists_and_writes_nothing(capsys):
    m = game(ITEMS)
    m.write = lambda *a, **k: (_ for _ in ()).throw(AssertionError("the probe must not write"))
    target = SimpleNamespace(profile=pf.params_profile(), base=BASE)
    sampler = Layout(m, pf.params_profile(), BASE)
    assert read_cmd._probe_inventory(SimpleNamespace(json=False), target, m, sampler) == 0
    out = capsys.readouterr().out
    assert "[PlayerGameData+0x5D8]+0x44" in out and "entry 16 bytes" in out and "1090  x3" in out
    assert read_cmd._probe_inventory(SimpleNamespace(json=True), target, m, sampler) == 0
    doc = json.loads(capsys.readouterr().out)["probe_inventory"]
    assert doc["runs"][0]["entry_size"] == 16 and doc["runs"][0]["quantity_from_id"] == 4


def test_probe_takes_inventory():
    import eldendisk.__main__ as cli
    args = cli.build_parser().parse_args(["probe", "inventory"])
    assert args.what == "inventory" and cli.build_parser().parse_args(["probe"]).what is None


def test_find_prints_every_place_of_an_id_with_the_words_around_it():
    m = game(ITEMS)
    gd, why = Layout(m, pf.params_profile(), BASE).locate_game_data()
    res = IP.probe_inventory(m, gd, set(GOODS), "", find=(1090, 15000))
    assert [(i, w) for i, w, _a, _d in res.found] == [(1090, "[PlayerGameData+0x5D8]+0x44"), (15000, "[PlayerGameData+0x5D8]+0xF4")]
    assert "[40000442] 00000003" in res.found[0][3]
    text = "\n".join(IP.lines(res))
    assert "where the ids asked for are" in text and "bytes around the first entries" in text


def test_lists_of_24_byte_entries_are_found_with_their_header_and_the_asked_quantities():
    """The layout the second probe showed in the game: handle, id, quantity, place, two more words."""
    m = Mem()
    world(m)
    m.put(GD, b"\0" * 0x1000)
    world(m)
    m.u64(GD + 0x418, INV)
    rows = [(0xB, 0x4, 1200, 10), (0x8, 0x0, 9000110, 1), (0xB, 0x4, 10100, 16), None, (0xA, 0x2, 1150, 1),
            (0xB, 0x4, 8000, 6), (0x9, 0x1, 50000, 1), (0xC, 0x8, 10000, 1)]
    raw = bytearray(len(rows) * 24 + 0x100)
    for n, r in enumerate(rows):
        if r is None:
            struct.pack_into("<IIIIII", raw, n * 24, 0, 0xFFFFFFFF, 0, 0, 0, 0xFFFFFFFF)
            continue
        h, k, iid, q = r
        handle = (h << 28) | (iid if h in (0xA, 0xB) else 0x10000 + n)
        struct.pack_into("<IIIIII", raw, n * 24, handle, (k << 28) | iid, q, 0x100 + n, 0, 0xFFFFFFFF)
    m.put(INV, bytes(raw))
    gd, _why = Layout(m, pf.params_profile(), BASE).locate_game_data()
    res = IP.probe_inventory(m, gd, set(GOODS), "", find=(1200, 10100))
    t = res.tables[0]
    assert (t.where, t.first, t.entries, t.span) == ("[PlayerGameData+0x418]", 0, 7, 8)
    assert t.kinds == {"0x0": 1, "0x1": 1, "0x2": 1, "0x4": 3, "0x8": 1} and t.asked == [(1200, 10), (10100, 16)]
    assert "lists of 24-byte entries" in "\n".join(IP.lines(res))

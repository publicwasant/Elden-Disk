"""`read --probe-params` (Phase 1, step 1.2a): finding the param files of other tables from the object that chain Z walks.
A fake game: one object, an entry per table in its slots, each entry -> +0x80 -> +0x80 -> a param file."""
import json
import struct
from types import SimpleNamespace

from eldendisk.commands import read as read_cmd
from eldendisk.game import probe as PR
from eldendisk.game.params import ParamStore
from tests import paramfile as pf
from tests.test_disk import BASE

OBJ = 0x330000000
Z_RVA, Z_OFFSETS = next((rva, offs) for rva, offs in pf.CHAINS if offs == (0x4C0, 0x80, 0x80))
SELECTOR = Z_OFFSETS[0]


def put_file(mem, head, ids, row_size, *, gap=0):
    n = len(ids)
    data_start = 0x40 + n * 24 + gap
    header = bytearray(0x40)
    struct.pack_into("<H", header, 0xA, n)
    struct.pack_into("<Q", header, 0x30, data_start)
    mem.put(head, bytes(header))
    mem.put(head + 0x40, b"".join(struct.pack("<IIQQ", rid, 0, data_start + i * row_size, 0) for i, rid in enumerate(ids)))


def entry(mem, slot, head, *, index):
    """OBJ+slot -> entry -> [+0x80] -> middle -> [+0x80] -> head."""
    cells = 0x340000000 + index * 0x10000
    mem.put(OBJ + slot, struct.pack("<Q", cells))
    mem.put(cells + 0x80, struct.pack("<Q", cells + 0x1000))
    mem.put(cells + 0x1000 + 0x80, struct.pack("<Q", head))


def world(tables):
    """tables: {slot: (n rows, row size)}; slot SELECTOR is the SpEffect file."""
    m = pf.Pages()
    m.put(BASE + Z_RVA, struct.pack("<Q", OBJ))
    m.put(OBJ, b"\0" * PR.SCAN_SPAN)
    for i, (slot, (n, size)) in enumerate(sorted(tables.items())):
        head = 0x350000000 + i * 0x2000000
        put_file(m, head, [100 + k for k in range(n)], size)
        entry(m, slot, head, index=i)
    return m


def run(mem):
    return PR.probe(ParamStore(mem, pf.params_profile(), BASE))


TABLES = {SELECTOR: (11354, 912), 0x4F8: (317, 168), 0x540: (15475, 272), 0x500: (40, 24)}


def test_the_files_behind_the_slots_are_found_and_named_by_row_size_and_count():
    res = run(world(TABLES))
    by_slot = {h.slot: h for h in res.hits if h.root_rva == Z_RVA}
    assert set(by_slot) == set(TABLES)
    assert by_slot[SELECTOR].table == "SpEffectParam" and by_slot[SELECTOR].known
    assert by_slot[0x4F8].table == "Magic" and not by_slot[0x4F8].known
    assert by_slot[0x540].table == "BulletParam"
    assert by_slot[0x500].table is None and by_slot[0x500].row_size == 24
    assert by_slot[0x4F8].first_ids == [100, 101, 102]
    assert by_slot[0x4F8].chain == {"rva": f"0x{Z_RVA:X}", "offsets": ["0x4F8", "0x80", "0x80"]}


def test_a_file_an_extension_grew_is_still_named_but_a_wrong_count_is_not():
    res = run(world({SELECTOR: (11354, 912), 0x4F8: (317 + 64, 168), 0x540: (15475 + 5000, 272)}))
    by_slot = {h.slot: h for h in res.hits if h.root_rva == Z_RVA}
    assert by_slot[0x4F8].table == "Magic"
    assert by_slot[0x540].table is None


def test_a_gap_before_the_data_is_accepted_like_the_reader_does():
    m = world({SELECTOR: (11354, 912)})
    put_file(m, 0x360000000, [7 + k for k in range(317)], 168, gap=4096)
    entry(m, 0x4F8, 0x360000000, index=9)
    hit = next(h for h in run(m).hits if h.slot == 0x4F8)
    assert hit.table == "Magic" and hit.gap == 4096


def test_slots_that_are_not_param_files_are_skipped_without_error():
    m = world({SELECTOR: (11354, 912)})
    m.put(OBJ + 0x600, struct.pack("<Q", 0x123))                 # not a user pointer
    m.put(OBJ + 0x608, struct.pack("<Q", 0x370000000))           # a pointer into nothing
    entry(m, 0x610, 0x380000000, index=11)                       # a head that holds zeros
    m.put(0x380000000, b"\0" * 0x40)
    res = run(m)
    assert [h.slot for h in res.hits if h.root_rva == Z_RVA] == [SELECTOR]


def test_an_empty_global_is_said_not_raised():
    m = pf.Pages()
    res = run(m)
    assert res.hits == [] and all("empty or unreadable" in r for r in res.roots)


def test_row_size_is_the_usual_gap_in_any_order():
    assert PR.row_size_of([504, 0, 336, 168]) == 168
    assert PR.row_size_of([5]) is None


def test_a_row_an_extension_put_before_the_data_does_not_change_the_row_size():
    """ShopLineup of the slot-1 build: a new row (small id, so among the first descriptors) sits in the gap, 56 bytes
    from the old data start; the gcd of the gaps was 4."""
    old = [2000 + 52 * i for i in range(20)]
    assert PR.row_size_of([1000, *old]) == 52


def test_shop_with_a_new_row_among_the_first_descriptors_is_named():
    m = pf.Pages()
    m.put(BASE + Z_RVA, struct.pack("<Q", OBJ))
    m.put(OBJ, b"\0" * PR.SCAN_SPAN)
    n, head, data_start = 1297, 0x350000000, 0x40 + 1297 * 24 + 56
    header = bytearray(0x40)
    struct.pack_into("<H", header, 0xA, n)
    struct.pack_into("<Q", header, 0x30, data_start)
    m.put(head, bytes(header))
    offs = [data_start + 52 * i for i in range(n - 1)]
    offs.insert(5, data_start - 56)                    # the new row, fifth in id order
    m.put(head + 0x40, b"".join(struct.pack("<IIQQ", 100 + i, 0, o, 0) for i, o in enumerate(offs)))
    entry(m, 0x820, head, index=1)
    hit = next(h for h in run(m).hits if h.slot == 0x820)
    assert hit.row_size == 52 and hit.table == "ShopLineupParam"


def test_the_text_lists_found_and_missing_tables_with_a_chain_to_paste():
    text = "\n".join(PR.lines(run(world(TABLES))))
    assert "Magic" in text and '"offsets": ["0x4F8", "0x80", "0x80"]' in text.replace("'", '"')
    assert any(l.strip().startswith("EquipParamGoods") and "not found" in l for l in text.splitlines())
    assert "(already in the profile)" in text


def test_the_command_prints_the_probe_and_writes_nothing(capsys):
    m = world(TABLES)
    m.write = lambda *a, **k: (_ for _ in ()).throw(AssertionError("the probe must not write"))
    target = SimpleNamespace(profile=pf.params_profile(), base=BASE)
    assert read_cmd._probe_params(SimpleNamespace(json=False), target, m) == 0
    assert "Magic" in capsys.readouterr().out
    assert read_cmd._probe_params(SimpleNamespace(json=True), target, m) == 0
    doc = json.loads(capsys.readouterr().out)["probe"]
    assert {h["table"] for h in doc["hits"]} >= {"Magic", "BulletParam", "SpEffectParam"}


def test_the_command_fails_when_nothing_is_found(capsys):
    target = SimpleNamespace(profile=pf.params_profile(), base=BASE)
    assert read_cmd._probe_params(SimpleNamespace(json=False), target, pf.Pages()) == 1

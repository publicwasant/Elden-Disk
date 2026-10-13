"""`read --param` (Phase 1, step 1.2b): any row of the six tables, any field by name. A fake game with the chains of
params.catalog; the golden test (needs the pristine regulation.bin) checks the layouts against the real file."""
import hashlib
import json
import os
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

from eldendisk.commands import read as read_cmd
from eldendisk.game import paramtables as PT
from eldendisk.game.paramlayouts import LAYOUTS
from eldendisk.game.params import ParamError, ParamNameError
from eldendisk.game.profile import Incomplete, load_profile
from tests import paramfile as pf
from tests.test_disk import BASE

_FMT = {"s8": "<b", "u8": "<B", "s16": "<h", "u16": "<H", "s32": "<i", "u32": "<I", "f32": "<f"}
OBJ = 0x330000000


def encode(table, **values) -> bytes:
    """A row of `table` with these fields set (bit fields included); the rest is zero."""
    raw = bytearray(LAYOUTS[table]["size"])
    for name, v in values.items():
        ftype, off, _size, bpos, bits, _arr = LAYOUTS[table]["fields"][name]
        if bits:
            cur = struct.unpack_from(_FMT[ftype], raw, off)[0]
            mask = ((1 << bits) - 1) << bpos
            struct.pack_into(_FMT[ftype], raw, off, (cur & ~mask) | ((v << bpos) & mask))
        else:
            struct.pack_into(_FMT[ftype], raw, off, v)
    return bytes(raw)


def put_table(mem, table, rows, *, new_rows=(), pad=0, size=None, index=0):
    """Fake file of `table` wired at its catalog chain. rows / new_rows: {id: bytes}. New rows (an extension's) sit in the gap
    in front of the old data, `pad` bytes after them, like the real grown files."""
    size = size or LAYOUTS[table]["size"]
    ids = sorted({*rows, *new_rows})
    n = len(ids)
    first = 0x40 + n * 24
    gap = len(new_rows) * size + pad
    data_start = first + gap
    head = 0x350000000 + index * 0x4000000
    header = bytearray(0x40)
    struct.pack_into("<H", header, 0xA, n)
    struct.pack_into("<Q", header, 0x30, data_start)
    mem.put(head, bytes(header))
    desc, old, new = [], 0, 0
    for rid in ids:
        if rid in new_rows:
            off = first + new * size
            mem.put(head + off, new_rows[rid])
            new += 1
        else:
            off = data_start + old * size
            mem.put(head + off, rows[rid])
            old += 1
        desc.append(struct.pack("<IIQQ", rid, 0, off, 0))
    mem.put(head + 0x40, b"".join(desc))
    chain = pf.params_profile().params.catalog[table]
    obj = mem.read(BASE + chain.rva, 8)
    if obj is None:
        mem.put(BASE + chain.rva, struct.pack("<Q", OBJ))
    cells = 0x340000000 + index * 0x10000
    mem.put(OBJ + chain.offsets[0], struct.pack("<Q", cells))
    mem.put(cells + chain.offsets[1], struct.pack("<Q", cells + 0x1000))
    mem.put(cells + 0x1000 + chain.offsets[2], struct.pack("<Q", head))
    return head


def tables(mem):
    return PT.Tables(mem, pf.params_profile(), BASE)


MAGIC = {4000: encode("Magic", mp=10), 6210: encode("Magic", mp=18, refCategory1=1, refId1=10621000, refType=17),
         6230: encode("Magic", mp=21, refCategory1=1, refId1=10623000, refType=22, isEnchant=1)}


# ---- names ----
@pytest.mark.parametrize("text,table", [("Magic", "Magic"), ("magicparam", "Magic"), ("EquipParamGoods", "Goods"),
                                        ("SPEFFECT", "SpEffect"), ("SpEffectParam", "SpEffect"), ("bullet", "Bullet"),
                                        ("AtkParam", "AtkParam_Pc"), ("atkparam_pc", "AtkParam_Pc"),
                                        ("ShopLineupParam", "ShopLineup")])
def test_a_table_can_be_typed_any_way_a_person_knows_it(text, table):
    assert PT.table_name(text) == table


def test_a_reference_is_table_id_and_optionally_a_field():
    assert PT.parse_ref("Magic.6230") == ("Magic", 6230, None)
    assert PT.parse_ref("params.magic.6230.mp*") == ("Magic", 6230, "mp*")
    for bad in ("Magic", "Magic.x", "Nothing.1", "Magic.1.a.b", ""):
        with pytest.raises(ParamNameError):
            PT.parse_ref(bad)


# ---- decoding ----
def test_a_row_is_decoded_field_by_field_with_bits_and_rounded_floats():
    row = PT.decode_row("Magic", MAGIC[6230])
    assert row["mp"] == 21 and row["refCategory1"] == 1 and row["refId1"] == 10623000 and row["refType"] == 22
    assert row["isEnchant"] == 1 and row["isShieldEnchant"] == 0         # two bits of the same byte
    assert list(row) == list(LAYOUTS["Magic"]["fields"])                   # the layout's order
    sp = PT.decode_row("SpEffect", encode("SpEffect", changeHpRate=-0.1, effectEndurance=2.0))
    assert sp["changeHpRate"] == -0.1 and sp["effectEndurance"] == 2.0     # 0.1 and not 0.10000000149


def test_a_row_of_the_wrong_length_is_refused():
    with pytest.raises(ParamError, match="168 bytes"):
        PT.decode_row("Magic", b"\0" * 100)


def test_pick_takes_fields_by_name_or_pattern_in_any_letter_case():
    row = PT.decode_row("Magic", MAGIC[6230])
    assert list(PT.pick(row, "MP")) == ["mp"]
    assert {"refId1", "refId2", "refId3", "refId4"} <= set(PT.pick(row, "refid?"))
    assert PT.pick(row, None) is row
    with pytest.raises(ParamNameError):
        PT.pick(row, "nope*")


# ---- the game ----
def test_a_row_is_found_by_id_in_the_old_data():
    m = pf.Pages()
    put_table(m, "Magic", MAGIC)
    row = tables(m).read_row("Magic", 6230)
    assert row["mp"] == 21 and row["isEnchant"] == 1


def test_a_row_an_extension_added_is_found_in_the_gap():
    m = pf.Pages()
    new = {2230000: encode("Magic", mp=90, refId1=21950111)}
    put_table(m, "Magic", MAGIC, new_rows=new, pad=8)
    t = tables(m)
    assert t.read_row("Magic", 2230000)["mp"] == 90 and t.read_row("Magic", 4000)["mp"] == 10


def put_end_grown(mem, table, old_rows, new_rows, relocate, index=0):
    """Fake file of a table an extension grew at its END (grow.py _grow_end): the descriptors grew into the front of the data, the
    `relocate` first old rows were copied behind the strings, the new rows follow the descriptors, `data_start` = end of the
    descriptors, the strings stay where they were."""
    size = LAYOUTS[table]["size"]
    old_ids, new_ids = sorted(old_rows), sorted(new_rows)
    ids = sorted(old_ids + new_ids)
    d0 = 0x40 + len(old_ids) * 24
    strings = d0 + len(old_ids) * size
    first = 0x40 + len(ids) * 24
    assert first + len(new_ids) * size <= d0 + relocate * size
    head = 0x350000000 + index * 0x4000000
    header = bytearray(0x40)
    struct.pack_into("<I", header, 0, strings)
    struct.pack_into("<H", header, 0xA, len(ids))
    struct.pack_into("<Q", header, 0x30, first)
    mem.put(head, bytes(header))
    where = {}
    for i, rid in enumerate(old_ids):
        where[rid] = strings + 16 + i * size if i < relocate else d0 + i * size
    for q, rid in enumerate(new_ids):
        where[rid] = first + q * size
    for rid, off in where.items():
        mem.put(head + off, old_rows[rid] if rid in old_rows else new_rows[rid])
    mem.put(head + 0x40, b"".join(struct.pack("<IIQQ", rid, 0, where[rid], 0) for rid in ids))
    chain = pf.params_profile().params.catalog[table]
    obj = mem.read(BASE + chain.rva, 8)
    if obj is None:
        mem.put(BASE + chain.rva, struct.pack("<Q", OBJ))
    cells = 0x340000000 + index * 0x10000
    mem.put(OBJ + chain.offsets[0], struct.pack("<Q", cells))
    mem.put(cells + chain.offsets[1], struct.pack("<Q", cells + 0x1000))
    mem.put(cells + 0x1000 + chain.offsets[2], struct.pack("<Q", head))
    return head


def test_a_table_grown_at_its_end_is_read_in_all_three_places_a_row_can_be():
    m = pf.Pages()
    old = {1000 + i: encode("AtkParam_Pc", atkPhys=i) for i in range(20)}
    new = {710000000: encode("AtkParam_Pc", atkPhys=777), 710000001: encode("AtkParam_Pc", atkPhys=778)}
    put_end_grown(m, "AtkParam_Pc", old, new, relocate=3)
    t = tables(m)
    assert t.read_row("AtkParam_Pc", 1000)["atkPhys"] == 0           # copied behind the strings
    assert t.read_row("AtkParam_Pc", 1010)["atkPhys"] == 10          # still in the old data, counted back from the strings
    assert t.read_row("AtkParam_Pc", 710000001)["atkPhys"] == 778    # new, right after the descriptors
    assert {r: decode["atkPhys"] for r, decode in ((i, PT.decode_row("AtkParam_Pc", b)) for i, b in t.all_rows("AtkParam_Pc").items())} == \
        {**{k: i for i, k in enumerate(sorted(old))}, 710000000: 777, 710000001: 778}


def test_a_row_far_behind_the_strings_or_in_front_of_the_data_is_still_refused():
    m = pf.Pages()
    old = {1000 + i: encode("AtkParam_Pc") for i in range(20)}
    head = put_end_grown(m, "AtkParam_Pc", old, {710000000: encode("AtkParam_Pc")}, relocate=2)
    m.put(head + 0x40 + 8, struct.pack("<Q", 0x10))
    with pytest.raises(ParamError, match="outside the data"):
        tables(m).read_row("AtkParam_Pc", 1000)
    m.put(head + 0x40 + 8, struct.pack("<Q", 64 << 20))
    with pytest.raises(ParamError, match="outside the data"):
        tables(m).read_row("AtkParam_Pc", 1000)


def test_every_table_is_reached_through_its_own_chain():
    m = pf.Pages()
    for i, table in enumerate(LAYOUTS):
        put_table(m, table, {7: encode(table)}, index=i)
    t = tables(m)
    assert all(t.read_row(table, 7) for table in LAYOUTS)


def test_a_missing_row_a_wrong_row_size_and_a_row_outside_the_data_are_errors_not_guesses():
    m = pf.Pages()
    put_table(m, "Magic", MAGIC)
    with pytest.raises(ParamError, match="row 1 is not in the file"):
        tables(m).read_row("Magic", 1)
    m = pf.Pages()
    put_table(m, "Magic", {i: b"\0" * 100 for i in range(1, 40)}, size=100)       # another table's rows behind Magic's chain
    with pytest.raises(ParamError, match="rows are 100 bytes"):
        tables(m).read_row("Magic", 5)
    m = pf.Pages()
    head = put_table(m, "Magic", {**MAGIC, **{5000 + i: encode("Magic") for i in range(30)}})
    m.put(head + 0x40 + 8, struct.pack("<Q", 0x10))                                  # first descriptor now points into the header
    with pytest.raises(ParamError, match="outside the data"):
        tables(m).read_row("Magic", 4000)


def test_a_table_without_a_chain_or_a_file_is_said_not_raised_blindly():
    with pytest.raises(ParamError, match="not found"):
        tables(pf.Pages()).read_row("Magic", 4000)


# ---- the command ----
def run(mem, refs, as_json=False, flat=False):
    target = SimpleNamespace(profile=pf.params_profile(), base=BASE)
    return read_cmd._read_params(SimpleNamespace(json=as_json, flat=flat), target, mem, refs)


def test_flat_prints_one_full_path_per_value_and_writes_nothing(capsys):
    m = pf.Pages()
    put_table(m, "Magic", MAGIC)
    m.write = lambda *a, **k: (_ for _ in ()).throw(AssertionError("read must not write"))
    assert run(m, [("Magic", 6230, "mp"), ("Magic", 6230, "refId1")], flat=True) == 0
    out = capsys.readouterr().out.split("\n")
    assert any(l.split() == ["params.Magic.6230.mp", "21"] for l in out)
    assert any(l.split() == ["params.Magic.6230.refId1", "10623000"] for l in out)
    assert run(m, [("Magic", 6210, None)], as_json=True) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["params.Magic.6210"]["mp"] == 18 and len(doc["params.Magic.6210"]) == len(LAYOUTS["Magic"]["fields"])


def test_the_default_is_a_tree_like_the_other_reads(capsys):
    m = pf.Pages()
    put_table(m, "Magic", MAGIC)
    assert run(m, [("Magic", 6230, "m*")]) == 0
    lines = [l.rstrip() for l in capsys.readouterr().out.split("\n") if l.strip()]
    assert lines[:3] == [" params", "   Magic", "     6230"] and any(l.split() == ["mp", "21"] for l in lines)
    assert not any("params.Magic" in l for l in lines)


def test_the_command_fails_clearly(capsys):
    assert run(pf.Pages(), [("Magic", 6230, None)]) == 1
    m = pf.Pages()
    put_table(m, "Magic", MAGIC)
    assert run(m, [("Magic", 6230, "zzz")]) == 1


# ---- the profile and the layouts ----
def test_the_profile_has_a_chain_for_each_of_the_six_tables():
    assert set(pf.params_profile().params.catalog) == set(LAYOUTS)


def test_a_catalog_with_an_unknown_table_is_refused(tmp_path):
    doc = json.loads(pf.OFFSETS.read_text())
    doc["profiles"][pf.EXE_SHA]["params"]["catalog"]["Nothing"] = {"rva": "0x10", "offsets": ["0x8"]}
    p = tmp_path / "offsets.json"
    p.write_text(json.dumps(doc))
    prof, why = load_profile(p, pf.EXE_SHA)
    assert prof is None and "Nothing" in why


def test_the_layouts_agree_with_the_ones_innovate_items_uses():
    from eldendisk.extension.innovate_items.paramdefs import PARAMDEFS
    for ext, ours in {"goods": "Goods", "magic": "Magic", "sp": "SpEffect", "shop": "ShopLineup"}.items():
        assert PARAMDEFS[ext]["size"] == LAYOUTS[ours]["size"]
        assert PARAMDEFS[ext]["fields"] == LAYOUTS[ours]["fields"]


# ---- the real file ----
ORIG = os.environ.get("ELDENDISK_REGULATION_ORIG")


@pytest.mark.skipif(not ORIG or not Path(ORIG).is_file(), reason="set ELDENDISK_REGULATION_ORIG to the pristine regulation.bin")
def test_every_row_of_the_real_tables_decodes_and_black_flame_is_where_the_survey_found_it():
    import struct as st
    from eldendisk.extension.innovate_items import bases, container, zstd
    from eldendisk.extension.innovate_items.container import Bnd4
    data = Path(ORIG).read_bytes()
    assert hashlib.sha256(data).hexdigest() == bases.BASES[bases.CURRENT_BASE]
    dcx = container.decrypt(data)
    body = zstd.decode_frame(dcx[0x4C:0x4C + st.unpack(">I", dcx[0x20:0x24])[0]])
    bnd = Bnd4(body)
    files = {"Goods": "EquipParamGoods", "Magic": "Magic", "SpEffect": "SpEffectParam", "Bullet": "Bullet",
             "AtkParam_Pc": "AtkParam_Pc", "ShopLineup": "ShopLineupParam"}
    rows = {}
    for table, fname in files.items():
        raw = bnd.get(fname).data
        n, size = st.unpack_from("<H", raw, 0xA)[0], LAYOUTS[table]["size"]
        start = st.unpack_from("<Q", raw, 0x30)[0]
        assert start == 0x40 + n * 24
        offs = [st.unpack_from("<IIQQ", raw, 0x40 + i * 24) for i in range(n)]
        assert all(o[2] % size == start % size for o in offs)
        for rid, _pad, off, _x in offs[::max(1, n // 400)]:
            PT.decode_row(table, raw[off:off + size])
        rows[table] = {rid: raw[off:off + size] for rid, _p, off, _x in offs if rid in (6210, 6230, 10621001, 1621000)}
    m6210 = PT.decode_row("Magic", rows["Magic"][6210])
    assert (m6210["mp"], m6210["refCategory1"], m6210["refId1"], m6210["refType"]) == (18, 1, 10621000, 17)
    assert PT.decode_row("Bullet", rows["Bullet"][10621001])["spEffectId0"] == 1621000
    burn = PT.decode_row("SpEffect", rows["SpEffect"][1621000])
    assert burn["effectEndurance"] == 2.0 and burn["changeHpRate"] == 0.1 and burn["changeHpPoint"] == 1


# ---- 1.7.2: the row index (a long-lived Tables reads the whole descriptor table once) ----
class _Counting(pf.Pages):
    def __init__(self):
        super().__init__()
        self.sizes = []

    def read(self, addr, size):
        self.sizes.append(size)
        return super().read(addr, size)


def test_a_row_read_again_reads_one_descriptor_not_the_whole_table():
    m = _Counting()
    put_table(m, "Magic", MAGIC)
    t = tables(m)
    whole = len(MAGIC) * 24                                                          # the descriptor table
    assert t.read_row("Magic", 6230)["mp"] == 21 and whole in m.sizes
    m.sizes.clear()
    assert t.read_row("Magic", 6210)["mp"] == 18 and t.read_row("Magic", 6230)["mp"] == 21
    assert whole not in m.sizes and m.sizes.count(24) == 2                            # one descriptor per row, not the table


def test_a_changed_table_is_indexed_again():
    m = pf.Pages()
    put_table(m, "Magic", MAGIC)
    t = tables(m)
    assert t.read_row("Magic", 6230)["mp"] == 21
    put_table(m, "Magic", {**MAGIC, 7000: encode("Magic", mp=77)})               # another row count: the index is built again
    assert t.read_row("Magic", 7000)["mp"] == 77 and t.read_row("Magic", 6230)["mp"] == 21


def test_a_descriptor_that_no_longer_names_the_row_makes_the_index_again():
    m = pf.Pages()
    head = put_table(m, "Magic", MAGIC)
    t = tables(m)
    t.read_row("Magic", 6230)
    i = t._index["Magic"][3][6230]
    other = t._index["Magic"][3][6210]
    a, b = m.read(head + 0x40 + i * 24, 24), m.read(head + 0x40 + other * 24, 24)
    m.put(head + 0x40 + i * 24, b)                                                   # the two descriptors swapped places
    m.put(head + 0x40 + other * 24, a)
    assert t.read_row("Magic", 6230)["mp"] == 21 and t.read_row("Magic", 6210)["mp"] == 18

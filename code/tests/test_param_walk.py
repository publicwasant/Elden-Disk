"""1.8.0 part 4: every table of the game, found by walking `params.repository` (the list the game keeps every table in).
A fake game: the global -> an object; slot n at +first + n*stride -> a slot object -> +0x80 -> +0x80 -> a param file that
says its param type, like the game's. Each file is then named by its type and rows, its first and last id, the digest of its rows
or the name next to its slot; anything else is left out with the reason."""
import copy
import json
import struct
from types import SimpleNamespace

import pytest

from eldendisk.commands import read as read_cmd
from eldendisk.creative.scripts.backend import LazyRows
from eldendisk.creative.scripts import edstdlib
from eldendisk.game import paramtables as PT
from eldendisk.game import probe as PR
from eldendisk.game.paramlayouts import LAYOUTS
from eldendisk.game.params import ParamError
from tests import paramfile as pf
from tests.test_disk import BASE
from tests.test_param_tables import encode

REPO = pf.params_profile().params.repository
OBJ = 0x360000000


def put_file(mem, head, ptype, rows, stride):
    """A param file at `head`: rows {id: bytes}, data right after the descriptors, the param type after the data."""
    ids = sorted(rows)
    data_start = 0x40 + len(ids) * 24
    type_at = data_start + len(ids) * stride
    header = bytearray(0x40)
    struct.pack_into("<H", header, 0xA, len(ids))
    struct.pack_into("<Q", header, PT.TYPE_AT, type_at)
    struct.pack_into("<Q", header, 0x30, data_start)
    mem.put(head, bytes(header))
    mem.put(head + 0x40, b"".join(struct.pack("<IIQQ", rid, 0, data_start + i * stride, 0) for i, rid in enumerate(ids)))
    mem.put(head + data_start, b"".join(rows[rid] for rid in ids))
    mem.put(head + type_at, ptype.encode("ascii") + b"\0")


def put_slot(mem, n, ptype, rows, stride, *, name=None):
    """Slot n of the list -> its file. `name`: the table's name in UTF-16 behind a pointer in the slot's object, as the game
    keeps it; a list: its own name, then the names of the slots around it, each behind a pointer of its own (as in the game)."""
    if mem.read(BASE + REPO.rva, 8) is None:
        mem.put(BASE + REPO.rva, struct.pack("<Q", OBJ))
    slot = 0x370000000 + n * 0x10000
    head = 0x400000000 + n * 0x1000000
    mem.put(OBJ + REPO.first + n * REPO.stride, struct.pack("<Q", slot))
    mem.put(slot + REPO.tail[0], struct.pack("<Q", slot + 0x1000))
    mem.put(slot + 0x1000 + REPO.tail[1], struct.pack("<Q", head))
    for i, text in enumerate([name] if isinstance(name, str) else name or []):
        mem.put(slot + 0x10 + 8 * i, struct.pack("<Q", slot + 0x2000 + 0x100 * i))
        mem.put(slot + 0x2000 + 0x100 * i, text.encode("utf-16-le") + b"\0\0")
    put_file(mem, head, ptype, rows, stride)
    return head


def like(table, n=None, *, first=None, last=None, **values):
    """Rows shaped like `table`'s file in the game: its row count (or n), its first and last id."""
    v = LAYOUTS[table]
    n = v["rows"] if n is None else n
    first = v["first"] if first is None else first
    last = v["last"] if last is None else last
    ids = [first + i for i in range(n - 1)] + [last]
    row = encode(table, **values) if v["fields"] else b"\0" * v["stride"]
    return {rid: row for rid in ids}


def put_like(mem, slot, table, *, name=None, **kw):
    return put_slot(mem, slot, LAYOUTS[table]["type"], like(table, **kw), LAYOUTS[table]["stride"], name=name)


def tables(mem):
    return PT.Tables(mem, pf.params_profile(), BASE)


def by_slot(mem):
    return {s.slot: s for s in tables(mem).found()}


# ---- naming a file -------------------------------------------------------------------------------------------------
def test_a_table_alone_of_its_type_is_named_by_type_and_rows_and_read_through_its_slot():
    m = pf.Pages()
    put_like(m, 40, "BonfireWarpTabParam")
    t = tables(m)
    [s] = t.found()
    assert (s.slot, s.table, s.stride, s.rows) == (40, "BonfireWarpTabParam", 16, 19)
    assert t.chain_of("bonfirewarptabparam") == REPO.chain(40)
    assert t.index() == {"BonfireWarpTabParam": {"rows": 19}}
    first = LAYOUTS["BonfireWarpTabParam"]["first"]
    assert t.ids("BonfireWarpTabParam")[0] == first and isinstance(t.read_row("BonfireWarpTabParam", first), dict)


def test_a_table_a_build_grew_is_still_named():
    m = pf.Pages()
    put_like(m, 7, "BonfireWarpTabParam", n=19 + PT.MAX_EXTRA)
    assert by_slot(m)[7].table == "BonfireWarpTabParam"
    m = pf.Pages()
    put_like(m, 7, "BonfireWarpTabParam", n=19 + PT.MAX_EXTRA + 1)
    s = by_slot(m)[7]
    assert s.table is None and "no table of type" in s.why


def test_tables_of_one_type_are_told_apart_by_their_rows_and_ids():
    m = pf.Pages()
    put_like(m, 1, "GrassTypeParam_Lv1")             # 73 rows: within MAX_EXTRA of Lv2's 58 too
    put_like(m, 2, "GrassTypeParam_Lv2")
    found = by_slot(m)
    assert found[1].table == "GrassTypeParam_Lv1" and found[2].table == "GrassTypeParam_Lv2"


def test_tables_of_one_shape_are_told_apart_by_the_digest_of_their_rows(monkeypatch):
    hp, mp = like("HPEstusFlaskRecoveryParam", host=1), like("MPEstusFlaskRecoveryParam", host=2)
    stride = LAYOUTS["HPEstusFlaskRecoveryParam"]["stride"]
    for table, rows in (("HPEstusFlaskRecoveryParam", hp), ("MPEstusFlaskRecoveryParam", mp)):
        digest = PT.hashlib.sha256(b"".join(rows[i] for i in sorted(rows))).hexdigest()[:16]
        monkeypatch.setitem(LAYOUTS, table, {**LAYOUTS[table], "digest": digest})      # the game's own rows, as generated
    m = pf.Pages()
    put_slot(m, 5, "ESTUS_FLASK_RECOVERY_PARAM_ST", mp, stride)
    put_slot(m, 6, "ESTUS_FLASK_RECOVERY_PARAM_ST", hp, stride)
    found = by_slot(m)
    assert found[5].table == "MPEstusFlaskRecoveryParam" and found[6].table == "HPEstusFlaskRecoveryParam"


def test_tables_of_identical_rows_are_told_apart_by_the_name_next_to_their_slot():
    m = pf.Pages()
    put_like(m, 10, "MultiHPEstusFlaskBonusParam", name="MultiHPEstusFlaskBonusParam")
    put_like(m, 11, "MultiMPEstusFlaskBonusParam", name="MultiMPEstusFlaskBonusParam")
    found = by_slot(m)
    assert found[10].table == "MultiHPEstusFlaskBonusParam" and found[11].table == "MultiMPEstusFlaskBonusParam"


def test_the_first_name_next_to_a_slot_is_its_own_and_the_names_after_it_are_its_neighbours():
    """As in the game (probe, 2026-10-15): slot 94 reads `..._ps4, ..._ps5`, slot 95 `..._ps5, ..._xb1`."""
    m = pf.Pages()
    base = "LoadBalancerDrawDistScaleParam"
    put_like(m, 93, base, name=[base, "MapMimicryEstablishmentParam", f"{base}_ps4"])
    put_like(m, 94, f"{base}_ps4", name=[f"{base}_ps4", "LoadBalancerDrawDistScal", f"{base}_ps5"])
    put_like(m, 95, f"{base}_ps5", name=[f"{base}_ps5", f"{base}_xb1"])
    put_like(m, 96, "KeyAssignParam_TypeB", name=["MultiPlayCorrectionParam", "KeyAssignParam_TypeB"])   # its own is no candidate
    found = by_slot(m)
    assert [found[n].table for n in (93, 94, 95)] == [base, f"{base}_ps4", f"{base}_ps5"]
    assert found[96].table is None and "cannot be told apart" in found[96].why


def test_tables_that_cannot_be_told_apart_are_left_out_with_the_reason_never_guessed():
    m = pf.Pages()
    put_like(m, 20, "KeyAssignParam_TypeB")
    put_like(m, 21, "KeyAssignParam_TypeC")
    t = tables(m)
    assert all(s.table is None and "cannot be told apart" in s.why for s in t.found())
    assert "KeyAssignParam_TypeB" not in t.index()
    with pytest.raises(ParamError, match="cannot be told apart"):
        t.read_row("KeyAssignParam_TypeB", 0)


def test_two_slots_that_look_like_one_table_are_both_left_out():
    m = pf.Pages()
    put_like(m, 30, "BonfireWarpTabParam")
    put_like(m, 31, "BonfireWarpTabParam")
    t = tables(m)
    assert [(s.table, s.why) for s in t.found()] == [(None, "two slots look like BonfireWarpTabParam")] * 2
    with pytest.raises(ParamError, match="two slots"):
        t.chain_of("BonfireWarpTabParam")


def test_a_slot_that_is_not_a_param_file_is_skipped_and_a_name_that_is_no_table_is_refused():
    m = pf.Pages()
    put_like(m, 3, "BonfireWarpTabParam")
    m.put(OBJ + REPO.first + 4 * REPO.stride, struct.pack("<Q", 0x380000000))      # a slot that leads nowhere readable
    assert [s.slot for s in tables(m).found()] == [3]
    with pytest.raises(PT.ParamNameError):
        tables(m).chain_of("Nothing")


def test_an_empty_list_is_walked_again_only_after_a_while(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(PT.time, "monotonic", lambda: clock[0])
    m = pf.Pages()
    t = tables(m)
    assert t.found() == []
    put_like(m, 40, "BonfireWarpTabParam")                 # the game loads its tables
    assert t.found() == []
    clock[0] += PT.WALK_AGAIN_S
    assert [s.table for s in t.found()] == ["BonfireWarpTabParam"]
    walks = []
    monkeypatch.setattr(t, "_walk", lambda: walks.append(1) or [])
    clock[0] += 60
    t.found()
    assert walks == []                                     # a list that had tables is not walked again


# ---- what a person sees --------------------------------------------------------------------------------------------
def test_read_names_a_table_found_by_the_walk(capsys):
    m = pf.Pages()
    put_like(m, 40, "BonfireWarpTabParam")
    first = LAYOUTS["BonfireWarpTabParam"]["first"]
    target = SimpleNamespace(profile=pf.params_profile(), base=BASE)
    args = SimpleNamespace(json=True, flat=False)
    assert read_cmd._read_params(args, target, m, [PT.parse_ref("params.BonfireWarpTabParam")]) == 0
    table = json.loads(capsys.readouterr().out)["params.BonfireWarpTabParam"]
    assert len(table) == 19 and str(first) in table
    field = next(iter(table[str(first)]))
    assert read_cmd._read_params(args, target, m, [PT.parse_ref(f"params.BonfireWarpTabParam.*.{field}")]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 1


def test_probe_lists_every_slot_with_its_table_and_the_texts_next_to_the_ones_left_out(capsys):
    m = pf.Pages()
    put_like(m, 40, "BonfireWarpTabParam")
    put_like(m, 20, "KeyAssignParam_TypeB", name="SomethingElse")
    put_like(m, 21, "KeyAssignParam_TypeC")
    target = SimpleNamespace(profile=pf.params_profile(), base=BASE)
    assert read_cmd._probe_params(SimpleNamespace(json=False), target, m) == 0
    out = capsys.readouterr().out
    assert any(l.split()[:3] == ["slot", "40", "BonfireWarpTabParam"] for l in out.splitlines())
    assert "texts next to the slot: SomethingElse" in out and "cannot be told apart" in out
    assert "tables of the game not found" in out
    assert read_cmd._probe_params(SimpleNamespace(json=True), target, m) == 0
    rep = json.loads(capsys.readouterr().out)["probe"]["repository"]
    assert {s["slot"]: s["table"] for s in rep["slots"]} == {20: None, 21: None, 40: "BonfireWarpTabParam"}
    assert "BonfireWarpTabParam" not in rep["missing"] and "NpcParam" in rep["missing"]


def test_the_probe_reads_only():
    m = pf.Pages()
    put_like(m, 40, "BonfireWarpTabParam")
    m.write = lambda *a, **k: (_ for _ in ()).throw(AssertionError("the probe must not write"))
    assert PR.walk_report(tables(m))["slots"][0]["table"] == "BonfireWarpTabParam"


# ---- a table in a script's document --------------------------------------------------------------------------------
def test_a_scripts_table_reads_a_row_only_when_it_is_touched():
    reads = []
    rows = LazyRows("NpcParam", 3, lambda t, i: reads.append(i) or {"hp": i * 10}, lambda t: [1, 2, 3])
    assert reads == [] and len(rows) == 3 and list(rows) == ["1", "2", "3"] and 2 in rows and "9" not in rows
    assert rows[2]["hp"] == 20 and rows["2"]["hp"] == 20 and reads == [2]
    with pytest.raises(KeyError):
        rows[9]
    kept = copy.deepcopy(rows)
    assert dict.get(kept, "2") == {"hp": 20} and reads == [2]
    shallow = copy.copy(rows)                                # a snapshot's copy (1.8.4 part 8): the rows read so far, no row read
    assert dict.get(shallow, "2") is dict.get(rows, "2") and reads == [2] and 3 in shallow and 4 not in shallow


def test_a_script_reaches_a_row_by_attribute_and_a_missing_row_says_so_briefly():
    rows = LazyRows("NpcParam", 3, lambda t, i: {"hp": i * 10}, lambda t: [1, 2, 3])
    node = edstdlib.Snapshot({"params": {"NpcParam": rows}}).params
    assert node.NpcParam[3].hp == 30 and node.npcparam["1"].hp == 10
    assert dict(dict.items(rows)) == {}                     # read into the snapshot's own copy of the table, the shared one untouched
    with pytest.raises(KeyError, match="no such row") as e:
        node.NpcParam[7]
    assert "1, 2" not in str(e.value)


# ---- export --params: every row of every table to params.json (1.8.0 part 4) ----------------------------------------
def test_export_params_writes_every_row_of_every_table_one_row_a_line(tmp_path, capsys):
    m = pf.Pages()
    put_like(m, 40, "BonfireWarpTabParam")
    put_like(m, 41, "BuddyParam")                              # no layout fits it: its rows as bytes
    target = SimpleNamespace(profile=pf.params_profile(), base=BASE, exe_path=tmp_path / "game" / "eldenring.exe",
                             sha256="ab" * 32, pid=7)
    m.write = lambda *a, **k: (_ for _ in ()).throw(AssertionError("export must not write to the game"))
    assert read_cmd._export_params(SimpleNamespace(out=str(tmp_path / "out")), target, m) == 0
    path = tmp_path / "out" / "params.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["profile"]["sha256"] == "ab" * 32 and doc["profile"]["pid"] == 7 and doc["skipped"] == {}
    first = LAYOUTS["BonfireWarpTabParam"]["first"]
    assert len(doc["params"]["BonfireWarpTabParam"]) == 19
    assert doc["params"]["BonfireWarpTabParam"][str(first)] == PT.decode_row("BonfireWarpTabParam", like("BonfireWarpTabParam")[first])
    buddy = doc["params"]["BuddyParam"]
    assert len(buddy) == LAYOUTS["BuddyParam"]["rows"] and all(len(r["_raw"]) == 2 * LAYOUTS["BuddyParam"]["stride"] for r in buddy.values())
    lines = path.read_text(encoding="utf-8").splitlines()
    assert any(l.strip().startswith(f'"{first}": {{') and l.rstrip(",").endswith("}") for l in lines)    # a row is one line
    assert not (tmp_path / "out" / "params.json.tmp").exists()


def test_a_table_that_cannot_be_read_is_left_out_with_the_reason():
    class Broken:
        def index(self):
            return {"BonfireWarpTabParam": {}, "Magic": {}}

        def all_rows(self, table, raw=False):
            if table == "Magic":
                raise PT.ParamError("Magic: the file's rows are 1 bytes")
            return {7: bytes(LAYOUTS[table]["size"])}
    from eldendisk.reader.export import params_chunks
    stats = {}
    doc = json.loads("".join(params_chunks(Broken(), {}, None, stats)))
    assert list(doc["params"]) == ["BonfireWarpTabParam"] and doc["skipped"] == {"Magic": "Magic: the file's rows are 1 bytes"}
    assert stats["tables"] == 1 and stats["rows"] == 1


def test_export_params_is_written_once_not_live():
    import eldendisk.__main__ as cli
    with pytest.raises(SystemExit):
        cli.main(["export", "--params", "--live"])


def test_a_scripts_document_has_every_table_though_disk_json_has_none(tmp_path):
    """The tables left disk.json (1.8.0 part 4); a script still reaches them: x.params.<Table>[id] reads the row from the game."""
    from eldendisk.creative.scripts.backend import LiveBackend
    from tests.test_disk import full_world, state_ids
    m = full_world()
    pf.build_file(m, pf.small_ids())
    pf.wire(m, 2)
    target = SimpleNamespace(profile=pf.params_profile(), base=BASE, pid=1, started=1.0, sha256="ab" * 32,
                             exe_path=tmp_path / "eldenring.exe")
    doc = LiveBackend(m, target, state_ids(), tmp_path / "vault").document()
    assert list(doc)[:3] == ["systems", "character", "params"] and list(doc)[-1] == "creative"
    rows = doc["params"]["SpEffectParam"]
    assert isinstance(rows, LazyRows) and len(rows) == len(pf.small_ids())
    assert rows[1621000]["effectEndurance"] == 2.0

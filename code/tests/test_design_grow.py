"""grow.py and ParamView on synthetic archives (no game data): a table gains rows by growing backwards into the entries in front of it.

The case that once went wrong is kept here: the evicted entries must be copied BEFORE the space they leave is overwritten."""
import random
import struct

import pytest

from eldendisk.extension.innovate_items import container, grow
from eldendisk.extension.innovate_items.container import Bnd4, ContainerError, ParamView
from tests import ext_helpers as H

RS = 16
rnd = random.Random(5)


def filler(n):
    return bytes(rnd.randrange(256) for _ in range(n))


def row(rid, fill=None):
    return struct.pack("<i", rid) + bytes([fill if fill is not None else rid & 255]) * (RS - 4)


def table(first, n):
    return H.param_blob([(first + i * 10, row(first + i * 10)) for i in range(n)], RS, b"TYPE\0\0\0\0name\0\0\0\0")


def archive(sizes_before=(100, 3000, 40, 700), n_rows=5, with_second=False):
    """filler entries, table T, an entry after it (and optionally a second table U right after T)."""
    entries = [("N:\\x\\F%d.param" % i, filler(s)) for i, s in enumerate(sizes_before)]
    entries.append(("N:\\x\\Alpha.param", table(1000, n_rows)))
    if with_second:
        entries.append(("N:\\x\\Beta.param", table(5000, 4)))
    entries.append(("N:\\x\\Z.param", filler(55)))
    return H.bnd4_blob(entries), entries


def entry_named(blob, short):
    return [e for e in Bnd4(blob).entries if e.name.endswith("\\%s.param" % short)][0]


def new_rows(ids):
    return [(i, row(i, 0xEE)) for i in ids]


def test_new_rows_are_added_sorted_and_everything_else_is_the_same():
    body, entries = archive()
    out, rep = grow.grow(body, {"Alpha": {"rows": new_rows([1015, 999, 2000]), "name_from": 1010}})
    assert len(out) > len(body) and rep[0]["table"] == "Alpha" and rep[0]["rows"] == 3 and rep[0]["evicted"]
    old, view = ParamView(entry_named(body, "Alpha").data, RS), ParamView(entry_named(out, "Alpha").data, RS)
    assert view.ids() == sorted(old.ids() + [1015, 999, 2000]) and view.count == old.count + 3
    shift = view.strings_off - old.strings_off
    for rid, (doff, noff) in old.offsets().items():            # every old row: same bytes, moved by the same amount
        assert view.find(rid)[2] == old.find(rid)[2] and view.offsets()[rid] == (doff + shift, noff + shift)
    assert all(view.find(i)[2] == row(i, 0xEE) for i in (1015, 999, 2000))
    assert view.tail == old.tail
    name_off = old.find(1010)[1] + shift
    assert all(view.find(i)[1] == name_off for i in (1015, 999, 2000))        # the new rows share the name pointer of `name_from`
    assert (view.head[0x10:0x18] == struct.pack("<Q", view.strings_off))


def test_the_evicted_entries_are_intact_after_they_move():
    """The regression: copying them after the table region was written gave corrupt copies."""
    body, entries = archive(sizes_before=(100, 3000, 40, 700))
    out, rep = grow.grow(body, {"Alpha": {"rows": new_rows(range(2000, 2030)), "name_from": 1010}})     # 30 rows: several entries evicted
    assert len(rep[0]["evicted"]) >= 2
    for name, data in entries:
        if "Alpha" not in name:
            assert entry_named(out, name.rsplit("\\", 1)[-1][:-6]).data == data, name


def test_every_entry_lies_inside_the_body_and_none_overlaps():
    body, _ = archive(with_second=True)
    out, _ = grow.grow(body, {"Alpha": {"rows": new_rows(range(2000, 2040)), "name_from": 1010},
                              "Beta": {"rows": new_rows(range(6000, 6010)), "name_from": 5010}})
    b = Bnd4(out)
    spans = sorted((struct.unpack_from("<I", e.hdr, 0x18)[0], struct.unpack_from("<I", e.hdr, 0x18)[0] + len(e.data)) for e in b.entries)
    assert spans[-1][1] <= len(out) and all(x[1] <= y[0] for x, y in zip(spans, spans[1:]))


def test_a_second_table_may_evict_the_first_after_it_has_grown():
    body, entries = archive(sizes_before=(60, 2000), with_second=True)      # Alpha takes the 2000-byte entry; Beta then needs Alpha
    out, rep = grow.grow(body, {"Alpha": {"rows": new_rows([1005]), "name_from": 1010},
                                "Beta": {"rows": new_rows(range(6000, 6040)), "name_from": 5010}})
    assert [r["table"] for r in rep] == ["Alpha", "Beta"] and "Alpha" in rep[1]["evicted"]
    a, bview = ParamView(entry_named(out, "Alpha").data, RS), ParamView(entry_named(out, "Beta").data, RS)
    assert 1005 in a.ids() and a.count == 6 and bview.count == 44
    assert entry_named(out, "Z").data == entries[-1][1]


def test_no_job_or_an_empty_job_changes_nothing():
    body, _ = archive()
    assert grow.grow(body, {})[0] == body
    assert grow.grow(body, {"Alpha": {"rows": [], "name_from": 1010}})[0] == body


@pytest.mark.parametrize("jobs,message", [
    ({"Alpha": {"rows": new_rows([1010]), "name_from": 1010}}, "already used"),                    # id of an existing row
    ({"Alpha": {"rows": new_rows([2000, 2000]), "name_from": 1010}}, "twice"),
    ({"Alpha": {"rows": [(2000, b"short")], "name_from": 1010}}, "bytes long"),
    ({"Alpha": {"rows": new_rows([2000]), "name_from": 7}}, "name source"),
    ({"Nope": {"rows": new_rows([2000]), "name_from": 1}}, "0 matches"),
])
def test_bad_jobs_are_refused_before_anything_is_written(jobs, message):
    body, _ = archive()
    with pytest.raises(grow.GrowError) as e:
        grow.grow(body, jobs)
    assert message in str(e.value)


def test_a_table_with_nothing_in_front_of_it_cannot_grow_backwards():
    body = H.bnd4_blob([("N:\\x\\Alpha.param", table(1000, 5)), ("N:\\x\\Z.param", filler(20))])
    with pytest.raises(grow.GrowError) as e:
        grow.grow(body, {"Alpha": {"rows": new_rows([2000]), "name_from": 1010}})
    assert "not enough room" in str(e.value)


def test_a_table_that_has_grown_cannot_be_grown_again_from_the_same_bytes():
    body, _ = archive()
    out, _ = grow.grow(body, {"Alpha": {"rows": new_rows([2000]), "name_from": 1010}})
    with pytest.raises(grow.GrowError) as e:
        grow.grow(out, {"Alpha": {"rows": new_rows([2001]), "name_from": 1010}})
    assert "original layout" in str(e.value)


def test_entries_in_front_that_are_not_contiguous_stop_the_growth():
    body, _ = archive()
    b = bytearray(body)
    # make the entry in front of Alpha end 64 bytes before it starts: a hole the code does not know how to account for
    idx = [i for i, e in enumerate(Bnd4(body).entries) if e.name.endswith("Alpha.param")][0]
    pos = 0x40 + 36 * (idx - 1)
    size = struct.unpack_from("<Q", b, pos + 8)[0]
    struct.pack_into("<Q", b, pos + 8, size - 64)
    struct.pack_into("<Q", b, pos + 0x10, size - 64)
    with pytest.raises(grow.GrowError) as e:
        grow.grow(bytes(b), {"Alpha": {"rows": new_rows([2000]), "name_from": 1010}})
    assert "not contiguous" in str(e.value)


def test_growth_is_deterministic():
    body, _ = archive()
    job = {"Alpha": {"rows": new_rows([1015, 999]), "name_from": 1010}}
    assert grow.grow(body, job)[0] == grow.grow(body, job)[0]


# ---------------- ParamView ----------------
def test_param_view_reads_an_untouched_table_like_param():
    blob = table(1000, 6)
    v, p = ParamView(blob, RS), container.Param(blob)
    assert v.ids() == p.ids() and [bytes(r[2]) for r in v.rows] == [bytes(r[2]) for r in p.rows] and v.find(1020)[2] == p.find(1020)[2]
    assert v.find(1) is None and v.tail == p.tail


def _tamper(blob, fn):
    b = bytearray(blob)
    fn(b)
    return bytes(b)


@pytest.mark.parametrize("fn,message", [
    (lambda b: struct.pack_into("<I", b, 0x40 + 24 * 2, 5), "sorted"),                                   # record 2 gets a smaller id
    (lambda b: struct.pack_into("<Q", b, 0x40 + 8, 0x40), "outside the data area"),                       # row points into the records
    (lambda b: struct.pack_into("<Q", b, 0x40 + 8, 10 ** 6), "outside the data area"),
    (lambda b: struct.pack_into("<Q", b, 0x40 + 24 + 8, struct.unpack_from("<Q", b, 0x40 + 8)[0]), "overlap"),    # two rows share data
    (lambda b: struct.pack_into("<Q", b, 0x40 + 16, 10 ** 6), "name pointer"),
    (lambda b: struct.pack_into("<I", b, 0x40 + 4, 1), "padding"),
])
def test_param_view_refuses_a_broken_layout(fn, message):
    with pytest.raises(ContainerError) as e:
        ParamView(_tamper(table(1000, 6), fn), RS)
    assert message in str(e.value)


def test_param_view_refuses_a_file_that_is_too_short_or_has_strings_outside():
    with pytest.raises(ContainerError):
        ParamView(b"short", RS)
    with pytest.raises(ContainerError):
        ParamView(_tamper(table(1000, 6), lambda b: struct.pack_into("<I", b, 0, 10 ** 6)), RS)


# ---------------- growth at the END of the table (AtkParam_Pc: the entry in front of it is too big to move) ----------------
def _end(body, ids, name_from=1010, short="Alpha"):
    return grow.grow(body, {short: {"rows": new_rows(ids), "name_from": name_from, "mode": "end"}})


def test_a_table_grown_at_its_end_keeps_every_row_and_moves_only_the_first_ones():
    body, entries = archive(n_rows=40)
    out, rep = _end(body, [1015, 999, 2000])
    assert rep[0]["mode"] == "end" and rep[0]["relocated"] >= 3 and not (set(rep[0]["evicted"]) - {"Z"})
    old, view = ParamView(entry_named(body, "Alpha").data, RS), ParamView(entry_named(out, "Alpha").data, RS)
    assert view.ids() == sorted(old.ids() + [1015, 999, 2000]) and view.count == old.count + 3
    for rid in old.ids():                                                      # same bytes for every old row
        assert view.find(rid)[2] == old.find(rid)[2]
    assert all(view.find(i)[2] == row(i, 0xEE) for i in (1015, 999, 2000))
    new, was = view.offsets(), old.offsets()
    moved = [i for i in old.ids() if new[i][0] != was[i][0]]
    assert moved == old.ids()[:len(moved)] and len(moved) == rep[0]["relocated"]      # only a prefix of the rows moved
    assert all(new[i][0] >= old.strings_off + len(old.tail) for i in moved)           # ... and they lie behind the old strings
    assert all(new[i][1] == was[i][1] for i in old.ids())                              # no name pointer changed
    assert view.strings_off == old.strings_off and view.tail[:len(old.tail)] == old.tail
    assert view.head[0x30:0x38] == struct.pack("<Q", 0x40 + 24 * view.count) and view.head[0x10:0x18] == old.head[0x10:0x18]
    name_off = old.find(1010)[1]
    assert all(view.find(i)[1] == name_off for i in (1015, 999, 2000))


def test_a_table_grown_at_its_end_leaves_the_other_entries_intact_and_inside_the_body():
    body, entries = archive(n_rows=40)
    out, rep = _end(body, range(3000, 3010))
    for name, data in entries:
        if "Alpha" not in name:
            assert entry_named(out, name.rsplit("\\", 1)[-1][:-6]).data == data, name
    ents = sorted((struct.unpack_from("<I", out, 0x40 + i * Bnd4(out).fhs + 0x18)[0], struct.unpack_from("<Q", out, 0x40 + i * Bnd4(out).fhs + 8)[0])
                  for i in range(len(Bnd4(out).entries)))
    assert all(a + s <= b for (a, s), (b, _) in zip(ents, ents[1:])) and ents[-1][0] + ents[-1][1] <= len(out)


def test_growth_at_the_end_is_deterministic_and_the_front_rows_are_the_only_bytes_that_change_in_the_table():
    body, _ = archive(n_rows=40)
    assert _end(body, [1015, 999])[0] == _end(body, [1015, 999])[0]
    out, rep = _end(body, [1015, 999])
    a, b = entry_named(body, "Alpha"), entry_named(out, "Alpha")
    first_kept = ParamView(a.data, RS).offsets()
    keep_from = min(d for i, (d, _) in ParamView(b.data, RS).offsets().items() if i in first_kept and d == first_kept[i][0])
    assert a.data[keep_from:] == b.data[keep_from:len(a.data)]                  # everything from the first unmoved row on is untouched


def test_growth_at_the_end_refuses_what_the_front_version_refuses():
    body, _ = archive(n_rows=40)
    with pytest.raises(grow.GrowError):
        _end(body, [1010])                                                      # id in use
    with pytest.raises(grow.GrowError):
        _end(body, [5], name_from=424242)                                       # name source missing
    with pytest.raises(grow.GrowError):
        grow.grow(body, {"Alpha": {"rows": [(7, b"short")], "name_from": 1010, "mode": "end"}})     # wrong row size


def test_a_table_at_the_very_end_of_the_body_grows_into_the_end_of_it():
    entries = [("N:\\x\\F0.param", filler(64)), ("N:\\x\\Alpha.param", table(1000, 40))]
    body = H.bnd4_blob(entries)
    out, rep = _end(body, [1015, 999])
    assert not rep[0]["evicted"] and ParamView(entry_named(out, "Alpha").data, RS).count == 42


def test_param_view_accepts_a_row_behind_the_strings_but_not_across_their_start():
    blob = table(1000, 6)
    b = bytearray(blob + bytes(RS))
    strings_off = struct.unpack_from("<I", b, 0)[0]
    struct.pack_into("<Q", b, 0x40 + 8, len(blob) + 0)                 # the first row now lies behind the strings, in the added bytes
    assert ParamView(bytes(b), RS).find(1000) is not None
    struct.pack_into("<Q", b, 0x40 + 8, strings_off - 4)               # across the start of the strings
    with pytest.raises(ContainerError):
        ParamView(bytes(b), RS)

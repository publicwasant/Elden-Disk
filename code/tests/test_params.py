"""Params (spec 1.6.3): finding the SpEffectParam file through the chains, rows by id, names, the profile block, and the
`params` block of the document. A fake file with the layout measured on the real game (docs/experiments/params)."""
import json
import struct
from datetime import datetime, timedelta, timezone

import jsonschema
import pytest

from eldendisk.game import params as P
from eldendisk.game.profile import load_profile
from eldendisk.game.values import is_param_name, normalize
from eldendisk.reader import view
from eldendisk.reader.export import build_document
from eldendisk.reader.sampler import PARAMS_EVERY_S, PARAMS_RETRY_S, Sampler
from tests import paramfile as pf
from tests.test_disk import BASE, SCHEMA, FakeMem, state_ids, full_world, valid

NOW = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)
KEY = "effects"


def store(mem, profile=None):
    return P.ParamStore(mem, profile or pf.params_profile(), BASE)


def small_world(chain=0, **kw):
    m = FakeMem()
    pf.build_file(m, pf.small_ids(), **kw)
    pf.wire(m, chain)
    return m


# ---- the real layout ----
def test_the_real_sized_file_puts_the_rows_where_cheat_engine_measured_them():
    m = pf.Pages()
    addrs = pf.build_file(m, pf.real_ids(), only=set(pf.ROWS.values()))
    pf.wire(m, 0)
    res = store(m).resolve(KEY)
    assert res.head == pf.HEAD
    spec = pf.params_profile().params.tables[KEY]
    for name, off in pf.REAL_ENDURANCE_FROM_HEAD.items():
        key = str(pf.ROWS[name])
        assert res.field_address(key, spec.fields["effectEndurance"]) == pf.HEAD + off
        assert res.rows[key] == addrs[pf.ROWS[name]]
    # 11,354 rows, data start 272,560 = 0x40 + 11,354 * 24 (read in Cheat Engine), black_flame effectEndurance at 0x799188
    assert struct.unpack("<H", m.read(pf.HEAD + 0xA, 2))[0] == 11354
    assert struct.unpack("<Q", m.read(pf.HEAD + 0x30, 8))[0] == 272560 == 0x428B0


def test_every_field_is_read_with_its_type_and_f32_is_shown_rounded():
    doc = store(small_world()).read_all()
    assert list(doc) == [KEY] and list(doc[KEY]) == [str(i) for i in pf.ROWS.values()]
    bf = doc[KEY]["1621000"]
    assert bf == {"name": "Black Flame", "effectEndurance": 2.0, "motionInterval": 0.1, "changeHpRate": 0.1, "changeHpPoint": 1,
                  "atkOccurrenceSpEffectId": -1, "vfxId": 9010}
    assert isinstance(bf["effectEndurance"], float) and isinstance(bf["vfxId"], int)


def test_rows_are_found_by_id_not_by_position():
    ids = pf.small_ids()
    ids[ids.index(pf.ROWS["black_flame"])], ids[ids.index(pf.ROWS["black_flame_blade"])] = \
        ids[ids.index(pf.ROWS["black_flame_blade"])], ids[ids.index(pf.ROWS["black_flame"])]
    rows = {pf.ROWS["black_flame"]: pf.row_bytes(effect_endurance=-1.0)}
    m = FakeMem()
    pf.build_file(m, ids, rows=rows)
    pf.wire(m, 0)
    doc = store(m).read_all()[KEY]
    assert doc["1621000"]["effectEndurance"] == -1.0 and doc["1626001"]["effectEndurance"] == 2.0


# ---- finding the head ----
@pytest.mark.parametrize("chain", [0, 1, 2])
def test_each_of_the_three_chains_leads_to_the_file(chain):
    assert store(small_world(chain)).resolve(KEY).head == pf.HEAD


def test_a_broken_first_chain_falls_back_to_the_next():
    m = small_world(chain=1)
    pf.wire(m, 0, head=0)                       # chain 1 now ends in a null pointer
    assert store(m).resolve(KEY).head == pf.HEAD


def test_a_chain_that_leads_to_something_that_is_not_the_file_is_not_trusted():
    m = small_world(chain=2)
    other = pf.HEAD + 0x2000000
    m.put(other, b"\x01" * 0x40)                # a readable block with nonsense in the header
    pf.wire(m, 0, head=other)
    assert store(m).resolve(KEY).head == pf.HEAD


def test_no_chain_gives_one_error_that_names_every_reason():
    m = FakeMem()
    with pytest.raises(P.ParamError) as exc:
        store(m).resolve(KEY)
    msg = str(exc.value)
    assert "SpEffectParam not found" in msg and "chain 1" in msg and "chain 3" in msg


@pytest.mark.parametrize("kw,why", [
    ({"data_start_field": 12345}, "data start 12345 does not match"),   # the one check that ties the header together
    ({"count_field": 0}, "row count 0"),
    ({"count_field": 60000}, "does not match"),
])
def test_a_header_that_does_not_add_up_is_refused(kw, why):
    m = small_world(**kw)
    with pytest.raises(P.ParamError, match=why):
        store(m).resolve(KEY)


def test_a_file_grown_by_an_extension_has_a_gap_before_its_data_and_is_still_read():
    m = small_world(data_start_field=0x40 + 30 * 24 + 1824)           # two rows' worth of space after the descriptors (SpEffect rows are 912 bytes)
    assert store(m).resolve(KEY).head == pf.HEAD


@pytest.mark.parametrize("gap", [184, 168, 56])
def test_the_gaps_measured_on_the_slot_1_build_are_accepted(gap):
    """Goods 184 (176 + 8 padding), Magic 168, Shop 56 (52 + 4 padding): found with `read --probe-params` on the real game."""
    m = small_world(data_start_field=0x40 + 30 * 24 + gap)
    info, why = store(m)._check_head(pf.HEAD)      # the header only: the fake rows are not moved behind the gap
    assert info == (30, 0x40 + 30 * 24 + gap), why


@pytest.mark.parametrize("gap", [-16, 6, (1 << 20) + 16])
def test_a_gap_that_is_not_a_whole_number_of_4s_or_too_big_or_negative_is_refused(gap):
    m = small_world(data_start_field=0x40 + 30 * 24 + gap)
    with pytest.raises(P.ParamError, match="does not match"):
        store(m).resolve(KEY)


def test_the_row_count_is_not_hard_coded():
    m = FakeMem()
    ids = pf.small_ids(extra_rows=range(5_000_000, 5_000_020))
    pf.build_file(m, ids)
    pf.wire(m, 0)
    assert store(m).resolve(KEY).head == pf.HEAD


# ---- rows ----
def test_a_row_id_that_is_not_in_the_file_is_an_error():
    m = FakeMem()
    pf.build_file(m, [i for i in pf.small_ids() if i != pf.ROWS["black_flame_ritual"]])
    pf.wire(m, 0)
    with pytest.raises(P.ParamError, match="1625000 .Black Flame Ritual. is not in the file"):
        store(m).resolve(KEY)


@pytest.mark.parametrize("shift", [1, 912 * 1000, -8])
def test_a_row_offset_outside_the_data_or_off_the_row_grid_is_refused(shift):
    m = small_world()
    idx = pf.small_ids().index(pf.ROWS["black_flame"])
    desc = pf.HEAD + 0x40 + idx * 24 + 8
    off = struct.unpack("<Q", m.read(desc, 8))[0]
    m.put(desc, struct.pack("<Q", off + shift))
    with pytest.raises(P.ParamError, match="points outside the data"):
        store(m).resolve(KEY)


def test_an_unreadable_row_stops_the_whole_read():
    m = small_world()
    res = store(m).resolve(KEY)
    for i in range(912):
        m.b.pop(res.rows["1626001"] + i)
    with pytest.raises(P.ParamError, match="unreadable"):
        store(m).read_all()


def test_a_field_that_is_not_a_number_is_an_error_not_a_value_in_the_document():
    m = small_world()
    res = store(m).resolve(KEY)
    m.put(res.rows["1621000"] + 0x8, struct.pack("<I", 0x7FC00000))   # NaN
    with pytest.raises(P.ParamError, match="not a number"):
        store(m).read_all()


# ---- names ----
SPEC = pf.params_profile().params


def hits(name, reset=False):
    h, skipped = P.match_names(SPEC, name, reset=reset)
    return h, skipped


def test_a_field_name_in_any_letter_case_means_that_field():
    for name in ("params.effects.1621000.effectEndurance", "PARAMS.Effects.1621000.EFFECTENDURANCE",
                 normalize("params.effects.1621000.effectEndurance")):
        assert hits(name) == ([(KEY, "1621000", "effectEndurance")], [])


def test_a_pattern_takes_the_rows_it_matches_and_skips_the_locked_fields():
    h, skipped = hits("params.effects.*.*")
    assert len(h) == 4 * 4 and {f for _k, _r, f in h} == {"effectEndurance", "motionInterval", "changeHpRate",
                                                         "changeHpPoint"}
    assert len(skipped) == 4 * 2 and all(s.endswith(("vfxId", "atkOccurrenceSpEffectId")) for s in skipped)
    h, skipped = hits("params.effects.*.effectEndurance")
    assert [r for _k, r, _f in h] == ["1621000", "1623000", "1625000", "1626001"]
    assert skipped == []


@pytest.mark.parametrize("name", ["params.effects.1621000.vfxId", "params.effects.1621000.atkOccurrenceSpEffectId"])
def test_a_locked_field_named_exactly_is_refused(name):
    with pytest.raises(P.ParamLockedError, match="locked"):
        hits(name)
    with pytest.raises(P.ParamLockedError, match="locked"):
        hits(name, reset=True)


def test_a_pattern_that_matches_only_locked_fields_is_refused():
    with pytest.raises(P.ParamLockedError, match="every matching value is locked"):
        hits("params.effects.*.vfxId")


def test_the_name_of_a_row_is_shown_but_never_written_and_never_reported_as_skipped():
    with pytest.raises(P.ParamLockedError, match="locked"):
        hits("params.effects.1621000.name")
    with pytest.raises(P.ParamLockedError, match="every matching value is locked"):
        hits("params.effects.*.name")
    h, skipped = hits("params.effects.1621000.*")        # the four values; vfxId and atkOccurrence... are the locked ones
    assert len(h) == 4 and not any(s.endswith(".name") for s in skipped) and len(skipped) == 2
    h, skipped = hits("params.effects.1621000", reset=True)
    assert len(h) == 4 and not any(s.endswith(".name") for s in skipped)


def test_an_unknown_name_suggests_the_close_ones():
    with pytest.raises(P.ParamNameError, match="did you mean params.effects.1621000.effectEndurance"):
        hits("params.effects.1621000.effectEndurence")
    with pytest.raises(P.ParamNameError, match="matches no value"):
        hits("params.effects.*zzz*.effectEndurance")


def test_a_group_cannot_be_set_but_can_be_reset():
    with pytest.raises(P.ParamNameError, match="is a group"):
        hits("params.effects.1621000")
    h, skipped = hits("params.effects.1621000", reset=True)
    assert [f for _k, _r, f in h] == ["effectEndurance", "motionInterval", "changeHpRate", "changeHpPoint"]
    assert len(skipped) == 2
    h, _ = hits("params.effects", reset=True)
    assert len(h) == 16


def test_values_are_read_as_the_type_of_the_field():
    f32 = SPEC.tables[KEY].fields["effectEndurance"]
    s32 = SPEC.tables[KEY].fields["changeHpPoint"]
    assert P.parse_value(f32, "-1") == -1.0 and isinstance(P.parse_value(f32, "-1"), float)
    assert P.parse_value(f32, "1_000.5") == 1000.5
    assert P.parse_value(s32, "-7") == -7
    for bad in ("abc", "", "nan", "inf"):
        with pytest.raises(P.ParamNameError):
            P.parse_value(f32, bad)
    for bad in ("1.5", "x", ""):
        with pytest.raises(P.ParamNameError, match="whole number"):
            P.parse_value(s32, bad)


def test_values_are_clamped_to_the_range_of_the_profile():
    f = SPEC.tables[KEY].fields["effectEndurance"]
    assert (P.clamp(f, -5), P.clamp(f, 1e9), P.clamp(f, 3.5)) == (-1, 9999, 3.5)
    m = SPEC.tables[KEY].fields["motionInterval"]
    assert P.clamp(m, 0) == 0.01        # a burn that ticks every frame or never is not a setting


def test_params_names_keep_their_own_rules():
    assert normalize("params.effects.1621000.effectEndurance") == "params.effects.1621000.effectendurance"
    assert normalize("effects.1621000") == "effects.1621000"   # no short form: `params` is always typed in full (and a name that
                                                               # names nothing is not read as a value of the character either)
    assert is_param_name("params") and is_param_name("Params.effects") and not is_param_name("character.buffs") and not is_param_name("effects")
    assert normalize("params.attrs.max") == "params.attrs.max"                    # the aliases of the character do not apply


# ---- the profile block ----
def block():
    return json.loads((pf.OFFSETS).read_text())


def load_with(tmp_path, mutate):
    data = block()
    mutate(data["profiles"][pf.EXE_SHA]["params"])
    p = tmp_path / "offsets.json"
    p.write_text(json.dumps(data))
    return load_profile(p, pf.EXE_SHA)


def table(params):
    return params["tables"]["effects"]


def test_the_real_profile_has_the_four_rows_and_the_two_locked_fields():
    prof, why = load_profile(pf.OFFSETS, pf.EXE_SHA)
    assert why is None
    t = prof.params.tables[KEY]
    assert t.table == "SpEffectParam" and t.row_size == 912 and len(t.chains) == 3
    assert {k: (r.id, r.name) for k, r in t.rows.items()} == {
        "1621000": (1621000, "Black Flame"), "1623000": (1623000, "Scouring Black Flame"),
        "1625000": (1625000, "Black Flame Ritual"), "1626001": (1626001, "Black Flame Blade")}
    assert {n for n, f in t.fields.items() if not f.writable} == {"atkOccurrenceSpEffectId", "vfxId"}
    assert all(r.defaults["effectEndurance"] == 2 for r in t.rows.values())
    assert all(isinstance(d, (int, float)) for r in t.rows.values() for d in r.defaults.values())


def test_a_profile_without_params_still_loads_and_has_no_params(tmp_path):
    data = block()
    del data["profiles"][pf.EXE_SHA]["params"]
    p = tmp_path / "o.json"
    p.write_text(json.dumps(data))
    prof, why = load_profile(p, pf.EXE_SHA)
    assert why is None and prof.params is None
    assert Sampler(FakeMem(), prof, state_ids(), BASE).read_params(NOW) == (None, None)


@pytest.mark.parametrize("mutate,why", [
    (lambda p: table(p)["fields"]["vfxId"].update(type="f64"), "type must be one of"),
    (lambda p: table(p)["fields"]["vfxId"].update(offset="0x38E"), "outside a row"),
    (lambda p: table(p)["fields"]["effectEndurance"].pop("max"), "needs min and max"),
    (lambda p: table(p)["fields"]["effectEndurance"].update(min=5, max=1), "needs min and max"),
    (lambda p: table(p)["fields"].update(EFFECTENDURANCE=dict(offset="0x8", type="f32")), "differ only in letter case"),
    (lambda p: table(p)["rows"]["1621000"]["defaults"].pop("motionInterval"), "defaults.motionInterval is not set"),
    (lambda p: table(p)["rows"]["1621000"]["defaults"].update(effectEndurance=-5), "outside"),
    (lambda p: table(p)["rows"]["1621000"]["defaults"].update(vfxId=1), "not a writable field"),
    (lambda p: table(p)["rows"].update({"black_flame": {"name": "x", "defaults": {}}}), "named by its id"),
    (lambda p: table(p)["rows"].update({"01621000": {"name": "x", "defaults": {}}}), "named by its id"),
    (lambda p: table(p)["rows"]["1621000"].pop("name"), "name must be a text"),
    (lambda p: table(p)["fields"].update(Name=dict(offset="0x8", type="f32")), "pick another field name"),
    (lambda p: table(p).update(head_chains=[]), "head_chains is empty"),
    (lambda p: table(p).update(rows={}), "rows is empty"),
    (lambda p: p["file_layout"].update(descriptor_size="0x8"), "descriptor_size is too small"),
    (lambda p: p["file_layout"].pop("data_start"), "data_start is not set"),
    (lambda p: p.update(tables={}), "tables is empty"),
])
def test_a_params_block_that_is_wrong_makes_the_profile_incomplete(tmp_path, mutate, why):
    prof, reason = load_with(tmp_path, mutate)
    assert prof is None and why in reason


# ---- the sampler and the document ----
def world_with_params(**kw):
    m = full_world()
    pf.build_file(m, pf.small_ids(), **kw)
    pf.wire(m, 0)
    return m


def sampler(m):
    return Sampler(m, pf.params_profile(), state_ids(), BASE)


def test_the_sample_carries_the_params_and_the_document_shows_them_after_character():
    m = world_with_params()
    s = sampler(m).sample(NOW)
    assert s.state == "CONNECTED" and s.params[KEY]["1621000"]["vfxId"] == 9010 and s.params_error is None
    doc = build_document(state="CONNECTED", pid=1, anti_cheat="DISABLED_OFFLINE", exe_sha256="ab" * 32,
                         profile_label="Elden Ring 1.17.1", sample=s)
    assert list(doc) == ["systems", "character", "params"] and doc["params"] == s.params
    valid(doc)


def test_params_are_looked_at_about_once_a_second_not_every_frame():
    m = world_with_params()
    sp = sampler(m)
    assert sp.sample(NOW).params[KEY]["1621000"]["effectEndurance"] == 2.0
    res = store(m).resolve(KEY)
    m.put(res.rows["1621000"] + 0x8, struct.pack("<f", -1.0))
    assert sp.sample(NOW + timedelta(seconds=PARAMS_EVERY_S / 2)).params[KEY]["1621000"]["effectEndurance"] == 2.0
    assert sp.sample(NOW + timedelta(seconds=PARAMS_EVERY_S + 0.01)).params[KEY]["1621000"]["effectEndurance"] == -1.0


def test_params_that_cannot_be_read_say_why_and_are_tried_again_soon():
    m = full_world()                                   # a world, but no param file yet
    sp = sampler(m)
    s = sp.sample(NOW)
    assert s.state == "CONNECTED" and s.params is None and "SpEffectParam not found" in s.params_error
    pf.build_file(m, pf.small_ids())
    pf.wire(m, 0)
    assert sp.sample(NOW + timedelta(seconds=PARAMS_RETRY_S / 2)).params is None
    assert sp.sample(NOW + timedelta(seconds=PARAMS_RETRY_S + 0.01)).params is not None


def test_params_never_stop_the_character_from_being_read():
    s = sampler(full_world()).sample(NOW)
    assert s.state == "CONNECTED" and s.character["level"] == 386 and s.params is None


@pytest.mark.parametrize("state,shown", [("CONNECTED", True), ("IDLE", True), ("WAITING_FOR_WORLD", True),
                                         ("DISCONNECTED", False), ("EAC_DETECTED", False)])
def test_params_are_null_when_there_is_no_game_to_look_at(state, shown):
    s = sampler(world_with_params()).sample(NOW)
    doc = build_document(state=state, pid=1, anti_cheat="UNKNOWN", exe_sha256=None, profile_label=None, sample=s)
    assert (doc["params"] is not None) is shown
    if state not in ("EAC_DETECTED",):
        valid(doc)
    assert build_document(state=state, pid=None, anti_cheat="UNKNOWN", exe_sha256=None, profile_label=None,
                          sample=None)["params"] is None


def test_the_schema_checks_the_params_block():
    doc = build_document(state="CONNECTED", pid=1, anti_cheat="DISABLED_OFFLINE", exe_sha256="ab" * 32,
                         profile_label="Elden Ring 1.17.1", sample=sampler(world_with_params()).sample(NOW))
    valid(doc)
    for mutate in (lambda d: d["params"]["effects"]["1621000"].pop("vfxId"),
                   lambda d: d["params"]["effects"]["1621000"].update(vfxId="9010"),
                   lambda d: d["params"]["effects"]["1621000"].update(changeHpPoint=1.5),
                   lambda d: d["params"]["effects"].update({"1621000": 5})):
        bad = json.loads(json.dumps(doc))
        mutate(bad)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, SCHEMA)


def test_a_document_of_1_6_2_without_params_is_still_valid():
    doc = build_document(state="CONNECTED", pid=1, anti_cheat="DISABLED_OFFLINE", exe_sha256="ab" * 32,
                         profile_label="x", sample=sampler(world_with_params()).sample(NOW))
    del doc["params"]
    valid(doc)


# ---- looking things up ----
def doc_with_params():
    s = sampler(world_with_params()).sample(NOW)
    return build_document(state="CONNECTED", pid=1, anti_cheat="DISABLED_OFFLINE", exe_sha256="ab" * 32,
                          profile_label="x", sample=s)


def test_a_query_finds_a_params_value_in_any_letter_case():
    doc = doc_with_params()
    for name in ("params.effects.1621000.effectEndurance", "PARAMS.effects.1621000.effectendurance"):
        assert view.select(doc, name) == [("params.effects.1621000.effectEndurance", 2.0)]
    assert [p for p, _ in view.select(doc, "params.effects.1625*.vfx*")] == ["params.effects.1625000.vfxId"]
    assert len(view.select(doc, "params")) == 1 and len(view.select(doc, "params.effects.1621000")[0][1]) == 7
    with pytest.raises(Exception, match="unknown name"):
        view.select(doc, "params.effects.1621001.effectEndurance")


def test_character_patterns_never_include_params():
    doc = doc_with_params()
    assert not any(p.startswith("params") for p, _ in view.select(doc, "character.*"))


def test_params_numbers_are_shown_as_they_are():
    doc = doc_with_params()
    rows = {r.path: r.value for r in view.rows(view.select(doc, "params.effects.1621000"), flat=True)}
    assert rows["params.effects.1621000.effectEndurance"] == "2.0"
    assert rows["params.effects.1621000.motionInterval"] == "0.1"
    assert rows["params.effects.1621000.vfxId"] == "9010"          # an id, not 9,010
    assert rows["params.effects.1621000.atkOccurrenceSpEffectId"] == "-1"
    one = view.rows(view.select(doc, "params.effects.1621000.changeHpPoint"))
    assert [(r.key, r.value) for r in one] == [("params.effects.1621000.changeHpPoint", "1")]
    tree = view.rows(view.select(doc, "params.effects.1621000"))
    assert [r.key for r in tree][:3] == ["params", "effects", "1621000"]


def test_a_change_of_a_params_value_is_a_change_for_the_live_view():
    a, b = doc_with_params(), doc_with_params()
    b["params"]["effects"]["1621000"]["effectEndurance"] = -1.0
    ch = view.changes(view.flatten(a), view.flatten(b))
    assert ch == [("params.effects.1621000.effectEndurance", 2.0, -1.0)]


def test_a_write_to_the_real_sized_file_lands_where_cheat_engine_wrote_it():
    from eldendisk.writer.writer import MemoryWriter, WriteGate, parse_policy, plan_params
    m = pf.Pages()
    pf.build_file(m, pf.real_ids(), only=set(pf.ROWS.values()))
    pf.wire(m, 2)                                              # the third chain this time
    prof = pf.params_profile()
    policy, _ = plan_params(prof.params, parse_policy(["params.effects.*.effectEndurance=-1"], None))
    gate = WriteGate()
    gate.open()
    w = MemoryWriter(m, Sampler(m, prof, state_ids(), BASE), policy, gate, clock=lambda: 0.0)
    assert [r.wrote for r in w.tick()] == [True] * 4
    assert sorted(m.log) == sorted(pf.HEAD + off for off in pf.REAL_ENDURANCE_FROM_HEAD.values())
    for off in pf.REAL_ENDURANCE_FROM_HEAD.values():
        assert struct.unpack("<f", m.read(pf.HEAD + off, 4))[0] == -1.0

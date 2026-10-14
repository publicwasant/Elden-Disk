"""innovate-items spells service: the design, the base (always the game's own file), the secured state and the decision to build.
The build and the gate are replaced by counters here (the real ones are in test_design_golden.py); what is tested is what
surrounds them: when a build happens, when it does not, and what a failed gate leaves behind."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from eldendisk.creative.innovate_spells import bases
from eldendisk.creative.innovate_spells import service, spec
from eldendisk.creative.innovate_spells.build import Result
from eldendisk.creative.innovate_spells.gate import Verdict

BASE = b"pretend this is the game's regulation.bin" * 50
PKG = Path(spec.__file__).parent
from tests.z4 import ID, SPELL, Z4, file_of, spell_of


@pytest.fixture
def ci(tmp_path, monkeypatch):
    monkeypatch.setitem(bases.BASES, bases.CURRENT_BASE, hashlib.sha256(BASE).hexdigest())
    state = {"makes": [], "verified": [], "problems": []}

    def fake_make(src, spells):
        state["makes"].append([i["id"] for i in spells])
        out = b"BUILT" + json.dumps(spec.build_view({"format": 1, "spells": spells}), sort_keys=True).encode()
        return Result(out, hashlib.sha256(out).hexdigest(), "d" * 64)

    def fake_verify(data, src, spells):
        state["verified"].append((data,))
        return Verdict(list(state["problems"]), ["a note"], {"changed_blocks": 3}, hashlib.sha256(data).hexdigest(), "d" * 64)

    monkeypatch.setattr(service, "make", fake_make)
    monkeypatch.setattr(service, "prepare", lambda data: "SRC")
    monkeypatch.setattr(service.gate, "verify", fake_verify)
    c = service.Spells(tmp_path / "ext", tmp_path / "creative.json")
    c.state, c.game = state, tmp_path / "game-regulation.bin"
    c.game.write_bytes(BASE)
    c.spec_path.write_text(json.dumps(Z4), encoding="utf-8")
    return c


def write_spec(c, doc):
    c.spec_path.write_text(json.dumps(doc), encoding="utf-8")


def edited(fn):
    d = copy.deepcopy(Z4)
    fn(spell_of(d))
    return d


def build_and_secure(c):
    spells = c.items("all")
    base, _ = c.read_base(c.game)
    c.build(spells, base)
    c.secure(spells, c.game)
    c.state["makes"].clear()
    return spells


def decide(c):
    return c.decide(c.items("all"), hashlib.sha256(BASE).hexdigest())


# ---------------- the shipped design ----------------
def test_the_shipped_design_and_schema_are_where_the_service_looks():
    code = PKG.parents[2]
    assert service.PKG_DIR == PKG and service.CODE_DIR == code and (code / "creative.json").is_file()
    assert (PKG / "spells.schema.json").is_file() and not (PKG / "spells.creative.json").exists()
    assert len(spec.normalise(json.loads((code / "creative.json").read_text(encoding="utf-8")))["spells"]) >= 1


def test_the_default_design_is_code_design_json(tmp_path):
    assert service.Spells(tmp_path).spec_path == PKG.parents[2] / "creative.json"


# ---------------- the build ----------------
def test_first_run_has_no_secured_build_so_it_builds(ci):
    d = decide(ci)
    assert not d.use_secured and "no secured build yet" in d.reasons[0] and d.diff == []


def test_a_build_goes_through_the_gate_and_then_replaces_regulation_bin(ci):
    base, _ = ci.read_base(ci.game)
    rep = ci.build(ci.items("all"), base)
    assert rep.built and rep.spells == ["reverse_curse_technique"] and rep.changed_blocks == 3 and rep.notes == ["a note"]
    assert ci.output_path.read_bytes().startswith(b"BUILT") and len(ci.state["verified"]) == 1
    assert ci.state["verified"][0][0] == ci.output_path.read_bytes()
    assert not list(ci.dir.glob("*.tmp"))
    assert sorted(p.name for p in ci.ext.rglob("*") if p.is_file()) == ["regulation.bin", "spells.build.json", "spells.resolved.json"]     # nothing secured by a build


def test_the_gate_judges_the_file_before_it_replaces_the_old_output(ci, monkeypatch):
    base, _ = ci.read_base(ci.game)
    ci.build(ci.items("all"), base)
    old = ci.output_path.read_bytes()
    write_spec(ci, edited(lambda i: i["shop"].update(price=1)))
    seen = []
    real = service.gate.verify

    def spy(data, src, spells):
        seen.append((ci.output_path.read_bytes(), (ci.dir / "regulation.bin.tmp").read_bytes() == data))
        return real(data, src, spells)

    monkeypatch.setattr(service.gate, "verify", spy)
    ci.build(ci.items("all"), base)
    assert seen == [(old, True)] and ci.output_path.read_bytes() != old       # judged on the tmp file read back, old one still there


def test_a_failed_gate_swaps_nothing_and_keeps_the_previous_output_and_the_secured_files(ci):
    build_and_secure(ci)
    before = {p.name: p.read_bytes() for p in ci.dir.iterdir()}
    write_spec(ci, edited(lambda i: i["shop"].update(price=1)))
    ci.state["problems"] = ["R1: the frame decodes to something else"]
    base, _ = ci.read_base(ci.game)
    with pytest.raises(service.GateFailed) as e:
        ci.build(ci.items("all"), base)
    assert "NOT safe for the game" in str(e.value) and "nothing was swapped" in str(e.value) and e.value.problems == ci.state["problems"]
    assert {p.name: p.read_bytes() for p in ci.dir.iterdir()} == before            # no tmp, nothing changed


def test_a_failed_gate_on_a_first_build_leaves_no_file(ci):
    ci.state["problems"] = ["G16: nope"]
    base, _ = ci.read_base(ci.game)
    with pytest.raises(service.GateFailed):
        ci.build(ci.items("all"), base)
    assert not list(ci.dir.glob("*"))


def test_the_decoder_tables_are_dropped_after_a_build_and_a_secure_whatever_the_gate_says(ci):
    """`run` goes on for the whole game after it built: the tables the build decoded with (tens of MB) are not kept."""
    from eldendisk.creative.innovate_spells import zstd
    base, _ = ci.read_base(ci.game)
    for problems, call in (([], lambda: ci.build(ci.items("all"), base)), ([], lambda: ci.secure(ci.items("all"), ci.game)),
                           (["G1: no"], lambda: ci.build(ci.items("all"), base))):
        zstd.build_fse(*zstd.LL_DEF)
        assert zstd._FSE_CACHE
        ci.state["problems"] = problems
        try:
            call()
        except service.GateFailed:
            assert problems
        assert not zstd._FSE_CACHE


def test_dry_run_verifies_in_memory_and_writes_nothing(ci):
    base, _ = ci.read_base(ci.game)
    rep = ci.build(ci.items("all"), base, dry_run=True)
    assert rep.dry_run and not rep.built and ci.state["verified"] and not ci.ext.exists()
    ci.state["problems"] = ["x"]
    with pytest.raises(service.GateFailed):
        ci.build(ci.items("all"), base, dry_run=True)


def test_an_empty_draft_builds_nothing(ci):
    write_spec(ci, file_of({}))
    spells = ci.items("all")
    rep = ci.build(spells, b"")
    assert spells == [] and not rep.built and not ci.state["makes"] and "nothing to build" in rep.reason and not ci.ext.exists()


def test_a_missing_or_invalid_draft_stops_before_anything(ci):
    ci.spec_path.unlink()
    with pytest.raises(service.CreativeError) as e:
        ci.items("all")
    assert "was not found" in str(e.value)
    write_spec(ci, edited(lambda i: i.update(fp_cost=-5)))
    with pytest.raises(service.CreativeError) as e:
        ci.items("all")
    assert "fp_cost" in str(e.value) and not ci.state["makes"] and not ci.ext.exists()


def test_every_slot_is_built_but_a_shop_needs_a_shop_line(ci):
    write_spec(ci, file_of({ID: copy.deepcopy(SPELL), "second": copy.deepcopy(SPELL)}))
    assert [s["slot"] for s in ci.items("all")] == [1, 2]
    assert [s["id"] for s in ci.items("second")] == ["second"]
    seven = {"s%d" % i: copy.deepcopy(SPELL) for i in range(1, 9)}                     # the 8th has a shop: no line left for it
    write_spec(ci, file_of(seven))
    with pytest.raises(service.CreativeError) as e:
        ci.items("all")
    assert "s8 is in slot 8" in str(e.value) and "shop" in str(e.value)
    seven["s8"].pop("shop")                                                             # without a shop it is fine
    write_spec(ci, file_of(seven))
    assert len(ci.items("all")) == 8
    write_spec(ci, file_of({"<id-1>": None, "second": copy.deepcopy(SPELL)}))         # alone, in slot 2
    base, _ = ci.read_base(ci.game)
    assert ci.build(ci.items("second"), base).spells == ["second"] and ci.state["makes"] == [["second"]]
    with pytest.raises(service.CreativeError):
        ci.items("missing")


# ---------------- the base is the game's own file, on every path ----------------
def test_the_base_must_be_the_known_original(ci):
    ci.game.write_bytes(BASE + b"modified")
    with pytest.raises(service.CreativeError) as e:
        ci.read_base(ci.game)
    msg = " ".join(str(e.value).split())
    assert "not a regulation.bin this version knows" in msg and "vault restore" in msg and "close it first" in msg
    with pytest.raises(service.CreativeError):
        ci.read_base(None)
    with pytest.raises(service.CreativeError):
        ci.read_base(ci.game.with_name("missing.bin"))
    assert not ci.ext.exists()


def test_our_own_output_is_never_a_base(ci):
    build_and_secure(ci)
    with pytest.raises(service.CreativeError):
        ci.read_base(ci.output_path)


# ---------------- --secure ----------------
def test_secure_keeps_the_build_and_writes_the_record_last(ci):
    spells = build_and_secure(ci)
    assert sorted(p.name for p in ci.dir.iterdir()) == ["regulation.bin", "regulation.secured.bin", "spells.build.json", "spells.commit.json", "spells.resolved.json"]
    assert ci.secured_bin.read_bytes() == ci.output_path.read_bytes()
    rec = ci.read_secured()
    assert rec["kind"] == service.SECURED_KIND and rec["recipe_version"] == bases.RECIPE_VERSION
    assert rec["base_sha256"] == hashlib.sha256(BASE).hexdigest() and rec["bin"]["sha256"] == hashlib.sha256(ci.secured_bin.read_bytes()).hexdigest()
    assert rec["spec"]["spells"] == spells and not list(ci.dir.glob("*.tmp"))
    assert rec["format"] == service.COMMIT_FORMAT and rec["committed_at"]
    assert rec["rows"] == {ID: service.recipes.slot_rows(1)}              # what the spell took in the game, kept in the commit


def test_secure_needs_a_build_to_exist(ci):
    with pytest.raises(service.CreativeError) as e:
        ci.secure(ci.items("all"), ci.game)
    assert "build it first" in str(e.value) and not ci.secured_path.exists()


def test_secure_runs_the_gate_again_and_a_failure_changes_nothing(ci):
    base, _ = ci.read_base(ci.game)
    ci.build(ci.items("all"), base)
    ci.state["problems"] = ["G12: the stock flag is used twice"]
    with pytest.raises(service.GateFailed) as e:
        ci.secure(ci.items("all"), ci.game)
    assert "G12" in str(e.value) and not ci.secured_bin.exists() and not ci.secured_path.exists()


def test_secure_refuses_a_modified_game_file(ci):
    base, _ = ci.read_base(ci.game)
    ci.build(ci.items("all"), base)
    ci.game.write_bytes(BASE + b"x")
    with pytest.raises(service.CreativeError):
        ci.secure(ci.items("all"), ci.game)
    assert not ci.secured_path.exists()


def test_a_secure_that_stops_half_way_is_just_not_secured(ci, monkeypatch):
    base, _ = ci.read_base(ci.game)
    ci.build(ci.items("all"), base)
    real, n = service._write_atomic, []

    def flaky(path, data):
        n.append(path.name)
        if len(n) == 2:
            raise OSError("disk full")
        real(path, data)

    monkeypatch.setattr(service, "_write_atomic", flaky)
    with pytest.raises(OSError):
        ci.secure(ci.items("all"), ci.game)
    assert n == ["regulation.secured.bin", "spells.commit.json"] and ci.secured_bin.exists() and not ci.secured_path.exists()
    assert not decide(ci).use_secured


# ---------------- the decision: swap the secured file, or build ----------------
def test_unchanged_draft_uses_the_secured_file_and_builds_nothing(ci):
    build_and_secure(ci)
    d = decide(ci)
    assert d.use_secured and d.reasons == [] and d.diff == [] and ci.state["makes"] == []


def test_deciding_never_builds_or_runs_the_gate(ci):
    build_and_secure(ci)
    n = len(ci.state["verified"])
    for _ in range(3):
        decide(ci)
    assert ci.state["makes"] == [] and len(ci.state["verified"]) == n


def test_a_changed_price_needs_a_build_and_the_diff_names_the_field(ci):
    build_and_secure(ci)
    write_spec(ci, edited(lambda i: i["shop"].update(price=40000)))
    d = decide(ci)
    assert not d.use_secured and d.diff == ["reverse_curse_technique.shop.price  34590 -> 40000"]
    assert any("design changed" in r and "1 field" in r for r in d.reasons)


def test_only_a_text_or_formatting_change_keeps_the_secured_file(ci):
    build_and_secure(ci)
    d = edited(lambda i: i.update(text={"goods_name": "Another name", "goods_captions": "x"}))
    s = spell_of(d)
    d["innovate_spells"]["slots"][ID] = dict(reversed(list(s.items())))       # the spell's own keys in another order
    ci.spec_path.write_text(json.dumps(d, indent=8), encoding="utf-8")
    assert decide(ci).use_secured


def test_another_spell_or_a_removed_spell_shows_in_the_diff(ci):
    build_and_secure(ci)
    write_spec(ci, file_of({"second": copy.deepcopy(SPELL)}))
    dec = decide(ci)
    assert not dec.use_secured and "reverse_curse_technique  removed" in dec.diff and "second  added" in dec.diff


def test_a_spell_moved_to_another_slot_is_a_change_because_the_slot_fixes_its_rows(ci):
    build_and_secure(ci)
    d = file_of({"<id-1>": None, ID: copy.deepcopy(SPELL)})
    ci.spec_path.write_text(json.dumps(d), encoding="utf-8")
    dec = service.Spells.decide(ci, spec.normalise(d)["spells"], hashlib.sha256(BASE).hexdigest())
    assert not dec.use_secured and f"{ID}.slot  1 -> 2" in dec.diff


def test_a_missing_secured_bin_needs_a_build(ci):
    build_and_secure(ci)
    ci.secured_bin.unlink()
    d = decide(ci)
    assert not d.use_secured and "regulation.secured.bin is missing" in d.reasons[0]


def test_an_edited_secured_bin_needs_a_build(ci):
    build_and_secure(ci)
    ci.secured_bin.write_bytes(ci.secured_bin.read_bytes() + b"x")
    d = decide(ci)
    assert not d.use_secured and "hash differs" in d.reasons[0]


def test_a_recipe_version_change_needs_a_build(ci, monkeypatch):
    build_and_secure(ci)
    monkeypatch.setattr(bases, "RECIPE_VERSION", bases.RECIPE_VERSION + 1)
    d = decide(ci)
    assert not d.use_secured and "recipes changed" in d.reasons[0]


def test_another_base_file_needs_a_build(ci):
    build_and_secure(ci)
    d = ci.decide(ci.items("all"), "ab" * 32)
    assert not d.use_secured and "not the file the secured build was made on" in d.reasons[0]


@pytest.mark.parametrize("text", ["", "not json", "[]", '{"kind": "other"}', '{"kind": "%s"}' % service.SECURED_KIND])
def test_a_damaged_record_needs_a_build(ci, text):
    build_and_secure(ci)
    ci.secured_path.write_text(text, encoding="utf-8")
    d = decide(ci)
    assert not d.use_secured and "spells.commit.json" in d.reasons[0]


def test_deleting_the_record_forces_a_build(ci):
    build_and_secure(ci)
    ci.secured_path.unlink()
    assert not decide(ci).use_secured


# ---------------- the diff ----------------
def test_diff_specs_lists_every_changed_field_in_dotted_form():
    old = spec.build_view(spec.normalise(Z4))
    new = copy.deepcopy(old)
    new["spells"][0]["effect"]["heal_hp_per_tick"] = 70
    new["spells"][0]["requires"].pop("arcane")
    new["spells"][0]["fp_cost"] = 81
    lines = service.diff_specs(old, new)
    assert lines == ["reverse_curse_technique.effect.heal_hp_per_tick  60 -> 70",
                     "reverse_curse_technique.fp_cost  80 -> 81",
                     "reverse_curse_technique.requires.arcane  10 -> (none)"]
    assert service.diff_specs(old, old) == []


# ---- 1.7.1: the text for the game ----
def test_texts_hold_every_slot_and_the_text_only_of_the_spells_that_are_built(ci):
    from eldendisk.creative.innovate_spells import recipes
    t = ci.texts("all")
    gid = recipes.slot_rows(1)["goods"]
    assert len(t) == 64 and t[gid] == SPELL["text"] and t[gid + 1] == {"goods_name": "", "goods_info": "", "goods_captions": ""}
    write_spec(ci, file_of({ID: copy.deepcopy(SPELL), "second": copy.deepcopy(SPELL)}))
    both, only_first = ci.texts("all"), ci.texts([ID])
    assert both[gid + 1] == SPELL["text"] and only_first[gid + 1]["goods_name"] == "" and only_first[gid] == SPELL["text"]


def test_a_text_change_is_not_a_build_change_for_any_of_the_decisions(ci):
    spells = build_and_secure(ci)
    d = edited(lambda i: i.update(text={"goods_name": "Changed"}))
    write_spec(ci, d)
    changed = ci.items("all")
    base, sha = ci.read_base(ci.game)
    assert ci.decide(changed, sha).use_secured and ci.decide_last(changed, "all", sha).use_secured


# ---- 1.7.1: the colour of the fire ----
def test_flame_color_is_none_without_one_and_the_first_slots_when_there_are_several(ci):
    assert ci.flame_color("all") == (None, None)
    a, b = copy.deepcopy(SPELL), copy.deepcopy(SPELL)
    a["flame_color"], b["flame_color"] = [0.2, 0.65, 1], [1, 0, 0]
    write_spec(ci, file_of({ID: a, "second": b}))
    colour, note = ci.flame_color("all")
    assert colour == (0.2, 0.65, 1.0) and "slot 1" in note and "2 different" in note
    assert ci.flame_color([ID]) == ((0.2, 0.65, 1.0), None)                    # only the spells that are built count
    b["flame_color"] = [0.2, 0.65, 1]
    write_spec(ci, file_of({ID: a, "second": b}))
    assert ci.flame_color("all") == ((0.2, 0.65, 1.0), None)


def test_a_flame_color_change_is_not_a_build_change_for_any_of_the_decisions(ci):
    build_and_secure(ci)
    write_spec(ci, edited(lambda i: i.update(flame_color=[0.2, 0.65, 1])))
    changed = ci.items("all")
    base, sha = ci.read_base(ci.game)
    assert ci.decide(changed, sha).use_secured and ci.decide_last(changed, "all", sha).use_secured


def test_eyes_color_is_none_without_one_and_the_first_slots_when_there_are_several(ci):
    assert ci.eyes_color("all") == (None, None)
    d = file_of({ID: copy.deepcopy(SPELL), "other": copy.deepcopy(SPELL)})
    a, b = spell_of(d, ID), spell_of(d, "other")
    a["positive_curse_energy_eyes"], b["positive_curse_energy_eyes"] = {"color": [0.2, 0.65, 1]}, {"color": [1, 0, 0]}
    write_spec(ci, d)
    colour, note = ci.eyes_color("all")
    assert colour == (0.2, 0.65, 1.0) and "slot 1" in note
    b["positive_curse_energy_eyes"] = {}                                                       # positive curse energy eyes without a colour: the game's gold
    write_spec(ci, d)
    assert ci.eyes_color("all") == ((0.2, 0.65, 1.0), None) and ci.eyes_color(["other"]) == (None, None)


def test_the_eyes_colour_is_no_build_change_but_the_eyes_are(ci):
    write_spec(ci, edited(lambda i: i.update(positive_curse_energy_eyes={})))
    build_and_secure(ci)
    base, sha = ci.read_base(ci.game)
    write_spec(ci, edited(lambda i: i.update(positive_curse_energy_eyes={"color": [0.2, 0.65, 1]})))
    assert ci.decide(ci.items("all"), sha).use_secured
    write_spec(ci, edited(lambda i: i.pop("positive_curse_energy_eyes", None)))
    d = ci.decide(ci.items("all"), sha)
    assert not d.use_secured and any("positive_curse_energy_eyes" in line for line in d.diff)


def test_the_flame_accent_colour_is_the_one_of_the_spell_that_gives_the_fire_its_colour(ci):
    assert ci.flame_accent_color("all") == (None, None)
    d = file_of({ID: copy.deepcopy(SPELL), "other": copy.deepcopy(SPELL)})
    spell_of(d, ID).update(flame_color=[0.2, 0.65, 1], flame_accent_color=[0.55, 0.2, 1])
    spell_of(d, "other").update(flame_color=[0.2, 0.65, 1], flame_accent_color=[1, 0, 0])
    write_spec(ci, d)
    colour, note = ci.flame_accent_color("all")
    assert colour == (0.55, 0.2, 1.0) and "slot 1" in note


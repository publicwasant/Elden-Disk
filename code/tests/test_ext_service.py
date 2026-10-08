"""customize-items service: the draft, the base (always the game's own file), the secured state and the decision to build.
The build and the gate are replaced by counters here (the real ones are in test_ext_golden.py); what is tested is what
surrounds them: when a build happens, when it does not, and what a failed gate leaves behind."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from eldendisk.extension.customize_items import bases, service, spec
from eldendisk.extension.customize_items.build import Result
from eldendisk.extension.customize_items.gate import Verdict

BASE = b"pretend this is the game's regulation.bin" * 50
PKG = Path(spec.__file__).parent
from tests.z4 import Z4


@pytest.fixture
def ci(tmp_path, monkeypatch):
    monkeypatch.setitem(bases.BASES, bases.CURRENT_BASE, hashlib.sha256(BASE).hexdigest())
    state = {"makes": [], "verified": [], "problems": []}

    def fake_make(src, items):
        state["makes"].append([i["id"] for i in items])
        out = b"BUILT" + json.dumps(spec.build_view({"format": 1, "items": items}), sort_keys=True).encode()
        return Result(out, hashlib.sha256(out).hexdigest(), "d" * 64)

    def fake_verify(data, src, items):
        state["verified"].append((data,))
        return Verdict(list(state["problems"]), ["a note"], {"changed_blocks": 3}, hashlib.sha256(data).hexdigest(), "d" * 64)

    monkeypatch.setattr(service, "make", fake_make)
    monkeypatch.setattr(service, "prepare", lambda data: "SRC")
    monkeypatch.setattr(service.gate, "verify", fake_verify)
    c = service.CustomizeItems(tmp_path / "ext", tmp_path / "items.draft.json")
    c.state, c.game = state, tmp_path / "game-regulation.bin"
    c.game.write_bytes(BASE)
    c.spec_path.write_text(json.dumps(Z4), encoding="utf-8")
    return c


def write_spec(c, doc):
    c.spec_path.write_text(json.dumps(doc), encoding="utf-8")


def edited(fn):
    d = copy.deepcopy(Z4)
    fn(d["items"][0])
    return d


def build_and_secure(c):
    items = c.items("all")
    base, _ = c.read_base(c.game)
    c.build(items, base)
    c.secure(items, c.game)
    c.state["makes"].clear()
    return items


def decide(c):
    return c.decide(c.items("all"), hashlib.sha256(BASE).hexdigest())


# ---------------- the shipped draft ----------------
def test_the_shipped_draft_and_schema_are_in_the_package_and_valid():
    assert service.PKG_DIR == PKG and (PKG / "items.draft.json").is_file() and (PKG / "items.schema.json").is_file()
    assert len(spec.normalise(json.loads((PKG / "items.draft.json").read_text(encoding="utf-8")))["items"]) >= 1


def test_the_default_draft_is_the_one_in_the_package(tmp_path):
    assert service.CustomizeItems(tmp_path).spec_path == PKG / "items.draft.json"


# ---------------- the build ----------------
def test_first_run_has_no_secured_build_so_it_builds(ci):
    d = decide(ci)
    assert not d.use_secured and "no secured build yet" in d.reasons[0] and d.diff == []


def test_a_build_goes_through_the_gate_and_then_replaces_regulation_bin(ci):
    base, _ = ci.read_base(ci.game)
    rep = ci.build(ci.items("all"), base)
    assert rep.built and rep.items == ["reverse-curse-technique"] and rep.changed_blocks == 3 and rep.notes == ["a note"]
    assert ci.output_path.read_bytes().startswith(b"BUILT") and len(ci.state["verified"]) == 1
    assert ci.state["verified"][0][0] == ci.output_path.read_bytes()
    assert not list(ci.dir.glob("*.tmp"))
    assert sorted(p.name for p in ci.ext.rglob("*") if p.is_file()) == ["regulation.bin"]     # nothing secured by a build


def test_the_gate_judges_the_file_before_it_replaces_the_old_output(ci, monkeypatch):
    base, _ = ci.read_base(ci.game)
    ci.build(ci.items("all"), base)
    old = ci.output_path.read_bytes()
    write_spec(ci, edited(lambda i: i["shop"].update(price=1)))
    seen = []
    real = service.gate.verify

    def spy(data, src, items):
        seen.append((ci.output_path.read_bytes(), (ci.dir / "regulation.bin.tmp").read_bytes() == data))
        return real(data, src, items)

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


def test_dry_run_verifies_in_memory_and_writes_nothing(ci):
    base, _ = ci.read_base(ci.game)
    rep = ci.build(ci.items("all"), base, dry_run=True)
    assert rep.dry_run and not rep.built and ci.state["verified"] and not ci.ext.exists()
    ci.state["problems"] = ["x"]
    with pytest.raises(service.GateFailed):
        ci.build(ci.items("all"), base, dry_run=True)


def test_an_empty_draft_builds_nothing(ci):
    write_spec(ci, {"format": 1, "items": []})
    items = ci.items("all")
    rep = ci.build(items, b"")
    assert items == [] and not rep.built and not ci.state["makes"] and "nothing to build" in rep.reason and not ci.ext.exists()


def test_a_missing_or_invalid_draft_stops_before_anything(ci):
    ci.spec_path.unlink()
    with pytest.raises(service.ExtensionError) as e:
        ci.items("all")
    assert "was not found" in str(e.value)
    write_spec(ci, edited(lambda i: i.update(fp_cost=-5)))
    with pytest.raises(service.ExtensionError) as e:
        ci.items("all")
    assert "fp_cost" in str(e.value) and not ci.state["makes"] and not ci.ext.exists()


def test_more_than_one_item_needs_an_id_in_this_version(ci):
    d = copy.deepcopy(Z4)
    second = copy.deepcopy(d["items"][0])
    second["id"] = "second"
    d["items"].append(second)
    write_spec(ci, d)
    with pytest.raises(service.ExtensionError) as e:
        ci.items("all")
    assert "one item per file" in str(e.value)
    base, _ = ci.read_base(ci.game)
    assert ci.build(ci.items("second"), base).items == ["second"] and ci.state["makes"] == [["second"]]
    with pytest.raises(service.ExtensionError):
        ci.items("missing")


# ---------------- the base is the game's own file, on every path ----------------
def test_the_base_must_be_the_known_original(ci):
    ci.game.write_bytes(BASE + b"modified")
    with pytest.raises(service.ExtensionError) as e:
        ci.read_base(ci.game)
    msg = " ".join(str(e.value).split())
    assert "not a regulation.bin this version knows" in msg and "vault restore" in msg and "close it first" in msg
    with pytest.raises(service.ExtensionError):
        ci.read_base(None)
    with pytest.raises(service.ExtensionError):
        ci.read_base(ci.game.with_name("missing.bin"))
    assert not ci.ext.exists()


def test_our_own_output_is_never_a_base(ci):
    build_and_secure(ci)
    with pytest.raises(service.ExtensionError):
        ci.read_base(ci.output_path)


# ---------------- --secure ----------------
def test_secure_keeps_the_build_and_writes_the_record_last(ci):
    items = build_and_secure(ci)
    assert sorted(p.name for p in ci.dir.iterdir()) == ["items.secured.json", "regulation.bin", "regulation.secured.bin"]
    assert ci.secured_bin.read_bytes() == ci.output_path.read_bytes()
    rec = ci.read_secured()
    assert rec["kind"] == service.SECURED_KIND and rec["recipe_version"] == bases.RECIPE_VERSION
    assert rec["base_sha256"] == hashlib.sha256(BASE).hexdigest() and rec["bin"]["sha256"] == hashlib.sha256(ci.secured_bin.read_bytes()).hexdigest()
    assert rec["spec"]["items"] == items and not list(ci.dir.glob("*.tmp"))


def test_secure_needs_a_build_to_exist(ci):
    with pytest.raises(service.ExtensionError) as e:
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
    with pytest.raises(service.ExtensionError):
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
    assert n == ["regulation.secured.bin", "items.secured.json"] and ci.secured_bin.exists() and not ci.secured_path.exists()
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
    assert not d.use_secured and d.diff == ["reverse-curse-technique.shop.price  34590 -> 40000"]
    assert any("draft changed" in r and "1 field" in r for r in d.reasons)


def test_only_a_name_or_description_or_formatting_change_keeps_the_secured_file(ci):
    build_and_secure(ci)
    d = edited(lambda i: i.update(name="Another name", description="x"))
    ci.spec_path.write_text(json.dumps(dict(reversed(list(d.items()))), indent=8, sort_keys=True), encoding="utf-8")
    assert decide(ci).use_secured


def test_a_second_item_or_a_removed_item_shows_in_the_diff(ci):
    build_and_secure(ci)
    d = copy.deepcopy(Z4)
    other = copy.deepcopy(d["items"][0])
    other["id"] = "second"
    d["items"] = [other]
    write_spec(ci, d)
    dec = decide(ci)
    assert not dec.use_secured and "reverse-curse-technique  removed" in dec.diff and "second  added" in dec.diff


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
    assert not d.use_secured and "items.secured.json" in d.reasons[0]


def test_deleting_the_record_forces_a_build(ci):
    build_and_secure(ci)
    ci.secured_path.unlink()
    assert not decide(ci).use_secured


# ---------------- the diff ----------------
def test_diff_specs_lists_every_changed_field_in_dotted_form():
    old = spec.build_view(spec.normalise(Z4))
    new = copy.deepcopy(old)
    new["items"][0]["effect"]["heal_hp_per_tick"] = 70
    new["items"][0]["requires"].pop("arcane")
    new["items"][0]["fp_cost"] = 81
    lines = service.diff_specs(old, new)
    assert lines == ["reverse-curse-technique.effect.heal_hp_per_tick  60 -> 70",
                     "reverse-curse-technique.fp_cost  80 -> 81",
                     "reverse-curse-technique.requires.arcane  10 -> (none)"]
    assert service.diff_specs(old, old) == []

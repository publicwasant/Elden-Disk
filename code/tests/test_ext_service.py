"""customize-items service: the spec, the base (always the game's own file), and a build on every call. The build itself is
replaced by a counter here (the real one is in test_ext_golden.py); what is tested is what surrounds it."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from eldendisk.extension.customize_items import bases, service, spec
from eldendisk.extension.customize_items.build import Result

BASE = b"pretend this is the game's regulation.bin" * 50
SOURCES = Path(spec.__file__).parent / "sources"
Z4 = json.loads((SOURCES / "items.json").read_text(encoding="utf-8"))


@pytest.fixture
def ci(tmp_path, monkeypatch):
    monkeypatch.setitem(bases.BASES, bases.CURRENT_BASE, hashlib.sha256(BASE).hexdigest())
    calls = []

    def fake_build(data, items, src=None):
        calls.append([i["id"] for i in items])
        out = b"BUILT" + json.dumps(spec.build_view({"format": 1, "items": items}), sort_keys=True).encode()
        return Result(out, hashlib.sha256(out).hexdigest(), "d" * 64, 3, [])

    monkeypatch.setattr(service, "run_build", fake_build)
    monkeypatch.setattr(service, "prepare", lambda data: None)
    c = service.CustomizeItems(tmp_path / "ext", tmp_path / "items.json")
    c.calls, c.game = calls, tmp_path / "game-regulation.bin"
    c.game.write_bytes(BASE)
    c.spec_path.write_text(json.dumps(Z4), encoding="utf-8")
    return c


def write_spec(c, doc):
    c.spec_path.write_text(json.dumps(doc), encoding="utf-8")


def edited(fn):
    d = copy.deepcopy(Z4)
    fn(d["items"][0])
    return d


def test_the_shipped_spec_is_in_sources_and_valid():
    assert service.SOURCES_DIR == SOURCES and (SOURCES / "items.json").is_file()
    assert len(spec.normalise(Z4)["items"]) == 1


def test_the_default_spec_is_the_one_in_sources(tmp_path):
    assert service.CustomizeItems(tmp_path).spec_path == SOURCES / "items.json"


def test_every_call_builds_even_when_nothing_changed(ci):
    for n in (1, 2, 3):
        rep = ci.build(ci.items("all"), ci.game)
        assert rep.built and rep.items == ["reverse-curse-technique"] and len(ci.calls) == n
    assert ci.output_path.read_bytes().startswith(b"BUILT")
    assert not list(ci.dir.glob("*.tmp"))


def test_only_the_output_is_written_no_manifest_no_base_copy(ci):
    ci.build(ci.items("all"), ci.game)
    assert sorted(p.name for p in ci.ext.rglob("*") if p.is_file()) == ["regulation.bin"]


def test_a_changed_spec_is_simply_built_again(ci):
    ci.build(ci.items("all"), ci.game)
    first = ci.output_path.read_bytes()
    write_spec(ci, edited(lambda i: i["shop"].update(price=1)))
    ci.build(ci.items("all"), ci.game)
    assert ci.output_path.read_bytes() != first and len(ci.calls) == 2


def test_dry_run_writes_nothing(ci):
    rep = ci.build(ci.items("all"), ci.game, dry_run=True)
    assert rep.dry_run and not rep.built and ci.calls and not ci.ext.exists()


def test_an_empty_spec_builds_nothing(ci):
    write_spec(ci, {"format": 1, "items": []})
    items = ci.items("all")
    rep = ci.build(items, ci.game)
    assert items == [] and not rep.built and not ci.calls and "nothing to build" in rep.reason and not ci.ext.exists()


def test_a_missing_or_invalid_spec_stops_before_anything(ci):
    ci.spec_path.unlink()
    with pytest.raises(service.ExtensionError) as e:
        ci.items("all")
    assert "was not found" in str(e.value)
    write_spec(ci, edited(lambda i: i.update(fp_cost=-5)))
    with pytest.raises(service.ExtensionError) as e:
        ci.items("all")
    assert "fp_cost" in str(e.value) and not ci.calls and not ci.ext.exists()


def test_a_failed_build_keeps_the_previous_output(ci):
    ci.build(ci.items("all"), ci.game)
    good = ci.output_path.read_bytes()
    ci.game.write_bytes(BASE + b"modified")
    with pytest.raises(service.ExtensionError):
        ci.build(ci.items("all"), ci.game)
    assert ci.output_path.read_bytes() == good


def test_the_base_is_always_the_games_own_file_and_must_be_the_known_original(ci):
    ci.game.write_bytes(BASE + b"modified")
    with pytest.raises(service.ExtensionError) as e:
        ci.build(ci.items("all"), ci.game)
    assert "not a regulation.bin this version knows" in str(e.value) and "vault restore" in str(e.value) and not ci.ext.exists()
    with pytest.raises(service.ExtensionError):
        ci.build(ci.items("all"), None)
    with pytest.raises(service.ExtensionError):
        ci.build(ci.items("all"), ci.game.with_name("missing.bin"))


def test_a_modified_file_is_never_used_as_a_base_for_the_next_build(ci):
    ci.build(ci.items("all"), ci.game)
    with pytest.raises(service.ExtensionError):
        ci.build(ci.items("all"), ci.output_path)               # our own output is not the original


def test_more_than_one_item_needs_an_id_in_this_version(ci):
    d = copy.deepcopy(Z4)
    second = copy.deepcopy(d["items"][0])
    second["id"] = "second"
    d["items"].append(second)
    write_spec(ci, d)
    with pytest.raises(service.ExtensionError) as e:
        ci.items("all")
    assert "one item per file" in str(e.value)
    assert ci.build(ci.items("second"), ci.game).items == ["second"] and ci.calls == [["second"]]
    with pytest.raises(service.ExtensionError):
        ci.items("missing")

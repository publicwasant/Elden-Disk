"""Phase 2.7: `--add` takes spell paths (several, or `all`), the choice is kept in the build record, and `run` builds the same
selection and reuses the latest build while nothing changed."""
import argparse
import copy
import hashlib
import json

import pytest

import eldendisk.__main__ as cli
import eldendisk.commands.run as run_cmd
from eldendisk.design.innovate_items import bases
from eldendisk.design.innovate_items.spells import service, spec
from eldendisk.design.innovate_items.spells.build import Result
from eldendisk.design.innovate_items.spells.gate import Verdict
from eldendisk.vault import SaveVault
from tests.z4 import ID, SPELL, file_of

BASE = b"pretend this is the game's regulation.bin" * 50
SECOND, THIRD = "second_spell", "third_spell"


def design(**changes):
    second = copy.deepcopy(SPELL)
    second["shop"] = {"price": 2000, "stock": 2}
    third = copy.deepcopy(SPELL)
    third["shop"] = {"price": 3000, "stock": 3}
    doc = file_of({ID: copy.deepcopy(SPELL), SECOND: second, THIRD: third}, maximum=7)
    for k, v in changes.items():
        doc["innovate_items"]["spells"]["slots"][k] = v
    return doc


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setitem(bases.BASES, bases.CURRENT_BASE, hashlib.sha256(BASE).hexdigest())
    monkeypatch.setattr(service, "prepare", lambda data: "SRC")
    builds = []

    def fake(src, spells):
        builds.append([s["id"] for s in spells])
        out = b"BUILT" + json.dumps([s["id"] + str(s["shop"]["price"]) for s in spells]).encode()
        return Result(out, hashlib.sha256(out).hexdigest(), "d" * 64)

    def verify(data, src, spells):
        return Verdict([], [], {"changed_blocks": 3}, hashlib.sha256(data).hexdigest(), "d" * 64)

    monkeypatch.setattr(service, "make", fake)
    monkeypatch.setattr(service.gate, "verify", verify)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    game = tmp_path / "Game"
    game.mkdir()
    (game / "eldenring.exe").write_bytes(b"EXE")
    (game / "regulation.bin").write_bytes(BASE)
    spec_file = tmp_path / "design.json"
    spec_file.write_text(json.dumps(design()), encoding="utf-8")
    return argparse.Namespace(ext=tmp_path / "ext", game=game, spec=spec_file, builds=builds, tmp=tmp_path)


def args_for(w, *more):
    return ["innovate-items", "spells", "--design-dir", str(w.ext), "--spec", str(w.spec), "--game-dir", str(w.game), *more]


def record(w):
    return json.loads((w.ext / "innovate-items" / "spells" / "spells.build.json").read_text(encoding="utf-8"))


def built(w):
    return (w.ext / "innovate-items" / "spells" / "regulation.bin").read_bytes()


def run_args(w):
    return argparse.Namespace(regulation=None, design_dir=str(w.ext), spec=str(w.spec))


def do_run(w, capsys=None):
    return run_cmd._regulation(run_args(w), SaveVault(w.tmp / "vault"), w.game, True)


def text(capsys):
    out = capsys.readouterr()
    return " ".join((out.out + out.err).split())


def set_spec(w, doc):
    w.spec.write_text(json.dumps(doc), encoding="utf-8")


# ---------------- the words of --add ----------------
@pytest.mark.parametrize("given, want", [
    (["all"], "all"), (["spells.slots"], "all"), (["innovate_items.spells.slots"], "all"),
    (["spells.slots.abc"], ["abc"]), (["innovate_items.spells.slots.abc"], ["abc"]), (["abc"], ["abc"]), ("abc", ["abc"]),
    (["spells.slots.b", "spells.slots.a", "b"], ["b", "a"]), ([" spells.slots.a "], ["a"]),
])
def test_what_add_was_given_becomes_all_or_the_ids(given, want):
    assert spec.selection_of(given) == want


@pytest.mark.parametrize("bad", [[], ["all", "spells.slots.a"], ["spells.slots.A"], ["spells.slots."], ["spells.slots.a.b"],
                                 ["weapons.slots.a"], ["<id-6>"], ["spells.slots.all"], [""]])
def test_what_add_cannot_mean_is_refused(bad):
    with pytest.raises(spec.SpecError):
        spec.selection_of(bad)


def test_select_gives_the_spells_in_slot_order_and_names_the_missing_ones():
    s = spec.normalise(design())
    assert [i["id"] for i in spec.select(s, [THIRD, ID])] == [ID, THIRD]
    assert [i["id"] for i in spec.select(s, "all")] == [ID, SECOND, THIRD]
    with pytest.raises(spec.SpecError) as e:
        spec.select(s, ["spells.slots.nope", "spells.slots." + SECOND])
    msg = str(e.value)
    assert "spells.slots.nope" in msg and "spells.slots." + ID in msg and "spells.slots." + THIRD in msg
    with pytest.raises(spec.SpecError) as e:
        spec.select(spec.normalise(file_of({}, maximum=3)), ["a"])
    assert "slots are all empty" in str(e.value)


def test_a_spell_cannot_be_called_all():
    with pytest.raises(spec.SpecError) as e:
        spec.normalise(file_of({"all": copy.deepcopy(SPELL)}, maximum=3))
    assert "reserved" in str(e.value)


# ---------------- --add ----------------
def test_add_with_a_path_builds_only_that_spell_and_remembers_it(world, capsys):
    assert cli.main(args_for(world, "--add", "spells.slots." + SECOND)) == 0
    assert world.builds == [[SECOND]] and record(world)["selection"] == [SECOND]
    assert [s["id"] for s in record(world)["spec"]["spells"]] == [SECOND]
    assert built(world).startswith(b"BUILT") and SECOND.encode() in built(world) and THIRD.encode() not in built(world)
    assert (world.game / "regulation.bin").read_bytes() == BASE


def test_add_with_several_paths_builds_them_in_slot_order(world):
    assert cli.main(args_for(world, "--add", "spells.slots." + THIRD, "spells.slots." + ID)) == 0
    assert world.builds == [[ID, THIRD]] and record(world)["selection"] == [ID, THIRD]


def test_add_all_and_a_bare_id_still_work_and_all_clears_the_choice(world):
    assert cli.main(args_for(world, "--add", SECOND)) == 0
    assert record(world)["selection"] == [SECOND]
    assert cli.main(args_for(world, "--add", "all")) == 0
    assert record(world)["selection"] == "all" and world.builds[-1] == [ID, SECOND, THIRD]


def test_an_unknown_path_is_an_error_that_lists_the_spells_and_writes_nothing(world, capsys):
    assert cli.main(args_for(world, "--add", "spells.slots.nope")) == 1
    out = text(capsys)
    assert "spells.slots.nope" in out and "spells.slots." + ID in out and not world.ext.exists() and world.builds == []


def test_all_does_not_mix_with_paths(world, capsys):
    assert cli.main(args_for(world, "--add", "all", "spells.slots." + ID)) == 1
    assert "stands alone" in text(capsys) and world.builds == []


def test_a_dry_run_changes_neither_the_files_nor_the_selection(world):
    assert cli.main(args_for(world, "--add", "spells.slots." + SECOND)) == 0
    before = (record(world), built(world))
    assert cli.main(args_for(world, "--add", "spells.slots." + ID, "--dry-run")) == 0
    assert (record(world), built(world)) == before


def test_a_failed_gate_keeps_the_old_selection(world, monkeypatch):
    assert cli.main(args_for(world, "--add", "spells.slots." + SECOND)) == 0
    monkeypatch.setattr(service.gate, "verify", lambda d, s, sp: Verdict(["R1: no"], [], {}, "", ""))
    assert cli.main(args_for(world, "--add", "spells.slots." + ID)) == 1
    assert record(world)["selection"] == [SECOND]


# ---------------- run ----------------
def test_without_any_add_run_builds_every_spell(world, capsys):
    out, mode = do_run(world)
    assert mode == "built" and world.builds == [[ID, SECOND, THIRD]] and record(world)["selection"] == "all"
    assert out.name == "regulation.bin"


def test_run_after_add_uses_that_build_without_building_again(world, capsys):
    cli.main(args_for(world, "--add", "spells.slots." + SECOND))
    capsys.readouterr()
    out, mode = do_run(world)
    assert mode == "last" and out == world.ext / "innovate-items" / "spells" / "regulation.bin" and world.builds == [[SECOND]]
    t = text(capsys)
    assert "unchanged since the last build" in t and "no build" in t and "building only" in t and SECOND in t


def test_run_keeps_building_the_chosen_spells_when_the_design_changes(world, capsys):
    cli.main(args_for(world, "--add", "spells.slots." + SECOND))
    doc = design()
    doc["innovate_items"]["spells"]["slots"][SECOND]["shop"]["price"] = 2500
    set_spec(world, doc)
    capsys.readouterr()
    out, mode = do_run(world)
    t = text(capsys)
    assert mode == "built" and world.builds == [[SECOND], [SECOND]] and record(world)["selection"] == [SECOND]
    assert "building only " + SECOND in t and f"left out: {ID}, {THIRD}" in t and "chosen with the last --add" in t
    assert "the design changed since the last build (1 field)" in t and "shop.price 2000 -> 2500" in t


def test_a_change_in_a_spell_that_is_not_chosen_does_not_rebuild(world):
    cli.main(args_for(world, "--add", "spells.slots." + SECOND))
    doc = design()
    doc["innovate_items"]["spells"]["slots"][THIRD]["shop"]["price"] = 9999
    set_spec(world, doc)
    assert do_run(world)[1] == "last" and world.builds == [[SECOND]]


def test_add_all_then_run_builds_everything_again(world):
    cli.main(args_for(world, "--add", "spells.slots." + SECOND))
    cli.main(args_for(world, "--add", "all"))
    assert do_run(world)[1] == "last" and world.builds[-1] == [ID, SECOND, THIRD]


def test_a_chosen_spell_that_left_the_design_stops_run(world):
    cli.main(args_for(world, "--add", "spells.slots." + SECOND))
    doc = design()
    doc["innovate_items"]["spells"]["slots"][SECOND] = None
    set_spec(world, doc)
    with pytest.raises(service.DesignError) as e:
        do_run(world)
    assert "spells.slots." + SECOND in str(e.value)


def test_a_tampered_or_missing_build_is_built_again(world):
    cli.main(args_for(world, "--add", "spells.slots." + SECOND))
    (world.ext / "innovate-items" / "spells" / "regulation.bin").write_bytes(b"other")
    assert do_run(world)[1] == "built" and world.builds == [[SECOND], [SECOND]]
    (world.ext / "innovate-items" / "spells" / "regulation.bin").unlink()
    assert do_run(world)[1] == "built" and len(world.builds) == 3


def test_a_changed_game_file_or_recipe_version_builds_again(world, monkeypatch):
    cli.main(args_for(world, "--add", "spells.slots." + SECOND))
    monkeypatch.setattr(bases, "RECIPE_VERSION", bases.RECIPE_VERSION + 1)
    assert do_run(world)[1] == "built"
    (world.game / "regulation.bin").write_bytes(BASE + b"x")
    with pytest.raises(service.DesignError):
        do_run(world)


def test_an_unreadable_record_builds_every_spell_and_says_so(world, capsys):
    cli.main(args_for(world, "--add", "spells.slots." + SECOND))
    (world.ext / "innovate-items" / "spells" / "spells.build.json").write_text("{not json", encoding="utf-8")
    capsys.readouterr()
    out, mode = do_run(world)
    assert mode == "built" and world.builds[-1] == [ID, SECOND, THIRD] and "cannot be read" in text(capsys)
    assert record(world)["selection"] == "all"


# ---------------- --secure and the secured copy ----------------
def test_secure_keeps_the_chosen_spells_and_run_uses_the_secured_copy(world, capsys):
    cli.main(args_for(world, "--add", "spells.slots." + SECOND))
    capsys.readouterr()
    assert cli.main(args_for(world, "--secure")) == 0
    assert [s["id"] for s in service.Spells(world.ext, world.spec).read_secured()["spec"]["spells"]] == [SECOND]
    assert do_run(world)[1] == "secured" and world.builds == [[SECOND]]


def test_a_secured_build_of_other_spells_is_not_used_for_this_selection(world, capsys):
    cli.main(args_for(world, "--add", "all"))
    cli.main(args_for(world, "--secure"))
    cli.main(args_for(world, "--add", "spells.slots." + SECOND))
    capsys.readouterr()
    assert do_run(world)[1] == "last"                  # the latest build matches; the secured copy holds other spells
    cli.main(args_for(world, "--add", "spells.slots." + THIRD))
    capsys.readouterr()
    (world.ext / "innovate-items" / "spells" / "regulation.bin").write_bytes(b"x")          # force a build
    assert do_run(world)[1] == "built"
    assert f"the secured build holds {ID}, {SECOND}, {THIRD}, this run builds {THIRD}" in text(capsys)


# ---------------- --list ----------------
def test_list_shows_the_selection(world, capsys):
    base = ["design", "--list", "--design-dir", str(world.ext), "--spec", str(world.spec)]
    assert cli.main(base) == 0
    assert "every spell" in capsys.readouterr().out
    cli.main(args_for(world, "--add", "spells.slots." + SECOND, "spells.slots." + THIRD))
    capsys.readouterr()
    assert cli.main(base) == 0
    out = capsys.readouterr().out
    assert f"{SECOND}, {THIRD} (chosen with --add" in out

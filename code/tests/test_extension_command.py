"""`extension --list` / `innovate-items spells --add ...` / `--secure` through the CLI, and what `run` builds, swaps and says."""
import argparse
import hashlib
import json
from pathlib import Path

import pytest

import eldendisk.__main__ as cli
import eldendisk.commands.run as run_cmd
from eldendisk.extension.innovate_items import bases
from eldendisk.extension.innovate_items.spells import service, spec
from eldendisk.extension.innovate_items.spells.build import Result
from eldendisk.extension.innovate_items.spells.gate import Verdict
from eldendisk.vault import SaveVault

BASE = b"pretend this is the game's regulation.bin" * 50
from tests.z4 import Z4_TEXT, spell_of


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setitem(bases.BASES, bases.CURRENT_BASE, hashlib.sha256(BASE).hexdigest())
    monkeypatch.setattr(service, "prepare", lambda data: "SRC")
    builds, problems = [], []

    def fake(src, spells):
        builds.append(spells[0]["id"] + ":" + str(spells[0]["shop"]["price"]))
        out = b"BUILT" + json.dumps(spells[0], sort_keys=True).encode()
        return Result(out, hashlib.sha256(out).hexdigest(), "d" * 64)

    def verify(data, src, spells):
        return Verdict(list(problems), ["R2-ish note"], {"changed_blocks": 3}, hashlib.sha256(data).hexdigest(), "d" * 64)

    monkeypatch.setattr(service, "make", fake)
    monkeypatch.setattr(service.gate, "verify", verify)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    game = tmp_path / "Game"
    game.mkdir()
    (game / "eldenring.exe").write_bytes(b"EXE")
    (game / "regulation.bin").write_bytes(BASE)
    spec_file = tmp_path / "extension.json"
    spec_file.write_text(Z4_TEXT, encoding="utf-8")
    return argparse.Namespace(ext=tmp_path / "ext", game=game, spec=spec_file, builds=builds, problems=problems)


def args_for(w, *more):
    return ["extension", "innovate-items", "spells", "--extension-dir", str(w.ext), "--spec", str(w.spec), "--game-dir", str(w.game), *more]


def test_add_builds_every_time_and_secures_nothing(world, capsys):
    assert cli.main(args_for(world, "--add", "all")) == 0
    out = capsys.readouterr()
    assert "built, gate passed" in out.err + out.out and "--secure" in out.err + out.out
    assert (world.ext / "innovate-items" / "spells" / "regulation.bin").read_bytes().startswith(b"BUILT")
    assert cli.main(args_for(world, "--add", "all")) == 0
    assert len(world.builds) == 2 and not any(world.ext.rglob("*.tmp"))
    assert sorted(p.name for p in world.ext.rglob("*") if p.is_file()) == ["regulation.bin", "spells.build.json"]
    assert (world.game / "regulation.bin").read_bytes() == BASE                                 # the game's file is only read


def test_a_failed_gate_gives_exit_1_and_writes_nothing(world, capsys):
    world.problems.append("R1: the frame decodes to something else")
    assert cli.main(args_for(world, "--add", "all")) == 1
    out = " ".join("".join(capsys.readouterr()).split())
    assert "GATE FAILED" in out and "R1" in out and "nothing was swapped" in out
    assert not list(world.ext.rglob("regulation*"))


def test_secure_keeps_the_build_and_list_shows_it(world, capsys):
    assert cli.main(args_for(world, "--secure")) == 1                                           # nothing built yet
    assert "build it first" in " ".join("".join(capsys.readouterr()).split())
    cli.main(args_for(world, "--add", "all"))
    capsys.readouterr()
    assert cli.main(args_for(world, "--secure")) == 0
    out = "".join(capsys.readouterr())
    assert "secured" in out and sorted(p.name for p in (world.ext / "innovate-items" / "spells").iterdir()) == \
        ["regulation.bin", "regulation.secured.bin", "spells.build.json", "spells.commit.json"]
    base = ["extension", "--list", "--extension-dir", str(world.ext), "--spec", str(world.spec)]
    assert cli.main(base) == 0
    assert "same: `run` swaps the secured file" in capsys.readouterr().out
    doc = json.loads(Z4_TEXT)
    spell_of(doc)["shop"]["price"] = 40000
    world.spec.write_text(json.dumps(doc), encoding="utf-8")
    assert cli.main(base) == 0
    out = capsys.readouterr().out
    assert "1 change(s): `run` builds" in out and "shop.price  34590 -> 40000" in out


def test_secure_cannot_be_combined_with_add_or_dry_run(world):
    for extra in (["--add", "all"], ["--dry-run"]):
        with pytest.raises(SystemExit) as e:
            cli.main(args_for(world, "--secure", *extra))
        assert e.value.code == 2


def test_source_overrides_the_game_folder(world, tmp_path, capsys):
    other = tmp_path / "orig.bin"
    other.write_bytes(BASE)
    (world.game / "regulation.bin").write_bytes(b"modified")
    assert cli.main(args_for(world, "--add", "all")) == 1
    assert cli.main(args_for(world, "--add", "all", "--source", str(other))) == 0


def test_dry_run_writes_nothing(world, capsys):
    assert cli.main(args_for(world, "--add", "all", "--dry-run")) == 0
    assert not world.ext.exists() and "run again without --dry-run" in "".join(capsys.readouterr())


def test_an_empty_spec_is_not_an_error(world, capsys):
    world.spec.write_text(spec.empty_text(), encoding="utf-8")
    assert cli.main(args_for(world, "--add", "all")) == 0
    assert "nothing to build" in "".join(capsys.readouterr()).replace("\n", " ") and not world.builds


def test_an_invalid_spec_gives_exit_1_and_names_the_field(world, capsys):
    doc = json.loads(Z4_TEXT)
    spell_of(doc)["fp_cost"] = -1
    world.spec.write_text(json.dumps(doc), encoding="utf-8")
    assert cli.main(args_for(world, "--add", "all")) == 1
    assert "fp_cost" in "".join(capsys.readouterr())


def test_a_modified_game_file_gives_exit_1_with_the_restore_hint(world, capsys):
    (world.game / "regulation.bin").write_bytes(BASE + b"x")
    assert cli.main(args_for(world, "--add", "all")) == 1
    out = " ".join("".join(capsys.readouterr()).split())
    assert "not a regulation.bin this version knows" in out and "vault restore" in out


def test_without_a_spec_file_the_shipped_one_is_used(world, tmp_path, monkeypatch):
    import eldendisk.commands.extension as ec
    assert ec.spec_file(argparse.Namespace(spec=None)) == service.CODE_DIR / "extension.json"
    assert ec.spec_file(argparse.Namespace(spec=str(world.spec))) == world.spec


def test_list_shows_the_spec_and_whether_anything_was_built(world, capsys):
    base = ["extension", "--list", "--extension-dir", str(world.ext), "--spec", str(world.spec)]
    assert cli.main(base) == 0
    out = capsys.readouterr().out
    assert "1 spell in the design" in out and "none yet" in out and not world.ext.exists()
    cli.main(args_for(world, "--add", "all"))
    capsys.readouterr()
    assert cli.main(base) == 0
    assert "regulation.bin" in capsys.readouterr().out


def test_extension_without_anything_to_do_is_a_usage_error():
    with pytest.raises(SystemExit) as e:
        cli.main(["extension"])
    assert e.value.code == 2
    with pytest.raises(SystemExit):
        cli.main(["extension", "innovate-items", "spells", "--list"])
    with pytest.raises(SystemExit):
        cli.main(["extension", "innovate-items", "spells", "--force"])        # gone: it builds every time


def test_innovate_items_spells_without_add_shows_where_things_are(world, capsys):
    assert cli.main(["extension", "innovate-items", "spells", "--extension-dir", str(world.ext), "--spec", str(world.spec)]) == 0
    assert "extension.json" in "".join(capsys.readouterr())


# ---- what `run` builds, swaps and says ----
def run_args(w, **kw):
    return argparse.Namespace(regulation=kw.get("regulation"), extension_dir=str(w.ext), spec=str(w.spec))


def secure(w):
    assert cli.main(args_for(w, "--add", "all")) == 0
    assert cli.main(args_for(w, "--secure")) == 0
    w.builds.clear()


def test_run_builds_the_first_time_and_says_why(world, tmp_path, capsys):
    vault = SaveVault(tmp_path / "vault")
    out, mode = run_cmd._regulation(run_args(world), vault, world.game, True)
    assert mode == "built" and out == world.ext / "innovate-items" / "spells" / "regulation.bin" and out.read_bytes().startswith(b"BUILT")
    assert "building because no secured build yet" in " ".join("".join(capsys.readouterr()).split())
    run_cmd._regulation(run_args(world), vault, world.game, True)
    assert len(world.builds) == 1                                                  # nothing secured, but the build is unchanged: reused


def test_run_swaps_the_secured_file_without_building(world, tmp_path, capsys):
    secure(world)
    capsys.readouterr()
    out, mode = run_cmd._regulation(run_args(world), SaveVault(tmp_path / "vault"), world.game, True)
    assert mode == "secured" and out == world.ext / "innovate-items" / "spells" / "regulation.secured.bin" and world.builds == []
    assert "no build" in "".join(capsys.readouterr())


def test_run_builds_again_when_the_draft_changed_and_prints_the_diff(world, tmp_path, capsys):
    secure(world)
    capsys.readouterr()
    doc = json.loads(Z4_TEXT)
    spell_of(doc)["shop"]["price"] = 40000
    world.spec.write_text(json.dumps(doc), encoding="utf-8")
    out, mode = run_cmd._regulation(run_args(world), SaveVault(tmp_path / "vault"), world.game, True)
    text = " ".join("".join(capsys.readouterr()).split())
    assert mode == "built" and out.name == "regulation.bin" and len(world.builds) == 1
    assert "the design changed since it was secured (1 field)" in text and "shop.price 34590 -> 40000" in text


def test_the_game_file_is_checked_even_when_the_secured_file_would_be_used(world, tmp_path):
    secure(world)
    (world.game / "regulation.bin").write_bytes(BASE + b"x")
    with pytest.raises(service.ExtensionError):
        run_cmd._regulation(run_args(world), SaveVault(tmp_path / "vault"), world.game, True)


def test_a_failed_gate_stops_run_and_says_nothing_was_swapped(world, tmp_path, monkeypatch, capsys):
    world.problems.append("G13: the heal has the wrong sign")
    monkeypatch.setattr(run_cmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(run_cmd.launcher, "find_game_dir", lambda d: world.game)
    monkeypatch.setattr(run_cmd, "sha256_file", lambda p: "ab" * 32)
    monkeypatch.setattr(run_cmd, "live_dir", lambda d: tmp_path / "live")
    started = []
    monkeypatch.setattr(run_cmd, "Session", lambda *a, **k: started.append(1))
    args = argparse.Namespace(vault=str(tmp_path / "vault"), save_dir=None, game_dir=None, offsets="x", no_archive_contaminated=False,
                              keep=0, launch_timeout=1.0, verbose=False, protect=True, regulation=None,
                              extension_dir=str(world.ext), spec=str(world.spec))
    assert run_cmd.cmd_run(args) == 1 and not started
    text = " ".join("".join(capsys.readouterr()).split())
    assert "GATE FAILED" in text and "G13" in text and "the game was not started" in text


def test_run_with_an_empty_spec_swaps_nothing(world, tmp_path):
    world.spec.write_text(spec.empty_text(), encoding="utf-8")
    assert run_cmd._regulation(run_args(world), SaveVault(tmp_path / "vault"), world.game, True) == (None, "none")


def test_run_with_the_vault_off_does_not_build(world, tmp_path, capsys):
    assert run_cmd._regulation(run_args(world), SaveVault(tmp_path / "vault"), world.game, False) == (None, "none")
    assert not world.builds and "vault OFF: the extension is not run" in "".join(capsys.readouterr())


def test_run_does_not_build_while_the_vault_owes_a_restore(world, tmp_path):
    live = tmp_path / "live" / "1"
    live.mkdir(parents=True)
    (live / "ER0000.sl2").write_bytes(b"save")
    v = SaveVault(tmp_path / "vault", sleep=lambda s: None)
    v.write_session(v.new_record(v.snapshot(live), live, exe_sha256=None))
    assert run_cmd._regulation(run_args(world), v, world.game, True) == (None, "none") and not world.builds


def test_a_build_error_stops_run_before_anything_starts(world, tmp_path, monkeypatch, capsys):
    (world.game / "regulation.bin").write_bytes(b"modified")
    monkeypatch.setattr(run_cmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(run_cmd.launcher, "find_game_dir", lambda d: world.game)
    monkeypatch.setattr(run_cmd, "sha256_file", lambda p: "ab" * 32)
    monkeypatch.setattr(run_cmd, "live_dir", lambda d: tmp_path / "live")
    started = []
    monkeypatch.setattr(run_cmd, "Session", lambda *a, **k: started.append(1))
    args = argparse.Namespace(vault=str(tmp_path / "vault"), save_dir=None, game_dir=None, offsets="x", no_archive_contaminated=False,
                              keep=0, launch_timeout=1.0, verbose=False, protect=True, regulation=None,
                              extension_dir=str(world.ext), spec=str(world.spec))
    assert run_cmd.cmd_run(args) == 1 and not started
    assert "vault restore" in " ".join("".join(capsys.readouterr()).split())


def test_regulation_flag_overrides_the_build(world, tmp_path):
    mine = tmp_path / "x.bin"
    mine.write_bytes(b"x")
    v = SaveVault(tmp_path / "vault")
    assert run_cmd._regulation(run_args(world, regulation=str(mine)), v, world.game, True) == (mine, "file") and not world.builds
    assert run_cmd._regulation(run_args(world, regulation=str(mine)), v, world.game, False) == (None, "none")
    with pytest.raises(FileNotFoundError):
        run_cmd._regulation(run_args(world, regulation=str(tmp_path / "missing.bin")), v, world.game, True)


# ---- the files live in the vault (1.7.0): <vault>\extension\innovate-items\spells ----
def vault_args(w, vault, *more):
    return ["extension", "innovate-items", "spells", "--vault", str(vault), "--spec", str(w.spec), "--game-dir", str(w.game), *more]


def test_without_extension_dir_the_files_go_under_the_vault(world, tmp_path):
    vault = tmp_path / "myvault"
    assert cli.main(vault_args(world, vault, "--add", "all")) == 0
    built = vault / "extension" / "innovate-items" / "spells" / "regulation.bin"
    assert built.read_bytes().startswith(b"BUILT")
    assert not (tmp_path / "local" / "EldenDisk" / "extension").exists()          # the old place is not used any more


def test_extension_dir_still_replaces_the_vault_place(world, tmp_path):
    vault = tmp_path / "myvault"
    assert cli.main(vault_args(world, vault, "--extension-dir", str(world.ext), "--add", "all")) == 0
    assert (world.ext / "innovate-items" / "spells" / "regulation.bin").is_file() and not (vault / "extension").exists()


def test_run_puts_the_files_in_the_vault_it_resolved(world, tmp_path):
    vault = SaveVault(tmp_path / "vault")
    args = argparse.Namespace(regulation=None, spec=str(world.spec), extension_dir=None)
    out, mode = run_cmd._regulation(args, vault, world.game, True)
    assert mode == "built" and out == tmp_path / "vault" / "extension" / "innovate-items" / "spells" / "regulation.bin"


def test_the_vault_does_not_take_the_extension_folder_for_a_snapshot(world, tmp_path):
    vault = tmp_path / "vault"
    assert cli.main(vault_args(world, vault, "--add", "all")) == 0
    sv = SaveVault(vault)
    assert sv.list_snapshots(verify=False) == [] and sv.prune(1) == [] and (vault / "extension").is_dir()

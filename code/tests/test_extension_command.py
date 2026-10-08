"""`extension --list` / `customize-items --add ...` / `--secure` through the CLI, and what `run` builds, swaps and says."""
import argparse
import hashlib
import json
from pathlib import Path

import pytest

import eldendisk.__main__ as cli
import eldendisk.commands.run as run_cmd
from eldendisk.extension.customize_items import bases, service, spec
from eldendisk.extension.customize_items.build import Result
from eldendisk.extension.customize_items.gate import Verdict
from eldendisk.vault import SaveVault

BASE = b"pretend this is the game's regulation.bin" * 50
Z4_TEXT = (Path(spec.__file__).parent / "items.draft.json").read_text(encoding="utf-8")


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setitem(bases.BASES, bases.CURRENT_BASE, hashlib.sha256(BASE).hexdigest())
    monkeypatch.setattr(service, "prepare", lambda data: "SRC")
    builds, problems = [], []

    def fake(src, items):
        builds.append(items[0]["id"] + ":" + str(items[0]["shop"]["price"]))
        out = b"BUILT" + json.dumps(items[0], sort_keys=True).encode()
        return Result(out, hashlib.sha256(out).hexdigest(), "d" * 64)

    def verify(data, src, items):
        return Verdict(list(problems), ["R2-ish note"], {"changed_blocks": 3}, hashlib.sha256(data).hexdigest(), "d" * 64)

    monkeypatch.setattr(service, "make", fake)
    monkeypatch.setattr(service.gate, "verify", verify)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    game = tmp_path / "Game"
    game.mkdir()
    (game / "eldenring.exe").write_bytes(b"EXE")
    (game / "regulation.bin").write_bytes(BASE)
    spec_file = tmp_path / "items.draft.json"
    spec_file.write_text(Z4_TEXT, encoding="utf-8")
    return argparse.Namespace(ext=tmp_path / "ext", game=game, spec=spec_file, builds=builds, problems=problems)


def args_for(w, *more):
    return ["extension", "customize-items", "--extension-dir", str(w.ext), "--spec", str(w.spec), "--game-dir", str(w.game), *more]


def test_add_builds_every_time_and_secures_nothing(world, capsys):
    assert cli.main(args_for(world, "--add", "all")) == 0
    out = capsys.readouterr()
    assert "built, gate passed" in out.err + out.out and "--secure" in out.err + out.out
    assert (world.ext / "customize-items" / "regulation.bin").read_bytes().startswith(b"BUILT")
    assert cli.main(args_for(world, "--add", "all")) == 0
    assert len(world.builds) == 2 and not any(world.ext.rglob("*.tmp"))
    assert sorted(p.name for p in world.ext.rglob("*") if p.is_file()) == ["regulation.bin"]
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
    assert "secured" in out and sorted(p.name for p in (world.ext / "customize-items").iterdir()) == \
        ["items.secured.json", "regulation.bin", "regulation.secured.bin"]
    base = ["extension", "--list", "--extension-dir", str(world.ext), "--spec", str(world.spec)]
    assert cli.main(base) == 0
    assert "same: `run` swaps the secured file" in capsys.readouterr().out
    doc = json.loads(Z4_TEXT)
    doc["items"][0]["shop"]["price"] = 40000
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
    world.spec.write_text('{"format": 1, "items": []}', encoding="utf-8")
    assert cli.main(args_for(world, "--add", "all")) == 0
    assert "nothing to build" in "".join(capsys.readouterr()).replace("\n", " ") and not world.builds


def test_an_invalid_spec_gives_exit_1_and_names_the_field(world, capsys):
    doc = json.loads(Z4_TEXT)
    doc["items"][0]["fp_cost"] = -1
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
    assert ec.spec_file(argparse.Namespace(spec=None)) == service.PKG_DIR / "items.draft.json"
    assert ec.spec_file(argparse.Namespace(spec=str(world.spec))) == world.spec


def test_list_shows_the_spec_and_whether_anything_was_built(world, capsys):
    base = ["extension", "--list", "--extension-dir", str(world.ext), "--spec", str(world.spec)]
    assert cli.main(base) == 0
    out = capsys.readouterr().out
    assert "1 item in the draft" in out and "none yet" in out and not world.ext.exists()
    cli.main(args_for(world, "--add", "all"))
    capsys.readouterr()
    assert cli.main(base) == 0
    assert "regulation.bin" in capsys.readouterr().out


def test_extension_without_anything_to_do_is_a_usage_error():
    with pytest.raises(SystemExit) as e:
        cli.main(["extension"])
    assert e.value.code == 2
    with pytest.raises(SystemExit):
        cli.main(["extension", "customize-items", "--list"])
    with pytest.raises(SystemExit):
        cli.main(["extension", "customize-items", "--force"])        # gone: it builds every time


def test_customize_items_without_add_shows_where_things_are(world, capsys):
    assert cli.main(["extension", "customize-items", "--extension-dir", str(world.ext), "--spec", str(world.spec)]) == 0
    assert "items.draft.json" in "".join(capsys.readouterr())


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
    assert mode == "built" and out == world.ext / "customize-items" / "regulation.bin" and out.read_bytes().startswith(b"BUILT")
    assert "building because no secured build yet" in " ".join("".join(capsys.readouterr()).split())
    run_cmd._regulation(run_args(world), vault, world.game, True)
    assert len(world.builds) == 2                                                  # nothing secured: every run builds


def test_run_swaps_the_secured_file_without_building(world, tmp_path, capsys):
    secure(world)
    capsys.readouterr()
    out, mode = run_cmd._regulation(run_args(world), SaveVault(tmp_path / "vault"), world.game, True)
    assert mode == "secured" and out == world.ext / "customize-items" / "regulation.secured.bin" and world.builds == []
    assert "no build" in "".join(capsys.readouterr())


def test_run_builds_again_when_the_draft_changed_and_prints_the_diff(world, tmp_path, capsys):
    secure(world)
    capsys.readouterr()
    doc = json.loads(Z4_TEXT)
    doc["items"][0]["shop"]["price"] = 40000
    world.spec.write_text(json.dumps(doc), encoding="utf-8")
    out, mode = run_cmd._regulation(run_args(world), SaveVault(tmp_path / "vault"), world.game, True)
    text = " ".join("".join(capsys.readouterr()).split())
    assert mode == "built" and out.name == "regulation.bin" and len(world.builds) == 1
    assert "the draft changed since it was secured (1 field)" in text and "shop.price 34590 -> 40000" in text


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
    world.spec.write_text('{"format": 1, "items": []}', encoding="utf-8")
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

"""`extension --list` / `extension customize-items --add ...` through the CLI, and what `run` builds and takes."""
import argparse
import hashlib
import json
from pathlib import Path

import pytest

import eldendisk.__main__ as cli
import eldendisk.commands.run as run_cmd
from eldendisk.extension.customize_items import bases, service, spec
from eldendisk.extension.customize_items.build import Result
from eldendisk.vault import SaveVault

BASE = b"pretend this is the game's regulation.bin" * 50
Z4_TEXT = (Path(spec.__file__).parent / "sources" / "items.json").read_text(encoding="utf-8")


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setitem(bases.BASES, bases.CURRENT_BASE, hashlib.sha256(BASE).hexdigest())
    monkeypatch.setattr(service, "prepare", lambda data: None)
    builds = []

    def fake(data, items, src=None):
        builds.append(items[0]["id"])
        out = b"BUILT" + items[0]["id"].encode()
        return Result(out, hashlib.sha256(out).hexdigest(), "d" * 64, 3, ["R2: a warning"])

    monkeypatch.setattr(service, "run_build", fake)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    game = tmp_path / "Game"
    game.mkdir()
    (game / "eldenring.exe").write_bytes(b"EXE")
    (game / "regulation.bin").write_bytes(BASE)
    spec_file = tmp_path / "items.json"
    spec_file.write_text(Z4_TEXT, encoding="utf-8")
    w = argparse.Namespace(ext=tmp_path / "ext", game=game, spec=spec_file, builds=builds)
    return w


def args_for(w, *more):
    return ["extension", "customize-items", "--extension-dir", str(w.ext), "--spec", str(w.spec), "--game-dir", str(w.game), *more]


def test_add_builds_every_time(world, capsys):
    assert cli.main(args_for(world, "--add", "all")) == 0
    out = capsys.readouterr()
    assert "built and checked" in out.err + out.out and "a warning" in out.err + out.out
    assert (world.ext / "customize-items" / "regulation.bin").read_bytes() == b"BUILTreverse-curse-technique"
    assert cli.main(args_for(world, "--add", "all")) == 0
    assert len(world.builds) == 2 and not any(world.ext.rglob("*.tmp"))
    assert sorted(p.name for p in world.ext.rglob("*") if p.is_file()) == ["regulation.bin"]     # no manifest, no base copy
    assert (world.game / "regulation.bin").read_bytes() == BASE                                 # the game's file is only read


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
    assert ec.spec_file(argparse.Namespace(spec=None)) == service.SOURCES_DIR / "items.json"
    assert ec.spec_file(argparse.Namespace(spec=str(world.spec))) == world.spec


def test_list_shows_the_spec_and_whether_anything_was_built(world, capsys):
    base = ["extension", "--list", "--extension-dir", str(world.ext), "--spec", str(world.spec)]
    assert cli.main(base) == 0
    out = capsys.readouterr().out
    assert "1 item in the spec" in out and "none yet" in out and not world.ext.exists()
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
    assert "items.json" in "".join(capsys.readouterr())


# ---- what `run` builds and takes ----
def run_args(w, **kw):
    return argparse.Namespace(regulation=kw.get("regulation"), extension_dir=str(w.ext), spec=str(w.spec))


def test_run_builds_on_the_games_file_and_hands_over_the_output(world, tmp_path):
    vault = SaveVault(tmp_path / "vault")
    out = run_cmd._regulation(run_args(world), vault, world.game, True)
    assert out == world.ext / "customize-items" / "regulation.bin" and out.read_bytes().startswith(b"BUILT")
    run_cmd._regulation(run_args(world), vault, world.game, True)
    assert len(world.builds) == 2                                                  # every run builds


def test_run_with_an_empty_spec_swaps_nothing(world, tmp_path):
    world.spec.write_text('{"format": 1, "items": []}', encoding="utf-8")
    assert run_cmd._regulation(run_args(world), SaveVault(tmp_path / "vault"), world.game, True) is None


def test_run_with_the_vault_off_does_not_build(world, tmp_path, capsys):
    assert run_cmd._regulation(run_args(world), SaveVault(tmp_path / "vault"), world.game, False) is None
    assert not world.builds and "vault OFF: the extension is not run" in "".join(capsys.readouterr())


def test_run_does_not_build_while_the_vault_owes_a_restore(world, tmp_path):
    live = tmp_path / "live" / "1"
    live.mkdir(parents=True)
    (live / "ER0000.sl2").write_bytes(b"save")
    v = SaveVault(tmp_path / "vault", sleep=lambda s: None)
    v.write_session(v.new_record(v.snapshot(live), live, exe_sha256=None))
    assert run_cmd._regulation(run_args(world), v, world.game, True) is None and not world.builds


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
    assert run_cmd._regulation(run_args(world, regulation=str(mine)), v, world.game, True) == mine and not world.builds
    assert run_cmd._regulation(run_args(world, regulation=str(mine)), v, world.game, False) is None
    with pytest.raises(FileNotFoundError):
        run_cmd._regulation(run_args(world, regulation=str(tmp_path / "missing.bin")), v, world.game, True)

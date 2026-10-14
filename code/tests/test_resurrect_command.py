"""1.8.0: `resurrect NAME | ID | PATH ... | all` through the CLI (--dry-run, --when-loaded), the step `run` starts, and the block of
read / write / the scripts (creative/scripts/backend.py), on a fake game whose event flags are built like the game's."""
import json
from types import SimpleNamespace

import pytest

import eldendisk.__main__ as cli
import eldendisk.commands.write as wcmd
from eldendisk.commands import resurrect as rcmd
from eldendisk.commands import run as run_cmd
from eldendisk.game.attach import AttachError
from tests.eventflag_fakes import BASE, LAYOUT, FlagMemory, OpenGate

MARGIT = (10000850, 10000851, 9100, 60510)
MOHG = (12050800, 12050801, 12050802, 9112, 510120)


def game(*on):
    m = FlagMemory([9, 60, 510, 10000, 12050, 30000])
    for f in on:
        m.set(f)
    m.close = lambda: None
    return m


@pytest.fixture
def rig(monkeypatch):
    """`resurrect` attached to a fake game in an authorised session with a character in the world."""
    box = SimpleNamespace(mem=game(*MARGIT, *MOHG), authorised=True, world=True)
    target = SimpleNamespace(pid=1, base=BASE, profile=SimpleNamespace(event_flags=LAYOUT))
    monkeypatch.setattr(rcmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(wcmd, "_attach", lambda args, wait: (target, None, object()))
    monkeypatch.setattr(wcmd, "_authorised", lambda t, r: box.authorised)
    monkeypatch.setattr(wcmd, "world_loaded", lambda mem, t: (box.world, "" if box.world else "title screen"))
    monkeypatch.setattr(rcmd, "WritableProcessMemory", lambda pid: box.mem)
    monkeypatch.setattr(rcmd, "locate", lambda offsets: target)
    monkeypatch.setattr(rcmd, "open_read", lambda t: box.mem)
    return box


def run(*argv):
    return cli.main(["resurrect", *argv])


def test_activate_turns_the_bosses_flags_off_and_says_where_they_are(rig, capsys):
    assert run("mohg lord", "fell omen") == 0
    assert not any(rig.mem.get(f) for f in (*MARGIT, *MOHG))
    out = "".join(capsys.readouterr())
    assert "Mohg, Lord of Blood alive again: Mohgwyn Palace" in out and "Dynasty Mausoleum Midpoint" in out and "420,000 runes" in out
    assert "2 great enemies alive again" in out and "warp to a grace in another region" in out
    assert "story bosses" in out                                                     # Mohg and Margit are story bosses


def test_a_boss_alive_already_is_said_and_nothing_is_written(rig, capsys):
    rig.mem.set(10000850, False)
    assert run("10000850") == 0
    assert "already alive" in "".join(capsys.readouterr()) and rig.mem.writes == []


def test_a_wrong_name_writes_nothing(rig, capsys):
    assert run("margit", "godrik") == 1
    out = "".join(capsys.readouterr())
    assert "closest: Godrick" in out and "nothing was written" in out and rig.mem.writes == []


def test_no_session_or_no_world_writes_nothing(rig, capsys):
    rig.authorised = False
    assert run("margit") == 5 and rig.mem.writes == []
    rig.authorised, rig.world = True, False
    assert run("margit") == 1 and rig.mem.writes == []
    assert "no character in the world" in "".join(capsys.readouterr())


def test_a_flag_that_does_not_stick_is_an_error(rig, capsys):
    rig.mem.fail_writes = True
    assert run("margit") == 1
    assert "not resurrected" in "".join(capsys.readouterr())


def test_all_brings_back_every_defeated_one(rig, capsys):
    assert run("all") == 0
    assert not rig.mem.get(10000850) and not rig.mem.get(12050800)
    assert "2 great enemies alive again" in "".join(capsys.readouterr())         # the others were alive (or not held) already


def test_a_boss_is_named_by_its_path_in_the_document_too(rig):
    assert run("creative.resurrect.great_enemies.10000850", "creative.resurrect.great_enemies.12050800.defeated") == 0
    assert not rig.mem.get(10000850) and not rig.mem.get(12050800)


def test_dry_run_says_what_would_come_back_and_writes_nothing(rig, capsys):
    assert run("margit", "mohg lord", "--dry-run") == 0
    out = capsys.readouterr().out
    assert "Margit, the Fell Omen" in out and "would come back" in out and "dry run: nothing was written" in out
    assert rig.mem.get(10000850) and rig.mem.get(12050800)


def test_dry_run_without_the_game_still_resolves_the_names(rig, monkeypatch, capsys):
    monkeypatch.setattr(rcmd, "locate", lambda o: (_ for _ in ()).throw(AttachError("eldenring.exe is not running")))
    assert run("margit", "--dry-run") == 0
    assert "the game was not read" in capsys.readouterr().out
    assert run("godrik", "--dry-run") == 1


def test_names_that_do_not_go_together_write_nothing(rig):
    assert run("all", "margit") == 1 and rig.mem.writes == []
    assert run("--when-loaded", "margit") == 1 and rig.mem.writes == []


@pytest.mark.parametrize("argv", [["--dry-run", "--when-loaded"], ["great-enemies", "--list"], ["--activate", "margit"]])
def test_options_that_do_not_go_together_or_are_gone(argv, rig):
    if argv[0] == "great-enemies":                        # `great-enemies` is no name of a boss now: nothing is written
        assert run(*argv[:1]) == 1 and rig.mem.writes == []
        with pytest.raises(SystemExit):
            run(*argv)
        return
    with pytest.raises(SystemExit):
        run(*argv)


def test_resurrect_alone_says_how_and_writes_nothing(rig, capsys):
    assert run() == 0 and rig.mem.writes == []
    assert "read creative.resurrect.great_enemies" in "".join(capsys.readouterr())


def test_when_loaded_activates_the_designs_list(rig, tmp_path, monkeypatch, capsys):
    spec = tmp_path / "creative.json"
    spec.write_text(json.dumps({"resurrect": {"great_enemies": {"activate": ["margit"]}}}), encoding="utf-8")
    monkeypatch.setattr(wcmd, "_wait_world", lambda *a, **k: True)
    assert run("--when-loaded", "--spec", str(spec)) == 0
    assert not rig.mem.get(10000850) and rig.mem.get(12050800)
    spec.write_text(json.dumps({"innovate_spells": {}}), encoding="utf-8")
    assert run("--when-loaded", "--spec", str(spec)) == 0 and "names none" in "".join(capsys.readouterr())


def test_run_starts_the_step_only_when_the_design_names_great_enemies(tmp_path):
    import argparse
    spec = tmp_path / "creative.json"
    args = argparse.Namespace(spec=str(spec), vault=None, offsets="x", creative_dir=None, verbose=False)
    spec.write_text(json.dumps({"resurrect": {"great_enemies": {"activate": "all"}}}), encoding="utf-8")
    assert run_cmd.creative_has_enemies(args, tmp_path)
    spec.write_text(json.dumps({"innovate_spells": {}}), encoding="utf-8")
    assert not run_cmd.creative_has_enemies(args, tmp_path)
    seen = []
    run_cmd.start_enemies(args, tmp_path / "vault", spawn=lambda c, **kw: seen.append(c))
    i = seen[0].index("resurrect")
    assert seen[0][i:i + 2] == ["resurrect", "--when-loaded"]


# ---- the block of read / write / the scripts
def live(mem, gate=OpenGate()):
    from eldendisk.creative.scripts.backend import CreativeLive
    target = SimpleNamespace(pid=1, started=1, base=BASE, profile=SimpleNamespace(event_flags=LAYOUT))
    return CreativeLive(mem, target, None, None, gate=gate)


def test_the_block_holds_the_defeated_great_enemies_only():
    block = live(game(10000850)).block()
    enemies = block["resurrect"]["great_enemies"]
    assert list(enemies) == ["10000850"] and "innovate_spells" not in block       # no build: only the great enemies
    assert enemies["10000850"]["defeated"] is True and enemies["10000850"]["grace"] == "Castleward Tunnel"
    assert "10000800" not in enemies and "1052380800" not in enemies               # alive, and a group the game does not hold


def test_a_boss_brought_back_leaves_the_block():
    m = game(*MARGIT, *MOHG)
    d = live(m)
    assert set(d.block()["resurrect"]["great_enemies"]) == {"10000850", "12050800"}
    d.apply_enemy("margit", ["defeated"], False)
    assert set(d.block()["resurrect"]["great_enemies"]) == {"12050800"}


def test_defeated_false_brings_one_back_and_true_or_another_field_is_refused():
    from eldendisk.creative.scripts.backend import Refused
    m = game(*MARGIT)
    d = live(m)
    assert d.apply_enemy("margit", ["defeated"], "false") == {"creative.resurrect.great_enemies.10000850.defeated": False}
    assert not any(m.get(f) for f in MARGIT)
    with pytest.raises(Refused, match="only the game marks"):
        d.apply_enemy("margit", ["defeated"], True)
    with pytest.raises(Refused, match="only `defeated`"):
        d.apply_enemy("margit", ["runes"], 1)


def test_plain_read_shows_the_defeated_ones_and_a_query_by_name_finds_one():
    from eldendisk.reader.view import select
    doc = {"creative": live(game(10000850, 12050800)).block()}
    whole = select(doc, None)[0][1]
    assert set(whole["creative"]["resurrect"]["great_enemies"]) == {"10000850", "12050800"}
    got = select(doc, "creative.resurrect.great_enemies.margit.defeated")
    assert got == [("creative.resurrect.great_enemies.10000850.defeated", True)]
    assert select(doc, "creative.resurrect.great_enemies.godrick") == []          # alive: not in the set now, not a wrong name


@pytest.mark.parametrize("argv", [["scripts"], ["scripts", "status"], ["innovate-spells"], ["innovate-spells", "build", "all"],
                                  ["resurrect", "margit"], ["read"], ["write"], ["export"], ["reset"], ["check"], ["probe"]])
def test_every_command_has_its_vault_and_verbose_defaults(argv):
    """Seen in the exe: `resurrect great-enemies --activate` without --vault stopped on `args.vault` (the top-level commands of 1.8.0
    had only the subcommands' SUPPRESS copies)."""
    args = cli.build_parser().parse_args(argv)
    assert args.vault is None and args.verbose is False
    args = cli.build_parser().parse_args([*argv, "--vault", "V", "-v"])
    assert args.vault == "V" and args.verbose is True


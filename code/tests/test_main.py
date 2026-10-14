"""CLI-level tests: config resolution, throttled writes, flags, logger and launcher helpers."""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import eldendisk.__main__ as cli
from eldendisk import paths
from eldendisk.game import attach, memory as memory_reader, processes
from eldendisk.host import launcher
from eldendisk.reader.export import JsonLogger, doc_signature
from eldendisk.reader.sampler import Sampler, WORLD_LOST_RESET_S, iso
from tests.test_disk import BASE, FakeMem, GD, NOW, state_ids, full_world, make_profile


# ---------- iso / doc_signature ----------
def test_iso_always_carries_utc_offset():
    assert iso(datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)) == "2026-09-30 12:00:00.000000+00:00"
    assert iso(datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone(timedelta(hours=7)))).endswith("+07:00")
    naive = iso(datetime(2026, 9, 30, 12, 0, 0))  # naive = local time, still labelled
    assert naive[-6] in "+-" and naive[-3] == ":"


def _doc(level=1, remaining=50.0):
    return {"system_status": {"state": "CONNECTED"},
            "character": {"level": level, "buffs": {
                "1": {"name": "a", "times": {"buff_duration": remaining, "max_duration": 60.0, "last_activated_at": "t"}},
                "2": {"name": "perm"}}}}


def test_doc_signature_ignores_only_the_countdown():
    assert doc_signature(_doc(remaining=50.0)) == doc_signature(_doc(remaining=49.0))
    assert doc_signature(_doc(level=1)) != doc_signature(_doc(level=2))
    assert doc_signature({"character": None}) == {"character": None}
    assert _doc(remaining=50.0)["character"]["buffs"]["1"]["times"]["buff_duration"] == 50.0  # input not mutated


# ---------- get_resource_path / describe_resource ----------
@pytest.fixture
def frozen(tmp_path, monkeypatch):
    ext, emb = tmp_path / "dist", tmp_path / "meipass"
    ext.mkdir(); emb.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(emb), raising=False)
    monkeypatch.setattr(sys, "executable", str(ext / "eldendisk.exe"))
    return ext, emb


def test_external_file_beats_embedded(frozen):
    ext, emb = frozen
    (ext / "offsets.json").write_text("{}"); (emb / "offsets.json").write_text("{}")
    assert paths.get_resource_path("offsets.json") == ext.resolve() / "offsets.json"
    assert paths.describe_resource(ext / "offsets.json") == "external"


def test_embedded_used_when_nothing_external(frozen):
    _ext, emb = frozen
    (emb / "offsets.json").write_text("{}")
    got = paths.get_resource_path("offsets.json")
    assert got == emb / "offsets.json" and paths.describe_resource(got) == "embedded"


def test_frozen_does_not_walk_ancestors(frozen):
    ext, _emb = frozen
    (ext.parent / "only-in-parent.json").write_text("{}")
    assert paths.get_resource_path("only-in-parent.json") == Path("only-in-parent.json")
    assert paths.describe_resource("nope.json") == "missing"


def test_source_run_resolves_project_files():
    assert paths.runtime_dirs() == (None, None)
    assert paths.get_resource_path("offsets.json").name == "offsets.json"
    assert paths.describe_resource(paths.get_resource_path("offsets.json")) == "source"


# ---------- argparse surface ----------
def test_run_flags_parse(monkeypatch):
    seen = {}
    monkeypatch.setattr(cli, "cmd_run", lambda a: seen.update(vars(a)) or 0)
    assert cli.main(["run", "--launch-timeout", "30", "--no-archive-contaminated", "-v"]) == 0
    assert seen["launch_timeout"] == 30.0 and seen["no_archive_contaminated"] is True and seen["verbose"] is True
    seen.clear()
    cli.main(["run"])
    assert seen["launch_timeout"] == 120.0 and seen["no_archive_contaminated"] is False and seen["vault"] is None
    assert seen["keep"] == 5 and seen["protect"] is True        # the vault is ON unless told otherwise
    with pytest.raises(SystemExit):
        cli.main(["run", "--launch-timeout", "0"])
    with pytest.raises(SystemExit):
        cli.main(["run", "--keep", "-1"])


def test_read_words_parse_into_what_read_does(monkeypatch):
    """1.8.0 part 2: `read [NAME ...]`, `read monitor...`, `export`, `check`, `probe` (no --query / --export / --live-buffs ...)."""
    import eldendisk.commands.read as rcmd
    seen = {}
    monkeypatch.setattr(rcmd, "cmd_read", lambda a: seen.update(vars(a)) or 0)
    assert cli.main(["read", "monitor", "-q", "--hz", "30"]) == 0
    assert seen["live_buffs"] and seen["live_animations"] and seen["quiet"] and not seen["live"] and not seen["export"]
    assert seen["hz"] == 30.0 and seen["unmapped"] and not seen["mapped"]          # --unmapped is the default of a monitor
    seen.clear()
    assert cli.main(["read", "monitor-animations"]) == 0
    assert seen["live_animations"] and not seen["live_buffs"] and seen["unmapped"]
    seen.clear()
    assert cli.main(["read", "monitor-buffs", "--mapped"]) == 0 and seen["mapped"] and not seen["unmapped"] and seen["live_buffs"]
    seen.clear()
    assert cli.main(["export", "--live", "--no-idle", "--export-interval", "1", "--timer-interval", "0"]) == 0
    assert seen["export"] and seen["live"] and seen["no_idle"] and seen["query"] is None
    assert (seen["export_interval"], seen["timer_interval"]) == (1.0, 0.0) and seen["out"].endswith("output")
    seen.clear()
    assert cli.main(["read", "runes", "--json"]) == 0
    assert seen["query"] == ["runes"] and seen["json"] and not seen["live"] and not seen["export"]
    seen.clear()
    assert cli.main(["read", "attrs.*", "--flat", "--live"]) == 0 and seen["flat"] and seen["live"]
    seen.clear()
    assert cli.main(["read", "character.runes.*", "character.buffs.*", "--live"]) == 0 and not seen["flat"]
    assert seen["query"] == ["character.runes.*", "character.buffs.*"] and seen["live"]
    seen.clear()
    assert cli.main(["read", "params.Magic.6230", "params.SpEffect.1621000.effectEndurance"]) == 0
    assert seen["param"] == ["params.Magic.6230", "params.SpEffect.1621000.effectEndurance"] and seen["query"] is None
    seen.clear()
    assert cli.main(["read", "params.effects.1621000"]) == 0 and seen["query"] == ["params.effects.1621000"] and not seen["param"]
    seen.clear()
    for whole in (["read"], ["read", "*"], ["read", "all"], ["read", "--tree"]):
        cli.main(whole)
        assert (seen["query"], seen["export"], seen["live"], seen["hz"], seen["timeout"]) == (None, False, False, 60.0, 15.0)
        seen.clear()
    assert cli.main(["check"]) == 0 and seen["param_check"] == ""
    seen.clear()
    assert cli.main(["check", "my.bin", "--json"]) == 0 and seen["param_check"] == "my.bin" and seen["json"]
    seen.clear()
    assert cli.main(["probe", "--json"]) == 0 and seen["probe_params"] and seen["json"]


@pytest.mark.parametrize("argv", [
    ["read", "--hz", "500"], ["read", "--hz", "0"], ["export", "--export-interval", "-1"], ["export", "--hz", "0"],
    ["read", "--timeout", "0"], ["read", "--json", "--live"], ["read", "--once"], ["read", "--flat", "--json"],
    ["read", "--tree", "--flat"], ["read", "monitor", "--mapped", "--unmapped"],
    ["read", "--query", "hp"], ["read", "--export"], ["read", "--live-buffs"], ["read", "--param", "Magic.6230"],
    ["read", "--probe-params"], ["read", "--param-check"], ["export", "hp"], ["probe", "x"],
])
def test_read_usage_errors(argv):
    with pytest.raises(SystemExit) as e:
        cli.main(argv)
    assert e.value.code == 2


@pytest.mark.parametrize("argv", [
    ["read", "monitor", "--live"], ["read", "monitor", "hp"], ["read", "--mapped"], ["read", "hp", "--unmapped"],
    ["read", "*", "hp"], ["read", "params.Magic.6230", "hp"], ["read", "params.Magic.6230", "--live"],
])
def test_read_word_errors_are_an_error_line_not_a_usage_error(argv, monkeypatch):
    import eldendisk.commands.read as rcmd
    monkeypatch.setattr(rcmd, "cmd_read", lambda a: 0)
    assert cli.main(argv) == 1


def test_old_command_names_are_gone():
    for argv in (["sandbox", "status"], ["buffs"], ["animations"], ["run", "--attach"], ["run", "--hz", "30"], ["design"],
                 ["innovate-items", "spells"], ["external-scripts"], ["run", "--scripts-dir", "x"]):
        with pytest.raises(SystemExit):
            cli.main(argv)


def test_write_commands_parse(monkeypatch):
    seen = {}
    monkeypatch.setattr(cli, "cmd_write", lambda a: seen.update(vars(a)) or 0)
    assert cli.main(["write", "vigor=99", "level=150", "-v"]) == 0
    assert seen["pairs"] == ["vigor=99", "level=150"] and seen["verbose"] and seen["vault"] is None
    assert cli.main(["write", "params.Magic.6230.mp=default"]) == 0 and seen["pairs"] == ["params.Magic.6230.mp=default"]
    assert cli.main(["write"]) == 0 and seen["pairs"] == []                  # write alone: the list of names
    for old in (["write", "--set", "level=1"], ["write", "--refill", "hp"], ["write", "--reset", "all"],
                ["write", "--text"], ["write", "--flame-color"]):
        with pytest.raises(SystemExit):
            cli.main(old)                     # the flags before 1.8.0 part 2 are gone


@pytest.mark.parametrize("argv", [
    ["write", "--vault", "VAULT", "level=1"], ["write", "level=1", "--vault", "VAULT"],
])
def test_write_accepts_the_vault_before_or_after_the_values(monkeypatch, argv):
    seen = {}
    monkeypatch.setattr(cli, "cmd_write", lambda a: seen.update(vault=a.vault) or 0)
    assert cli.main(["X" if a == "VAULT" else a for a in argv]) == 0 and seen["vault"] == "X"


def test_the_creative_commands_parse(monkeypatch):
    seen = {}
    for name in ("cmd_scripts", "cmd_innovate", "cmd_resurrect", "cmd_reset"):
        monkeypatch.setattr(cli, name, lambda a: seen.update(vars(a)) or 0)
    assert cli.main(["scripts", "start", "RctColoursFollowTheSpell:1", "--when-loaded"]) == 0
    assert seen["words"] == ["start", "RctColoursFollowTheSpell:1"] and seen["when_loaded"]
    with pytest.raises(SystemExit):
        cli.main(["scripts", "stop", "*", "--when-loaded"])            # --when-loaded goes with start
    assert cli.main(["innovate-spells", "build", "reverse_cursed_technique", "2230001", "--dry-run"]) == 0
    assert seen["function"] == "build" and seen["names"] == ["reverse_cursed_technique", "2230001"] and seen["dry_run"]
    assert cli.main(["innovate-spells", "apply", "--when-loaded"]) == 0 and seen["function"] == "apply" and seen["when_loaded"]
    assert cli.main(["innovate-spells"]) == 0 and seen["function"] is None
    for bad in (["innovate-spells", "secure", "--dry-run"], ["innovate-spells", "build", "--when-loaded"], ["innovate-spells", "make"]):
        with pytest.raises(SystemExit):
            cli.main(bad)
    assert cli.main(["resurrect", "mohg lord", "10000850", "--dry-run"]) == 0 and seen["names"] == ["mohg lord", "10000850"]
    with pytest.raises(SystemExit):
        cli.main(["resurrect", "--dry-run", "--when-loaded"])
    assert cli.main(["reset", "runes", "monitor"]) == 0 and seen["words"] == ["runes", "monitor"]


def test_exit_codes():
    assert (attach.EXIT_UNSUPPORTED, attach.EXIT_EAC, attach.EXIT_NO_SESSION) == (2, 3, 5)


# ---------- JsonLogger ----------
def test_logger_survives_locked_tmp_file(tmp_path, monkeypatch):
    lg = JsonLogger(tmp_path)
    real = Path.write_text
    n = {"i": 0}

    def flaky(self, *a, **k):
        n["i"] += 1
        if n["i"] < 3:
            raise PermissionError("locked")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "write_text", flaky)
    monkeypatch.setattr("eldendisk.reader.export.RETRY_DELAY_S", 0)
    assert lg.write({"a": 1}) is True and json.loads(lg.path.read_text()) == {"a": 1}


def test_logger_returns_false_instead_of_raising_when_always_locked(tmp_path, monkeypatch):
    lg = JsonLogger(tmp_path)
    monkeypatch.setattr(Path, "write_text", lambda *a, **k: (_ for _ in ()).throw(PermissionError("locked")))
    monkeypatch.setattr("eldendisk.reader.export.RETRY_DELAY_S", 0)
    assert lg.write({"a": 1}) is False


# ---------- game_launcher / memory_reader helpers ----------
def test_has_eac_and_sha(tmp_path):
    assert processes.has_eac(["eldenring.exe", "EasyAntiCheat_EOS.dll"])
    assert not processes.has_eac(["eldenring.exe", "kernel32.dll"])
    f = tmp_path / "x.bin"; f.write_bytes(b"abc")
    assert processes.sha256_file(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_find_game_dir_override(tmp_path):
    with pytest.raises(FileNotFoundError):
        launcher.find_game_dir(str(tmp_path))
    (tmp_path / "eldenring.exe").write_bytes(b"")
    assert launcher.find_game_dir(str(tmp_path)) == tmp_path


def test_launch_is_offline_and_sets_steam_ids(tmp_path, monkeypatch):
    got = {}
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda cmd, cwd, env, **kw: got.update(cmd=cmd, cwd=cwd, env=env))
    launcher.launch(tmp_path)
    assert got["cmd"][1] == "-eac-nop-loaded" and got["env"]["SteamAppId"] == "1245620"


def test_memory_reader_helpers():
    assert memory_reader.is_user_ptr(0x140000000) and not memory_reader.is_user_ptr(0) and not memory_reader.is_user_ptr(1 << 63)
    m = FakeMem(); m.u32(0x200000000, 7); m.u64(0x200000010, 0x210000000)
    assert memory_reader.read_u32(m, 0x200000000) == 7 and memory_reader.read_ptr(m, 0x200000010) == 0x210000000
    assert memory_reader.read_u32(m, 0x300000000) is None


# ---------- Sampler: leaving the world resets per-character state ----------
def test_baseline_and_animation_reset_after_world_lost():
    m = full_world()
    s = Sampler(m, make_profile(), state_ids(), BASE)
    assert s.sample(NOW).character["runes"]["baseline"] == 10_008_626
    s._last_animation = {"2000000": {"name": "Standing", "categories": "MANNER"}}

    m.u64(BASE + 0x1000, 0)  # title screen
    assert s.sample(NOW + timedelta(seconds=1)).state == "WAITING_FOR_WORLD"
    assert s.baseline_runes == 10_008_626  # short load (fast travel): kept
    s.sample(NOW + timedelta(seconds=WORLD_LOST_RESET_S + 2))
    assert s.baseline_runes is None and s._last_animation == {}

    from tests.test_disk import world
    world(m, runes=5_000)  # another character loaded
    r = s.sample(NOW + timedelta(seconds=WORLD_LOST_RESET_S + 3))
    assert r.character["runes"]["baseline"] == 5_000 and r.character["runes"]["delta"] == 0


def test_read_failures_do_not_start_the_world_lost_clock():
    m = full_world()
    s = Sampler(m, make_profile(), state_ids(), BASE)
    s.sample(NOW)
    m.u32(GD + 0x68, 9999)  # level out of range -> diagnostic error, not a title screen
    for i in range(1, 30):
        assert s.sample(NOW + timedelta(seconds=i)).error
    assert s.baseline_runes == 10_008_626


def test_locate_player_reports_reason():
    m = full_world()
    s = Sampler(m, make_profile(), state_ids(), BASE)
    assert s.locate_player()[0] is not None
    m.u64(BASE + 0x1000, 0)
    assert s.locate_player() == (None, "world not loaded")


def test_script_mode_runs_without_relative_import_errors(tmp_path):
    """A frozen exe / `python eldendisk/__main__.py` runs __main__ as a top-level script: no relative imports allowed."""
    import subprocess
    script = Path(cli.__file__)
    r = subprocess.run([sys.executable, str(script), "vault", "status", "--vault", str(tmp_path / "v")],
                       capture_output=True, text=True)
    assert r.returncode == 0 and "live save is trusted" in r.stdout, r.stderr
    r = subprocess.run([sys.executable, str(script), "vault", "list", "--vault", str(tmp_path / "v")], capture_output=True, text=True)
    assert r.returncode == 0 and "no snapshots" in r.stdout, r.stderr
    r = subprocess.run([sys.executable, str(script), "--version"], capture_output=True, text=True)
    assert r.returncode == 0 and "eldendisk" in r.stdout, r.stderr


def test_every_help_page_renders(capsys):
    """argparse %-formats help strings: a bare % (e.g. %LOCALAPPDATA%) crashes `-h`."""
    pages = [[], ["run"], ["read"], ["write"], ["vault"], ["vault", "restore"],
             ["vault", "keep"], ["vault", "list"], ["vault", "verify"], ["vault", "prune"], ["vault", "status"],
             ["hash"]]
    for page in pages:
        with pytest.raises(SystemExit) as exc:
            cli.main([*page, "-h"])
        assert exc.value.code == 0, page
    assert "LOCALAPPDATA" in capsys.readouterr().out


def test_vault_on_and_off_are_per_run_flags(monkeypatch):
    seen = {}
    monkeypatch.setattr(cli, "cmd_run", lambda a: seen.update(vars(a)) or 0)
    assert cli.main(["run", "--vault-off", "-v"]) == 0 and seen["protect"] is False and seen["vault"] is None
    cli.main(["run", "--vault-on"])
    assert seen["protect"] is True
    cli.main(["run", "--vault", "D:\\v", "--vault-off"])
    assert seen["protect"] is False and seen["vault"] == "D:\\v"      # --vault DIR is still the folder
    with pytest.raises(SystemExit) as e:
        cli.main(["run", "--vault-on", "--vault-off"])
    assert e.value.code == 2


# ---------- where the files go ----------
def test_the_default_export_folder_is_under_the_eldendisk_data_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert paths.default_out_dir() == str(tmp_path / "EldenDisk" / "output")
    assert paths.app_data_dir() == tmp_path / "EldenDisk"


def test_the_exe_has_no_build_command():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["build"])

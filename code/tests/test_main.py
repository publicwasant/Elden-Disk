"""CLI-level tests: config resolution, throttled writes, build command, flags, logger and launcher helpers."""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import eldendisk.__main__ as cli
from eldendisk import game_launcher, memory_reader
from eldendisk.disk import Sample, Sampler, WORLD_LOST_RESET_S, doc_signature, iso
from eldendisk.json_logger import JsonLogger
from tests.test_disk import BASE, FakeMem, GD, NOW, effects, full_world, make_profile


# ---------- iso / doc_signature ----------
def test_iso_always_carries_utc_offset():
    assert iso(datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)) == "2026-09-30 12:00:00.000000+00:00"
    assert iso(datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone(timedelta(hours=7)))).endswith("+07:00")
    naive = iso(datetime(2026, 9, 30, 12, 0, 0))  # naive = local time, still labelled
    assert naive[-6] in "+-" and naive[-3] == ":"


def _doc(level=1, remaining=50.0):
    return {"system_status": {"state": "CONNECTED"},
            "character": {"level": level, "effects": {
                "1": {"name": "a", "times": {"buff_duration": remaining, "max_duration": 60.0, "last_activated_at": "t"}},
                "2": {"name": "perm"}}}}


def test_doc_signature_ignores_only_the_countdown():
    assert doc_signature(_doc(remaining=50.0)) == doc_signature(_doc(remaining=49.0))
    assert doc_signature(_doc(level=1)) != doc_signature(_doc(level=2))
    assert doc_signature({"character": None}) == {"character": None}
    assert _doc(remaining=50.0)["character"]["effects"]["1"]["times"]["buff_duration"] == 50.0  # input not mutated


# ---------- Monitor write throttling ----------
class RecLogger:
    def __init__(self, ok=True):
        self.docs, self.ok = [], ok

    def write(self, doc):
        if self.ok:
            self.docs.append(doc)
        return self.ok


def _sample(level=1, remaining=50.0):
    return Sample("CONNECTED", _doc(level, remaining)["character"])


def _monitor(interval=0.5, logger=None):
    args = argparse.Namespace(verbose=False, timer_interval=interval)
    return cli.Monitor(args, logger or RecLogger())


def test_countdown_only_changes_are_throttled_but_real_changes_are_immediate():
    mon = _monitor()
    mon.emit("CONNECTED", _sample(remaining=50.00), now_mono=0.0)
    mon.emit("CONNECTED", _sample(remaining=49.98), now_mono=0.016)
    mon.emit("CONNECTED", _sample(remaining=49.70), now_mono=0.30)
    assert len(mon.logger.docs) == 1
    mon.emit("CONNECTED", _sample(remaining=49.40), now_mono=0.60)  # interval elapsed
    assert len(mon.logger.docs) == 2
    mon.emit("CONNECTED", _sample(level=2, remaining=49.38), now_mono=0.61)  # real change: no waiting
    assert len(mon.logger.docs) == 3


def test_timer_interval_zero_writes_every_change():
    mon = _monitor(interval=0)
    for i in range(5):
        mon.emit("CONNECTED", _sample(remaining=50.0 - i * 0.02), now_mono=i * 0.016)
    assert len(mon.logger.docs) == 5


def test_busy_output_warns_once_per_streak(capsys):
    mon = _monitor(logger=RecLogger(ok=False))
    for i in range(4):
        mon.emit("CONNECTED", _sample(level=i + 1), now_mono=float(i))
    assert capsys.readouterr().err.count("output file busy") == 1
    mon.logger.ok = True
    mon.emit("CONNECTED", _sample(level=9), now_mono=10.0)
    mon.logger.ok = False
    mon.emit("CONNECTED", _sample(level=10), now_mono=11.0)
    assert capsys.readouterr().err.count("output file busy") == 1  # new streak warns again


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
    assert cli.get_resource_path("offsets.json") == ext.resolve() / "offsets.json"
    assert cli.describe_resource(ext / "offsets.json") == "external"


def test_embedded_used_when_nothing_external(frozen):
    _ext, emb = frozen
    (emb / "offsets.json").write_text("{}")
    got = cli.get_resource_path("offsets.json")
    assert got == emb / "offsets.json" and cli.describe_resource(got) == "embedded"


def test_frozen_does_not_walk_ancestors(frozen):
    ext, _emb = frozen
    (ext.parent / "only-in-parent.json").write_text("{}")
    assert cli.get_resource_path("only-in-parent.json") == Path("only-in-parent.json")
    assert cli.describe_resource("nope.json") == "missing"


def test_source_run_resolves_project_files():
    assert cli.runtime_dirs() == (None, None)
    assert cli.get_resource_path("offsets.json").name == "offsets.json"
    assert cli.describe_resource(cli.get_resource_path("offsets.json")) == "source"


# ---------- build ----------
@pytest.fixture
def project(tmp_path, monkeypatch):
    code = tmp_path / "code"
    (code / "eldendisk").mkdir(parents=True)
    (code / "offsets.json").write_text("{}")
    (code / "chr_state_ids.json").write_text("{}")
    (code / "eldendisk" / "__main__.py").write_text("")
    monkeypatch.setattr(cli, "HERE", code)
    return tmp_path


def _args(**kw):
    base = dict(engine="pyinstaller", clean=False, embed_configs=False, icon=None)
    base.update(kw)
    return argparse.Namespace(**base)


def _run_build(monkeypatch, args, rc=0):
    calls = []

    def fake_run(cmd, check=False):
        calls.append(cmd)
        return argparse.Namespace(returncode=rc)

    monkeypatch.setattr("subprocess.run", fake_run)
    return cli.cmd_build(args), calls


def test_pyinstaller_embed_adds_configs_not_schema(project, monkeypatch):
    rc, calls = _run_build(monkeypatch, _args(embed_configs=True))
    cmd = calls[0]
    assert rc == 0 and "PyInstaller" in cmd and "--onefile" in cmd
    adds = [c for c in cmd if c.startswith("--add-data=")]
    assert len(adds) == 2 and not any("schema" in a for a in adds)
    assert not (project / "build" / "dist" / cli.__version__ / "offsets.json").exists()  # embedded: nothing copied


def test_nuitka_embed_includes_data_files(project, monkeypatch):
    rc, calls = _run_build(monkeypatch, _args(engine="nuitka", embed_configs=True))
    inc = [c for c in calls[0] if c.startswith("--include-data-files=")]
    assert rc == 0 and len(inc) == 2 and inc[0].endswith("=offsets.json")
    assert "--output-filename=eldendisk.exe" in calls[0]


@pytest.mark.parametrize("engine", ["pyinstaller", "nuitka"])
def test_non_embedded_build_copies_editable_configs_for_both_engines(project, monkeypatch, engine):
    rc, calls = _run_build(monkeypatch, _args(engine=engine))
    out = project / "build" / "dist" / cli.__version__
    assert rc == 0 and (out / "offsets.json").exists() and (out / "chr_state_ids.json").exists()
    assert not any(c.startswith(("--add-data=", "--include-data-files=")) for c in calls[0])


def test_failed_build_returns_1_and_copies_nothing(project, monkeypatch):
    rc, _ = _run_build(monkeypatch, _args(), rc=2)
    assert rc == 1 and not (project / "build" / "dist" / cli.__version__ / "offsets.json").exists()


def test_clean_removes_old_artifacts(project, monkeypatch):
    stale = project / "build" / "work" / "stale.txt"
    stale.parent.mkdir(parents=True); stale.write_text("x")
    _run_build(monkeypatch, _args(clean=True))
    assert not stale.exists()


def test_unknown_engine_and_missing_icon(project, monkeypatch, capsys):
    assert cli.cmd_build(_args(engine="cx_freeze")) == 1
    _rc, calls = _run_build(monkeypatch, _args(icon="nope.ico"))
    assert not any(c.startswith("--icon=") for c in calls[0]) and "icon file not found" in capsys.readouterr().err


# ---------- argparse surface ----------
def test_run_flags_parse(monkeypatch):
    seen = {}
    monkeypatch.setattr(cli, "cmd_run", lambda a: seen.update(vars(a)) or 0)
    assert cli.main(["run", "--no-idle", "--timer-interval", "0.25", "--hz", "30"]) == 0
    assert seen["no_idle"] is True and seen["timer_interval"] == 0.25 and seen["hz"] == 30.0
    seen.clear()
    cli.main(["run"])
    assert seen["no_idle"] is False and seen["timer_interval"] == 0.5


def test_hz_out_of_range_is_a_usage_error():
    with pytest.raises(SystemExit) as e:
        cli.main(["run", "--hz", "500"])
    assert e.value.code == 2


def test_deprecated_noop_flags_still_accepted(monkeypatch):
    monkeypatch.setattr(cli, "cmd_animations", lambda a: 0)
    monkeypatch.setattr(cli, "cmd_effects", lambda a: 0)
    assert cli.main(["animations", "-q"]) == 0
    assert cli.main(["effects", "--effects", "x.json", "-q"]) == 0


def test_exit_codes():
    assert (cli.EXIT_UNSUPPORTED, cli.EXIT_EAC) == (2, 3)


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
    monkeypatch.setattr("eldendisk.json_logger.RETRY_DELAY_S", 0)
    assert lg.write({"a": 1}) is True and json.loads(lg.path.read_text()) == {"a": 1}


def test_logger_returns_false_instead_of_raising_when_always_locked(tmp_path, monkeypatch):
    lg = JsonLogger(tmp_path)
    monkeypatch.setattr(Path, "write_text", lambda *a, **k: (_ for _ in ()).throw(PermissionError("locked")))
    monkeypatch.setattr("eldendisk.json_logger.RETRY_DELAY_S", 0)
    assert lg.write({"a": 1}) is False


# ---------- game_launcher / memory_reader helpers ----------
def test_has_eac_and_sha(tmp_path):
    assert game_launcher.has_eac(["eldenring.exe", "EasyAntiCheat_EOS.dll"])
    assert not game_launcher.has_eac(["eldenring.exe", "kernel32.dll"])
    f = tmp_path / "x.bin"; f.write_bytes(b"abc")
    assert game_launcher.sha256_file(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_find_game_dir_override(tmp_path):
    with pytest.raises(FileNotFoundError):
        game_launcher.find_game_dir(str(tmp_path))
    (tmp_path / "eldenring.exe").write_bytes(b"")
    assert game_launcher.find_game_dir(str(tmp_path)) == tmp_path


def test_launch_is_offline_and_sets_steam_ids(tmp_path, monkeypatch):
    got = {}
    monkeypatch.setattr(game_launcher.subprocess, "Popen", lambda cmd, cwd, env: got.update(cmd=cmd, cwd=cwd, env=env))
    game_launcher.launch(tmp_path)
    assert got["cmd"][1] == "-eac-nop-loaded" and got["env"]["SteamAppId"] == "1245620"


def test_memory_reader_helpers():
    assert memory_reader.is_user_ptr(0x140000000) and not memory_reader.is_user_ptr(0) and not memory_reader.is_user_ptr(1 << 63)
    m = FakeMem(); m.u32(0x200000000, 7); m.u64(0x200000010, 0x210000000)
    assert memory_reader.read_u32(m, 0x200000000) == 7 and memory_reader.read_ptr(m, 0x200000010) == 0x210000000
    assert memory_reader.read_u32(m, 0x300000000) is None


# ---------- Sampler: leaving the world resets per-character state ----------
def test_baseline_and_animation_reset_after_world_lost():
    m = full_world()
    s = Sampler(m, make_profile(), effects(), BASE)
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
    s = Sampler(m, make_profile(), effects(), BASE)
    s.sample(NOW)
    m.u32(GD + 0x68, 9999)  # level out of range -> diagnostic error, not a title screen
    for i in range(1, 30):
        assert s.sample(NOW + timedelta(seconds=i)).error
    assert s.baseline_runes == 10_008_626


def test_locate_player_reports_reason():
    m = full_world()
    s = Sampler(m, make_profile(), effects(), BASE)
    assert s.locate_player()[0] is not None
    m.u64(BASE + 0x1000, 0)
    assert s.locate_player() == (None, "world not loaded")

"""1.8.0 part 2: `reset`, the read baselines in a small file (reader/baselines.py) that every reader of the same game takes."""
from types import SimpleNamespace

import pytest

import eldendisk.__main__ as cli
from eldendisk.commands import read as rcmd
from eldendisk.reader import baselines
from eldendisk.reader.ledger import Ledger


def test_the_names_of_reset():
    assert baselines.names_of([]) == baselines.names_of(["*"]) == baselines.names_of(["all"]) == ["runes", "buffs", "animations"]
    assert baselines.names_of(["monitor"]) == ["buffs", "animations"]
    assert baselines.names_of(["runes.delta", "character.runes", "monitor-buffs"]) == ["runes", "buffs"]
    for bad in (["hp"], ["*", "runes"]):
        with pytest.raises(ValueError):
            baselines.names_of(bad)


def test_a_reader_takes_what_was_set_for_its_game_once(tmp_path):
    f = tmp_path / "baselines.json"
    baselines.save(10, 1.5, {"runes": 1234}, f)
    w = baselines.Watch(10, 1.5, f)
    got = w.new()
    assert list(got) == ["runes"] and got["runes"]["total"] == 1234
    assert w.new() == {}                                                         # nothing new since
    baselines.save(10, 1.5, {"buffs": None}, f)
    got = w.new()
    assert list(got) == ["buffs"] and baselines.load(f)["runes"]["total"] == 1234   # the runes of the same game are kept
    assert baselines.Watch(11, 1.5, f).new() == {}                               # another game process: none of it
    baselines.save(11, 9.0, {"animations": None}, f)
    assert set(baselines.load(f)) == {"pid", "started", "animations"}             # the file of another game is replaced


def test_a_reader_started_after_a_monitor_reset_does_not_clear_its_own_history(tmp_path):
    f = tmp_path / "baselines.json"
    baselines.save(10, 1.5, {"runes": 5, "buffs": None}, f)
    got = baselines.Watch(10, 1.5, f, since=0.0).new()
    assert list(got) == ["runes"]                                                # the runes count at once, the old buffs reset not


def test_what_a_reset_set_reaches_the_sampler_and_the_monitors(tmp_path, capsys):
    f = tmp_path / "baselines.json"
    sampler = SimpleNamespace(baseline_runes=None, reset_baseline=lambda r: setattr(sampler, "baseline_runes", r))
    ledger = Ledger()
    from datetime import datetime, timedelta
    t0 = datetime.now().astimezone()
    ledger.update({1: None, 2: None}, t0)
    ledger.update({1: None}, t0 + timedelta(seconds=30))                        # 2 has ended
    monitor = SimpleNamespace(name="buffs", ledger=ledger)
    w = baselines.Watch(10, 1.5, f)
    baselines.save(10, 1.5, {"runes": 777, "buffs": None}, f)
    rcmd._take_baselines(w, sampler, [monitor])
    assert sampler.baseline_runes == 777 and list(ledger.entries) == [1]          # what ended is gone, what is active stays
    assert "runes: the baseline is 777" in capsys.readouterr().err


def test_reset_takes_the_runes_of_the_game_now_and_writes_nothing_to_it(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    target = SimpleNamespace(pid=10, started=1.5, profile=SimpleNamespace(), base=0)
    monkeypatch.setattr(rcmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(rcmd, "locate", lambda offsets: target)
    monkeypatch.setattr(rcmd, "open_read", lambda t: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(rcmd, "Sampler", lambda *a: None)
    monkeypatch.setattr(rcmd, "_first_sample", lambda args, mem, s: SimpleNamespace(runes=4242))
    assert cli.main(["reset", "runes", "monitor"]) == 0
    doc = baselines.load()
    assert doc["pid"] == 10 and doc["runes"]["total"] == 4242 and "buffs" in doc and "animations" in doc
    assert "4,242" in capsys.readouterr().err
    assert cli.main(["reset", "hp"]) == 1

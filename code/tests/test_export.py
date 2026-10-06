"""`read export`: when the document reaches the disk (spec 1.6.2 section 5)."""
import json

import pytest

from eldendisk.reader.export import ExportWriter, JsonLogger
from eldendisk.reader.sampler import Sample


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def character(buff=10.0, level=100):
    return {"level": level, "effects": {"1": {"name": "B", "categories": "CONSUMABLES",
                                              "times": {"buff_duration": buff, "max_duration": 60.0,
                                                        "last_activated_at": "2026-10-06 21:00:00.000000+07:00"}}}}


def sample(**kw):
    return Sample("CONNECTED", character(**kw))


@pytest.fixture
def rig(tmp_path):
    clock = Clock()
    lg = JsonLogger(tmp_path / "out")
    ew = ExportWriter(lg, interval=0.5, timer_interval=2.0, clock=clock)
    ew.pid = 1
    return ew, lg, clock, tmp_path / "out" / "disk-state.json"


def test_first_document_is_written_at_once(rig):
    ew, lg, clock, path = rig
    ew.emit("CONNECTED", sample())
    assert ew.writes == 1 and json.loads(path.read_text())["character"]["level"] == 100


def test_identical_documents_are_never_rewritten(rig):
    ew, lg, clock, path = rig
    for _ in range(100):
        clock.t += 0.1
        ew.emit("CONNECTED", sample())
    assert ew.writes == 1


def test_a_real_change_waits_for_the_interval_then_is_written_without_a_new_change(rig):
    ew, lg, clock, path = rig
    ew.emit("CONNECTED", sample())
    clock.t += 0.1
    ew.emit("CONNECTED", sample(level=101))          # inside the 0.5 s interval: held
    assert ew.writes == 1 and json.loads(path.read_text())["character"]["level"] == 100
    clock.t += 0.5
    ew.emit("CONNECTED", sample(level=101))          # the same document, interval elapsed: the held change lands
    assert ew.writes == 2 and json.loads(path.read_text())["character"]["level"] == 101


def test_countdown_only_changes_refresh_every_timer_interval(rig):
    ew, lg, clock, path = rig
    ew.emit("CONNECTED", sample(buff=10.0))
    for i in range(1, 20):                            # 1.9 s of ticking buff
        clock.t += 0.1
        ew.emit("CONNECTED", sample(buff=10.0 - i * 0.1))
    assert ew.writes == 1
    clock.t += 0.2                                     # 2.1 s since the last write
    ew.emit("CONNECTED", sample(buff=7.9))
    assert ew.writes == 2


def test_timer_interval_zero_never_refreshes_a_countdown(tmp_path):
    clock = Clock()
    ew = ExportWriter(JsonLogger(tmp_path / "o"), interval=0.5, timer_interval=0, clock=clock)
    ew.emit("CONNECTED", sample(buff=10.0))
    clock.t += 60
    ew.emit("CONNECTED", sample(buff=1.0))
    assert ew.writes == 1


def test_close_writes_the_last_document(rig):
    ew, lg, clock, path = rig
    ew.emit("CONNECTED", sample())
    clock.t += 0.1
    ew.emit("DISCONNECTED", sample())                  # within the interval: not written yet
    assert json.loads(path.read_text())["systems"]["status"]["tool_state"] == "CONNECTED"
    ew.close()
    assert json.loads(path.read_text())["systems"]["status"]["tool_state"] == "DISCONNECTED"


def test_a_locked_file_is_retried_not_dropped(rig, monkeypatch):
    ew, lg, clock, path = rig
    calls = []
    real = lg.write
    monkeypatch.setattr(lg, "write", lambda doc: calls.append(1) or (len(calls) > 1 and real(doc)))
    ew.emit("CONNECTED", sample())
    assert ew.writes == 0
    clock.t += 0.1
    ew.emit("CONNECTED", sample())
    assert ew.writes == 1


def test_session_label_follows_the_flag_and_read_only_stays_true(rig):
    ew, lg, clock, path = rig
    ew.sandbox = True
    ew.emit("CONNECTED", sample())
    assert json.loads(path.read_text())["systems"]["session"] == {"mode": "sandbox", "read_only": True, "sandbox": True}

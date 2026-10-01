import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import soak_check  # noqa: E402


def doc(state="CONNECTED", **over):
    ch = {"level": 386, "runes": 1000, "attributes": dict(zip(soak_check.ATTRS, [80, 60, 60, 90, 90, 15, 60, 10])),
          "effects": {}}
    d = {"system_status": {"state": state, "read_only": True}, "character": ch if state == "CONNECTED" else None,
         "telemetry": {"session_start_runes": 900, "rune_delta": 100}}
    d.update(over)
    return d


def test_valid_documents_have_no_problems():
    assert soak_check.check(doc()) == []
    assert soak_check.check(doc("WAITING_FOR_WORLD")) == []


def test_detects_problems():
    bad = doc(); bad["character"]["level"] = 0
    assert any("level" in p for p in soak_check.check(bad))
    bad = doc(); bad["telemetry"]["rune_delta"] = 5
    assert any("rune_delta" in p for p in soak_check.check(bad))
    bad = doc("WAITING_FOR_WORLD"); bad["character"] = {"level": 1}
    assert any("character present" in p for p in soak_check.check(bad))
    bad = doc()
    bad["character"]["effects"] = {
        "1": {"name": "Test", "kind": "TIMED", "times": {"buff_duration": 90.0, "max_duration": 30.0}}
    }
    assert any("impossible timer" in p for p in soak_check.check(bad))
    assert soak_check.check({}) == ["missing top-level keys"]

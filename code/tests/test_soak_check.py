import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import soak_check  # noqa: E402


def doc(state="CONNECTED", **over):
    runes = {
        "total": 1000,
        "baseline": 900,
        "delta": 100,
    }
    vitals = {
        "hit_point": {"current": 890, "maximum": 1914, "base": 2015},
        "focus_point": {"current": 350, "maximum": 350, "base": 350},
        "stamina": {"current": 178, "maximum": 178, "base": 158},
    }
    ch = {"level": 386, "vitals": vitals, "runes": runes, "attributes": dict(zip(soak_check.ATTRS, [80, 60, 60, 90, 90, 15, 60, 10])),
          "buffs": {}, "animations": {}}
    d = {"systems": {
            "profile": {"sha256": "abc", "game": "eldenring.exe", "version": "1.17.1"},
            "features": {"buffs_supported": True, "animations_supported": True, "creative_supported": True},
            "status": {"pid": 1234, "tool_state": state, "anti_cheat_state": "DISABLED_OFFLINE", "game_connected": True, "ignored": {"buffs": 0, "animations": 0}},
            "session": {"mode": "telemetry", "read_only": True, "sandbox": False}
         },
         "character": ch}
    d.update(over)
    return d


def test_valid_documents_have_no_problems():
    assert soak_check.check(doc()) == []
    assert soak_check.check(doc("IDLE")) == []
    assert soak_check.check(doc("DISCONNECTED")) == []
    assert soak_check.check(doc("WAITING_FOR_WORLD")) == []
    assert soak_check.check(doc("WAITING_FOR_PROCESS")) == []
    assert soak_check.check(doc("EAC_ACTIVE")) == []
    assert soak_check.check(doc("UNSUPPORTED_VERSION")) == []
    assert soak_check.check(doc("WAITING_FOR_WORLD", character=None)) == []


def test_detects_problems():
    bad = doc(); bad["character"]["level"] = 0
    assert any("level" in p for p in soak_check.check(bad))
    bad = doc(); bad["character"]["runes"]["delta"] = 5
    assert any("runes.delta" in p for p in soak_check.check(bad))
    bad = doc("WAITING_FOR_WORLD"); bad["character"]["level"] = 0
    assert any("level" in p for p in soak_check.check(bad))
    bad = doc()
    bad["character"]["buffs"] = {
        "1": {"name": "Test", "kind": "TIMED", "times": {"buff_duration": 90.0, "max_duration": 30.0}}
    }
    assert any("impossible timer" in p for p in soak_check.check(bad))
    assert soak_check.check({}) == ["missing top-level keys"]

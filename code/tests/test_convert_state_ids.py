"""tools/convert_state_ids.py: the old flat chr_state_ids.json becomes {"buffs": ..., "animations": ...} without `sources`."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import convert_state_ids as conv  # noqa: E402

from eldendisk.game.profile import load_state_ids  # noqa: E402

OLD = {
    "_readme": "dropped",
    "311100": {"name": "Gold Scarab", "sources": "EFFECTS", "categories": "TALISMANS", "abilities": "+20% runes"},
    "2000000": {"name": "Standing", "sources": "ANIMATIONS", "categories": "MANNER"},
    "5": {"name": "No sources given"},
}


def test_convert_splits_by_sources_and_drops_the_field():
    new = conv.convert(OLD)
    assert list(new) == ["buffs", "animations"]
    assert new["buffs"] == {"311100": {"name": "Gold Scarab", "categories": "TALISMANS", "abilities": "+20% runes"},
                            "5": {"name": "No sources given"}}
    assert new["animations"] == {"2000000": {"name": "Standing", "categories": "MANNER"}}
    assert OLD["311100"]["sources"] == "EFFECTS"          # the input is not changed


def test_the_command_keeps_a_backup_and_the_result_loads(tmp_path, capsys):
    f = tmp_path / "chr_state_ids.json"
    f.write_text(json.dumps(OLD), encoding="utf-8")
    assert conv.main([str(f)]) == 0
    assert json.loads((tmp_path / "chr_state_ids.json.bak").read_text(encoding="utf-8")) == OLD
    ids = load_state_ids(f)
    assert set(ids.buffs) == {311100, 5} and set(ids.animations) == {2000000}
    assert conv.main([str(f)]) == 1 and "already in the new shape" in capsys.readouterr().err


def test_out_leaves_the_input_alone(tmp_path):
    f, out = tmp_path / "old.json", tmp_path / "new.json"
    f.write_text(json.dumps(OLD), encoding="utf-8")
    assert conv.main([str(f), "--out", str(out)]) == 0
    assert json.loads(f.read_text(encoding="utf-8")) == OLD and not (tmp_path / "old.json.bak").exists()
    assert "buffs" in json.loads(out.read_text(encoding="utf-8"))

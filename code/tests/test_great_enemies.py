"""1.8.0: the great-enemies table (design/resurrect), its names, and (golden) that it agrees with the game's own file."""
import os
import struct
from pathlib import Path

import pytest

from eldendisk.creative.resurrect.great_enemies import TableError, load
from eldendisk.creative.resurrect.great_enemies.table import creative_list

T = load()


def test_the_table_has_every_great_enemy_of_1_17_1_with_its_flags():
    assert len(T.rows) == 212 and T.game == "1.17.1"
    assert sum(1 for r in T.rows.values() if r["dlc"]) == 40
    for rid, r in T.rows.items():
        assert r["flags"]["defeated"] > 0 and r["runes"] >= 0 and r["name"]
        assert all(not 61000 <= f < 62000 for f in T.flags_of(rid)), "the achievement flags are never turned off"
    assert T.flags_of(10000850) == [10000850, 9100, 60510, 10000851]                # Margit: defeat, play log, drop, intro
    assert T.flags_of(12050800)[:2] == [12050800, 9112] and {510120, 12050801, 12050802} <= set(T.flags_of(12050800))


def test_the_rows_say_what_the_game_shows():
    margit, mohg = T.rows[10000850], T.rows[12050800]
    assert margit["name"] == "Margit, the Fell Omen" and margit["place"] == "Stormhill" and margit["grace"]["name"] == "Castleward Tunnel"
    assert margit["runes"] == 12000 and margit["drop"] == ["Talisman Pouch"] and margit["story"] and not margit["dlc"]
    assert mohg["runes"] == 420000 and "Remembrance of the Blood Lord" in mohg["drop"]
    assert mohg["grace"]["name"] == "Dynasty Mausoleum Midpoint"                     # not the grace the fight lights


@pytest.mark.parametrize("names, want", [
    (["margit"], [10000850]), (["Margit, the Fell Omen"], [10000850]), (["fell omen"], [10000850]), (["10000850"], [10000850]),
    (["mohg lord"], [12050800]), (["radahn caelid"], [1052380800]), (["margit", "10000850"], [10000850]),
])
def test_a_great_enemy_is_named_by_its_name_part_of_it_or_its_id(names, want):
    assert T.resolve(names) == want


@pytest.mark.parametrize("name, says", [
    ("mohg", "2 great enemies"), ("godrick", "Soldier of Godrick"), ("dragonkin soldier", "Lake of Rot"), ("godrik", "closest: Godrick"),
    ("123", "no great enemy has this id"),
])
def test_an_ambiguous_or_wrong_name_is_refused_with_what_it_fits(name, says):
    with pytest.raises(TableError, match=says):
        T.resolve([name])


def test_all_is_every_great_enemy_and_stands_alone():
    assert len(T.resolve(["all"])) == 212 and T.resolve(["*"]) == T.resolve(["all"])
    with pytest.raises(TableError, match="stands alone"):
        T.resolve(["margit", "all"])
    with pytest.raises(TableError):
        T.resolve(["margit", "godrik"])                                              # one wrong name: nothing is chosen


def test_the_design_list():
    assert creative_list({"innovate_items": {}}) is None
    assert creative_list({"resurrect": {"great_enemies": {"activate": ["margit", 10000800]}}}) == ["margit", "10000800"]
    assert creative_list({"resurrect": {"great_enemies": {"activate": "all"}}}) == ["all"]
    with pytest.raises(TableError):
        creative_list({"resurrect": {"great_enemies": {"activate": {"x": 1}}}})


ORIG = os.environ.get("ELDENDISK_REGULATION_ORIG")


@pytest.mark.skipif(not ORIG, reason="needs ELDENDISK_REGULATION_ORIG (the game's original regulation.bin)")
def test_golden_the_table_agrees_with_the_games_gamearea_param():
    from eldendisk.creative.innovate_spells import container, zstd
    from eldendisk.creative.innovate_spells.container import Bnd4
    dcx = container.decrypt(Path(ORIG).read_bytes())
    csize = struct.unpack(">I", dcx[0x20:0x24])[0]
    blob = Bnd4(zstd.decode_frame(dcx[0x4C:0x4C + csize])).get("GameAreaParam").data
    n = struct.unpack_from("<H", blob, 0xA)[0]
    game = {}
    for i in range(n):
        rid, _p, off, _nm = struct.unpack_from("<iIQQ", blob, 0x40 + 24 * i)
        defeat, = struct.unpack_from("<I", blob, off + 68)
        if defeat:
            game[rid] = (defeat, struct.unpack_from("<I", blob, off + 4)[0])
    assert set(game) == set(T.rows)
    assert all(game[rid] == (r["flags"]["defeated"], r["runes"]) for rid, r in T.rows.items())

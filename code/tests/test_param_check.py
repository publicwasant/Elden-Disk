"""`read --param-check FILE` (Phase 1, step 1.4): the six tables of a regulation.bin against the same tables in the game."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from eldendisk.commands import paramcheck as PC
from eldendisk.commands import read as read_cmd
from eldendisk.game.paramlayouts import LAYOUTS
from eldendisk.game.params import ParamError
from tests import paramfile as pf
from tests.test_disk import BASE
from tests.test_param_tables import MAGIC, encode, put_table, tables

FILE_MAGIC = dict(MAGIC)


def game_with(rows, new_rows=()):
    m = pf.Pages()
    put_table(m, "Magic", rows, new_rows=new_rows)
    return m


def check(mem, checked, as_json=False):
    target = SimpleNamespace(profile=pf.params_profile(), base=BASE)
    return read_cmd._param_check(SimpleNamespace(json=as_json), target, mem, checked)


# ---- the game side: a whole table at once ----
def test_all_rows_gives_every_row_including_the_ones_an_extension_added():
    m = game_with(MAGIC, new_rows={90000: encode("Magic", mp=7)})
    rows = tables(m).all_rows("Magic")
    assert set(rows) == {4000, 6210, 6230, 90000}
    for rid, raw in rows.items():
        assert raw == tables(m).row_address("Magic", rid)[1]


def test_all_rows_reads_in_pieces_and_still_gives_the_same_rows(monkeypatch):
    from eldendisk.game import paramtables
    m = game_with(MAGIC, new_rows={90000: encode("Magic", mp=7)})
    whole = tables(m).all_rows("Magic")
    monkeypatch.setattr(paramtables, "READ_CHUNK", 100)
    assert tables(m).all_rows("Magic") == whole


def test_an_unreadable_table_is_an_error_not_a_partial_result():
    with pytest.raises(ParamError, match="not found"):
        tables(pf.Pages()).all_rows("Magic")


# ---- the comparison ----
def test_equal_rows_differences_and_rows_on_one_side_only():
    game = dict(MAGIC)
    game[6230] = encode("Magic", mp=0, refCategory1=1, refId1=10623000, refType=22, isEnchant=1)
    game[5]= encode("Magic", mp=1)
    file = dict(MAGIC)
    file[99] = encode("Magic", mp=2)
    d = PC.compare("Magic", file, game)
    assert (d.in_file, d.in_game, d.equal) == (4, 4, 2)
    assert d.differ == {6230: [("mp", 21, 0)]}
    assert d.only_file == [99] and d.only_game == [5] and not d.same


def test_bytes_that_differ_outside_every_named_field_are_still_reported():
    a = bytearray(MAGIC[4000])
    named = {off + i for _t, off, size, _b, _bits, _a in LAYOUTS["Magic"]["fields"].values() for i in range(size)}
    free = next(i for i in range(len(a)) if i not in named)
    b = bytearray(a)
    b[free] ^= 0xFF
    d = PC.compare("Magic", {1: bytes(a)}, {1: bytes(b)})
    assert d.differ[1][0][0].startswith("(bytes not in a named field)")


def test_identical_tables_are_the_same():
    assert PC.compare("Magic", MAGIC, dict(MAGIC)).same


def test_the_text_names_the_rows_and_fields_and_caps_long_lists():
    file = {i: encode("Magic", mp=1) for i in range(1, 40)}
    game = {i: encode("Magic", mp=2) for i in range(1, 40)}
    text = "\n".join(PC.lines([PC.compare("Magic", file, game)]))
    assert "Magic.1  mp: file 1, game 2" in text and "39 differ" in text
    assert f"{39 - PC.SHOWN_ROWS} more rows differ" in text and "Magic.30 " not in text
    bad = PC.TableDiff("Goods", 3, 0)
    bad.error = "Goods not found (x)"
    assert "not read: Goods not found" in "\n".join(PC.lines([bad]))


# ---- the command ----
def test_agreement_is_exit_0_and_nothing_is_written(capsys):
    m = game_with(MAGIC, new_rows={90000: encode("Magic", mp=7)})
    m.write = lambda *a, **k: (_ for _ in ()).throw(AssertionError("a check must not write"))
    assert check(m, {"Magic": {**MAGIC, 90000: encode("Magic", mp=7)}}) == 0
    assert "4 rows in the file, 4 in the game: 4 equal" in capsys.readouterr().out


def test_a_value_changed_in_the_game_is_exit_1_and_named(capsys):
    m = game_with({**MAGIC, 6230: encode("Magic", mp=0, refCategory1=1, refId1=10623000, refType=22, isEnchant=1)})
    assert check(m, {"Magic": MAGIC}) == 1
    assert "Magic.6230  mp: file 21, game 0" in capsys.readouterr().out


def test_json_lists_every_difference(capsys):
    m = game_with({**MAGIC, 4000: encode("Magic", mp=99)})
    assert check(m, {"Magic": MAGIC}, as_json=True) == 1
    doc = json.loads(capsys.readouterr().out)["param_check"]["Magic"]
    assert doc["differ"] == {"4000": [{"field": "mp", "file": 10, "game": 99}]} and doc["equal"] == 2


def test_a_table_the_game_cannot_give_fails_the_check(capsys):
    assert check(pf.Pages(), {"Magic": MAGIC}) == 1
    assert "not read" in capsys.readouterr().out


# ---- the file side ----
def test_a_missing_file_and_a_file_that_is_not_a_regulation_are_told_not_raised(tmp_path):
    with pytest.raises(PC.CheckFileError, match="nope.bin"):
        PC.file_rows(tmp_path / "nope.bin")
    junk = tmp_path / "junk.bin"
    junk.write_bytes(b"not a regulation" * 10)
    with pytest.raises(PC.CheckFileError):
        PC.file_rows(junk)


def test_the_command_stops_before_the_game_when_the_file_is_bad(tmp_path, monkeypatch):
    monkeypatch.setattr(read_cmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(read_cmd, "_wait_for_game", lambda *a, **k: pytest.fail("the game must not be waited for"))
    args = SimpleNamespace(param=None, param_check=str(tmp_path / "nope.bin"), state_ids="x", offsets="x", timeout=1.0,
                           export=False, live=False, live_buffs=False, live_animations=False, query=None, probe_params=False)
    assert read_cmd.cmd_read(args) == 1


def _read_args(**over):
    base = dict(param=None, param_check=None, state_ids="x", offsets="x", timeout=1.0, export=False, live=False,
                live_buffs=False, live_animations=False, query=None, probe_params=False, json=False, vault=None,
                flat=False, verbose=False, hz=1, quiet=False, no_idle=True, out="x", mapped=False, unmapped=False,
                export_interval=0.0, timer_interval=0.0)
    return SimpleNamespace(**{**base, **over})


def test_without_a_file_the_regulation_bin_in_the_game_folder_is_opened(monkeypatch, tmp_path):
    """`--param-check` alone: the file the game loaded (a `run` session puts the build there)."""
    opened = []
    monkeypatch.setattr(read_cmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(read_cmd.paramcheck, "file_rows", lambda p: opened.append(Path(p)) or (_ for _ in ()).throw(
        PC.CheckFileError("stop here")))
    monkeypatch.setattr(read_cmd, "_wait_for_game", lambda *a, **k: SimpleNamespace(exe_path=tmp_path / "Game" / "eldenring.exe"))
    monkeypatch.setattr(read_cmd, "load_state_ids", lambda p: {})
    assert read_cmd.cmd_read(_read_args(param_check="")) == 1
    assert opened == [tmp_path / "Game" / "regulation.bin"]


def test_a_named_file_is_opened_before_waiting_for_the_game(monkeypatch, tmp_path):
    monkeypatch.setattr(read_cmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(read_cmd, "_wait_for_game", lambda *a, **k: pytest.fail("the game must not be waited for"))
    assert read_cmd.cmd_read(_read_args(param_check=str(tmp_path / "nope.bin"))) == 1


def test_the_flag_alone_parses_and_a_file_after_it_too(monkeypatch):
    import eldendisk.__main__ as cli
    seen = {}
    monkeypatch.setattr(cli, "cmd_read", lambda a: seen.update(vars(a)) or 0)
    assert cli.main(["read", "--param-check"]) == 0 and seen["param_check"] == ""
    assert cli.main(["read", "--param-check", "x.bin", "--json"]) == 0 and seen["param_check"] == "x.bin" and seen["json"]
    assert cli.main(["read"]) == 0 and seen["param_check"] is None


@pytest.mark.parametrize("extra", [["--flat"], ["--live"], ["--probe-params"], ["--param", "Magic.6230"], ["--query", "hp"]])
def test_param_check_stands_alone(extra):
    import eldendisk.__main__ as cli
    with pytest.raises(SystemExit):
        cli.main(["read", "--param-check", "x.bin", *extra])
    with pytest.raises(SystemExit):
        cli.main(["read", "--param-check", *extra])


ORIG = os.environ.get("ELDENDISK_REGULATION_ORIG")


@pytest.mark.skipif(not ORIG or not Path(ORIG).is_file(), reason="set ELDENDISK_REGULATION_ORIG to the pristine regulation.bin")
def test_the_real_file_gives_the_six_tables_with_the_rows_the_survey_found():
    rows = PC.file_rows(Path(ORIG))
    assert {t: len(r) for t, r in rows.items()} == {"Goods": 2329, "Magic": 317, "SpEffect": 11354, "Bullet": 15475,
                                                     "AtkParam_Pc": 11017, "ShopLineup": 1296}
    from eldendisk.game.paramtables import decode_row
    assert decode_row("Magic", rows["Magic"][6230])["mp"] == 21

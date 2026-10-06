"""Game-folder hygiene helpers and anti-cheat process detection."""
import pytest

from eldendisk.game.processes import anticheat_processes
from eldendisk.vault import GameFolderGuard, cleanup_recorded


@pytest.fixture
def game(tmp_path):
    g = tmp_path / "Game"
    g.mkdir()
    (g / "eldenring.exe").write_bytes(b"EXE")
    return g


def test_guard_never_touches_existing_files_or_paths_outside(game):
    g = GameFolderGuard(game)
    with pytest.raises(FileExistsError):
        g.create_file("eldenring.exe", b"x")
    with pytest.raises(ValueError):
        g.create_file("../escape.txt", b"x")
    assert (game / "eldenring.exe").read_bytes() == b"EXE"
    (game.parent / "victim.txt").write_text("keep")
    assert cleanup_recorded(game, ["../victim.txt"]) == [] and (game.parent / "victim.txt").exists()


def test_guard_records_before_creating_and_cleans_up(game):
    seen = []
    g = GameFolderGuard(game, on_change=lambda files: seen.append(list(files)))
    g.create_file("steam_appid.txt", b"1")
    assert seen == [["steam_appid.txt"]] and (game / "steam_appid.txt").exists()
    assert g.cleanup() == ["steam_appid.txt"] and not (game / "steam_appid.txt").exists() and seen[-1] == []


def test_guard_diff_reports_changes(game):
    g = GameFolderGuard(game)
    g.take_listing()
    (game / "new.log").write_text("x")
    (game / "eldenring.exe").write_bytes(b"EXEEXE")
    assert g.diff() == ["added: new.log", "size changed: eldenring.exe"]


def test_anticheat_process_detection():
    assert anticheat_processes(["explorer.exe", "EasyAntiCheat_EOS.exe", "start_protected_game.exe"]) == \
        ["EasyAntiCheat_EOS.exe", "start_protected_game.exe"]
    assert anticheat_processes(["eldenring.exe", "steam.exe"]) == []

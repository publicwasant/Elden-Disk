"""`locate`: what it says when the game's module list cannot be read."""
import pytest

from eldendisk.game import attach
from eldendisk.game.attach import EXIT_EAC, AttachError


@pytest.fixture
def running(monkeypatch):
    monkeypatch.setattr(attach, "find_pid", lambda name: 4242)
    monkeypatch.setattr(attach, "list_modules", lambda pid: None)   # what the Toolhelp snapshot gives under EAC


def test_unreadable_modules_with_anticheat_processes_means_eac(running, monkeypatch, tmp_path):
    monkeypatch.setattr(attach, "list_process_names", lambda: ["steam.exe", "start_protected_game.exe", "eldenring.exe"])
    with pytest.raises(AttachError) as e:
        attach.locate(tmp_path / "offsets.json")
    assert e.value.code == EXIT_EAC and "EasyAntiCheat" in str(e.value) and "eldendisk run" in str(e.value)


def test_unreadable_modules_without_anticheat_is_a_plain_error(running, monkeypatch, tmp_path):
    monkeypatch.setattr(attach, "list_process_names", lambda: ["steam.exe", "eldenring.exe"])
    with pytest.raises(AttachError) as e:
        attach.locate(tmp_path / "offsets.json")
    assert e.value.code == 1 and "cannot list the modules" in str(e.value)

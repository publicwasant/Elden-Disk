"""Where the vault lives: --vault > remembered in the Registry > %LOCALAPPDATA%\\EldenDisk\\vault (never next to the exe)."""
import argparse
from pathlib import Path

import pytest

import eldendisk.commands.run as run_cmd
import eldendisk.commands.vault as vault_cmd
import eldendisk.vault.location as loc
from eldendisk.vault import VaultError, resolve_vault


@pytest.fixture
def registry(monkeypatch):
    box = {"v": None}
    monkeypatch.setattr(loc, "load_registry_vault_dir", lambda: box["v"])
    monkeypatch.setattr(loc, "save_registry_vault_dir", lambda p: box.__setitem__("v", p))
    return box


def test_default_is_under_localappdata_not_next_to_the_exe(monkeypatch, registry, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert resolve_vault(None) == tmp_path / "Local" / "EldenDisk" / "vault"


def test_explicit_wins_and_is_remembered_only_when_asked(registry, tmp_path):
    registry["v"] = str(tmp_path / "old")
    assert resolve_vault(str(tmp_path / "x")) == tmp_path / "x" and registry["v"] == str(tmp_path / "old")
    assert resolve_vault(str(tmp_path / "x"), remember=True) == tmp_path / "x" and registry["v"] == str(tmp_path / "x")


def test_the_remembered_vault_is_used_without_the_flag(registry, tmp_path):
    (tmp_path / "keep").mkdir()
    registry["v"] = str(tmp_path / "keep" / "vault")   # parent exists, vault itself not created yet
    assert resolve_vault(None) == tmp_path / "keep" / "vault"


def test_an_unavailable_remembered_vault_is_an_error_not_a_fresh_vault(registry, tmp_path):
    registry["v"] = str(tmp_path / "gone" / "drive" / "vault")
    with pytest.raises(VaultError, match="--vault"):
        resolve_vault(None)


def test_vault_commands_use_the_remembered_vault(registry, tmp_path):
    (tmp_path / "keep").mkdir()
    registry["v"] = str(tmp_path / "keep" / "v")
    assert vault_cmd._vault(argparse.Namespace(vault=None)).root == Path(registry["v"])


def test_run_remembers_an_explicit_vault(registry, tmp_path, monkeypatch):
    monkeypatch.setattr(run_cmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(run_cmd.launcher, "find_game_dir", lambda d: (_ for _ in ()).throw(FileNotFoundError("stop")))
    with pytest.raises(FileNotFoundError):   # the vault is resolved (and remembered) before the game is looked for
        run_cmd.cmd_run(argparse.Namespace(vault=str(tmp_path / "v"), game_dir=None))
    assert registry["v"] == str(tmp_path / "v")


def test_run_refuses_an_unavailable_remembered_vault(registry, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(run_cmd, "require_windows_x64", lambda: None)
    registry["v"] = str(tmp_path / "no" / "such" / "vault")
    assert run_cmd.cmd_run(argparse.Namespace(vault=None, game_dir=None)) == 1
    assert "--vault" in capsys.readouterr().err

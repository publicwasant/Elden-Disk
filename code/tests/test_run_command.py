"""Pieces of `run` around the host session: pruning after a finished session and the Steam Cloud note."""
import pytest

import eldendisk.commands.run as run_cmd
from eldendisk.vault import SaveVault


@pytest.fixture
def vault(tmp_path):
    live = tmp_path / "live" / "1"
    live.mkdir(parents=True)
    (live / "ER0000.sl2").write_bytes(b"save")
    v = SaveVault(tmp_path / "vault", sleep=lambda s: None)
    return v, live


def snaps(v):
    return [s["name"] for s in v.list_snapshots(verify=False)]


def test_auto_prune_keeps_the_newest_n(vault, capsys):
    v, live = vault
    for _ in range(4):
        v.snapshot(live)
    run_cmd.auto_prune(v, 2)
    assert len(snaps(v)) == 2 and "pruned 2" in capsys.readouterr().err


def test_auto_prune_zero_never_prunes(vault):
    v, live = vault
    for _ in range(3):
        v.snapshot(live)
    run_cmd.auto_prune(v, 0)
    assert len(snaps(v)) == 3


def test_auto_prune_never_touches_a_vault_that_owes_a_restore(vault):
    v, live = vault
    for _ in range(3):
        v.snapshot(live)
    v.write_session(v.new_record(v.snapshot(live), live, exe_sha256=None))
    run_cmd.auto_prune(v, 1)
    assert len(snaps(v)) == 4


def test_a_prune_failure_is_only_a_warning(vault, monkeypatch, capsys):
    v, live = vault
    v.snapshot(live); v.snapshot(live)
    monkeypatch.setattr(SaveVault, "prune", lambda self, keep: (_ for _ in ()).throw(OSError("locked")))
    run_cmd.auto_prune(v, 1)
    assert "could not prune" in capsys.readouterr().err

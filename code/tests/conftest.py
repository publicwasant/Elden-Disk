import pytest


@pytest.fixture(autouse=True)
def _no_registry(monkeypatch):
    """Tests never read or write the Windows Registry (HKCU\\Software\\EldenDisk)."""
    monkeypatch.setattr("eldendisk.save_vault.load_registry_save_dir", lambda: None)
    monkeypatch.setattr("eldendisk.save_vault.save_registry_save_dir", lambda p: None)

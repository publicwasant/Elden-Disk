import pytest


@pytest.fixture(autouse=True)
def _no_registry(monkeypatch):
    """Tests never read or write the Windows Registry (HKCU\\Software\\EldenDisk)."""
    monkeypatch.setattr("eldendisk.vault.saves.load_registry_save_dir", lambda: None)
    monkeypatch.setattr("eldendisk.vault.saves.save_registry_save_dir", lambda p: None)


@pytest.fixture(autouse=True)
def _no_vault_registry(monkeypatch):
    monkeypatch.setattr("eldendisk.vault.location.load_registry_vault_dir", lambda: None)
    monkeypatch.setattr("eldendisk.vault.location.save_registry_vault_dir", lambda p: None)


@pytest.fixture(autouse=True)
def _isolated_logbook(monkeypatch, tmp_path):
    """No test writes a log file outside tmp; events reach the console exactly as in the CLI (concise layout)."""
    from eldendisk import ui
    from eldendisk.logbook import book
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.chdir(tmp_path)   # relative --vault values in tests must not litter the source tree
    book.configure(console=ui.pretty_sink())
    yield
    book.configure()

"""The save vault: the only component that touches save files. Knows nothing about the game process or its memory."""
from .errors import VaultError
from .gamefolder import GameFolderGuard, cleanup_recorded, listing
from .location import default_vault_dir, resolve_vault
from .saves import check_live_dir, find_save_dir, save_registry_save_dir
from .session import SessionLog, SessionRecord, SessionState, authorise
from .vault import SaveVault, Snapshot, names_of, save_names, scan

__all__ = ["VaultError", "GameFolderGuard", "cleanup_recorded", "listing", "check_live_dir", "find_save_dir",
           "save_registry_save_dir", "SessionLog", "SessionRecord", "SessionState", "authorise", "SaveVault",
           "Snapshot", "scan", "names_of", "save_names", "default_vault_dir", "resolve_vault"]
from .recover import EXIT_RESTORE_PENDING, recover, restore_from_record

__all__ += ["EXIT_RESTORE_PENDING", "recover", "restore_from_record"]

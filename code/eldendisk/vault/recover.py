"""Restore of an owed session: one code path for the host (after the game exits) and for `vault restore`.

Order: archive what would be overwritten -> restore -> verify live == snapshot -> remove files created in the game folder
-> remove the session record. Any failure leaves the record (state RESTORE_PENDING) and the snapshot untouched.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from .errors import VaultError
from .gamefolder import cleanup_recorded
from .session import SessionLog, SessionRecord, SessionState
from .vault import SaveVault

EXIT_RESTORE_PENDING = 4


def restore_from_record(vault: SaveVault, record: SessionRecord, *, archive: bool, log: SessionLog) -> int:
    snap_dir, live = Path(record.snapshot_dir), Path(record.live_save_dir)

    def pending(why: str) -> int:
        log.e("vault", f"{why}. The session record stays; nothing was deleted from the vault")
        vault.update_session(state=SessionState.RESTORE_PENDING)
        return EXIT_RESTORE_PENDING

    try:
        files = vault.load_manifest(snap_dir)["files"]
        if archive and vault.verify_live(live, files):   # only a save that differs holds anything worth keeping
            log.ok("vault", f"modified save archived to {vault.archive_contaminated(live, snap_dir)}")
        vault.restore(snap_dir, live)
        log.d("vault", f"restored {snap_dir} -> {live}")
        problems = vault.verify_live(live, files)
    except (VaultError, OSError) as exc:
        return pending(f"restore failed: {exc}")
    if problems:
        return pending("verification failed: " + "; ".join(problems[:3]))
    log.ok("vault", "save restored, byte-identical to the snapshot")
    if record.game_dir and record.game_folder_files_created:
        removed = cleanup_recorded(Path(record.game_dir), record.game_folder_files_created)
        log.ok("vault", f"removed from game folder: {', '.join(removed) or 'nothing'}")
    vault.clear_session()
    return 0


def keep_from_record(vault: SaveVault, record: SessionRecord, *, log: SessionLog) -> int:
    """`vault keep`: accept the CURRENT save as the new baseline instead of restoring the pre-session one.

    The current save is snapshotted and verified first (suffix `-kept`), the pre-session snapshot stays in the vault,
    and only then is the record removed. Any failure leaves the record untouched.
    """
    live = Path(record.live_save_dir)
    try:
        kept = vault.snapshot(live, suffix="-kept")
    except (VaultError, OSError) as exc:
        log.e("vault", f"could not back up the current save, nothing changed: {exc}")
        return 1
    log.attach(kept.dir / "session.log")
    log.ok("vault", f"current save kept as the new baseline: {kept.dir.name} ({len(kept.files)} file{"" if len(kept.files) == 1 else "s"} verified)")
    log.i("vault", f"the pre-session snapshot {Path(record.snapshot_dir).name} stays in the vault")
    if record.game_dir and record.game_folder_files_created:
        removed = cleanup_recorded(Path(record.game_dir), record.game_folder_files_created)
        log.ok("vault", f"removed from game folder: {', '.join(removed) or 'nothing'}")
    vault.clear_session()
    return 0


def recover(vault: SaveVault, *, game_running: Callable[[], bool], archive: bool = True,
            log: SessionLog | None = None) -> int:
    """`vault restore` for an unresolved session. Idempotent: no record means nothing to do."""
    log = log or SessionLog()
    try:
        record = vault.read_session()
    except VaultError as exc:
        log.e("vault", str(exc))
        return 1
    if record is None:
        log.i("vault", "nothing to restore: no unresolved session")
        return 0
    if game_running():
        log.e("vault", "eldenring.exe is running; close it before restoring")
        return 1
    snap_dir = Path(record.snapshot_dir)
    if snap_dir.is_dir():
        log.attach(snap_dir / "session.log")
    log.i("vault", f"restoring {snap_dir.name} to {record.live_save_dir}")
    return restore_from_record(vault, record, archive=archive, log=log)

"""Sandbox session: the lifecycle of spec 1.6.0 section 8. Orchestration only; it never touches files or memory itself.

  IDLE -> PREFLIGHT -> SNAPSHOTTING -> RUNNING -> RESTORING -> VERIFYING -> CLEANUP -> IDLE
                                          \\____ any failure after the marker is written -> RESTORE_PENDING (marker stays)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from .game_launcher import GameFolderGuard, cleanup_recorded
from .memory_writer import WriteGate
from .save_vault import SaveVault, SessionLog, VaultError

EXIT_RESTORE_PENDING = 4

CLOUD_WARNING = ("Steam Cloud: this tool cannot read the setting. Until you have tested it (spec section 9, SC-1), "
                 "turn Steam Cloud OFF for Elden Ring while using the sandbox, or a contaminated save may be synced.")


class State(str, Enum):
    IDLE = "IDLE"
    PREFLIGHT = "PREFLIGHT"
    SNAPSHOTTING = "SNAPSHOTTING"
    RUNNING = "RUNNING"
    RESTORING = "RESTORING"
    VERIFYING = "VERIFYING"
    CLEANUP = "CLEANUP"
    RESTORE_PENDING = "RESTORE_PENDING"


@dataclass
class Hooks:
    game_running: Callable[[], bool]
    anticheat_running: Callable[[], bool]
    run_game: Callable[[WriteGate], int]          # blocks through the RUNNING phase, returns an exit code
    wait_game_exit: Callable[[], bool]            # blocks until no game process exists; True when gone
    extra_preflight: Callable[[], list[str]] = lambda: []
    game_guard: GameFolderGuard | None = None
    game_dir: Path | None = None
    exe_sha256: str | None = None


class SandboxSession:
    def __init__(self, vault: SaveVault, live_dir: Path, hooks: Hooks, *,
                 archive_contaminated: bool = False, log: SessionLog | None = None):
        self.vault, self.live, self.hooks = vault, Path(live_dir), hooks
        self.archive = archive_contaminated
        self.log = log or SessionLog()
        self.gate = WriteGate()
        self.state = State.IDLE
        self.history: list[State] = [State.IDLE]

    def _to(self, state: State) -> None:
        self.state = state
        self.history.append(state)
        self.log.write(f"state -> {state.value}")

    # ---- FR-1 / FR-2 ----
    def preflight(self) -> list[str]:
        problems = self.vault.preflight(self.live)
        if self.hooks.game_running():
            problems.append("eldenring.exe is already running; close it first")
        if self.hooks.anticheat_running():
            problems.append("anti-cheat processes are running; the sandbox is offline-only")
        problems += self.hooks.extra_preflight()
        return problems

    def run(self) -> int:
        self._to(State.PREFLIGHT)
        problems = self.preflight()
        if problems:
            for p in problems:
                self.log.write(f"preflight refused: {p} ✖️")
            self._to(State.IDLE)
            return 1
        self.log.write(CLOUD_WARNING)

        self._to(State.SNAPSHOTTING)
        try:
            snap = self.vault.snapshot(self.live)
        except (VaultError, OSError) as exc:
            self.log.write(f"snapshot failed, nothing changed: {exc} ✖️")
            self._to(State.IDLE)
            return 1
        self.log.attach(snap.dir / "session.log")
        self.log.write(f"[vault] backup save {self.live} (steamID: {self.live.name}) to {snap.dir} ✓")
        self.log.write(f"snapshot {snap.dir.name}: {len(snap.files)} file(s) verified ✓")
        guard = self.hooks.game_guard
        if guard is not None:
            guard.take_listing()
        try:  # the marker is written BEFORE the game is launched, AFTER the snapshot is verified
            self.vault.write_marker(snap, self.live, exe_sha256=self.hooks.exe_sha256, game_dir=self.hooks.game_dir)
        except OSError as exc:
            self.log.write(f"could not write the marker, discarding snapshot: {exc} ✖️")
            import shutil
            shutil.rmtree(snap.dir, ignore_errors=True)
            self._to(State.IDLE)
            return 1
        if guard is not None:
            guard._on_change = self.vault.set_game_files

        self._to(State.RUNNING)
        self.gate.open()
        code = 1
        try:
            code = self.hooks.run_game(self.gate)
        except KeyboardInterrupt:
            self.log.write("interrupted; waiting for the game to exit before restoring")
            code = 130
        except Exception as exc:  # restore must still run
            self.log.write(f"error while running: {exc!r} ✖️")
            code = 1
        finally:
            self.gate.close("session ended")
        return self._finish(snap, code)

    def _pending(self, why: str) -> int:
        self.log.write(f"{why} ✖️. The marker stays; the live save is NOT trusted. Close the game and run `sandbox restore`.")
        self._to(State.RESTORE_PENDING)
        return EXIT_RESTORE_PENDING

    def _finish(self, snap, code: int) -> int:
        try:
            gone = self.hooks.wait_game_exit()
        except KeyboardInterrupt:
            return self._pending("restore postponed (second interrupt)")
        if not gone:
            return self._pending("the game is still running")

        self._to(State.RESTORING)
        try:
            if self.archive:
                self.log.write(f"contaminated save archived to {self.vault.archive_contaminated(self.live, snap.dir)} ✓")
            self.vault.restore(snap.dir, self.live)
            self.log.write(f"[vault] restored save from {snap.dir} to {self.live} ✓")
        except (VaultError, OSError) as exc:
            return self._pending(f"restore failed: {exc}")

        self._to(State.VERIFYING)
        problems = self.vault.verify_live(self.live, snap.files)
        if problems:
            return self._pending("verification failed: " + "; ".join(problems[:3]))
        self.log.write("[vault] verification passed: restore verified; save folder is byte-identical to snapshot ✓")

        self._to(State.CLEANUP)
        guard = self.hooks.game_guard
        if guard is not None:
            removed = guard.cleanup()
            if removed:
                self.log.write(f"removed from game folder: {', '.join(removed)} ✓")
            for d in guard.diff():
                self.log.write(f"warning, game folder differs from before the session: {d}")
        self.vault.clear_marker()
        self._to(State.IDLE)
        return code


def restore_pending(vault: SaveVault, *, game_running: Callable[[], bool], archive: bool = False,
                    log: SessionLog | None = None) -> int:
    """`sandbox restore` for an unresolved session (FR-9, FR-10). Idempotent: no marker means nothing to do."""
    log = log or SessionLog()
    try:
        marker = vault.read_marker()
    except VaultError as exc:
        log.write(f"{exc} ✖️")
        return 1
    if marker is None:
        log.write("nothing to restore: no unresolved session")
        return 0
    if game_running():
        log.write("eldenring.exe is running; close it before restoring ✖️")
        return 1
    snap_dir, live = Path(marker["snapshot_dir"]), Path(marker["live_save_dir"])
    log.attach(snap_dir / "session.log") if snap_dir.is_dir() else None
    log.write(f"[vault] restoring {live} (steamID: {live.name}) from {snap_dir.name}")
    try:
        if archive:
            log.write(f"contaminated save archived to {vault.archive_contaminated(live, snap_dir)} ✓")
        vault.restore(snap_dir, live)
        log.write(f"[vault] restored save from {snap_dir} to {live} ✓")
        problems = vault.verify_live(live, vault.load_manifest(snap_dir)["files"])
    except (VaultError, OSError) as exc:
        log.write(f"restore failed: {exc} ✖️. The marker stays; nothing was deleted from the vault.")
        return EXIT_RESTORE_PENDING
    if problems:
        log.write("verification failed: " + "; ".join(problems[:3]) + " ✖️. The marker stays.")
        return EXIT_RESTORE_PENDING
    if marker.get("game_dir") and marker.get("game_folder_files_created"):
        removed = cleanup_recorded(Path(marker["game_dir"]), marker["game_folder_files_created"])
        log.write(f"removed from game folder: {', '.join(removed) or 'nothing'} ✓")
    vault.clear_marker()
    log.write("[vault] verification passed: restore verified; marker removed ✓")
    return 0

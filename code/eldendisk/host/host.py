"""The host session: spec 1.6.2 section 4. Orchestration only; it never touches memory (I2) and never touches files
itself: every file operation goes through the vault.

  H1 preflight -> H2 snapshot+verify -> H3 record READY -> H4 launch -> H5 record RUNNING -> H6 wait for exit
  -> H7 record RESTORING + restore -> H8 verify -> H9 cleanup + record removed

Since 1.6.4 (1.7.0: the file comes from the caller, `Hooks.regulation_world`), when there is a file to swap in, H2 also backs up the game's own regulation.bin and H3b (after
the record, before the launch) swaps the user's file in; H7 puts the original back with the save. The host only calls the vault.

Invariant I1: at every instant either live save == snapshot and there is no record, or a record exists whose snapshot
is verified. Any failure after H3 ends in the restore path, or leaves the record as RESTORE_PENDING.
"""
from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from . import interrupts
from ..vault import (EXIT_RESTORE_PENDING, GameFolderGuard, SaveVault, SessionLog, SessionState, VaultError,
                     restore_from_record)


class State(str, Enum):
    IDLE = "IDLE"
    PREFLIGHT = "PREFLIGHT"
    SNAPSHOTTING = "SNAPSHOTTING"
    READY = "READY"
    RUNNING = "RUNNING"
    RESTORING = "RESTORING"
    RESTORE_PENDING = "RESTORE_PENDING"


@dataclass
class Hooks:
    find_game_pid: Callable[[], int | None]        # pid of eldenring.exe, None when it is not running
    process_started: Callable[[int], int | None]   # start time of a pid (limited query access only)
    anticheat_running: Callable[[], bool]
    launch: Callable[[], None]                     # start the game offline (returns at once)
    exe_sha256: str | None = None
    game_dir: Path | None = None
    game_guard: GameFolderGuard | None = None
    regulation_world: Path | None = None           # 1.7.0: the regulation.bin to swap in for this session (named by the caller)
    extra_preflight: Callable[[], list[str]] = lambda: []
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    launch_timeout: float = 120.0                  # seconds to wait for the game process to appear
    exit_settle: float = 1.0                       # let the game release its save files before the restore
    poll: float = 0.5
    install_close_handler: Callable[[Callable[[], None]], Callable[[], None]] = interrupts.install


class _Postpone(Exception):
    """Second Ctrl+C while waiting for the game: stop waiting, leave the restore owed."""


class _Stop(Exception):
    """Ctrl+C in a session without a vault: nothing is owed, so stop waiting at once."""


class Session:
    def __init__(self, vault: SaveVault, live_dir: Path, hooks: Hooks, *, archive_contaminated: bool = True,
                 log: SessionLog | None = None, pid: int | None = None, protect: bool = True):
        """`protect` False = vault OFF: the game is launched offline and watched, the save is neither backed up nor
        restored, there is no session record (so `write` is never allowed). An owed restore still blocks it."""
        self.vault, self.live, self.hooks = vault, Path(live_dir), hooks
        self.protect = protect
        self.archive = archive_contaminated
        self.log = log or SessionLog()
        self.pid = os.getpid() if pid is None else pid
        self.state = State.IDLE
        self.history: list[State] = [State.IDLE]
        self._interrupts = 0

    def _to(self, state: State) -> None:
        self.state = state
        self.history.append(state)
        self.log.d("host", f"state {state.value}")

    # ---- H1 ----
    def preflight(self) -> list[str]:
        problems = self.vault.preflight(self.live) if self.protect else []
        if self.hooks.find_game_pid() is not None:
            problems.append("eldenring.exe is already running; close it first")
        if self.hooks.anticheat_running():
            problems.append("anti-cheat processes are running; the host is offline-only")
        if self.protect and self.hooks.process_started(self.pid) is None:
            problems.append("cannot read this process's start time, so `write` could never be authorised")
        if self.protect and self.hooks.game_dir is not None:
            problems += self.vault.regulation_problems(self.hooks.game_dir, self.hooks.regulation_world)
        problems += self.hooks.extra_preflight()
        return problems

    def run(self) -> int:
        self._to(State.PREFLIGHT)
        self.log.d("vault", f"status {'ON' if self.protect else 'OFF'}")
        try:
            owed = self.vault.read_session()
        except VaultError as exc:
            self.log.e("host", str(exc))
            self._to(State.IDLE)
            return EXIT_RESTORE_PENDING
        if owed is not None:
            self.log.e("host", "an unresolved session exists, so the live save is NOT trusted")
            self.log.i("host", f"close the game, then run `{self.vault.restore_hint()}`")
            self._to(State.IDLE)
            return EXIT_RESTORE_PENDING
        problems = self.preflight()
        if problems:
            for p in problems:
                self.log.e("host", f"cannot start: {p}")
            self._to(State.IDLE)
            return 1

        if not self.protect:
            return self._unprotected()
        remove_handler = self.hooks.install_close_handler(self._on_console_close)
        try:
            snap, code = self._prepare()
            return code if snap is None else self._session()
        finally:
            remove_handler()

    def _unprotected(self) -> int:
        """Vault OFF: launch, wait for the game, leave the save alone. Nothing is owed afterwards."""
        self.log.w("vault", "vault OFF: the save is not backed up and will not be restored; `write` is not allowed")
        code = 0
        try:
            code = self._launch_and_wait()
        except _Stop:
            self.log.w("host", "Ctrl+C: stopped waiting; the game keeps running (vault off: nothing to restore)")
            self._to(State.IDLE)
            return 130
        except Exception as exc:
            self.log.e("host", f"error while running: {exc!r}")
            code = 1
        self.log.i("vault", "vault OFF: the save was left as the game wrote it")
        self._to(State.IDLE)
        return code

    # ---- H2, H3 ----
    def _discard(self, snap) -> None:
        """Remove a snapshot nobody owes a restore for. Its session.log goes with it, so the log must stop writing there."""
        self.log.detach()
        shutil.rmtree(snap.dir, ignore_errors=True)

    def _prepare(self):
        """(snapshot, 0) when the session may start, else (None, exit code)."""
        self._to(State.SNAPSHOTTING)
        try:
            snap = self.vault.snapshot(self.live)
        except KeyboardInterrupt:
            self.log.w("host", "interrupted while taking the snapshot; nothing changed")
            self._to(State.IDLE)
            return None, 130
        except (VaultError, OSError) as exc:
            self.log.e("vault", f"snapshot failed, nothing changed: {exc}")
            self._to(State.IDLE)
            return None, 1
        self.log.attach(snap.dir / "session.log")
        self.log.d("vault", f"backup {self.live} (steamID {self.live.name}) -> {snap.dir}")
        self.log.ok("vault", f"snapshot {snap.dir.name}, {len(snap.files)} file{"" if len(snap.files) == 1 else "s"} verified")
        try:   # nothing in the game folder changes here: the game's own regulation.bin is only copied into the snapshot
            reg = self.vault.backup_regulation(snap, self.hooks.game_dir, self.hooks.regulation_world) if self.hooks.game_dir is not None else None
        except KeyboardInterrupt:
            self.log.w("host", "interrupted while backing up regulation.bin; nothing changed")
            self._discard(snap)
            self._to(State.IDLE)
            return None, 130
        except (VaultError, OSError) as exc:
            self.log.e("vault", f"could not back up regulation.bin, discarding the snapshot: {exc}")
            self._discard(snap)
            self._to(State.IDLE)
            return None, 1
        if reg:
            self.log.ok("vault", f"game's regulation.bin backed up to {snap.dir.name}/bin (sha256 {reg['original_sha256'][:12]})")
        guard = self.hooks.game_guard
        if guard is not None:
            guard.take_listing()
        try:   # the record is written BEFORE the game is launched and AFTER the snapshot is verified
            self.vault.write_session(self.vault.new_record(
                snap, self.live, exe_sha256=self.hooks.exe_sha256, game_dir=self.hooks.game_dir,
                host_pid=self.pid, host_started=self.hooks.process_started(self.pid), regulation=reg))
        except KeyboardInterrupt:
            self.log.w("host", "interrupted before the session started; nothing changed")
            self._to(State.IDLE)
            return None, 130
        except OSError as exc:
            self.log.e("vault", f"could not write the session record, discarding the snapshot: {exc}")
            self._discard(snap)
            self._to(State.IDLE)
            return None, 1
        if guard is not None:
            guard._on_change = lambda files: self.vault.update_session(game_folder_files_created=list(files))
        self._to(State.READY)
        if reg:   # H3b: the record exists, so every way out of here ends in the restore
            try:
                self.vault.install_regulation(reg)
            except (VaultError, OSError, KeyboardInterrupt) as exc:
                interrupted = isinstance(exc, KeyboardInterrupt)
                self.log.e("vault", "interrupted while swapping regulation.bin" if interrupted
                           else f"could not swap regulation.bin: {exc}")
                return None, self._restore(130 if interrupted else 1)
            self.log.ok("vault", f"regulation.bin: your file replaces the game's for this session (sha256 {reg['world_sha256'][:12]})")
        return snap, 0

    # ---- H4 .. H9 ----
    def _session(self) -> int:
        code = 0
        try:
            code = self._launch_and_wait()
        except _Postpone:
            return self._pending("restore postponed (second interrupt)")
        except Exception as exc:   # the restore must still run
            self.log.e("host", f"error while running: {exc!r}")
            code = 1
        return self._restore(code)

    def _launch_and_wait(self) -> int:
        """H4..H6. Ctrl+C is absorbed once (the game keeps running); the second one raises _Postpone."""
        h = self.hooks
        launched, pid, code = False, None, 0
        deadline = h.clock() + h.launch_timeout
        while True:
            try:
                if not launched:
                    launched = True   # never launch twice, even if interrupted inside launch()
                    self.log.i("game", "launching eldenring.exe offline")
                    h.launch()
                cur = h.find_game_pid()
                if cur is None:
                    if pid is not None:
                        self.log.i("game", "exited")
                        break   # the game exited
                    if h.clock() > deadline:
                        self.log.e("host", f"eldenring.exe did not start within {h.launch_timeout:g} s; ending the session")
                        code = 1
                        break
                elif cur != pid:
                    pid = cur
                    if self.protect:
                        self.vault.update_session(state=SessionState.RUNNING, game_pid=cur,
                                                  game_started=h.process_started(cur))
                        self.log.ok("game", f"running, pid {cur}; `write` is now allowed")
                    else:
                        self.log.ok("game", f"running, pid {cur}; `write` is not allowed")
                    self._to(State.RUNNING)   # from here `write` may edit; the record is what authorises it
                h.sleep(h.poll)
            except KeyboardInterrupt:
                self._absorb_interrupt()
        while True:   # let the game release its save files (A3)
            try:
                h.sleep(h.exit_settle)
                return code
            except KeyboardInterrupt:
                self._absorb_interrupt()

    def _absorb_interrupt(self) -> None:
        if not self.protect:
            raise _Stop()
        self._interrupts += 1
        if self._interrupts >= 2:
            raise _Postpone()
        self.log.w("host", "Ctrl+C: the game keeps running; the save is restored when it exits "
                           "(press again to postpone the restore)")

    def _pending(self, why: str) -> int:
        self.log.e("host", f"{why}. The live save is NOT trusted")
        self.log.i("host", f"close the game, then run `{self.vault.restore_hint()}`")
        self.vault.update_session(state=SessionState.RESTORE_PENDING)
        self._to(State.RESTORE_PENDING)
        return EXIT_RESTORE_PENDING

    def _restore(self, code: int) -> int:
        self._to(State.RESTORING)
        try:
            self.vault.update_session(state=SessionState.RESTORING)
            record = self.vault.read_session()
            if record is None:
                self.log.e("host", "the session record disappeared; nothing was restored")
                self._to(State.IDLE)
                return 1
            rc = restore_from_record(self.vault, record, archive=self.archive, log=self.log)
        except KeyboardInterrupt:
            return self._pending("restore interrupted")
        except (VaultError, OSError) as exc:
            return self._pending(f"restore failed: {exc}")
        if rc != 0:
            self._to(State.RESTORE_PENDING)
            return rc
        guard = self.hooks.game_guard
        if guard is not None:
            for d in guard.diff():
                self.log.w("host", f"game folder changed during the session: {d}")
        self._to(State.IDLE)
        return code

    def _on_console_close(self) -> None:
        """Console window closed / logoff / shutdown (separate thread, a few seconds to live)."""
        self.vault.update_session(state=SessionState.RESTORE_PENDING)

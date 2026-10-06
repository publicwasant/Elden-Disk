"""The session record (`session.json`) and the session log.

One record lives in the vault exactly while a restore is owed. It says which game process the host started and in
which state the session is; the writer reads it before every write (spec 1.6.2, section 3). No game or memory code here:
process identity is passed in as plain values and a `started_of(pid)` callable.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable

from .errors import VaultError

SESSION_NAME = "session.json"
LEGACY_MARKER_NAME = "PENDING_RESTORE.json"   # 1.6.0 / 1.6.1 marker (version 1), read as RESTORE_PENDING
RECORD_VERSION = 2
_LOCK = threading.RLock()   # the console-close handler runs in another thread and updates the record


class SessionState(str, Enum):
    READY = "READY"                      # snapshot verified, game not started yet
    RUNNING = "RUNNING"                  # game started; `write` may edit
    RESTORING = "RESTORING"
    RESTORE_PENDING = "RESTORE_PENDING"  # something interrupted the session; `vault restore` is owed


@dataclass
class SessionRecord:
    state: SessionState
    snapshot_dir: str
    live_save_dir: str
    hashes: dict
    created: str
    snapshot_verified: bool = False
    exe_sha256: str | None = None
    game_dir: str | None = None
    game_folder_files_created: list = field(default_factory=list)
    host_pid: int | None = None
    host_started: int | None = None
    game_pid: int | None = None
    game_started: int | None = None
    version: int = RECORD_VERSION

    def to_json(self) -> dict:
        d = asdict(self)
        d["state"] = self.state.value
        return d

    @classmethod
    def from_json(cls, d: dict) -> "SessionRecord":
        if d.get("version") == 1:   # marker of 1.6.0 / 1.6.1: the snapshot was verified before it was written
            return cls(SessionState.RESTORE_PENDING, d["snapshot_dir"], d["live_save_dir"], d["hashes"],
                       d.get("created", ""), True, d.get("exe_sha256"), d.get("game_dir"),
                       list(d.get("game_folder_files_created") or []), version=1)
        if d.get("version") != RECORD_VERSION:
            raise ValueError(f"unknown record version {d.get('version')!r}")
        fields = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        fields["state"] = SessionState(fields["state"])
        return cls(**fields)


def atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _paths(root: Path) -> tuple[Path, Path]:
    return Path(root) / SESSION_NAME, Path(root) / LEGACY_MARKER_NAME


def load(root: Path) -> SessionRecord | None:
    """The record, None when no restore is owed, VaultError when a record exists but cannot be trusted."""
    for path in _paths(root):
        if not path.exists():
            continue
        try:
            return SessionRecord.from_json(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise VaultError(f"{path} exists but is unreadable ({exc}); the live save cannot be trusted. "
                             f"Do not delete it; restore from the newest snapshot in {Path(root)}") from exc
    return None


def store(root: Path, record: SessionRecord) -> None:
    with _LOCK:
        Path(root).mkdir(parents=True, exist_ok=True)
        atomic_write_json(_paths(root)[0], record.to_json())
        _paths(root)[1].unlink(missing_ok=True)   # a v1 marker is superseded by the v2 record


def update(root: Path, **changes) -> SessionRecord | None:
    """Change fields of the existing record; None (and nothing written) when there is none."""
    with _LOCK:   # read-modify-write is atomic against clear() and other updates in this process
        record = load(root)
        if record is None:
            return None
        for k, v in changes.items():
            setattr(record, k, v)
        store(root, record)
        return record


def clear(root: Path) -> None:
    with _LOCK:
        for path in _paths(root):
            path.unlink(missing_ok=True)


def authorise(record: SessionRecord | None, *, game_pid: int | None, game_started: int | None,
              exe_sha256: str | None, started_of: Callable[[int], int | None]) -> list[str]:
    """Reasons the writer must refuse; an empty list means writing is allowed (spec 1.6.2, section 3)."""
    if record is None:
        return ["no active session: start the game with `eldendisk run` (same --vault)"]
    problems = []
    if record.state != SessionState.RUNNING:
        problems.append(f"the session is {record.state.value}, not RUNNING")
    if not record.snapshot_verified:
        problems.append("the session snapshot is not verified")
    if game_pid is None or record.game_pid != game_pid or record.game_started is None or record.game_started != game_started:
        problems.append("the running eldenring.exe is not the game `run` started")
    if not record.exe_sha256 or record.exe_sha256 != exe_sha256:
        problems.append("the running eldenring.exe is not the one the session snapshot was taken for")
    if not host_alive(record, started_of):
        problems.append("the host (`eldendisk run`) is no longer running, so nothing would restore the save")
    return problems


def host_alive(record: SessionRecord, started_of: Callable[[int], int | None]) -> bool:
    """True while the process that wrote the record (pid and start time) still runs."""
    return record.host_pid is not None and record.host_started is not None and started_of(record.host_pid) == record.host_started


class SessionLog:
    """Event log of one session. Every event goes to `session.log` in the snapshot directory (buffered until that
    directory exists) and to `emit(level, tag, msg, ok)`, which the command wires to the tool's logbook. The vault and
    the host stay independent of the console this way.
    """

    def __init__(self, emit: Callable[..., None] | None = None):
        self.path: Path | None = None
        self._buffer: list[str] = []
        self._emit = emit

    def attach(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._flush()

    def write(self, msg: str, *, level: str = "I", tag: str = "host", ok: bool = False) -> None:
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        for line in str(msg).splitlines() or [""]:
            self._buffer.append(f"{stamp} {level} {tag:<6}: {line}")
        if self.path is not None:
            self._flush()
        if self._emit:
            self._emit(level, tag, msg, ok=ok)

    def d(self, tag: str, msg: str) -> None: self.write(msg, level="D", tag=tag)
    def i(self, tag: str, msg: str) -> None: self.write(msg, level="I", tag=tag)
    def ok(self, tag: str, msg: str) -> None: self.write(msg, level="I", tag=tag, ok=True)
    def w(self, tag: str, msg: str) -> None: self.write(msg, level="W", tag=tag)
    def e(self, tag: str, msg: str) -> None: self.write(msg, level="E", tag=tag)

    def _flush(self) -> None:
        if self.path is not None and self._buffer:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write("\n".join(self._buffer) + "\n")
            self._buffer = []

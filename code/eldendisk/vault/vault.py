"""SaveVault: snapshot / restore / verify of the live save folder (spec 1.6.2, sections 3-4) and, since 1.6.4, the swap
of the game's `regulation.bin` (spec 1.6.4).

Pure filesystem. It knows nothing about the game process and is the only component that touches save files and the one
game file the tool may replace. The one guarantee: after a verified restore the live save folder is byte-identical to the
snapshot taken before, and the game folder holds its own `regulation.bin` again.

Ordering: snapshot complete + hash-verified -> session record written -> ... -> verified restore -> record removed.
"""
from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import session as sess
from .errors import VaultError
from .saves import check_live_dir
from .session import SessionRecord, SessionState, atomic_write_json

MANIFEST_NAME = "manifest.json"
SAVE_SUBDIR = "save"
BIN_SUBDIR = "bin"                    # <snapshot>/bin/regulation.bin: the game's own file, kept to put it back
REGULATION_DIR = "regulation"         # <vault>/regulation/regulation.bin: the folder 1.6.4 read the swap file from; ignored since 1.7.0
REGULATION_NAME = "regulation.bin"
CONTAMINATED_SUBDIR = "contaminated"
TMP_SUFFIX = ".eldendisk-tmp"
SPACE_FACTOR = 3                      # free space >= 3x the save folder
RESTORE_TIMEOUT_S = 30.0              # bounded retry on file locks
SNAPSHOT_NAME = re.compile(r"^\d{8}-\d{6}(-\d+)?(-pre-restore|-kept)?$")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan(root: Path) -> dict[str, dict]:
    """{relative posix path: {sha256, size, mtime_ns}} for every file under root."""
    out: dict[str, dict] = {}
    root = Path(root)
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            p = Path(dirpath) / name
            st = p.stat()
            out[p.relative_to(root).as_posix()] = {"sha256": sha256_of(p), "size": st.st_size, "mtime_ns": st.st_mtime_ns}
    return out


def dir_size(root: Path) -> int:
    return sum(Path(dp, f).stat().st_size for dp, _d, fs in os.walk(root) for f in fs)


@dataclass
class Snapshot:
    dir: Path
    files: dict[str, dict]

    @property
    def save_dir(self) -> Path:
        return self.dir / SAVE_SUBDIR

    @property
    def bin_dir(self) -> Path:
        return self.dir / BIN_SUBDIR


class SaveVault:
    def __init__(self, root: Path, *, timeout: float = RESTORE_TIMEOUT_S,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic):
        self.root = Path(root)
        self._timeout, self._sleep, self._clock = timeout, sleep, clock

    # ---------------- session record (see session.py) ----------------
    def read_session(self) -> SessionRecord | None:
        return sess.load(self.root)

    def write_session(self, record: SessionRecord) -> None:
        sess.store(self.root, record)

    def update_session(self, **changes) -> SessionRecord | None:
        return sess.update(self.root, **changes)

    def clear_session(self) -> None:
        sess.clear(self.root)

    def new_record(self, snap: Snapshot, live_dir: Path, *, exe_sha256: str | None, game_dir: Path | None = None,
                   host_pid: int | None = None, host_started: int | None = None,
                   regulation: dict | None = None) -> SessionRecord:
        """The READY record of a snapshot that has just been verified."""
        return SessionRecord(
            state=SessionState.READY, snapshot_dir=str(snap.dir), live_save_dir=str(live_dir),
            hashes={rel: info["sha256"] for rel, info in snap.files.items()},
            created=datetime.now().astimezone().isoformat(timespec="seconds"),
            snapshot_verified=True, exe_sha256=exe_sha256, game_dir=str(game_dir) if game_dir else None,
            host_pid=host_pid, host_started=host_started, regulation=regulation)

    # ---------------- the game's regulation.bin (spec 1.6.4; since 1.7.0 the caller names the file to swap in) ----------------
    def legacy_world(self) -> Path | None:
        """`<vault>/regulation/regulation.bin`, where 1.6.4 looked for the swap file. Not read any more; only reported."""
        p = self.root / REGULATION_DIR / REGULATION_NAME
        return p if p.is_file() else None

    @staticmethod
    def world_info(world: Path | None) -> dict | None:
        if world is None:
            return None
        return {"path": str(world), "size": Path(world).stat().st_size, "sha256": sha256_of(Path(world))}

    @staticmethod
    def regulation_problems(game_dir: Path, world: Path | None) -> list[str]:
        """What stops a swap before anything is touched (empty when there is no file to swap in)."""
        if world is None:
            return []
        world = Path(world)
        problems = []
        if not world.is_file():
            problems.append(f"{world} not found")
        elif world.stat().st_size == 0:
            problems.append(f"{world} is empty")
        if not (Path(game_dir) / REGULATION_NAME).is_file():
            problems.append(f"{Path(game_dir) / REGULATION_NAME} not found, so there is nothing to back up before the swap")
        return problems

    def backup_regulation(self, snap: Snapshot, game_dir: Path, world: Path | None) -> dict | None:
        """Copy the game's own regulation.bin to `<snapshot>/bin/`, verify the copy and note both hashes in the manifest.

        Returns what the session record needs, or None when there is no file to swap in. The game folder is not touched.
        """
        if world is None:
            return None
        world = Path(world)
        game_file = Path(game_dir) / REGULATION_NAME
        original = sha256_of(game_file)
        dst = snap.bin_dir / REGULATION_NAME
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(game_file, dst)
        if sha256_of(dst) != original or sha256_of(game_file) != original:
            raise VaultError("the backup of regulation.bin does not match the game's file, or the file changed while it was copied")
        info = {"game_file": str(game_file), "world_file": str(world), "original_sha256": original,
                "world_sha256": sha256_of(world)}
        manifest = self.load_manifest(snap.dir)
        manifest["regulation"] = {"original_sha256": original, "world_sha256": info["world_sha256"]}
        atomic_write_json(snap.dir / MANIFEST_NAME, manifest)
        return info

    def install_regulation(self, info: dict) -> None:
        """Replace the game's regulation.bin with the user's file. Only after the session record holds `info`."""
        world, game_file = Path(info["world_file"]), Path(info["game_file"])
        if not world.is_file() or sha256_of(world) != info["world_sha256"]:
            raise VaultError(f"{world} changed while the session was being prepared; nothing was swapped")
        tmp = game_file.with_name(game_file.name + TMP_SUFFIX)

        def _swap():
            tmp.unlink(missing_ok=True)
            shutil.copy2(world, tmp)
            os.replace(tmp, game_file)

        self._retry(_swap, f"swap {REGULATION_NAME}")
        if sha256_of(game_file) != info["world_sha256"]:
            raise VaultError(f"{REGULATION_NAME} in the game folder does not match your file after the swap")

    def restore_regulation(self, record: SessionRecord) -> bool:
        """Give the game folder its own regulation.bin back and verify it. True when a file was put back; False when
        the record has no swap or the game folder already holds the original (idempotent, also after a crash)."""
        info = record.regulation
        if not info:
            return False
        game_file = Path(info["game_file"])
        backup = Path(record.snapshot_dir) / BIN_SUBDIR / REGULATION_NAME
        tmp = game_file.with_name(game_file.name + TMP_SUFFIX)
        tmp.unlink(missing_ok=True)   # left by an interrupted swap or restore
        if game_file.is_file() and sha256_of(game_file) == info["original_sha256"]:
            return False   # the record's hash is the truth: also when the backup is gone and the user put the file back
        if not backup.is_file() or sha256_of(backup) != info["original_sha256"]:
            raise VaultError(f"the backup {backup} is missing or damaged; {REGULATION_NAME} was not touched")

        def _put():
            shutil.copy2(backup, tmp)
            os.replace(tmp, game_file)

        self._retry(_put, f"restore {REGULATION_NAME}")
        if sha256_of(game_file) != info["original_sha256"]:
            raise VaultError(f"{REGULATION_NAME} in the game folder does not match the backup after the restore")
        return True

    # ---------------- preflight (FR-1, vault part) ----------------
    def restore_hint(self) -> str:
        """The exact command that finishes an owed restore of THIS vault (the path matters when it is not the default)."""
        return f'eldendisk vault restore --vault "{self.root}"'

    def preflight(self, live_dir: Path) -> list[str]:
        problems: list[str] = []
        try:
            record = self.read_session()
        except VaultError as exc:
            return [str(exc)]
        if record is not None:
            problems.append(f"an unresolved session exists ({sess.SESSION_NAME} in {self.root}); run `{self.restore_hint()}` first")
        live, root = Path(live_dir).resolve(), self.root.resolve()
        if root == live or live in root.parents or root in live.parents:
            problems.append("the vault and the save folder must not contain each other")
        try:
            check_live_dir(live)
            self.root.mkdir(parents=True, exist_ok=True)
            probe = self.root / ".write-test"
            probe.write_text("x")
            probe.unlink()
            need, free = SPACE_FACTOR * dir_size(live), shutil.disk_usage(self.root).free
            if free < need:
                problems.append(f"vault needs {need // 2**20} MiB free, only {free // 2**20} MiB available")
        except (VaultError, OSError) as exc:
            problems.append(str(exc))
        return problems

    # ---------------- snapshot (FR-3) ----------------
    def snapshot(self, live_dir: Path, *, suffix: str = "") -> Snapshot:
        live = Path(live_dir)
        src = scan(live)
        if not src:
            raise VaultError(f"no files found in {live}")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        name, n = stamp + suffix, 1
        while (self.root / name).exists():
            n += 1
            name = f"{stamp}-{n}{suffix}"
        snap_dir = self.root / name
        snap = Snapshot(snap_dir, src)
        try:
            for rel in src:
                dst = snap.save_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(live / rel, dst)
            copied = scan(snap.save_dir)
            if {k: v["sha256"] for k, v in copied.items()} != {k: v["sha256"] for k, v in src.items()}:
                raise VaultError("snapshot copy does not match the source files")
            after = scan(live)
            if {k: v["sha256"] for k, v in after.items()} != {k: v["sha256"] for k, v in src.items()}:
                raise VaultError("the live save changed while it was being copied")
            atomic_write_json(snap_dir / MANIFEST_NAME, {
                "version": 1, "created": datetime.now().astimezone().isoformat(timespec="seconds"),
                "live_save_dir": str(live), "files": src})
        except BaseException as exc:
            shutil.rmtree(snap_dir, ignore_errors=True)  # nothing is kept, no session record exists yet
            if isinstance(exc, (VaultError, KeyboardInterrupt)):
                raise
            raise VaultError(f"snapshot failed: {exc}") from exc
        return snap

    # ---------------- snapshots on disk ----------------
    def snapshot_path(self, name: str) -> Path:
        if not SNAPSHOT_NAME.match(name):
            raise VaultError(f"not a snapshot name: {name!r}")
        p = self.root / name
        if not p.is_dir():
            raise VaultError(f"snapshot not found: {p}")
        return p

    def load_manifest(self, snap_dir: Path) -> dict:
        try:
            m = json.loads((Path(snap_dir) / MANIFEST_NAME).read_text(encoding="utf-8"))
            if not isinstance(m.get("files"), dict) or not m["files"]:
                raise ValueError("no files listed")
            return m
        except (OSError, ValueError) as exc:
            raise VaultError(f"manifest of {snap_dir} is unusable: {exc}") from exc

    def _save_problems(self, snap_dir: Path) -> list[str]:
        """The `save/` part of a snapshot against its manifest. A restore of the save depends on this part only."""
        try:
            files = self.load_manifest(snap_dir)["files"]
        except VaultError as exc:
            return [str(exc)]
        return _compare(scan(Path(snap_dir) / SAVE_SUBDIR) if (Path(snap_dir) / SAVE_SUBDIR).is_dir() else {}, files)

    def _bin_problems(self, snap_dir: Path) -> list[str]:
        """The `bin/` part (the game's own regulation.bin), when the manifest says there is one."""
        try:
            reg = self.load_manifest(snap_dir).get("regulation")
        except VaultError:
            return []   # already reported by _save_problems
        if not reg:
            return []
        f = Path(snap_dir) / BIN_SUBDIR / REGULATION_NAME
        if not f.is_file():
            return [f"missing: {BIN_SUBDIR}/{REGULATION_NAME}"]
        return [] if sha256_of(f) == reg["original_sha256"] else [f"hash mismatch: {BIN_SUBDIR}/{REGULATION_NAME}"]

    def verify_snapshot(self, snap_dir: Path) -> list[str]:
        """Problems found re-hashing the snapshot against its own manifest (empty list = intact)."""
        return self._save_problems(snap_dir) + self._bin_problems(snap_dir)

    def list_snapshots(self, verify: bool = True) -> list[dict]:
        if not self.root.is_dir():
            return []
        out = []
        for d in sorted(self.root.iterdir()):
            if not (d.is_dir() and SNAPSHOT_NAME.match(d.name)):
                continue
            has_manifest = (d / MANIFEST_NAME).exists()
            size = sum(dir_size(d / sub) for sub in (SAVE_SUBDIR, BIN_SUBDIR) if (d / sub).is_dir())
            verified = (not self.verify_snapshot(d)) if (verify and has_manifest) else None
            out.append({"name": d.name, "path": d, "size": size, "has_manifest": has_manifest, "verified": verified})
        return out

    def prune(self, keep: int) -> list[str]:
        if keep < 1:
            raise VaultError("--keep must be at least 1")
        if self.read_session() is not None:
            raise VaultError("refusing to prune while an unresolved session exists (safety rule 3)")
        names = [s["name"] for s in self.list_snapshots(verify=False)]
        gone = names[:-keep] if len(names) > keep else []
        for n in gone:
            shutil.rmtree(self.root / n)
        return gone

    def status(self) -> dict:
        snaps = self.list_snapshots(verify=False)
        last = snaps[-1] if snaps else None
        record, record_error = None, None
        try:
            record = self.read_session()
        except VaultError as exc:
            record_error = str(exc)
        return {"session": record, "session_error": record_error, "snapshots": len(snaps), "legacy_world": self.legacy_world(),
                "last": last["name"] if last else None,
                "last_problems": self.verify_snapshot(last["path"]) if last else [],
                "vault_bytes": dir_size(self.root) if self.root.is_dir() else 0}

    # ---------------- restore / verify (FR-7, FR-8) ----------------
    def _retry(self, fn: Callable[[], None], what: str) -> None:
        deadline = self._clock() + self._timeout
        delay = 0.05
        while True:
            try:
                fn()
                return
            except PermissionError as exc:
                last = exc
            except OSError as exc:
                if exc.errno not in (errno.EBUSY, errno.ETXTBSY):
                    raise VaultError(f"{what}: {exc}") from exc
                last = exc
            if self._clock() >= deadline:
                raise VaultError(f"{what}: still locked after {self._timeout:g}s ({last})")
            self._sleep(delay)
            delay = min(delay * 2, 1.0)

    def restore(self, snap_dir: Path, live_dir: Path) -> None:
        """Make live_dir byte-identical to the snapshot. The snapshot is verified first; a damaged one is never used."""
        snap_dir, live = Path(snap_dir), Path(live_dir)
        problems = self._save_problems(snap_dir)   # a damaged bin/ must not stop the save from coming back
        if problems:
            raise VaultError("snapshot is damaged, nothing was touched: " + "; ".join(problems[:3]))
        files = self.load_manifest(snap_dir)["files"]
        save_dir = snap_dir / SAVE_SUBDIR
        live.mkdir(parents=True, exist_ok=True)

        for rel in sorted(set(scan_names(live)) - set(files)):  # files the session (or a crash) left behind
            self._retry(lambda rel=rel: os.remove(live / rel), f"delete {rel}")
        keep_dirs = {(live / rel).parent for rel in files}
        for dirpath, _d, _f in os.walk(live, topdown=False):
            d = Path(dirpath)
            if d != live and d not in keep_dirs:
                try:
                    d.rmdir()
                except OSError:
                    pass

        for rel, info in files.items():
            dst = live / rel
            if dst.is_file() and sha256_of(dst) == info["sha256"]:
                self._retry(lambda dst=dst, info=info: os.utime(dst, ns=(info["mtime_ns"], info["mtime_ns"])), f"touch {rel}")
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(dst.name + TMP_SUFFIX)

            def _copy(src=save_dir / rel, dst=dst, tmp=tmp):
                shutil.copy2(src, tmp)
                os.replace(tmp, dst)

            self._retry(_copy, f"restore {rel}")

    def verify_live(self, live_dir: Path, files: dict[str, dict]) -> list[str]:
        return _compare(scan(Path(live_dir)) if Path(live_dir).is_dir() else {}, files)

    def archive_contaminated(self, live_dir: Path, snap_dir: Path) -> Path:
        """FR-13: keep the contaminated save for inspection. It is never restored."""
        dest = Path(snap_dir) / CONTAMINATED_SUBDIR
        n = 1
        while dest.exists():
            n += 1
            dest = Path(snap_dir) / f"{CONTAMINATED_SUBDIR}-{n}"
        shutil.copytree(live_dir, dest)
        return dest


def scan_names(root: Path) -> list[str]:
    return [Path(dp, f).relative_to(root).as_posix() for dp, _d, fs in os.walk(root) for f in fs]


def names_of(files) -> str:
    """File names for a log message: `ER0000.sl2`, `ER0000.sl2.bak` (the backticks make them cyan on a colour console).
    No files known: just "save"."""
    names = sorted(files)
    return ", ".join(f"`{n}`" for n in names) if names else "save"


def save_names(live_dir: Path) -> str:
    """names_of() the files that are in the live save folder now ("save" when it cannot be listed)."""
    try:
        return names_of(scan_names(Path(live_dir)))
    except OSError:
        return "save"


def _compare(actual: dict[str, dict], expected: dict[str, dict]) -> list[str]:
    problems = []
    for rel, info in expected.items():
        if rel not in actual:
            problems.append(f"missing: {rel}")
        elif actual[rel]["sha256"] != info["sha256"]:
            problems.append(f"hash mismatch: {rel}")
    problems += [f"extra file: {rel}" for rel in sorted(set(actual) - set(expected))]
    return problems

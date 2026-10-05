"""SaveVault: snapshot / marker / restore / verify of the live save folder (spec 1.6.0, sections 6-11).

Pure filesystem. It knows nothing about the game process and is the only component that touches save files.
The one guarantee: after a verified restore the live save folder is byte-identical to the snapshot taken before.

Ordering (NFR-3): snapshot complete + hash-verified -> marker written -> ... -> verified restore -> marker removed.
"""
from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

MARKER_NAME = "PENDING_RESTORE.json"
MANIFEST_NAME = "manifest.json"
SAVE_SUBDIR = "save"
CONTAMINATED_SUBDIR = "contaminated"
TMP_SUFFIX = ".eldendisk-tmp"
SPACE_FACTOR = 3                      # FR-1: free space >= 3x the save folder
RESTORE_TIMEOUT_S = 30.0              # FR-7: bounded retry on file locks
SNAPSHOT_NAME = re.compile(r"^\d{8}-\d{6}(-\d+)?(-pre-restore)?$")
SAVE_FILE_HINT = ".sl2"


class VaultError(RuntimeError):
    pass


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


REG_KEY_PATH = r"Software\EldenDisk"


def load_registry_save_dir() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY_PATH, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, "SaveDir")
            if val and Path(val).is_dir():
                p = Path(val)
                p_lower = str(p).lower()
                if "pytest" in p_lower or "tmp" in p_lower or "temp" in p_lower:
                    return None
                if any(f.suffix.lower() == SAVE_FILE_HINT for f in p.iterdir() if f.is_file()):
                    return str(p)
    except Exception:
        return None
    return None


def save_registry_save_dir(save_dir: str) -> None:
    if sys.platform != "win32" or not save_dir:
        return
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    p_lower = str(save_dir).lower()
    if "pytest" in p_lower or "\\tmp\\" in p_lower or "\\temp\\" in p_lower:
        return
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY_PATH) as key:
            winreg.SetValueEx(key, "SaveDir", 0, winreg.REG_SZ, str(save_dir))
    except Exception:
        pass


def dir_size(root: Path) -> int:
    return sum(Path(dp, f).stat().st_size for dp, _d, fs in os.walk(root) for f in fs)


def find_save_dir(appdata: Path | None = None, base_dir: Path | None = None) -> Path:
    """%APPDATA%\\EldenRing\\<SteamID64>. Exactly one candidate or it refuses to guess (A5, safety rule 5)."""
    if appdata is None:
        reg_dir = load_registry_save_dir()
        if reg_dir:
            p = Path(reg_dir)
            if p.is_dir() and any(f.suffix.lower() == SAVE_FILE_HINT for f in p.iterdir() if f.is_file()):
                return p

    base = Path(appdata) if appdata else Path(os.environ.get("APPDATA", "")) / "EldenRing"
    if not base.is_dir():
        raise VaultError(f"save root not found: {base} (use --save-dir)")
    cands = [d for d in base.iterdir() if d.is_dir() and d.name.isdigit()
             and any(f.suffix.lower() == SAVE_FILE_HINT for f in d.iterdir() if f.is_file())]
    if len(cands) != 1:
        names = ", ".join(d.name for d in cands) or "none"
        raise VaultError(f"expected exactly one save folder under {base}, found {len(cands)} ({names}); use --save-dir")

    found = cands[0]
    if appdata is None:
        save_registry_save_dir(str(found))
    return found


def check_live_dir(live_dir: Path) -> None:
    """Refuse folders that cannot be a save folder (restore deletes unknown files inside it)."""
    p = Path(live_dir).resolve()
    if not p.is_dir():
        raise VaultError(f"save folder does not exist: {p}")
    if p == Path(p.anchor) or p == Path.home().resolve() or len(p.parts) < 3:
        raise VaultError(f"refusing to treat {p} as a save folder")
    if not any(f.is_file() for f in p.rglob("*")):
        raise VaultError(f"save folder has no files: {p}")


def _atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


class SessionLog:
    """NFR-4: timestamped log kept in the vault. Lines are buffered until the snapshot directory exists."""

    def __init__(self, echo: Callable[[str], None] | None = None):
        self.path: Path | None = None
        self._buffer: list[str] = []
        self._echo = echo

    def attach(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._flush()

    def write(self, msg: str) -> None:
        line = f"{datetime.now().astimezone().isoformat(timespec='seconds')} {msg}"
        self._buffer.append(line)
        if self.path is not None:
            self._flush()
        if self._echo:
            self._echo(msg)

    def _flush(self) -> None:
        if self.path is not None and self._buffer:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write("\n".join(self._buffer) + "\n")
            self._buffer = []


@dataclass
class Snapshot:
    dir: Path
    files: dict[str, dict]

    @property
    def save_dir(self) -> Path:
        return self.dir / SAVE_SUBDIR


class SaveVault:
    def __init__(self, root: Path, *, timeout: float = RESTORE_TIMEOUT_S,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic):
        self.root = Path(root)
        self._timeout, self._sleep, self._clock = timeout, sleep, clock

    @property
    def marker_path(self) -> Path:
        return self.root / MARKER_NAME

    # ---------------- marker ----------------
    def read_marker(self) -> dict | None:
        if not self.marker_path.exists():
            return None
        try:
            m = json.loads(self.marker_path.read_text(encoding="utf-8"))
            if m.get("version") != 1 or not all(k in m for k in ("snapshot_dir", "live_save_dir", "hashes")):
                raise ValueError("missing keys")
            return m
        except (OSError, ValueError) as exc:
            raise VaultError(f"{self.marker_path} exists but is unreadable ({exc}); the live save cannot be trusted. "
                             f"Do not delete it; restore from the newest snapshot in {self.root}") from exc

    def write_marker(self, snap: Snapshot, live_dir: Path, *, exe_sha256: str | None,
                     game_dir: Path | None = None, game_files: list[str] | None = None) -> None:
        _atomic_write_json(self.marker_path, {
            "version": 1,
            "created": datetime.now().astimezone().isoformat(timespec="seconds"),
            "snapshot_dir": str(snap.dir),
            "live_save_dir": str(live_dir),
            "hashes": {rel: info["sha256"] for rel, info in snap.files.items()},
            "game_dir": str(game_dir) if game_dir else None,
            "game_folder_files_created": list(game_files or []),
            "exe_sha256": exe_sha256,
        })

    def set_game_files(self, files: list[str]) -> None:
        m = self.read_marker()
        if m is not None:
            m["game_folder_files_created"] = list(files)
            _atomic_write_json(self.marker_path, m)

    def clear_marker(self) -> None:
        self.marker_path.unlink(missing_ok=True)

    # ---------------- preflight (FR-1, vault part) ----------------
    def preflight(self, live_dir: Path) -> list[str]:
        problems: list[str] = []
        try:
            marker = self.read_marker()
        except VaultError as exc:
            return [str(exc)]
        if marker is not None:
            problems.append(f"an unresolved session exists ({self.marker_path}); run `sandbox restore` first")
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
            _atomic_write_json(snap_dir / MANIFEST_NAME, {
                "version": 1, "created": datetime.now().astimezone().isoformat(timespec="seconds"),
                "live_save_dir": str(live), "files": src})
        except BaseException as exc:
            shutil.rmtree(snap_dir, ignore_errors=True)  # nothing is kept, no marker exists yet
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

    def verify_snapshot(self, snap_dir: Path) -> list[str]:
        """Problems found re-hashing the snapshot against its own manifest (empty list = intact)."""
        try:
            files = self.load_manifest(snap_dir)["files"]
        except VaultError as exc:
            return [str(exc)]
        return _compare(scan(Path(snap_dir) / SAVE_SUBDIR) if (Path(snap_dir) / SAVE_SUBDIR).is_dir() else {}, files)

    def list_snapshots(self, verify: bool = True) -> list[dict]:
        if not self.root.is_dir():
            return []
        out = []
        for d in sorted(self.root.iterdir()):
            if not (d.is_dir() and SNAPSHOT_NAME.match(d.name)):
                continue
            has_manifest = (d / MANIFEST_NAME).exists()
            size = dir_size(d / SAVE_SUBDIR) if (d / SAVE_SUBDIR).is_dir() else 0
            verified = (not self.verify_snapshot(d)) if (verify and has_manifest) else None
            out.append({"name": d.name, "path": d, "size": size, "has_manifest": has_manifest, "verified": verified})
        return out

    def prune(self, keep: int) -> list[str]:
        if keep < 1:
            raise VaultError("--keep must be at least 1")
        if self.read_marker() is not None:
            raise VaultError("refusing to prune while an unresolved session exists (safety rule 3)")
        names = [s["name"] for s in self.list_snapshots(verify=False)]
        gone = names[:-keep] if len(names) > keep else []
        for n in gone:
            shutil.rmtree(self.root / n)
        return gone

    def status(self) -> dict:
        snaps = self.list_snapshots(verify=False)
        last = snaps[-1] if snaps else None
        marker, marker_error = None, None
        try:
            marker = self.read_marker()
        except VaultError as exc:
            marker_error = str(exc)
        return {"marker": marker, "marker_error": marker_error, "snapshots": len(snaps),
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
        problems = self.verify_snapshot(snap_dir)
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


def _compare(actual: dict[str, dict], expected: dict[str, dict]) -> list[str]:
    problems = []
    for rel, info in expected.items():
        if rel not in actual:
            problems.append(f"missing: {rel}")
        elif actual[rel]["sha256"] != info["sha256"]:
            problems.append(f"hash mismatch: {rel}")
    problems += [f"extra file: {rel}" for rel in sorted(set(actual) - set(expected))]
    return problems

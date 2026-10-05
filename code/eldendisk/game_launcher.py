"""Offline launch: eldenring.exe -eac-nop-loaded, with Steam IDs passed via env vars."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

STEAM_APP_ID = "1245620"
GAME_EXE = "eldenring.exe"
EAC_MARKER = "easyanticheat"


def _steam_libraries() -> list[Path]:
    import winreg  # Windows only

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
        steam_path = Path(winreg.QueryValueEx(k, "SteamPath")[0])
    libs = [steam_path]
    vdf = steam_path / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        text = vdf.read_text(encoding="utf-8", errors="replace")
        libs += [Path(m.replace("\\\\", "\\")) for m in re.findall(r'"path"\s+"([^"]+)"', text)]
    seen, out = set(), []
    for lib in libs:
        if lib not in seen:
            seen.add(lib)
            out.append(lib)
    return out


def find_game_dir(override: str | None = None) -> Path:
    if override:
        d = Path(override)
        if not (d / GAME_EXE).is_file():
            raise FileNotFoundError(f"{GAME_EXE} not found in {d}")
        return d
    try:
        libs = _steam_libraries()
    except OSError as exc:
        raise FileNotFoundError(f"Steam not found in registry ({exc}); use --game-dir") from exc
    for lib in libs:
        d = lib / "steamapps" / "common" / "ELDEN RING" / "Game"
        if (d / GAME_EXE).is_file():
            return d
    raise FileNotFoundError("Elden Ring not found in any Steam library; use --game-dir")


def launch(game_dir: Path) -> subprocess.Popen:
    env = dict(os.environ, SteamAppId=STEAM_APP_ID, SteamGameId=STEAM_APP_ID)
    return subprocess.Popen(
        [str(game_dir / GAME_EXE), "-eac-nop-loaded"], cwd=str(game_dir), env=env
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:  # read-only
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def has_eac(module_names) -> bool:
    return any(EAC_MARKER in n.lower() for n in module_names)


# ---- sandbox helpers (spec 1.6.0: FR-2, FR-11, GF-1..GF-3) ----
ANTICHEAT_PROCESS_MARKERS = ("easyanticheat", "start_protected_game")


def anticheat_processes(process_names) -> list[str]:
    """Running processes that indicate EasyAntiCheat (sandbox refuses to start / write while any exist)."""
    return sorted({n for n in process_names if any(m in n.lower() for m in ANTICHEAT_PROCESS_MARKERS)})


def listing(game_dir: Path) -> dict[str, int]:
    """{relative path: size} of everything under the game folder (names and sizes only, nothing is read)."""
    out: dict[str, int] = {}
    for dp, _d, fs in os.walk(game_dir):
        for f in fs:
            p = Path(dp) / f
            try:
                out[p.relative_to(game_dir).as_posix()] = p.stat().st_size
            except OSError:
                pass
    return out


def cleanup_recorded(game_dir: Path, files: list[str]) -> list[str]:
    """Remove files this tool recorded as created in the game folder (also used by crash recovery). Returns removed."""
    base, removed = Path(game_dir).resolve(), []
    for rel in files:
        p = (base / rel).resolve()
        if base not in p.parents:  # never delete outside the game folder, whatever the marker says
            continue
        if p.is_file():
            p.unlink()
            removed.append(rel)
    return removed


class GameFolderGuard:
    """Records every file the tool creates in the game folder so it can be removed, even after a crash."""

    def __init__(self, game_dir: Path, on_change=None):
        self.dir = Path(game_dir).resolve()
        self.created: list[str] = []
        self.before: dict[str, int] | None = None
        self._on_change = on_change  # called with the created list after each change (to persist it in the marker)

    def take_listing(self) -> None:
        self.before = listing(self.dir)

    def create_file(self, rel: str, data: bytes) -> Path:
        p = (self.dir / rel).resolve()
        if self.dir not in p.parents:
            raise ValueError(f"{rel!r} is outside the game folder")
        if p.exists():
            raise FileExistsError(f"{p} already exists; pre-existing game files are never modified")
        self.created.append(rel)  # record first, create second: a crash in between leaves nothing unrecorded
        if self._on_change:
            self._on_change(list(self.created))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    def cleanup(self) -> list[str]:
        removed = cleanup_recorded(self.dir, self.created)
        self.created = []
        if self._on_change:
            self._on_change([])
        return removed

    def diff(self) -> list[str]:
        """Differences between the pre-session listing and now (empty = identical, GF-2 / T11)."""
        if self.before is None:
            return []
        now = listing(self.dir)
        out = [f"added: {r}" for r in sorted(set(now) - set(self.before))]
        out += [f"removed: {r}" for r in sorted(set(self.before) - set(now))]
        out += [f"size changed: {r}" for r in sorted(set(now) & set(self.before)) if now[r] != self.before[r]]
        return out

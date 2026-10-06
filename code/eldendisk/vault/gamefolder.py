"""Keeping the game folder as it was: record files the tool creates there, remove them afterwards (even after a crash)."""
from __future__ import annotations

import os
from pathlib import Path


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

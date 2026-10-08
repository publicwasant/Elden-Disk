"""customize-items: read the spec, take the game's original regulation.bin as the base, build, write the result.

    sources/items.json    the spec of the items you want in the game (you edit it; the exe embeds a copy)
    <game>/regulation.bin the base: always the game's own file, never an already modified one
    <extension dir>/customize-items/regulation.bin    the output, rebuilt on every call

No state is kept between builds: every call reads the spec and the base again and builds. No printing here (the command
prints). Never imports the vault, the host or the game."""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import bases, spec as specmod
from .build import PreflightError, build as run_build, prepare
from .reblock import BuildError

NAME = "customize-items"
SPEC_FILE, OUTPUT_FILE = "items.json", "regulation.bin"
SOURCES_DIR = Path(__file__).resolve().parent / "sources"      # where items.json lives in the source tree


class ExtensionError(Exception):
    pass


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


@dataclass
class Report:
    built: bool                     # False = nothing to build, or a dry run
    dry_run: bool
    reason: str
    sha256: str = ""
    decrypted_sha256: str = ""
    changed_blocks: int = 0
    warnings: list = field(default_factory=list)
    output: Path | None = None
    items: list = field(default_factory=list)


class CustomizeItems:
    def __init__(self, ext_dir: Path, spec_path: Path | None = None):
        self.ext = Path(ext_dir)
        self.dir = self.ext / NAME
        self.spec_path = Path(spec_path) if spec_path else SOURCES_DIR / SPEC_FILE
        self.output_path = self.dir / OUTPUT_FILE

    # ---------------- the spec ----------------
    def load_spec(self) -> dict:
        if not self.spec_path.is_file():
            raise ExtensionError(f"the spec {self.spec_path} was not found")
        try:
            return specmod.parse(self.spec_path.read_text(encoding="utf-8"))
        except specmod.SpecError as e:
            raise ExtensionError(f"{self.spec_path} is not valid:\n  " + "\n  ".join(e.problems))
        except UnicodeDecodeError:
            raise ExtensionError(f"{self.spec_path} must be UTF-8 text")

    def items(self, which: str = "all") -> list:
        """The items to build: all of them, or the one with this id. An empty list means nothing to do."""
        raw = self.load_spec()
        try:
            items = specmod.select(raw, which)
        except specmod.SpecError as e:
            raise ExtensionError(str(e))
        if len(items) > specmod.MAX_ITEMS_2A:
            raise ExtensionError(f"the spec has {len(items)} items; this version builds one item per file (Level 2a). "
                                 "Choose one with --add <id>")
        return items

    # ---------------- the base ----------------
    def read_base(self, game_file: Path | None) -> bytes:
        """The game's own regulation.bin, which must be the known untouched original."""
        if game_file is None or not Path(game_file).is_file():
            raise ExtensionError("the game's regulation.bin was not found; give --game-dir or --source")
        data = Path(game_file).read_bytes()
        got = hashlib.sha256(data).hexdigest()
        if bases.version_of(got) is None:
            raise ExtensionError(
                f"{game_file} is not a regulation.bin this version knows (sha256 {got[:12]}…). Only the game's own, untouched "
                f"file of version {', '.join(bases.BASES)} works as a base. If it is already modified (for example after a "
                "crashed session), run `eldendisk vault restore`, or verify the game files in Steam")
        return data

    # ---------------- the build ----------------
    def build(self, items: list, game_file: Path | None, dry_run: bool = False) -> Report:
        """Build `items` on the game's original file and write the result to the output path (atomically)."""
        if not items:
            return Report(False, dry_run, f"no items in {self.spec_path}: nothing to build", output=self.output_path)
        data = self.read_base(game_file)
        try:
            res = run_build(data, items, prepare(data))
        except PreflightError as e:
            raise ExtensionError("the file was NOT written because a safety check failed:\n  " + "\n  ".join(e.problems))
        except BuildError as e:
            raise ExtensionError(f"build failed: {e}")
        rep = Report(not dry_run, dry_run, "built", res.sha256, res.decrypted_sha256, res.changed_blocks, list(res.warnings),
                     self.output_path, [i["id"] for i in items])
        if dry_run:
            rep.reason = "dry run: built in memory and checked, nothing written"
            return rep
        _write_atomic(self.output_path, res.data)
        return rep

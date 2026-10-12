"""innovate-items spells: design -> built -> secured.

    extension.json            the design you edit (code/extension.json; section `innovate_items.spells`; the exe embeds a copy)
    <game>/regulation.bin     the base: always the game's own, untouched file
    <extension dir>/innovate-items/spells/    (<extension dir> = <vault>/extension)
        regulation.bin            the latest build (judged by the gate, not yet confirmed in the game)
        regulation.secured.bin    a copy of the build you confirmed (`--secure`)
        spells.commit.json        the commit: the spec behind that copy, the rows each slot took, and the proof (hashes, recipe
                                  version, base)
        spells.build.json         the record of the latest build: WHICH spells it holds (the selection `--add` made, or `all`)
                                  and the proof; `run` builds that selection and reuses the build while nothing changed

`run` swaps the secured file without building when nothing changed (see `decide`), else reuses the latest build while nothing
changed (see `decide_last`); otherwise it builds the selection (everything by default), and the gate judges the
FILE (read back from disk) before it may replace regulation.bin. A failed gate raises GateFailed and nothing is swapped.
No printing here (the commands print). Never imports the vault, the host or the game."""
from __future__ import annotations

import functools
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from .. import bases, zstd
from . import gate, recipes, spec as specmod
from .build import make, prepare
from ..reblock import BuildError

NAME = "innovate-items/spells"
PKG_DIR = Path(__file__).resolve().parent                 # where spells.schema.json lives
CODE_DIR = PKG_DIR.parents[3]                             # code/: where extension.json lives in the source tree
SPEC_FILE, SCHEMA_FILE = "extension.json", "spells.schema.json"
OUTPUT_FILE, SECURED_BIN, SECURED_FILE = "regulation.bin", "regulation.secured.bin", "spells.commit.json"
BUILD_FILE, BUILD_KIND, BUILD_FORMAT = "spells.build.json", "innovate-items.spells build", 1
SECURED_KIND = "innovate-items.spells commit"
COMMIT_FORMAT = 2


class ExtensionError(Exception):
    pass


class GateFailed(ExtensionError):
    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("GATE FAILED: this regulation.bin is NOT safe for the game; nothing was swapped\n  "
                         + "\n  ".join(self.problems))


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


# ---------------- the field-by-field diff ----------------
def _flatten(v, prefix: str, out: dict) -> None:
    if isinstance(v, dict):
        for k in v:
            _flatten(v[k], f"{prefix}.{k}" if prefix else str(k), out)
    else:
        out[prefix] = v


def _shown(v) -> str:
    return "(none)" if v is _MISSING else json.dumps(v, ensure_ascii=False)


_MISSING = object()


def diff_specs(old_view: dict, new_view: dict) -> list:
    """build_view of two specs -> lines like `reverse_curse_technique.shop.price  34590 -> 40000`."""
    lines = []
    if old_view.get("format") != new_view.get("format"):
        lines.append(f"format  {_shown(old_view.get('format', _MISSING))} -> {_shown(new_view.get('format', _MISSING))}")
    old = {it["id"]: it for it in old_view.get("spells", [])}
    new = {it["id"]: it for it in new_view.get("spells", [])}
    for iid in sorted(set(old) | set(new)):
        if iid not in new:
            lines.append(f"{iid}  removed")
            continue
        if iid not in old:
            lines.append(f"{iid}  added")
            continue
        a, b = {}, {}
        _flatten({k: v for k, v in old[iid].items() if k != "id"}, "", a)
        _flatten({k: v for k, v in new[iid].items() if k != "id"}, "", b)
        for path in sorted(set(a) | set(b)):
            x, y = a.get(path, _MISSING), b.get(path, _MISSING)
            if x is _MISSING or y is _MISSING or x != y or type(x) is not type(y):
                lines.append(f"{iid}.{path}  {_shown(x)} -> {_shown(y)}")
    return lines


def _ids_text(ids) -> str:
    return ", ".join(ids) if ids else "no spell"


def _sel_text(sel) -> str:
    return "all spells" if sel == "all" else ", ".join(sel)


@dataclass
class Decision:
    use_secured: bool
    reasons: list = field(default_factory=list)      # why a build is needed (empty when use_secured)
    diff: list = field(default_factory=list)         # field-by-field changes of the design since it was secured


@dataclass
class Report:
    built: bool                     # False = a dry run
    dry_run: bool
    reason: str
    sha256: str = ""
    decrypted_sha256: str = ""
    changed_blocks: int = 0
    notes: list = field(default_factory=list)
    output: Path | None = None
    spells: list = field(default_factory=list)


def _tables_dropped(fn):
    """The decoder's tables are kept for the length of a build or a secure (the gate decodes what the build decoded) and dropped
    after it: `run` goes on for the whole game."""
    @functools.wraps(fn)
    def run(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        finally:
            zstd.forget_tables()
    return run


class Spells:
    def __init__(self, ext_dir: Path, spec_path: Path | None = None):
        self.ext = Path(ext_dir)
        self.dir = self.ext / NAME
        self.spec_path = Path(spec_path) if spec_path else CODE_DIR / SPEC_FILE
        self.output_path = self.dir / OUTPUT_FILE
        self.secured_bin = self.dir / SECURED_BIN
        self.secured_path = self.dir / SECURED_FILE
        self.build_path = self.dir / BUILD_FILE

    # ---------------- the design ----------------
    def load_spec(self) -> dict:
        if not self.spec_path.is_file():
            raise ExtensionError(f"the design {self.spec_path} was not found")
        try:
            return specmod.parse(self.spec_path.read_text(encoding="utf-8"))
        except specmod.SpecError as e:
            raise ExtensionError(f"{self.spec_path} is not valid:\n  " + "\n  ".join(e.problems))
        except UnicodeDecodeError:
            raise ExtensionError(f"{self.spec_path} must be UTF-8 text")

    def items(self, which="all") -> list:
        """The spells to build, in slot order: `all`, or the ones named by id / path (see spec.selection_of). An empty list
        means nothing to do."""
        raw = self.load_spec()
        try:
            spells = specmod.select(raw, which)
        except specmod.SpecError as e:
            raise ExtensionError(str(e))
        for s in spells:
            if s.get("shop") is not None and recipes.slot_rows(s["slot"])["shop_line"] is None:
                raise ExtensionError(f"{s['id']} is in slot {s['slot']} and has a `shop`, but only the first {len(recipes.SHOP_LINES)} "
                                     "slots have a shop line (the merchant's group has no more free lines): remove its `shop`")
        return spells

    def flame_color(self, which="all") -> tuple:
        """-> (colour, note): the [red, green, blue] the design gives the fire of Flame, Grant Me Strength, or None. The game's fire
        effects are shared by every spell that uses them, so there is ONE colour for the design: the first spell (by slot) that names
        one; when the spells name different colours the note says which one is used. `write --flame-color` puts it into the game."""
        named = [(s["slot"], tuple(s["flame_color"])) for s in self.items(which) if "flame_color" in s]
        if not named:
            return None, None
        first = named[0][1]
        other = sorted({c for _slot, c in named if c != first})
        note = (f"the spells name {len(other) + 1} different flame colours; the fire effects are shared, so only slot {named[0][0]}'s is used"
                if other else None)
        return first, note

    def texts(self, which="all") -> dict:
        """The text for the game: {goods id: {"goods_name", "goods_info", "goods_captions"}} for EVERY slot of the design (the Goods
        id is the one the slot owns), empty where nothing is to be shown: a slot with no spell, or a spell that is not in `which`
        (it is not built, so the game has no item to show it for). `write --text` puts this into the running game."""
        raw = self.load_spec()
        out = {recipes.slot_rows(n)["goods"]: dict.fromkeys(specmod.TEXT_FIELDS, "") for n in range(1, raw["maximum"] + 1)}
        for s in self.items(which):
            out[recipes.slot_rows(s["slot"])["goods"]] = dict(s["text"])
        return out

    # ---------------- the base ----------------
    def read_base(self, game_file: Path | None) -> tuple:
        """The game's own regulation.bin -> (bytes, sha256). It must be the known untouched original, on every path."""
        if game_file is None or not Path(game_file).is_file():
            raise ExtensionError("the game's regulation.bin was not found; give --game-dir or --source")
        data = Path(game_file).read_bytes()
        got = hashlib.sha256(data).hexdigest()
        if bases.version_of(got) is None:
            raise ExtensionError(
                f"{game_file} is not a regulation.bin this version knows (sha256 {got[:12]}…). Only the game's own, untouched "
                f"file of version {', '.join(bases.BASES)} works as a base. If the game is still running, close it first. If a "
                "session crashed and left the game's file modified, run `eldendisk vault restore`, or verify the game files in Steam")
        return data, got

    # ---------------- secured state ----------------
    def read_secured(self) -> dict | None:
        """The record of spells.commit.json, or None when there is none. A record that cannot be read raises ValueError."""
        if not self.secured_path.is_file():
            return None
        try:
            rec = json.loads(self.secured_path.read_text(encoding="utf-8"))
            ok = (isinstance(rec, dict) and rec.get("kind") == SECURED_KIND and rec.get("format") == COMMIT_FORMAT
                  and isinstance(rec["spec"]["spells"], list) and isinstance(rec["rows"], dict)
                  and isinstance(rec["bin"]["sha256"], str) and isinstance(rec["base_sha256"], str)
                  and isinstance(rec["recipe_version"], int))
        except (OSError, ValueError, KeyError, TypeError) as e:
            raise ValueError(f"{self.secured_path.name} cannot be read ({e})")
        if not ok:
            raise ValueError(f"{self.secured_path.name} is not an innovate-items.spells record")
        return rec

    # ---------------- the latest build and what it holds ----------------
    def read_build(self) -> dict | None:
        """The record of spells.build.json, or None when there is none. A record that cannot be read raises ValueError."""
        if not self.build_path.is_file():
            return None
        try:
            rec = json.loads(self.build_path.read_text(encoding="utf-8"))
            sel = rec["selection"]
            ok = (isinstance(rec, dict) and rec.get("kind") == BUILD_KIND and rec.get("format") == BUILD_FORMAT
                  and (sel == "all" or (isinstance(sel, list) and sel and all(isinstance(i, str) for i in sel)))
                  and isinstance(rec["spec"]["spells"], list) and isinstance(rec["bin"]["sha256"], str)
                  and isinstance(rec["base_sha256"], str) and isinstance(rec["recipe_version"], int))
        except (OSError, ValueError, KeyError, TypeError) as e:
            raise ValueError(f"{self.build_path.name} cannot be read ({e})")
        if not ok:
            raise ValueError(f"{self.build_path.name} is not an innovate-items.spells build record")
        return rec

    def selection(self) -> tuple:
        """-> (selection, note): "all" or the list of spell ids the last `--add` chose (kept in the build record). Without a
        record, or with one that cannot be read, it is "all" (the note says so for the unreadable one)."""
        try:
            rec = self.read_build()
        except ValueError as e:
            return "all", f"{e}: building every spell"
        return (rec["selection"] if rec else "all"), None

    def decide_last(self, spells: list, selection, base_sha: str) -> Decision:
        """Use the latest build (regulation.bin) as it is? Only when ALL hold: its record holds the same selection and the
        design of those spells is equal, the file has the recorded hash, the game's file is the base it was built on, and the
        recipes are the same version. `use_secured` here means "use this file". Nothing is built to decide."""
        try:
            rec = self.read_build()
        except ValueError as e:
            return Decision(False, [f"{e}"])
        if rec is None:
            return Decision(False, ["no build yet"])
        reasons, diff = [], []
        if rec["selection"] != selection:
            reasons.append("the selection changed (%s -> %s)" % (_sel_text(rec["selection"]), _sel_text(selection)))
        if rec["recipe_version"] != bases.RECIPE_VERSION:
            reasons.append(f"the recipes changed (built with version {rec['recipe_version']}, now {bases.RECIPE_VERSION})")
        if rec["base_sha256"] != base_sha:
            reasons.append("the game's regulation.bin is not the file the last build was made on")
        diff = diff_specs(specmod.build_view(rec["spec"]), specmod.build_view({"format": specmod.FORMAT, "spells": spells}))
        if diff and not reasons:
            reasons.append(f"the design changed since the last build ({len(diff)} field{'s' if len(diff) != 1 else ''})")
        if not self.output_path.is_file():
            reasons.append(f"{OUTPUT_FILE} is missing")
        elif sha256_file(self.output_path) != rec["bin"]["sha256"]:
            reasons.append(f"{OUTPUT_FILE} is not the file that was built (its hash differs)")
        return Decision(not reasons, reasons, diff)

    def decide(self, spells: list, base_sha: str) -> Decision:
        """Use the secured file as it is, or build? Secured only when ALL hold: the design equals the secured spec (text,
        whitespace, key order do not count), the secured file has the recorded hash, the game's file is the base
        the record was made on, and the recipes are the same version. Nothing is ever built to decide this."""
        want = {"format": specmod.FORMAT, "spells": spells}      # build_view looks only at the spells
        try:
            rec = self.read_secured()
        except ValueError as e:
            return Decision(False, [f"{e}: building again"])
        if rec is None:
            return Decision(False, ["no secured build yet (first run, or spells.commit.json was deleted)"])
        reasons, diff = [], []
        if rec["recipe_version"] != bases.RECIPE_VERSION:
            reasons.append(f"the recipes changed (secured with version {rec['recipe_version']}, now {bases.RECIPE_VERSION})")
        if rec["base_sha256"] != base_sha:
            reasons.append("the game's regulation.bin is not the file the secured build was made on")
        held, now = [i["id"] for i in rec["spec"]["spells"]], [i["id"] for i in spells]
        diff = diff_specs(specmod.build_view(rec["spec"]), specmod.build_view(want))
        if set(held) != set(now):
            reasons.append("the secured build holds %s, this run builds %s" % (_ids_text(held), _ids_text(now)))
        elif diff:
            reasons.append(f"the design changed since it was secured ({len(diff)} field{'s' if len(diff) != 1 else ''})")
        if not self.secured_bin.is_file():
            reasons.append(f"{SECURED_BIN} is missing")
        elif sha256_file(self.secured_bin) != rec["bin"]["sha256"]:
            reasons.append(f"{SECURED_BIN} is not the file that was secured (its hash differs)")
        return Decision(not reasons, reasons, diff)

    # ---------------- the build ----------------
    @_tables_dropped
    def build(self, spells: list, base: bytes, dry_run: bool = False, selection="all") -> Report:
        """Build `spells` on the game's original file; the gate judges the bytes READ BACK from disk; only then does the result
        replace regulation.bin, and the build record (which spells it holds: `selection` is "all" or their ids; `run` builds the
        same selection again) is written after it. A failed gate raises GateFailed and leaves regulation.bin, the record and the
        secured files as they were. A dry run writes nothing, so it never changes the selection."""
        if not spells:
            return Report(False, dry_run, f"no spells in {self.spec_path}: nothing to build", output=self.output_path)
        try:
            src = prepare(base)
            res = make(src, spells)
        except BuildError as e:
            raise ExtensionError(f"build failed: {e}")
        tmp = self.output_path.with_name(self.output_path.name + ".tmp")
        if dry_run:
            v = gate.verify(res.data, src, spells)
        else:
            self.dir.mkdir(parents=True, exist_ok=True)
            with open(tmp, "wb") as f:
                f.write(res.data)
                f.flush()
                os.fsync(f.fileno())
            try:
                v = gate.verify(tmp.read_bytes(), src, spells)
            except BaseException:
                tmp.unlink(missing_ok=True)
                raise
        if not v.ok:
            tmp.unlink(missing_ok=True)
            raise GateFailed(v.problems)
        if not dry_run:
            os.replace(tmp, self.output_path)
            rec = {"kind": BUILD_KIND, "format": BUILD_FORMAT, "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "recipe_version": bases.RECIPE_VERSION, "base_sha256": hashlib.sha256(base).hexdigest(),
                   "bin": {"file": OUTPUT_FILE, "sha256": res.sha256, "size": len(res.data)},
                   "selection": selection, "spec": {"format": specmod.FORMAT, "spells": spells}}
            _write_atomic(self.build_path, (json.dumps(rec, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
        return Report(not dry_run, dry_run, "built and checked" if not dry_run else "dry run: built in memory and checked, nothing written",
                      res.sha256, res.decrypted_sha256, v.stats.get("changed_blocks", 0), list(v.notes), self.output_path,
                      [i["id"] for i in spells])

    @_tables_dropped
    def secure(self, spells: list, game_file: Path | None) -> Report:
        """Commit the current regulation.bin: the gate judges it against the CURRENT design, then it is copied to
        regulation.secured.bin and the record is written (the bin first, the record last, so a half-done secure is just 'not secured')."""
        if not spells:
            raise ExtensionError(f"no spells in {self.spec_path}: nothing to secure")
        if not self.output_path.is_file():
            raise ExtensionError(f"{self.output_path} does not exist yet: build it first (`eldendisk run`, or `extension innovate-items spells --add all`)")
        base, base_sha = self.read_base(game_file)
        try:
            src = prepare(base)
        except BuildError as e:
            raise ExtensionError(f"the base cannot be read: {e}")
        data = self.output_path.read_bytes()
        v = gate.verify(data, src, spells)
        if not v.ok:
            raise GateFailed(v.problems + [f"(if the design changed after this regulation.bin was built, build again first: it must match {self.spec_path.name})"])
        _write_atomic(self.secured_bin, data)
        if sha256_file(self.secured_bin) != v.sha256:
            raise ExtensionError(f"{self.secured_bin} was not written correctly (hash differs); nothing was secured")
        rec = {"kind": SECURED_KIND, "format": COMMIT_FORMAT, "committed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
               "recipe_version": bases.RECIPE_VERSION, "base_version": bases.version_of(base_sha), "base_sha256": base_sha,
               "bin": {"file": SECURED_BIN, "sha256": v.sha256, "decrypted_sha256": v.decrypted_sha256, "size": len(data)},
               "rows": {s["id"]: recipes.slot_rows(s["slot"]) for s in spells},       # what each committed spell took in the game
               "spec": {"format": specmod.FORMAT, "spells": spells}}
        _write_atomic(self.secured_path, (json.dumps(rec, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
        return Report(True, False, "secured", v.sha256, v.decrypted_sha256, v.stats.get("changed_blocks", 0), list(v.notes),
                      self.secured_bin, [i["id"] for i in spells])

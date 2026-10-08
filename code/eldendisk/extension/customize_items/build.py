"""spec items + the game's original regulation.bin -> a new regulation.bin (bytes). Pure functions; no file access."""
from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field

from . import container, preflight, reblock, recipes
from .container import Bnd4, Param
from .defs import TABLE_FILES, Def
from .reblock import BuildError, Source


class PreflightError(BuildError):
    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("preflight failed: " + "; ".join(self.problems))


@dataclass
class Result:
    data: bytes                       # the encrypted regulation.bin
    sha256: str
    decrypted_sha256: str
    changed_blocks: int = 0
    warnings: list = field(default_factory=list)


def prepare(base: bytes):
    """-> Source of the original (also checks that our container code reads and writes it back unchanged)."""
    src = Source(container.decrypt(base))
    bnd = Bnd4(src.body)
    if bnd.build() != src.body:
        raise BuildError("internal check failed: the BND4 writer does not reproduce the original")
    for fname in TABLE_FILES.values():
        e = bnd.get(fname)
        if Param(e.data).build() != e.data:
            raise BuildError("internal check failed: the PARAM writer does not reproduce %s" % fname)
    return src


def plan(src: Source, items: list):
    """Apply the recipes to the original -> (the new decoded body, the Footprint of rows the recipes touched)."""
    if len(items) != 1:
        raise BuildError("this version builds exactly one item per file (Level 2a); select one with --add <id>")
    bnd = Bnd4(src.body)
    D = {k: Def(k) for k in TABLE_FILES}
    P = {k: Param(bnd.get(f).data) for k, f in TABLE_FILES.items()}
    fp = recipes.Footprint()
    for item in items:
        if item["type"] != "incantation":
            raise BuildError("unsupported item type %r" % item["type"])
        try:
            recipes.apply_incantation(P, D, item, fp)
        except recipes.RecipeError as e:
            raise BuildError(str(e))
    for k, f in TABLE_FILES.items():
        bnd.get(f).data = P[k].build()
    newbody = bnd.build()
    if len(newbody) != len(src.body):
        raise BuildError("the body length changed (%d -> %d)" % (len(src.body), len(newbody)))
    return newbody, fp


def build(base: bytes, items: list, src: Source | None = None) -> Result:
    src = src or prepare(base)
    newbody, fp = plan(src, items)
    frame, edit, converted = reblock.rewrite(src, newbody)
    h = bytearray(src.header)
    struct.pack_into(">II", h, 0x1C, len(newbody), len(frame))
    dcx = bytes(h) + frame + b"\0" * ((-(len(h) + len(frame))) % 16)
    problems, warnings, stats = preflight.check(src, dcx, newbody, fp)
    if problems:
        raise PreflightError(problems)
    data = container.encrypt(dcx)
    if container.decrypt(data) != dcx:
        raise BuildError("internal check failed: encrypt/decrypt does not round-trip")
    return Result(data, hashlib.sha256(data).hexdigest(), hashlib.sha256(dcx).hexdigest(), stats.get("changed_blocks", 0), warnings)

"""spec spells + the game's original regulation.bin -> a new regulation.bin (bytes). Pure functions; no file access."""
from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field

from . import chain as chainmod, container, grow, reblock, recipes
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
    notes: list = field(default_factory=list)


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


def plan(src: Source, spells: list):
    """Apply the recipes to the original -> (the new decoded body, the Footprint of rows the recipes added). The body is LONGER
    than the original: the tables grew (grow.py)."""
    for spell in spells:
        kind = spell.get("kind", "buff")
        if kind not in ("buff", "clone", "enchant", "projectile"):
            raise BuildError("unsupported spell kind %r" % kind)
        if kind == "buff" and "from" not in spell and spell["type"] != "incantation":
            raise BuildError("unsupported spell type %r" % spell["type"])
    bnd = Bnd4(src.body)
    D = {k: Def(k) for k in TABLE_FILES}
    P = {k: Param(bnd.get(f).data) for k, f in TABLE_FILES.items()}
    try:
        chain = chainmod.load(bnd, P, D) if any(recipes.needs_chain(s) for s in spells) else None
        jobs, fp = recipes.make_rows(P, D, spells, chain)
        newbody, _reports = grow.grow(src.body, jobs)
    except recipes.RecipeError as e:
        raise BuildError(str(e))
    return newbody, fp


def make(src: Source, spells: list) -> Result:
    """spells + the game's original -> the finished (encrypted) file. NO checks here: the gate (gate.verify) judges the bytes."""
    newbody, _fp = plan(src, spells)
    frame, _edit, _converted, _appended = reblock.rewrite_grow(src, newbody)
    h = bytearray(src.header)
    struct.pack_into(">II", h, 0x1C, len(newbody), len(frame))
    dcx = bytes(h) + frame + b"\0" * ((-(len(h) + len(frame))) % 16)
    data = container.encrypt(dcx)
    return Result(data, hashlib.sha256(data).hexdigest(), hashlib.sha256(dcx).hexdigest())


def build(base: bytes, spells: list, src: Source | None = None) -> Result:
    """make + the gate, all in memory (the service writes to disk and reads back; this is for tests and tools)."""
    from . import gate
    src = src or prepare(base)
    res = make(src, spells)
    v = gate.verify(res.data, src, spells)
    if v.problems:
        raise PreflightError(v.problems)
    res.changed_blocks, res.notes = v.stats.get("changed_blocks", 0), v.notes
    return res

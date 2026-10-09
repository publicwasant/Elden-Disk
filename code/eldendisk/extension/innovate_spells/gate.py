"""The gate: does this regulation.bin look like a file the game accepts? Stdlib only.

It judges the bytes of the FILE (read back from disk, decrypted again), not what the builder believes it wrote. It rebuilds
the intended content from the design and the game's own file and compares, then reads the rows of the file itself.
Every rule is a lesson from the handbook (R1-R6 in preflight.py; G5, G11-G13, G16 here). Any problem, and also any
warning, is a stop: the file is not swapped and the game is not started.

A pass means "nothing we know the game rejects". It is necessary, not sufficient; the game is the real test."""
from __future__ import annotations

import hashlib
import importlib
import struct
from dataclasses import dataclass, field

from . import container, preflight, recipes
from .build import plan
from .container import Bnd4, ParamView
from .defs import TABLE_FILES, Def
from .reblock import BuildError, Source


@dataclass
class Verdict:
    problems: list = field(default_factory=list)
    notes: list = field(default_factory=list)       # harmless facts (for example: the second decoder is not available)
    stats: dict = field(default_factory=dict)
    sha256: str = ""                                # of the file as given (encrypted)
    decrypted_sha256: str = ""

    @property
    def ok(self) -> bool:
        return not self.problems


def second_decode(frame: bytes):
    """Decode with a second, independent decoder when this Python has one (3.14: compression.zstd).
    -> ("ok", bytes) | ("unavailable", None) | ("error", message)"""
    try:
        z = importlib.import_module("compression.zstd")
    except ImportError:
        return "unavailable", None
    try:
        return "ok", z.decompress(frame)
    except Exception as e:
        return "error", str(e)


def verify(data: bytes, src: Source, spells: list) -> Verdict:
    """`data`: the encrypted regulation.bin as it is on disk. `src`: the game's original. `spells`: the design's spells."""
    v = Verdict(sha256=hashlib.sha256(data).hexdigest())
    try:
        dcx = container.decrypt(data)
    except Exception as e:
        v.problems.append("G0: the file cannot be decrypted (%s)" % e)
        return v
    v.decrypted_sha256 = hashlib.sha256(dcx).hexdigest()
    try:
        newbody, fp = plan(src, spells)             # what the file must contain, computed again from the design and the game's file
    except BuildError as e:
        v.problems.append("G5: the intended content cannot be computed (%s)" % e)
        return v
    bad, warn, stats = preflight.check(src, dcx, newbody, fp)
    v.problems += bad
    v.problems += ["%s (a warning counts as a stop)" % w for w in warn]
    decoded = stats.pop("decoded", None)
    v.stats = stats
    if decoded is None:
        return v
    try:
        bnd = Bnd4(decoded)
        D = {k: Def(k) for k in TABLE_FILES}
        P = {k: ParamView(bnd.get(f).data, D[k].size) for k, f in TABLE_FILES.items()}
    except Exception as e:
        v.problems.append("G11: the tables of the file cannot be read (%s)" % e)
        return v
    for spell in spells:
        v.problems += recipes.check_incantation(P, D, spell)
    csize = struct.unpack(">I", dcx[0x20:0x24])[0]
    state, other = second_decode(dcx[0x4C:0x4C + csize])
    if state == "unavailable":
        v.notes.append("the second decoder (compression.zstd) is not available in this Python: only our own decoder was used")
    elif state == "error":
        v.problems.append("G16: the second decoder cannot decode the frame (%s)" % other)
    elif other != decoded:
        v.problems.append("G16: the second decoder decodes the frame to different bytes than ours")
    else:
        v.notes.append("the second decoder (compression.zstd) agrees")
    return v

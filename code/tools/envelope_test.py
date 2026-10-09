"""Developer tool (not shipped, not used by `run`): build a regulation.bin that goes BEYOND what the gate accepts, to find out in the
game whether the game accepts it. The gate keeps its numbers (preflight.MAX_*) until a file like this has passed in the game.

    python tools/envelope_test.py --source <game>/regulation.bin --out regulation.envelope-test.bin [--spec extension.json]

T7 = the spells of the design (as in a normal build) + 4 UNREFERENCED copies of the Black Flame bullets (Bullet rows 10623000,
10623001, 10623050, 10623051 under the ids 500000000-500000003). Nothing points at the copies: the game must simply load the file.
What it tests: a fifth table (Bullet, 15,475 rows, 4.5 MB) that grows, and about 20 re-encoded blocks. T7 passed in the game on 2026-10-10 (the gate then went from 13 to 20 blocks); the tool stays for the next, bigger experiment.

Everything the gate checks is checked here too (R1-R6, G11-G13) EXCEPT the envelope numbers: those are printed. The file is not
written when anything else is wrong. Use it on the game's own file only; write the result to a path of your own, then put it
in place with `run --regulation FILE` (vault ON) so the original comes back."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eldendisk.extension.innovate_spells import bases, build, chain as chainmod, container, grow, preflight, recipes, reblock, spec   # noqa: E402
from eldendisk.extension.innovate_spells.container import Bnd4, Param, ParamView                                           # noqa: E402
from eldendisk.extension.innovate_spells.defs import TABLE_FILES, Def                                                       # noqa: E402

COPIES = {500000000: 10623000, 500000001: 10623001, 500000002: 10623050, 500000003: 10623051}      # new id -> Black Flame bullet it copies
ENVELOPE = ("R2: ", "R7: ")          # the warnings this tool lets through (they are the point of the test)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", required=True, help="the game's own regulation.bin (1.17.1)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--spec", default=str(Path(__file__).resolve().parent.parent / "extension.json"))
    a = ap.parse_args(argv)
    base = Path(a.source).read_bytes()
    if hashlib.sha256(base).hexdigest() != bases.BASES[bases.CURRENT_BASE]:
        print("the source is not the original regulation.bin of 1.17.1", file=sys.stderr)
        return 2
    spells = spec.normalise(json.loads(Path(a.spec).read_text(encoding="utf-8")))["spells"]
    src = build.prepare(base)
    bnd = Bnd4(src.body)
    D = {k: Def(k) for k in TABLE_FILES}
    P = {k: Param(bnd.get(f).data) for k, f in TABLE_FILES.items()}
    chain = chainmod.load(bnd, P, D) if any(recipes.needs_chain(x) for x in spells) else None
    jobs, fp = recipes.make_rows(P, D, spells, chain)
    rows = []
    for new, old in COPIES.items():
        r = P["bullet"].find(old)
        if r is None:
            print("Bullet row %d is missing: not the 1.17.1 file" % old, file=sys.stderr)
            return 2
        rows.append((new, bytes(r[2])))
    jobs["Bullet"] = {"rows": rows, "name_from": recipes.NAME_FROM["bullet"]}
    fp.added["bullet"] = set(COPIES)
    newbody, _ = grow.grow(src.body, jobs)
    frame, *_ = reblock.rewrite_grow(src, newbody)
    h = bytearray(src.header)
    struct.pack_into(">II", h, 0x1C, len(newbody), len(frame))
    dcx = bytes(h) + frame + b"\0" * ((-(len(h) + len(frame))) % 16)
    bad, warn, stats = preflight.check(src, dcx, newbody, fp)
    decoded = stats.pop("decoded", None)
    problems = list(bad) + [w for w in warn if not w.startswith(ENVELOPE)]
    if decoded is not None:
        nb = Bnd4(decoded)
        V = {k: ParamView(nb.get(f).data, D[k].size) for k, f in TABLE_FILES.items()}
        for s in spells:
            problems += recipes.check_template(V, D, s, P, chain) if recipes.is_template(s) else recipes.check_incantation(V, D, s)
        for new, old in COPIES.items():
            got, want = V["bullet"].find(new), V["bullet"].find(old)
            if got is None or want is None or bytes(got[2]) != bytes(want[2]):
                problems.append("T7: bullet copy %d is not a byte-for-byte copy of %d" % (new, old))
    if problems:
        print("NOT written, the file is wrong in ways that are not the envelope:", *problems, sep="\n  ", file=sys.stderr)
        return 1
    data = container.encrypt(dcx)
    Path(a.out).write_bytes(data)
    print("written %s" % a.out)
    print("  sha256 %s" % hashlib.sha256(data).hexdigest())
    print("  decrypted sha256 %s" % hashlib.sha256(dcx).hexdigest())
    print("  re-encoded blocks %d (gate limit %d, tested in the game: 20)" % (stats["changed_blocks"], preflight.MAX_CHANGED_BLOCKS))
    print("  body growth %d (gate limit %d)" % (stats["body_growth"], preflight.MAX_BODY_GROWTH))
    print("  frame growth %d (gate limit %d)" % (stats["frame_growth"], preflight.MAX_FRAME_GROWTH))
    print("  envelope warnings: %s" % ("; ".join(warn) or "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Developer tool (not shipped, not used by `run`): build a regulation.bin that goes BEYOND what the gate accepts, to find out in the
game whether the game accepts it. The gate keeps its numbers (preflight.MAX_*) until a file like this has passed in the game.

    python tools/envelope_test.py --source <game>/regulation.bin --out regulation.envelope-test.bin [--spec extension.json]

T9 = the spells of the design (as in a normal build) + 4 UNREFERENCED copies of Black Flame bullets (as in T7: Bullet rows 10623000,
10623001, 10623050, 10623051 under the ids 500002000-500002003, outside the 64 slot blocks) + 4 UNREFERENCED copies of attack rows
(AtkParam_Pc rows 62101, 62106, 62502, 62503 under the ids 710002000-710002003), the Atk table GROWN AT ITS END (grow.py
`_grow_end`). Nothing points at the copies: the game must simply load the file. What it tests: a sixth table, with a layout the game
has not seen (the first rows of its data are copied behind the strings to make room for the records), and 26 re-encoded blocks.
T7 (the Bullet copies alone) passed in the game on 2026-10-10, the gate then went from 13 to 20 blocks; T9 passed on 2026-10-10 too (26 blocks, frame +242,464). T8 (the same Atk rows with the
table grown BACKWARDS as the other tables are) did not pass: the 6 MB table in front of it had to move, body +6.27 MB.

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

from eldendisk.extension.innovate_items import bases, container, grow, preflight, reblock
from eldendisk.extension.innovate_items.spells import build, chain as chainmod, recipes, spec   # noqa: E402
from eldendisk.extension.innovate_items.container import Bnd4, Param, ParamView                                           # noqa: E402
from eldendisk.extension.innovate_items.defs import TABLE_FILES, Def                                                       # noqa: E402

COPIES = {500002000: 10623000, 500002001: 10623001, 500002002: 10623050, 500002003: 10623051}      # new id -> Black Flame bullet it copies
ATK_COPIES = {710002000: 62101, 710002001: 62106, 710002002: 62502, 710002003: 62503}              # new id -> AtkParam_Pc row it copies
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
    jobs["Bullet"] = {"rows": jobs.get("Bullet", {"rows": []})["rows"] + rows, "name_from": recipes.NAME_FROM["bullet"]}     # after the design's own rows, if any
    fp.added["bullet"] |= set(COPIES)
    arows = []
    for new, old in ATK_COPIES.items():
        r = P["atk"].find(old)
        if r is None:
            print("AtkParam_Pc row %d is missing: not the 1.17.1 file" % old, file=sys.stderr)
            return 2
        arows.append((new, bytes(r[2])))
    jobs["AtkParam_Pc"] = {"rows": jobs.get("AtkParam_Pc", {"rows": []})["rows"] + arows, "name_from": recipes.NAME_FROM["atk"], "mode": "end"}
    fp.added["atk"] |= set(ATK_COPIES)
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
        for new, old in ATK_COPIES.items():
            got, want = V["atk"].find(new), V["atk"].find(old)
            if got is None or want is None or bytes(got[2]) != bytes(want[2]):
                problems.append("T8: attack copy %d is not a byte-for-byte copy of %d" % (new, old))
    if problems:
        print("NOT written, the file is wrong in ways that are not the envelope:", *problems, sep="\n  ", file=sys.stderr)
        return 1
    data = container.encrypt(dcx)
    Path(a.out).write_bytes(data)
    print("written %s" % a.out)
    print("  sha256 %s" % hashlib.sha256(data).hexdigest())
    print("  decrypted sha256 %s" % hashlib.sha256(dcx).hexdigest())
    print("  re-encoded blocks %d (gate limit %d, tested in the game: 26 in T9)" % (stats["changed_blocks"], preflight.MAX_CHANGED_BLOCKS))
    print("  body growth %d (gate limit %d)" % (stats["body_growth"], preflight.MAX_BODY_GROWTH))
    print("  frame growth %d (gate limit %d)" % (stats["frame_growth"], preflight.MAX_FRAME_GROWTH))
    print("  envelope warnings: %s" % ("; ".join(warn) or "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

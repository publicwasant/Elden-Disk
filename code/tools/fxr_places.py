"""Where the colours sit in an effect file (FXR version 5, Elden Ring): the data for writer/fxr_plans.py.

    python tools/fxr_places.py sfxdump/f000301262.fxr          prints the plan of the file (paste it into writer/fxr_plans.py)

Get the file with tools/dump_sfx.py (`--sfx 301262`). What is read (nothing else of the format is needed):
    header      "FXR\\0", version 5; at 0x10 eleven (offset, count) pairs; section 6 = actions (64 bytes each), section 7 =
                properties (40 bytes each)
    property    s16 type (low 2 bits: number of components - 1, so 3 = a colour; the next bits: the function), ..., s32 field count
                at 0x08, s32 field offset at 0x10
    function 2  (constant) the 4 fields are the colour
    function 4+ (linear, curves) s32 key count n, then 8 fields (the smallest and the biggest value of each component), n times,
                then n colours (curves keep their tangents after them: not colours, left alone)
    action      s32 id (+ 0x1000000) at 0x00, s32 count of its first fields at 0x08, of its second fields at 0x10, s32 offset of its
                fields at 0x20; the drawing actions 602, 603, 604 and 10012 keep their bloom colour at second-fields 5..8 (RGB and
                strength: a bloom colour, recoloured as v * target)
Checked against the plans of 524400 and 524401 that were made with an effect library and tried in the game: 71 of their 72 places
are found here (the one left is a black curve tangent, which a recolouring leaves black anyway); this reading also finds a few more
(the smallest value and some first keys of linear colours, which those plans skipped)."""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

BLOOM_ACTIONS = (602, 603, 604, 10012)
ACTION_BASE = 0x1000000


class FxrError(Exception):
    pass


def _sections(d: bytes) -> dict:
    if d[:4] != b"FXR\0" or struct.unpack_from("<H", d, 6)[0] != 5:
        raise FxrError("not an FXR version 5 file")
    pairs = struct.unpack_from("<22i", d, 0x10)
    return {k + 1: (pairs[2 * k], pairs[2 * k + 1]) for k in range(11)}


def places(d: bytes) -> list[tuple[int, bool]]:
    """[(offset of 16 bytes RGBA, is it a bloom colour)] of the file, sorted, each once."""
    secs = _sections(d)
    out = set()
    p7, n7 = secs[7]
    for i in range(n7):
        ta, fc, fo = struct.unpack_from("<h", d, p7 + 40 * i)[0], *struct.unpack_from("<i4xi", d, p7 + 40 * i + 8)
        if ta & 3 != 3 or not fc:
            continue
        if ta >> 4 == 2:
            if fc != 4:
                raise FxrError("a constant colour at %#x has %d fields" % (fo, fc))
            out.add((fo, False))
            continue
        n = struct.unpack_from("<i", d, fo)[0]
        if not 1 <= n or 1 + 8 + n + 4 * n > fc:
            raise FxrError("a colour at %#x has %d keys in %d fields" % (fo, n, fc))
        out |= {(fo + 4, False), (fo + 20, False)}                     # the smallest and the biggest value
        out |= {(fo + 4 * (9 + n) + 16 * k, False) for k in range(n)}  # the keys
    p6, n6 = secs[6]
    for i in range(n6):
        aid, f1, f2, fo = struct.unpack_from("<i4xi4xi12xi", d, p6 + 64 * i)
        if aid - ACTION_BASE in BLOOM_ACTIONS and f2 >= 9:
            out.add((fo + 4 * f1 + 20, True))
    for at, _ in out:
        if not 0 <= at <= len(d) - 16:
            raise FxrError("a colour at %#x lies outside the file" % at)
    return sorted(out)


def plan_text(eid: str, d: bytes) -> str:
    lines = ['    "%s": {' % eid, '        "size": %d,' % len(d), '        "colours": [']
    lines += ['            (%#x, "%s", %s),' % (at, d[at:at + 16].hex(), bloom) for at, bloom in places(d)]
    return "\n".join(lines + ["        ],", "    },"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="print the colour plan of an FXR file for writer/fxr_plans.py")
    ap.add_argument("file", nargs="+")
    a = ap.parse_args(argv)
    for f in a.file:
        p = Path(f)
        try:
            print(plan_text(p.stem.lstrip("f").lstrip("0"), p.read_bytes()))
        except (OSError, FxrError) as exc:
            print(f"{p}: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

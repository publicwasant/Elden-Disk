#!/usr/bin/env python3
"""LEGACY (the approach that FAILED in game): a no-op regulation.bin whose listed zstd blocks are stored RAW.

    python legacy_raw_noop.py --name S6 15 75 135 195 255 315
    python make_u_noop.py --name U6 15 75 135 195 255 315      # same blocks, but re-written as COMPRESSED blocks (passes)

The decoded body is byte-identical to the original in both cases; only the frame layout differs.
The game rejects the first kind (S6 -> "Failed to save game. Save data is corrupted") and accepts the second (U6).
Blocks that cannot be stored raw in isolation (their successor depends on rep-offset state) are added automatically.
"""
import argparse, io, os, struct, zstandard
import erlib, erreg
from blockedit import SRC, OUT

ap = argparse.ArgumentParser(); ap.add_argument("--name", required=True); ap.add_argument("blocks", type=int, nargs="+")
a = ap.parse_args()
raw, dcx, body, hdr, bnd = erlib.load_regulation(SRC)
S = erlib.SplitSplicer(dcx)
r = set(a.blocks)
while True:                                   # closure: add every block that no longer decodes right
    f = S._build(r, body); bad = S._first_bad(f, body)
    if bad is None: break
    r.add(bad)
cand = [i for i in sorted(r) if i != len(S.blocks) - 1]
for pieces in range(1, 17):                   # hit the "2 zero bytes of padding" shape by cutting one stored block in pieces
    f = S._build_split(r, body, cand[0], pieces)
    if (-(len(S.header) + len(f))) % 16 == 2: break
assert zstandard.ZstdDecompressor().stream_reader(io.BytesIO(f)).read() == body
h = bytearray(S.header); struct.pack_into(">II", h, 0x1C, len(body), len(f))
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, "regulation.%s.bin" % a.name), "wb").write(erreg.encrypt(bytes(h) + f))
print("raw (stored) blocks:", sorted(r))

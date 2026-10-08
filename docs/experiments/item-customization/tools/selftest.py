#!/usr/bin/env python3
"""Sanity checks that do not need the game. Run this first."""
import struct, erreg, erlib, zdec, fse
from blockedit import Orig, SRC
from seqparse import parse_block
raw = open(SRC, "rb").read()
dcx = erreg.decrypt(raw)
assert dcx[:4] == b"DCX\0", "AES key / file is wrong"
body, hdr = erlib.dcx_unpack(dcx)
print("1. decrypt + zstd OK, body", len(body), "bytes")
assert erlib.Bnd4(body).build() == body
print("2. BND4 parse -> build is byte-identical")
raw2, dcx2, body2, _, bnd = erlib.load_regulation(SRC)
ok = skipped = 0
for e in bnd.entries:
    if not e.name.endswith(".param"): continue
    try: P = erlib.Param(e.data)
    except AssertionError: skipped += 1; continue      # a few tables use another layout (not needed here)
    assert P.build() == e.data, e.name
    ok += 1
print("3. %d .param tables parse and rebuild byte-identical (%d use another layout and are not touched)" % (ok, skipped))
for n in ("EquipParamGoods", "Magic", "SpEffectParam", "ShopLineupParam"): erlib.Param(bnd.get(n).data)
O = Orig()
assert zdec.decode_frame(O.fr) == O.body
print("4. pure-Python zstd decoder reproduces the whole body")
D = zdec.Dec(); n = 0
for i, (p, ty, size, last) in enumerate(O.blocks):
    c = O.fr[p+3:p+3+size]
    if ty == 0: D.stored(c); continue
    if i in (3, 100, 426, 433, 515):
        info = parse_block(D, c)
        seqs = [(ll, ml, ofv) for ll, ml, ofv, off, kind in info["seqs"]]
        got, _ = fse.decode_triples(fse.encode_sequences(seqs)); assert got == seqs; n += 1
    D.block(c)
print("5. FSE sequence encoder round-trips on", n, "real blocks")
print("ALL OK")

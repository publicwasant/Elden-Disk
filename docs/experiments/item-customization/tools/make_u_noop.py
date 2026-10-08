#!/usr/bin/env python3
"""The PASSING counterpart of legacy_raw_noop.py (tests U6 / U32): the same blocks, rewritten as COMPRESSED blocks
that carry RAW LITERALS + the original sequence section byte for byte. Decoded body unchanged, rep-offset state
unchanged, Huffman state unchanged (a raw-literals block does not touch it; treeless followers are converted too).

    python make_u_noop.py --name U6 15 75 135 195 255 315
    python make_u_noop.py --name U32 $(seq 2 33)
"""
import argparse, struct
import zdec, erlib
from blockedit import Orig, pack_file, write_file, verify
O = Orig()

ap = argparse.ArgumentParser(); ap.add_argument("--name", required=True); ap.add_argument("blocks", type=int, nargs="+")
a = ap.parse_args()
todo = set(a.blocks)
for t in list(todo):                          # a type-2 (new Huffman tree) block feeds the treeless blocks after it
    if O.info[t].get("lit", (None,))[0] == 2:
        j = t + 1
        while j < len(O.info) and O.info[j].get("lit", (None,))[0] == 3: todo.add(j); j += 1
D = zdec.Dec(); res = {}
for i, (p, ty, size, last) in enumerate(O.blocks):
    c = O.fr[p + 3:p + 3 + size]
    if ty == 0: D.stored(c); continue
    if i in todo:
        lit, q = D.literals(c, 0)             # decoded literals; the sequence section c[q:] is kept as it is
        res[i] = (lit, bytes(c[q:]))
    D.block(c)
fr = pack_file(O, res)
write_file(O, fr, a.name); verify(a.name, O.body)
print("converted blocks:", sorted(res))

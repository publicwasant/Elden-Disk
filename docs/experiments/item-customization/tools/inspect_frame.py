#!/usr/bin/env python3
"""Print the block/feature census of the zstd frame inside a regulation.bin."""
import collections
from blockedit import Orig
O = Orig()
print("blocks", len(O.blocks), "frame bytes", len(O.fr), "body bytes", len(O.body), "frame header", O.fhdr.hex())
c = collections.Counter()
for x in O.info:
    c[("block type", x["ty"])] += 1
    if "lit" in x: c[("literals type/size-format", x["lit"])] += 1
    for k in ("ll", "of", "ml"):
        if k in x: c[("seq mode " + k, x[k])] += 1
for k, v in sorted(c.items(), key=str): print(k, v)

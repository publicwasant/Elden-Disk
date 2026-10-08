#!/usr/bin/env python3
"""Dump / diff rows of any param table.  python inspect_rows.py Magic MagicParam 6421 6050"""
import sys, erlib, erdefs
from blockedit import SRC
raw, dcx, body, hdr, bnd = erlib.load_regulation(sys.argv[5] if len(sys.argv) > 5 else SRC)
tn, dn, a, b = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
P = erlib.Param(bnd.get(tn).data); d = erdefs.Def(dn)
ra, rb = P.find(a), P.find(b)
print("%-36s %14s %14s" % (tn, a, b))
for n in d.order:
    if n.startswith(("pad", "dummy")): continue
    try: va, vb = d.get(ra[2], n), d.get(rb[2], n)
    except KeyError: continue
    if va != vb: print("%-36s %14s %14s" % (n, va, vb))

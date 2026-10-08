"""Build a regulation whose changed blocks are re-encoded as *compressed* blocks (raw literals + re-segmented sequences),
keeping the rep-offset transitions of the original so that neighbouring original blocks decode unchanged."""
import struct, sys
import erreg, erlib, zdec, fse
from blockedit import *
from seqparse import parse_block

BS = 65536

def ofv_for(kind, off, ll):
    if kind == "push": return off + 3
    if kind == "r0":
        assert ll > 0; return 1
    if kind == "r1": return 2 if ll > 0 else 1
    if kind == "r2": return 3 if ll > 0 else 2
    if kind == "r3":
        assert ll == 0; return 3
    raise ValueError(kind)

def options(state, X, ll):
    """all (ofv, newstate) that decode to offset X from rep-state `state` with literal length ll."""
    r0, r1, r2 = state
    res = [(X + 3, (X, r0, r1))]
    for ofv in (1, 2, 3):
        idx = ofv - 1 + (1 if ll == 0 else 0)
        off = r0 if idx == 0 else (r1 if idx == 1 else (r2 if idx == 2 else r0 - 1))
        if off != X or off <= 0: continue
        if idx == 0: ns = (r0, r1, r2)
        elif idx == 1: ns = (r1, r0, r2)
        elif idx == 2: ns = (r2, r0, r1)
        else: ns = (off, r0, r1)
        res.append((ofv, ns))
    return res

def encode_offsets(seqs, rep_start, rep_end):
    """seqs: [(ll, ml, X)] -> [(ll, ml, ofv)] such that decoding from rep_start ends in rep_end (DP over rep states)."""
    layer = {tuple(rep_start): None}; hist = []
    for (ll, ml, X) in seqs:
        nxt = {}
        for st in layer:
            for ofv, ns in options(st, X, ll):
                if ns not in nxt: nxt[ns] = (st, ofv)
        hist.append(nxt); layer = nxt
    end = tuple(rep_end)
    if end not in layer: raise RuntimeError("rep state not reachable (%d states in last layer)" % len(layer))
    out = []; st = end
    for k in range(len(seqs) - 1, -1, -1):
        prev, ofv = hist[k][st]
        out.append((seqs[k][0], seqs[k][1], ofv)); st = prev
    return out[::-1]

def resegment(info, a, nb):
    """-> (literals, [(ll, ml, ofv)]). Old matches that are still valid stay; broken ones keep only their valid runs (>=3) or vanish;
    the rep-offset encodings are then re-chosen by DP so that the block ends in the original rep state."""
    olds = []; pos = a
    for (ll, ml, ofv, off, kind) in info["seqs"]:
        pos += ll; olds.append((pos, pos + ml, off)); pos += ml
    end = a + BS
    out = []; lits = bytearray(); emitted = a
    for k, (ms, me, off) in enumerate(olds):
        runs = []; j = max(ms, emitted)
        while j < me:
            if j - off >= 0 and nb[j] == nb[j - off]:
                q = j
                while q < me and q - off >= 0 and nb[q] == nb[q - off]: q += 1
                if q - j >= 3: runs.append((j, q))
                j = q
            else: j += 1
        for (rs, re_) in runs:
            lits += nb[emitted:rs]
            out.append((rs - emitted, re_ - rs, off)); emitted = re_
    lits += nb[emitted:end]
    return bytes(lits), encode_offsets(out, info["rep0"], info["rep1"])

def reencode(O, newbody, edit, treeless_follow=True):
    """edit: set of block indices whose output changed (or must be re-segmented). Returns {i: (lit, rest)}."""
    D = zdec.Dec(); res = {}
    todo = set(edit)
    for t in list(edit):
        if O.info[t].get("lit", (None,))[0] == 2 and treeless_follow:
            j = t + 1
            while j < len(O.info) and O.info[j].get("lit", (None,))[0] == 3: todo.add(j); j += 1
    for i, (p, ty, size, last) in enumerate(O.blocks):
        c = O.fr[p+3:p+3+size]
        if ty == 0: D.stored(c); continue
        if i in todo:
            a = i * BS
            if i in edit:
                info = parse_block(D, c)
                lits, seqs = resegment(info, a, newbody)
                same = (len(seqs) == info["nseq"] and all(s[:2] == (x[0], x[1]) for s, x in zip(seqs, info["seqs"])))
                res[i] = (lits, fse.encode_sequences(seqs))
            else:   # treeless follower: only swap the literal section
                lit, q = D.literals(c, 0)
                res[i] = (lit, bytes(c[q:]))
        D.block(c)
    return res

def build(name, newbody, edit0, pad_to=2, max_iter=12):
    edit = set(edit0)
    for it in range(max_iter):
        res = reencode(O, newbody, edit)
        fr = pack_file(O, res, pad_to=pad_to)
        h = bytearray(O.dhdr); struct.pack_into(">II", h, 0x1C, len(newbody), len(fr))
        dd = bytes(h) + fr
        pad = (-len(dd)) % 16; dd += bytes(pad)
        body2, _ = erlib.dcx_unpack(dd)
        if body2 == newbody:
            write_file(O, fr, name); verify(name, newbody)
            print("edited blocks:", sorted(edit), "| converted:", sorted(set(res) - edit))
            return fr
        bad = next(k for k in range(len(newbody)) if body2[k:k+1] != newbody[k:k+1]) // BS if len(body2) == len(newbody) else None
        print("iteration", it, "first bad block", bad, "-> adding to edit set")
        edit.add(bad)
    raise RuntimeError("no fixpoint")

O = Orig()

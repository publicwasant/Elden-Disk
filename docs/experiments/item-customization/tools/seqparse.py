import struct, zdec
from blockedit import *

def run_to(O, upto):
    """Dec positioned before block `upto` (standard semantics)."""
    D = zdec.Dec()
    for i in range(upto):
        p, ty, size, last = O.blocks[i]
        c = O.fr[p+3:p+3+size]
        if ty == 0: D.stored(c)
        else: D.block(c)
    return D

def parse_block(D, c):
    """Return dict(lit, seqs=[(ll, ml, ofv, off)], nseq, rep_before, rep_after, tail_lit) without mutating D (works on a copy of state)."""
    import copy
    D2 = zdec.Dec(); D2.rep = list(D.rep); D2.tabs = dict(D.tabs); D2.huf = D.huf
    D2.out = bytearray()
    rep0 = list(D2.rep)
    lit, p = D2.literals(c, 0)
    # replicate sequence decoding to capture triples
    b0 = c[p]
    if b0 < 128: nseq = b0; p += 1
    elif b0 < 255: nseq = ((b0 - 128) << 8) + c[p+1]; p += 2
    else: nseq = c[p+1] + (c[p+2] << 8) + 0x7F00; p += 3
    seqs = []
    if nseq:
        m = c[p]; p += 1
        p = D2.seq_table("ll", (m >> 6) & 3, c, p, zdec.LL_DEF, 35)
        p = D2.seq_table("of", (m >> 4) & 3, c, p, zdec.OF_DEF, 31)
        p = D2.seq_table("ml", (m >> 2) & 3, c, p, zdec.ML_DEF, 52)
        br = zdec.RBits(c[p:])
        (llc, llacc), (ofc, ofacc), (mlc, mlacc) = D2.tabs["ll"], D2.tabs["of"], D2.tabs["ml"]
        sll = br.read(llacc); sof = br.read(ofacc); sml = br.read(mlacc)
        rep = D2.rep
        for i in range(nseq):
            ofs, ofnb, ofbase = ofc[sof]; mls, mlnb, mlbase = mlc[sml]; lls, llnb, llbase = llc[sll]
            ofv = (1 << ofs) + br.read(ofs)
            ml = zdec.ML_BASE[mls] + br.read(zdec.ML_BITS[mls])
            ll = zdec.LL_BASE[lls] + br.read(zdec.LL_BITS[lls])
            if i != nseq - 1:
                sll = llbase + br.read(llnb); sml = mlbase + br.read(mlnb); sof = ofbase + br.read(ofnb)
            if ofv > 3:
                off = ofv - 3; rep[2] = rep[1]; rep[1] = rep[0]; rep[0] = off; kind = "push"
            else:
                idx = ofv - 1 + (1 if ll == 0 else 0)
                if idx == 0: off = rep[0]; kind = "r0"
                else:
                    off = rep[0] - 1 if idx == 3 else rep[idx]
                    if idx >= 2: rep[2] = rep[1]
                    rep[1] = rep[0]; rep[0] = off; kind = "r%d" % idx
            seqs.append((ll, ml, ofv, off, kind))
    return dict(lit=lit, seqs=seqs, nseq=nseq, rep0=rep0, rep1=list(D2.rep), seqstart=p)

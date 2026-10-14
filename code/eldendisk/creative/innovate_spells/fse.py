"""FSE/zstd sequence-section encoder (modes: FSE-compressed tables only, like the original encoder)."""
import bisect
from . import zstd as zdec

def ceil_log2(x): return (x - 1).bit_length() if x > 1 else 0

def pick_tl(n, distinct, maxlog):
    tl = max(5, min(maxlog, ceil_log2(n) - 1 if n > 2 else 5))
    tl = max(tl, ceil_log2(distinct) if distinct > 1 else 5, 5)
    return min(max(tl, 5), 9 if maxlog <= 9 else maxlog)

def normalize(counts, tl):
    """counts: list (index=symbol). returns norm list with each present symbol >= 1, summing to 2**tl."""
    N = 1 << tl; T = sum(counts)
    present = [s for s, c in enumerate(counts) if c]
    assert len(present) <= N
    norm = [0] * len(counts)
    for s in present:
        norm[s] = max(1, (counts[s] * N * 2 + T) // (2 * T))
    diff = N - sum(norm)
    order = sorted(present, key=lambda s: -counts[s])
    k = 0
    while diff != 0:
        s = order[k % len(order)]
        if diff > 0: norm[s] += 1; diff -= 1
        elif norm[s] > 1: norm[s] -= 1; diff += 1
        k += 1
    return norm

class BW:
    def __init__(self): self.acc = 0; self.n = 0
    def put(self, v, nb):
        assert 0 <= v < (1 << nb) or nb == 0
        self.acc |= v << self.n; self.n += nb
    def bytes_(self):
        return self.acc.to_bytes((self.n + 7) // 8, "little")

def write_ncount(norm, tl):
    bw = BW(); bw.put(tl - 5, 4)
    N = 1 << tl; rem = N + 1; thr = N; nb = tl + 1
    sym = 0; prev0 = False; A = len(norm)
    while sym < A and rem > 1:
        if prev0:
            start = sym
            while sym < A and norm[sym] == 0: sym += 1
            if sym == A: break
            z = sym - start
            while z >= 3: bw.put(3, 2); z -= 3
            bw.put(z, 2)
        cnt = norm[sym]; sym += 1
        mx = (2 * thr - 1) - rem
        rem -= abs(cnt)
        cnt += 1
        if cnt >= thr: cnt += mx
        if cnt < mx: bw.put(cnt, nb - 1)
        else: bw.put(cnt, nb)
        prev0 = (cnt == 1)
        assert rem >= 1
        while rem < thr: nb -= 1; thr >>= 1
    return bw.bytes_()

class Enc:
    def __init__(self, counts, maxlog):
        distinct = sum(1 for c in counts if c)
        if distinct == 1:                      # avoid single-symbol tables: add a never-used neighbour
            s = [i for i, c in enumerate(counts) if c][0]
            counts = list(counts); counts[s + 1 if s + 1 < len(counts) else s - 1] = 1; counts[s] = 1000000
            self.fake = True
        tl = pick_tl(sum(counts), sum(1 for c in counts if c), maxlog)
        self.tl = tl
        self.norm = normalize(counts, tl)
        while self.norm and self.norm[-1] == 0: self.norm.pop()
        self.cells, _ = zdec.build_fse(self.norm, tl)
        self.by = {}
        for d, (s, nb, base) in enumerate(self.cells): self.by.setdefault(s, []).append((base, nb, d))
        for s in self.by: self.by[s].sort()
        self.starts = {s: [b for b, _, _ in v] for s, v in self.by.items()}
        self.header = write_ncount(self.norm, tl)
    def prev(self, s, v):
        i = bisect.bisect_right(self.starts[s], v) - 1
        base, nb, d = self.by[s][i]
        assert base <= v < base + (1 << nb)
        return d, v - base, nb

def codes(ll, ml, ofv):
    # the last code whose base is <= the value (the bases rise: a bisection finds the same code as a scan of all of them)
    lc = bisect.bisect_right(zdec.LL_BASE, ll) - 1
    mc = bisect.bisect_right(zdec.ML_BASE, ml) - 1
    oc = ofv.bit_length() - 1
    return lc, mc, oc, ll - zdec.LL_BASE[lc], ml - zdec.ML_BASE[mc], ofv - (1 << oc)

def encode_sequences(seqs):
    """seqs: [(ll, ml, ofv)] -> bytes of the sequence section (nseq header, modes, tables, bitstream)."""
    n = len(seqs)
    assert n > 0
    C = [codes(*s) for s in seqs]
    cnt = {"ll": [0] * 36, "ml": [0] * 53, "of": [0] * 32}
    for lc, mc, oc, *_ in C: cnt["ll"][lc] += 1; cnt["ml"][mc] += 1; cnt["of"][oc] += 1
    E = {"ll": Enc(cnt["ll"], 9), "ml": Enc(cnt["ml"], 9), "of": Enc(cnt["of"], 8)}
    # states backwards
    dll = [0] * n; dml = [0] * n; dof = [0] * n
    upd = [None] * n     # bits for transition i-1 -> i : (ll,v,nb),(ml..),(of..)
    def first(e, s): return e.by[s][0][2]
    dll[n-1] = first(E["ll"], C[n-1][0]); dml[n-1] = first(E["ml"], C[n-1][1]); dof[n-1] = first(E["of"], C[n-1][2])
    for i in range(n - 2, -1, -1):
        a, va, na = E["ll"].prev(C[i][0], dll[i+1]); b, vb, nb_ = E["ml"].prev(C[i][1], dml[i+1]); c, vc, nc = E["of"].prev(C[i][2], dof[i+1])
        dll[i], dml[i], dof[i] = a, b, c
        upd[i+1] = ((va, na), (vb, nb_), (vc, nc))
    items = [(dll[0], E["ll"].tl), (dof[0], E["of"].tl), (dml[0], E["ml"].tl)]
    for i in range(n):
        lc, mc, oc, lx, mx, ox = C[i]
        items += [(ox, oc), (mx, zdec.ML_BITS[mc]), (lx, zdec.LL_BITS[lc])]
        if i < n - 1:
            items += [upd[i+1][0], upd[i+1][1], upd[i+1][2]]
    bw = BW()
    for v, nb in reversed(items):
        if nb: bw.put(v, nb)
    bw.put(1, 1)
    stream = bw.bytes_()
    hdr = bytes([n]) if n < 128 else bytes([(n >> 8) + 128, n & 255]) if n < 0x7F00 else bytes([255, (n - 0x7F00) & 255, (n - 0x7F00) >> 8])
    return hdr + bytes([0xA8]) + E["ll"].header + E["of"].header + E["ml"].header + stream

def decode_triples(sec):
    """Decode a sequence section (nseq header onwards) into [(ll, ml, ofv)] using zdec's table logic."""
    D = zdec.Dec(); c = sec; p = 0
    b0 = c[p]
    if b0 < 128: nseq = b0; p += 1
    elif b0 < 255: nseq = ((b0 - 128) << 8) + c[p+1]; p += 2
    else: nseq = c[p+1] + (c[p+2] << 8) + 0x7F00; p += 3
    m = c[p]; p += 1
    p = D.seq_table("ll", (m >> 6) & 3, c, p, zdec.LL_DEF, 35)
    p = D.seq_table("of", (m >> 4) & 3, c, p, zdec.OF_DEF, 31)
    p = D.seq_table("ml", (m >> 2) & 3, c, p, zdec.ML_DEF, 52)
    br = zdec.RBits(c[p:])
    (llc, llacc), (ofc, ofacc), (mlc, mlacc) = D.tabs["ll"], D.tabs["of"], D.tabs["ml"]
    sll = br.read(llacc); sof = br.read(ofacc); sml = br.read(mlacc)
    out = []
    for i in range(nseq):
        ofs, ofnb, ofbase = ofc[sof]; mls, mlnb, mlbase = mlc[sml]; lls, llnb, llbase = llc[sll]
        ofv = (1 << ofs) + br.read(ofs)
        ml = zdec.ML_BASE[mls] + br.read(zdec.ML_BITS[mls])
        ll = zdec.LL_BASE[lls] + br.read(zdec.LL_BITS[lls])
        if i != nseq - 1:
            sll = llbase + br.read(llnb); sml = mlbase + br.read(mlnb); sof = ofbase + br.read(ofnb)
        out.append((ll, ml, ofv))
    assert not br.overflow()
    return out, p

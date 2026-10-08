"""Block-level editing of the original zstd frame: keep every block, but rewrite chosen ones as *compressed* blocks
with raw literals + the original sequence section (state preserving: reps, FSE tables are per block, huf table kept)."""
import os, struct, erreg, erlib, zdec

SRC = os.environ.get("ER_REGULATION", "regulation.orig.bin")   # the untouched game file
OUT = os.environ.get("ER_OUT", "out")

class Orig:
    def __init__(self, path=None):
        path = path or SRC
        self.raw, self.dcx, self.body, self.hdr, self.bnd = erlib.load_regulation(path)
        d = erreg.decrypt(open(path, "rb").read())
        self.dhdr = bytearray(d[:0x4C])
        comp = struct.unpack(">I", d[0x20:0x24])[0]
        self.fr = d[0x4C:0x4C + comp]
        self.fhdr = self.fr[:6]
        self.blocks = []   # (hdr_off, ty, size, last)
        p = 6
        while True:
            h = self.fr[p] | self.fr[p+1] << 8 | self.fr[p+2] << 16
            ty = (h >> 1) & 3; size = h >> 3
            self.blocks.append((p, ty, size, h & 1))
            p += 3 + (size if ty != 1 else 1)
            if h & 1: break
        self.end = p
        self.info = self._census()   # per block: ty, size, lit=(type,sf), ll/of/ml sequence modes


    def _census(self):
        D = zdec.Dec(); info = []; cur = {}
        ol, os_ = D.literals, D.seq_table
        def lit(dd, p):
            b0 = dd[p]; cur["lit"] = (b0 & 3, (b0 >> 2) & 3); return ol(dd, p)
        def st(which, mode, dd, p, deflt, ms):
            cur[which] = mode; return os_(which, mode, dd, p, deflt, ms)
        D.literals = lit; D.seq_table = st
        for (p, ty, size, last) in self.blocks:
            cur = {"ty": ty, "size": size}
            c = self.fr[p + 3:p + 3 + size]
            if ty == 0: D.stored(c)
            elif ty == 1: D.stored(bytes([c[0]]) * size)
            else: D.block(c)
            info.append(cur)
        return info

    def content(self, i):
        p, ty, size, last = self.blocks[i]
        return self.fr[p+3:p+3+size]

def lit_section_len(c):
    b0 = c[0]; ty = b0 & 3; sf = (b0 >> 2) & 3
    if ty in (0, 1):
        if sf in (0, 2): n, hl = b0 >> 3, 1
        elif sf == 1: n, hl = (b0 >> 4) | (c[1] << 4), 2
        else: n, hl = (b0 >> 4) | (c[1] << 4) | (c[2] << 12), 3
        return (n if ty == 0 else 1) + hl
    if sf in (0, 1): comp = (int.from_bytes(c[:3], "little") >> 14) & 0x3FF; hl = 3
    elif sf == 2: comp = int.from_bytes(c[:4], "little") >> 18; hl = 4
    else: comp = int.from_bytes(c[:5], "little") >> 22; hl = 5
    return hl + comp

def raw_lit_header(n):
    if n < 32: return bytes([n << 3])
    if n < 4096: return bytes([(n << 4) | 4 | 0, n >> 4]) if False else bytes([((n & 15) << 4) | 4, n >> 4])
    return bytes([((n & 15) << 4) | 12, (n >> 4) & 255, n >> 12])

def decode_literals(O, i, st):
    """literals of block i given decoder state st (a zdec.Dec positioned before block i)."""
    c = O.content(i)
    lit, p = st.literals(c, 0)
    return lit, p

def to_raw_literals(O, i, st):
    c = O.content(i)
    lit, p = st.literals(c, 0)
    # st.huf may have been updated by this call; caller manages state by running the real decoder separately
    return raw_lit_header(len(lit)) + lit + bytes(c[p:])

def assemble(O, newcontent):
    """newcontent: {block index: new compressed content}. Returns frame bytes."""
    out = bytearray(O.fhdr)
    n = len(O.blocks)
    for i, (p, ty, size, last) in enumerate(O.blocks):
        if i in newcontent:
            c = newcontent[i]; assert len(c) < 1 << 17
            out += struct.pack("<I", (len(c) << 3) | (2 << 1) | last)[:3] + c
        else:
            out += O.fr[p:p+3+(size if ty != 1 else 1)]
    return bytes(out)

def lit_header_form(n, form):
    """form 0 minimal, 1 = one byte longer, 2 = two bytes longer (all legal size formats)"""
    if n < 32: forms = [1, 2, 3]
    elif n < 4096: forms = [2, 3]
    else: forms = [3]
    k = forms[min(form, len(forms) - 1)]
    if k == 1: return bytes([n << 3])
    if k == 2: return bytes([((n & 15) << 4) | 4, n >> 4])
    return bytes([((n & 15) << 4) | 12, (n >> 4) & 255, n >> 12])

def pack_file(O, newcontent_forms, pad_to=2, free_knobs=20):
    """Adjust literal-size-format byte counts (all legal) so that len(hdr+frame) % 16 == 16-pad_to.
    Extra knobs: already-raw-literal blocks re-emitted with a longer header form."""
    nf = dict(newcontent_forms)
    cand = []
    for i, x in enumerate(O.info):
        if i in nf or x.get("ty") != 2 or x.get("lit", (None,))[0] != 0: continue
        c = O.content(i)
        b0 = c[0]; sf = (b0 >> 2) & 3
        hl = 1 if sf in (0, 2) else 2 if sf == 1 else 3
        n = (b0 >> 3) if hl == 1 else ((b0 >> 4) | (c[1] << 4)) if hl == 2 else ((b0 >> 4) | (c[1] << 4) | (c[2] << 12))
        if n < 4096: cand.append((i, c[hl:hl+n], c[hl+n:]))
        if len(cand) >= free_knobs: break
    base = dict(nf)
    for i, lit, rest in cand: base[i] = (lit, rest)
    idx = sorted(base)
    def build(forms):
        nc = {}
        for i, f in zip(idx, forms):
            lit, rest = base[i]
            nc[i] = lit_header_form(len(lit), f) + lit + rest
        return assemble(O, nc)
    import random
    rnd = random.Random(1)
    fs0 = [0] * len(idx)
    for attempt in range(20000):
        fs = fs0 if attempt == 0 else [rnd.choice((0, 0, 1, 2)) for _ in idx]
        # forced-minimal for targets? no: any form is legal
        fr = build(fs)
        if (0x4C + len(fr)) % 16 == 16 - pad_to: return fr
    raise RuntimeError("no padding fit")

def write_file(O, fr, name):
    h = bytearray(O.dhdr); struct.pack_into(">II", h, 0x1C, len(O.body), len(fr))
    blob = erreg.encrypt(bytes(h) + fr)
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "regulation.%s.bin" % name), "wb").write(blob)
    return blob

def verify(name, expect_body):
    import hashlib
    dd = erreg.decrypt(open(os.path.join(OUT, "regulation.%s.bin" % name), "rb").read())
    b2, _ = erlib.dcx_unpack(dd)
    assert b2 == expect_body, "libzstd decode mismatch"
    comp = struct.unpack(">I", dd[0x20:0x24])[0]
    print("verified %s: %d bytes, trailing %d" % (name, len(dd), len(dd) - 0x4C - comp))

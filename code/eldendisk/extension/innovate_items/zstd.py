"""Pure-Python zstd decoder (standard library only).

It decodes exactly the frames this package reads and writes: the single frame inside the game's regulation.bin.
It is the one verifier the tool has at run time (about 2 s for the whole file), so it is strict: anything it does not
understand raises ZErr instead of guessing. libzstd is used only in the tests, as a second opinion."""
import struct

# ---------------------------------------------------------------- tables
LL_BASE = list(range(16)) + [16, 18, 20, 22, 24, 28, 32, 40, 48, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536]
LL_BITS = [0] * 16 + [1, 1, 1, 1, 2, 2, 3, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
ML_BASE = [i + 3 for i in range(32)] + [35, 37, 39, 41, 43, 47, 51, 59, 67, 83, 99, 131, 259, 515, 1027, 2051, 4099, 8195, 16387, 32771, 65539]
ML_BITS = [0] * 32 + [1, 1, 1, 1, 2, 2, 3, 3, 4, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
LL_DEF = ([4, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 2, 1, 1, 1, 1, 1, -1, -1, -1, -1], 6)
ML_DEF = ([1, 4, 3, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, -1, -1, -1, -1, -1, -1], 6)
OF_DEF = ([1, 1, 1, 1, 1, 1, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, -1, -1, -1, -1], 5)


class ZErr(Exception):
    pass


def hb(x):
    return x.bit_length() - 1


_FSE_CACHE = {}


def build_fse(norm, acc):
    """-> (cells, acc). The same table comes back for the same counts (most blocks share them): the cells are a tuple, never
    changed by a caller."""
    key = (tuple(norm), acc)
    hit = _FSE_CACHE.get(key)
    if hit is None:
        hit = _FSE_CACHE[key] = (tuple(_build_fse(norm, acc)), acc)
    return hit


def _build_fse(norm, acc):
    size = 1 << acc
    sym = [0] * size
    high = size - 1
    for s, c in enumerate(norm):
        if c == -1:
            sym[high] = s
            high -= 1
    step = (size >> 1) + (size >> 3) + 3
    mask = size - 1
    pos = 0
    for s, c in enumerate(norm):
        for _ in range(max(c, 0)):
            sym[pos] = s
            pos = (pos + step) & mask
            while pos > high:
                pos = (pos + step) & mask
    nxt = [(1 if c == -1 else max(c, 0)) for c in norm]
    cells = []
    for u in range(size):
        s = sym[u]
        ns = nxt[s]
        nxt[s] += 1
        nb = acc - hb(ns)
        cells.append((s, nb, (ns << nb) - size))
    return cells


def read_ncount(data, p, max_sym):
    """FSE normalized counts header. Returns (norm, acc, bytes_consumed)."""
    bits = int.from_bytes(data[p:p + 8], "little")
    bc = 0

    def take(n):
        nonlocal bits, bc
        v = bits & ((1 << n) - 1)
        bits >>= n
        bc += n
        return v

    acc = take(4) + 5
    rem = (1 << acc) + 1
    thr = 1 << acc
    nb = acc + 1
    norm = []
    prev0 = False
    cur = 0
    # we may need more than 64 bits for long zero runs: refill lazily
    def refill():
        nonlocal bits
        done = bc
        bits = int.from_bytes(data[p + (done >> 3): p + (done >> 3) + 8], "little") >> (done & 7)
    while rem > 1 and len(norm) <= max_sym:
        refill()
        if prev0:
            n0 = len(norm)
            while (bits & 0xFFFF) == 0xFFFF:
                n0 += 24
                take(16)
                refill()
            while (bits & 3) == 3:
                n0 += 3
                take(2)
                refill()
            n0 += take(2)
            while len(norm) < n0:
                norm.append(0)
            prev0 = False
            refill()
            if len(norm) > max_sym:
                break
        mx = (2 * thr - 1) - rem
        low = bits & (thr - 1)
        if low < mx:
            cnt = low
            take(nb - 1)
        else:
            cnt = bits & (2 * thr - 1)
            if cnt >= thr:
                cnt -= mx
            take(nb)
        cnt -= 1
        rem -= abs(cnt)
        norm.append(cnt)
        prev0 = cnt == 0
        while rem < thr:
            nb -= 1
            thr >>= 1
    if rem != 1:
        raise ZErr("bad ncount")
    return norm, acc, (bc + 7) >> 3


class RBits:
    """Backward bit reader over a stream whose last byte carries an end marker."""

    def __init__(self, data):
        if not data or data[-1] == 0:
            raise ZErr("bad stream end")
        self.d = data
        self.pos = (len(data) - 1) * 8 + hb(data[-1])     # bits left (marker excluded)

    def read(self, n):
        if n == 0:
            return 0
        self.pos -= n
        if self.pos >= 0:
            lo = self.pos >> 3
            hi = (self.pos + n - 1) >> 3
            return (int.from_bytes(self.d[lo:hi + 1], "little") >> (self.pos & 7)) & ((1 << n) - 1)
        # overflow: bits below position 0 are zeros
        k = -self.pos
        hi = (self.pos + n - 1) >> 3
        v = int.from_bytes(self.d[0:hi + 1], "little") & ((1 << (n - k)) - 1)
        return v << k

    def overflow(self):
        return self.pos < 0


def huff_weights(data, p):
    h = data[p]
    if h >= 128:
        n = h - 127
        nb = (n + 1) // 2
        w = []
        for i in range(n):
            b = data[p + 1 + i // 2]
            w.append(b >> 4 if i % 2 == 0 else b & 15)
        return w, 1 + nb
    norm, acc, used = read_ncount(data, p + 1, 12)
    cells, acc = build_fse(norm, acc)
    br = RBits(data[p + 1 + used:p + 1 + h])
    s1 = br.read(acc)
    s2 = br.read(acc)
    out = []
    while True:
        sy, nb, base = cells[s1]
        out.append(sy)
        s1 = base + br.read(nb)
        if br.overflow():
            out.append(cells[s2][0])
            break
        sy, nb, base = cells[s2]
        out.append(sy)
        s2 = base + br.read(nb)
        if br.overflow():
            out.append(cells[s1][0])
            break
        if len(out) > 255:
            raise ZErr("too many weights")
    return out, 1 + h


def huff_table(weights):
    tot = sum(1 << (w - 1) for w in weights if w)
    mb = hb(tot) + 1
    rem = (1 << mb) - tot
    if rem & (rem - 1) or rem == 0:
        raise ZErr("bad huffman weights")
    weights = list(weights) + [hb(rem) + 1]
    table = [None] * (1 << mb)
    pos = 0
    for w in range(1, mb + 1):
        for s, ww in enumerate(weights):
            if ww == w:
                n = mb + 1 - w
                cnt = 1 << (w - 1)
                for k in range(pos, pos + cnt):
                    table[k] = (s, n)
                pos += cnt
    return table, mb


def huff_stream(data, n, table, mb):
    br = RBits(data)
    out = bytearray()
    append, from_bytes = out.append, int.from_bytes
    mask = (1 << mb) - 1
    pos = br.pos
    wbase, win = pos + 1, 0           # `win` holds the stream's bits from bit `wbase` up (to at least `pos`): read 32 bytes at a time
    for _ in range(n):
        pos -= mb
        if pos >= wbase:
            v = (win >> (pos - wbase)) & mask
        elif pos >= 0:
            lo = max((pos >> 3) - 31, 0)
            win = from_bytes(data[lo:((pos + mb - 1) >> 3) + 1], "little")
            wbase = lo << 3
            v = (win >> (pos - wbase)) & mask
        else:
            k = -pos
            hi = (pos + mb - 1) >> 3
            v = (from_bytes(data[0:hi + 1], "little") & ((1 << (mb - k)) - 1)) << k
        s, nb = table[v]
        pos += mb - nb
        append(s)
    return bytes(out)


class Dec:
    """Decoder state that lives across blocks: the output so far, the three repeat offsets, the last Huffman tree.
    (Sequence FSE tables never carry over in this file: no block uses the 'repeat' mode; a stored block resets nothing.)"""

    def __init__(self):
        self.out = bytearray()
        self.rep = [1, 4, 8]
        self.tabs = {"ll": None, "of": None, "ml": None}
        self.huf = None

    def literals(self, d, p):
        b0 = d[p]
        ty = b0 & 3
        sf = (b0 >> 2) & 3
        if ty in (0, 1):
            if sf in (0, 2):
                n = b0 >> 3
                hl = 1
            elif sf == 1:
                n = (b0 >> 4) | (d[p + 1] << 4)
                hl = 2
            else:
                n = (b0 >> 4) | (d[p + 1] << 4) | (d[p + 2] << 12)
                hl = 3
            if ty == 0:
                return d[p + hl:p + hl + n], p + hl + n
            return bytes([d[p + hl]]) * n, p + hl + 1
        if sf in (0, 1):
            v = int.from_bytes(d[p:p + 3], "little")
            regen = (v >> 4) & 0x3FF
            comp = (v >> 14) & 0x3FF
            hl = 3
        elif sf == 2:
            v = int.from_bytes(d[p:p + 4], "little")
            regen = (v >> 4) & 0x3FFF
            comp = v >> 18
            hl = 4
        else:
            v = int.from_bytes(d[p:p + 5], "little")
            regen = (v >> 4) & 0x3FFFF
            comp = v >> 22
            hl = 5
        body = d[p + hl:p + hl + comp]
        q = 0
        if ty == 2:
            w, used = huff_weights(body, 0)
            self.huf = huff_table(w)
            q = used
        elif self.huf is None:
            raise ZErr("treeless literals without a tree")
        table, mb = self.huf
        if sf == 0:
            lit = huff_stream(body[q:], regen, table, mb)
        else:
            s1, s2, s3 = struct.unpack_from("<HHH", body, q)
            q += 6
            seg = (regen + 3) // 4
            parts = [body[q:q + s1], body[q + s1:q + s1 + s2], body[q + s1 + s2:q + s1 + s2 + s3], body[q + s1 + s2 + s3:]]
            sizes = [seg, seg, seg, regen - 3 * seg]
            lit = b"".join(huff_stream(parts[i], sizes[i], table, mb) for i in range(4))
        return lit, p + hl + comp

    def seq_table(self, which, mode, d, p, deflt, maxsym):
        if mode == 0:
            self.tabs[which] = build_fse(*deflt)
            return p
        if mode == 1:
            self.tabs[which] = ([(d[p], 0, 0)], 0)
            return p + 1
        if mode == 2:
            norm, acc, used = read_ncount(d, p, maxsym)
            self.tabs[which] = build_fse(norm, acc)
            return p + used
        if self.tabs[which] is None:
            raise ZErr("repeat table missing: " + which)
        return p

    def block(self, d):
        lit, p = self.literals(d, 0)
        b0 = d[p]
        if b0 < 128:
            nseq = b0
            p += 1
        elif b0 < 255:
            nseq = ((b0 - 128) << 8) + d[p + 1]
            p += 2
        else:
            nseq = d[p + 1] + (d[p + 2] << 8) + 0x7F00
            p += 3
        out = self.out
        if nseq == 0:
            out += lit
            return
        m = d[p]
        p += 1
        p = self.seq_table("ll", (m >> 6) & 3, d, p, LL_DEF, 35)
        p = self.seq_table("of", (m >> 4) & 3, d, p, OF_DEF, 31)
        p = self.seq_table("ml", (m >> 2) & 3, d, p, ML_DEF, 52)
        br = RBits(d[p:])
        (llc, llacc), (ofc, ofacc), (mlc, mlacc) = self.tabs["ll"], self.tabs["of"], self.tabs["ml"]
        sll = br.read(llacc)
        sof = br.read(ofacc)
        sml = br.read(mlacc)
        rep = self.rep
        r0, r1, r2 = rep               # the repeat offsets live in locals during the loop and go back into self.rep after it
        lp = 0
        bits, from_bytes = br.d, int.from_bytes
        last = nseq - 1
        for i in range(nseq):
            ofs, ofnb, ofbase = ofc[sof]
            mls, mlnb, mlbase = mlc[sml]
            lls, llnb, llbase = llc[sll]
            mlb, llb = ML_BITS[mls], LL_BITS[lls]
            # the six fields of a sequence lie next to each other in the stream: read them with one slice instead of six
            # br.read calls (same bits, same order); near the start of the stream, where br.read pads with zeros, read one by one
            r = ofs + mlb + llb + (llnb + mlnb + ofnb if i != last else 0)
            pos = br.pos - r
            if pos >= 0:
                br.pos = pos
                v = from_bytes(bits[pos >> 3:((pos + r - 1) >> 3) + 1], "little") >> (pos & 7) if r else 0
                r -= ofs
                ofv = (1 << ofs) + ((v >> r) & ((1 << ofs) - 1))
                r -= mlb
                ml = ML_BASE[mls] + ((v >> r) & ((1 << mlb) - 1))
                r -= llb
                ll = LL_BASE[lls] + ((v >> r) & ((1 << llb) - 1))
                if i != last:
                    r -= llnb
                    sll = llbase + ((v >> r) & ((1 << llnb) - 1))
                    r -= mlnb
                    sml = mlbase + ((v >> r) & ((1 << mlnb) - 1))
                    sof = ofbase + (v & ((1 << ofnb) - 1))
            else:
                ofv = (1 << ofs) + br.read(ofs)
                ml = ML_BASE[mls] + br.read(mlb)
                ll = LL_BASE[lls] + br.read(llb)
                if i != last:
                    sll = llbase + br.read(llnb)
                    sml = mlbase + br.read(mlnb)
                    sof = ofbase + br.read(ofnb)
            if ofv > 3:
                off = ofv - 3
                r2 = r1
                r1 = r0
                r0 = off
            else:
                idx = ofv - 1 + (1 if ll == 0 else 0)
                if idx == 0:
                    off = r0
                else:
                    off = r0 - 1 if idx == 3 else (r1 if idx == 1 else r2)
                    if idx >= 2:
                        r2 = r1
                    r1 = r0
                    r0 = off
            if off <= 0:
                rep[:] = [r0, r1, r2]
                raise ZErr("zero offset")
            out += lit[lp:lp + ll]
            lp += ll
            olen = len(out)
            if off > olen:
                rep[:] = [r0, r1, r2]
                raise ZErr("offset beyond start seq %d (ll=%d ml=%d ofv=%d ofcode=%d mlcode=%d llcode=%d off=%d rep=%s nseq=%d)" % (i, ll, ml, ofv, ofs, mls, lls, off, rep, nseq))
            st = olen - off
            if off >= ml:
                out += out[st:st + ml]
            else:
                chunk = bytes(out[st:])
                reps = ml // off + 1
                out += (chunk * reps)[:ml]
        rep[:] = [r0, r1, r2]
        out += lit[lp:]

    def stored(self, data):
        self.out += data


FRAME_HEADER = bytes([0x28, 0xB5, 0x2F, 0xFD, 0x00, 0x80])   # magic, no flags (no size, no checksum), 64 MiB window


def split_blocks(frame):
    """[(header offset, type, size, last)] of every block. Type 0 stored, 1 RLE, 2 compressed. Raises ZErr if malformed."""
    if bytes(frame[:6]) != FRAME_HEADER:
        raise ZErr("unexpected frame header %s" % bytes(frame[:6]).hex())
    blocks, p = [], 6
    while True:
        if p + 3 > len(frame):
            raise ZErr("frame ends inside a block header")
        h = frame[p] | frame[p + 1] << 8 | frame[p + 2] << 16
        ty, size, last = (h >> 1) & 3, h >> 3, h & 1
        if ty == 3:
            raise ZErr("reserved block type")
        blocks.append((p, ty, size, last))
        p += 3 + (1 if ty == 1 else size)
        if p > len(frame):
            raise ZErr("block runs past the end of the frame")
        if last:
            return blocks, p


def decode_frame(frame):
    """The decoded body of a frame made of the blocks above. Trailing bytes after the last block are returned unchecked
    by the caller (the file format pads with zeros)."""
    blocks, _ = split_blocks(frame)
    d = Dec()
    for p, ty, size, _last in blocks:
        if ty == 0:
            d.stored(frame[p + 3:p + 3 + size])
        elif ty == 1:
            d.stored(bytes([frame[p + 3]]) * size)
        else:
            d.block(frame[p + 3:p + 3 + size])
    return bytes(d.out)

"""Rewriting a zstd frame block by block.

The game accepts the frame it ships with and frames in which only some blocks were re-encoded as ordinary
*compressed* blocks; it rejected every frame that contained stored (raw) blocks or came from a general-purpose
encoder (handbook Chapters 9-11). So an edit is made like this:

* every 64 KiB block whose decoded bytes are unchanged is copied byte for byte;
* every changed block is re-encoded as a compressed block: raw literals + sequences that reuse the old matches that
  are still valid (the repeat-offset registers are steered so the block ends in the state the original block ended
  in, which keeps all following original blocks decodable);
* a block with Huffman-treeless literals that follows a replaced Huffman block is converted to raw literals too;
* the tail of the file is brought back to the original shape ("2 zero bytes after the frame") with legal variations
  of the literal-size header of untouched raw-literal blocks.
"""
from __future__ import annotations

import random
import struct

from . import fse, zstd

BS = 65536            # decoded bytes per block in the game's frame
TAIL_ZEROS = 2        # the original file has exactly 2 zero bytes after the frame (inside the AES padding)


class BuildError(Exception):
    pass


class Source:
    """The frame we start from (the game's own), decoded once, with the decoder state in front of every block."""

    def __init__(self, dcx: bytes):
        if bytes(dcx[:4]) != b"DCX\0" or bytes(dcx[0x28:0x2C]) != b"ZSTD":
            raise BuildError("not a DCX/ZSTD container")
        self.header = bytearray(dcx[:0x4C])
        comp = struct.unpack(">I", dcx[0x20:0x24])[0]
        self.frame = bytes(dcx[0x4C:0x4C + comp])
        self.blocks, end = zstd.split_blocks(self.frame)
        if end != comp:
            raise BuildError("frame size in the header does not match the blocks")
        if any(dcx[0x4C + comp:]):
            raise BuildError("non-zero bytes after the frame")
        self.rep_before: dict[int, list[int]] = {}
        self.huf_before: dict[int, object] = {}
        self.lit_type: dict[int, int] = {}
        d = zstd.Dec()
        for i, (p, ty, size, _last) in enumerate(self.blocks):
            c = self.frame[p + 3:p + 3 + size]
            if ty == 0:
                d.stored(c)
            elif ty == 1:
                d.stored(bytes([c[0]]) * size)
            else:
                self.rep_before[i], self.huf_before[i], self.lit_type[i] = list(d.rep), d.huf, c[0] & 3
                d.block(c)
        self.body = bytes(d.out)
        declared = struct.unpack(">I", dcx[0x1C:0x20])[0]
        if declared != len(self.body):
            raise BuildError("decoded size %d differs from the DCX header (%d)" % (len(self.body), declared))

    def content(self, i: int) -> bytes:
        p, ty, size, _ = self.blocks[i]
        return self.frame[p + 3:p + 3 + (1 if ty == 1 else size)]


# ---------------------------------------------------------------- one block: parse the old sequences
def parse_block(c: bytes, rep_before, huf_before) -> dict:
    """The literals and the sequences [(ll, ml, ofv, off, kind)] of a compressed block, plus its repeat-offset states."""
    d = zstd.Dec()
    d.rep, d.huf = list(rep_before), huf_before
    lit, p = d.literals(c, 0)
    b0 = c[p]
    if b0 < 128:
        nseq, p = b0, p + 1
    elif b0 < 255:
        nseq, p = ((b0 - 128) << 8) + c[p + 1], p + 2
    else:
        nseq, p = c[p + 1] + (c[p + 2] << 8) + 0x7F00, p + 3
    seqs = []
    if nseq:
        m = c[p]
        p += 1
        p = d.seq_table("ll", (m >> 6) & 3, c, p, zstd.LL_DEF, 35)
        p = d.seq_table("of", (m >> 4) & 3, c, p, zstd.OF_DEF, 31)
        p = d.seq_table("ml", (m >> 2) & 3, c, p, zstd.ML_DEF, 52)
        br = zstd.RBits(c[p:])
        (llc, llacc), (ofc, ofacc), (mlc, mlacc) = d.tabs["ll"], d.tabs["of"], d.tabs["ml"]
        sll, sof, sml = br.read(llacc), br.read(ofacc), br.read(mlacc)
        rep = d.rep
        for i in range(nseq):
            ofs, ofnb, ofbase = ofc[sof]
            mls, mlnb, mlbase = mlc[sml]
            lls, llnb, llbase = llc[sll]
            ofv = (1 << ofs) + br.read(ofs)
            ml = zstd.ML_BASE[mls] + br.read(zstd.ML_BITS[mls])
            ll = zstd.LL_BASE[lls] + br.read(zstd.LL_BITS[lls])
            if i != nseq - 1:
                sll = llbase + br.read(llnb)
                sml = mlbase + br.read(mlnb)
                sof = ofbase + br.read(ofnb)
            if ofv > 3:
                off = ofv - 3
                rep[2], rep[1], rep[0] = rep[1], rep[0], off
                kind = "push"
            else:
                idx = ofv - 1 + (1 if ll == 0 else 0)
                if idx == 0:
                    off, kind = rep[0], "r0"
                else:
                    off = rep[0] - 1 if idx == 3 else rep[idx]
                    if idx >= 2:
                        rep[2] = rep[1]
                    rep[1], rep[0] = rep[0], off
                    kind = "r%d" % idx
            seqs.append((ll, ml, ofv, off, kind))
    return dict(lit=lit, seqs=seqs, nseq=nseq, rep0=list(rep_before), rep1=list(d.rep))


# ---------------------------------------------------------------- choosing offset codes
def _options(state, x, ll):
    """All (ofv, new_state) that decode to offset x from the repeat-offset state `state` with literal length ll."""
    r0, r1, r2 = state
    res = [(x + 3, (x, r0, r1))]
    for ofv in (1, 2, 3):
        idx = ofv - 1 + (1 if ll == 0 else 0)
        off = r0 if idx == 0 else (r1 if idx == 1 else (r2 if idx == 2 else r0 - 1))
        if off != x or off <= 0:
            continue
        if idx == 0:
            ns = (r0, r1, r2)
        elif idx == 1:
            ns = (r1, r0, r2)
        elif idx == 2:
            ns = (r2, r0, r1)
        else:
            ns = (off, r0, r1)
        res.append((ofv, ns))
    return res


def encode_offsets(seqs, rep_start, rep_end):
    """[(ll, ml, offset)] -> [(ll, ml, ofv)] such that decoding from rep_start ends in rep_end (DP over the register states)."""
    layer = {tuple(rep_start): None}
    hist = []
    for ll, ml, x in seqs:
        nxt = {}
        for st in layer:
            for ofv, ns in _options(st, x, ll):
                if ns not in nxt:
                    nxt[ns] = (st, ofv)
        hist.append(nxt)
        layer = nxt
    end = tuple(rep_end)
    if end not in layer:
        raise BuildError("repeat-offset state not reachable (%d states in the last layer)" % len(layer))
    out, st = [], end
    for k in range(len(seqs) - 1, -1, -1):
        prev, ofv = hist[k][st]
        out.append((seqs[k][0], seqs[k][1], ofv))
        st = prev
    return out[::-1]


def resegment(info: dict, start: int, newbody: bytes):
    """-> (literals, [(ll, ml, ofv)]) for the block at body offset `start`. Old matches that are still valid stay; broken
    ones keep only their valid runs (>= 3 bytes) or vanish; everything else becomes literals."""
    olds, pos = [], start
    for ll, ml, _ofv, off, _kind in info["seqs"]:
        pos += ll
        olds.append((pos, pos + ml, off))
        pos += ml
    end = start + BS
    out, lits, emitted = [], bytearray(), start
    for ms, me, off in olds:
        runs, j = [], max(ms, emitted)
        while j < me:
            if j - off >= 0 and newbody[j] == newbody[j - off]:
                q = j
                while q < me and q - off >= 0 and newbody[q] == newbody[q - off]:
                    q += 1
                if q - j >= 3:
                    runs.append((j, q))
                j = q
            else:
                j += 1
        for rs, re_ in runs:
            lits += newbody[emitted:rs]
            out.append((rs - emitted, re_ - rs, off))
            emitted = re_
    lits += newbody[emitted:end]
    return bytes(lits), encode_offsets(out, info["rep0"], info["rep1"])


# ---------------------------------------------------------------- frame assembly
def _lit_header_form(n: int, form: int) -> bytes:
    """Raw-literals section header for n bytes; form 0 is the minimal one, 1 and 2 are longer but equally legal."""
    forms = [1, 2, 3] if n < 32 else [2, 3] if n < 4096 else [3]
    k = forms[min(form, len(forms) - 1)]
    if k == 1:
        return bytes([n << 3])
    if k == 2:
        return bytes([((n & 15) << 4) | 4, n >> 4])
    return bytes([((n & 15) << 4) | 12, (n >> 4) & 255, n >> 12])


def _assemble(src: Source, newcontent: dict, appended=()) -> bytes:
    """The frame: the source blocks (those in `newcontent` re-encoded) and the `appended` block contents (a longer body).
    The game's frame ends with an EMPTY stored block that carries the last flag (after the 826 data blocks); appended blocks go
    in front of it. A frame without such a block would pass the last flag on to the final appended block."""
    n_data = (len(src.body) + BS - 1) // BS
    sentinel = len(src.blocks) > n_data
    out = bytearray(src.frame[:6])

    def put_appended():
        for k, c in enumerate(appended):
            if len(c) >= 1 << 17:
                raise BuildError("appended block %d would exceed the 128 KiB block limit" % k)
            fin = 1 if (not sentinel and k == len(appended) - 1) else 0
            out.extend(struct.pack("<I", (len(c) << 3) | (2 << 1) | fin)[:3] + c)

    for i, (p, ty, size, last) in enumerate(src.blocks):
        if appended and i == n_data:
            put_appended()
        if appended and not sentinel:
            last = 0
        if i in newcontent:
            c = newcontent[i]
            if len(c) >= 1 << 17:
                raise BuildError("block %d would exceed the 128 KiB block limit" % i)
            out += struct.pack("<I", (len(c) << 3) | (2 << 1) | last)[:3] + c
        else:
            out += src.frame[p:p + 3 + (1 if ty == 1 else size)]
    if appended and not sentinel:
        put_appended()
    return bytes(out)


def _pack(src: Source, edited: dict, free_knobs: int = 20, appended=()) -> bytes:
    """Assemble the frame so that header + frame leaves exactly TAIL_ZEROS bytes of padding to a multiple of 16 (as in the
    original). The free knob is the literal-size header form of untouched raw-literal blocks."""
    cand = []
    for i, (p, ty, size, _last) in enumerate(src.blocks):
        if i in edited or ty != 2 or src.lit_type.get(i) != 0:
            continue
        c = src.content(i)
        sf = (c[0] >> 2) & 3
        hl = 1 if sf in (0, 2) else 2 if sf == 1 else 3
        n = (c[0] >> 3) if hl == 1 else ((c[0] >> 4) | (c[1] << 4)) if hl == 2 else ((c[0] >> 4) | (c[1] << 4) | (c[2] << 12))
        if n < 4096:
            cand.append((i, c[hl:hl + n], c[hl + n:]))
        if len(cand) >= free_knobs:
            break
    base = dict(edited)
    for i, lit, rest in cand:
        base[i] = (lit, rest)
    idx = sorted(base)
    rnd = random.Random(1)              # fixed seed: the same input always gives the same file
    for attempt in range(20000):
        forms = [0] * len(idx) if attempt == 0 else [rnd.choice((0, 0, 1, 2)) for _ in idx]
        nc = {i: _lit_header_form(len(base[i][0]), f) + base[i][0] + base[i][1] for i, f in zip(idx, forms)}
        fr = _assemble(src, nc, appended)
        if (0x4C + len(fr)) % 16 == 16 - TAIL_ZEROS:
            return fr
    raise BuildError("could not bring the file tail to the original shape")


def rewrite(src: Source, newbody: bytes, max_iter: int = 12):
    """New frame whose decoded body is `newbody` (same length as the source body).

    Returns (frame, edited_blocks, converted_blocks). Raises BuildError if no frame decodes back to newbody."""
    if len(newbody) != len(src.body):
        raise BuildError("the body length must not change (%d -> %d)" % (len(src.body), len(newbody)))
    edit = {i for i in range((len(newbody) + BS - 1) // BS) if newbody[i * BS:(i + 1) * BS] != src.body[i * BS:(i + 1) * BS]}
    if not edit:
        return src.frame, set(), set()
    for _ in range(max_iter):
        todo = set(edit)
        for t in list(edit):                       # blocks whose Huffman tree dies with the replaced block
            if src.lit_type.get(t) == 2:
                j = t + 1
                while j < len(src.blocks) and src.lit_type.get(j) == 3:
                    todo.add(j)
                    j += 1
        res = {}
        for i in sorted(todo):
            c = src.content(i)
            if i in edit:
                info = parse_block(c, src.rep_before[i], src.huf_before[i])
                lits, seqs = resegment(info, i * BS, newbody)
                res[i] = (lits, fse.encode_sequences(seqs))
            else:                                   # treeless follower: only the literals change form
                d = zstd.Dec()
                d.huf = src.huf_before[i]
                lit, q = d.literals(c, 0)
                res[i] = (lit, bytes(c[q:]))
        frame = _pack(src, res)
        got = zstd.decode_frame(frame)
        if got == newbody:
            return frame, edit, set(res) - edit
        bad = next(k for k in range(len(newbody)) if got[k:k + 1] != newbody[k:k + 1]) // BS if len(got) == len(newbody) else None
        if bad is None or bad in edit:
            raise BuildError("the rewritten frame does not decode to the intended body")
        edit.add(bad)
    raise BuildError("no fixed point after %d rounds" % max_iter)


def literal_block(raw: bytes) -> bytes:
    """The content of a compressed block that holds `raw` as raw literals and has no sequences (for appended data)."""
    return _lit_header_form(len(raw), 0) + raw + b"\x00"


def rewrite_grow(src: Source, newbody: bytes, max_iter: int = 12):
    """Like rewrite(), but newbody may be LONGER than the source body (data appended at the end; nothing is removed).

    The old last block is re-encoded (it gets more bytes), the blocks that changed are re-encoded as in rewrite(), and the
    appended data becomes new blocks of 64 KiB (compressed blocks with raw literals, no sequences). Returns
    (frame, edited_blocks, converted_blocks, appended_block_count)."""
    old_len = len(src.body)
    old_n = (old_len + BS - 1) // BS                 # blocks that hold data (the game's frame has one more: an empty last block)
    if len(newbody) < old_len:
        raise BuildError("rewrite_grow only appends (%d -> %d)" % (old_len, len(newbody)))
    nblocks = (len(newbody) + BS - 1) // BS
    appended = [literal_block(newbody[i * BS:(i + 1) * BS]) for i in range(old_n, nblocks)]
    edit = {i for i in range(old_n) if newbody[i * BS:(i + 1) * BS] != src.body[i * BS:(i + 1) * BS]}
    for _ in range(max_iter):
        todo = set(edit)
        for t in list(edit):
            if src.lit_type.get(t) == 2:
                j = t + 1
                while j < old_n and src.lit_type.get(j) == 3:
                    todo.add(j)
                    j += 1
        res = {}
        for i in sorted(todo):
            c = src.content(i)
            if i in edit:
                info = parse_block(c, src.rep_before[i], src.huf_before[i])
                lits, seqs = resegment(info, i * BS, newbody)
                res[i] = (lits, fse.encode_sequences(seqs))
            else:
                d = zstd.Dec()
                d.huf = src.huf_before[i]
                lit, q = d.literals(c, 0)
                res[i] = (lit, bytes(c[q:]))
        frame = _pack(src, res, appended=appended)
        got = zstd.decode_frame(frame)
        if got == newbody:
            return frame, edit, set(res) - edit, len(appended)
        bad = next((k for k in range(min(len(got), len(newbody))) if got[k] != newbody[k]), None)
        bad = None if bad is None else bad // BS
        if bad is None or bad in edit or bad >= old_n:
            raise BuildError("the rewritten frame does not decode to the intended body")
        edit.add(bad)
    raise BuildError("no fixed point after %d rounds" % max_iter)

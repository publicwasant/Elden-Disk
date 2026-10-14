"""Synthetic files for the design tests: a zstd frame of compressed blocks, a BND4 with PARAM tables, a DCX wrapper.
No game data needed; the encoders under test are the project's own, the decoders used as a second opinion are the project's
decoder and (when installed) the `zstandard` library."""
import random
import struct

from eldendisk.creative.innovate_spells import fse, zstd
from eldendisk.creative.innovate_spells.reblock import BS

FRAME_HEADER = bytes([0x28, 0xB5, 0x2F, 0xFD, 0x00, 0x80])


def raw_literals_header(n):
    if n < 32:
        return bytes([n << 3])
    if n < 4096:
        return bytes([((n & 15) << 4) | 4, n >> 4])
    return bytes([((n & 15) << 4) | 12, (n >> 4) & 255, n >> 12])


def compressed_block_content(lits: bytes, seqs):
    """seqs: [(ll, ml, offset)] pushing new offsets (ofv = offset + 3)."""
    sec = fse.encode_sequences([(ll, ml, off + 3) for ll, ml, off in seqs]) if seqs else b"\0"
    return raw_literals_header(len(lits)) + lits + sec


def make_block(rnd: random.Random, history: bytes, size=BS):
    light = len(history) > 0                      # blocks after the first copy a lot: few literals, as in the game's file
    """-> (content, decoded bytes) for one block of `size` decoded bytes; matches may reach into `history`."""
    out, lits, seqs, buf = bytearray(), bytearray(), [], bytearray(history)
    remaining = size
    while remaining > 0:
        ll = min(rnd.randint(0, 20) if light else rnd.randint(0, 300), remaining)
        chunk = bytes(rnd.randrange(256) for _ in range(ll)) if rnd.random() < 0.5 else bytes([rnd.randrange(8)] * ll)
        lits += chunk
        buf += chunk
        out += chunk
        remaining -= ll
        if remaining < 4 or (not light and rnd.random() < 0.05):
            if remaining:
                chunk = bytes(rnd.randrange(256) for _ in range(remaining))
                lits += chunk
                buf += chunk
                out += chunk
                remaining = 0
            break
        ml = min(rnd.randint(100, 600) if light else rnd.randint(3, 120), remaining)
        off = rnd.randint(1, len(buf))
        for _ in range(ml):
            buf.append(buf[-off])
            out.append(buf[-1])
        seqs.append((ll, ml, off))
        remaining -= ml
    # literals after the last sequence belong to the block, not to a sequence
    return compressed_block_content(bytes(lits), seqs), bytes(out)


def frame_of(contents):
    """FRAME_HEADER + compressed blocks + the empty stored last block, as the game's frame ends."""
    out = bytearray(FRAME_HEADER)
    for c in contents:
        out += struct.pack("<I", (len(c) << 3) | (2 << 1))[:3] + c
    out += struct.pack("<I", 1)[:3]                       # last, stored, size 0
    return bytes(out)


def make_frame(seed=7, blocks=6):
    rnd = random.Random(seed)
    contents, body = [], b""
    for _ in range(blocks):
        c, dec = make_block(rnd, body[-65536:])
        contents.append(c)
        body += dec
    return frame_of(contents), body


def dcx_of(frame: bytes, body: bytes) -> bytes:
    h = bytearray(0x4C)
    h[:4] = b"DCX\0"
    h[0x28:0x2C] = b"ZSTD"
    struct.pack_into(">II", h, 0x1C, len(body), len(frame))
    return bytes(h) + frame + b"\0" * ((-(0x4C + len(frame))) % 16)


# ---------------- BND4 / PARAM ----------------
def param_blob(rows, row_size=16, tail=b"NAME\0\0\0\0"):
    """rows: [(id, bytes of row_size)] -> a .param file as the container code expects it."""
    n = len(rows)
    data_start = 0x40 + 24 * n
    strings_off = data_start + row_size * n
    head = bytearray(0x40)
    struct.pack_into("<I", head, 0, strings_off)
    struct.pack_into("<H", head, 0x0A, n)
    struct.pack_into("<Q", head, 0x30, data_start)
    rec, data = bytearray(), bytearray()
    for i, (rid, rd) in enumerate(rows):
        assert len(rd) == row_size
        rec += struct.pack("<iIQQ", rid, 0, data_start + i * row_size, 0)
        data += rd
    return bytes(head) + bytes(rec) + bytes(data) + tail


def bnd4_blob(entries):
    """entries: [(name, bytes)]."""
    n = len(entries)
    names, name_offs = bytearray(), []
    base = 0x40 + 36 * n
    for name, _ in entries:
        name_offs.append(base + len(names))
        names += name.encode("utf-16le") + b"\0\0"
    data_start = base + len(names)
    data_start += (-data_start) % 16
    head = bytearray(0x40)
    head[:4] = b"BND4"
    struct.pack_into("<I", head, 0x0C, n)
    struct.pack_into("<Q", head, 0x10, 0x40)
    struct.pack_into("<Q", head, 0x20, 36)
    struct.pack_into("<Q", head, 0x28, data_start)
    head[0x30:0x33] = bytes([1, 0x74, 4])
    recs, body, pos = bytearray(), bytearray(), data_start
    for i, (name, data) in enumerate(entries):
        r = bytearray(36)
        struct.pack_into("<Q", r, 8, len(data))
        struct.pack_into("<Q", r, 0x10, len(data))
        struct.pack_into("<I", r, 0x18, pos)
        struct.pack_into("<i", r, 0x1C, i)
        struct.pack_into("<I", r, 0x20, name_offs[i])
        recs += r
        body += data
        pos += len(data)
        if i + 1 < n:
            pad = (-pos) % 16
            body += b"\0" * pad
            pos += pad
    blob = bytes(head) + bytes(recs) + bytes(names)
    return blob + b"\0" * (data_start - len(blob)) + bytes(body)

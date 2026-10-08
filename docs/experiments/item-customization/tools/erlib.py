"""Lossless reader/writer for Elden Ring regulation.bin: AES -> DCX(ZSTD) -> BND4 -> PARAM.
Nothing is re-encoded that was not edited: unedited bytes are copied as they are."""
import io, struct
import zstandard
import erreg


def u32(b, o): return struct.unpack_from("<I", b, o)[0]
def u64(b, o): return struct.unpack_from("<Q", b, o)[0]


# ---------------- DCX (ZSTD) ----------------
def dcx_unpack(dcx: bytes):
    assert dcx[:4] == b"DCX\0" and dcx[0x28:0x2C] == b"ZSTD"
    unc, comp = struct.unpack(">II", dcx[0x1C:0x24])
    body = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(dcx[0x4C:0x4C + comp])).read()
    assert len(body) == unc
    return body, bytearray(dcx[:0x4C])


def _frame64k(body, level, **kw):
    p = zstandard.ZstdCompressionParameters.from_level(level, window_log=26, write_content_size=False,
                                                       write_checksum=False, threads=0, **kw)
    c = zstandard.ZstdCompressor(compression_params=p).compressobj()
    out = bytearray()
    for i in range(0, len(body), 65536):
        out += c.compress(body[i:i + 65536])
        out += c.flush(zstandard.COMPRESSOBJ_FLUSH_BLOCK)
    out += c.flush(zstandard.COMPRESSOBJ_FLUSH_FINISH)
    return bytes(out)


def dcx_pack(body: bytes, header: bytearray, level: int = 8) -> bytes:
    """Shape of the game's own frames: 64 KiB blocks, no content size, no checksum, 64 MiB window, and
    at most 2 bytes of zero padding after the frame (the file is padded to 16 bytes by the AES layer).
    Tries a few parameter variants until the padding is <= 2 (the original has exactly 2)."""
    payload = None
    variants = [{}] + [dict(search_log=sl, target_length=tl) for sl in (3, 4, 2, 5) for tl in (None, 8, 16, 32, 48)]
    for kw in variants:
        kw = {k: v for k, v in kw.items() if v is not None}
        payload = _frame64k(body, level, **kw)
        if (-(len(header) + len(payload))) % 16 <= 2:
            break
    else:
        raise RuntimeError("no parameter variant gave <= 2 bytes of padding")
    h = bytearray(header)
    struct.pack_into(">II", h, 0x1C, len(body), len(payload))
    return bytes(h) + payload


# ---------------- BND4 ----------------
class Entry:
    __slots__ = ("hdr", "id", "name", "data")


class Bnd4:
    ENTRY_SIZE_FIELDS = (0x08, 0x10)   # compressed / uncompressed size (equal: entries are stored raw)
    DATA_OFFSET_FIELD = 0x18

    def __init__(self, blob: bytes):
        assert blob[:4] == b"BND4"
        self.count = u32(blob, 0x0C)
        hs, self.fhs, self.data_start = u64(blob, 0x10), u64(blob, 0x20), u64(blob, 0x28)
        assert (hs, self.fhs) == (0x40, 36) and blob[0x30:0x33] == bytes([1, 0x74, 4])
        self.head = bytearray(blob[:self.data_start])
        self.entries = []
        for i in range(self.count):
            o = hs + i * self.fhs
            e = Entry()
            e.hdr = bytearray(blob[o:o + self.fhs])
            size, size2, off = u64(blob, o + 8), u64(blob, o + 0x10), u32(blob, o + 0x18)
            assert size == size2
            e.id = struct.unpack_from("<i", blob, o + 0x1C)[0]
            no = u32(blob, o + 0x20)
            end = no
            while blob[end:end + 2] != b"\0\0" or (end - no) % 2:
                end += 1
            e.name = blob[no:end].decode("utf-16le")
            e.data = bytes(blob[off:off + size])
            self.entries.append(e)

    def build(self) -> bytes:
        head = bytearray(self.head)
        out = bytearray()
        pos = self.data_start
        for i, e in enumerate(self.entries):
            o = 0x40 + i * self.fhs
            struct.pack_into("<Q", head, o + 8, len(e.data))
            struct.pack_into("<Q", head, o + 0x10, len(e.data))
            struct.pack_into("<I", head, o + 0x18, pos)
            out += e.data
            pos += len(e.data)
            pad = (-pos) % 16 if i + 1 < len(self.entries) else 0
            out += b"\0" * pad
            pos += pad
        return bytes(head) + bytes(out)

    def get(self, short: str) -> Entry:
        hits = [e for e in self.entries if e.name.replace("\\", "/").rsplit("/", 1)[-1] == short + ".param"]
        assert len(hits) == 1, (short, len(hits))
        return hits[0]


def load_regulation(path):
    raw = open(path, "rb").read()
    dcx = erreg.decrypt(raw)
    body, dcxhdr = dcx_unpack(dcx)
    return raw, dcx, body, dcxhdr, Bnd4(body)


# ---------------- PARAM ----------------
class Param:
    """One .param file. rows: list of [id, name_offset, data bytes]. Layout (ER, verified against the memory layout):
    0x00 u32 strings_off | 0x08 u16 row_count@0x0A | 0x10 u64 type_off | 0x30 u64 data_start | 0x40.. 24-byte row records."""
    def __init__(self, blob: bytes):
        self.head = bytearray(blob[:0x40])
        self.strings_off = u32(blob, 0)
        self.count = struct.unpack_from("<H", blob, 0x0A)[0]
        self.data_start = u64(blob, 0x30)
        assert self.data_start == 0x40 + 24 * self.count, "unexpected row table size"
        self.row_size = (self.strings_off - self.data_start) // self.count if self.count else 0
        assert self.count == 0 or self.row_size * self.count == self.strings_off - self.data_start
        self.rows = []
        for i in range(self.count):
            o = 0x40 + 24 * i
            rid, pad, doff, noff = struct.unpack_from("<iIQQ", blob, o)
            assert pad == 0 and doff == self.data_start + i * self.row_size, (i, rid, doff)
            self.rows.append([rid, noff, bytearray(blob[doff:doff + self.row_size])])
        self.tail = bytes(blob[self.strings_off:])    # type string + row names, copied as is
        assert [r[0] for r in self.rows] == sorted(r[0] for r in self.rows)

    def find(self, rid):
        import bisect
        ids = [r[0] for r in self.rows]
        i = bisect.bisect_left(ids, rid)
        return self.rows[i] if i < len(ids) and ids[i] == rid else None

    def name_of(self, row):
        noff = row[1]
        if noff < self.strings_off or noff >= self.strings_off + len(self.tail):
            return ""
        t = self.tail[noff - self.strings_off:]
        end = 0
        while t[end:end + 2] != b"\0\0" or end % 2:
            end += 2 if end % 2 == 0 and t[end:end + 2] != b"\0\0" else 1
            if end >= len(t): break
        return t[:end].decode("utf-16le", "replace")

    def add_row(self, rid, data: bytes, name: str | None = None):
        """Insert a row (kept sorted by id). The name is appended to the strings area (or points at nothing)."""
        assert self.find(rid) is None and len(data) == self.row_size
        noff = 0
        if name is not None:
            noff = self.strings_off + len(self.tail)      # relative to the OLD layout; fixed in build()
            self.tail += name.encode("utf-16le") + b"\0\0"
            self._new_names = True
        import bisect
        ids = [r[0] for r in self.rows]
        self.rows.insert(bisect.bisect_left(ids, rid), [rid, noff, bytearray(data)])
        self.count += 1

    def build(self) -> bytes:
        old_strings = self._old_strings = getattr(self, "_old_strings", self.strings_off)
        n = len(self.rows)
        data_start = 0x40 + 24 * n
        strings_off = data_start + self.row_size * n
        shift = strings_off - old_strings           # names moved by this much
        head = bytearray(self.head)
        struct.pack_into("<I", head, 0, strings_off)
        struct.pack_into("<H", head, 0x0A, n)
        struct.pack_into("<Q", head, 0x30, data_start)
        # the type-name offset at 0x10 points into the strings area as well
        t_off = struct.unpack_from("<Q", head, 0x10)[0]
        if t_off >= old_strings:
            struct.pack_into("<Q", head, 0x10, t_off + shift)
        rec, data = bytearray(), bytearray()
        for i, (rid, noff, rd) in enumerate(self.rows):
            noff2 = noff + shift if noff >= old_strings else noff
            rec += struct.pack("<iIQQ", rid, 0, data_start + i * self.row_size, noff2)
            data += rd
        return bytes(head) + bytes(rec) + bytes(data) + self.tail


# ---------------- splice: keep the game's own zstd blocks, raw-store only what changed ----------------
class Splicer:
    """Verified in the real game: the game accepts its own zstd blocks mixed with stored (raw) blocks, but NOT frames
    re-encoded by libzstd (tests A, C2, C3, C5 failed; E3, E7 passed).  So an edited body is written as: the
    original frame with every block whose output changed (or whose decoding depends on a changed block) stored raw."""

    def __init__(self, orig_dcx: bytes):
        self.header = bytearray(orig_dcx[:0x4C])
        comp = struct.unpack(">I", orig_dcx[0x20:0x24])[0]
        self.frame = orig_dcx[0x4C:0x4C + comp]
        self.blocks = []                       # (start, end, type) of every block incl. its 3-byte header
        p = 6
        while True:
            h = self.frame[p] | self.frame[p + 1] << 8 | self.frame[p + 2] << 16
            ty = (h >> 1) & 3
            end = p + 3 + (1 if ty == 1 else h >> 3)
            self.blocks.append((p, end, ty))
            p = end
            if h & 1:
                break
        assert p == comp
        d = zstandard.ZstdDecompressor().decompressobj()
        self.spans, pos = [], 0
        for i, (s, e, _) in enumerate(self.blocks):
            n = len(d.decompress(self.frame[:e] if i == 0 else self.frame[s:e]))
            self.spans.append((pos, pos + n)); pos += n
        self.body_len = pos

    def _build(self, raw: set, body: bytes) -> bytes:
        out = bytearray(self.frame[:6])
        last = len(self.blocks) - 1
        for i, (s, e, _) in enumerate(self.blocks):
            if i in raw:
                a, b = self.spans[i]
                out += struct.pack("<I", ((b - a) << 3) | (1 if i == last else 0))[:3] + body[a:b]
            else:
                out += self.frame[s:e]
        return bytes(out)

    def _first_bad(self, frame: bytes, body: bytes):
        """Index of the first block that fails or decodes to something else; None when the frame is right."""
        d = zstandard.ZstdDecompressor().decompressobj()
        p, pos = 6, 0
        for i in range(len(self.blocks)):
            h = frame[p] | frame[p + 1] << 8 | frame[p + 2] << 16
            ty = (h >> 1) & 3
            end = p + 3 + (1 if ty == 1 else h >> 3)
            try:
                got = d.decompress(frame[:end] if i == 0 else frame[p:end])
            except zstandard.ZstdError:
                return i
            a, b = self.spans[i]
            if got != body[a:b]:
                return i
            p = end
        return None

    def pack(self, new_body: bytes, old_body: bytes, pad_to: int | None = 2) -> bytes:
        assert len(new_body) == self.body_len == len(old_body), "a splice needs a body of the same length"
        raw = {i for i, (a, b) in enumerate(self.spans) if new_body[a:b] != old_body[a:b]}
        while True:
            f = self._build(raw, new_body)
            bad = self._first_bad(f, new_body)
            if bad is None:
                break
            raw.add(bad)
        if pad_to is not None:                 # same zero padding after the frame as the original file has
            i = 0
            while (-(len(self.header) + len(f))) % 16 != pad_to:
                while i in raw:
                    i += 1
                trial = self._build(raw | {i}, new_body)
                if self._first_bad(trial, new_body) is None:
                    raw.add(i); f = trial
                i += 1
                assert i < len(self.blocks), "cannot reach the wanted padding"
        self.raw_blocks = sorted(raw)
        h = bytearray(self.header)
        struct.pack_into(">II", h, 0x1C, len(new_body), len(f))
        return bytes(h) + f


class GrowSplicer(Splicer):
    """Same as Splicer, but the new body may be LONGER than the original (data appended at the end):
    the original last block loses its 'last' flag and stored blocks carry the new tail."""

    def _build_grown(self, raw: set, body: bytes, tail_blocks: int) -> bytes:
        out = bytearray(self.frame[:6])
        last = len(self.blocks) - 1
        for i, (s, e, _) in enumerate(self.blocks):
            if i in raw:
                a, b = self.spans[i]
                out += struct.pack("<I", ((b - a) << 3))[:3] + body[a:b]
            else:
                blk = bytearray(self.frame[s:e])
                if i == last:
                    blk[0] &= 0xFE                  # no longer the last block
                out += blk
        tail = body[self.body_len:]
        n = tail_blocks
        step = -(-len(tail) // n) if n else 0
        assert 0 < n and step < (1 << 17)
        for k in range(n):
            part = tail[k * step:(k + 1) * step]
            out += struct.pack("<I", (len(part) << 3) | (1 if k == n - 1 else 0))[:3] + part
        return bytes(out)

    def pack_grown(self, new_body: bytes, old_body: bytes, pad_to: int = 2) -> bytes:
        assert len(new_body) > self.body_len == len(old_body)
        raw = {i for i, (a, b) in enumerate(self.spans) if new_body[a:b] != old_body[a:b]}
        n0 = -(-(len(new_body) - self.body_len) // 65536)
        while True:
            f = self._build_grown(raw, new_body, n0)
            bad = self._first_bad(f, new_body[:self.body_len])
            if bad is None:
                break
            raw.add(bad)
        for n in range(n0, n0 + 16):                 # same zero padding after the frame as the original file
            f = self._build_grown(raw, new_body, n)
            if (-(len(self.header) + len(f))) % 16 == pad_to:
                break
        else:
            raise RuntimeError("cannot reach the wanted padding")
        got = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(f)).read()
        assert got == new_body, "grown frame does not decode to the new body"
        self.raw_blocks = sorted(raw)
        h = bytearray(self.header)
        struct.pack_into(">II", h, 0x1C, len(new_body), len(f))
        return bytes(h) + f


def bnd_append(body: bytes, replacements: dict) -> bytes:
    """Return a BND4 body in which each named entry's data is replaced by a NEW copy appended at the end of the file
    (16-aligned); the old copy stays where it was, unreferenced.  Nothing else moves.  replacements: short name -> bytes."""
    blob = bytearray(body)
    b = Bnd4(bytes(body))
    for name, data in replacements.items():
        e = b.get(name)
        idx = b.entries.index(e)
        o = 0x40 + idx * b.fhs
        pad = (-len(blob)) % 16
        blob += b"\0" * pad
        off = len(blob)
        blob += data
        struct.pack_into("<Q", blob, o + 8, len(data))
        struct.pack_into("<Q", blob, o + 0x10, len(data))
        struct.pack_into("<I", blob, o + 0x18, off)
    return bytes(blob)


class SplitSplicer(Splicer):
    """Splicer that reaches the original 2-byte zero padding WITHOUT extra raw blocks: one of the stored blocks is
    cut into several stored blocks (each cut costs 3 header bytes), so the file stays as small as the edit allows."""

    def _build_split(self, raw, body, split_at, pieces):
        out = bytearray(self.frame[:6]); last = len(self.blocks) - 1
        for i, (s, e, _) in enumerate(self.blocks):
            if i in raw:
                a, b = self.spans[i]
                n = pieces if i == split_at else 1
                step = -(-(b - a) // n)
                for k in range(n):
                    part = body[a + k * step: min(a + (k + 1) * step, b)]
                    fin = 1 if (i == last and k == n - 1) else 0
                    out += struct.pack("<I", (len(part) << 3) | fin)[:3] + part
            else:
                out += self.frame[s:e]
        return bytes(out)

    def pack_split(self, new_body, old_body, pad_to=2):
        assert len(new_body) == self.body_len == len(old_body)
        raw = {i for i, (a, b) in enumerate(self.spans) if new_body[a:b] != old_body[a:b]}
        while True:
            f = self._build(raw, new_body); bad = self._first_bad(f, new_body)
            if bad is None: break
            raw.add(bad)
        cand = [i for i in sorted(raw) if i != len(self.blocks) - 1] or sorted(raw)
        split_at, pieces = cand[0], 1
        for n in range(1, 17):
            f = self._build_split(raw, new_body, split_at, n)
            if (-(len(self.header) + len(f))) % 16 == pad_to:
                pieces = n; break
        else:
            raise RuntimeError("cannot reach padding")
        assert zstandard.ZstdDecompressor().stream_reader(io.BytesIO(f)).read() == new_body
        self.raw_blocks = sorted(raw); self.split = (split_at, pieces)
        h = bytearray(self.header); struct.pack_into(">II", h, 0x1C, len(new_body), len(f))
        return bytes(h) + f

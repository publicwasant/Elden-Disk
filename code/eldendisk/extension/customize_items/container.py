"""regulation.bin = AES-256-CBC( DCX( zstd frame( BND4( PARAM files ) ) ) ).  Lossless readers and writers.

Everything not edited is copied as it is. Standard library only."""
from __future__ import annotations

import bisect
import hashlib
import struct

from . import aes

# The game's own key (public knowledge in the modding community; verified here by the DCX magic after decrypting).
KEY = bytes([0x99, 0xBF, 0xFC, 0x36, 0x6A, 0x6B, 0xC8, 0xC6, 0xF5, 0x82, 0x7D, 0x09, 0x36, 0x02, 0xD6, 0x76,
             0xC4, 0x28, 0x92, 0xA0, 0x1C, 0x20, 0x7F, 0xB0, 0x24, 0xD3, 0xAF, 0x4E, 0x49, 0x3F, 0xEF, 0x99])


class ContainerError(Exception):
    pass


def u32(b, o): return struct.unpack_from("<I", b, o)[0]
def u64(b, o): return struct.unpack_from("<Q", b, o)[0]


# ---------------- AES layer ----------------
def decrypt(raw: bytes) -> bytes:
    """The DCX bytes (with up to 15 zero bytes of padding at the end)."""
    if len(raw) < 32 or (len(raw) - 16) % 16:
        raise ContainerError("not a regulation.bin: the size is not 16 + a multiple of 16")
    dcx = aes.cbc_decrypt(KEY, raw[:16], raw[16:])
    if dcx[:4] != b"DCX\0":
        raise ContainerError("not a regulation.bin: decrypting did not give a DCX container")
    return dcx


def encrypt(dcx: bytes, iv: bytes | None = None) -> bytes:
    """Pads with zeros to 16 bytes. Without `iv` the IV is derived from the content, so the same input always gives
    the same file (the game accepts any IV: test C1 of the handbook)."""
    dcx = dcx + b"\0" * ((-len(dcx)) % 16)
    iv = iv or hashlib.sha256(dcx).digest()[:16]
    return iv + aes.cbc_encrypt(KEY, iv, dcx)


# ---------------- BND4 ----------------
class Entry:
    __slots__ = ("hdr", "id", "name", "data")


class Bnd4:
    def __init__(self, blob: bytes):
        if blob[:4] != b"BND4":
            raise ContainerError("not a BND4 archive")
        self.count = u32(blob, 0x0C)
        hs, self.fhs, self.data_start = u64(blob, 0x10), u64(blob, 0x20), u64(blob, 0x28)
        if (hs, self.fhs) != (0x40, 36) or blob[0x30:0x33] != bytes([1, 0x74, 4]):
            raise ContainerError("unexpected BND4 layout")
        self.head = bytearray(blob[:self.data_start])
        self.entries = []
        for i in range(self.count):
            o = hs + i * self.fhs
            e = Entry()
            e.hdr = bytearray(blob[o:o + self.fhs])
            size, size2, off = u64(blob, o + 8), u64(blob, o + 0x10), u32(blob, o + 0x18)
            if size != size2:
                raise ContainerError("compressed BND4 entries are not supported")
            e.id = struct.unpack_from("<i", blob, o + 0x1C)[0]
            no = u32(blob, o + 0x20)
            end = no
            while blob[end:end + 2] != b"\0\0" or (end - no) % 2:
                end += 1
            e.name = blob[no:end].decode("utf-16le")
            e.data = bytes(blob[off:off + size])
            self.entries.append(e)

    def build(self) -> bytes:
        head, out, pos = bytearray(self.head), bytearray(), self.data_start
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
        if len(hits) != 1:
            raise ContainerError("%s.param: %d matches in the archive" % (short, len(hits)))
        return hits[0]


# ---------------- PARAM ----------------
class Param:
    """One .param file. rows: [id, name_offset, data bytearray], sorted by id.
    Layout (ER): 0x00 u32 strings_off | 0x0A u16 row count | 0x10 u64 type-name offset | 0x30 u64 data_start |
    0x40.. 24-byte row records (i32 id, u32 0, u64 data offset, u64 name offset) | row data | strings."""

    def __init__(self, blob: bytes):
        self.head = bytearray(blob[:0x40])
        self.strings_off = u32(blob, 0)
        self.count = struct.unpack_from("<H", blob, 0x0A)[0]
        self.data_start = u64(blob, 0x30)
        if self.data_start != 0x40 + 24 * self.count:
            raise ContainerError("unexpected row table size")
        self.row_size = (self.strings_off - self.data_start) // self.count if self.count else 0
        if self.count and self.row_size * self.count != self.strings_off - self.data_start:
            raise ContainerError("row data does not divide evenly")
        self.rows = []
        for i in range(self.count):
            rid, pad, doff, noff = struct.unpack_from("<iIQQ", blob, 0x40 + 24 * i)
            if pad != 0 or doff != self.data_start + i * self.row_size:
                raise ContainerError("row %d is not laid out in order" % i)
            self.rows.append([rid, noff, bytearray(blob[doff:doff + self.row_size])])
        self.tail = bytes(blob[self.strings_off:])
        ids = [r[0] for r in self.rows]
        if ids != sorted(ids) or len(set(ids)) != len(ids):
            raise ContainerError("rows are not sorted by unique id")

    def ids(self) -> list[int]:
        return [r[0] for r in self.rows]

    def find(self, rid: int):
        ids = self.ids()
        i = bisect.bisect_left(ids, rid)
        return self.rows[i] if i < len(ids) and ids[i] == rid else None

    def resort(self) -> None:
        self.rows.sort(key=lambda r: r[0])

    def build(self) -> bytes:
        if len(self.rows) != self.count:
            raise ContainerError("the number of rows must not change")
        self.resort()
        head = bytearray(self.head)
        rec, data = bytearray(), bytearray()
        for i, (rid, noff, rd) in enumerate(self.rows):
            rec += struct.pack("<iIQQ", rid, 0, self.data_start + i * self.row_size, noff)
            data += rd
        return bytes(head) + bytes(rec) + bytes(data) + self.tail

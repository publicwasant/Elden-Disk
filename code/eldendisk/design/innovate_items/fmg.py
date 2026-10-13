"""FMG, the game's text table (version 2, 64-bit offsets): ids -> text. Lossless read, canonical write. Standard library only.

    0x00 u8 0, u8 0 (little endian), u8 2 (version), u8 0   0x04 u32 file size   0x08 u32 1   0x0C i32 group count
    0x10 i32 string count   0x14 u32 (kept as read)   0x18 i64 offset of the string offsets   0x20 i64 0
    0x28 groups of 16 bytes: i32 index of the first string, i32 first id, i32 last id, i32 0
    then the offsets (i64 each, 0 = the id exists and has no text) and the strings (UTF-16, null terminated).
"""
from __future__ import annotations

import struct


class FmgError(Exception):
    pass


class Fmg:
    def __init__(self, entries: dict[int, str | None], unk14: int = 0xFF):
        self.entries = entries
        self.unk14 = unk14

    @classmethod
    def read(cls, data: bytes) -> "Fmg":
        if len(data) < 0x28 or data[2] != 2 or data[1] != 0:
            raise FmgError("not a little-endian FMG version 2")
        groups, strings = struct.unpack_from("<ii", data, 0x0C)
        unk14, = struct.unpack_from("<I", data, 0x14)
        offsets_at, = struct.unpack_from("<q", data, 0x18)
        entries: dict[int, str | None] = {}
        for g in range(groups):
            first_index, first, last, _ = struct.unpack_from("<iiii", data, 0x28 + g * 16)
            for k in range(last - first + 1):
                at, = struct.unpack_from("<q", data, offsets_at + (first_index + k) * 8)
                if at == 0:
                    entries[first + k] = None
                    continue
                end = at
                while data[end:end + 2] != b"\0\0" or (end - at) % 2:
                    end += 1
                    if end > len(data):
                        raise FmgError("a string runs past the end of the table")
                entries[first + k] = data[at:end].decode("utf-16le")
        if len(entries) != strings:
            raise FmgError(f"{len(entries)} ids found, the header says {strings}")
        return cls(entries, unk14)

    def write(self) -> bytes:
        ids = sorted(self.entries)
        groups: list[list[int]] = []                      # [first index, first id, last id]
        for index, i in enumerate(ids):
            if groups and groups[-1][2] == i - 1:
                groups[-1][2] = i
            else:
                groups.append([index, i, i])
        offsets_at = 0x28 + 16 * len(groups)
        strings_at = offsets_at + 8 * len(ids)
        body = bytearray()
        offsets = []
        for i in ids:
            text = self.entries[i]
            if text is None:
                offsets.append(0)
                continue
            offsets.append(strings_at + len(body))
            body += text.encode("utf-16le") + b"\0\0"
        out = bytearray(0x28)
        out[2] = 2
        struct.pack_into("<I", out, 0x04, strings_at + len(body))
        struct.pack_into("<I", out, 0x08, 1)
        struct.pack_into("<ii", out, 0x0C, len(groups), len(ids))
        struct.pack_into("<I", out, 0x14, self.unk14)
        struct.pack_into("<q", out, 0x18, offsets_at)
        for g in groups:
            out += struct.pack("<iiii", g[0], g[1], g[2], 0)
        out += struct.pack("<%dq" % len(offsets), *offsets)
        return bytes(out + body)

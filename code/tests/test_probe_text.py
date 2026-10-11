"""The pure parts of tools/probe_text.py (searching a fake memory); the Windows part needs the game."""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import probe_text as pt  # noqa: E402


class Fake:
    def __init__(self, regions):
        self.mem = {base: bytearray(data) for base, data in regions}

    def regions(self):
        return [(b, len(d), "private", 4) for b, d in self.mem.items()]

    def read(self, addr, size):
        for b, d in self.mem.items():
            if b <= addr and addr + size <= b + len(d):
                return bytes(d[addr - b:addr - b + size])
        return None


BLOB = bytes(range(256)) * 4


def test_exact_copies_pointers_and_text():
    a = bytearray(8192)
    a[100:100 + len(BLOB)] = BLOB
    near = bytearray(BLOB)
    near[0x80] ^= 1                                   # same start, one byte different: not an exact copy
    b = bytearray(8192)
    b[0:len(near)] = near
    ptr = bytearray(4096)
    struct.pack_into("<Q", ptr, 16, 0x10000 + 100)
    struct.pack_into("<Q", ptr, 33, 0x10000 + 100)    # unaligned: ignored
    text = "Flame, Grant Me Strength\0".encode("utf-16le")
    a[3000:3000 + len(text)] = text
    mem = Fake([(0x10000, a), (0x20000, b), (0x30000, ptr)])
    assert pt.exact_copies(mem, BLOB) == [0x10000 + 100]
    assert pt.pointers_to(mem, 0x10000 + 100) == [0x30000 + 16]
    assert list(pt.scan(mem, text)) == [0x10000 + 3000]
    assert pt.region_of(mem, 0x30000 + 16)["base"] == hex(0x30000)
    assert len(pt.context(mem, 0x30000 + 64)) == 16


def test_a_pattern_across_the_chunk_border_is_found():
    d = bytearray(100)
    d[46:54] = b"ABCDEFGH"
    assert list(pt.scan(Fake([(0x1000, d)]), b"ABCDEFGH", chunk=50)) == [0x1000 + 46]


def test_analyse_lays_the_file_over_the_text_and_reports_fixups():
    blob = bytearray(2048)
    struct.pack_into("<q", blob, 0x18, 0x100)                                 # offset table at 0x100
    for i in range(8):
        struct.pack_into("<Q", blob, 0x100 + i * 8, 0x400 + i * 16)           # relative offsets in the file
    text = "Flame, Grant Me Strength\0".encode("utf-16le")
    blob[0x400:0x400 + len(text)] = text
    live = bytearray(blob)
    for i in range(8):
        struct.pack_into("<Q", live, 0x100 + i * 8, 0x7000 + 0x400 + i * 16)  # the game turned them into pointers
    mem = Fake([(0x7000, live)])
    got = pt.analyse(mem, bytes(blob), 0x7000 + 0x400, 0x400)
    assert got["base"] == hex(0x7000) and got["readable"]
    assert got["different_runs"] == 8 and got["size"] == 2048 and got["bytes_equal"] < 2048
    assert got["offset_table_memory"][0] == hex(0x7400) and got["offset_table_file"][0] == hex(0x400)
    assert pt.diff_ranges(b"abcd", b"abXd") == ([(2, 1)], 1)

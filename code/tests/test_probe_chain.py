"""tools/probe_chain.py on a fake game: a global in the exe image -> manager object -> repository object with the slot."""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import probe_chain as pc  # noqa: E402

EXE = 0x7FF600000000


class Fake:
    def __init__(self):
        self.mem, self.kind = {}, {}

    def add(self, base, size, kind):
        self.mem[base] = bytearray(size)
        self.kind[base] = kind

    def put(self, addr, value):
        for b, d in self.mem.items():
            if b <= addr < b + len(d):
                struct.pack_into("<Q", d, addr - b, value)
                return
        raise KeyError(hex(addr))

    def regions(self):
        return [(b, len(d), self.kind[b], 4) for b, d in self.mem.items()]

    def read(self, addr, size):
        for b, d in self.mem.items():
            if b <= addr and addr + size <= b + len(d):
                return bytes(d[addr - b:addr - b + size])
        return None


def world(two_levels):
    g = Fake()
    g.add(EXE, 0x4000, "image")
    g.add(0x7FF400000000, 0x10000, "private")
    g.add(0x7FF400100000, 0x10000, "private")
    repo, mgr, slot = 0x7FF400000800, 0x7FF400100200, 0x7FF400000800 + 0x1C0 + 10 * 8
    g.put(slot, 0x1234)
    if two_levels:
        g.put(mgr + 0x30, repo)                         # manager object holds the repository pointer
        g.put(EXE + 0x2468, mgr)                        # the exe global holds the manager
    else:
        g.put(EXE + 0x2468, repo)
    return g, slot


def test_one_level_chain_is_found_and_walks_back_to_the_slot():
    g, slot = world(False)
    chains = pc.backward(g, slot, EXE, 0x4000, 1 << 20, say=lambda *_: None)
    assert chains and chains[0][0] == 0x2468
    assert pc.walk(g, EXE, *chains[0]) == slot


def test_two_level_chain_goes_through_the_heap():
    g, slot = world(True)
    chains = pc.backward(g, slot, EXE, 0x4000, 1 << 20, say=lambda *_: None)
    assert chains, "no chain"
    rva, offs = chains[0]
    assert rva == 0x2468 and len(offs) == 2
    assert pc.walk(g, EXE, rva, offs) == slot


def test_no_chain_when_nothing_points_back():
    g, slot = world(False)
    g.put(EXE + 0x2468, 0)
    assert pc.backward(g, slot, EXE, 0x4000, 1 << 20, say=lambda *_: None) == []


def test_qwords_across_a_chunk_border_and_prefix_blocks():
    g = Fake()
    g.add(0x7FF400000000, 3 * 1024, "private")
    g.put(0x7FF400000000 + 1000, 0x7FF4000000F0)
    old = pc.CHUNK
    pc.CHUNK = 1000                                      # the value starts at the very end of the first chunk
    try:
        hits = list(pc.qwords_in_range(g, g.regions(), 0x7FF400000000, 0x7FF4000001FF))
    finally:
        pc.CHUNK = old
    assert hits == [(0x7FF400000000 + 1000, 0x7FF4000000F0)]

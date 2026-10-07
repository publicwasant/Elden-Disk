"""A fake param file in fake memory, laid out like the real SpEffectParam (see docs/experiments/params/sp-effect-params):
header (row count u16 at +0xA, data start u64 at +0x30), 24-byte row descriptors from +0x40, 912-byte rows after them."""
import json
import struct
from dataclasses import replace
from pathlib import Path

import eldendisk
from eldendisk.game import memory as memory_reader
from eldendisk.game.profile import load_profile
from tests.test_disk import BASE, make_profile

PKG = Path(eldendisk.__file__).parent
OFFSETS = PKG.parent / "offsets.json"
EXE_SHA = "1a3547101327f65d0c76da2f9190ac0aa66871ea42bae2aecc61e11a8b597891"   # the 1.17.1 profile in offsets.json

HEAD = 0x300000000
CELLS = 0x310000000      # scratch area for the pointer cells of the chains
ROW = 912
REAL = json.loads((OFFSETS).read_text())["profiles"][EXE_SHA]["params"]
CHAINS = [(int(c["rva"], 0), tuple(int(o, 0) for o in c["offsets"]))
          for c in REAL["tables"]["effects"]["head_chains"]]
ROWS = {"black_flame": 1621000, "scouring_black_flame": 1623000, "black_flame_ritual": 1625000, "black_flame_blade": 1626001}
# (the tests call the rows by these short names; the tool itself knows them by id only: params.effects.1621000.…)
assert {str(i) for i in ROWS.values()} == set(REAL["tables"]["effects"]["rows"])

# where the four rows are in the real file (index in the CSV): 1621000 is row 8437, measured with Cheat Engine
REAL_INDEX = {"black_flame": 8437, "scouring_black_flame": 8438, "black_flame_ritual": 8441, "black_flame_blade": 8443}
REAL_ENDURANCE_FROM_HEAD = {"black_flame": 0x799188, "scouring_black_flame": 0x799518,
                            "black_flame_ritual": 0x799FC8, "black_flame_blade": 0x79A6E8}


def params_profile():
    """The real 1.17.1 params block inside the test profile used everywhere else."""
    real, why = load_profile(OFFSETS, EXE_SHA)
    assert real is not None, why
    return replace(make_profile(), params=real.params)


class Pages:
    """Sparse memory of 4 KB pages: room for a file of the real size without a dict entry per byte."""
    PAGE = 4096

    def __init__(self):
        self.pages: dict[int, bytearray] = {}
        self.log: list[int] = []

    def put(self, addr, data):
        data = bytes(data)
        i = 0
        while i < len(data):
            n, off = divmod(addr + i, self.PAGE)
            page = self.pages.setdefault(n, bytearray(self.PAGE))
            take = min(self.PAGE - off, len(data) - i)
            page[off:off + take] = data[i:i + take]
            i += take

    def read(self, addr, size):
        if size <= 0 or not memory_reader.is_user_ptr(addr):
            return None
        out = bytearray()
        pos = addr
        while pos < addr + size:
            n, off = divmod(pos, self.PAGE)
            page = self.pages.get(n)
            if page is None:
                return None
            take = min(self.PAGE - off, addr + size - pos)
            out += page[off:off + take]
            pos += take
        return bytes(out)

    def write(self, addr, data):
        self.log.append(addr)
        self.put(addr, data)
        return True


def row_bytes(effect_endurance=2.0, motion_interval=0.1, change_hp_rate=0.1, change_hp_point=1,
              atk=-1, vfx=9010) -> bytes:
    raw = bytearray(b"\xaa" * ROW)     # the rest of a row is not ours: anything must survive a write untouched
    struct.pack_into("<f", raw, 0x8, effect_endurance)
    struct.pack_into("<f", raw, 0xC, motion_interval)
    struct.pack_into("<f", raw, 0x9C, change_hp_rate)
    struct.pack_into("<i", raw, 0xA0, change_hp_point)
    struct.pack_into("<i", raw, 0x12C, atk)
    struct.pack_into("<i", raw, 0x170, vfx)
    return bytes(raw)


def build_file(mem, ids, *, head=HEAD, only=None, rows=None, count_field=None, data_start_field=None):
    """Write a param file with these row ids into `mem`. `only`: put just the rows of these ids (a file of the real
    size without 10 MB of rows). `rows`: {id: bytes} for rows that are not the default. Returns {id: row data address}."""
    n = len(ids)
    data_start = 0x40 + n * 24
    header = bytearray(0x40)
    struct.pack_into("<H", header, 0xA, n if count_field is None else count_field)
    struct.pack_into("<Q", header, 0x30, data_start if data_start_field is None else data_start_field)
    mem.put(head, bytes(header))
    mem.put(head + 0x40, b"".join(struct.pack("<IIQQ", rid, 0, data_start + i * ROW, 0) for i, rid in enumerate(ids)))
    addrs = {}
    for i, rid in enumerate(ids):
        addrs[rid] = head + data_start + i * ROW
        if only is None or rid in only:
            mem.put(addrs[rid], (rows or {}).get(rid) or row_bytes())
    return addrs


def small_ids(extra_rows=()):
    """30 filler ids with the four Black Flame rows among them, in file order."""
    ids = [1000 + i for i in range(10)] + [ROWS["black_flame"], ROWS["scouring_black_flame"], 1622000,
                                          1624010, ROWS["black_flame_ritual"], ROWS["black_flame_blade"]]
    return ids + [2_000_000 + i for i in range(14)] + list(extra_rows)


def real_ids():
    """The 11,354 ids of the real file: the four Black Flame rows at the indexes measured in Cheat Engine."""
    ids = [3_000_000 + i for i in range(11354)]
    for name, idx in REAL_INDEX.items():
        ids[idx] = ROWS[name]
    return ids


def wire(mem, chain=0, head=HEAD, *, base=BASE):
    """Make `base + rva` lead through the offsets of chain `chain` to `head` (each hop is a pointer in a scratch area)."""
    rva, offsets = CHAINS[chain]
    cells = CELLS + chain * 0x100000
    cell, nxt = base + rva, cells
    for off in offsets:
        mem.put(cell, struct.pack("<Q", nxt))
        cell, nxt = nxt + off, nxt + 0x1000
    mem.put(cell, struct.pack("<Q", head))

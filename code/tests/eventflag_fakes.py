"""A fake game memory with an event flag manager built like the game's (spec 1.8.0 section 3), for the 1.8.0 tests."""
import struct

from eldendisk.game.profile import EventFlagsLayout

BASE, RVA = 0x140000000, 0x3D6C4B8
MAN, HEAD, NODES, BLOCKS, EXTERNAL = 0x20000000, 0x21000000, 0x22000000, 0x23000000, 0x24000000
LAYOUT = EventFlagsLayout(man_rva=RVA, divisor=1000, holder_size=125)
NODE = 0x38


class FlagMemory:
    """Regions of bytes; `fail_writes` makes every write fail (a flag that does not stick)."""

    def __init__(self, groups, external=(), divisor=1000, holder=125):
        self.mem = {}
        self.fail_writes = False
        self.writes = []
        self.mem[BASE + RVA] = bytearray(struct.pack("<Q", MAN))
        man = bytearray(0x48)
        struct.pack_into("<II", man, 0x1C, divisor, holder)
        struct.pack_into("<Q", man, 0x28, BLOCKS)
        struct.pack_into("<Q", man, 0x38, HEAD)
        self.mem[MAN] = man
        keys = sorted(set(groups) | set(external))
        self.index = {g: i for i, g in enumerate(sorted(groups))}
        self.mem[BLOCKS] = bytearray(125 * max(1, len(self.index)))
        self.external = {}
        for k, g in enumerate(sorted(external)):
            self.external[g] = EXTERNAL + k * 0x100
            self.mem[self.external[g]] = bytearray(125)
        nodes = {}

        def build(lo, hi, parent):
            if lo > hi:
                return HEAD
            mid = (lo + hi) // 2
            addr = NODES + mid * 0x40
            g = keys[mid]
            n = bytearray(NODE)
            struct.pack_into("<QQQ", n, 0, build(lo, mid - 1, addr), parent, build(mid + 1, hi, addr))
            struct.pack_into("<I", n, 0x20, g)
            if g in self.external:
                struct.pack_into("<I", n, 0x28, 2)
                struct.pack_into("<Q", n, 0x30, self.external[g])
            else:
                struct.pack_into("<I", n, 0x28, 1)
                struct.pack_into("<I", n, 0x30, self.index[g])
            nodes[addr] = n
            return addr
        root = build(0, len(keys) - 1, HEAD)
        head = bytearray(NODE)
        struct.pack_into("<QQQ", head, 0, HEAD, root, HEAD)
        head[0x19] = 1
        self.mem[HEAD] = head
        self.mem.update(nodes)

    def _find(self, addr, size):
        for b, d in self.mem.items():
            if b <= addr and addr + size <= b + len(d):
                return b, d
        return None, None

    def read(self, addr, size):
        b, d = self._find(addr, size)
        return None if d is None else bytes(d[addr - b:addr - b + size])

    def write(self, addr, data):
        self.writes.append((addr, bytes(data)))
        if self.fail_writes:
            return False
        b, d = self._find(addr, len(data))
        if d is None:
            return False
        d[addr - b:addr - b + len(data)] = data
        return True

    # ---- test helpers
    def block_addr(self, group):
        return self.external.get(group, BLOCKS + self.index.get(group, 0) * 125)

    def set(self, flag, on=True):
        at = self.block_addr(flag // 1000) + (flag % 1000) // 8
        mask = 1 << (7 - flag % 8)
        b, d = self._find(at, 1)
        d[at - b] = d[at - b] | mask if on else d[at - b] & ~mask & 0xFF

    def get(self, flag):
        at = self.block_addr(flag // 1000) + (flag % 1000) // 8
        return bool(self.read(at, 1)[0] & (1 << (7 - flag % 8)))


class OpenGate:
    allowed, reason = True, "open"


class ClosedGate:
    allowed, reason = False, "the session ended"

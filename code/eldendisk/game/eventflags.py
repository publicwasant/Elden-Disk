"""The game's event flags, read-only (1.8.0, spec 1.8.0 section 3): how the game remembers what happened (a boss defeated, its intro
seen, its drop given). The profile's `event_flags` block says where the manager is; the layout below was found on 1.17.1 (the MIT crate
`eldenring`, cs/event_flag.rs, then checked in the game: spec section 13).

    [base + man_rva]          CSEventFlagMan, whose first member is CSFD4VirtualMemoryFlag:
      +0x1C u32 divisor       1000: a flag's group is flag // 1000
      +0x20 u32 holder size   125: the bytes of one group
      +0x28 ptr blocks        the groups' blocks, one after another
      +0x38 ptr head          the head node of a std::map group -> descriptor (+0x30 its allocator, +0x40 its count)
    tree node: +0x00 left, +0x08 parent, +0x10 right, +0x19 nil, +0x20 u32 group, +0x28 u32 mode, +0x30 u32 index (mode 1: the block
    is blocks + index * holder size; mode 2: +0x30 is the block's own pointer)
    bit of a flag: byte (flag % divisor) // 8 of its block, bit 7 - (flag % 8)

Every address is checked before it is used: the manager must hold the profile's divisor and holder size, a node must be a tree node.
A group's block is kept until the manager or the tree changes (the game rebuilds them when it loads a save); `forget()` drops them.
"""
from __future__ import annotations

import struct

from .memory import is_user_ptr, read_ptr
from .profile import EventFlagsLayout

MAX_DEPTH = 64          # a std::map of ~12,000 groups is about 14 deep; more means the tree is not what it should be


class EventFlagError(Exception):
    """The manager or its tree is not where or what the profile says (a game version moved it, or no save is loaded yet)."""


class EventFlags:
    def __init__(self, mem, base: int, layout: EventFlagsLayout):
        self.mem, self.base, self.layout = mem, base, layout
        self._key = None                        # (manager, blocks, head, root): the blocks below belong to it
        self._blocks: dict[int, int | None] = {}

    def forget(self) -> None:
        self._key, self._blocks = None, {}

    # ---- the manager
    def _manager(self) -> tuple[int, int, int, int]:
        man = read_ptr(self.mem, self.base + self.layout.man_rva)
        if man is None or not is_user_ptr(man):
            raise EventFlagError("the event flag manager is not there (no save loaded yet?)")
        raw = self.mem.read(man, 0x48)
        if raw is None:
            raise EventFlagError(f"the event flag manager at {man:#x} cannot be read")
        div, size = struct.unpack_from("<II", raw, 0x1C)
        if (div, size) != (self.layout.divisor, self.layout.holder_size):
            raise EventFlagError(f"the event flag manager at {man:#x} holds divisor {div}, size {size} (expected "
                                 f"{self.layout.divisor}, {self.layout.holder_size}): this game version moved it")
        blocks, = struct.unpack_from("<Q", raw, 0x28)
        head, = struct.unpack_from("<Q", raw, 0x38)
        node = self.mem.read(head, 0x20) if is_user_ptr(head) else None
        if not is_user_ptr(blocks) or node is None or node[0x19] != 1:
            raise EventFlagError(f"the event flag manager at {man:#x} has no tree yet")
        root, = struct.unpack_from("<Q", node, 8)
        key = (man, blocks, head, root)
        if key != self._key:
            self._key, self._blocks = key, {}
        return key

    def block(self, group: int) -> int | None:
        """The address of the block of `group`, or None when the game does not hold that group."""
        _man, blocks, head, root = self._manager()
        if group in self._blocks:
            return self._blocks[group]
        node, found = root, None
        for _ in range(MAX_DEPTH):
            if node == head or not is_user_ptr(node):
                break
            raw = self.mem.read(node, 0x38)
            if raw is None or raw[0x19]:
                break
            key, = struct.unpack_from("<I", raw, 0x20)
            if key == group:
                mode, = struct.unpack_from("<I", raw, 0x28)
                if mode == 1:
                    found = blocks + struct.unpack_from("<I", raw, 0x30)[0] * self.layout.holder_size
                elif mode == 2:
                    ptr, = struct.unpack_from("<Q", raw, 0x30)
                    found = ptr if is_user_ptr(ptr) else None
                break
            node, = struct.unpack_from("<Q", raw, 0 if group < key else 0x10)
        self._blocks[group] = found
        return found

    def where(self, flag: int) -> tuple[int, int] | None:
        """(address of the byte, bit mask) of `flag`, or None when the game does not hold its group."""
        at = self.block(flag // self.layout.divisor)
        if at is None:
            return None
        rest = flag % self.layout.divisor
        return at + rest // 8, 1 << (7 - rest % 8)

    def get(self, flag: int) -> bool | None:
        return self.get_many([flag])[flag]

    def get_many(self, flags) -> dict[int, bool | None]:
        """{flag: ON?} for every flag; None for a flag whose group the game does not hold. One read per group."""
        groups: dict[int, bytes | None] = {}
        out = {}
        for f in flags:
            g = f // self.layout.divisor
            if g not in groups:
                at = self.block(g)
                groups[g] = self.mem.read(at, self.layout.holder_size) if at is not None else None
            data = groups[g]
            rest = f % self.layout.divisor
            out[f] = None if data is None else bool(data[rest // 8] & (1 << (7 - rest % 8)))
        return out

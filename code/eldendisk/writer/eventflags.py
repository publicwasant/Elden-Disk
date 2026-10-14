"""Turning event flags OFF in the running game (1.8.0, spec 1.8.0 section 3): the one write of `resurrect`. Memory
only; the vault puts the save back when the game closes.

There is no general flag writer: `turn_off` refuses any flag that is not in `allowed` (the flags of the great-enemies table), never
turns a flag ON (only the game marks a boss defeated), writes one byte at a time through the session gate and reads it back."""
from __future__ import annotations

from ..game.eventflags import EventFlags


class FlagRefused(Exception):
    pass


def turn_off(mem, gate, flags: EventFlags, wanted, allowed) -> dict[int, str]:
    """Turn every flag of `wanted` OFF. -> {flag: "off" (written and read back) | "was off" | "not held" (the game does not hold its
    group) | "did not stick"}. FlagRefused before anything is written when a flag is not allowed or the gate is closed."""
    wanted = list(dict.fromkeys(int(f) for f in wanted))
    bad = [f for f in wanted if f not in allowed]
    if bad:
        raise FlagRefused(f"not a flag of the great-enemies table: {', '.join(map(str, bad))}")
    if not gate.allowed:
        raise FlagRefused(f"writes are not allowed ({gate.reason})")
    out = {}
    for f in wanted:
        at = flags.where(f)
        if at is None:
            out[f] = "not held"
            continue
        addr, mask = at
        before = mem.read(addr, 1)
        if before is None:
            out[f] = "did not stick"
            continue
        if not before[0] & mask:
            out[f] = "was off"
            continue
        if not gate.allowed:
            raise FlagRefused(f"writes are not allowed ({gate.reason})")
        ok = mem.write(addr, bytes([before[0] & ~mask & 0xFF]))
        after = mem.read(addr, 1)
        out[f] = "off" if ok and after is not None and not after[0] & mask else "did not stick"
    return out

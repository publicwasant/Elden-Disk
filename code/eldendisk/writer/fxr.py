"""`write --flame-color`: recolour the fire of Flame, Grant Me Strength in the running game (spec 1.7.1). Memory only.

What tools/fxr_recolor.py showed on 1.17.1 (checked in the game): the game keeps each SFX file (f000<id>.fxr) in memory exactly as
it is in the file, the colours as four little-endian floats (RGBA). Two files make the fire that is recoloured: 524400 (the fire while
casting) and 524401 (the burst when the cast ends); the third (524402, the fire on the body) is left alone. writer/fxr_plans.py lists where
every colour sits in each file. So the whole change is: find the game's copy of a file by its colours, and write new colour bytes at the
listed places. The game's files are not touched, and the change disappears when the game closes.

How a colour changes: with v = the biggest of R,G,B (the brightness, may be above 1) and w = 1 - (v - smallest)/v (how white it
is), new RGB = v * (w * white + (1 - w) * target); white stays white, black stays black, alpha is never touched. A bloom colour
becomes v * target.

The copies are found by reading the game's memory (writer/scan.py): the first part of each very large block of its private memory
first, where the logs show both files, then the rest, and the look ends as soon as every file has a copy. A copy counts only when every
colour of the plan has its bytes at its place.

The effect files are shared by every spell that uses them (Flame, Grant Me Strength itself too), so the colour is one for the whole
game session.

The same is done for the glowing eyes (`golden_eyes` of the design): f000004866 (EYES_PLANS), the eyes of a human NPC of the DLC, with
their own colour, in the same look. That file is shared with that NPC too.

This module knows bytes only. The design's colour is read by the command (extension/.../service.py: flame_color); the writer
package may not import the extension package.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

from . import scan
from .fxr_plans import ACCENT_PLANS, EYES_PLANS, PLANS

_ALL = {**PLANS, **EYES_PLANS, **ACCENT_PLANS}


class FlameError(Exception):
    pass


# ---- pure parts ---------------------------------------------------------------------------------------------------
def recolor(old: bytes, target, bloom: bool = False) -> bytes:
    """The new 16 bytes of one colour (see the module text). `old` is RGBA as four little-endian floats."""
    r, g, b, a = struct.unpack("<4f", old)
    v = max(r, g, b)
    if v <= 0:
        return old
    if bloom:
        return struct.pack("<4f", v * target[0], v * target[1], v * target[2], a)
    w = 1 - (v - min(r, g, b)) / v
    return struct.pack("<4f", *(v * (w + (1 - w) * t) for t in target), a)


def colour_states(plan: dict, target) -> list[tuple[int, bytes, bytes]]:
    """[(offset, the game's own bytes, the bytes after the change)] for every colour of the plan (equal where nothing changes)."""
    out = []
    for at, hexa, bloom in plan["colours"]:
        old = bytes.fromhex(hexa)
        out.append((at, old, recolor(old, target, bloom)))
    return out


def accent_writes(plan: dict, accent) -> dict[int, tuple[bytes, bytes]]:
    """offset -> (the game's own bytes, the bytes in the `accent` colour) of the plan's `accent` places (the parts of the fire the
    plan's colours leave out), only where something changes."""
    out = {}
    for at, hexa, bloom in plan.get("accent", ()):
        old = bytes.fromhex(hexa)
        new = recolor(old, accent, bloom)
        if new != old:
            out[at] = (old, new)
    return out


def plan_writes(plan: dict, target) -> dict[int, tuple[bytes, bytes]]:
    """offset -> (the game's own bytes, the new bytes), only where something changes."""
    return {at: (old, new) for at, old, new in colour_states(plan, target) if new != old}


def _signature(plan: dict, target) -> tuple[int, bytes, bytes]:
    """The changing colour that tells the effect apart best: the one with the most different numbers in it."""
    changing = [s for s in colour_states(plan, target) if s[1] != s[2]]
    if not changing:
        raise FlameError("this colour changes nothing in the effect")
    return max(changing, key=lambda s: len(set(struct.unpack("<4f", s[1]))))


@dataclass(frozen=True)
class Found:
    """What one look found: per effect the base addresses of the copies with the game's own colours and of the ones already changed."""
    own: dict
    changed: dict
    walked: scan.Walked      # how far the look went and how long it took


def _target(target, eid):
    """`target` is one colour for every effect, or {effect: colour}."""
    return target[eid] if isinstance(target, dict) else target


EFFECTS_AT = 1312 * 1024 * 1024      # where every log of 1.17.1 saw the effect files: this far into the game's biggest private block
EFFECTS_BLOCK = 2048 * 1024 * 1024   # (2560 MB): the fire 1312 MB in, the eyes 1327 MB, the ring 1300 MB; blocks at least this big


def _joined(looks: list) -> scan.Walked:
    """One Walked for several looks made one after the other."""
    return scan.Walked(any(w.stopped for w in looks), all(w.complete for w in looks), sum(w.megabytes for w in looks),
                       sum(w.seconds for w in looks), looks[-1].tier, sum(w.pieces for w in looks),
                       max(w.slowest for w in looks), sum(w.slept for w in looks))


def find_all(mem, eids, target, budget: float = scan.BUDGET, painted: bool = True, everything: bool = False,
             required=None) -> Found:
    """One look through the game's memory for all of `eids`; it ends when every one has a copy (own colours, or already changed when
    `painted`). A copy counts only when EVERY colour of the plan has its bytes at its place. `target`: one colour, or {effect: colour}.

    `everything`: every copy, not only the first (the game holds the file of the eyes two and three times and draws from a copy a look
    that stops at the first one did not reach, 2026-10-12). The copies the game draws from lie together, 1300-1330 MB into its biggest
    private block in every log, so the look goes there first (NEAR bytes each way around EFFECTS_AT), then around every copy it found
    (they may lie further on in another game), and stops: about 200 MB instead of all the memory (7 GB, two minutes while the world
    loads). Only when an effect of `required` (default: all of `eids`) is not found there is all the memory read, as before."""
    patterns, sig, states = {}, {}, {}
    for eid in eids:
        at, old, new = _signature(_ALL[eid], _target(target, eid))
        patterns[(eid, False)], sig[eid], states[eid] = old, at, colour_states(_ALL[eid], _target(target, eid))
        if painted:
            patterns[(eid, True)] = new
    own, changed, seen = {e: [] for e in eids}, {e: [] for e in eids}, set()

    def visit(addr: int, data: bytes, n: int) -> bool:
        for (eid, is_painted), pattern in patterns.items():
            i = data.find(pattern)
            while i != -1:
                base = addr + i - sig[eid]
                if i < n and (addr + i) % 4 == 0 and (eid, is_painted, base) not in seen:
                    seen.add((eid, is_painted, base))
                    if all(mem.read(base + a, 16) == (nw if is_painted else od) for a, od, nw in states[eid]):
                        (changed if is_painted else own)[eid].append(base)
                i = data.find(pattern, i + 1)
        return not everything and all(own[e] or changed[e] for e in eids)

    overlap = max(len(p) for p in patterns.values()) - 1
    if not everything:
        return Found(own, changed, scan.walk(mem, visit, overlap=overlap, budget=budget))
    regions = mem.regions(True)
    hint = [b + EFFECTS_AT for b, n in regions if n >= EFFECTS_BLOCK]
    looks = [scan.walk(mem, visit, overlap=overlap, budget=budget, near=hint, only_near=True, regions=regions)]
    if all(own[e] or changed[e] for e in (required if required is not None else eids)):
        read = [w for w in (scan._window(regions, a) for a in hint) if w]
        found = [b for bs in (*own.values(), *changed.values()) for b in bs]
        looks.append(scan.walk(mem, visit, overlap=overlap, budget=budget, near=found, only_near=True, skip=read, regions=regions))
    else:
        looks.append(scan.walk(mem, visit, overlap=overlap, budget=budget, regions=regions))
    return Found(own, changed, _joined(looks))


def effect_ids() -> tuple[str, ...]:
    """The fire of Flame, Grant Me Strength."""
    return tuple(PLANS)


def eyes_ids() -> tuple[str, ...]:
    """The golden eyes."""
    return tuple(EYES_PLANS)


def ring_ids() -> tuple[str, ...]:
    """The ring of runes of fire incantations (painted with the fire's accent colour; the game may not hold it)."""
    return tuple(ACCENT_PLANS)


# ---- writing ------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Painted:
    effect: str
    copies: int        # copies of the file found in the game (own colours)
    already: int       # copies that already carry the change
    places: int        # places written now
    bases: tuple = ()  # where the game holds the copies that now carry the change


def paint_many(mem, gate, eids, target, budget: float = scan.BUDGET, painted: bool = True, everything: bool = False,
               accent=None, required=None) -> tuple[dict, Found]:
    """Change the game's copies of `eids` after ONE look through its memory (find_all). -> ({effect: Painted, only those the game holds},
    what the look found). An effect the game does not hold (yet) is not in the result. A copy is written only when EVERY place still holds the game's
    own bytes; a write that does not stick is an error. `accent` (one colour, or {effect: colour}): the plan's `accent` places of every
    copy found (painted now or before) are given that colour too, each place only while it holds the game's own bytes."""
    if not gate.allowed:
        raise FlameError(f"writes are not allowed ({gate.reason})")
    found = find_all(mem, eids, target, budget, painted, everything, required)
    out = {}
    for eid in eids:
        bases, done = found.own[eid], found.changed[eid]
        if not bases and not done:
            continue
        writes = plan_writes(_ALL[eid], _target(target, eid))
        places = 0
        for base in bases:
            for off, (old, _new) in writes.items():
                if mem.read(base + off, len(old)) != old:
                    raise FlameError(f"{eid}: {base + off:#x} does not hold the game's own bytes any more; nothing written at this copy")
            for off, (old, new) in writes.items():
                if not mem.write(base + off, new) or mem.read(base + off, len(new)) != new:
                    raise FlameError(f"{eid}: could not write at {base + off:#x}")
                places += 1
        extra = accent_writes(_ALL[eid], _target(accent, eid)) if accent is not None and _target(accent, eid) is not None else {}
        for base in (*bases, *done):
            for off, (old, new) in extra.items():
                if mem.read(base + off, len(old)) != old:
                    continue                              # painted already (or not the game's own bytes): left alone
                if not mem.write(base + off, new) or mem.read(base + off, len(new)) != new:
                    raise FlameError(f"{eid}: could not write at {base + off:#x}")
                places += 1
        out[eid] = Painted(eid, len(bases), len(done), places, tuple(bases or done))
    return out, found

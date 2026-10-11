"""One way to look through the running game's memory for something, shared by `write --flame-color` and `write --text`.

What the logs of 1.17.1 showed (nothing is assumed beyond them):
- The effect files and the text tables are loaded by the game early and stay where they were put, in the game's own private heap.
- That heap is a few very big blocks (about 1.2 GB each). The files lie near the START of such a block (the logs print how far from it),
  so a look at the first HEAD bytes of each big block finds them in a fraction of a second; the rest of the memory is only read when
  that does not.
- The time of the first versions went into resting (a rest of 5 ms after every MB becomes ~15 ms on Windows), not into reading.
  Here the pieces are big (CHUNK) and the rest after each is a share (REST) of the time that piece took, so the game keeps its
  share of the memory bus whatever the speed.

The caller gives a `visit(address, data, n)` that looks at one piece and returns True when it has found enough: the look ends there.
Nothing here writes."""
from __future__ import annotations

import time
from dataclasses import dataclass

CHUNK = 16 * 1024 * 1024        # bytes read at once
REST = 0.5                      # seconds of rest per second a piece took
BIG = 256 * 1024 * 1024         # a block at least this big is read from its start first ...
HEAD = 128 * 1024 * 1024        # ... this much of it
BUDGET = 120.0                  # seconds a look may take at most
SPLIT = 256 * 1024              # a piece that cannot be read whole is read in parts of this size
_sleep, _clock = time.sleep, time.monotonic      # tests replace these


@dataclass(frozen=True)
class Walked:
    stopped: bool       # `visit` had found enough
    complete: bool      # all the memory was seen (or the look stopped because enough was found)
    megabytes: int      # read in all
    seconds: float
    tier: str           # "head" or "rest": which part of the memory the look ended in


def plan(mem, overlap: int, heads: bool = True) -> list[tuple[str, list[tuple[int, int]]]]:
    """[(tier, [(start, size)])] in the order the look goes: the first HEAD bytes of each big private block (the biggest first), then
    all the rest, the biggest first. Pieces of the rest start `overlap` bytes early, so nothing on the border is missed."""
    regions = mem.regions(True)
    big = [(b, n) for b, n in regions if n >= BIG] if heads else []
    if not big:
        return [("rest", sorted(regions, key=lambda r: -r[1]))]
    rest = [(b + HEAD - overlap, n - HEAD + overlap) for b, n in big if n > HEAD] + [(b, n) for b, n in regions if n < BIG]
    return [("head", [(b, min(n, HEAD)) for b, n in sorted(big, key=lambda r: -r[1])]), ("rest", sorted(rest, key=lambda r: -r[1]))]


def _pieces(mem, addr: int, want: int, n: int):
    """(address, data, own length) of what can be read of [addr, addr + want). A piece that cannot be read whole is read in parts, so
    one page that is gone does not hide the rest."""
    data = mem.read(addr, want)
    if data is not None:
        yield addr, data, n
        return
    for off in range(0, n, SPLIT):
        size = min(SPLIT, n - off)
        part = mem.read(addr + off, size)
        if part is not None:
            yield addr + off, part, size


def walk(mem, visit, overlap: int = 64, budget: float = BUDGET, heads: bool = True) -> Walked:
    """Read the game's private memory piece by piece (see the module text) and give each piece to `visit(address, data, n)`: `data` holds
    the piece (n bytes) and up to `overlap` bytes of the next one, so something that begins in the piece but ends after it is seen
    whole; only what BEGINS in the first n bytes is the piece's own."""
    t0, read = _clock(), 0
    for tier, places in plan(mem, overlap, heads):
        for base, size in places:
            pos = 0
            while pos < size:
                n = min(CHUNK, size - pos)
                t = _clock()
                for addr, data, own in _pieces(mem, base + pos, n + overlap if pos + n < size else n, n):
                    read += own
                    if visit(addr, data, own):
                        return Walked(True, True, read >> 20, _clock() - t0, tier)
                pos += n
                if _clock() - t0 > budget:
                    return Walked(False, False, read >> 20, _clock() - t0, tier)
                took = _clock() - t
                if took > 0:
                    _sleep(took * REST)
    return Walked(False, True, read >> 20, _clock() - t0, "rest")


def where(mem, addr: int) -> str:
    """For the log: how far into its private block `addr` lies."""
    for b, n in mem.regions(True):
        if b <= addr < b + n:
            return f"{(addr - b) >> 20} MB ({addr - b:#x}) into a private block of {n >> 20} MB at {b:#x}"
    return "outside the private blocks"

"""One way to look through the running game's memory for something, shared by `write --flame-color` and `write --text`.

What the logs of 1.17.1 showed (nothing is assumed beyond them):
- The effect files and the text tables are loaded by the game early and stay where they were put, in the game's own private heap.
- That heap is a few very big blocks (about 1.2 GB each). The files lie near the START of such a block (the logs print how far from it),
  so a look at the first HEAD bytes of each big block finds them in a fraction of a second; the rest of the memory is only read when
  that does not.
- The time of the first versions went into resting (a rest of 5 ms after every MB becomes ~15 ms on Windows), not into reading.
  Here the rest is a share (REST) of the time the reading took, owed piece by piece and slept in lumps (LUMP), so the game keeps its
  share of the memory bus whatever the speed, and no single read is long enough to be a frame the game misses (CHUNK is small).
- A caller that knows roughly where the thing is (the text array lies within a few tens of MB of the text tables) gives `near`:
  addresses whose surroundings are read first (NEAR bytes each way), and not read again later.

The caller gives a `visit(address, data, n)` that looks at one piece and returns True when it has found enough: the look ends there.
Nothing here writes."""
from __future__ import annotations

import time
from dataclasses import dataclass

CHUNK = 1024 * 1024             # bytes read at once (a read of this size is about a millisecond: no frame of the game waits for it)
REST = 0.5                      # seconds of rest per second of reading
LUMP = 0.002                    # the rest owed is slept once it is this long (a shorter sleep is rounded up by Windows)
NEAR = 64 * 1024 * 1024         # how far each way from an address given as `near` the look goes first
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
    tier: str           # "near", "head" or "rest": which part of the memory the look ended in
    pieces: int = 0     # how many pieces were read
    slowest: float = 0.0    # seconds the slowest piece took (its read and its look): the longest the game could have waited
    slept: float = 0.0      # seconds spent resting


def _window(regions, addr: int, reach: int | None = None) -> tuple[int, int] | None:
    reach = NEAR if reach is None else reach
    for b, n in regions:
        if b <= addr < b + n:
            return max(b, addr - reach), min(b + n, addr + reach)
    return None


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[list[int]] = []
    for s, e in sorted(spans):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(s, e) for s, e in out]


def _minus(places: list[tuple[int, int]], taken: list[tuple[int, int]], overlap: int) -> list[tuple[int, int]]:
    """`places` [(start, size)] without the spans `taken` [(start, end)] (sorted, apart). What lies across a border is not lost: the part
    kept reaches `overlap` bytes into the taken span at its end, and starts `overlap` bytes before it at its start."""
    out = []
    for start, size in places:
        end, cur = start + size, start
        for ts, te in taken:
            if te <= cur or ts >= end:
                continue
            if ts > cur:
                out.append((cur, min(end, ts + overlap) - cur))
            cur = max(cur, te - overlap)
        if cur < end:
            out.append((cur, end - cur))
    return out


def plan(mem, overlap: int, heads: bool = True, near=(), only_near: bool = False, skip=(),
         regions=None, reach: int | None = None) -> list[tuple[str, list[tuple[int, int]]]]:
    """[(tier, [(start, size)])] in the order the look goes: NEAR bytes each way around the addresses `near`; the first HEAD bytes of
    each big private block (the biggest first); then all the rest, the biggest first. Nothing is read twice. Pieces of the rest start
    `overlap` bytes early, so nothing on the border is missed. `only_near`: the near tier alone. `skip`: spans [(start, end)] already
    read by an earlier look (left out of the near tier). `reach`: how far each way from a `near` address (NEAR by default)."""
    regions = mem.regions(True) if regions is None else regions
    big = [(b, n) for b, n in regions if n >= BIG] if heads else []
    if big:
        rest = [(b + HEAD - overlap, n - HEAD + overlap) for b, n in big if n > HEAD] + [(b, n) for b, n in regions if n < BIG]
        tiers = [("head", [(b, min(n, HEAD)) for b, n in sorted(big, key=lambda r: -r[1])]), ("rest", sorted(rest, key=lambda r: -r[1]))]
    else:
        tiers = [("rest", sorted(regions, key=lambda r: -r[1]))]
    spans = _merge([w for w in (_window(regions, a, reach) for a in near) if w])
    if not spans:
        return [] if only_near else tiers
    first = [(s, e - s) for s, e in spans]
    if skip:
        first = [p for p in _minus(first, _merge(list(skip)), overlap) if p[1] > overlap]
    near_tier = [("near", sorted(first, key=lambda r: -r[1]))]
    return near_tier if only_near else near_tier + [(t, _minus(places, spans, overlap)) for t, places in tiers]


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


def walk(mem, visit, overlap: int = 64, budget: float = BUDGET, heads: bool = True, near=(), only_near: bool = False, skip=(),
         regions=None, reach: int | None = None) -> Walked:
    """Read the game's private memory piece by piece (see the module text) and give each piece to `visit(address, data, n)`: `data` holds
    the piece (n bytes) and up to `overlap` bytes of the next one, so something that begins in the piece but ends after it is seen
    whole; only what BEGINS in the first n bytes is the piece's own."""
    t0, read, pieces, slowest, slept, debt = _clock(), 0, 0, 0.0, 0.0, 0.0

    def done(stopped: bool, complete: bool, tier: str) -> Walked:
        return Walked(stopped, complete, read >> 20, _clock() - t0, tier, pieces, slowest, slept)

    tier = "near"
    for tier, places in plan(mem, overlap, heads, near, only_near, skip, regions, reach):
        for base, size in places:
            pos = 0
            while pos < size:
                n = min(CHUNK, size - pos)
                t, looked = _clock(), 0.0
                for addr, data, own in _pieces(mem, base + pos, n + overlap if pos + n < size else n, n):
                    read += own
                    v = _clock()
                    if visit(addr, data, own):
                        pieces += 1
                        return done(True, True, tier)
                    looked += _clock() - v
                pos += n
                pieces += 1
                took = _clock() - t
                slowest = max(slowest, took)
                if _clock() - t0 > budget:
                    return done(False, False, tier)
                debt += max(0.0, took - looked) * REST                  # owed for the reading: looking through our copy costs the game nothing
                if debt >= LUMP:
                    s0 = _clock()
                    _sleep(debt)
                    nap = _clock() - s0
                    slept += max(nap, 0.0)
                    debt = 0.0 if nap <= 0 else max(-0.05, debt - nap)       # a sleep that ran long is paid back by the reads after it
    return done(False, True, tier if only_near else "rest")      # a look of the near tier alone ended there, not after all the memory


def go_easy() -> str:
    """Before a look in a short-lived process of our own: background priority and a fine timer, so the game is not made to wait. -> what
    Windows granted (for the log)."""
    from ..game import _win
    return _win.go_easy()


def where(mem, addr: int) -> str:
    """For the log: how far into its private block `addr` lies."""
    for b, n in mem.regions(True):
        if b <= addr < b + n:
            return f"{(addr - b) >> 20} MB ({addr - b:#x}) into a private block of {n >> 20} MB at {b:#x}"
    return "outside the private blocks"

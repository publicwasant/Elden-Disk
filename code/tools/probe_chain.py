"""Level 3, step 2b (read-only dev probe): a fixed path from eldenring.exe to the game's table of text pointers.

    python tools/probe_chain.py [--record textpatch.json] [--out textchain.json]

patch_text.py has to search all of the game's memory for the text tables, which takes minutes and makes the PC stutter. The
game's pointer to each table sits in a slot (`textpatch.json` holds three such addresses); this probe looks BACKWARDS from
that slot for what points at the object holding it, level by level, until it reaches the exe's own data (an address
`eldenring.exe + rva` that is the same in every run). Level 1 reads only the exe image (small). Deeper levels read the
heap, regions up to --max-region-mb only, in small pieces with short pauses. Run it in the same game session in which you ran
`patch_text.py --apply` (the addresses are only valid there). Read-only; writes only --out.

A chain is printed as `exe + rva`, then offsets: read the 8-byte pointer at exe+rva, add offsets[0], read the pointer there,
add offsets[1], ... the address reached by the last offset is the slot itself.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import probe_text as pt                                                  # noqa: E402

WINDOW = 0x8000          # how far before the slot the object may start
CHUNK = 4 * 1024 * 1024
MAX_HITS = 40
MAX_DEPTH = 3


# ---- pure parts (tested without a game) ---------------------------------------------------------------------------
def qwords_in_range(mem, regions, lo: int, hi: int, pause: float = 0.0):
    """(location, value) of every aligned 8-byte value in [lo, hi] found in `regions`. The high 5 bytes of the value are
    searched as bytes (fast, in C), then each candidate is checked."""
    parts, a = [], lo
    while a <= hi:                                    # one prefix per 16 MiB block of the range
        top = min(hi, ((a >> 24) + 1 << 24) - 1)
        parts.append((a, top, (a >> 24).to_bytes(5, "little")))
        a = top + 1
    for base, size, _kind, _prot in regions:
        pos = 0
        while pos < size:
            n = min(CHUNK, size - pos)
            data = mem.read(base + pos, n + 8 if pos + n < size else n)
            if data:
                for plo, phi, prefix in parts:
                    i = data.find(prefix)
                    while i != -1:
                        start = i - 3
                        loc = base + pos + start
                        if start >= 0 and start < n and loc % 8 == 0 and start + 8 <= len(data):
                            v = struct.unpack_from("<Q", data, start)[0]
                            if plo <= v <= phi:
                                yield loc, v
                        i = data.find(prefix, i + 1)
            pos += n
            if pause:
                time.sleep(pause)


def backward(mem, slot: int, exe_base: int, exe_size: int, max_region: int, pause: float = 0.0, say=print):
    """Chains [(rva, [offsets])] that lead from the exe's data to `slot`; looks at most MAX_DEPTH objects back."""
    regions = mem.regions()
    image = [r for r in regions if r[2] == "image" and exe_base <= r[0] < exe_base + exe_size]
    heap = [r for r in regions if r[2] == "private" and r[1] <= max_region]
    chains = []
    frontier = [(slot, [])]                           # (address we want a pointer to, offsets collected so far, last first)
    for depth in range(1, MAX_DEPTH + 1):
        say(f"level {depth}: looking for pointers into {len(frontier)} place(s)")
        nxt = []
        for target, offs in frontier:
            lo = max(target - WINDOW, 0x10000)
            for loc, v in qwords_in_range(mem, image, lo, target, pause):
                chains.append((loc - exe_base, [target - v] + offs))
            if chains:
                continue
            found = 0
            for loc, v in qwords_in_range(mem, heap, lo, target, pause):
                nxt.append((loc, [target - v] + offs))
                found += 1
                if found >= MAX_HITS:
                    break
        if chains:
            return chains
        frontier = nxt[:MAX_HITS]
        if not frontier:
            break
    return chains


def walk(mem, exe_base: int, rva: int, offsets: list[int]):
    """Follow a chain in `mem`; the address the last offset reaches, or None."""
    addr = exe_base + rva
    for off in offsets:
        raw = mem.read(addr, 8)
        if raw is None:
            return None
        addr = struct.unpack("<Q", raw)[0] + off
    return addr


# ---- Windows part -------------------------------------------------------------------------------------------------
def main() -> int:
    from eldendisk.game.memory import list_modules
    from eldendisk.game.processes import GAME_EXE, find_pid, has_eac
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", default="textpatch.json")
    ap.add_argument("--out", default="textchain.json")
    ap.add_argument("--max-region-mb", type=int, default=64)
    ap.add_argument("--pause", type=float, default=0.004, help="seconds between 4 MiB reads (less stutter)")
    a = ap.parse_args()
    pid = find_pid(GAME_EXE)
    if pid is None:
        print("eldenring.exe is not running")
        return 1
    mods = list_modules(pid) or []
    main_mod = next((m for m in mods if m.name.lower() == GAME_EXE), None)
    if main_mod is None or has_eac(m.name for m in mods):
        print("anti-cheat is loaded or the modules cannot be read; start the game with `eldendisk run`")
        return 3
    rec = json.loads(Path(a.record).read_text(encoding="utf-8"))
    if rec["pid"] != pid:
        print(f"{a.record} is from game process {rec['pid']}, the game now is {pid}: its addresses are gone. "
              "Run `patch_text.py --apply` in this game session first")
        return 1
    mem = pt.WinMem(pid)
    base = main_mod.base
    exe_size = max((r[0] + r[1] for r in mem.regions() if r[2] == "image" and r[0] >= base), default=base) - base
    exe_size = min(exe_size, 0x10000000)
    slots = {s["name"]: s["pointer_at"] for s in rec["steps"]}
    first = slots["GoodsName"]
    print(f"exe at {base:#x} (image {exe_size >> 20} MiB); slot of GoodsName at {first:#x}; "
          f"heap regions up to {a.max_region_mb} MiB")
    chains = backward(mem, first, base, exe_size, a.max_region_mb << 20, a.pause)
    out = {"pid": pid, "exe_base": hex(base), "slots": {k: hex(v) for k, v in slots.items()}, "chains": []}
    for rva, offs in chains[:MAX_HITS]:
        reached = walk(mem, base, rva, offs)
        ok = reached == first
        out["chains"].append({"rva": hex(rva), "offsets": [hex(o) for o in offs], "reaches_slot": ok})
        print(f"  exe + {rva:#x} -> offsets {[hex(o) for o in offs]}  {'OK' if ok else 'does not reach the slot'}")
    if not chains:
        print("no chain found within the limits (try --max-region-mb 256)")
    Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"report: {a.out}")
    return 0 if chains else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Level 3, step 3 (dev experiment): recolour the fire of Flame, Grant Me Strength in the running game's memory only.

    python tools/fxr_recolor.py                  dry run: finds the effects in the game's memory, says what it would write
    python tools/fxr_recolor.py --apply          writes the tint (default colour: a sky blue)
    python tools/fxr_recolor.py --apply --target 0.2 0.65 1 --blend add
    python tools/fxr_recolor.py --undo           puts the game's own colours back

The effects (SFX files of the game, all found by id in the common effect archive):
    524402  the burning body (SpEffectVfx 1605000)
    524400  the cast effect (Magic.6421.castSfxId)
    524401  the fire effect (Magic.6421.fireSfxId)
tools/fxr_plans.json lists, for each file, where every colour sits (offset, the 16 bytes of the game's own colour, whether it is a
bloom colour) and, for 524402, where its blend mode sits. The offsets were read from the files themselves (the effect library's own
reader), they are the same in the game's memory (the game keeps the file layout). This tool needs no copy of the game files.

How a colour is changed: with v = the biggest of R,G,B (the brightness, may be above 1) and w = 1 - (v - smallest)/v (how white it is),
new RGB = v * (w * white + (1 - w) * target); white stays white, black stays black, alpha is never touched. A bloom colour becomes
v * target. Blend `add` (only 524402 has one to change) lets the flames add light instead of covering, so the black tongues go.
Every write checks first that the game still holds its own bytes there; the old bytes go to fxrpatch.json for --undo.
Needs the game started with `eldendisk run` (no anti-cheat). Cast the spell once first so that the effects are loaded; cast it again
after --apply. Nothing is written to any file of the game.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import probe_text as pt                                                  # noqa: E402

PLANS = Path(__file__).resolve().parent / "fxr_plans.json"
STATE = "fxrpatch.json"
DEFAULT_TARGET = (0.2, 0.65, 1.0)
BLENDS = ("normal", "add")


class TintError(Exception):
    pass


# ---- pure parts (tested without a game) ---------------------------------------------------------------------------
def load_plans(path: Path = PLANS) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


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


def plan_writes(plan: dict, target, blend: str | None = None) -> dict[int, tuple[bytes, bytes]]:
    """offset -> (the game's own bytes, the new bytes) for one effect."""
    if blend is not None and blend not in BLENDS:
        raise TintError(f"blend must be one of {', '.join(BLENDS)}")
    writes = {}
    for c in plan["colours"]:
        old = bytes.fromhex(c["old"])
        new = recolor(old, target, c.get("bloom", False))
        if new != old:
            writes[c["at"]] = (old, new)
    if blend is not None:
        for b in plan.get("blend", []):
            writes[b["at"]] = (struct.pack("<i", b["old"]), struct.pack("<i", b["add"] if blend == "add" else b["old"]))
    return writes


def signature(plan: dict) -> dict:
    """The colour that tells the effect apart best: the one with the most different numbers in it."""
    return max(plan["colours"], key=lambda c: len(set(struct.unpack("<4f", bytes.fromhex(c["old"])))))


def find_copies(mem, plan: dict, hits=None):
    """Base addresses where the game holds this effect: every colour of the plan has its own bytes at base + offset.
    Returns (bases, nearly) - `nearly` are candidates where most (not all) colours matched, for the report."""
    sig = signature(plan)
    pat = bytes.fromhex(sig["old"])
    bases, nearly = [], []
    for hit in (hits if hits is not None else pt.scan(mem, pat, align=4)):
        base = hit - sig["at"]
        good = sum(mem.read(base + c["at"], 16) == bytes.fromhex(c["old"]) for c in plan["colours"])
        if good == len(plan["colours"]):
            bases.append(base)
        elif good * 2 > len(plan["colours"]):
            nearly.append((base, good))
    return bases, nearly


def apply(mem, plan: dict, bases, target, blend: str | None = None) -> list[dict]:
    """Write the plan at every base. Nothing is written at a base unless every place still holds the game's bytes."""
    writes = plan_writes(plan, target, blend)
    record = []
    for base in bases:
        for off, (old, _new) in writes.items():
            if mem.read(base + off, len(old)) != old:
                raise TintError(f"{base + off:#x} does not hold the game's own bytes any more; nothing written at this copy")
        for off, (old, new) in writes.items():
            mem.write(base + off, new)
            record.append({"at": base + off, "old": old.hex(), "new": new.hex()})
    return record


def undo(mem, record) -> int:
    """Put the old bytes back where the new ones are still in place. Returns how many places were restored."""
    n = 0
    for rec in record:
        if mem.read(rec["at"], len(rec["new"]) // 2) == bytes.fromhex(rec["new"]):
            mem.write(rec["at"], bytes.fromhex(rec["old"]))
            n += 1
    return n


def main() -> int:
    from eldendisk.game.memory import list_modules
    from eldendisk.game.processes import GAME_EXE, find_pid, has_eac
    import patch_text as ptx
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=float, nargs=3, default=DEFAULT_TARGET, metavar=("R", "G", "B"),
                    help="the colour of the fire, 0..1 (more than 1 is brighter); default a sky blue")
    ap.add_argument("--blend", choices=list(BLENDS), help="add: the flames of the body only shine (the black tongues go)")
    ap.add_argument("--only", action="append", default=[], metavar="ID", help="only this effect (524400, 524401, 524402); may be repeated")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--undo", action="store_true")
    a = ap.parse_args()
    pid = find_pid(GAME_EXE)
    if pid is None:
        print("eldenring.exe is not running (start it with `eldendisk run`)")
        return 1
    mods = list_modules(pid) or []
    game = next((m for m in mods if m.name.lower() == GAME_EXE), None)
    if game is None or has_eac(m.name for m in mods):
        print("anti-cheat is loaded or the modules cannot be read; start the game with `eldendisk run`")
        return 3
    mem = ptx.WinRW(pid)
    state = Path(STATE)
    if a.undo:
        if not state.is_file():
            print(f"no {STATE}: nothing to undo (a new game process has its own colours anyway)")
            return 1
        saved = json.loads(state.read_text(encoding="utf-8"))
        if saved["pid"] != pid:
            print("the record is from another game process; nothing to undo")
            return 1
        print(f"restored {undo(mem, saved['record'])} of {len(saved['record'])} places")
        state.unlink()
        return 0
    plans = load_plans()
    wanted = [i for i in plans if not a.only or i in a.only]
    if not wanted:
        print(f"no such effect; the plans are for {', '.join(plans)}")
        return 1
    record = []
    print(f"pid {pid}; new colour (RGB): {tuple(a.target)} | blend: {a.blend or 'unchanged'}")
    for eid in wanted:
        plan = plans[eid]
        print(f"effect {eid}: scanning {len(mem.regions())} regions ...")
        bases, nearly = find_copies(mem, plan)
        print(f"  copies in memory: {len(bases)}" + "".join(f"  (almost: {hex(b)} with {n} of {len(plan['colours'])} colours)" for b, n in nearly[:3]))
        if not bases:
            print("  not found: cast the spell once so that the effect is loaded, then run this again.")
            continue
        if not a.apply:
            print(f"  would write {len(plan_writes(plan, a.target, a.blend))} places per copy")
            continue
        try:
            record += apply(mem, plan, bases, a.target, a.blend)
        except TintError as exc:
            print("  " + str(exc))
            continue
        print(f"  written; {len(record)} places so far")
    if not a.apply:
        print("dry run: nothing written. Add --apply to do it.")
        return 0
    if record:
        state.write_text(json.dumps({"pid": pid, "record": record}, indent=1), encoding="utf-8")
    print(f"written {len(record)} places; saved {STATE}. Cast the spell again and look at the fire. `--undo` puts it back.")
    return 0 if record else 2


if __name__ == "__main__":
    raise SystemExit(main())

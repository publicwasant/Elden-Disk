"""Level 3, step 2 (dev experiment): give the running game a rebuilt text table, without touching any file.

    python tools/patch_text.py            dry run: finds the tables (by the chain from the exe, no search) and says what it would do
    python tools/patch_text.py --apply    does it
    python tools/patch_text.py --undo     puts the game's own pointers back

What `probe_text.py` showed: the game keeps each text table (FMG) as it is in the file, except that the 8 bytes at 0x18
(where the string offsets are) hold an address, and ONE pointer in the game's memory points at the table. This tool builds
the table again with new text (innovate-spells slot 1 = goods id 2230000, and a visible rename of Flame, Grant Me
Strength), puts it into memory it allocates in the game, and changes that one pointer. The old table stays where it was;
`--undo` points back to it. Needs the game started with `eldendisk run` (no anti-cheat); refuses otherwise.

Reads the tables written by tools/dump_msgbnd.py (default msgdump\\item). Run from `code`. Opening the inventory again
shows the new text; nothing is saved in the game's files.
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
from eldendisk.extension.innovate_items.fmg import Fmg                   # noqa: E402

CHANGES = {
    "GoodsName": {6050: "Flame, Grant Me Strength (text test)", 2230000: "Reverse Curse Technique"},
    "GoodsInfo": {2230000: "Heals over time without a flash"},
    "GoodsCaption": {2230000: "A test text written by Elden-Disk.\nSecond line of the long text."},
}
STATE = "textpatch.json"

# Found by tools/probe_chain.py (exe 1.17.1): the pointer at eldenring.exe + CHAIN_RVA leads to an object that holds one
# pointer per text file, at CHAIN_ARRAY + file id * 8 (GoodsName 10, GoodsInfo 20, GoodsCaption 24: checked in game).
CHAIN_RVA, CHAIN_ARRAY = 0x3D61FB8, 0x1F20
FILE_IDS = {"GoodsName": 10, "GoodsInfo": 20, "GoodsCaption": 24}


# ---- pure parts (tested without a game) ---------------------------------------------------------------------------
def live_form(blob: bytes, base: int) -> bytes:
    """The table as the game holds it at `base`: the same bytes, the offsets position (0x18) turned into an address."""
    offsets_at, = struct.unpack_from("<q", blob, 0x18)
    return blob[:0x18] + struct.pack("<Q", base + offsets_at) + blob[0x20:]


def find_live(mem, blob: bytes):
    """Addresses where the game holds exactly `blob` in its live form."""
    return [a for a in pt.scan(mem, blob[:0x18]) if mem.read(a, len(blob)) == live_form(blob, a)]


def plan(mem, name: str, blob: bytes, rows: dict[int, str]):
    """What to do for one table: where it is, which pointer leads to it, the new table. Raises ValueError when unclear."""
    found = find_live(mem, blob)
    if len(found) != 1:
        raise ValueError(f"{name}: expected one live copy, found {len(found)}")
    base = found[0]
    pointers = pt.pointers_to(mem, base)
    if len(pointers) != 1:
        raise ValueError(f"{name}: expected one pointer to the table at {base:#x}, found {len(pointers)}")
    fmg = Fmg.read(blob)
    fmg.entries.update(rows)
    return {"name": name, "old_base": base, "pointer_at": pointers[0], "new": fmg.write()}


def plan_chain(mem, exe_base: int, name: str, blob: bytes, rows: dict[int, str]):
    """Like `plan`, without searching: follow the chain to the slot of this text file and check it holds the game's table."""
    raw = mem.read(exe_base + CHAIN_RVA, 8)
    obj = struct.unpack("<Q", raw)[0] if raw else 0
    slot = obj + CHAIN_ARRAY + FILE_IDS[name] * 8
    raw = mem.read(slot, 8) if obj else None
    base = struct.unpack("<Q", raw)[0] if raw else 0
    if not raw or mem.read(base, len(blob)) != live_form(blob, base):
        raise ValueError(f"{name}: the slot at {slot:#x} does not hold the game's own table (the game is not 1.17.1, it is "
                         "still starting, or the text is already patched: restart the game, or use --scan)")
    fmg = Fmg.read(blob)
    fmg.entries.update(rows)
    return {"name": name, "old_base": base, "pointer_at": slot, "new": fmg.write()}


def apply(mem, step) -> int:
    """Allocate, write the new table, then change the pointer (one aligned 8-byte write). Returns the new base."""
    new_base = mem.alloc(len(step["new"]))
    mem.write(new_base, live_form(step["new"], new_base))
    mem.write(step["pointer_at"], struct.pack("<Q", new_base))
    return new_base


def undo(mem, record) -> bool:
    """Put the old pointer back, only when the pointer still holds what we wrote."""
    now = mem.read(record["pointer_at"], 8)
    if now is None or struct.unpack("<Q", now)[0] != record["new_base"]:
        return False
    mem.write(record["pointer_at"], struct.pack("<Q", record["old_base"]))
    return True


# ---- Windows part -------------------------------------------------------------------------------------------------
class WinRW(pt.WinMem):
    """The probe's read view plus what this experiment needs: allocate and write in the game. Nothing else."""
    ACCESS = 0x10 | 0x400 | 0x20 | 0x8            # VM_READ | QUERY_INFORMATION | VM_WRITE | VM_OPERATION

    def __init__(self, pid: int):
        super().__init__(pid)
        from ctypes import wintypes
        k, ct = self.k32, self.ct
        k.VirtualAllocEx.argtypes = [wintypes.HANDLE, ct.c_void_p, ct.c_size_t, wintypes.DWORD, wintypes.DWORD]
        k.VirtualAllocEx.restype = ct.c_void_p
        k.WriteProcessMemory.argtypes = [wintypes.HANDLE, ct.c_void_p, ct.c_void_p, ct.c_size_t, ct.POINTER(ct.c_size_t)]
        k.WriteProcessMemory.restype = wintypes.BOOL

    def alloc(self, size: int) -> int:
        addr = self.k32.VirtualAllocEx(self.h, None, size, 0x3000, 0x04)          # reserve+commit, read/write
        if not addr:
            raise OSError(self.ct.get_last_error(), "VirtualAllocEx failed")
        return addr

    def write(self, addr: int, data: bytes) -> None:
        got = self.ct.c_size_t(0)
        if not self.k32.WriteProcessMemory(self.h, self.ct.c_void_p(addr), data, len(data), self.ct.byref(got)) \
                or got.value != len(data):
            raise OSError(self.ct.get_last_error(), f"WriteProcessMemory failed at {addr:#x}")


def main() -> int:
    from eldendisk.game.memory import list_modules
    from eldendisk.game.processes import GAME_EXE, find_pid, has_eac
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=r"msgdump\item")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--undo", action="store_true")
    ap.add_argument("--scan", action="store_true", help="search all memory instead of following the chain (slow)")
    a = ap.parse_args()
    pid = find_pid(GAME_EXE)
    if pid is None:
        print("eldenring.exe is not running (start it with `eldendisk run`)")
        return 1
    mods = list_modules(pid) or []
    main_mod = next((m for m in mods if m.name.lower() == GAME_EXE), None)
    main_base = main_mod.base if main_mod else 0
    if main_mod is None or has_eac(m.name for m in mods):
        print("anti-cheat is loaded or the modules cannot be read; start the game with `eldendisk run`")
        return 3
    mem = WinRW(pid)
    state = Path(STATE)
    if a.undo:
        if not state.is_file():
            print(f"no {STATE}: nothing to undo (a new game process has its own tables anyway)")
            return 1
        saved = json.loads(state.read_text(encoding="utf-8"))
        if saved["pid"] != pid:
            print("the record is from another game process; nothing to undo")
            return 1
        for rec in saved["steps"]:
            print(f"{rec['name']}: {'restored' if undo(mem, rec) else 'pointer changed since, left alone'}")
        return 0
    steps = []
    for name, rows in CHANGES.items():
        blob = (Path(a.dir) / f"{name}.fmg").read_bytes()
        try:
            step = plan(mem, name, blob, rows) if a.scan else plan_chain(mem, main_base, name, blob, rows)
        except ValueError as exc:
            print(f"{exc}; nothing written")
            return 1
        print(f"{name}: table at {step['old_base']:#x}, pointer at {step['pointer_at']:#x}, "
              f"{len(blob)} -> {len(step['new'])} bytes")
        steps.append(step)
    if not a.apply:
        print("dry run: nothing written. Add --apply to do it.")
        return 0
    record = {"pid": pid, "steps": []}
    for step in steps:
        new_base = apply(mem, step)
        record["steps"].append({"name": step["name"], "old_base": step["old_base"], "pointer_at": step["pointer_at"],
                                "new_base": new_base})
        print(f"{step['name']}: new table at {new_base:#x}, pointer changed")
    state.write_text(json.dumps(record, indent=1), encoding="utf-8")
    print(f"done; saved {STATE}. Open the inventory again and look at Flame, Grant Me Strength. `--undo` puts it back.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

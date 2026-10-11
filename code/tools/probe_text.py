"""Level 3, step 1c (read-only dev probe): where does the running game keep its item text?

    python tools/probe_text.py [--fmg msgdump\\item\\GoodsName.fmg] [--out textprobe.json]

Start the game with `eldendisk run` (no anti-cheat), wait for the title screen or the world, then run this from `code`
in another terminal. It only READS the game's memory (PROCESS_VM_READ | PROCESS_QUERY_INFORMATION), writes only --out.

What it looks for, in this order:
  1. exact copies of GoodsName.fmg (the file written by tools/dump_msgbnd.py) anywhere in the game's memory: address, region;
  2. every 8-byte value that points at the start of such a copy (the repository entry that the game follows), with the
     16 values around it, and whether it sits inside eldenring.exe's image or in the heap;
  3. the text "Flame, Grant Me Strength" (UTF-16) anywhere, and which copy it is inside.
Nothing here is a setting: it tells us whether the game keeps the file as it is (so a rebuilt file could be pointed at).
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

CHUNK = 16 * 1024 * 1024
MAX_POINTERS = 40
SAMPLE_TEXT = "Flame, Grant Me Strength"


# ---- pure parts (tested without a game) ---------------------------------------------------------------------------
def scan(mem, pattern: bytes, align: int = 1, chunk: int = CHUNK):
    """Addresses where `pattern` occurs in the readable memory of `mem` (regions read in chunks that overlap)."""
    for base, size, _kind, _prot in mem.regions():
        pos = 0
        while pos < size:
            n = min(chunk, size - pos)
            data = mem.read(base + pos, n + len(pattern) - 1 if pos + n < size else n)
            if data:
                i = data.find(pattern)
                while i != -1:
                    if i < n and (base + pos + i) % align == 0:
                        yield base + pos + i
                    i = data.find(pattern, i + 1)
            pos += n


def exact_copies(mem, blob: bytes):
    """Start addresses of full copies of `blob` (its first 0x40 bytes are the search key, the rest is compared)."""
    return [a for a in scan(mem, blob[:0x40]) if mem.read(a, len(blob)) == blob]


def pointers_to(mem, address: int):
    return list(scan(mem, struct.pack("<Q", address), align=8))


def region_of(mem, address: int):
    for base, size, kind, prot in mem.regions():
        if base <= address < base + size:
            return {"base": hex(base), "size": size, "type": kind, "protect": prot}
    return None


def context(mem, address: int, before: int = 8, after: int = 8):
    raw = mem.read(address - before * 8, (before + after) * 8)
    if raw is None:
        return None
    return [hex(v) for v in struct.unpack("<%dQ" % (before + after), raw)]


def diff_ranges(a: bytes, b: bytes, limit: int = 40):
    """Runs of bytes where `a` and `b` (same length) differ: [(offset, length)], at most `limit` runs, plus the total."""
    runs, i, n, total = [], 0, min(len(a), len(b)), 0
    while i < n:
        if a[i] != b[i]:
            j = i
            while j < n and a[j] != b[j]:
                j += 1
            total += 1
            if len(runs) < limit:
                runs.append((i, j - i))
            i = j
        else:
            i += 1
    return runs, total


def analyse(mem, blob: bytes, text_address: int, text_offset: int):
    """The game may keep the table with fix-ups (offsets turned into pointers): lay the file over the memory around the
    text we found (the strings are not moved) and say where the two differ."""
    base = text_address - text_offset
    cur = mem.read(base, len(blob))
    if cur is None:
        return {"base": hex(base), "readable": False}
    runs, total = diff_ranges(blob, cur)
    offsets_at = struct.unpack_from("<q", blob, 0x18)[0]
    first = struct.unpack_from("<8Q", cur, offsets_at) if offsets_at + 64 <= len(cur) else ()
    return {"base": hex(base), "readable": True, "bytes_equal": sum(x == y for x, y in zip(blob, cur)), "size": len(blob),
            "different_runs": total, "first_runs": [[hex(o), n] for o, n in runs],
            "header_file": blob[:0x40].hex(" "), "header_memory": cur[:0x40].hex(" "),
            "offset_table_at": hex(offsets_at), "offset_table_memory": [hex(v) for v in first],
            "offset_table_file": [hex(v) for v in struct.unpack_from("<8Q", blob, offsets_at)]}


# ---- Windows part -------------------------------------------------------------------------------------------------
class WinMem:
    """Read-only view of the game: regions (committed, readable) and reads. Never opens a write handle."""
    PROCESS_VM_READ, PROCESS_QUERY_INFORMATION = 0x10, 0x400
    MEM_COMMIT, PAGE_NOACCESS, PAGE_GUARD = 0x1000, 0x01, 0x100
    TYPES = {0x20000: "private", 0x40000: "mapped", 0x1000000: "image"}

    ACCESS = PROCESS_VM_READ | PROCESS_QUERY_INFORMATION

    def __init__(self, pid: int):
        import ctypes
        from ctypes import wintypes
        self.ct = ctypes
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)

        class MBI(ctypes.Structure):
            _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                        ("AllocationProtect", wintypes.DWORD), ("PartitionId", wintypes.WORD),
                        ("RegionSize", ctypes.c_size_t), ("State", wintypes.DWORD), ("Protect", wintypes.DWORD),
                        ("Type", wintypes.DWORD)]
        self.MBI = MBI
        k = self.k32
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
        k.VirtualQueryEx.restype = ctypes.c_size_t
        k.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.POINTER(ctypes.c_size_t)]
        k.ReadProcessMemory.restype = wintypes.BOOL
        self.h = k.OpenProcess(self.ACCESS, False, pid)
        if not self.h:
            raise OSError(ctypes.get_last_error(), f"OpenProcess failed for pid {pid}")
        self._regions = None

    def regions(self):
        if self._regions is None:
            out, addr, mbi = [], 0, self.MBI()
            while addr < 0x7FFFFFFF0000 and self.k32.VirtualQueryEx(self.h, addr, self.ct.byref(mbi), self.ct.sizeof(mbi)):
                size = mbi.RegionSize
                if (mbi.State == self.MEM_COMMIT and mbi.Protect and not mbi.Protect & (self.PAGE_NOACCESS | self.PAGE_GUARD)):
                    out.append((mbi.BaseAddress or 0, size, self.TYPES.get(mbi.Type, hex(mbi.Type)), mbi.Protect))
                addr = (mbi.BaseAddress or 0) + size
            self._regions = out
        return self._regions

    def read(self, addr: int, size: int):
        buf = self.ct.create_string_buffer(size)
        got = self.ct.c_size_t(0)
        ok = self.k32.ReadProcessMemory(self.h, self.ct.c_void_p(addr), buf, size, self.ct.byref(got))
        return buf.raw if ok and got.value == size else None


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from eldendisk.game.memory import list_modules
    from eldendisk.game.processes import GAME_EXE, find_pid, has_eac
    ap = argparse.ArgumentParser()
    ap.add_argument("--fmg", default=r"msgdump\item\GoodsName.fmg")
    ap.add_argument("--out", default="textprobe.json")
    a = ap.parse_args()
    blob = Path(a.fmg).read_bytes()
    pid = find_pid(GAME_EXE)
    if pid is None:
        print("eldenring.exe is not running (start it with `eldendisk run`)")
        return 1
    mods = list_modules(pid) or []
    main_mod = next((m for m in mods if m.name.lower() == GAME_EXE), None)
    if main_mod is None or has_eac(m.name for m in mods):
        print("anti-cheat is loaded or the modules cannot be read; start the game with `eldendisk run`")
        return 3
    mem = WinMem(pid)
    base = main_mod.base
    print(f"pid {pid}, eldenring.exe at {base:#x}; {len(mem.regions())} readable regions; scanning for {len(blob)} bytes ...")
    report = {"pid": pid, "exe_base": hex(base), "copies": [], "text_hits": []}
    copies = exact_copies(mem, blob)
    print(f"exact copies of {Path(a.fmg).name}: {len(copies)}")
    for addr in copies:
        entry = {"address": hex(addr), "region": region_of(mem, addr), "pointers": []}
        for p in pointers_to(mem, addr)[:MAX_POINTERS]:
            rva, where = p - base, region_of(mem, p)
            in_exe = bool(where) and where["type"] == "image" and 0 <= rva < 0x10000000      # the exe's own sections
            entry["pointers"].append({"at": hex(p), "in_exe_image": in_exe, "exe_rva": hex(rva) if in_exe else None,
                                      "region": where, "around": context(mem, p)})
        print(f"  {addr:#x}  pointers to it: {len(entry['pointers'])}")
        report["copies"].append(entry)
    needle = (SAMPLE_TEXT + "\0").encode("utf-16le")
    for addr in list(scan(mem, needle))[:20]:
        inside = next((c["address"] for c in report["copies"]
                       if int(c["address"], 16) <= addr < int(c["address"], 16) + len(blob)), None)
        report["text_hits"].append({"address": hex(addr), "inside_copy": inside})
        print(f"  text at {addr:#x} {'(inside copy ' + inside + ')' if inside else '(not inside a copy)'}")
    text_offset = blob.find(needle)
    report["analysis"] = []
    for hit in report["text_hits"]:
        if text_offset < 0:
            break
        addr = int(hit["address"], 16)
        info = analyse(mem, blob, addr, text_offset)
        base = int(info["base"], 16)
        info["pointers_to_base"] = [hex(p) for p in pointers_to(mem, base)[:MAX_POINTERS]]
        info["pointers_to_text"] = [hex(p) for p in pointers_to(mem, addr)[:MAX_POINTERS]]
        info["region"] = region_of(mem, base)
        report["analysis"].append(info)
        print(f"  table laid over the text: base {info['base']}, "
              f"{info.get('bytes_equal')} of {info.get('size')} bytes equal, {info.get('different_runs')} differing runs, "
              f"{len(info['pointers_to_base'])} pointers to its start")
    Path(a.out).write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"report: {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

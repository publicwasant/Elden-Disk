"""Read-only process memory access (Windows, ctypes).

This module only ever requests PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION. Writing lives in
writer/writer.py and is imported by `write` only. The host never imports this module (spec 1.6.2, I2).
"""
from __future__ import annotations

import ctypes
import struct
from dataclasses import dataclass

from . import _win

# QUERY_INFORMATION (not only LIMITED): VirtualQueryEx needs it to list the regions a scan reads (1.8.1: the reader finds the item
# names). Still read-only: nothing here can write or change the game.
ACCESS_MASK = _win.PROCESS_VM_READ | _win.PROCESS_QUERY_LIMITED_INFORMATION | _win.PROCESS_QUERY_INFORMATION
MEM_COMMIT, PAGE_NOACCESS, PAGE_GUARD = 0x1000, 0x01, 0x100
PAGE_NOCACHE, PAGE_WRITECOMBINE, MEM_PRIVATE = 0x200, 0x400, 0x20000      # a scan skips the first two (slow to read) and keeps private memory only

USER_MIN = 0x10000
USER_MAX = 0x7FFFFFFF0000


def is_user_ptr(p: int) -> bool:
    return USER_MIN <= p < USER_MAX


@dataclass(frozen=True)
class Module:
    name: str
    base: int
    path: str


def list_modules(pid: int) -> list[Module] | None:
    """Loaded modules of `pid`, or None if the snapshot failed (retry later)."""
    snap = _win.snapshot(_win.TH32CS_SNAPMODULE | _win.TH32CS_SNAPMODULE32, pid)
    if snap is None:
        return None
    try:
        entry = _win.MODULEENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        out: list[Module] = []
        ok = _win.k32.Module32FirstW(snap, ctypes.byref(entry))
        while ok:
            out.append(Module(entry.szModule, entry.modBaseAddr or 0, entry.szExePath))
            ok = _win.k32.Module32NextW(snap, ctypes.byref(entry))
        return out
    finally:
        _win.k32.CloseHandle(snap)


class ProcessMemory:
    """Read-only handle to another process (`access` is only widened by the writer package)."""

    def __init__(self, pid: int, access: int = ACCESS_MASK):
        h = _win.k32.OpenProcess(access, False, pid)
        if not h:
            raise OSError(ctypes.get_last_error(), f"OpenProcess failed for pid {pid}")
        self.pid = pid
        self._h = h

    def read(self, addr: int, size: int) -> bytes | None:
        """Exactly `size` bytes, or None on any failure (never zero-filled)."""
        if size <= 0 or not is_user_ptr(addr):
            return None
        buf = ctypes.create_string_buffer(size)
        n = ctypes.c_size_t(0)
        ok = _win.k32.ReadProcessMemory(self._h, ctypes.c_void_p(addr), buf, size, ctypes.byref(n))
        if not ok or n.value != size:
            return None
        return buf.raw

    def regions(self, strict: bool = False) -> list[tuple[int, int]]:
        """(base, size) of every committed region of the game that can be read (not no-access, not guard), user space only. `strict`
        (for a scan of the whole game) keeps only the game's own private memory (its heap) and leaves out what is slow or pointless to
        read: write-combined and uncached memory (shared with the graphics card), mapped files and the program's own image."""
        out, addr, mbi = [], 0, _win.MEMORY_BASIC_INFORMATION()
        while addr < 0x7FFFFFFF0000 and _win.k32.VirtualQueryEx(self._h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            size = mbi.RegionSize
            if mbi.State == MEM_COMMIT and mbi.Protect and not mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD):
                if not strict or (mbi.Type == MEM_PRIVATE and not mbi.Protect & (PAGE_NOCACHE | PAGE_WRITECOMBINE)):
                    out.append((mbi.BaseAddress or 0, size))
            addr = (mbi.BaseAddress or 0) + size
        return out

    def describe(self, addr: int) -> str:
        """What kind of memory `addr` is in (for the log): type, protection, the size of its region."""
        mbi = _win.MEMORY_BASIC_INFORMATION()
        if not _win.k32.VirtualQueryEx(self._h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            return "unknown"
        kind = {0x20000: "private", 0x40000: "mapped", 0x1000000: "image"}.get(mbi.Type, f"type {mbi.Type:#x}")
        return f"{kind}, protect {mbi.Protect:#x}, region {mbi.RegionSize >> 20} MB at {mbi.BaseAddress or 0:#x}"

    def alive(self) -> bool:
        code = _win.wintypes.DWORD(0)
        if not _win.k32.GetExitCodeProcess(self._h, ctypes.byref(code)):
            return False
        return code.value == _win.STILL_ACTIVE

    def close(self) -> None:
        if self._h:
            _win.k32.CloseHandle(self._h)
            self._h = None


# Helpers that work on anything with .read(addr, size) -> bytes | None
def read_u32(mem, addr: int) -> int | None:
    b = mem.read(addr, 4)
    return None if b is None else struct.unpack("<I", b)[0]


def read_ptr(mem, addr: int) -> int | None:
    b = mem.read(addr, 8)
    return None if b is None else struct.unpack("<Q", b)[0]

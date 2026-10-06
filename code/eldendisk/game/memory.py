"""Read-only process memory access (Windows, ctypes).

This module only ever requests PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION. Writing lives in
writer/writer.py and is imported by `write` only. The host never imports this module (spec 1.6.2, I2).
"""
from __future__ import annotations

import ctypes
import struct
from dataclasses import dataclass

from . import _win

ACCESS_MASK = _win.PROCESS_VM_READ | _win.PROCESS_QUERY_LIMITED_INFORMATION

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

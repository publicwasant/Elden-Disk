"""Read-only process memory access (Windows, ctypes).

Only PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION is ever requested.
"""
from __future__ import annotations

import ctypes
import struct
import sys
from dataclasses import dataclass

IS_WINDOWS = sys.platform == "win32"

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
ACCESS_MASK = PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION

STILL_ACTIVE = 259
TH32CS_SNAPPROCESS = 0x2
TH32CS_SNAPMODULE = 0x8
TH32CS_SNAPMODULE32 = 0x10

USER_MIN = 0x10000
USER_MAX = 0x7FFFFFFF0000


def is_user_ptr(p: int) -> bool:
    return USER_MIN <= p < USER_MAX


@dataclass(frozen=True)
class Module:
    name: str
    base: int
    path: str


if IS_WINDOWS:
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _u32 = ctypes.WinDLL("user32", use_last_error=True)
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class MODULEENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("th32ModuleID", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("GlblcntUsage", wintypes.DWORD),
            ("ProccntUsage", wintypes.DWORD),
            ("modBaseAddr", ctypes.c_void_p),
            ("modBaseSize", wintypes.DWORD),
            ("hModule", ctypes.c_void_p),
            ("szModule", ctypes.c_wchar * 256),
            ("szExePath", ctypes.c_wchar * 260),
        ]

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.ReadProcessMemory.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t),
    ]
    _k32.ReadProcessMemory.restype = wintypes.BOOL
    _k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    _k32.GetExitCodeProcess.restype = wintypes.BOOL
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.CloseHandle.restype = wintypes.BOOL
    _k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for _fn in (_k32.Module32FirstW, _k32.Module32NextW):
        _fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
        _fn.restype = wintypes.BOOL
    for _fn in (_k32.Process32FirstW, _k32.Process32NextW):
        _fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        _fn.restype = wintypes.BOOL

    _u32.GetForegroundWindow.restype = wintypes.HWND
    _u32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _u32.GetWindowThreadProcessId.restype = wintypes.DWORD


def is_window_active(pid: int | None) -> bool:
    """True if the foreground window belongs to process `pid`, or if pid is None / non-Windows."""
    if not IS_WINDOWS or pid is None:
        return True
    hwnd = _u32.GetForegroundWindow()
    if not hwnd:
        return False
    fg_pid = wintypes.DWORD(0)
    _u32.GetWindowThreadProcessId(hwnd, ctypes.byref(fg_pid))
    return fg_pid.value == pid


def _snapshot(flags: int, pid: int):
    h = _k32.CreateToolhelp32Snapshot(flags, pid)
    if h is None or h == INVALID_HANDLE_VALUE:
        return None
    return h


def list_modules(pid: int) -> list[Module] | None:
    """Loaded modules of `pid`, or None if the snapshot failed (retry later)."""
    snap = _snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snap is None:
        return None
    try:
        entry = MODULEENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        out: list[Module] = []
        ok = _k32.Module32FirstW(snap, ctypes.byref(entry))
        while ok:
            out.append(Module(entry.szModule, entry.modBaseAddr or 0, entry.szExePath))
            ok = _k32.Module32NextW(snap, ctypes.byref(entry))
        return out
    finally:
        _k32.CloseHandle(snap)


def find_pid(exe_name: str) -> int | None:
    snap = _snapshot(TH32CS_SNAPPROCESS, 0)
    if snap is None:
        return None
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = _k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == exe_name.lower():
                return int(entry.th32ProcessID)
            ok = _k32.Process32NextW(snap, ctypes.byref(entry))
        return None
    finally:
        _k32.CloseHandle(snap)


class ProcessMemory:
    """Read-only handle to another process."""

    def __init__(self, pid: int):
        h = _k32.OpenProcess(ACCESS_MASK, False, pid)
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
        ok = _k32.ReadProcessMemory(self._h, ctypes.c_void_p(addr), buf, size, ctypes.byref(n))
        if not ok or n.value != size:
            return None
        return buf.raw

    def alive(self) -> bool:
        code = wintypes.DWORD(0)
        if not _k32.GetExitCodeProcess(self._h, ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE

    def close(self) -> None:
        if self._h:
            _k32.CloseHandle(self._h)
            self._h = None


# Helpers that work on anything with .read(addr, size) -> bytes | None
def read_u32(mem, addr: int) -> int | None:
    b = mem.read(addr, 4)
    return None if b is None else struct.unpack("<I", b)[0]


def read_ptr(mem, addr: int) -> int | None:
    b = mem.read(addr, 8)
    return None if b is None else struct.unpack("<Q", b)[0]

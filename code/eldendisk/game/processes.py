"""Who is running: process lookup, start time, anti-cheat detection, foreground window, exe hash.

Nothing here can read or write the memory of another process: the only access it ever asks for is
PROCESS_QUERY_LIMITED_INFORMATION (start time), so the host may use it (spec 1.6.2, I2).
"""
from __future__ import annotations

import ctypes
import hashlib
from pathlib import Path

from . import _win

GAME_EXE = "eldenring.exe"
EAC_MARKER = "easyanticheat"
ANTICHEAT_PROCESS_MARKERS = ("easyanticheat", "start_protected_game")


def has_eac(module_names) -> bool:
    return any(EAC_MARKER in n.lower() for n in module_names)


def anticheat_processes(process_names) -> list[str]:
    """Running processes that indicate EasyAntiCheat (the host refuses to start while any exist)."""
    return sorted({n for n in process_names if any(m in n.lower() for m in ANTICHEAT_PROCESS_MARKERS)})


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:  # read-only
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_pid(exe_name: str) -> int | None:
    snap = _win.snapshot(_win.TH32CS_SNAPPROCESS, 0)
    if snap is None:
        return None
    try:
        entry = _win.PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = _win.k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == exe_name.lower():
                return int(entry.th32ProcessID)
            ok = _win.k32.Process32NextW(snap, ctypes.byref(entry))
        return None
    finally:
        _win.k32.CloseHandle(snap)


def list_process_names() -> list[str]:
    """Image names of all running processes (empty list if the snapshot failed)."""
    snap = _win.snapshot(_win.TH32CS_SNAPPROCESS, 0)
    if snap is None:
        return []
    try:
        entry = _win.PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        out: list[str] = []
        ok = _win.k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            out.append(entry.szExeFile)
            ok = _win.k32.Process32NextW(snap, ctypes.byref(entry))
        return out
    finally:
        _win.k32.CloseHandle(snap)


def process_started(pid: int) -> int | None:
    """Creation time of `pid` as a Windows FILETIME integer (100 ns ticks), or None when it cannot be read.

    (pid, start time) identifies one process for good: a recycled pid has a different start time.
    """
    h = _win.k32.OpenProcess(_win.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        created, exited, kernel, user = (_win.wintypes.FILETIME() for _ in range(4))
        if not _win.k32.GetProcessTimes(h, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
            return None
        return (created.dwHighDateTime << 32) | created.dwLowDateTime
    finally:
        _win.k32.CloseHandle(h)


def is_window_active(pid: int | None) -> bool:
    """True if the foreground window belongs to process `pid`, or if pid is None / non-Windows."""
    if not _win.IS_WINDOWS or pid is None:
        return True
    hwnd = _win.u32.GetForegroundWindow()
    if not hwnd:
        return False
    fg_pid = _win.wintypes.DWORD(0)
    _win.u32.GetWindowThreadProcessId(hwnd, ctypes.byref(fg_pid))
    return fg_pid.value == pid

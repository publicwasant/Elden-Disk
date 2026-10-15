"""Windows bindings (ctypes) shared by processes.py, memory.py and the writer. Nothing here opens a process by itself."""
from __future__ import annotations

import ctypes
import sys

IS_WINDOWS = sys.platform == "win32"

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_QUERY_INFORMATION = 0x0400      # VirtualQueryEx: to list the game's memory regions (a scan: the writer, and since 1.8.1 the item names)
STILL_ACTIVE = 259
PROCESS_MODE_BACKGROUND_BEGIN = 0x00100000      # SetPriorityClass: low CPU, I/O and memory priority for this process
TH32CS_SNAPPROCESS = 0x2
TH32CS_SNAPMODULE = 0x8
TH32CS_SNAPMODULE32 = 0x10

if IS_WINDOWS:
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    u32 = ctypes.WinDLL("user32", use_last_error=True)
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

    class MEMORY_BASIC_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BaseAddress", ctypes.c_void_p),
            ("AllocationBase", ctypes.c_void_p),
            ("AllocationProtect", wintypes.DWORD),
            ("PartitionId", wintypes.WORD),
            ("RegionSize", ctypes.c_size_t),
            ("State", wintypes.DWORD),
            ("Protect", wintypes.DWORD),
            ("Type", wintypes.DWORD),
        ]

    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.ReadProcessMemory.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t),
    ]
    k32.ReadProcessMemory.restype = wintypes.BOOL
    k32.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t]
    k32.VirtualQueryEx.restype = ctypes.c_size_t
    k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k32.GetExitCodeProcess.restype = wintypes.BOOL
    k32.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
                                    ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME)]
    k32.GetProcessTimes.restype = wintypes.BOOL
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.CloseHandle.restype = wintypes.BOOL
    k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for _fn in (k32.Module32FirstW, k32.Module32NextW):
        _fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
        _fn.restype = wintypes.BOOL
    for _fn in (k32.Process32FirstW, k32.Process32NextW):
        _fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        _fn.restype = wintypes.BOOL

    u32.GetForegroundWindow.restype = wintypes.HWND
    u32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    u32.GetWindowThreadProcessId.restype = wintypes.DWORD


def snapshot(flags: int, pid: int):
    """A Toolhelp snapshot handle, or None on failure. The caller closes it."""
    h = k32.CreateToolhelp32Snapshot(flags, pid)
    if h is None or h == INVALID_HANDLE_VALUE:
        return None
    return h


def go_easy() -> str:
    """Ask Windows to treat THIS process as background work (it then gives way to the game for CPU, disk and memory) and to wake it from
    a sleep after about a millisecond instead of about fifteen. Only for the short-lived process that scans the game. -> what was
    granted, for the log ("" when nothing, or not Windows). Never raises: it is a courtesy, not a need."""
    if not IS_WINDOWS:
        return ""
    got = []
    try:
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k32.SetPriorityClass.restype = wintypes.BOOL
        if k32.SetPriorityClass(k32.GetCurrentProcess(), PROCESS_MODE_BACKGROUND_BEGIN):
            got.append("background priority")
    except Exception:
        pass
    try:
        winmm = ctypes.WinDLL("winmm")
        if winmm.timeBeginPeriod(1) == 0:
            got.append("1 ms timer")
    except Exception:
        pass
    return " and ".join(got)

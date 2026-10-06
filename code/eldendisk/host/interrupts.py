"""Console close / logoff / shutdown (Windows). Ctrl+C is left to Python (KeyboardInterrupt).

Windows kills the process a few seconds after these events, so the handler does one quick thing: call `on_close`
(which marks the session RESTORE_PENDING). The game is not touched; the save is restored by `vault restore`.
"""
from __future__ import annotations

import sys
from typing import Callable

CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT = 2, 5, 6
_KEEP = []   # the ctypes callback must outlive the call that registered it


def install(on_close: Callable[[], None]) -> Callable[[], None]:
    """Register the handler. Returns a function that removes it. A no-op away from Windows."""
    if sys.platform != "win32":
        return lambda: None
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handler_t = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

    def handler(event: int) -> bool:
        if event in (CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT):
            try:
                on_close()
            except Exception:
                pass
            return True
        return False   # Ctrl+C / Ctrl+Break: Python raises KeyboardInterrupt

    cb = handler_t(handler)
    _KEEP.append(cb)
    k32.SetConsoleCtrlHandler.argtypes = [handler_t, wintypes.BOOL]
    k32.SetConsoleCtrlHandler.restype = wintypes.BOOL
    k32.SetConsoleCtrlHandler(cb, True)

    def remove() -> None:
        k32.SetConsoleCtrlHandler(cb, False)
        if cb in _KEEP:
            _KEEP.remove(cb)

    return remove

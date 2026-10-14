"""Finding the game and checking it is safe to touch, once, for `read` and `write` (spec 1.6.2: replaces four copies).

`locate` opens no handle on the game (Toolhelp snapshots only). The caller decides which handle to open afterwards:
read-only for the reader, read+write for the writer after the session check.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .memory import Module, ProcessMemory, list_modules
from .processes import (GAME_EXE, anticheat_processes, find_pid, has_eac, list_process_names, process_started,
                        exe_sha256)
from .profile import Profile, load_profile

EXIT_ERROR, EXIT_UNSUPPORTED, EXIT_EAC, EXIT_NO_SESSION = 1, 2, 3, 5


class AttachError(RuntimeError):
    def __init__(self, message: str, code: int = EXIT_ERROR):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Target:
    pid: int
    started: int | None
    main: Module
    sha256: str
    profile: Profile

    @property
    def base(self) -> int:
        return self.main.base

    @property
    def exe_path(self) -> Path:
        return Path(self.main.path)


def locate(offsets: Path) -> Target:
    """The running game, or AttachError (exit code inside): not running, EAC loaded, unsupported exe."""
    pid = find_pid(GAME_EXE)
    if pid is None:
        raise AttachError("eldenring.exe is not running")
    mods = list_modules(pid) or []
    main = next((m for m in mods if m.name.lower() == GAME_EXE), None)
    if main is None:
        # Under EasyAntiCheat the module list of the game cannot be read at all, so "no module" is the first sign of it
        # (Steam's offline mode does not switch EAC off; only `eldendisk run` starts the game without it).
        if anticheat_processes(list_process_names()):
            raise AttachError("the game was started with EasyAntiCheat (its modules cannot be read, anti-cheat "
                              "processes are running); not attaching. Start the game with `eldendisk run`, "
                              "not from Steam", EXIT_EAC)
        raise AttachError("cannot list the modules of eldenring.exe (still starting, or access denied: run the "
                          "terminal as the same user and not elevated unless the game is)")
    if has_eac(m.name for m in mods):
        raise AttachError("EasyAntiCheat is loaded in eldenring.exe; not attaching. "
                          "Start the game offline with `eldendisk run`.", EXIT_EAC)
    sha = exe_sha256(Path(main.path))
    profile, reason = load_profile(Path(offsets), sha)
    if profile is None:
        raise AttachError(f"no verified profile for this eldenring.exe ({reason}); exe sha256: {sha}", EXIT_UNSUPPORTED)
    return Target(pid, process_started(pid), main, sha, profile)


def eac_loaded(pid: int) -> bool:
    """Re-scan the modules of a running game (EAC can appear later)."""
    mods = list_modules(pid)
    return bool(mods) and has_eac(m.name for m in mods)


def open_read(target: Target) -> ProcessMemory:
    return ProcessMemory(target.pid)

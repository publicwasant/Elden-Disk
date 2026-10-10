"""`hash`: SHA-256 of eldenring.exe, the key for offsets.json."""
from __future__ import annotations

from ..game.processes import GAME_EXE, sha256_file
from ..host.launcher import find_game_dir
from ..logbook import book


def cmd_hash(args) -> int:
    d = find_game_dir(args.game_dir)
    digest = sha256_file(d / GAME_EXE)
    book.d("hash", f"{d / GAME_EXE}: {digest}")
    print(digest)   # the result, alone on stdout so that it can be piped
    return 0

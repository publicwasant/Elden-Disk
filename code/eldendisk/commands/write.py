"""`write --set NAME=VALUE... --refill LIST`: apply edits once to the running game, inside an authorised session."""
from __future__ import annotations

from pathlib import Path

from ..console import require_windows_x64
from ..logbook import book
from ..game.attach import EXIT_NO_SESSION, AttachError, Target, locate
from ..game.layout import Layout
from ..game.processes import process_started
from ..vault import VaultError, authorise, resolve_vault
from ..vault import session as vault_session
from ..writer.writer import MemoryWriter, WritableProcessMemory, WriteGate, parse_policy


def cmd_write(args) -> int:
    require_windows_x64()
    try:
        policy = parse_policy(args.set, args.refill)
    except ValueError as exc:   # unknown or unsettable name, bad value
        book.e("write", str(exc))
        return 1
    if policy.empty:
        book.i("write", "nothing to do")
        return 0

    try:
        record = vault_session.load(resolve_vault(args.vault))
    except VaultError as exc:
        book.e("write", str(exc))
        return EXIT_NO_SESSION
    try:
        target: Target = locate(Path(args.offsets))
    except AttachError as exc:
        book.e("write", str(exc))
        return exc.code

    problems = authorise(record, game_pid=target.pid, game_started=target.started,
                         exe_sha256=target.sha256, started_of=process_started)
    if problems:
        book.e("write", "refused, no edit was made:")
        for p in problems:
            book.e("write", f"  {p}")
        return EXIT_NO_SESSION

    mem = WritableProcessMemory(target.pid)
    try:
        gate = WriteGate()
        gate.open()   # only after the session, anti-cheat and profile checks above
        writer = MemoryWriter(mem, Layout(mem, target.profile, target.base), policy, gate,
                              log=lambda m: book.d("write", m))
        results = writer.apply_once()
    finally:
        mem.close()

    failed = [r.name for r in results if not r.wrote]
    for r in results:
        if r.wrote:
            book.ok("write", f"{r.name} = {r.value}")
    if writer.skipped or failed:
        for why in writer.skipped:
            book.e("write", f"not applied: {why}")
        if failed:
            book.e("write", f"failed or did not stick: {', '.join(failed)}")
        return 1
    if not results:
        book.i("write", "values already match")
    return 0

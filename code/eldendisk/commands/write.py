"""`write --set NAME=VALUE... --refill LIST --reset NAME...`: apply edits once to the running game, inside an authorised
session. Names under `params.` edit the game's own tables (and `--reset` puts the game's own values back)."""
from __future__ import annotations

from pathlib import Path

from ..console import require_windows_x64
from ..logbook import book
from ..game.attach import EXIT_NO_SESSION, EXIT_UNSUPPORTED, AttachError, Target, locate
from ..game.layout import Layout
from ..game.params import ParamLockedError, ParamNameError
from ..game.processes import process_started
from ..vault import VaultError, authorise, resolve_vault
from ..vault import session as vault_session
from ..writer.paramedit import SNAPSHOT_NAME, Snapshot
from ..writer.writer import MemoryWriter, WritableProcessMemory, WriteGate, parse_policy, plan_params


def cmd_write(args) -> int:
    require_windows_x64()
    try:
        policy = parse_policy(args.set, args.refill, getattr(args, "reset", None))
    except ValueError as exc:   # unknown or unsettable name, bad value
        book.e("write", str(exc))
        return 1
    if policy.empty:
        book.i("write", "nothing to do")
        return 0

    try:
        vault_root = resolve_vault(args.vault)
        record = vault_session.load(vault_root)
    except VaultError as exc:
        book.e("write", str(exc))
        return EXIT_NO_SESSION
    try:
        target: Target = locate(Path(args.offsets))
    except AttachError as exc:
        book.e("write", str(exc))
        return exc.code

    snapshot = Snapshot(vault_root / SNAPSHOT_NAME, target.pid, target.started)    # the game's own values, for --reset
    snapshot.load()
    try:   # what the params names mean needs the profile; a read-only field is refused before the session is looked at
        policy, notes = plan_params(target.profile.params, policy, snapshot)
    except ParamLockedError as exc:
        book.e("write", f"{exc}; nothing was written")
        return EXIT_UNSUPPORTED
    except ParamNameError as exc:
        book.e("write", f"{exc}; nothing was written")
        return 1
    for note in notes:
        book.i("write", note)

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
                              log=lambda m: book.d("write", m), snapshot=snapshot)
        results = writer.apply_once()
    finally:
        mem.close()
        try:
            snapshot.save()
        except OSError as exc:
            book.w("write", f"could not save {SNAPSHOT_NAME} ({exc}); --reset of these values will not find the game's own value")

    failed = [r.name for r in results if not r.wrote]
    for r in results:
        if r.wrote:
            book.ok("write", f"{r.name} = {r.value}" + (f"  ({r.note})" if r.note else ""))
    if writer.skipped or failed:
        for why in writer.skipped:
            book.e("write", f"not applied: {why}")
        if failed:
            book.e("write", f"failed or did not stick: {', '.join(failed)}")
        return 1
    if not results:
        book.i("write", "values already match")
    return 0

"""`vault status | list | verify | restore | keep | prune`.

Actions (restore, keep, prune, verify) report as log events; the queries (status, list) print their result.
"""
from __future__ import annotations

from pathlib import Path

from .. import ui
from ..console import require_windows_x64
from ..game.processes import GAME_EXE, find_pid, process_started
from ..logbook import book
from ..vault import SaveVault, SessionState, VaultError, recover, resolve_vault
from ..vault.recover import keep_from_record
from ..vault.session import host_alive
from ..vault.vault import REGULATION_DIR, REGULATION_NAME
from .common import live_dir, session_log


def _vault(args) -> SaveVault:
    return SaveVault(resolve_vault(args.vault))


def cmd_restore(args) -> int:
    require_windows_x64()
    vault, slog = _vault(args), session_log()
    running = lambda: find_pid(GAME_EXE) is not None
    archive = not args.no_archive_contaminated
    if not args.snapshot:
        return recover(vault, game_running=running, archive=archive, log=slog)
    if vault.read_session() is not None:
        slog.e("vault", "an unresolved session exists; run `eldendisk vault restore` without --snapshot first")
        return 1
    if running():
        slog.e("vault", "eldenring.exe is running; close it before restoring")
        return 1
    live, snap_dir = live_dir(args.save_dir), vault.snapshot_path(args.snapshot)
    safety = vault.snapshot(live, suffix="-pre-restore")  # what is there now stays recoverable
    slog.i("vault", f"current save kept as {safety.dir.name}")
    vault.restore(snap_dir, live)
    problems = vault.verify_live(live, vault.load_manifest(snap_dir)["files"])
    if problems:
        slog.e("vault", "verification failed: " + "; ".join(problems[:3]))
        return 4
    slog.ok("vault", f"restored {args.snapshot}, byte-identical")
    return 0


def cmd_keep(args) -> int:
    """Accept the modified save as the new baseline (what a manual "kill the host and delete the vault" did)."""
    require_windows_x64()
    vault, slog = _vault(args), session_log()
    record = vault.read_session()
    if record is None:
        slog.i("vault", "nothing to keep: no unresolved session")
        return 0
    if record.state == SessionState.RESTORING:
        slog.e("vault", "a restore was interrupted, so the save may be half restored; run `eldendisk vault restore` instead")
        return 1
    if find_pid(GAME_EXE) is not None:
        slog.e("vault", "eldenring.exe is running; close it so that the game has written its save")
        return 1
    if host_alive(record, process_started):
        slog.e("vault", "the host (`eldendisk run`) is still running and would restore the save when the game exits; stop it first")
        return 1
    if not args.yes:
        ui.result("warn", "this keeps the CURRENT save as the new baseline and ends the session")
        ui.fields([("save", record.live_save_dir),
                   ("backup", "the current save is snapshotted first"),
                   ("kept", f"pre-session snapshot {Path(record.snapshot_dir).name} stays in the vault")]
                  + ([("regulation", "the game's own regulation.bin is put back first")] if record.regulation else []))
        ui.out()
        ui.out("     run again with --yes to do it, or `eldendisk vault restore` to go back to the pre-session save")
        return 1
    return keep_from_record(vault, record, log=slog)


def cmd_status(args) -> int:
    vault = _vault(args)
    s = vault.status()
    rec = s["session"]
    rows = []
    if s["session_error"]:
        book.d("vault", f"session record unreadable: {s['session_error']}")
        ui.result("error", "session record unreadable, the live save cannot be trusted")
        rows.append(("detail", s["session_error"]))
    elif rec:
        ui.result("error", f"session {rec.state.value}: the live save is NOT trusted until it is restored")
        if rec.state.value == "RUNNING":
            rows.append(("running", f"host pid {rec.host_pid}, game pid {rec.game_pid}"))
        if rec.regulation:
            rows.append(("regulation", "a different regulation.bin was swapped into the game folder; the restore puts the original back"))
        rows += [("since", rec.created), ("snapshot", rec.snapshot_dir),
                 ("next", f"close the game, then run `{vault.restore_hint()}`")]
    else:
        ui.result("ok", "no unresolved session, the live save is trusted")
    w = s["world"]
    rows.append(("regulation", f"{w['path']} ({w['size'] / 2**20:.1f} MiB, sha256 {w['sha256'][:12]}): the next `run` with the vault ON swaps it in"
                 if w else f"no file: put yours at {vault.root / REGULATION_DIR / REGULATION_NAME} to swap it in "
                           "(the folder is not created for you); without it the game keeps its own"))
    rows.append(("snapshots", f"{s['snapshots']}, last {s['last'] or '-'}"
                 + (", verified" if s["last"] and not s["last_problems"] else "")))
    if s["last"] and s["last_problems"]:
        rows.append(("problems", "; ".join(s["last_problems"][:3])))
    rows += [("vault", f"{s['vault_bytes'] / 2**20:.1f} MiB in {vault.root}")]
    ui.fields(rows)
    return 4 if rec or s["session_error"] else 0


def cmd_list(args) -> int:
    rows = _vault(args).list_snapshots(verify=not args.fast)
    if not rows:
        ui.result("info", "no snapshots")
        return 0
    cells = {True: ("ok", "verified"), False: ("error", "DAMAGED")}
    ui.out(f" {'snapshot':<24} {'size':>10}  status")
    for r in rows:
        kind, text = cells.get(r["verified"], ("info", "not checked" if r["has_manifest"] else "no manifest"))
        ui.out(f" {r['name']:<24} {r['size'] / 2**20:>7.1f} MiB  {ui.mark(kind)} {text}")
    return 0


def cmd_verify(args) -> int:
    v = _vault(args)
    problems = v.verify_snapshot(v.snapshot_path(args.snapshot))
    if problems:
        for p in problems:
            book.e("vault", p)
        return 1
    book.ok("vault", f"snapshot {args.snapshot} matches its manifest")
    return 0


def cmd_prune(args) -> int:
    gone = _vault(args).prune(args.keep)
    book.ok("vault", f"deleted {len(gone)} snapshot(s), kept the newest {args.keep}")
    if gone:
        book.d("vault", "deleted: " + ", ".join(gone))
    return 0


COMMANDS = {"restore": cmd_restore, "keep": cmd_keep, "status": cmd_status, "list": cmd_list, "verify": cmd_verify, "prune": cmd_prune}


def cmd_vault(args) -> int:
    try:
        return COMMANDS[args.vault_cmd](args)
    except VaultError as exc:
        book.e("vault", str(exc))
        return 1

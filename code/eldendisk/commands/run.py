"""`run`: the host. Vault backup -> offline launch -> wait for the game -> restore. It never reads game memory."""
from __future__ import annotations

from pathlib import Path

from ..console import require_windows_x64
from ..logbook import book
from ..game.processes import GAME_EXE, anticheat_processes, find_pid, list_process_names, process_started, sha256_file
from ..game.profile import load_profile
from ..host import launcher
from ..host.host import Hooks, Session, State
from ..paths import describe_resource
from ..vault import GameFolderGuard, SaveVault, VaultError, resolve_vault
from .common import begin, live_dir, session_log


STEAM_EXE = "steam.exe"
STEAM_CLOUD_NOTE = ("Steam is running: Steam Cloud may sync the save when the game exits (not verified). "
                    "Use Steam offline mode, or turn Steam Cloud off for Elden Ring")


def auto_prune(vault: SaveVault, keep: int) -> None:
    """After a finished session keep only the newest `keep` snapshots (0 = never). A failure is only a warning."""
    if keep <= 0:
        return
    try:
        if vault.read_session() is not None:
            return
        gone = vault.prune(keep)
    except (VaultError, OSError) as exc:
        book.w("vault", f"could not prune old snapshots: {exc}")
        return
    if gone:
        book.ok("vault", f"pruned {len(gone)} old snapshot(s), kept the newest {keep}")
        book.d("vault", "pruned: " + ", ".join(gone))


def cmd_run(args) -> int:
    require_windows_x64()
    try:
        vault_path = resolve_vault(args.vault, remember=True)   # an explicit --vault is remembered, like --save-dir
    except VaultError as exc:
        book.e("run", str(exc))
        return 1
    game_dir = launcher.find_game_dir(args.game_dir)
    sha = sha256_file(game_dir / GAME_EXE)
    vault, live = SaveVault(vault_path), live_dir(args.save_dir)

    book.d("config", f"offsets: {args.offsets} ({describe_resource(args.offsets)})")
    begin(args, "run", [("vault", str(vault_path)), ("save", str(live)), ("game", str(game_dir))])

    def extra() -> list[str]:
        out = []
        profile, reason = load_profile(Path(args.offsets), sha)
        if profile is None:
            out.append(f"no usable profile for this eldenring.exe ({reason}); `read` and `write` could not attach")
        root, gd = vault_path.resolve(), game_dir.resolve()
        if root == gd or gd in root.parents:
            out.append("the vault must not be inside the game folder")
        return out

    hooks = Hooks(
        find_game_pid=lambda: find_pid(GAME_EXE),
        process_started=process_started,
        anticheat_running=lambda: bool(anticheat_processes(list_process_names())),
        launch=lambda: launcher.launch(game_dir),
        exe_sha256=sha, game_dir=game_dir, game_guard=GameFolderGuard(game_dir), extra_preflight=extra,
        launch_timeout=args.launch_timeout,
    )
    if any(n.lower() == STEAM_EXE for n in list_process_names()):
        book.w("steam", STEAM_CLOUD_NOTE)
    session = Session(vault, live, hooks, archive_contaminated=not args.no_archive_contaminated,
                      log=session_log())
    rc = session.run()
    if State.RESTORING in session.history:   # a session really ran; never prune a vault that still owes a restore
        auto_prune(vault, args.keep)
    return rc

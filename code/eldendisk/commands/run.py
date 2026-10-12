"""`run`: the host. Vault backup -> offline launch -> wait for the game -> restore. It never reads game memory."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import eldendisk
from ..console import require_windows_x64
from .. import extension, ui
from ..logbook import EXT_TAG, Tail, book
from ..game.processes import GAME_EXE, anticheat_processes, find_pid, list_process_names, process_started, sha256_file
from ..game.profile import load_profile
from ..host import launcher
from ..host.host import Hooks, Session, State
from ..paths import HERE, describe_resource, get_resource_path
from ..vault import GameFolderGuard, SaveVault, VaultError, resolve_vault
from .common import begin, live_dir, session_log
from .extension import ext_dir, prepare_regulation, spec_file
from ..extension.innovate_items.spells.service import ExtensionError, GateFailed


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


TEXT_MODES = ("secured", "last", "built")      # the regulation.bin is the extension's: the design's text belongs to it


def design_has_text(args, vault_path: Path) -> bool:
    """Is there any text in the design for the spells the build holds? (Nothing to start otherwise.)"""
    try:
        ci = extension.open_spells(ext_dir(args, vault_path), spec_file(args))
        sel, _note = ci.selection()
        return any(any(t.values()) for t in ci.texts(sel).values())
    except ExtensionError:
        return False


def design_has_flame(args, vault_path: Path) -> bool:
    """Does a spell of the design name a flame_color, or a colour for its golden_eyes? (Nothing to start otherwise.)"""
    try:
        ci = extension.open_spells(ext_dir(args, vault_path), spec_file(args))
        sel, _note = ci.selection()
        return ci.flame_color(sel)[0] is not None or ci.eyes_color(sel)[0] is not None
    except ExtensionError:
        return False


def text_command(args, vault_path: Path, flag: str = "--text") -> tuple[list[str], str | None]:
    """The command that gives the running game the design's text, and the folder to run it in: `eldendisk write --text --when-loaded`
    (`--flame-color` for the colour of the fire). `run` itself never touches the game's memory; this is a separate process, as
    if you typed it in another terminal."""
    frozen = getattr(sys, "frozen", False)
    cmd = [sys.executable] if frozen else [sys.executable, "-m", "eldendisk"]
    cmd += ["write", flag, "--when-loaded"]
    if getattr(args, "vault", None):                 # the vault `run` was told is remembered, so the step finds the same one without being told
        cmd += ["--vault", str(vault_path)]
    if str(args.offsets) != str(get_resource_path("offsets.json", default_dir=HERE)):      # only an offsets.json the user chose
        cmd += ["--offsets", str(args.offsets)]
    for flag, value in (("--spec", getattr(args, "spec", None)), ("--extension-dir", getattr(args, "extension_dir", None))):
        if value:
            cmd += [flag, str(value)]
    return cmd, None if frozen else str(Path(eldendisk.__file__).resolve().parent.parent)


def start_text(args, vault_path: Path, spawn=subprocess.Popen, flag: str = "--text"):
    """Start the text step (or, with flag --flame-color, the fire colour step) in the background. Its lines appear in this console
    and in the log; if it fails the game goes on."""
    cmd, cwd = text_command(args, vault_path, flag)
    book.d(EXT_TAG, "starting: " + " ".join(["eldendisk"] + cmd[1 if getattr(sys, "frozen", False) else 3:]))
    quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL} if getattr(args, "verbose", False) else {}   # -v shows its log lines
    return spawn(cmd, cwd=cwd, creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0), **quiet)


def start_flame(args, vault_path: Path):
    return start_text(args, vault_path, flag="--flame-color")


def _regulation(args, vault: SaveVault, game_dir: Path, protect: bool) -> tuple:
    """-> (the regulation.bin to swap in for this session or None, mode). mode: "none" | "file" (--regulation) | "secured"
    (the confirmed copy, nothing built) | "last" (the latest build, unchanged since, nothing built) | "built" (a new build the gate
    passed). `--regulation FILE` wins. Otherwise, with the vault ON, the extension swaps the secured file, or the latest build, when
    the design is unchanged and builds (a few seconds) when it is not: the spells the last `--add` chose, every spell without one. The vault
    is what makes that safe: it puts the game's file back. With the vault OFF the extension does not run. A build error or a
    failed gate stops `run` (ExtensionError / GateFailed): nothing is swapped, the game is not started.
    The 1.6.4 place `<vault>/regulation/regulation.bin` is not read any more."""
    legacy = vault.legacy_world()
    if legacy is not None:
        book.w("vault", f"{legacy} is no longer read (since 1.7.0); the extension builds the file from the spec now, "
                        "or pass a file as --regulation FILE")
    if getattr(args, "regulation", None):
        f = Path(args.regulation)
        if not f.is_file():
            raise FileNotFoundError(f"--regulation {f}: file not found")
        if not protect:
            book.w("vault", f"{f} is ignored: with the vault OFF nothing would put the game's regulation.bin back")
            return None, "none"
        return f, "file"
    if not protect:
        book.i(EXT_TAG, "vault OFF: the extension is not run (it changes the game's files; only the vault can put them back)")
        return None, "none"
    if vault.read_session() is not None:
        book.d(EXT_TAG, "the vault owes a restore from an earlier session: not building; the session will say what to do")
        return None, "none"
    prep = prepare_regulation(args, game_dir / "regulation.bin", allow_secured=True, vault_dir=vault.root)
    return prep.path, prep.mode


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
    protect = getattr(args, "protect", True)
    try:
        world, mode = _regulation(args, vault, game_dir, protect)
    except GateFailed as exc:
        book.e("run", str(exc))
        book.e("run", "the game was not started and nothing was swapped; the game's files are as they were")
        return 1
    except (ExtensionError, FileNotFoundError) as exc:
        book.e("run", str(exc))
        return 1
    rows = [("vault", str(vault_path)), ("save", str(live)), ("game", str(game_dir)),
            ("mode", "vault ON (backup before, restore after)" if protect else "vault OFF (no backup, no restore)")]
    if world is not None and protect:
        what = {"secured": "secured copy, not rebuilt", "last": "latest build, unchanged, not rebuilt",
                "built": "new build, gate passed"}.get(mode, "your file")
        rows.append(("regulation", f"{world} ({what}) replaces the game's regulation.bin for this session"))
    begin(args, "run", rows)

    def extra() -> list[str]:
        out = []
        profile, reason = load_profile(Path(args.offsets), sha)
        if profile is None:
            out.append(f"no usable profile for this eldenring.exe ({reason}); `read` and `write` could not attach")
        root, gd = vault_path.resolve(), game_dir.resolve()
        if root == gd or gd in root.parents:
            out.append("the vault must not be inside the game folder")
        return out

    children: list = []
    steps = []       # the memory steps that have something to give: the regulation.bin is the extension's, the design has it
    if protect and world is not None and mode in TEXT_MODES:
        if design_has_text(args, vault_path):
            steps.append(start_text)
        if design_has_flame(args, vault_path):
            steps.append(start_flame)

    def on_running(pid):
        for start in steps:
            children.append(start(args, vault_path))

    hooks = Hooks(
        find_game_pid=lambda: find_pid(GAME_EXE),
        process_started=process_started,
        anticheat_running=lambda: bool(anticheat_processes(list_process_names())),
        launch=lambda: launcher.launch(game_dir),
        exe_sha256=sha, game_dir=game_dir, game_guard=GameFolderGuard(game_dir), extra_preflight=extra,
        regulation_world=world,
        launch_timeout=args.launch_timeout,
        on_running=on_running,
    )
    if any(n.lower() == STEAM_EXE for n in list_process_names()):
        book.w("steam", STEAM_CLOUD_NOTE)
    session = Session(vault, live, hooks, archive_contaminated=not args.no_archive_contaminated,
                      log=session_log(), protect=protect)
    tail = None
    if book.path is not None:       # what the other processes do: the text and flame steps (all lines with -v, their progress without)
        show = ui.raw_line if getattr(args, "verbose", False) else ui.child_line
        tail = Tail(book.path, lambda line: book.locked(show, line), book.pid)
        tail.start()
    try:
        rc = session.run()
    finally:
        for child in children:      # the steps end by themselves; do not leave one behind
            if child.poll() is None:
                child.terminate()
        if tail is not None:
            tail.stop()
    if State.RESTORING in session.history:   # a session really ran; never prune a vault that still owes a restore
        auto_prune(vault, args.keep)
        if mode in ("built", "last"):
            book.i(EXT_TAG, "this regulation.bin is a build that is not secured yet. If it worked in the game, keep it for next time: "
                                "eldendisk extension innovate-items spells --secure   (game closed)")
    return rc

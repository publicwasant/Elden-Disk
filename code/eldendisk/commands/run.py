"""`run`: the portal. Vault backup -> the regulation.bin of creative.json swapped in -> offline launch -> once a character is in the
world: `innovate-spells apply`, `resurrect` (creative.json's list) and `scripts start *`, each a process of its own -> the game closes ->
restore. It never reads game memory itself."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

import eldendisk
from ..console import require_windows_x64
from .. import creative, ui
from ..logbook import CREATIVE_TAG, Tail, book
from ..game.processes import GAME_EXE, anticheat_processes, find_pid, list_process_names, process_started, remember_sha256, sha256_file
from ..game.profile import load_profile
from ..host import launcher
from ..host.host import Hooks, Session, State
from ..paths import HERE, describe_resource, get_resource_path
from ..vault import GameFolderGuard, SaveVault, VaultError, resolve_vault
from .common import begin, live_dir, log_config, session_log
from .innovate import creative_folder, prepare_regulation, say_error, spec_file
from .scripts import WORLD_READY, has_scripts
from ..creative.innovate_spells.service import CreativeError, GateFailed


STEAM_EXE = "steam.exe"
STEAM_CLOUD_NOTE = ("Steam is running: Steam Cloud may sync the save when the game exits (not verified). "
                    "Use Steam offline mode, or turn Steam Cloud off for Elden Ring")


STEPS_POLL = 0.25      # seconds between two looks at the memory steps (apply, resurrect), while the scripts wait for them

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


TEXT_MODES = ("secured", "last", "built")      # the regulation.bin is creative.json's: the spells' texts and colours belong to it


def creative_has_text(args, vault_path: Path) -> bool:
    """Is there any text in creative.json for the spells the build holds? (Nothing to start otherwise.)"""
    try:
        ci = creative.open_spells(creative_folder(args, vault_path), spec_file(args))
        sel, _note = ci.selection()
        return any(any(t.values()) for t in ci.texts(sel).values())
    except CreativeError:
        return False


def creative_has_flame(args, vault_path: Path) -> bool:
    """Does a spell of creative.json name a flame_color, or a colour for its positive_curse_energy_eyes? (Nothing to start otherwise.)"""
    try:
        ci = creative.open_spells(creative_folder(args, vault_path), spec_file(args))
        sel, _note = ci.selection()
        return (ci.flame_color(sel)[0] is not None or ci.eyes_color(sel)[0] is not None
                or bool(ci.colours(sel)[0]))
    except CreativeError:
        return False


def apply_command(args, vault_path: Path) -> tuple[list[str], str | None]:
    """The command that gives the running game the spells' texts and colours, and the folder to run it in: `eldendisk innovate-spells
    apply --when-loaded`. `run` itself never touches the game's memory; this is a separate process, as if you typed it in another
    terminal."""
    return child_command(args, vault_path, ["innovate-spells", "apply", "--when-loaded"])


def child_command(args, vault_path: Path, words: list[str]) -> tuple[list[str], str | None]:
    """`eldendisk <words>` as a process of its own, with the vault, offsets.json and creative.json `run` was given (only those the user
    chose), and the folder to run it in."""
    frozen = getattr(sys, "frozen", False)
    cmd = [sys.executable] if frozen else [sys.executable, "-m", "eldendisk"]
    cmd += list(words)
    if getattr(args, "vault", None):                 # the vault `run` was told is remembered, so the step finds the same one without being told
        cmd += ["--vault", str(vault_path)]
    if str(args.offsets) != str(get_resource_path("offsets.json", default_dir=HERE)):      # only an offsets.json the user chose
        cmd += ["--offsets", str(args.offsets)]
    for flag, value in (("--spec", getattr(args, "spec", None)), ("--creative-dir", getattr(args, "creative_dir", None))):
        if value:
            cmd += [flag, str(value)]
    return cmd, None if frozen else str(Path(eldendisk.__file__).resolve().parent.parent)


def _child_env() -> dict:
    """The environment of a step `run` starts: its own command line is not logged again (`creative: starting: ...` says it)."""
    from ..logsetup import STARTED_BY
    return {**os.environ, STARTED_BY: "run"}


def _spawn(args, cmd, cwd, spawn, env=None):
    book.d(CREATIVE_TAG, "starting: " + " ".join(["eldendisk"] + cmd[1 if getattr(sys, "frozen", False) else 3:]))
    quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL} if getattr(args, "verbose", False) else {}   # -v shows its log lines
    return spawn(cmd, cwd=cwd, creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0), env=env or _child_env(), **quiet)


def start_apply(args, vault_path: Path, spawn=subprocess.Popen):
    """Start `innovate-spells apply --when-loaded` (the spells' texts, then their colours) in the background. Its lines appear in this
    console and in the log; if it fails the game goes on."""
    cmd, cwd = apply_command(args, vault_path)
    return _spawn(args, cmd, cwd, spawn)


def creative_has_enemies(args, vault_path: Path) -> bool:
    """Does creative.json name great enemies to bring back (`resurrect.great_enemies.activate`, 1.8.0)?"""
    import json
    from ..creative.resurrect.great_enemies.table import TableError, creative_list
    try:
        return bool(creative_list(json.loads(Path(spec_file(args)).read_text(encoding="utf-8"))))
    except (OSError, ValueError, TableError):
        return False


def start_enemies(args, vault_path: Path, spawn=subprocess.Popen):
    """Start `resurrect --when-loaded` in the background: the great enemies of creative.json, once a character is in the world."""
    cmd, cwd = child_command(args, vault_path, ["resurrect", "--when-loaded"])
    return _spawn(args, cmd, cwd, spawn)


def start_scripts(args, vault_path: Path, spawn=subprocess.Popen, after_steps: bool = False):
    """Start the scripts' host (`scripts start * --when-loaded`) in the background: its lines appear in this console and in the log;
    a script that fails, or the host itself, never stops the game or the restore."""
    cmd, cwd = child_command(args, vault_path, ["scripts", "start", "*", "--when-loaded"])
    env = _child_env()
    if after_steps:                    # the memory steps waited for a stable world: the scripts look once and start
        env[WORLD_READY] = "1"
    return _spawn(args, cmd, cwd, spawn, env)


def _regulation(args, vault: SaveVault, game_dir: Path, protect: bool) -> tuple:
    """-> (the regulation.bin to swap in for this session or None, mode). mode: "none" | "file" (--regulation) | "secured"
    (the confirmed copy, nothing built) | "last" (the latest build, unchanged since, nothing built) | "built" (a new build the gate
    passed). `--regulation FILE` wins. Otherwise, with the vault ON, `innovate-spells` swaps the secured file, or the latest build, when
    the spells are unchanged and builds (a few seconds) when they are not: the spells the last `innovate-spells build` chose, every spell
    without one. The vault is what makes that safe: it puts the game's file back. With the vault OFF nothing creative runs. A build error or a
    failed gate stops `run` (CreativeError / GateFailed): nothing is swapped, the game is not started.
    The 1.6.4 place `<vault>/regulation/regulation.bin` is not read any more."""
    legacy = vault.legacy_world()
    if legacy is not None:
        book.w("vault", f"{legacy} is no longer read (since 1.7.0); `innovate-spells` builds the file from creative.json now, "
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
        book.i(CREATIVE_TAG, "vault OFF: nothing creative runs (it changes the game; only the vault can put it back)")
        return None, "none"
    if vault.read_session() is not None:
        book.d(CREATIVE_TAG, "the vault owes a restore from an earlier session: not building; the session will say what to do")
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
    sha = sha256_file(game_dir / GAME_EXE)          # afresh: the anchor of the session record
    remember_sha256(game_dir / GAME_EXE, sha)       # the steps and the other terminals attach without hashing again
    vault, live = SaveVault(vault_path), live_dir(args.save_dir)

    log_config("offsets", args.offsets)
    protect = getattr(args, "protect", True)
    try:
        world, mode = _regulation(args, vault, game_dir, protect)
    except GateFailed as exc:
        say_error(exc, "run")
        book.e("run", "the game was not started and nothing was swapped; the game's files are as they were")
        return 1
    except (CreativeError, FileNotFoundError) as exc:
        say_error(exc, "run")
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
    steps = []       # the memory steps that have something to give: the regulation.bin is creative.json's, and it has texts or colours
    if protect and world is not None and mode in TEXT_MODES and (creative_has_text(args, vault_path) or creative_has_flame(args, vault_path)):
        steps.append(start_apply)
    if protect and creative_has_enemies(args, vault_path):     # 1.8.0: whatever regulation.bin is swapped (memory only, the session's)
        steps.append(start_enemies)
    scripts = None
    if protect and has_scripts(args):          # the scripts: whatever regulation.bin the session swaps (they write through the session)
        scripts = start_scripts
    elif protect:
        book.d(CREATIVE_TAG, "no scripts (none in creative/scripts/defaults when the exe was built, none in scripts.added): none started")
    ended, starting = threading.Event(), threading.Lock()

    def scripts_after(memory, pid):
        """The scripts start once the memory steps are done: what `run` gives the game is in place, so a script that changes a colour
        finds it painted (started side by side, its first writes were refused: "not painted yet")."""
        while not ended.is_set() and any(c.poll() is None for c in memory):
            ended.wait(STEPS_POLL)
        with starting:
            if not ended.is_set() and find_pid(GAME_EXE) == pid:
                children.append(scripts(args, vault_path, after_steps=True))

    def on_running(pid):
        memory = [start(args, vault_path) for start in steps]
        children.extend(memory)
        if scripts is None:
            return
        if not memory:
            children.append(scripts(args, vault_path))
            return
        book.d(CREATIVE_TAG, "scripts: they start once the memory steps (apply, resurrect) are done")
        threading.Thread(target=scripts_after, args=(memory, pid), name="scripts-after", daemon=True).start()

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
    if book.path is not None:       # what the other processes do: the memory steps and the scripts (all lines with -v, their progress without)
        show = ui.raw_line if getattr(args, "verbose", False) else ui.child_line
        tail = Tail(book.path, lambda line: book.locked(show, line), book.pid)
        tail.start()
    try:
        rc = session.run()
    finally:
        with starting:
            ended.set()             # the scripts are not started after this
        for child in children:      # the steps end by themselves; do not leave one behind
            if child.poll() is None:
                child.terminate()
        if tail is not None:
            tail.stop()
    if State.RESTORING in session.history:   # a session really ran; never prune a vault that still owes a restore
        auto_prune(vault, args.keep)
        if mode in ("built", "last"):
            book.i(CREATIVE_TAG, "this regulation.bin is a build that is not secured yet. If it worked in the game, keep it for next time: "
                                "eldendisk innovate-spells secure   (game closed)")
    return rc

"""`extension external-scripts [--run [--when-loaded]] [--scripts-dir DIR]` (1.7.2): the user's Python scripts next to the game.

Without `--run` it lists the scripts of the folder and how each ended the last time. `--run` is the host of the scripts
(eldendisk/extension/external_scripts/host.py): it attaches to the game `run` started, checks the session as `write` does, and runs every script of the
folder until the game closes. `run` starts it by itself (vault ON) when the folder has a script, with `--when-loaded`: the scripts start
once a character is in the world. By hand (game running, session open) it starts them at once.

The scripts: the default ones, those of code/eldendisk/extension/external_scripts/defaults (the exe carries them: the build embeds
them; a build with --no-embed puts them in `external-scripts\\` next to the exe), and IN ADDITION every `--scripts-dir PATH`: a folder
(its `*.py`) or one `.py` file, anywhere, as many as wanted (for scripts written after the exe was built).

Everything of the scripts is in eldendisk/extension/external_scripts/ (edstdlib, the host, the backend on the game, FakeGame, the
examples, defaults/). The backend opens the write handle only after the session check here, as `write` does."""
from __future__ import annotations

from pathlib import Path

from .. import extension, ui
from ..console import require_windows_x64
from ..extension.external_scripts import EXAMPLES_DIR, FOLDER_NAME, DEFAULTS_DIR, edstdlib as ed
from ..extension.external_scripts import host as shost
from ..extension.external_scripts.backend import open_live
from ..extension.innovate_items.spells.service import ExtensionError
from ..game.attach import EXIT_NO_SESSION, AttachError, Target, locate
from ..game.processes import process_started
from ..game.profile import StateIds, load_state_ids
from ..logbook import book
from ..paths import HERE, get_resource_path, runtime_dirs
from ..vault import VaultError, authorise, resolve_vault
from ..vault import session as vault_session
from .extension import ext_dir, spec_file

TAG = shost.TAG
_LEVELS = {"I": book.i, "OK": book.ok, "W": book.w, "E": book.e, "D": book.d}


def say(level: str, msg: str) -> None:
    """The host's and the scripts' lines, in the log (tag `scripts`) and on the console of `run`."""
    _LEVELS.get(level, book.i)(TAG, msg)


# ---------------------------------------------------------------------------------------------------------------------------- the command
def default_dir() -> Path:
    """The folder of the default scripts: the ones embedded in the exe (or copied next to it by a build with --no-embed), else
    code/eldendisk/extension/external_scripts/defaults in the source tree."""
    external, embedded = runtime_dirs()
    for d in (embedded, external):
        if d is not None and (d / FOLDER_NAME).is_dir():
            return d / FOLDER_NAME
    return DEFAULTS_DIR if external is None else (embedded or external) / FOLDER_NAME


def extra_paths(args) -> list[Path]:
    """`--scripts-dir PATH ...` as given: folders or `.py` files."""
    got = getattr(args, "scripts_dir", None) or []
    return [Path(p) for p in ([got] if isinstance(got, (str, Path)) else got)]


def script_paths(args, warn=None) -> list[Path]:
    """Every script to run: the default ones, then those of each --scripts-dir (a folder: its *.py; a file: itself). The same file
    twice is taken once. `warn(text)`: what is said about a path that is neither."""
    out = list(shost.script_files(default_dir()))
    for p in extra_paths(args):
        if p.is_dir():
            out += shost.script_files(p)
        elif p.is_file() and p.suffix.lower() == ".py":
            out.append(p)
        elif warn is not None:
            warn(f"--scripts-dir {p}: not a folder or a .py file; left out")
    seen, unique = set(), []
    for p in out:
        key = str(p.resolve()).lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def has_scripts(args) -> bool:
    """Is there a script to run? (`run` starts the host only then.)"""
    return bool(script_paths(args))


def status_path(args, vault_dir=None) -> Path:
    return ext_dir(args, vault_dir) / shost.STATUS_FILE


def cmd_scripts_list(args) -> int:
    folder = default_dir()
    ui.result("info", f"external scripts: the default ones ({folder})" + (" and " + ", ".join(str(p) for p in extra_paths(args))
                                                                          if extra_paths(args) else ""))
    try:
        sp = status_path(args)
        last = shost.read_status(sp)
    except ExtensionError:
        sp, last = None, None
    ended = {s.get("name"): s for s in (last or {}).get("scripts", [])}
    rows = []
    for f in script_paths(args, warn=lambda t: book.w(TAG, t)):
        found = shost.load_file(f)
        if found.error and not found.scripts:
            rows.append((f.name, f"cannot be loaded: {found.error}"))
            continue
        for s in found.scripts:
            text = f"{s.name}, every {max(shost.MIN_EVERY, float(s.every)):g} s" + ("" if getattr(s, "enabled", True) else ", off (enabled = False)")
            was = ended.get(s.name)
            if was is not None:
                text += f"; last run: {was.get('state')}" + (f" after {was['loops']} loop(s)" if was.get("loops") else "") \
                        + (f" ({was['error']})" if was.get("error") else "")
            rows.append((f.name, text))
    if not rows:
        rows.append(("", f"no scripts yet: put one in {DEFAULTS_DIR} (copy from {EXAMPLES_DIR}) and build, or give --scripts-dir PATH"))
    ui.fields(rows)
    if last is not None:
        ui.fields([("status", f"{sp} ({last.get('updated', '?')})")])
    return 0


def cmd_scripts_run(args) -> int:
    """The host: every script of the folder until the game closes."""
    require_windows_x64()
    files = script_paths(args, warn=lambda t: book.w(TAG, t))
    if not files:
        book.i(TAG, "no external scripts (none embedded, no --scripts-dir): nothing to run")
        return 0
    try:
        vault_root = resolve_vault(getattr(args, "vault", None))
        record = vault_session.load(vault_root)
    except VaultError as exc:
        book.e(TAG, str(exc))
        return EXIT_NO_SESSION
    when_loaded = bool(getattr(args, "when_loaded", False))
    from .write import ATTACH_WAIT, POLL, _clock, _sleep, _wait_world      # the same waits as the steps `run` starts
    t0 = _clock()
    while True:
        try:
            target: Target = locate(Path(args.offsets))
            break
        except AttachError as exc:
            if not when_loaded or "not running" in str(exc) or _clock() - t0 >= ATTACH_WAIT:
                book.e(TAG, str(exc))
                return exc.code
            _sleep(POLL)
    problems = authorise(record, game_pid=target.pid, game_started=target.started, exe_sha256=target.sha256,
                         started_of=process_started)
    if problems:
        book.e(TAG, "refused, no script was started:")
        for p in problems:
            book.e(TAG, f"  {p}")
        return EXIT_NO_SESSION
    try:
        state_ids = load_state_ids(Path(getattr(args, "state_ids", None) or get_resource_path("chr_state_ids.json", default_dir=HERE)))
    except ValueError as exc:
        book.w(TAG, f"{exc}; buffs and animations are read without names")
        state_ids = StateIds({}, {})
    try:
        resolved = extension.open_spells(ext_dir(args, vault_root), spec_file(args)).resolved_path
        status = ext_dir(args, vault_root) / shost.STATUS_FILE
    except ExtensionError as exc:
        book.w(TAG, f"the extension's files cannot be found ({exc}); game.spells is empty")
        resolved, status = None, None
    backend = open_live(target, state_ids, vault_root, resolved, say)      # the write handle: only now, after the session check
    try:
        if when_loaded and not _wait_world(backend.mem, target, "external scripts"):
            book.i(TAG, "the game closed before a character was in the world; no script was started")
            return 0
        return run_scripts(files, backend, status)
    finally:
        backend.close()


def run_scripts(files, backend, status: Path | None, until=None) -> int:
    """Load `files`, run their scripts on `backend` until the game closes (or `until()`), and end them. -> exit code."""
    shost.install()
    shost.set_log(say)
    old = ed._use(backend)
    try:
        sup = shost.Supervisor([shost.load_file(f) for f in files], backend.alive, status)
        if not sup.runners:
            book.w(TAG, "no script can run")
            sup.save_status()
            return 1
        sup.start()
        sup.watch(until)
        return 0
    finally:
        ed._use(old)


def cmd_external_scripts(args) -> int:
    if getattr(args, "run", False):
        return cmd_scripts_run(args)
    return cmd_scripts_list(args)

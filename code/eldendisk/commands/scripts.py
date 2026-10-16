"""`scripts` (1.7.2 `external-scripts`; 1.8.0 part 2): your Python scripts, running next to the game while it runs.

    scripts [* | all]                                  every script (the defaults and the added ones) with its state
    scripts start [NAME[:ID[:PROCESS_ID]] | * | all] [--when-loaded]
    scripts restart | stop | status [NAME[:ID[:PROCESS_ID]] | * | all]
    scripts add | remove | change PATH                 the list `scripts.added` of creative.json (a .py file or a folder)

The host (eldendisk/creative/scripts/host.py) is ONE process that holds every script of the session, each in a thread of its own. When no
host runs, `scripts start` becomes it: it attaches to the game `run` started, checks the session as `write` does, and runs the scripts
until the game closes (`run` starts it by itself, vault ON, with `--when-loaded`: the scripts start once a character is in the world).
When a host runs, `start`, `restart` and `stop` from another terminal leave it a request file in `<vault>\\creative\\scripts.requests\\`;
it does what each asks within a second and answers in its status file (`scripts.status.json`), which `scripts`, `scripts status` and
the document's `creative.scripts` read. No port is opened. `stop *` ends the host itself (a script stuck in its own loop ends only so).

The scripts: the default ones (code/eldendisk/creative/scripts/defaults: the exe carries them) and those of `scripts.added` in
creative.json (files or folders anywhere, kept there by `scripts add / remove / change`).

Everything of the scripts is in eldendisk/creative/scripts/ (edstdlib, the host, the backend on the game, FakeGame, the defaults/;
example scripts are in code/tests/external_scripts). The backend opens the write handle only after the session check here, as `write`
does."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .. import creative, ui
from ..console import require_windows_x64
from ..creative.scripts import FOLDER_NAME, DEFAULTS_DIR, edstdlib as ed
from ..creative.scripts import host as shost
from ..creative.scripts.backend import open_live
from ..creative.innovate_spells.service import CreativeError
from ..game.attach import EXIT_ERROR, EXIT_NO_SESSION, AttachError, Target, locate
from ..game.processes import process_alive, process_started
from ..game.profile import StateIds, load_state_ids
from ..logbook import book
from ..paths import describe_resource, runtime_dirs
from ..reader import view
from ..vault import VaultError, authorise, resolve_vault
from ..vault import session as vault_session
from .innovate import creative_folder, spec_file

TAG = shost.TAG
WORLD_READY = "ELDENDISK_WORLD_READY"   # set by `run` when it starts the scripts after the memory steps: no second wait of 5 s
ANSWER_WAIT = 15.0       # seconds to wait for the host to answer a request
_LEVELS = {"I": book.i, "OK": book.ok, "W": book.w, "E": book.e, "D": book.d}
_sleep, _clock = time.sleep, time.monotonic        # tests replace these


def say(level: str, msg: str) -> None:
    """The host's and the scripts' lines, in the log (tag `scripts`) and on the console of `run`."""
    _LEVELS.get(level, book.i)(TAG, msg)


# ---------------------------------------------------------------------------------------------------------------------------- the files
def default_dir() -> Path:
    """The folder of the default scripts: the ones embedded in the exe (or copied next to it by a build with --no-embed), else
    code/eldendisk/creative/scripts/defaults in the source tree."""
    external, embedded = runtime_dirs()
    for d in (embedded, external):
        if d is not None and (d / FOLDER_NAME).is_dir():
            return d / FOLDER_NAME
    return DEFAULTS_DIR if external is None else (embedded or external) / FOLDER_NAME


def _read_creative(path: Path) -> dict:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise CreativeError(f"{path}: cannot be read ({exc})")
    if not isinstance(doc, dict):
        raise CreativeError(f"{path}: must contain a JSON object")
    return doc


def added_list(doc: dict) -> list[str]:
    """`scripts.added` of creative.json: the paths as written. CreativeError when it is not a list of paths."""
    sec = doc.get("scripts")
    if sec is None:
        return []
    if not isinstance(sec, dict):
        raise CreativeError("creative.json: scripts must be an object ({\"added\": [paths]})")
    got = sec.get("added")
    if got is None:
        return []
    if not isinstance(got, list) or not all(isinstance(x, str) and x.strip() for x in got):
        raise CreativeError("creative.json: scripts.added must be a list of paths (a .py file or a folder each)")
    return list(got)


def added_paths(args, warn=None) -> list[Path]:
    """The paths of `scripts.added` in creative.json; a file that cannot be read is said through `warn` and gives none."""
    try:
        return [Path(p) for p in added_list(_read_creative(spec_file(args)))]
    except CreativeError as exc:
        if warn is not None:
            warn(str(exc))
        return []


def script_files(args, warn=None) -> list[tuple[Path, bool]]:
    """Every script file to run, with True for an added one: the default ones, then each of `scripts.added` (a folder: its *.py; a
    file: itself). The same file twice is taken once. `warn(text)`: what is said about a path that is neither."""
    out = [(p, False) for p in shost.script_files(default_dir())]
    for p in added_paths(args, warn):
        if p.is_dir():
            out += [(q, True) for q in shost.script_files(p)]
        elif p.is_file() and p.suffix.lower() == ".py":
            out.append((p, True))
        elif warn is not None:
            warn(f"scripts.added: {p}: not a folder or a .py file; left out")
    seen, unique = set(), []
    for p, added in out:
        key = str(p.resolve()).lower()
        if key not in seen:
            seen.add(key)
            unique.append((p, added))
    return unique


def has_scripts(args) -> bool:
    """Is there a script to run? (`run` starts the host only then.)"""
    return bool(script_files(args))


def status_path(args, vault_dir=None) -> Path:
    return creative_folder(args, vault_dir) / shost.STATUS_FILE


def _status(args) -> tuple[Path | None, dict | None, bool]:
    """(the creative folder, the host's last status, does that host run now)."""
    try:
        folder = creative_folder(args)
    except CreativeError:
        return None, None, False
    st = shost.read_status(folder / shost.STATUS_FILE)
    return folder, st, shost.host_running(st, process_alive)


# ---------------------------------------------------------------------------------------------------------------------------- showing
def _show(args, path: str, value) -> None:
    if getattr(args, "json", False):
        ui.out(view.as_json([(path, value)]))
    else:
        ui.rows(view.rows([(path, value)], flat=getattr(args, "flat", False)))


def _listed(args) -> dict:
    """What the files hold, as the status file says a script (for the scripts no host runs now)."""
    found = [shost.load_file(f, added) for f, added in script_files(args, warn=lambda t: book.w(TAG, t))]
    sup = shost.Supervisor(found, lambda: False)
    return {"pid": None, "state": "stopped", "scripts": [e.view() for e in sup.entries]}


def _block(args, target: str = "*") -> tuple[dict | None, bool]:
    """The `creative.scripts` block (from the running host, else from the files with the states of the last host), only the scripts
    `target` names. -> (block, does a host run). ValueError for a target that names no script."""
    _folder, st, running = _status(args)
    if not running:
        listed = _listed(args)
        last = {(s.get("path") or "").lower(): s for s in (st or {}).get("scripts", []) if isinstance(s, dict)}
        for s in listed["scripts"]:
            was = last.get((s.get("path") or "").lower())
            if was is not None and was.get("name") == s.get("name"):
                s.update({k: was[k] for k in ("state", "loops", "slow", "last_error", "started") if k in was})
            elif s["state"] == "loaded":
                s["state"] = "stopped"
        st = listed
    if target not in ("", "*", "all"):
        st = {**st, "scripts": shost.match(st.get("scripts", []), target, st.get("pid") if running else None)}
    return shost.block_of(st, running), running


def cmd_scripts_list(args, target: str = "*") -> int:
    """`scripts` and `scripts status`: every script (or those `target` names) with its state."""
    block, running = _block(args, target)
    _show(args, "creative.scripts", block)
    if getattr(args, "json", False):
        return 0
    if not running:
        ui.result("info", "no host runs: `scripts start` starts it (the game running, inside the session `run` started)")
    if not (block["defaults"] or block["added"]):
        ui.result("info", f"no scripts yet: put one in {DEFAULTS_DIR} and build, or `scripts add PATH`")
    return 0


# ---------------------------------------------------------------------------------------------------------------------------- the host
def cmd_scripts_start(args, target: str = "*") -> int:
    """`scripts start`: a request to the running host, or, when none runs, this process becomes the host."""
    folder, _st, running = _status(args)
    if running:
        return _ask(folder, "start", target)
    return cmd_scripts_host(args, None if target in ("", "*", "all") else [target])


def cmd_scripts_host(args, only: list[str] | None = None) -> int:
    """The host: the scripts of the session until the game closes (or `scripts stop *`)."""
    require_windows_x64()
    files = script_files(args, warn=lambda t: book.w(TAG, t))
    if not files:
        book.i(TAG, "no scripts (none embedded, none in scripts.added of creative.json): nothing to run")
        return 0
    try:
        vault_root = resolve_vault(getattr(args, "vault", None))
        record = vault_session.load(vault_root)
    except VaultError as exc:
        book.e(TAG, str(exc))
        return EXIT_NO_SESSION
    when_loaded = bool(getattr(args, "when_loaded", False))
    from .write import ATTACH_WAIT, POLL, _wait_world      # the same waits as the steps `run` starts
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
    from .read import names_file
    try:
        state_ids = load_state_ids(names_file(args))
    except ValueError as exc:
        book.w(TAG, f"{exc}; animations are read without names")
        state_ids = StateIds({})
    folder = creative_folder(args, vault_root)
    try:
        resolved = creative.open_spells(folder, spec_file(args)).resolved_path
    except CreativeError as exc:
        book.w(TAG, f"the spells' files cannot be found ({exc}); creative.innovate_spells is empty")
        resolved = None
    status = folder / shost.STATUS_FILE
    backend = open_live(target, state_ids, vault_root, resolved, say, status_path=status)   # the write handle: only now, after the check
    try:
        ready = os.environ.get(WORLD_READY) == "1"        # `run` started us after the memory steps: the world was checked
        if when_loaded and not _wait_world(backend.mem, target, "scripts", tag=TAG, stable=0.0 if ready else None):
            book.i(TAG, "the game closed before a character was in the world; no script was started")
            return 0
        return run_scripts(files, backend, status, only=only, control=folder)
    finally:
        backend.close()


def run_scripts(files, backend, status: Path | None, until=None, only=None, control: Path | None = None) -> int:
    """Load `files` ((path, added) or paths), run their scripts on `backend` until the game closes (or `until()`, or `scripts stop *`
    when `control` is the folder of the requests), and end them. -> exit code."""
    shost.install()
    shost.set_log(say)
    old = ed._use(backend)
    try:
        found = [shost.load_file(*f) if isinstance(f, tuple) else shost.load_file(f) for f in files]
        if control is not None:
            for q in shost.take_requests(control):       # requests left for a host that is gone: not for this one
                book.d(TAG, f"an old request was dropped: {q.get('action')} {q.get('target') or q.get('path') or ''}")
        sup = shost.Supervisor(found, backend.alive, status, only=only, control=control)
        if not sup.runners and control is None:
            book.w(TAG, "no script can run")
            sup.save_status()
            return 1
        sup.start()
        sup.watch(until)
        return 0
    finally:
        ed._use(old)


def _ask(folder: Path | None, action: str, target: str = "*", path: str | None = None) -> int:
    """Leave a request for the running host and say its answer. -> exit code."""
    if folder is None:
        book.e(TAG, "the vault cannot be found: no host to ask")
        return EXIT_ERROR
    sp = folder / shost.STATUS_FILE
    rid = shost.send_request(folder, action, target, path)
    t0 = _clock()
    while _clock() - t0 < ANSWER_WAIT:
        st = shost.read_status(sp)
        reply = next((r for r in (st or {}).get("replies", []) if r.get("id") == rid), None)
        if reply is not None:
            for line in reply.get("lines", []):
                (book.ok if reply.get("ok") else book.e)(TAG, line)
            return 0 if reply.get("ok") else EXIT_ERROR
        if not shost.host_running(st, process_alive):
            book.e(TAG, "the host has ended; nothing was done")
            return EXIT_ERROR
        _sleep(0.2)
    book.e(TAG, f"the host (process {(shost.read_status(sp) or {}).get('pid')}) did not answer within {ANSWER_WAIT:g} s; the request "
                "stays and is done when it looks again")
    return EXIT_ERROR


def _when_host(action: str):
    def go(args, target: str = "*") -> int:
        folder, _st, running = _status(args)
        if not running:
            book.i(TAG, f"no host runs: nothing to {action}")
            return 0 if action == "stop" else EXIT_ERROR
        return _ask(folder, action, target)
    return go


cmd_scripts_stop = _when_host("stop")
cmd_scripts_restart = _when_host("restart")


# ---------------------------------------------------------------------------------------------------------------------------- the list
def editable_creative(args) -> Path:
    """The creative.json `scripts add / remove / change` edit: `--spec FILE`, else the one next to the exe (made from the copy in the
    exe the first time), else code/creative.json in the source tree."""
    path = spec_file(args)
    if describe_resource(path) != "embedded":
        return Path(path)
    external, _embedded = runtime_dirs()
    out = Path(external) / Path(path).name
    if not out.exists():
        out.write_bytes(Path(path).read_bytes())
        book.i(TAG, f"{out}: made from the copy in the exe (it wins over that copy from now on)")
    return out


def _save_creative(path: Path, doc: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _check_loads(p: Path) -> tuple[list[str], list[str]]:
    """The scripts in a file or a folder, and the problems of the files that do not load."""
    files = shost.script_files(p) if p.is_dir() else [p]
    names, bad = [], []
    for f in files:
        got = shost.load_file(f, True)
        names += [s.name for s in got.scripts]
        if got.error:
            bad.append(f"{f.name}: {got.error}")
    return names, bad


def _same_entry(a: str, b: Path) -> bool:
    try:
        return Path(a).resolve() == b.resolve()
    except OSError:
        return a.lower() == str(b).lower()


def _the_list(args):
    """(the creative.json to edit, its document, its scripts.added) or raises CreativeError."""
    file = editable_creative(args)
    doc = _read_creative(file)
    return file, doc, added_list(doc)


def _entries(have: list[str], raw: str) -> list[str]:
    """The entries of scripts.added `raw` names: the same path, else the same file or folder name."""
    p = Path(raw).expanduser()
    return [h for h in have if _same_entry(h, p.resolve())] or [h for h in have if Path(h).name.lower() == p.name.lower()]


def _set_list(doc: dict, have: list[str]) -> None:
    if not isinstance(doc.get("scripts"), dict):
        doc["scripts"] = {}
    doc["scripts"]["added"] = have


def cmd_scripts_add(args, paths: list[str]) -> int:
    if not paths:
        book.e(TAG, "give the path of a .py file or of a folder: scripts add PATH")
        return EXIT_ERROR
    file, doc, have = _the_list(args)
    new = []
    for raw in paths:
        p = Path(raw).expanduser().resolve()
        if not (p.is_dir() or (p.is_file() and p.suffix.lower() == ".py")):
            book.e(TAG, f"{raw}: not a .py file or a folder; nothing was added")
            return EXIT_ERROR
        names, bad = _check_loads(p)
        if bad or not names:
            for b in bad:
                book.e(TAG, b)
            book.e(TAG, f"{raw}: " + ("does not load" if bad else "no script in it (class MyScript(Interface): ... def loop(self): ...)")
                   + "; nothing was added")
            return EXIT_ERROR
        if any(_same_entry(h, p) for h in have + new):
            book.i(TAG, f"{p}: in scripts.added already")
            continue
        new.append(str(p))
        book.ok(TAG, f"{p} added to scripts.added ({', '.join(names)})")
    if not new:
        return 0
    _set_list(doc, have + new)
    _save_creative(file, doc)
    book.i(TAG, f"{file}: `run` starts them with the defaults")
    folder, _st, running = _status(args)
    code = 0
    if running:
        for p in new:
            code = _ask(folder, "load", path=p) or code
    return code


def cmd_scripts_remove(args, paths: list[str]) -> int:
    if not paths:
        book.e(TAG, "give the path to take out: scripts remove PATH")
        return EXIT_ERROR
    file, doc, have = _the_list(args)
    gone = []
    for raw in paths:
        hits = _entries(have, raw)
        if len(hits) != 1:
            book.e(TAG, f"{raw}: " + ("not in scripts.added" if not hits else f"fits several: {', '.join(hits)}")
                   + f" (it has: {', '.join(have) or 'none'})")
            return EXIT_ERROR
        gone.append(hits[0])
    folder, _st, running = _status(args)
    for h in gone:
        if running:
            _ask(folder, "unload", path=h)
        have.remove(h)
        book.ok(TAG, f"{h} taken out of scripts.added")
    _set_list(doc, have)
    _save_creative(file, doc)
    return 0


def cmd_scripts_change(args, paths: list[str]) -> int:
    """`scripts change NEW` (the entry with the same file or folder name) or `scripts change OLD NEW`: point the entry at another
    file; a running host loads it again."""
    if len(paths) not in (1, 2):
        book.e(TAG, "give the new path (scripts change PATH), or the old and the new one (scripts change OLD NEW)")
        return EXIT_ERROR
    file, doc, have = _the_list(args)
    new = Path(paths[-1]).expanduser().resolve()
    hits = _entries(have, paths[0])
    if len(hits) != 1:
        book.e(TAG, f"{paths[0]}: " + ("no entry of scripts.added has that name" if not hits else f"fits several: {', '.join(hits)}")
               + f" (it has: {', '.join(have) or 'none'}); `scripts add PATH` adds one")
        return EXIT_ERROR
    if not (new.is_dir() or (new.is_file() and new.suffix.lower() == ".py")):
        book.e(TAG, f"{new}: not a .py file or a folder; nothing was changed")
        return EXIT_ERROR
    names, bad = _check_loads(new)
    if bad or not names:
        for b in bad:
            book.e(TAG, b)
        book.e(TAG, f"{new}: " + ("does not load" if bad else "no script in it") + "; nothing was changed")
        return EXIT_ERROR
    have[have.index(hits[0])] = str(new)
    _set_list(doc, have)
    _save_creative(file, doc)
    book.ok(TAG, f"scripts.added: {hits[0]} -> {new} ({', '.join(names)})")
    folder, _st, running = _status(args)
    if running:
        _ask(folder, "unload", path=hits[0])
        return _ask(folder, "load", path=str(new))
    return 0


# ---------------------------------------------------------------------------------------------------------------------------- the command
FUNCTIONS = ("start", "restart", "stop", "status", "add", "remove", "change")


def cmd_scripts(args) -> int:
    words = list(getattr(args, "words", None) or [])
    fn = words.pop(0) if words and words[0] in FUNCTIONS else None
    try:
        if fn in ("add", "remove", "change"):
            return {"add": cmd_scripts_add, "remove": cmd_scripts_remove, "change": cmd_scripts_change}[fn](args, words)
        if len(words) > 1:
            book.e(TAG, f"one script at a time (NAME, NAME:ID or NAME:ID:PROCESS_ID), or * / all: {' '.join(words)}")
            return EXIT_ERROR
        target = words[0] if words else "*"
        if fn is None and target not in ("*", "all"):
            book.e(TAG, f"unknown function {target!r}: scripts [* | all], or scripts {' | '.join(FUNCTIONS)} ...")
            return EXIT_ERROR
        shost.parse_target(target)            # a wrong address is told before anything
        if fn is None or fn == "status":
            return cmd_scripts_list(args, target)
        return {"start": cmd_scripts_start, "restart": cmd_scripts_restart, "stop": cmd_scripts_stop}[fn](args, target)
    except (ValueError, CreativeError) as exc:
        book.e(TAG, str(exc))
        return EXIT_ERROR

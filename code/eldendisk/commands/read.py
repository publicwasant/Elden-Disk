"""`read` and the Data commands (`export`, `check`, `probe`, `reset`): the game's values. Read-only; they never open a write handle.

    read [* | all]                     the whole document once (`--tree`, the default; `--flat`; `--json`)
    read NAME | ID | PATH ...          a part of it: `hp`, `attrs.*`, `character.runes`, `creative.resurrect.great_enemies`,
                                       `params.effects.1621000`, and any row of the six tables: `params.Magic.6230`, `params.Magic.6230.mp*`
    read ... --live                    the same, kept current (at --hz)
    read monitor | monitor-buffs | monitor-animations [--mapped | --unmapped]
                                       the monitors: one row per id that appears; `--unmapped` (the default) shows only the ids names.json
                                       does not name yet, `--mapped` only those it names
    export [--live]                    the whole document to <TOOLS-DIR>\\output\\disk.json (again each time it changes with --live)
    check [FILE]                       a regulation.bin (the game folder's by default) against the game, row by row
    probe                              where the param files of the other tables are in memory
    reset [* | all | runes | buffs | animations | monitor]
                                       the read baselines start again from now: `runes.delta` = 0, the monitors' history cleared

One attach and one loop serve every mode (spec 1.6.2 section 5)."""
from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path

from .. import ui
from ..console import require_windows_x64
from ..game.attach import EXIT_ERROR, EXIT_EAC, AttachError, Target, eac_loaded, locate, open_read
from ..game.processes import is_window_active, process_started
from ..game.paramtables import Tables, parse_ref, pick
from . import paramcheck
from ..game.params import ParamError, ParamNameError, ParamStore
from ..game.invprobe import as_json as inventory_json, lines as inventory_lines, probe_inventory
from ..game.probe import as_json as probe_json, lines as probe_lines, probe, walk_lines, walk_report
from ..game.profile import load_state_ids
from ..game.values import UnknownName, normalize
from ..logbook import book
from ..paths import describe_resource, get_resource_path
from ..reader import baselines, view
from ..reader.animations import AnimationsMonitor
from ..reader.buffs import BuffsMonitor
from ..reader.export import PARAMS_NAME, ExportWriter, JsonLogger, params_chunks
from ..reader.sampler import Sampler
from ..vault import VaultError, authorise, resolve_vault
from ..vault import session as vault_session
from .common import begin, log_config

RESCAN_S = 2.0       # how often EAC and the session record are re-checked
EXPORT_NAME = "disk.json"
MONITORS = {"monitor": ("buffs", "animations"), "monitor-buffs": ("buffs",), "monitor-animations": ("animations",)}


def names_file(args) -> Path:
    """names.json: `--names FILE`, else the one next to the exe, else the one in the exe / the reader's package."""
    given = getattr(args, "state_ids", None)
    if given:
        return Path(given)
    from .. import reader
    return get_resource_path("names.json", default_dir=Path(reader.__file__).resolve().parent)


def _wait_for_game(offsets: Path, timeout: float | None = None) -> Target:
    """Wait (saying so once) until eldenring.exe runs, then attach; `timeout` None = wait for ever. Other errors end it."""
    deadline = None if timeout is None else time.monotonic() + timeout
    warned = False
    while True:
        try:
            return locate(offsets)
        except AttachError as exc:
            if "not running" not in str(exc) or (deadline is not None and time.monotonic() >= deadline):
                raise
            if not warned:
                book.i("read", "waiting for eldenring.exe (start it with `eldendisk run`; Ctrl+C to stop)")
                warned = True
            time.sleep(1.0)


def _in_session(vault: Path, target: Target) -> bool:
    """True while a valid RUNNING session record covers this very game process (labels the export)."""
    try:
        record = vault_session.load(vault)
    except VaultError:
        return False
    return record is not None and not authorise(record, game_pid=target.pid, game_started=target.started,
                                                exe_sha256=target.sha256, started_of=process_started)


def _export_log(message: str) -> None:
    """ExportWriter reports `warning: ...` and `[STATE] detail`; show them as warnings and state changes."""
    if message.startswith("warning:"):
        book.w("export", message[len("warning:"):].strip())
    else:
        book.i("export", "state " + re.sub(r"^\[(\w+)\]\s*", r"\1 ", message).strip())


def _why_unknown(exc: UnknownName, doc: dict, sample, names) -> str:
    """The message for a name that matched nothing; a `params` name with no params to look in says why there are none."""
    wanted = [names] if isinstance(names, str) else names or []
    creative = doc.get("creative") or {}
    if not creative.get("innovate_spells") and any(n.strip().lower().startswith("creative.innovate_spells") for n in wanted):
        return ("no spells are built in this vault yet (spells.resolved.json is written by every build: `run`, or "
                "`innovate-spells build`)")
    if not creative and any(n.strip().lower().startswith("creative") for n in wanted):
        return "the creative block is empty: no build, no scripts' host, and no event_flags block for this game version"
    return str(exc)


def _continuous(args) -> bool:
    return bool(args.live or args.live_buffs or args.live_animations)


def _mode_text(args) -> str:
    if args.live_buffs or args.live_animations:
        return ", ".join(n for n, on in (("buffs", args.live_buffs), ("animations", args.live_animations)) if on) + " (live)"
    if args.export:
        return f"export to {args.out} (live)"
    return f"{view.label(args.query)} (live)"


def read_words(args) -> int:
    """`read [EMPTY | * | all | NAME ...]` and `read monitor | monitor-buffs | monitor-animations`: the words -> what `cmd_read` does."""
    words = [w for w in (getattr(args, "words", None) or []) if w.strip()]
    args.live_buffs = args.live_animations = False
    if words and words[0].lower() in MONITORS:
        if len(words) > 1:
            book.e("read", f"`read {words[0]}` stands alone (--mapped or --unmapped go with it)")
            return EXIT_ERROR
        if args.live or args.json or args.flat:
            book.e("read", "the monitors are live by themselves: --live, --flat and --json do not go with them")
            return EXIT_ERROR
        kinds = MONITORS[words[0].lower()]
        args.live_buffs, args.live_animations = "buffs" in kinds, "animations" in kinds
        if not (args.mapped or args.unmapped):
            args.unmapped = True                 # 1.8.0: the ids names.json does not name yet are what a monitor is for
        return cmd_read(args)
    if args.mapped or args.unmapped:
        book.e("read", "--mapped / --unmapped go with read monitor, monitor-buffs, monitor-animations")
        return EXIT_ERROR
    if any(w in ("*", "all") for w in words) and len(words) > 1:
        book.e("read", "`*` and `all` stand alone: they are the whole document")
        return EXIT_ERROR
    words = [w for w in words if w not in ("*", "all")]
    refs = [w for w in words if _is_table_ref(w)]
    if refs and len(refs) != len(words):
        book.e("read", "the game's tables (params...) are read on their own, from the game: give them without disk names")
        return EXIT_ERROR
    if refs and args.live:
        book.e("read", "the game's tables (params...) are read once: --live does not go with them")
        return EXIT_ERROR
    args.param = refs or None
    args.query = None if refs else (words or None)
    return cmd_read(args)


def _wants_inventory(args) -> bool:
    """Whether this command shows `character.inventory` (1.8.1): the whole document, an export, a name under `character` or a pattern
    that may reach it. Otherwise the inventory and its names (a look of about a second for the text) are not read."""
    if args.export or getattr(args, "live_buffs", False) or getattr(args, "live_animations", False):
        return bool(args.export)
    names = [args.query] if isinstance(args.query, str) else list(args.query or [])
    if not names:
        return True
    for name in names:
        n = name.strip().lower()
        if n.startswith("disk"):
            n = n[4:].lstrip(".")
        if not n or "*" in n or "?" in n:
            return True
        path = normalize(n)
        if path in ("character", "") or path.startswith("character.inventory"):
            return True
    return False


def _is_table_ref(name: str) -> bool:
    """`params.<Table>[.<id or *>[.<field>]]` for a table of the game (1.8.0 part 4: every table, read when named); `params` alone and
    `params.*`: every table of the game with its rows. All read from the game: the tables are not in disk.json. `params.effects`
    (before 1.8.0) too, so that it says where its rows went."""
    parts = name.strip().split(".")
    if parts[0].lower() == "params" and (len(parts) == 1 or (len(parts) == 2 and parts[1] == "*")):
        return True
    if len(parts) < 2 or parts[0].lower() != "params" or parts[1] in ("*", ""):
        return False
    from ..game.paramnames import TABLES
    return parts[1].lower() in TABLES or parts[1].lower() == "effects"


def cmd_export(args) -> int:
    """`export [--disk] [--params] [--live]`: the whole document to <TOOLS-DIR>\\output\\disk.json (`--disk`, the default); every row of
    every table of the game to params.json (`--params`, 1.8.0 part 4)."""
    args.export, args.query, args.param, args.live_buffs, args.live_animations = True, None, None, False, False
    args.disk = bool(getattr(args, "disk", False)) or not getattr(args, "params", False)
    return cmd_read(args)


def cmd_check(args) -> int:
    """`check [FILE]`: a regulation.bin against the running game (the game folder's when no FILE is given)."""
    args.param_check = args.file or ""
    args.query, args.param, args.live_buffs, args.live_animations = None, None, False, False
    return cmd_read(args)


def cmd_probe(args) -> int:
    """`probe`: where the param files of the other tables are in memory."""
    args.probe_params, args.query, args.param, args.live_buffs, args.live_animations = True, None, None, False, False
    return cmd_read(args)


def cmd_reset(args) -> int:
    """`reset [* | all | runes | buffs | animations | monitor]`: the read baselines start again from now. Writes nothing to the game:
    a small file (reader/baselines.py) that every reader of this game looks at."""
    require_windows_x64()
    try:
        names = baselines.names_of([w for w in (getattr(args, "words", None) or []) if w.strip()])
    except ValueError as exc:
        book.e("reset", str(exc))
        return EXIT_ERROR
    try:
        target = locate(Path(args.offsets))
    except AttachError as exc:
        book.e("reset", str(exc))
        return exc.code
    what: dict = {n: None for n in names}
    if "runes" in names:
        mem = open_read(target)
        try:
            sampler = Sampler(mem, target.profile, load_state_ids(names_file(args)), target.base)
            sample = _first_sample(args, mem, sampler)
        finally:
            mem.close()
        if sample is None:
            return EXIT_ERROR
        what["runes"] = sample.runes
    path = baselines.save(target.pid, target.started, what)
    for n in names:
        book.ok("reset", {"runes": f"runes: the baseline is {what['runes']:,} now (delta 0)" if what.get("runes") is not None else "runes",
                          "buffs": "buffs: the monitor's history starts again from now",
                          "animations": "animations: the monitor's history starts again from now"}[n])
    book.d("reset", f"written to {path}; nothing was written to the game")
    return 0


def cmd_read(args) -> int:
    require_windows_x64()
    continuous = _continuous(args)
    timeout = None if continuous else args.timeout
    refs = []
    for text in args.param or []:
        try:
            parts = text.strip().split(".")
            if len(parts) == 1 or (len(parts) == 2 and parts[1] == "*"):
                refs.append((None, None, None))          # `params`: the tables of the game and their rows
                continue
            if len(parts) >= 2 and parts[1].lower() == "effects":
                raise ParamNameError(f"{text}: `params.effects` is gone (1.8.0): its rows are SpEffectParam's, for example "
                                     "params.SpEffectParam.1621000")
            refs.append(parse_ref(text))
        except ParamNameError as exc:      # a wrong name is told before waiting for the game
            book.e("read", str(exc))
            return EXIT_ERROR
    checked = None
    if args.param_check:                       # a file named on the command line is opened before waiting for the game
        checked = _open_check_file(args.param_check)
        if checked is None:
            return EXIT_ERROR
    try:
        state_ids = load_state_ids(names_file(args))     # before waiting for the game: a bad file is told at once
    except ValueError as exc:
        book.e("read", str(exc))
        return EXIT_ERROR
    try:
        target = _wait_for_game(Path(args.offsets), timeout)
    except AttachError as exc:
        book.e("read", str(exc))
        return exc.code
    except KeyboardInterrupt:
        return 130

    if args.param_check == "":                 # no file named: the game's own regulation.bin, the one it loaded (a `run` session swaps the build in)
        checked = _open_check_file(str(target.exe_path.parent / "regulation.bin"), default=True)
        if checked is None:
            return EXIT_ERROR

    log_config("offsets", args.offsets)
    log_config("names", names_file(args))
    vault = Path()
    try:
        vault = resolve_vault(args.vault)
    except VaultError as exc:
        if args.export and getattr(args, "disk", True):   # disk.json is labelled by the session record, so a vault that cannot be found is an error
            book.e("read", str(exc))
            return EXIT_ERROR
        book.w("read", str(exc))
        vault = None
    profile = target.profile
    if continuous:
        begin(args, "read", [("game", f"eldenring.exe, pid {target.pid}"), ("profile", str(profile.label)),
                             ("mode", _mode_text(args))])
    if profile.buffs_note:
        book.w("read", profile.buffs_note)

    mem = open_read(target)
    sampler = Sampler(mem, profile, state_ids, target.base)
    sampler.inventory_wanted = _wants_inventory(args)
    watch = baselines.Watch(target.pid, target.started, since=time.time())
    _take_baselines(watch, sampler, [])          # a runes baseline `reset` set for this game counts at once
    try:
        if args.probe_params:
            if getattr(args, "what", None) == "inventory":
                return _probe_inventory(args, target, mem, sampler)
            return _probe_params(args, target, mem)
        if refs:
            return _read_params(args, target, mem, refs)
        if checked is not None:
            return _param_check(args, target, mem, checked)
        if args.live_buffs or args.live_animations:
            return _monitors(args, target, mem, sampler, vault, watch)
        if args.export and getattr(args, "params", False) and not getattr(args, "disk", True):
            return _export_params(args, target, mem)
        export = _exporter(args, target, vault)
        export.creative_block = _creative_block(args, target, mem, vault, sampler)
        if args.export and not args.live:
            return _export_once(args, target, mem, sampler, export)
        if not args.export and not args.live:
            return _query_once(args, mem, sampler, export)
        return _live(args, target, mem, sampler, export, vault, watch)
    except KeyboardInterrupt:
        book.i("read", "stopped; the game keeps running")
        return 130
    finally:
        mem.close()


def _take_baselines(watch: baselines.Watch | None, sampler: Sampler, monitors) -> None:
    """What `reset` set since the last look: the runes baseline into the sampler, the monitors' history cleared."""
    if watch is None:
        return
    for name, entry in watch.new().items():
        if name == "runes" and entry.get("total") is not None:
            sampler.reset_baseline(int(entry["total"]))
            book.i("read", f"runes: the baseline is {int(entry['total']):,} (reset at {entry.get('at')})")
        for m in monitors:
            if m.name == name:
                m.ledger.forget()
                book.i("read", f"{name}: the history starts again from now (reset at {entry.get('at')})")


def _probe_params(args, target: Target, mem) -> int:
    """`probe`: list the param files reachable from the globals of the known chains, then every slot of `params.repository` with the
    table it was named as (1.8.0 part 4). Reads only."""
    if target.profile.params is None:
        book.e("read", "this exe version has no params block in offsets.json; nothing to probe from")
        return EXIT_ERROR
    result = probe(ParamStore(mem, target.profile, target.base))
    book.d("read", f"probe: {len(result.hits)} param file(s)")
    walk = None
    if target.profile.params.repository is not None:
        walk = walk_report(Tables(mem, target.profile, target.base))
        book.d("read", f"probe: {len(walk['slots'])} slot(s) of params.repository, {len(walk['missing'])} table(s) not found")
    if args.json:
        ui.out(view.as_json([("probe", {**probe_json(result), **({"repository": walk} if walk else {})})]))
    else:
        for line in probe_lines(result) + (walk_lines(walk) if walk else []):
            ui.out(line)
    if not result.hits and not (walk and walk["slots"]):
        book.e("read", "no param file found from the known chains (is a character loaded? try again in the world)")
        return EXIT_ERROR
    return 0


def _probe_inventory(args, target: Target, mem, sampler: Sampler) -> int:
    """`probe inventory` (1.8.1): look for the inventory in PlayerGameData. Reads only."""
    game_data, why = sampler.locate_game_data()
    goods: set[int] = set()
    if game_data is not None:
        try:
            goods = set(Tables(mem, target.profile, target.base).ids("EquipParamGoods"))
        except ParamError as exc:
            book.e("read", f"the goods ids cannot be read: {exc}")
            return EXIT_ERROR
    result = probe_inventory(mem, game_data, goods, why or "", tuple(getattr(args, "find", None) or ()))
    book.d("read", f"probe inventory: {len(result.runs)} list(s), {result.read_bytes / 1048576:.1f} MB read")
    if args.json:
        ui.out(view.as_json([("probe_inventory", inventory_json(result))]))
    else:
        for line in inventory_lines(result):
            ui.out(line)
    if game_data is None:
        book.e("read", "no character in the world: load one and probe again")
        return EXIT_ERROR
    return 0 if result.runs else EXIT_ERROR


def _read_params(args, target: Target, mem, refs) -> int:
    """`read params.<Table>[.<id or *>[.<field>]]`: a table (every row), a row, the fields of every row that match, as a tree
    (`--flat`: one `params.<Table>.<id>.<field>  value` row each). Reads only; the rows are read now, from the game (1.8.0 part 4)."""
    if target.profile.params is None:
        book.e("read", "this exe version has no params block in offsets.json")
        return EXIT_ERROR
    try:
        tables = Tables(mem, target.profile, target.base)
        selection: list[tuple[str, object]] = []
        for table, row_id, pattern in refs:
            if table is None:
                index = tables.index()
                if not index:
                    raise ParamError("no param table found yet (the game is still loading them)")
                path, value = "params", index
            elif row_id is None or row_id == "*":
                path, value = f"params.{table}", {str(rid): row for rid, row in tables.read_table(table, pattern).items()}
            else:
                path, value = f"params.{table}.{row_id}", pick(tables.read_row(table, row_id), pattern)
            if all(path != p for p, _ in selection):
                selection.append((path, value))
            else:    # the same row or table asked twice (two patterns): merge
                dict(selection)[path].update(value)
    except (ParamError, ParamNameError) as exc:
        book.e("read", str(exc))
        return EXIT_ERROR
    if args.json:
        ui.out(view.as_json(selection))
    else:
        ui.rows(view.rows(selection, flat=args.flat))
    return 0


def _open_check_file(path: str, default: bool = False):
    """The rows of the regulation.bin at `path`, or None after telling why not."""
    what = "the game folder's regulation.bin, " if default else ""
    book.i("read", f"opening {what}{path} (a few seconds)")
    try:
        return paramcheck.file_rows(Path(path))
    except paramcheck.CheckFileError as exc:
        book.e("read", str(exc))
        return None


def _param_check(args, target: Target, mem, checked) -> int:
    """`check FILE`: the six tables of the file against the same tables in the game. Reads only; 0 only when all agree."""
    if target.profile.params is None:
        book.e("read", "this exe version has no params block in offsets.json")
        return EXIT_ERROR
    tables = Tables(mem, target.profile, target.base)
    diffs = []
    for table, rows in checked.items():
        try:
            diffs.append(paramcheck.compare(table, rows, tables.all_rows(table)))
        except ParamError as exc:
            bad = paramcheck.TableDiff(table, len(rows), 0)
            bad.error = str(exc)
            diffs.append(bad)
    if args.json:
        ui.out(view.as_json([("", paramcheck.as_json(diffs))]))
    else:
        for line in paramcheck.lines(diffs):
            ui.out(line)
    if all(d.same for d in diffs):
        book.ok("read", "the file and the game agree on every row of the six tables")
        return 0
    book.e("read", "the file and the game differ (a value changed with `write` in this game process shows here too)")
    return EXIT_ERROR


def _exporter(args, target: Target, vault: Path | None) -> ExportWriter:
    """The object that builds the documents (`disk.json`); it writes them only when it has a logger (`export`)."""
    profile = target.profile
    logger = JsonLogger(Path(args.out), target.exe_path.parent, filename=EXPORT_NAME) if args.export else None
    export = ExportWriter(logger, interval=0.0 if not args.live else args.export_interval,
                          timer_interval=0.0 if not args.live else args.timer_interval, verbose=args.live, log=_export_log)
    export.pid, export.sha, export.label = target.pid, target.sha256, profile.label
    export.anti_cheat = "DISABLED_OFFLINE"
    export.buffs_supported = profile.sp_effect is not None
    export.animations_supported = profile.anim is not None
    export.creative = bool(vault) and _in_session(vault, target)
    return export


def _creative_block(args, target: Target, mem, vault: Path | None, sampler: Sampler | None = None, every: float = 1.0):
    """The `creative` block of the document (1.7.2; 1.8.0): the scripts' host, the spells of the last build with what the game holds
    now, the defeated great enemies; read again at most every `every` seconds (a few rows of the game's tables, the event flags of the
    table and three small files). None without a vault."""
    if not vault:
        return None
    from .innovate import creative_folder, spec_file
    from .. import creative
    from ..creative.scripts import host as shost
    from ..creative.scripts.backend import CreativeLive, with_spell_buffs
    from ..creative.innovate_spells.service import CreativeError
    status = None
    try:
        folder = creative_folder(args, vault)
        status = folder / shost.STATUS_FILE
        resolved = creative.open_spells(folder, spec_file(args)).resolved_path
    except CreativeError:
        resolved = None                # no build: the scripts and the great enemies (1.8.0) are still there
    ext = CreativeLive(mem, target, vault, resolved, status_path=status)
    if sampler is not None:            # the buffs of the design's spells are named in character.buffs
        sampler.state_ids = with_spell_buffs(sampler.state_ids, ext.spells())
    last = {"at": -1e9, "block": None}

    def block():
        now = time.monotonic()
        if now - last["at"] >= every:
            last["at"], last["block"] = now, ext.block()
        return last["block"]
    return block


def _first_sample(args, mem, sampler: Sampler):
    """The first CONNECTED sample, or None after `--timeout` seconds (the game is on the title screen or loading)."""
    deadline = time.monotonic() + (args.timeout if not _continuous(args) else 10**9)
    while True:
        s = sampler.sample()
        if s.state == "CONNECTED":
            return s
        if not mem.alive():
            book.e("read", "eldenring.exe exited")
            return None
        if time.monotonic() >= deadline:
            book.e("read", f"no loaded world after {args.timeout:g} s ({s.error or 'title screen or loading'}); "
                           "load a character first")
            return None
        time.sleep(0.25)


def _query_once(args, mem, sampler: Sampler, export: ExportWriter) -> int:
    sample = _first_sample(args, mem, sampler)
    if sample is None:
        return EXIT_ERROR
    doc = export.build("CONNECTED", sample)
    try:
        selection = view.select(doc, args.query)
    except UnknownName as exc:
        book.e("read", _why_unknown(exc, doc, sample, args.query))
        if getattr(sampler, "names_error", None) and "inventory" in view.label(args.query).lower():
            book.w("read", f"an item cannot be found by its name now: {sampler.names_error}")
        return EXIT_ERROR
    book.d("read", f"query {view.label(args.query)}: {len(selection)} result(s)")
    if getattr(sampler, "names_error", None) and any(p.startswith(("character.inventory", "disk.character.inventory", "character"))
                                                     or p in ("", "disk") for p, _v in selection):
        book.w("read", f"the items' names are not shown: {sampler.names_error}")
    if not selection:
        book.i("read", f"nothing matches {view.label(args.query)!r} right now (no such buff or animation is active)")
    if args.json:
        ui.out(view.as_json(selection))
    else:
        ui.rows(view.rows(selection, flat=args.flat))
    return 0


def _export_once(args, target: Target, mem, sampler: Sampler, export: ExportWriter) -> int:
    sample = _first_sample(args, mem, sampler)
    if sample is None:
        return EXIT_ERROR
    export.emit("CONNECTED", sample)
    export.close()   # retries a write that a reader or the scanner held up
    if export.writes == 0:
        book.e("export", f"could not write {export.logger.path}: the file is busy")
        return EXIT_ERROR
    size = export.logger.path.stat().st_size
    book.ok("export", f"{EXPORT_NAME} ({size / 1024:.1f} KB) written to {export.logger.path.parent}")
    if getattr(args, "params", False):
        return _export_params(args, target, mem)
    return 0


def _export_params(args, target: Target, mem) -> int:
    """`export --params`: every row of every table of the game, every field, read now, to params.json (1.8.0 part 4). Reads only."""
    if target.profile.params is None:
        book.e("export", "this exe version has no params block in offsets.json")
        return EXIT_ERROR
    try:
        tables = Tables(mem, target.profile, target.base)
        logger = JsonLogger(Path(args.out), target.exe_path.parent, filename=PARAMS_NAME)
    except (ParamError, ValueError) as exc:
        book.e("export", str(exc))
        return EXIT_ERROR
    if not tables.index():
        book.e("export", "no param table found yet (the game is still loading them)")
        return EXIT_ERROR
    label = target.profile.label or ""
    profile = {"sha256": target.sha256, "game": "eldenring.exe", "version": label.replace("Elden Ring ", "") or None, "pid": target.pid}
    stats: dict = {}
    started = time.monotonic()
    with ui.working("export", f"writing every param table to {logger.path}", short="reading the param tables") as step:
        def progress(i: int, n: int, table: str) -> None:
            step.short = f"params {i + 1}/{n}: {table}"
        ok = logger.write_chunks(params_chunks(tables, profile, progress, stats))
        if not ok:
            book.e("export", f"could not write {logger.path}: the file is busy")
            return EXIT_ERROR
        size = logger.path.stat().st_size
        step.done(f"{PARAMS_NAME} ({size / 1048576:.1f} MB) written to {logger.path.parent}: {stats['tables']} tables, "
                  f"{stats['rows']:,} rows in {time.monotonic() - started:.1f} s")
    if stats["raw"]:
        book.i("export", f"{len(stats['raw'])} table(s) as bytes (no layout decodes them yet): {', '.join(stats['raw'])}")
    for table, why in stats["skipped"].items():
        book.w("export", f"{table} left out: {why}")
    return 0


class _Redraw:
    """Draws a block of lines on the terminal when they differ from what is shown (at most 30 times a second)."""
    MIN_DRAW_S = 1 / 30

    def __init__(self):
        self.screen = ui.Screen()
        self._shown: list[str] | None = None
        self._last = 0.0

    def show(self, lines: list[str]) -> None:
        now = time.monotonic()
        if (lines == self._shown and self.screen.height) or now - self._last < self.MIN_DRAW_S:
            return
        self.screen.show(lines)
        self._shown, self._last = lines, now

    def detach(self) -> None:
        self.screen.detach()

    def close(self) -> None:
        self.screen.close()


NONE_NOW = "none active"


class _LiveValues:
    """`--live`: the values, kept current.

    On a terminal the tree is redrawn where it stands and a value that just changed is highlighted for `HOLD_S`.
    Elsewhere (an IDE run window, a pipe) the tree is printed once and then one line per changed value follows.
    Buff countdowns and the counters of ignored buffs / animations do not count as changes.
    """
    HOLD_S = 1.0       # how long a changed value stays highlighted

    def __init__(self, name: str | None, export: ExportWriter, sampler: Sampler, as_paths: bool = False):
        self.name, self.export, self.sampler, self.as_paths = name, export, sampler, as_paths
        self.flat: dict[str, object] | None = None
        self.waiting = False
        self._lines: list[str] = []      # the last tree drawn, kept on screen while the world is loading
        self.painter = _Redraw() if ui.can_redraw() else None
        self.hot: dict[str, float] = {}

    def check(self, sample) -> bool:
        """False (after saying why) when the name matches nothing."""
        doc = self.export.build("CONNECTED", sample)
        try:
            view.select(doc, self.name)
            return True
        except UnknownName as exc:
            book.e("read", _why_unknown(exc, doc, sample, self.name))
            return False

    def close(self) -> None:
        if self.painter is not None:
            self.painter.close()

    def _wait(self, sample) -> None:
        """A loading screen (warp, death, quit to title). On a terminal the last tree stays where it is with one status
        line below it and the next frame redraws over both; elsewhere the two messages are printed as events."""
        why = f": {sample.error}" if sample.error else ""
        if self.painter is None:
            if not self.waiting:
                book.i("read", f"waiting for a loaded world{why}")
        else:
            if not self.waiting:
                book.d("read", f"waiting for a loaded world{why}")
            screen = self.painter.screen
            status = ui.paint(" waiting for a loaded world \u2026", "dim", ui.use_color(screen.stream))
            self.painter.show([*self._lines, "", status])
        self.waiting = True

    def tick(self) -> None:
        sample = self.sampler.sample()
        if sample.state != "CONNECTED":
            self._wait(sample)
            return
        if self.waiting:
            (book.d if self.painter is not None else book.i)("read", "world loaded")
            self.waiting = False
        selection = view.select(self.export.build("CONNECTED", sample), self.name)
        shown = selection or [(view.label(self.name), NONE_NOW)]    # a list name with nothing active: say so, keep running
        flat = {}
        for path, value in selection:
            flat.update(view.flatten(value, path))
        now = time.monotonic()
        if self.flat is not None:
            for path, _old, _new in view.changes(self.flat, flat):
                self.hot[path] = now
        first, previous, self.flat = self.flat is None, self.flat, flat
        if self.painter is not None:
            self.hot = {p: t for p, t in self.hot.items() if now - t < self.HOLD_S}
            screen = self.painter.screen
            rows = view.rows(shown, flat=self.as_paths)
            self._lines = ui.format_rows(rows, color=ui.use_color(screen.stream), hot=frozenset(self.hot),
                                         ticking=frozenset(r.path for r in rows if r.path.endswith(view.TICKING)),
                                         columns=screen.size()[0])
            self.painter.show(self._lines)
        elif first:
            ui.rows(view.rows(shown, flat=self.as_paths))
        else:
            stamp = datetime.now().strftime("%H:%M:%S")
            for path, old, new in view.changes(previous, flat):
                key = path.rsplit(".", 1)[-1]
                ui.out(f" {stamp}  {path}  {view.fmt(key, old, path)} \u2192 {view.fmt(key, new, path)}")


class _Board:
    """`read monitor` (`monitor-buffs` / `monitor-animations`) on a terminal: one table per monitor, redrawn where it stands."""

    def __init__(self, monitors):
        self.monitors = monitors
        self.painter = _Redraw()

    def close(self) -> None:
        self.painter.close()

    def tick(self) -> None:
        screen = self.painter.screen
        columns, rows = screen.size()
        color = ui.use_color(screen.stream)
        budget = rows - 1 - (len(self.monitors) - 1)   # the blank lines between tables
        want = {m: len(m.lines(m._now())) + 2 for m in self.monitors}
        share, left = {}, budget
        for i, m in enumerate(sorted(self.monitors, key=lambda m: want[m])):   # small tables first, the rest is shared
            share[m] = max(3, min(want[m], left // (len(self.monitors) - i)))
            left -= share[m]
        lines: list[str] = []
        for m in self.monitors:
            if lines:
                lines.append("")
            lines += ui.format_ledger(m.name, m.summary(), m.lines(m._now()), color=color, columns=columns,
                                      max_rows=share[m], waiting=m.waiting)
        self.painter.show(lines)


class _TableReload:
    """Re-reads names.json when it changed, so names added while a monitor runs show up at once."""

    def __init__(self, path: Path, sampler: Sampler):
        self.path, self.sampler = Path(path), sampler
        self._stamp = self._mtime()

    def _mtime(self):
        try:
            st = self.path.stat()
            return st.st_mtime_ns, st.st_size
        except OSError:
            return None

    def check(self) -> None:
        stamp = self._mtime()
        if stamp == self._stamp:
            return
        self._stamp = stamp
        if stamp is None:
            return
        try:
            table = load_state_ids(self.path)
        except ValueError as exc:
            book.w("read", f"{self.path.name} changed but cannot be read, keeping the old names: {exc}")
            return
        self.sampler.state_ids = table
        book.i("read", f"{self.path.name} reloaded ({len(table.buffs)} buffs, {len(table.animations)} animations)")


def _live(args, target: Target, mem, sampler: Sampler, export: ExportWriter, vault: Path | None,
          watch: baselines.Watch | None = None) -> int:
    stream = None
    if not args.export:
        sample = _first_sample(args, mem, sampler)
        if sample is None:
            return EXIT_ERROR
        stream = _LiveValues(args.query, export, sampler, args.flat)
        if not stream.check(sample):
            return EXIT_ERROR
    book.ok("read", "attached, reading (Ctrl+C to stop)")
    try:
        return _loop(args, target, mem, sampler, [], export, vault, stream, watch=watch)
    finally:
        if stream is not None:
            stream.close()
        if args.export:
            export.close()


def _monitors(args, target: Target, mem, sampler: Sampler, vault: Path | None, watch: baselines.Watch | None = None) -> int:
    both = args.live_buffs and args.live_animations
    show = "mapped" if args.mapped else "unmapped" if args.unmapped else "all"
    redraw = ui.can_redraw()

    def out_for(name: str):
        if redraw:
            return None   # the table shows it
        prefix = f"[{name}] " if both else ""
        return lambda line: print(prefix + line, flush=True)

    monitors = []
    if args.live_buffs:
        monitors.append(BuffsMonitor(sampler, out_for("buffs"), quiet=args.quiet, show=show))
    if args.live_animations:
        monitors.append(AnimationsMonitor(sampler, out_for("animations"), show=show))
    for m in monitors:
        why = m.unsupported(target.profile)
        if why:
            book.e("read", f"{m.name}: {why}")
            return EXIT_ERROR
    for m in monitors:
        m.start()
    board = _Board(monitors) if redraw else None
    book.ok("read", "attached, reading (Ctrl+C to stop)")
    try:
        return _loop(args, target, mem, sampler, monitors, None, vault, board,
                     _TableReload(names_file(args), sampler), watch=watch)
    finally:
        if board is not None:
            board.close()


def _loop(args, target: Target, mem, sampler: Sampler, monitors, export: ExportWriter | None, vault: Path | None,
          stream: _LiveValues | _Board | None, reload: _TableReload | None = None, watch: baselines.Watch | None = None) -> int:
    period = 1.0 / args.hz
    next_tick = time.monotonic()
    next_scan = next_tick + RESCAN_S
    last_sample = None
    live_export = export is not None and export.logger is not None
    while True:
        if not mem.alive():
            if live_export:
                export.emit("DISCONNECTED", sample=last_sample)
            return 0

        now = time.monotonic()
        if now >= next_scan:
            if eac_loaded(target.pid):
                if live_export:
                    export.anti_cheat = "ACTIVE_EAC"
                    export.emit("EAC_DETECTED", note="EasyAntiCheat module appeared; stopped reading")
                book.e("read", "EasyAntiCheat appeared in eldenring.exe; stopped reading")
                return EXIT_EAC
            if export is not None:
                export.creative = bool(vault) and _in_session(vault, target)
            if reload is not None:
                reload.check()
            _take_baselines(watch, sampler, monitors)
            next_scan = now + RESCAN_S

        for m in monitors:
            m.tick()

        if stream is not None:
            stream.tick()
        elif live_export:
            if not args.no_idle and not is_window_active(target.pid):
                export.emit("IDLE", sample=last_sample)
            else:
                last_sample = sampler.sample()
                export.emit(last_sample.state, last_sample)

        next_tick += period
        delay = next_tick - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        else:
            next_tick = time.monotonic()   # fell behind: do not try to catch up

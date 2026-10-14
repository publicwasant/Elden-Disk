"""`resurrect` (1.8.0, spec 1.8.0; `resurrect great-enemies --activate` in its part 1): bring a beaten boss back for this session.

    resurrect NAME | ID | PATH ...        a name in any letter case or a part of it (`margit`, `mohg lord`), the id (`10000850`), or the
                                         path in the document (`creative.resurrect.great_enemies.10000850`)
    resurrect * | all                    every great enemy that is defeated
    resurrect ... --dry-run              say what would come back; write nothing (reads the game when it runs)
    resurrect --when-loaded              what `run` starts: `resurrect.great_enemies.activate` of creative.json, once a character is
                                         in the world

`read creative.resurrect.great_enemies` shows the ones that are defeated now: the ones that can be brought back (there is no list here).

The game remembers a defeated boss in event flags of the save. `resurrect` turns the boss's flags OFF in the game's memory only (the
defeat, the play-log trigger of its Remembrance, its drops' flags, its intro's flags; the table says which, spec section 4), inside the
session `run` started with the vault ON: when the game closes the vault puts the save back. The boss appears once its area loads again.
Only the flags of the table can be written (writer/eventflags.py); a flag is never turned ON.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..console import require_windows_x64
from ..creative.resurrect.great_enemies import TableError, load
from ..creative.resurrect.great_enemies.table import creative_list
from ..game.attach import EXIT_NO_SESSION, EXIT_UNSUPPORTED, AttachError, locate, open_read
from ..game.eventflags import EventFlagError, EventFlags
from ..logbook import CREATIVE_TAG, book
from ..writer.eventflags import FlagRefused, turn_off
from ..writer.writer import WritableProcessMemory, WriteGate
from .. import ui

APPEARS = "it appears once its area loads again: warp to a grace in another region, then come back"


def _states(table, mem, target) -> dict[int, bool | None]:
    flags = EventFlags(mem, target.base, target.profile.event_flags)
    got = flags.get_many(table.defeated_flags().values())
    return {rid: got[f] for rid, f in table.defeated_flags().items()}


def _facts(r: dict) -> str:
    grace = f"grace: {r['grace']['name']}" if r.get("grace") else "grace: (none in its map)"
    drop = ", ".join(r.get("drop") or []) or "drop: (unknown)"
    return f"{r.get('place') or r['map']} \u00b7 {grace} \u00b7 {r['runes']:,} runes \u00b7 {drop}"


def activate(table, rids: list[int], mem, target, gate, every: bool = False) -> int:
    """Bring `rids` back (spec 1.8.0 section 6). -> exit code. `every` (`all`): a boss whose flags the game does not hold now is left
    out quietly instead of being an error."""
    flags = EventFlags(mem, target.base, target.profile.event_flags)
    allowed = table.allowed()
    done, alive, failed, story = [], [], [], []
    for rid in rids:
        r = table.rows[rid]
        state = flags.get(r["flags"]["defeated"])
        if state is False:
            alive.append(rid)
            continue
        if state is None:
            if not every:
                failed.append(rid)
                book.e(CREATIVE_TAG, f"{r['name']}: not resurrected: the game does not hold its flags now")
            continue
        got = turn_off(mem, gate, flags, table.flags_of(rid), allowed)
        bad = [f"{f} ({how})" for f, how in got.items() if how in ("did not stick",) or (how == "not held" and f == r["flags"]["defeated"])]
        if bad:
            failed.append(rid)
            book.e(CREATIVE_TAG, f"{r['name']}: not resurrected: {', '.join(bad)}")
            continue
        done.append(rid)
        book.i(CREATIVE_TAG, f"{r['name']} alive again: {_facts(r)}")
        if r.get("story"):
            story.append(r["name"])
    if every:
        book.i(CREATIVE_TAG, f"{len(alive)} great enemies were alive already")
    else:
        for rid in alive:
            book.i(CREATIVE_TAG, f"{table.rows[rid]['name']}: already alive")
    if done:
        book.i(CREATIVE_TAG, f"{len(done)} great enem{'y' if len(done) == 1 else 'ies'} alive again; {APPEARS}")
    if story:
        book.w(CREATIVE_TAG, f"{', '.join(story)}: story boss{'es' if len(story) > 1 else ''}: what the death started (a Great Rune, the people "
                           "who speak of it) may look odd until the game closes; the vault puts your save back then")
    return 1 if failed else 0


PREFIX = "creative.resurrect.great_enemies."


def names_of(words: list[str]) -> list[str]:
    """The words as the table resolves them: a path of the document becomes its last part (the id or the name); `*` -> `all`."""
    out = []
    for w in (x.strip() for x in words if x.strip()):
        if w.lower().startswith(PREFIX):
            w = w[len(PREFIX):].split(".")[0]
        out.append("all" if w == "*" else w)
    return out


def _dry_run(table, rids: list[int], args) -> int:
    """`--dry-run`: what would come back. Reads the game when it runs (read-only); nothing is written."""
    states, why = None, ""
    try:
        target = locate(Path(args.offsets))
        if target.profile.event_flags is None:
            why = "this game version has no event_flags block in offsets.json"
        else:
            mem = open_read(target)
            try:
                states = _states(table, mem, target)
            finally:
                mem.close()
    except (AttachError, EventFlagError, OSError) as exc:
        why = str(exc)
    for rid in rids:
        r = table.rows[rid]
        state = None if states is None else states.get(rid)
        what = {True: "would come back", False: "alive already: nothing to do", None: "the game does not hold its flags now"}[state] \
            if states is not None else "the game was not read"
        ui.out(f"  {rid:>10}  {r['name']:<38} {what}  ({_facts(r)})")
    ui.result("info", f"dry run: nothing was written" + (f"; the game: {why}" if why else ""))
    return 0


def cmd_resurrect(args) -> int:
    require_windows_x64()
    try:
        table = load(getattr(args, "table", None))
    except TableError as exc:
        book.e(CREATIVE_TAG, str(exc))
        return 1
    names = names_of(getattr(args, "names", None) or [])
    if "all" in names and len(names) > 1:
        book.e(CREATIVE_TAG, "`*` and `all` stand alone: every great enemy that is defeated")
        return 1
    if args.when_loaded and names:
        book.e(CREATIVE_TAG, "--when-loaded brings back the list of creative.json (resurrect.great_enemies.activate): give no names with it")
        return 1
    if args.when_loaded:
        from .innovate import spec_file
        try:
            design = json.loads(Path(spec_file(args)).read_text(encoding="utf-8"))
            names = creative_list(design) or []
        except (OSError, ValueError, TableError) as exc:
            book.e(CREATIVE_TAG, f"great enemies: creative.json cannot be read ({exc})")
            return 1
        if not names:
            book.i(CREATIVE_TAG, "great enemies: creative.json names none (resurrect.great_enemies.activate): nothing to do")
            return 0
    if not names:
        ui.result("info", f"resurrect NAME | ID | PATH ... (or * / all): {len(table.rows)} great enemies in the table ({table.game}); "
                          "`read creative.resurrect.great_enemies` shows the ones that are defeated now")
        return 0
    try:
        rids = table.resolve(names)
    except TableError as exc:
        book.e(CREATIVE_TAG, f"great enemies: {exc}; nothing was written")
        return 1
    if getattr(args, "dry_run", False):
        return _dry_run(table, rids, args)
    if names == ["all"]:
        book.i(CREATIVE_TAG, f"great enemies: every one of the {len(rids)} that is defeated comes back (the vault restores the save "
                           "when the game closes)")

    from .write import ATTACH_WAIT, _attach, _authorised, _wait_world
    target, code, record = _attach(args, ATTACH_WAIT if args.when_loaded else 0)
    if target is None:
        return code
    if target.profile.event_flags is None:
        book.e(CREATIVE_TAG, "this game version has no event_flags block in offsets.json")
        return EXIT_UNSUPPORTED
    if not _authorised(target, record):
        return EXIT_NO_SESSION
    mem = WritableProcessMemory(target.pid)
    try:
        gate = WriteGate()
        gate.open()   # only after the session check above
        if args.when_loaded:
            if not _wait_world(mem, target, "great enemies", tag=CREATIVE_TAG, stable=0.0 if getattr(args, "world_ready", False) else None):
                book.i(CREATIVE_TAG, "great enemies: the game closed before a character was in the world; nothing was written")
                return 0
        else:
            from .write import world_loaded
            loaded, why = world_loaded(mem, target)
            if not loaded:
                book.e(CREATIVE_TAG, f"great enemies: no character in the world ({why}); nothing was written")
                return 1
        return activate(table, rids, mem, target, gate, every=names == ["all"])
    except (EventFlagError, FlagRefused) as exc:
        book.e(CREATIVE_TAG, f"great enemies: {exc}; nothing more was written")
        return EXIT_UNSUPPORTED if "moved it" in str(exc) else 1
    finally:
        mem.close()

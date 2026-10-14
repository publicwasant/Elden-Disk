"""`resurrect great-enemies` (1.8.0, spec 1.8.0): bring a beaten boss back for this session.

    resurrect great-enemies --list [--defeated | --alive] [--area NAME] [--story] [--dlc] [--json]
    resurrect great-enemies --activate NAME|ID [NAME|ID ...]      (or --activate --all / `*` / `all`)
    resurrect great-enemies --when-loaded                        (what `run` starts: the design's list)

The game remembers a defeated boss in event flags of the save. --activate turns the boss's flags OFF in the game's memory only (the
defeat, the play-log trigger of its Remembrance, its drops' flags, its intro's flags; the table says which, spec section 4), inside the
session `run` started with the vault ON: when the game closes the vault puts the save back. The boss appears once its area loads again.
Only the flags of the table can be written (writer/eventflags.py); a flag is never turned ON.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..console import require_windows_x64
from ..design.resurrect.great_enemies import TableError, load
from ..design.resurrect.great_enemies.table import design_list
from ..game.attach import EXIT_NO_SESSION, EXIT_UNSUPPORTED, AttachError, locate, open_read
from ..game.eventflags import EventFlagError, EventFlags
from ..logbook import DESIGN_TAG, book
from ..writer.eventflags import FlagRefused, turn_off
from ..writer.writer import WritableProcessMemory, WriteGate
from .. import ui

APPEARS = "it appears once its area loads again: warp to a grace in another region, then come back"


def _rows(table, args, states: dict | None) -> list[int]:
    out = []
    for rid, r in table.rows.items():
        if getattr(args, "story", False) and not r.get("story"):
            continue
        if getattr(args, "dlc", False) and not r.get("dlc"):
            continue
        area = (getattr(args, "area", None) or "").lower()
        if area and area not in f"{r.get('place') or ''} {r.get('map')} {r['name']}".lower():
            continue
        if states is not None and getattr(args, "defeated", False) and states.get(rid) is not True:
            continue
        if states is not None and getattr(args, "alive", False) and states.get(rid) is not False:
            continue
        out.append(rid)
    return out


def _states(table, mem, target) -> dict[int, bool | None]:
    flags = EventFlags(mem, target.base, target.profile.event_flags)
    got = flags.get_many(table.defeated_flags().values())
    return {rid: got[f] for rid, f in table.defeated_flags().items()}


def _facts(r: dict) -> str:
    grace = f"grace: {r['grace']['name']}" if r.get("grace") else "grace: (none in its map)"
    drop = ", ".join(r.get("drop") or []) or "drop: (unknown)"
    return f"{r.get('place') or r['map']} · {grace} · {r['runes']:,} runes · {drop}"


def cmd_list(args, table) -> int:
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
    if (args.defeated or args.alive) and states is None:
        book.e(DESIGN_TAG, f"--defeated / --alive read the game: {why}")
        return EXIT_UNSUPPORTED if "event_flags" in why else 1
    rows = _rows(table, args, states)
    if args.json:
        ui.out(json.dumps([{"id": rid, **table.rows[rid], **({"defeated": states.get(rid)} if states is not None else {})}
                           for rid in rows], ensure_ascii=False, indent=1))
        return 0
    for rid in rows:
        r = table.rows[rid]
        state = "" if states is None else {True: "defeated  ", False: "alive     ", None: "not held  "}[states.get(rid)]
        marks = (" story" if r.get("story") else "") + (" DLC" if r.get("dlc") else "")
        ui.out(f"  {rid:>10}  {state}{r['name']:<38} {_facts(r)}{marks}")
    tail = f"; the game: {why}" if states is None and why else ""
    ui.result("info", f"{len(rows)} of {len(table.rows)} great enemies{tail}")
    return 0


def activate(table, rids: list[int], mem, target, gate, every: bool = False) -> int:
    """Bring `rids` back (spec 1.8.0 section 6). -> exit code. `every` (--all): a boss whose flags the game does not hold now is left
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
                book.e(DESIGN_TAG, f"{r['name']}: not resurrected: the game does not hold its flags now")
            continue
        got = turn_off(mem, gate, flags, table.flags_of(rid), allowed)
        bad = [f"{f} ({how})" for f, how in got.items() if how in ("did not stick",) or (how == "not held" and f == r["flags"]["defeated"])]
        if bad:
            failed.append(rid)
            book.e(DESIGN_TAG, f"{r['name']}: not resurrected: {', '.join(bad)}")
            continue
        done.append(rid)
        book.i(DESIGN_TAG, f"{r['name']} alive again: {_facts(r)}")
        if r.get("story"):
            story.append(r["name"])
    if every:
        book.i(DESIGN_TAG, f"{len(alive)} great enemies were alive already")
    else:
        for rid in alive:
            book.i(DESIGN_TAG, f"{table.rows[rid]['name']}: already alive")
    if done:
        book.i(DESIGN_TAG, f"{len(done)} great enem{'y' if len(done) == 1 else 'ies'} alive again; {APPEARS}")
    if story:
        book.w(DESIGN_TAG, f"{', '.join(story)}: story boss{'es' if len(story) > 1 else ''}: what the death started (a Great Rune, the people "
                           "who speak of it) may look odd until the game closes; the vault puts your save back then")
    return 1 if failed else 0


def cmd_resurrect(args) -> int:
    require_windows_x64()
    try:
        table = load(getattr(args, "table", None))
    except TableError as exc:
        book.e(DESIGN_TAG, str(exc))
        return 1
    if args.list:
        return cmd_list(args, table)
    names = list(args.activate or [])
    if args.all:
        names = ["all"]
    if args.when_loaded and not names:
        from .design import spec_file
        try:
            design = json.loads(Path(spec_file(args)).read_text(encoding="utf-8"))
            names = design_list(design) or []
        except (OSError, ValueError, TableError) as exc:
            book.e(DESIGN_TAG, f"great enemies: the design cannot be read ({exc})")
            return 1
        if not names:
            book.i(DESIGN_TAG, "great enemies: the design names none (resurrect.great_enemies.activate): nothing to do")
            return 0
    if not names:
        ui.result("info", f"great enemies: {len(table.rows)} in the table ({table.game}); --list shows them, --activate NAME brings one back")
        return 0
    try:
        rids = table.resolve(names)
    except TableError as exc:
        book.e(DESIGN_TAG, f"great enemies: {exc}; nothing was written")
        return 1
    if names == ["all"]:
        book.i(DESIGN_TAG, f"great enemies: every one of the {len(rids)} that is defeated comes back (the vault restores the save "
                           "when the game closes)")

    from .write import ATTACH_WAIT, _attach, _authorised, _wait_world
    target, code, record = _attach(args, ATTACH_WAIT if args.when_loaded else 0)
    if target is None:
        return code
    if target.profile.event_flags is None:
        book.e(DESIGN_TAG, "this game version has no event_flags block in offsets.json")
        return EXIT_UNSUPPORTED
    if not _authorised(target, record):
        return EXIT_NO_SESSION
    mem = WritableProcessMemory(target.pid)
    try:
        gate = WriteGate()
        gate.open()   # only after the session check above
        if args.when_loaded:
            if not _wait_world(mem, target, "great enemies", tag=DESIGN_TAG):
                book.i(DESIGN_TAG, "great enemies: the game closed before a character was in the world; nothing was written")
                return 0
        else:
            from .write import world_loaded
            loaded, why = world_loaded(mem, target)
            if not loaded:
                book.e(DESIGN_TAG, f"great enemies: no character in the world ({why}); nothing was written")
                return 1
        return activate(table, rids, mem, target, gate, every=names == ["all"])
    except (EventFlagError, FlagRefused) as exc:
        book.e(DESIGN_TAG, f"great enemies: {exc}; nothing more was written")
        return EXIT_UNSUPPORTED if "moved it" in str(exc) else 1
    finally:
        mem.close()

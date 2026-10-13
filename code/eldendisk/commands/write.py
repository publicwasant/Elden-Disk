"""`write --set NAME=VALUE... --refill LIST --reset NAME...`: apply edits once to the running game, inside an authorised
session. Names under `params.` edit the game's own tables (and `--reset` puts the game's own values back).

`write --text [--wait [SEC]]` (1.7.1) puts the text of the design's spells (name, short line, long description) into the running
game: it rebuilds the game's three text tables and switches the game to them (writer/text.py). `run` starts it by itself after the
game is up. Needs the same authorised session; the text lasts until the game closes.

`write --flame-color [--wait [SEC]]` (1.7.1) recolours the fire of Flame, Grant Me Strength (the fire while casting and the burst; the fire
on the body is left alone) in the running game with the design's `flame_color` (writer/fxr.py). `run` starts it after the game is up too;
same session, same life span.

`--when-loaded` (what `run` starts, with --text and --flame-color): wait until a character is in the world (the player exists: the chain
`read` follows), then write ONCE and end. Nothing watches the game afterwards. The text tables stay as written when the world is
loaded again (seen in the game's log). Both steps FIND what they change by looking through the game's memory (writer/scan.py): the
effect files by their colours (writer/fxr.py), the text tables by their shape and the array that points at them (writer/text.py);
no fixed chain from the exe is used for either, because the one for the text did not hold from run to run."""
from __future__ import annotations

import time
from pathlib import Path

from ..console import require_windows_x64
from ..logbook import book
from ..extension.innovate_items.fmg import Fmg, FmgError
from ..game.attach import EXIT_ERROR, EXIT_NO_SESSION, EXIT_UNSUPPORTED, AttachError, Target, locate
from ..game.layout import LEVEL_RANGE, Layout
from ..game.memory import read_u32
from ..game.params import ParamLockedError, ParamNameError
from ..game.processes import process_started
from ..vault import VaultError, authorise, resolve_vault
from ..vault import session as vault_session
from ..writer.paramedit import SNAPSHOT_NAME, Snapshot
from ..writer import fxr as wfxr
from ..writer import scan as wscan
from ..writer import text as wtext
from ..writer.cache import CACHE_NAME, MemoryCache
from ..writer.writer import MemoryWriter, WritableProcessMemory, WriteGate, parse_policy, plan_params
from .extension import ext_dir, spec_file
from .. import extension
from ..extension.innovate_items.spells.service import ExtensionError

TEXT_TABLES = {"GoodsName": "goods_name", "GoodsInfo": "goods_info", "GoodsCaption": "goods_captions"}   # game table -> field of `text`
POLL, SETTLE = 1.0, 3.0     # seconds between looks for the game's modules; seconds to see that the game kept the new tables
TELL_EVERY = 30.0           # seconds between the log lines of a wait
WORLD_POLL, WORLD_STABLE = 2.0, 5.0     # --when-loaded: seconds between looks for a character in the world; seconds it must stay there
ATTACH_WAIT = 600.0         # --when-loaded: seconds to wait for the game's modules to be readable (it is still starting)
LOOKS = (0.0, 10.0, 20.0, 40.0, 60.0)   # seconds of rest before each look through the game's memory, while what is looked for is not there yet
ONCE = (0.0,)               # by hand without --wait: one look
_sleep, _clock = time.sleep, time.monotonic      # tests replace these


def new_table(old: wtext.Table, rows: dict) -> bytes | None:
    """The game's table `old` with `rows` (goods id -> text) in it, in its file form; an empty text takes the id out. None when the
    result says what `old` says already (so nothing is allocated and nothing is switched). Raises FmgError."""
    fmg = Fmg.read(old.data)
    before = dict(fmg.entries)
    for gid, text in rows.items():
        if text:
            fmg.entries[gid] = text
        else:
            fmg.entries.pop(gid, None)
    return None if fmg.entries == before else fmg.write()


def _sizes_line(seen) -> str:
    big = sorted(seen.sizes, reverse=True)[:6]
    return f"{sum(seen.sizes.values())} text tables of the game were seen; the biggest sizes: " + ", ".join(f"{k} (x{seen.sizes[k]})" for k in big)


def _cost(w) -> str:
    """For the log: what a look cost the game: the pieces read, the longest one, the time spent resting."""
    return f"{w.pieces} pieces, the slowest {w.slowest * 1000:.0f} ms, {w.slept:.1f} s resting"


def _look_for_tables(mem, text) -> tuple[list, str]:
    """One look for the three tables and the array that points at them. -> ([{table name: Table}] one per array found, "") or ([], why
    not). The look for the tables ends when each has been seen; if no array points at them it is made again through ALL the memory
    (there can be a second copy of a table), and the array is looked for again."""
    seen = wtext.find_tables(mem, text)
    walked = seen.walked
    book.d("write", f"goods text: looked for the tables: {walked.megabytes} MB read in {walked.seconds:.1f} s ({walked.tier}; {_cost(walked)}); "
           + ", ".join(f"{n}: " + (", ".join(f"{b:#x}" for b in bs) or "not seen") for n, bs in seen.found.items()))
    if not all(seen.found.values()):
        missing = [n for n, bs in seen.found.items() if not bs]
        return [], (f"no table of the size offsets.json says for {', '.join(missing)} ({', '.join(str(text.sizes[n]) for n in missing)} bytes); "
                    + _sizes_line(seen) + " - the game is still starting, or it is played in another language than offsets.json describes")
    arrays = wtext.find_arrays(mem, text, seen.found)
    walked = arrays.walked
    book.d("write", f"goods text: looked for the array that points at them: {walked.megabytes} MB read in {walked.seconds:.1f} s "
           f"({walked.tier}; {_cost(walked)}); {arrays.pointers} pointer(s) to the first table seen, {len(arrays.found)} array(s)")
    if not arrays.found and seen.walked.stopped:
        more = wtext.find_tables(mem, text, everything=True)
        if sum(map(len, more.found.values())) > sum(map(len, seen.found.values())):
            book.d("write", "goods text: more tables seen in the whole memory: " + ", ".join(f"{n}: {len(bs)}" for n, bs in more.found.items()))
            arrays = wtext.find_arrays(mem, text, more.found)
    if not arrays.found:
        return [], ("the tables were seen but nothing points at all three of them at the places the file numbers say: the text was set already "
                    "in this session (the game no longer points at its own tables), or the game keeps them differently than offsets.json describes")
    out = []
    for array, bases in arrays.found:
        tables = {}
        for name, number in text.files.items():
            table, why = wtext.read_table(mem, name, array + 8 * number)
            if table is None:
                return [], f"{name}: {why}"
            tables[name] = table
        book.d("write", f"goods text: array at {array:#x} ({wscan.where(mem, array)}): " + ", ".join(f"{n} -> {t.base:#x}" for n, t in tables.items()))
        out.append(tables)
    return out, ""


def _find_tables(mem, target: Target, passes):
    """-> ([{table name: Table}], "") or ([], why not): looks for the tables as `passes` says (the rest in seconds before each look), until
    they are found."""
    why = ""
    for number, rest in enumerate(passes, 1):
        if rest:
            book.d("write", f"goods text: not found yet ({why}); looking again in {rest:g} s")
            _sleep(rest)
        found, why = _look_for_tables(mem, target.profile.text)
        if found:
            return found, ""
    return [], why


def _cache_of(args, target: Target) -> MemoryCache | None:
    """The memory cache of this game process (writer/cache.py), or None when the vault cannot be found."""
    try:
        return MemoryCache(resolve_vault(args.vault) / CACHE_NAME, target.pid, target.started).load()
    except VaultError:
        return None


def _keep(cache: MemoryCache | None, what: str) -> None:
    if cache is None:
        return
    try:
        cache.save()
    except OSError as exc:
        book.w("write", f"could not save {CACHE_NAME} ({exc}); a later write of the {what} in this game looks through the memory again")


def _put_text(mem, gate, target: Target, texts: dict, passes, cache: MemoryCache | None = None) -> int:
    after: dict[int, bytes] = {}
    names: dict[int, str] = {}
    for attempt in (1, 2):
        arrays, why = _find_tables(mem, target, passes if attempt == 1 else ONCE)
        if not arrays:
            book.e("write", f"the game's text tables were not found ({why})")
            return 1
        for tables in arrays:
            for name, field in TEXT_TABLES.items():
                old = tables[name]
                names[old.slot_at] = name
                try:
                    new = new_table(old, {gid: t[field] for gid, t in texts.items()})
                    if new is None:
                        after[old.slot_at] = old.data
                        book.d("write", f"goods text {name}: already as the design says")
                        continue
                    base = wtext.swap(mem, gate, old, new)
                except (FmgError, wtext.TextError) as exc:
                    book.e("write", f"goods text {name}: {exc}")
                    return 1
                after[old.slot_at] = new
                book.d("write", f"goods text {name}: {len(old.data)} -> {len(new)} bytes, now at {base:#x}")
        if len(passes) <= 1:
            break
        _sleep(SETTLE)
        kept = {at: wtext.read_table(mem, names[at], at)[0] for at in after}
        if all(t is not None and t.data == after[at] for at, t in kept.items()):
            break
        if attempt == 2:
            book.e("write", "the game replaced its text tables again after they were set; run `eldendisk write --text` again")
            return 1
        book.w("write", "the game replaced its text tables after they were set (it was still loading); setting them once more")
    if cache is not None:                       # where the pointers are and what they hold now: a later write needs no look
        cache.set_text({name: at for at, name in names.items()}, {gid: dict(t) for gid, t in texts.items()})
        _keep(cache, "text")
    shown = sum(1 for t in texts.values() if any(t.values()))
    book.ok("write", f"goods text: {shown} spell{'s' if shown != 1 else ''} named in the game (name, short line, description); "
                     "it lasts until the game closes")
    return 0


def world_loaded(mem, target: Target) -> tuple[bool, str]:
    """Is a character in the world? The chain `read` follows: WorldChrMan -> PlayerIns -> PlayerGameData, and a level that makes sense.
    -> (True, "") or (False, why not yet)."""
    gd, why = Layout(mem, target.profile, target.base).locate_game_data()
    if gd is None:
        return False, why or "title screen or loading (no player yet)"
    level = read_u32(mem, gd + target.profile.level)
    if level is None or not LEVEL_RANGE[0] <= level <= LEVEL_RANGE[1]:
        return False, "the player's data is not valid yet"
    return True, ""


def _wait_world(mem, target: Target, name: str, tag: str = "write") -> bool:
    """Wait until a character is in the world and has stayed there for WORLD_STABLE seconds (the loading screens flicker). The only thing
    done meanwhile is a look at a few pointers every WORLD_POLL seconds. False when the game closed first."""
    since, said_at, said_before = None, -2 * TELL_EVERY, False
    while mem.alive():
        loaded, why = world_loaded(mem, target)
        now = _clock()
        if loaded:
            since = now if since is None else since
            if now - since >= WORLD_STABLE:
                book.i(tag, f"{name}: a character is in the world")
                return True
        else:
            since = None
            if not said_before:
                book.i(tag, f"{name}: waiting for a character to be in the world ({why})")
                said_before, said_at = True, now
            elif now - said_at >= 2 * TELL_EVERY:
                said_at = now
                book.d(tag, f"{name}: still waiting for the world ({why})")
        _sleep(WORLD_POLL)
    return False


def _attach(args, wait: float):
    """The running game of an authorised session -> (target, None), or (None, the exit code) after saying why. Shared by the
    steps `run` starts (--text, --flame-color)."""
    try:
        vault_root = resolve_vault(args.vault)
        record = vault_session.load(vault_root)
    except VaultError as exc:
        book.e("write", str(exc))
        return None, EXIT_NO_SESSION, None
    t0 = _clock()
    while True:
        try:
            target: Target = locate(Path(args.offsets))
            break
        except AttachError as exc:     # the game may still be starting (its modules cannot be listed yet): with --wait, look again
            if wait <= 0 or exc.code != EXIT_ERROR or "not running" in str(exc) or _clock() - t0 >= wait:
                book.e("write", str(exc))
                return None, exc.code, None
            _sleep(POLL)
    return target, None, record


def _authorised(target: Target, record) -> bool:
    problems = authorise(record, game_pid=target.pid, game_started=target.started,
                         exe_sha256=target.sha256, started_of=process_started)
    if problems:
        book.e("write", "refused, no edit was made:")
        for p in problems:
            book.e("write", f"  {p}")
    return not problems


def cmd_write_text(args) -> int:
    """`write --text [--wait [SEC] | --when-loaded]`: see the module text."""
    require_windows_x64()
    when_loaded = bool(getattr(args, "when_loaded", False))
    wait = ATTACH_WAIT if when_loaded else float(getattr(args, "wait", 0) or 0)
    try:
        ci = extension.open_spells(ext_dir(args), spec_file(args))
        sel, note = ci.selection()          # the spells the build holds: the last `--add` chose them
        if note:
            book.w("write", f"innovate-items spells: {note}")
        texts = ci.texts(sel)
    except ExtensionError as exc:
        book.e("write", str(exc))
        return 1
    target, code, record = _attach(args, wait)
    if target is None:
        return code
    if target.profile.text is None or not set(TEXT_TABLES) <= set(target.profile.text.files):
        book.e("write", "this game version has no `text` block (files and sizes of GoodsName GoodsInfo GoodsCaption) in offsets.json")
        return EXIT_UNSUPPORTED
    if not _authorised(target, record):
        return EXIT_NO_SESSION
    mem = WritableProcessMemory(target.pid)
    book.d("write", "scan: " + (wscan.go_easy() or "ordinary priority"))
    try:
        gate = WriteGate()
        gate.open()   # only after the session, anti-cheat and profile checks above
        if when_loaded:
            if not _wait_world(mem, target, "goods text"):
                book.i("write", "goods text: the game closed before a character was in the world; nothing was written")
                return 0
            return _put_text(mem, gate, target, texts, LOOKS, _cache_of(args, target))
        return _put_text(mem, gate, target, texts, LOOKS if wait > 0 else ONCE, _cache_of(args, target))
    finally:
        mem.close()


def _shown(rgb) -> str:
    """A colour in a log line as the design writes it: "#90D5FF", or the numbers when a channel is above 1."""
    from ..extension.innovate_items.spells.spec import colour_text
    t = colour_text(rgb)
    return t if isinstance(t, str) else str(tuple(round(c, 3) for c in rgb))


def _put_flame(mem, gate, colour, passes=ONCE, eyes=None, accent=None, fresh=False, cache: MemoryCache | None = None) -> int:
    """Recolour the fire (`colour`, the two effects) and the positive curse energy eyes (`eyes`, when the design gives them a colour): one look
    through the game's memory for the effect files not done yet (all in the same look), as the schedule `passes` says (the rest in
    seconds before each look). A look is only made while something is missing. Either colour may be None. `accent`: the second colour
    of the fire (the places the fire's plan leaves out, writer/fxr_plans.py `accent`), with `colour` only. `fresh` (`--when-loaded`, a game
    `run` has just started): nothing can be painted yet, so the look searches only for the game's own colours (half the searching)."""
    ring = accent if colour is not None else None          # the ring of runes at the hand takes the fire's second colour
    targets = {**({e: colour for e in wfxr.effect_ids()} if colour is not None else {}),
               **({e: eyes for e in wfxr.eyes_ids()} if eyes is not None else {}),
               **({e: ring for e in wfxr.ring_ids()} if ring is not None else {})}
    label = {**{e: "flame colour" for e in wfxr.effect_ids()}, **{e: "eyes colour" for e in wfxr.eyes_ids()},
             **{e: "ring colour" for e in wfxr.ring_ids()}}
    optional = set(wfxr.ring_ids())                        # the game may hold no ring: it is painted when it is there
    what = "flame colour" if eyes is None else "eyes colour" if colour is None else "flame and eyes colour"
    todo, done = list(targets), {}
    for number, rest in enumerate(passes, 1):
        if rest:
            book.d("write", f"{what}: the game does not hold {', '.join(todo)} yet; looking again in {rest:g} s")
            _sleep(rest)
        try:
            # the eyes and the ring: every copy (the game holds the eyes' file more than once and draws from one a first find missed)
            got, found = wfxr.paint_many(mem, gate, todo, {e: targets[e] for e in todo},
                                         everything=any(e in wfxr.eyes_ids() or e in optional for e in todo),
                                         accent=accent if colour is not None else None,
                                         required=[e for e in todo if e not in optional], painted=not fresh)
        except wfxr.FlameError as exc:
            book.e("write", f"{what}: {exc}")
            return 1
        w = found.walked
        book.d("write", f"{what}: look {number}/{len(passes)}: {w.megabytes} MB read in {w.seconds:.1f} s ("
                        + (f"stopped in the {w.tier} of the blocks, all found" if w.stopped
                           else "around where the effect files lie" if w.complete and w.tier == "near"
                           else "the whole memory" if w.complete else "ran out of time before the end")
                        + f"; {_cost(w)}); found {', '.join(got) or 'nothing'}")
        for eid, p in got.items():
            done[eid] = p
            where = f" at {p.bases[0]:#x}, {wscan.where(mem, p.bases[0])}" if p.bases else ""
            book.d("write", f"{label[eid]} {eid}: {p.copies} copy(ies) changed ({p.places} places), {p.already} already changed{where}")
        todo = [e for e in todo if e not in done]
        if not [e for e in todo if e not in optional]:
            break
    for e in [e for e in todo if e in optional]:
        book.d("write", f"{label[e]}: the game does not hold {e} (the ring of runes) now; left as it is")
    todo = [e for e in todo if e not in optional]
    if todo:
        book.e("write", f"{what}: the game does not hold the effect file(s) {', '.join(todo)} after {len(passes)} look(s)"
               + ": the game is still starting (use --wait), or it is not the version this was made for")
        return 1
    if cache is not None:                       # every copy and the colours it carries now: a later change of colour needs no look
        for eid, p in done.items():
            if eid in wfxr.effect_ids():
                cache.set_effect(eid, p.bases, colour, accent)
            elif eid in wfxr.eyes_ids():
                cache.set_effect(eid, p.bases, eyes, None)
            else:
                cache.set_effect(eid, p.bases, ring, None)
        _keep(cache, "colours")
    fire = [done[e] for e in wfxr.effect_ids() if e in done]
    if fire:
        second = f" and {_shown(accent)}" if accent is not None else ""
        book.ok("write", f"flame colour: the fire of Flame, Grant Me Strength is now {_shown(colour)}{second} in {len(fire)} "
                         f"effects ({sum(g.places for g in fire)} places written); it lasts until the game closes")
    rings = [done[e] for e in wfxr.ring_ids() if e in done]
    if rings:
        book.ok("write", f"ring colour: the ring of runes at the hand is now {_shown(ring)} ({sum(g.places for g in rings)} "
                         "places written); it lasts until the game closes")
    glow = [done[e] for e in wfxr.eyes_ids() if e in done]
    if glow:
        book.ok("write", f"eyes colour: the glowing eyes are now {_shown(eyes)} ({sum(g.places for g in glow)} places "
                         "written); it lasts until the game closes")
    return 0


def cmd_write_flame(args) -> int:
    """`write --flame-color [--wait [SEC] | --when-loaded]`: see the module text. The positive curse energy eyes get their colour in the same step."""
    require_windows_x64()
    when_loaded = bool(getattr(args, "when_loaded", False))
    wait = ATTACH_WAIT if when_loaded else float(getattr(args, "wait", 0) or 0)
    try:
        ci = extension.open_spells(ext_dir(args), spec_file(args))
        sel, note = ci.selection()
        if note:
            book.w("write", f"innovate-items spells: {note}")
        colour, cnote = ci.flame_color(sel)
        eyes, enote = ci.eyes_color(sel)
        accent, anote = ci.flame_accent_color(sel)
    except ExtensionError as exc:
        book.e("write", str(exc))
        return 1
    for n in (cnote, enote, anote):
        if n:
            book.w("write", n)
    if colour is None and eyes is None:
        book.i("write", "no spell of the design names a flame_color or a positive_curse_energy_eyes color: nothing to do")
        return 0
    target, code, record = _attach(args, wait)
    if target is None:
        return code
    if not _authorised(target, record):
        return EXIT_NO_SESSION
    mem = WritableProcessMemory(target.pid)
    book.d("write", "scan: " + (wscan.go_easy() or "ordinary priority"))
    try:
        gate = WriteGate()
        gate.open()   # only after the session and anti-cheat checks above
        if when_loaded:
            if not _wait_world(mem, target, "flame colour"):
                book.i("write", "flame colour: the game closed before a character was in the world; nothing was written")
                return 0
            return _put_flame(mem, gate, colour, LOOKS, eyes, accent, fresh=True, cache=_cache_of(args, target))
        return _put_flame(mem, gate, colour, LOOKS if wait > 0 else ONCE, eyes, accent, cache=_cache_of(args, target))
    finally:
        mem.close()


def ext_value(raw: str):
    """The value of `--set extension....=VALUE` as typed: a number, `null` (the game's own colour), or a text / a hex colour (quotes
    around it are taken off)."""
    t = raw.strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "'\"":
        return t[1:-1]
    if t.lower() in ("null", "none"):
        return None
    for kind in (int, float):
        try:
            return kind(t.replace("_", "")) if kind is int else kind(t)
        except ValueError:
            pass
    return t


def _write_extension(args, target: Target, mem, gate, snapshot, sets: list) -> tuple[int, int]:
    """`--set extension.innovate_items.spells.<goods id>.<path>=VALUE` (1.7.2): the values of the extension's spells in the running
    game (extension/external_scripts/backend.py). -> (written, refused)."""
    from ..extension.external_scripts.backend import ExtensionLive, Refused, extension_path
    vault_root = resolve_vault(args.vault)
    try:
        resolved = extension.open_spells(ext_dir(args, vault_root), spec_file(args)).resolved_path
    except ExtensionError as exc:
        book.e("write", str(exc))
        return 0, len(sets)
    live = ExtensionLive(mem, target, vault_root, resolved, gate=gate, snapshot=snapshot,
                         say=lambda level, msg: {"W": book.w, "E": book.e, "D": book.d}.get(level, book.i)("write", msg))
    ok = bad = 0
    for item in sets:
        name, _sep, raw = item.partition("=")
        goods, parts = extension_path(name)
        try:
            for what, value in live.apply(goods, parts, ext_value(raw)).items():
                book.ok("write", f"{name.strip()} = {value}  ({what})")
            ok += 1
        except Refused as exc:
            book.e("write", f"not applied: {exc}")
            bad += 1
    return ok, bad


def cmd_write(args) -> int:
    if getattr(args, "text", False):
        return cmd_write_text(args)
    if getattr(args, "flame_color", False):
        return cmd_write_flame(args)
    require_windows_x64()
    ext_sets = [s for s in (args.set or []) if s.strip().lower().startswith("extension.")]
    for item in ext_sets:
        name, sep, _raw = item.partition("=")
        if not sep or len(name.strip().split(".")) < 5 or name.strip().split(".")[:3] != ["extension", "innovate_items", "spells"]:
            book.e("write", f"--set {item!r}: expected extension.innovate_items.spells.<goods id>.<path>=VALUE")
            return 1
    try:
        policy = parse_policy([s for s in (args.set or []) if s not in ext_sets], args.refill, getattr(args, "reset", None))
    except ValueError as exc:   # unknown or unsettable name, bad value
        book.e("write", str(exc))
        return 1
    if policy.empty and not ext_sets:
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
        ext_ok, ext_bad = _write_extension(args, target, mem, gate, snapshot, ext_sets) if ext_sets else (0, 0)
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
    if ext_bad:
        return 1
    if writer.skipped or failed:
        for why in writer.skipped:
            book.e("write", f"not applied: {why}")
        if failed:
            book.e("write", f"failed or did not stick: {', '.join(failed)}")
        return 1
    if not results and not ext_ok:
        book.i("write", "values already match")
    return 0

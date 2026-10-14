"""The running game for edstdlib and for `read` / `write` of the `design` block (1.7.2): the one file of design/external_scripts
that touches the game (tests/test_architecture.py: EXCEPTIONS).

Nothing new touches the game here: the character is read by the Sampler of `read` and the document is the one `read --export` builds
(reader/export.py); values are written by the MemoryWriter of `write --set` (the same policy, gate and snapshot of the game's own values).
What this adds:

  * `DesignLive`: the block `design.innovate_items.spells.<goods id>` of the document (spells.resolved.json and what the game
    holds now) and the writes of its values (design/innovate_items/spells/live.py says what each name is in the game): a field of
    a row through the MemoryWriter; a text by rebuilding that one table at the pointer `write --text` switched; a colour by repainting
    the copies `write --flame-color` painted, from the colours they carry to the new ones. The last two use the memory cache
    (writer/cache.py) and never look through the memory unless the game reloaded what the cache knows;
  * `LiveBackend`: what edstdlib's `tools` talks to: the document, shared by every script for SHARE seconds, and the writes of a
    snapshot's changed values, one at a time, with the session checked again at most every RECHECK seconds (when it is no longer the
    one `run` started for this game, the gate closes for good).

Like the other engines it reports through a function it is given (`say(level, message)`), never the console or the log file."""
from __future__ import annotations

import copy
import json
import os
import threading
import time
from pathlib import Path

from ...game.eventflags import EventFlagError, EventFlags
from ...game.layout import Layout
from ...game.params import ParamError, ParamLockedError, ParamNameError
from ...game.paramtables import Tables
from ...game.processes import process_started
from ...game.profile import StateConfig, StateIds
from ...reader.export import build_document
from ...reader.sampler import Sampler
from ...vault import VaultError, authorise
from ...vault import session as vault_session
from ...writer import fxr as wfxr
from ...writer import text as wtext
from ...writer.cache import CACHE_NAME, MemoryCache
from ...writer.eventflags import FlagRefused, turn_off
from ...writer.paramedit import SNAPSHOT_NAME, Snapshot
from ...writer.writer import MemoryWriter, WritableProcessMemory, WriteGate, parse_policy, plan_params
from ..innovate_items.fmg import Fmg, FmgError
from ..innovate_items.spells import live
from ..innovate_items.spells.spec import colour_of, colour_text
from ..resurrect.great_enemies import TableError
from ..resurrect.great_enemies import load as load_enemies

SHARE = 0.05          # seconds a read of the game is shared by every script
RECHECK = 1.0         # seconds between two checks of the session while writing
TEXT_TABLES = {"goods_name": "GoodsName", "goods_info": "GoodsInfo", "goods_captions": "GoodsCaption"}


class Refused(Exception):
    """A write that was not made; the message says why."""


def write_values(mem, target, gate, snapshot, values: dict, say, tables=None) -> dict:
    """{name `write --set` takes: number} through the MemoryWriter -> {name: value} written. Refused when anything was not applied."""
    sets = [f"{k}={v!r}" if isinstance(v, float) else f"{k}={v}" for k, v in values.items()]
    try:
        policy = parse_policy(sets, None, [])
        policy, notes = plan_params(target.profile.params, policy, snapshot)
    except (ValueError, ParamLockedError, ParamNameError) as exc:
        raise Refused(str(exc)) from None
    for n in notes:
        say("D", n)
    writer = MemoryWriter(mem, Layout(mem, target.profile, target.base), policy, gate, log=lambda m: say("D", m), snapshot=snapshot,
                          tables=tables)
    results = writer.apply_once()
    try:
        snapshot.save()
    except OSError as exc:
        say("W", f"could not save {SNAPSHOT_NAME} ({exc})")
    failed = [r.name for r in results if not r.wrote]
    if writer.skipped or failed:
        raise Refused("; ".join(writer.skipped + [f"{n}: did not stick" for n in failed]))
    return {r.name: r.value for r in results if r.wrote}


# ---------------------------------------------------------------------------------------------------------------------------- the block
class DesignLive:
    """The `design` block of the document, and its writes. `mem` may be read-only for `block()`; `apply` needs the write handle
    and an open `gate`."""

    def __init__(self, mem, target, vault_root: Path | None, resolved_path: Path | None, *, gate=None, snapshot=None,
                 say=lambda level, msg: None):
        self.mem, self.target, self.vault_root, self.resolved_path = mem, target, vault_root, resolved_path
        self.gate, self.snapshot, self.say = gate, snapshot, say
        self.tables = None                     # the six tables, opened the first time a value of them is read
        self._files: dict = {}                 # path -> (stat key, what was read): a file is read again only when it changed

    def table_index(self):
        """The six tables with their row index, kept for this game process (None for a game version without params.catalog)."""
        if self.tables is None:
            try:
                self.tables = Tables(self.mem, self.target.profile, self.target.base)
            except (ParamError, AttributeError):
                return None
        return self.tables

    def _once(self, path: Path | None, read):
        """`read(path)`, again only when the file changed (its size or time); None when there is no file."""
        if path is None:
            return None
        try:
            st = os.stat(path)
        except OSError:
            self._files.pop(str(path), None)
            return None
        key = (st.st_mtime_ns, st.st_size)
        hit = self._files.get(str(path))
        if hit is None or hit[0] != key:
            hit = (key, read(path))
            self._files[str(path)] = hit
        return hit[1]

    def cache(self) -> MemoryCache | None:
        """The memory cache of this game process. A fresh object each time (the caller may change and save it); the file is read
        again only when another process (the text or colour step) changed it."""
        if self.vault_root is None:
            return None
        path = Path(self.vault_root) / CACHE_NAME
        known = self._once(path, lambda q: MemoryCache(q, self.target.pid, self.target.started).load())
        fresh = MemoryCache(path, self.target.pid, self.target.started)
        if known is not None:
            fresh.text, fresh.fxr = copy.deepcopy(known.text), copy.deepcopy(known.fxr)
        return fresh

    def spells(self) -> dict:
        """{goods id (text): the spell's record} of spells.resolved.json (read again only when a build changed it); empty without one."""
        def read(q):
            try:
                rec = json.loads(Path(q).read_text(encoding="utf-8"))
                spells = dict(rec.get("spells", {}))
                return spells, {g: live.reads(g, r) for g, r in spells.items()}
            except (OSError, ValueError, TypeError, AttributeError):
                return {}, {}
        got = self._once(self.resolved_path, read)
        return got[0] if got else {}

    def _reads(self, goods: str) -> dict:
        got = self._files.get(str(self.resolved_path))
        return got[1][1].get(goods, {}) if got else {}

    # ---- reading
    def block(self) -> dict | None:
        """{"innovate_items": {"spells": {goods id: node}}, "resurrect": {"great_enemies": {id: node}}} with the values the game
        holds now; a part without data is left out, None when both are."""
        out = {}
        spells = self._spells_block()
        if spells is not None:
            out["innovate_items"] = {"spells": spells}
        enemies = self.enemies_block()
        if enemies is not None:
            out["resurrect"] = {"great_enemies": enemies}
        return out or None

    # ---- the great enemies (1.8.0)
    def enemy_table(self):
        if not hasattr(self, "_enemies"):
            try:
                self._enemies = load_enemies()
            except TableError as exc:
                self.say("W", str(exc))
                self._enemies = None
        return self._enemies

    def event_flags(self) -> EventFlags | None:
        lay = getattr(self.target.profile, "event_flags", None)
        if lay is None:
            return None
        if getattr(self, "_flags", None) is None:
            self._flags = EventFlags(self.mem, self.target.base, lay)
        return self._flags

    def enemies_block(self) -> dict | None:
        """{id: {name, place, grace, runes, drop, story, dlc, defeated}}: the table with the defeat flag the game holds now (null when the
        game holds no save yet); None when this game version has no event_flags block or the table cannot be read."""
        table, flags = self.enemy_table(), self.event_flags()
        if table is None or flags is None:
            return None
        try:
            got = flags.get_many(table.defeated_flags().values())
        except EventFlagError:
            got = {}
        out = {}
        for rid, r in table.rows.items():
            out[str(rid)] = {"name": r["name"], "place": r.get("place"), "grace": (r.get("grace") or {}).get("name"), "runes": r["runes"],
                             "drop": list(r.get("drop") or []), "story": bool(r.get("story")), "dlc": bool(r.get("dlc")),
                             "defeated": got.get(r["flags"]["defeated"])}
        return out

    def apply_enemy(self, who: str, parts, value) -> dict:
        """`design.resurrect.great_enemies.<id or name>.defeated = false`: the boss comes back (spec 1.8.0 section 8). -> {name: value}
        written; Refused with the reason. `true` is refused: only the game marks a great enemy defeated."""
        table, flags = self.enemy_table(), self.event_flags()
        if table is None or flags is None:
            raise Refused("great enemies: this game version has no event_flags block in offsets.json, or the table cannot be read")
        if list(parts) != ["defeated"]:
            raise Refused(f"great enemies: only `defeated` can be written (`{'.'.join(parts)}` is the table's)")
        if value not in (False, "false", "False", 0):
            raise Refused("great enemies: only the game marks a great enemy defeated (write defeated = false to bring it back)")
        try:
            rids = table.one(str(who))
        except TableError as exc:
            raise Refused(f"great enemies: {exc}") from None
        if self.gate is None or not self.gate.allowed:
            raise Refused(f"writes are not allowed ({getattr(self.gate, 'reason', 'no session')})")
        try:
            done = {}
            for rid in rids:
                got = turn_off(self.mem, self.gate, flags, table.flags_of(rid), table.allowed())
                bad = [f"{f} ({how})" for f, how in got.items() if how == "did not stick"]
                if bad:
                    raise Refused(f"{table.rows[rid]['name']}: not resurrected: {', '.join(bad)}")
                done[f"design.resurrect.great_enemies.{rid}.defeated"] = False
            self.say("I", f"{table.rows[rids[0]]['name']} alive again: it appears once its area loads again (warp to another region, "
                          "then come back)")
            return done
        except (EventFlagError, FlagRefused) as exc:
            raise Refused(f"great enemies: {exc}") from None

    def _spells_block(self) -> dict | None:
        spells = self.spells()
        if not spells:
            return None
        cache, rows = self.cache(), {}
        out = {}
        for goods, rec in spells.items():
            n = copy.deepcopy(live.node(goods, rec))
            for path, name in self._reads(goods).items():
                v = self._param(name, rows)
                if v is not None:
                    live.put(n, list(path), v)
            if cache is not None:
                for field, text in cache.texts(int(goods)).items():
                    key = {v: k for k, v in live.TEXTS.items()}.get(field)
                    if key is not None:
                        live.put(n, ["customs", "advanced", "texts", key], text)
                self._colours(n, rec, cache)
            out[str(goods)] = n
        return out

    def _param(self, name: str, rows: dict):
        _p, table, rid, field = name.split(".", 3)
        key = (table, int(rid))
        if key not in rows:
            try:
                if self.table_index() is None:
                    raise ParamError("no params.catalog")
                rows[key] = self.tables.read_row(table, int(rid))
            except (ParamError, AttributeError):         # no params.catalog for this game version: the design's values are shown
                rows[key] = None
        row = rows[key]
        if row is None:
            return None
        hit = next((k for k in row if k.lower() == field.lower()), None)
        return row[hit] if hit is not None else None

    def _colours(self, n: dict, rec: dict, cache: MemoryCache) -> None:
        """The colours the copies carry now, when this game process painted them."""
        colors = n.get("customs", {}).get("advanced", {}).get("colors")
        if not isinstance(colors, dict):
            return
        fire = cache.effect(wfxr.effect_ids()[0])
        eyes = cache.effect(wfxr.eyes_ids()[0])
        for key, val in list(colors.items()):
            if key.startswith("Magic.") and fire is not None:
                main = colour_text(fire["main"]) if fire["main"] is not None else None
                acc = colour_text(fire["accent"]) if fire["accent"] is not None else None
                colors[key] = {"main": main, "accent": acc} if isinstance(val, dict) or acc is not None else main
            elif key.startswith("SpEffect.") and eyes is not None:
                colors[key] = colour_text(eyes["main"]) if eyes["main"] is not None else None

    # ---- writing
    def apply(self, goods: str, parts, value) -> dict:
        """Write one value of the block (the path below the spell `goods`). -> {name: value} written; Refused with the reason."""
        spells = self.spells()
        rec = spells.get(str(goods))
        if rec is None:                        # a spell is named by its label too: spells.reverse_cursed_technique
            goods = next((g for g, r in spells.items() if str(r.get("id", "")).lower() == str(goods).lower()), goods)
            rec = spells.get(str(goods))
        if rec is None:
            raise Refused(f"design.innovate_items.spells.{goods}: no such spell in the last build (it has: {', '.join(spells) or 'none'})")
        try:
            kind, *what = live.target(str(goods), rec, parts)
        except live.Locked as exc:
            raise Refused(str(exc)) from None
        if self.gate is None or not self.gate.allowed:
            raise Refused(f"writes are not allowed ({getattr(self.gate, 'reason', 'no session')})")
        if kind == "param":
            if isinstance(value, str):
                raise Refused(f"{what[0]}: a number is needed, not {value!r}")
            return write_values(self.mem, self.target, self.gate, self.snapshot, {what[0]: value}, self.say, self.table_index())
        if kind == "text":
            return self._text(int(what[0]), what[1], value)
        return self._colour(what[0], value)

    def _text(self, goods: int, field: str, text) -> dict:
        if not isinstance(text, str):
            raise Refused(f"{field}: a text is needed, not {text!r}")
        cache = self.cache()
        slot = (cache.text_slots() if cache is not None else {}).get(TEXT_TABLES[field])
        if slot is None:
            raise Refused(f"{field}: the text of this game was not set yet (`run` sets it once a character is in the world), so its "
                          "table is not known")
        table, why = wtext.read_table(self.mem, TEXT_TABLES[field], slot)
        if table is None:
            raise Refused(f"{field}: {why}")
        try:
            fmg = Fmg.read(table.data)
            if text:
                fmg.entries[goods] = text
            else:
                fmg.entries.pop(goods, None)
            wtext.swap(self.mem, self.gate, table, fmg.write())
        except (FmgError, wtext.TextError) as exc:
            raise Refused(f"{field}: {exc}") from None
        cache.set_text({}, {goods: {field: text}})
        self._save(cache)
        return {f"{TEXT_TABLES[field]}.{goods}": text}

    def _colour(self, which: str, value) -> dict:
        rgb = colour_of(value) if value is not None else None
        if value is not None and rgb is None:
            raise Refused(f"{value!r} is not a colour (\"#RRGGBB\", or [red, green, blue] from 0 to 2)")
        cache = self.cache()
        if cache is None:
            raise Refused("the vault is not known, so the copies of the effects are not either")
        plan = {"main": [(e, "main") for e in wfxr.effect_ids()],
                "accent": [(e, "accent") for e in wfxr.effect_ids()] + [(e, "main") for e in wfxr.ring_ids()],
                "eyes": [(e, "main") for e in wfxr.eyes_ids()]}[which]
        done = []
        for eid, part in plan:
            known = cache.effect(eid)
            if known is None:
                continue                       # this game process never painted it (or does not hold it): nothing to change
            before = {"main": known["main"], "accent": known["accent"]}
            after = dict(before, **{part: rgb})
            try:
                _n, bases = wfxr.repaint(self.mem, self.gate, eid, known["bases"], before, after)
            except wfxr.Stale:
                _n, bases = self._again(eid, after)
            except wfxr.FlameError as exc:
                raise Refused(str(exc)) from None
            cache.set_effect(eid, bases, after["main"], after["accent"])
            done.append(eid)
        if not done:
            raise Refused("the colours of this game were not painted yet (`run` paints them once a character is in the world)")
        self._save(cache)
        shown = colour_text(rgb) if rgb is not None else "the game's own"
        return {f"colour.{which}": shown}

    def _again(self, eid: str, after: dict) -> tuple[int, list]:
        """The game reloaded the file: its new copy has the game's own colours; look for it and paint it."""
        if after.get("main") is None:          # back to the game's own colours: a reloaded copy has them already
            return 0, []
        got, _found = wfxr.paint_many(self.mem, self.gate, [eid], {eid: after["main"]}, everything=True,
                                      accent=after.get("accent"), painted=False, required=[])
        p = got.get(eid)
        return (p.places, list(p.bases)) if p is not None else (0, [])

    def _save(self, cache: MemoryCache) -> None:
        try:
            cache.save()
        except OSError as exc:
            self.say("W", f"could not save {CACHE_NAME} ({exc})")


def with_spell_buffs(state_ids: StateIds, spells: dict) -> StateIds:
    """`state_ids` with the buffs of the design's spells named (their copied SpEffect rows, by the spell's label), so the document
    lists them under character.buffs like any buff the tool knows (they are in no chr_state_ids.json)."""
    extra = {}
    for goods, rec in spells.items():
        for sp in rec.get("rows", {}).get("sp_effect", ()):
            extra[int(sp)] = StateConfig(rec.get("id", str(goods)), "DESIGN", f"a buff of the design's spell {rec.get('id')} (goods {goods})")
    if not extra:
        return state_ids
    return StateIds({**extra, **state_ids.buffs}, state_ids.animations)


ENEMIES = ["design", "resurrect", "great_enemies"]


def enemy_path(name: str) -> tuple[str, list] | None:
    """`design.resurrect.great_enemies.<id or name>.<field>` -> (id or name, field parts); None for any other name."""
    parts = name.strip().split(".")
    if [p.lower() for p in parts[:3]] != ENEMIES or len(parts) < 5:
        return None
    return parts[3], parts[4:]


def design_path(name: str) -> tuple[str, list] | None:
    """`design.innovate_items.spells.<goods>.<path>` -> (goods, path parts); None for any other name."""
    parts = name.strip().split(".")
    if parts[:3] != ["design", "innovate_items", "spells"] or len(parts) < 5:
        return None
    return parts[3], parts[4:]


# ---------------------------------------------------------------------------------------------------------------------------- edstdlib's
def open_live(target, state_ids, vault_root: Path, resolved_path: Path | None, say) -> "LiveBackend":
    """The write handle on the game `target` and the backend on it. Only after the session check (the command does it)."""
    return LiveBackend(WritableProcessMemory(target.pid), target, state_ids, vault_root, resolved_path, say=say)


class LiveBackend:
    """What edstdlib's `tools` talks to. `mem`: the writable handle opened after the session check."""

    def __init__(self, mem, target, state_ids, vault_root: Path, resolved_path: Path | None = None, *,
                 say=lambda level, msg: None, clock=time.monotonic):
        self.mem, self.target, self.vault_root, self.say = mem, target, Path(vault_root), say
        self.sampler = Sampler(mem, target.profile, state_ids, target.base)
        self.gate = WriteGate()
        self.gate.open()                       # made only after the session check
        self.snapshot = Snapshot(self.vault_root / SNAPSHOT_NAME, target.pid, target.started)
        self.snapshot.load()
        self.design = DesignLive(mem, target, self.vault_root, resolved_path, gate=self.gate, snapshot=self.snapshot, say=say)
        self.sampler.state_ids = with_spell_buffs(state_ids, self.design.spells())
        self._clock = clock
        self._read_lock, self._write_lock = threading.Lock(), threading.Lock()
        self._doc, self._doc_at = None, -1e9
        self._checked_at = clock()

    def alive(self) -> bool:
        return bool(self.mem.alive())

    def log(self, level: str, msg: str) -> None:
        self.say(level, msg)

    def close(self) -> None:
        self.mem.close()

    def document(self) -> dict:
        """The document `read --export` writes, with the `design` block: one read, shared for SHARE seconds."""
        with self._read_lock:
            now = self._clock()
            if self._doc is not None and now - self._doc_at < SHARE:
                return self._doc
            s = self.sampler.sample()
            p = self.target.profile
            doc = build_document(state="CONNECTED" if s.state == "CONNECTED" else "IDLE", pid=self.target.pid,
                                 anti_cheat="DISABLED_OFFLINE", exe_sha256=self.target.sha256, profile_label=p.label,
                                 buffs_supported=p.sp_effect is not None, animations_supported=p.anim is not None, sample=s,
                                 mode="sandbox", read_only=False, sandbox=True)
            doc["design"] = self.design.block()
            self._doc, self._doc_at = doc, now
            return doc

    def _authorised(self) -> None:
        if not self.gate.allowed:
            raise Refused(f"writes are closed ({self.gate.reason})")
        now = self._clock()
        if now - self._checked_at < RECHECK:
            return
        self._checked_at = now
        try:
            record = vault_session.load(self.vault_root)
            problems = authorise(record, game_pid=self.target.pid, game_started=self.target.started,
                                 exe_sha256=self.target.sha256, started_of=process_started)
        except VaultError as exc:
            problems = [str(exc)]
        if problems:
            self.gate.close("; ".join(problems))
            raise Refused(f"writes are closed ({self.gate.reason})")

    def write(self, changes: dict) -> tuple[dict, list]:
        """{path in the document (a tuple of keys): value} -> ({name: value} written, [why each that was not])."""
        done, problems = {}, []
        with self._write_lock:
            try:
                self._authorised()
            except Refused as exc:
                return {}, [str(exc)]
            plain, colours = {}, {}
            for path, value in changes.items():
                name = ".".join(str(p) for p in path)
                if not path or path[0] == "systems":
                    problems.append(f"{name}: what the tool knows of itself, not a value of the game")
                elif path[0] == "design" and [str(p).lower() for p in path[:3]] == ENEMIES and len(path) >= 5:
                    try:
                        done.update(self.design.apply_enemy(str(path[3]), [str(p) for p in path[4:]], value))
                    except Refused as exc:
                        problems.append(str(exc))
                elif path[0] == "design":
                    ext = design_path(name) if len(path) >= 5 else None
                    if ext is None or list(path[:3]) != ["design", "innovate_items", "spells"]:
                        problems.append(f"{name}: not a value of the game")
                        continue
                    try:
                        got = self.design.apply(str(path[3]), list(path[4:]), value)
                    except Refused as exc:
                        problems.append(str(exc))
                        continue
                    done.update(got)
                    colours.setdefault(str(path[3]), []).extend(f"{k[len('colour.'):]} {v}" for k, v in got.items() if k.startswith("colour."))
                else:
                    plain[name] = value
            for name, value in plain.items():       # one at a time, so one refused value does not keep the others back
                try:
                    done.update(write_values(self.mem, self.target, self.gate, self.snapshot, {name: value}, self.say,
                                             self.design.table_index()))
                except Refused as exc:
                    problems.append(f"{name}: {exc}")
            with self._read_lock:                    # the next read sees what was just written
                self._doc = None
        for goods, shown in colours.items():         # one short info line per spell (the debug lines say where):
            if shown:                                # `reverse_cursed_technique colours: main #90D5FF, accent #FF909E`
                self.say("I", f"{self._label(goods)} colours: {', '.join(shown)}")
        return done, problems

    def _label(self, goods: str) -> str:
        """The spell's label (`reverse_cursed_technique`) for its goods id; what was typed when it is not known."""
        try:
            rec = self.design.spells().get(goods)
        except AttributeError:
            rec = None
        return str(rec.get("id", goods)) if isinstance(rec, dict) else goods

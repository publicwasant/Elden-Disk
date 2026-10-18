"""The running game for edstdlib and for `read` / `write` of the `creative` block (1.7.2; 1.8.0): the one file of creative/scripts
that touches the game (tests/test_architecture.py: EXCEPTIONS).

Nothing new touches the game here: the character is read by the Sampler of `read` and the document is the one `export` builds
(reader/export.py); values are written by the MemoryWriter of `write --set` (the same policy, gate and snapshot of the game's own values).
What this adds:

  * `CreativeLive`: the block `creative` of the document: `creative.scripts` (the host's status file), `creative.innovate_spells.<goods
    id>` (spells.resolved.json and what the game holds now), `creative.resurrect.great_enemies` (the defeated ones), and the writes of
    their values (creative/innovate_spells/live.py says what each name is in the game): a field of
    a row through the MemoryWriter; a text by rebuilding that one table at the pointer `innovate-spells apply` switched; a colour by repainting
    the copies `innovate-spells apply` painted, from the colours they carry to the new ones. The last two use the memory cache
    (writer/cache.py) and never look through the memory unless the game reloaded what the cache knows;
  * `LiveBackend`: what edstdlib's `tools` talks to: the document, shared by every script for SHARE seconds, and the writes of a
    snapshot's changed values, one at a time, with the session checked again at most every RECHECK seconds (when it is no longer the
    one `run` started for this game, the gate closes for good).

Like the other engines it reports through a function it is given (`say(level, message)`), never the console or the log file."""
from __future__ import annotations

import copy
import json
import struct
import os
import threading
import time
from pathlib import Path

from ...game.eventflags import EventFlagError, EventFlags
from ...game.layout import Layout
from ...game.params import ParamError, ParamLockedError, ParamNameError
from ...game.paramtables import Tables
from ...game.processes import process_started
from ...reader.export import build_document
from ...reader.sampler import Sampler
from ...vault import VaultError, authorise
from ...vault import session as vault_session
from ...writer import fxr as wfxr
from ...writer import text as wtext
from ...writer.cache import CACHE_NAME, MemoryCache
from ...writer.eventflags import FlagRefused, turn_off
from ...writer.inventoryedit import InventoryEditError, is_inventory_name, write_counts
from ...writer.paramedit import SNAPSHOT_NAME, Snapshot
from ...writer.writer import MemoryWriter, WritableProcessMemory, WriteGate, parse_policy, plan_params
from ..innovate_spells.fmg import Fmg, FmgError
from ..innovate_spells import live
from ..innovate_spells.spec import COLOR_KEY_RE, PLACE_RE, colour_effect, colour_of, colour_text, place_value
from ..resurrect.great_enemies import TableError
from ..resurrect.great_enemies import load as load_enemies

SHARE = 0.05          # seconds a read of the game is shared by every script
RECHECK = 1.0         # seconds between two checks of the session while writing
TEXT_TABLES = {"goods_name": "GoodsName", "goods_info": "GoodsInfo", "goods_captions": "GoodsCaption"}


class Refused(Exception):
    """A write that was not made; the message says why."""


def _index_of(tables) -> dict:
    """{table: {"rows": n}} of the game's tables, or {} when they cannot be read now."""
    if tables is None:
        return {}
    try:
        return tables.index()
    except ParamError:
        return {}


class LazyPart:
    """1.8.5 part 2: a part of the document the scripts share, built when a script first touches it, once for that document (the
    scripts that touch it within SHARE get the same), not at all while none does: the default scripts read the character only, and
    the tables (4.9 ms), the spells (3.3 ms) and the great enemies (3.3 ms) were 11 of the 12 ms of each read (2026-10-18 in the game).
    edstdlib's Node takes its value at the touch; `value()` is it for anything else."""
    _lazy_part = True

    def __init__(self, build):
        self._build, self._lock, self._done, self._value = build, threading.Lock(), False, None

    def value(self):
        with self._lock:
            if not self._done:
                self._value, self._done = self._build(), True
            return self._value

    def __deepcopy__(self, memo):
        return copy.deepcopy(self.value(), memo)

    def __repr__(self) -> str:
        return f"<built when touched{': ' + repr(self._value)[:60] if self._done else ''}>"


class LazyRows(dict):
    """A table of the game in a script's document (1.8.0 part 4): its rows are read from the game when one is touched
    (`x.params.NpcParam[10000000].hp`), not when the document is built: all the tables are hundreds of MB. `read_row(id)` and `ids()`
    are the backend's. A plain dict to everything else (edstdlib's Node, deepcopy keeps what was read)."""
    _lazy_rows = True

    def __init__(self, table: str, rows: int, read_row, ids, loaded=None):
        super().__init__(loaded or {})
        self.table, self.rows, self._read_row, self._ids, self._known, self._known_set = table, rows, read_row, ids, None, None

    def _all_ids(self) -> list[str]:
        if self._known is None:
            self._known = [str(i) for i in self._ids(self.table)]
            self._known_set = frozenset(self._known)      # 1.8.4 part 8: "is this a row" in one step, not a walk of every id
        return self._known

    def _has(self, k: str) -> bool:
        self._all_ids()
        return k in self._known_set

    def __missing__(self, key):
        k = str(key)
        if k != key and dict.__contains__(self, k):       # x[10000000] after x["10000000"]: the row already read
            return dict.__getitem__(self, k)
        if not k.isdigit() or not self._has(k):
            raise KeyError(k)
        row = self._read_row(self.table, int(k))
        dict.__setitem__(self, k, row)
        return row

    def __contains__(self, key) -> bool:
        return self._has(str(key))

    def __iter__(self):
        return iter(self._all_ids())

    def __len__(self) -> int:
        return len(self._all_ids())

    def keys(self):
        return list(self._all_ids())

    def items(self):
        return [(k, self[k]) for k in self._all_ids()]

    def values(self):
        return [self[k] for k in self._all_ids()]

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __deepcopy__(self, memo):
        import copy
        out = LazyRows(self.table, self.rows, self._read_row, self._ids, copy.deepcopy(dict(dict.items(self)), memo))     # the rows read so far, not every row
        out._known, out._known_set = self._known, self._known_set
        return out

    def __copy__(self):
        """The rows read so far, the same row objects (a script's snapshot copies a row when it touches it, 1.8.4 part 8); a plain
        copy.copy would walk every row of the table, reading each from the game."""
        out = LazyRows(self.table, self.rows, self._read_row, self._ids, dict(dict.items(self)))
        out._known, out._known_set = self._known, self._known_set
        return out


def write_values(mem, target, gate, snapshot, values: dict, say, tables=None) -> dict:
    """{name `write --set` takes: number} through the MemoryWriter -> {name: value} written. Refused when anything was not applied.
    A count of the inventory (1.8.1 part 2) goes through writer/inventoryedit.py."""
    inv = {k: v for k, v in values.items() if is_inventory_name(k)}
    values = {k: v for k, v in values.items() if k not in inv}
    done: dict = {}
    if inv:
        try:
            done = {r.name: r.value for r in write_counts(mem, target, gate, snapshot, [(k, str(v)) for k, v in inv.items()])
                    if r.wrote}
        except InventoryEditError as exc:
            raise Refused(str(exc)) from None
        if not values:
            try:
                snapshot.save()
            except OSError as exc:
                say("W", f"could not save {SNAPSHOT_NAME} ({exc})")
            return done
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
    return {**done, **{r.name: r.value for r in results if r.wrote}}


# ---------------------------------------------------------------------------------------------------------------------------- the block
def shown_place(now: bytes, own: bytes):
    """A colour place as the design writes it (1.8.3 part 2): "#RRGGBB" when a hex colour gives it (the place's own alpha, not brighter
    than its own colour), else [r, g, b, a]."""
    r, g, b, a = struct.unpack("<4f", now)
    o = struct.unpack("<4f", own)
    v = max(o[:3]) if max(o[:3]) > 0 else 1.0
    c = [x / v for x in (r, g, b)]
    if struct.pack("<f", a) == struct.pack("<f", o[3]) and max(c) <= 1.0 + 1e-6 and min(c) >= 0:
        return "#%02X%02X%02X" % tuple(round(min(1.0, x) * 255) for x in c)
    return [round(x, 4) for x in (r, g, b, a)]


class CreativeLive:
    """The `creative` block of the document, and its writes. `mem` may be read-only for `block()`; `apply` needs the write handle
    and an open `gate`."""

    def __init__(self, mem, target, vault_root: Path | None, resolved_path: Path | None, *, gate=None, snapshot=None,
                 say=lambda level, msg: None, status_path: Path | None = None):
        self.mem, self.target, self.vault_root, self.resolved_path = mem, target, vault_root, resolved_path
        self.status_path = status_path         # the scripts' host writes its status there (scripts_block)
        self.gate, self.snapshot, self.say = gate, snapshot, say
        self.tables = None                     # the game's tables, opened the first time a value of them is read
        self._files: dict = {}                 # path -> (stat key, what was read): a file is read again only when it changed

    def table_index(self):
        """The game's tables with their row index, kept for this game process (None for a game version without params)."""
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
    def block(self, times: dict | None = None) -> dict | None:
        """The `creative` block (spec 1.8.0 part 2): {"scripts": {host, defaults, added}, "innovate_spells": {goods id: node},
        "resurrect": {"great_enemies": {id: node of a defeated one}}} with what the game holds now; a part without data is left out,
        None when all are. `times` (1.8.5 part 2): gets the seconds each part took ("scripts", "spells", "enemies")."""
        out = {}
        t0 = time.perf_counter()
        scripts = self.scripts_block()
        if scripts is not None:
            out["scripts"] = scripts
        t1 = time.perf_counter()
        spells = self._spells_block()
        if spells is not None:
            out["innovate_spells"] = spells
        t2 = time.perf_counter()
        enemies = self.enemies_block()
        if enemies is not None:
            out["resurrect"] = {"great_enemies": enemies}
        if times is not None:
            times.update(scripts=t1 - t0, spells=t2 - t1, enemies=time.perf_counter() - t2)
        return out or None

    # ---- the scripts (1.8.0 part 2): what the host says of itself
    def scripts_block(self) -> dict | None:
        """{"host": {process_id, state, started, scripts} | None, "defaults": {NAME: ...}, "added": {NAME: ...}} from the host's status
        file; None when no host ever wrote one."""
        if self.status_path is None:
            return None
        def read(q):
            try:
                return json.loads(Path(q).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None
        st = self._once(self.status_path, read)
        if not isinstance(st, dict):
            return None
        from ...game.processes import process_alive
        from .host import block_of, host_running
        return block_of(st, host_running(st, process_alive))

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
        """{id: {name, place, grace, runes, drop, story, dlc, defeated: true}}: **the defeated great enemies only** (spec 1.8.0 part 2:
        the ones that can be brought back; `read creative.resurrect.great_enemies.*` gives their ids). {} when the game holds no save
        yet; None when this game version has no event_flags block or the table cannot be read."""
        table, flags = self.enemy_table(), self.event_flags()
        if table is None or flags is None:
            return None
        try:
            got = flags.get_many(table.defeated_flags().values())
        except EventFlagError:
            return {}
        out = {}
        for rid, r in table.rows.items():
            if got.get(r["flags"]["defeated"]) is True:
                out[str(rid)] = {"name": r["name"], "place": r.get("place"), "grace": (r.get("grace") or {}).get("name"),
                                 "runes": r["runes"], "drop": list(r.get("drop") or []), "story": bool(r.get("story")),
                                 "dlc": bool(r.get("dlc")), "defeated": True}
        return out

    def apply_enemy(self, who: str, parts, value) -> dict:
        """`creative.resurrect.great_enemies.<id or name>.defeated = false`: the boss comes back (spec 1.8.0). -> {name: value}
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
                done[f"creative.resurrect.great_enemies.{rid}.defeated"] = False
            from ..resurrect.great_enemies.table import resurrected
            self.say("I", resurrected(table.rows[rids[0]]))
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
                        live.put(n, ["design", "customs", "advanced", "texts", key], text)
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
        colors = n.get("design", {}).get("customs", {}).get("advanced", {}).get("colors")
        if not isinstance(colors, dict):
            return
        fire = cache.effect(wfxr.effect_ids()[0])
        eyes = cache.effect(wfxr.eyes_ids()[0])
        basic = {"set": n.get("design", {}).get("customs", {}).get("basic", {})}
        for key, val in list(colors.items()):
            if COLOR_KEY_RE.fullmatch(key) and isinstance(val, dict) and not ({"main", "accent"} & set(val)):
                colors[key] = self._places_now(key, val, basic, cache)       # 1.8.3 part 2: every place, as the game's copy has it
                continue
            two = fire if key.startswith("Magic.") else None
            if two is not None:
                main = colour_text(two["main"]) if two["main"] is not None else None
                acc = colour_text(two["accent"]) if two["accent"] is not None else None
                colors[key] = {"main": main, "accent": acc} if isinstance(val, dict) or acc is not None else main
            elif key.startswith("SpEffect.") and eyes is not None:
                colors[key] = colour_text(eyes["main"]) if eyes["main"] is not None else None

    def _places_now(self, key: str, val: dict, basic: dict, cache: MemoryCache) -> dict:
        """{place: [r, g, b, a]} of every colour place of the effect `key` points at, read from the copy the tool painted (the cache);
        the design's values when the game process never painted it."""
        fx = colour_effect(key, basic)
        known = cache.effect(str(fx)) if fx is not None and str(fx) in wfxr._ALL else None
        if not known or not known["bases"]:
            return val
        places = wfxr.places_of(str(fx))
        lo, hi = min(places), max(places) + 16
        block = self.mem.read(known["bases"][0] + lo, hi - lo)
        if block is None:
            return val
        return {"0x%x" % at: shown_place(block[at - lo:at - lo + 16], own) for at, (own, _bloom) in places.items()}

    # ---- writing
    def apply(self, goods: str, parts, value) -> dict:
        """Write one value of the block (the path below the spell `goods`). -> {name: value} written; Refused with the reason."""
        spells = self.spells()
        rec = spells.get(str(goods))
        if rec is None:                        # a spell is named by its label too: spells.reverse_cursed_technique
            goods = next((g for g, r in spells.items() if str(r.get("id", "")).lower() == str(goods).lower()), goods)
            rec = spells.get(str(goods))
        if rec is None:
            raise Refused(f"creative.innovate_spells.{goods}: no such spell in the last build (it has: {', '.join(spells) or 'none'})")
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
        if kind == "colours":
            return self._places(rec, what[0], what[1], value)
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

    def _places(self, rec: dict, key: str, place, value) -> dict:
        """1.8.3 part 2: write one colour place (`place`), or every place of the effect (`place` None; `value` an object {place: value}
        or None), of the effect `key` points at, at the copies `run` painted (the cache). A value: [r, g, b, a], "#RRGGBB", or None /
        `default` (the game's own)."""
        fx = colour_effect(key, {"set": rec.get("design", {}).get("customs", {}).get("basic", {})})
        if fx is None or str(fx) not in wfxr._ALL:
            raise Refused(f"colors.{key}: no effect with a colour plan (it paints {fx})")
        eid = str(fx)
        cache = self.cache()
        if cache is None:
            raise Refused("the vault is not known, so the copies of the effects are not either")
        known = cache.effect(eid)
        own = {at: b for at, (b, _bloom) in wfxr.places_of(eid).items()}
        now = {at: ((known or {}).get("places") or {}).get(at, own[at]) for at in own}

        def bytes_of(at: int, v) -> bytes:
            if isinstance(v, str) and v.strip().startswith("["):
                try:
                    v = json.loads(v)
                except ValueError:
                    pass
            if v is None:
                return own[at]
            pv = place_value(v)
            if pv is None:
                raise Refused(f"colors.{key}.0x{at:x}: {v!r} is not a colour ([r, g, b, a] from 0 to 100, or \"#RRGGBB\")")
            return wfxr.value_bytes(own[at], tuple(colour_of(pv)) if isinstance(pv, str) else tuple(pv))

        if place is not None:
            at = int(place, 16)
            if at not in own:
                raise Refused(f"colors.{key}.{place}: the effect {eid} has no colour at this place")
            want = {at: bytes_of(at, value)}
        else:
            if value is not None and not isinstance(value, dict):
                raise Refused(f"colors.{key}: an object {{place: colour}}, or default")
            given = {int(k, 16): v for k, v in (value or {}).items() if isinstance(k, str) and PLACE_RE.fullmatch(k)}
            bad = [f"0x{a:x}" for a in given if a not in own]
            if bad:
                raise Refused(f"colors.{key}: the effect {eid} has no colour at {', '.join(bad)}")
            want = {at: bytes_of(at, given.get(at)) for at in own}
        before = {at: now[at] for at in want}
        if known is None:
            raise Refused("the colours of this game were not painted yet (`run` paints them once a character is in the world)")
        try:
            _n, bases = wfxr.repaint_places(self.mem, self.gate, eid, known["bases"], before, want)
        except wfxr.Stale:
            full = {**now, **want}
            if all(full[at] == own[at] for at in own):
                # the game loaded the file again (a loading screen): it holds its own colours, which is what is asked; nothing to
                # look for (a look for "no change" has nothing to find: it was an error that ended the script, 2026-10-18). The copies
                # are kept: a copy loaded where it was holds the game's own, so the next paint finds it there (elsewhere: Stale, a look)
                bases = list(known["bases"])
            else:
                try:
                    got, _found = wfxr.paint_many(self.mem, self.gate, [eid], {eid: None}, everything=True, painted=False,
                                                  required=[], states={eid: [(at, own[at], full[at]) for at in own]})
                except wfxr.FlameError as exc:
                    raise Refused(str(exc)) from None
                p = got.get(eid)
                bases = list(p.bases) if p is not None else []
        except wfxr.FlameError as exc:
            raise Refused(str(exc)) from None
        places = {at: b for at, b in {**now, **want}.items() if b != own[at]}
        cache.set_effect(eid, bases, places=places)
        self._save(cache)
        if place is not None:
            shown = "the game's own" if want[int(place, 16)] == own[int(place, 16)] else \
                str([round(x, 4) for x in struct.unpack("<4f", want[int(place, 16)])])
            return {f"colour.{key}.{place}": shown}
        return {f"colour.{key}": f"{len(places)} of {len(own)} places the design's" if places else "the game's own"}

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


def spell_buffs(spells: dict) -> dict[int, int]:
    """{SpEffect id: goods id}: the copied SpEffect rows of the design's spells (1.8.2: listed under character.buffs with the spell's
    goods item of the inventory when the character holds it, like any buff an item gives)."""
    return {int(sp): int(goods) for goods, rec in spells.items() for sp in rec.get("rows", {}).get("sp_effect", ())}


ENEMIES = ["creative", "resurrect", "great_enemies"]
SPELLS = ["creative", "innovate_spells"]


def enemy_path(name: str) -> tuple[str, list] | None:
    """`creative.resurrect.great_enemies.<id or name>.<field>` -> (id or name, field parts); None for any other name."""
    parts = name.strip().split(".")
    if [p.lower() for p in parts[:3]] != ENEMIES or len(parts) < 5:
        return None
    return parts[3], parts[4:]


def spell_path(name: str) -> tuple[str, list] | None:
    """`creative.innovate_spells.<goods>.<path>` -> (goods, path parts); None for any other name."""
    parts = name.strip().split(".")
    if [p.lower() for p in parts[:2]] != SPELLS or len(parts) < 4:
        return None
    return parts[2], parts[3:]


# ---------------------------------------------------------------------------------------------------------------------------- edstdlib's
def open_live(target, state_ids, vault_root: Path, resolved_path: Path | None, say, status_path: Path | None = None) -> "LiveBackend":
    """The write handle on the game `target` and the backend on it. Only after the session check (the command does it)."""
    return LiveBackend(WritableProcessMemory(target.pid), target, state_ids, vault_root, resolved_path, say=say, status_path=status_path)


TIMES_EVERY = 60.0                   # 1.8.5 part 2: seconds between two lines of how long the reads of the game took
READ_PARTS = ("character", "scripts", "spells", "enemies", "tables")


class ReadTimes:
    """1.8.5 part 2: how long each part of the backend's read of the game took (the document the scripts share): one line in the
    log every TIMES_EVERY seconds, the reads counted, each part's mean and the slowest read, in milliseconds."""

    def __init__(self, at: float):
        self._reset(at)

    def _reset(self, at: float) -> None:
        self.at, self.n, self.sums, self.worst = at, 0, dict.fromkeys(READ_PARTS, 0.0), 0.0

    def add_part(self, part: str, seconds: float) -> None:
        """A part built when touched (LazyPart): its time counts in the minute's line, the read it belongs to already counted."""
        self.sums[part] = self.sums.get(part, 0.0) + seconds

    def add(self, parts: dict, now: float, say) -> None:
        self.n += 1
        for k in READ_PARTS:
            self.sums[k] += parts.get(k, 0.0)
        self.worst = max(self.worst, sum(parts.values()))
        if now - self.at >= TIMES_EVERY:
            say("D", self.line(now))
            self._reset(now)

    def line(self, now: float) -> str:
        def ms(v: float) -> str:
            return f"{v * 1000 / self.n:.1f}"
        return (f"{self.n} reads of the game in the last {now - self.at:.0f} s, {ms(sum(self.sums.values()))} ms each ("
                + ", ".join(f"{k} {ms(v)}" for k, v in self.sums.items()) + f"), the slowest {self.worst * 1000:.1f} ms")


class LiveBackend:
    """What edstdlib's `tools` talks to. `mem`: the writable handle opened after the session check."""
    game_closed = False                 # 1.8.5: the host sets it when the game has closed (the scripts' teardowns write nothing then)
    _said_closed = False

    def __init__(self, mem, target, state_ids, vault_root: Path, resolved_path: Path | None = None, *,
                 say=lambda level, msg: None, clock=time.monotonic, status_path: Path | None = None, timer=time.perf_counter):
        self.mem, self.target, self.vault_root, self.say = mem, target, Path(vault_root), say
        self._timer = timer
        self.times = ReadTimes(clock())
        self.sampler = Sampler(mem, target.profile, state_ids, target.base)
        self.sampler.game = (target.pid, target.started)          # the array of the text tables is remembered for this game
        self.gate = WriteGate()
        self.gate.open()                       # made only after the session check
        self.snapshot = Snapshot(self.vault_root / SNAPSHOT_NAME, target.pid, target.started)
        self.snapshot.load()
        self.creative = CreativeLive(mem, target, self.vault_root, resolved_path, gate=self.gate, snapshot=self.snapshot, say=say,
                                     status_path=status_path)
        self.sampler.spell_buffs = spell_buffs(self.creative.spells())
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
        """The document `export` writes, with the `creative` block: one read, shared for SHARE seconds."""
        with self._read_lock:
            now = self._clock()
            if self._doc is not None and now - self._doc_at < SHARE:
                return self._doc
            t0 = self._timer()
            s = self.sampler.sample()
            p = self.target.profile
            doc = build_document(state="CONNECTED" if s.state == "CONNECTED" else "IDLE", pid=self.target.pid,
                                 anti_cheat="DISABLED_OFFLINE", exe_sha256=self.target.sha256, profile_label=p.label,
                                 buffs_supported=p.sp_effect is not None, animations_supported=p.anim is not None, sample=s,
                                 mode="creative", read_only=False, creative=True)
            times = {"character": self._timer() - t0}
            t1 = self._timer()
            doc["creative"] = self._creative_part()
            times["scripts"] = self._timer() - t1
            tables = self.creative.table_index()
            if tables is not None:   # every table of the game, its rows read when touched (not disk.json's: the scripts' own, 1.8.0 part 4)
                def params(tables=tables):
                    return {t: LazyRows(t, v["rows"], tables.read_row, tables.ids) for t, v in _index_of(tables).items()}
                doc = {**{k: v for k, v in doc.items() if k != "creative"}, "params": self._timed("tables", params),
                       "creative": doc.get("creative")}
            self.times.add(times, now, self.say)
            self._doc, self._doc_at = doc, now
            return doc

    def _timed(self, part: str, build) -> LazyPart:
        def run():
            with self._read_lock:              # one read of the game at a time, as the document's own (the caches are not shared safely)
                t = self._timer()
                try:
                    return build()
                finally:
                    self.times.add_part(part, self._timer() - t)
        return LazyPart(run)

    def _creative_part(self) -> dict | None:
        """The `creative` block (CreativeLive.block's parts), the spells and the great enemies built when touched (1.8.5 part 2)."""
        c = self.creative
        out = {}
        scripts = c.scripts_block()
        if scripts is not None:
            out["scripts"] = scripts
        if c.spells():
            out["innovate_spells"] = self._timed("spells", c._spells_block)
        if c.enemy_table() is not None and c.event_flags() is not None:
            def enemies():
                got = c.enemies_block()
                return None if got is None else {"great_enemies": got}
            out["resurrect"] = self._timed("enemies", enemies)
        return out or None

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
        if self.game_closed:                # 1.8.5: the game closed (the host says so): nothing to put back in it, nothing refused
            if not self._said_closed:
                self._said_closed = True
                self.say("D", "the game closed: the scripts' last writes are not made (its memory is going away)")
            return {}, []
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
                elif path[0] == "creative" and [str(p).lower() for p in path[:3]] == ENEMIES and len(path) >= 5:
                    try:
                        done.update(self.creative.apply_enemy(str(path[3]), [str(p) for p in path[4:]], value))
                    except Refused as exc:
                        problems.append(str(exc))
                elif path[0] == "creative":
                    if [str(p).lower() for p in path[:2]] != SPELLS or len(path) < 4:
                        problems.append(f"{name}: not a value of the game")
                        continue
                    try:
                        got = self.creative.apply(str(path[2]), [str(p) for p in path[3:]], value)
                    except Refused as exc:
                        problems.append(str(exc))
                        continue
                    done.update(got)
                    colours.setdefault(str(path[2]), []).extend(f"{k[len('colour.'):]} {v}" for k, v in got.items() if k.startswith("colour."))
                else:
                    plain[name] = value
            for name, value in plain.items():       # one at a time, so one refused value does not keep the others back
                try:
                    done.update(write_values(self.mem, self.target, self.gate, self.snapshot, {name: value}, self.say,
                                             self.creative.table_index()))
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
            rec = self.creative.spells().get(goods)
        except AttributeError:
            rec = None
        return str(rec.get("id", goods)) if isinstance(rec, dict) else goods

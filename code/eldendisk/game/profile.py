"""Loads offsets.json (per exe version) and chr_state_ids.json (buff and animation ID tables)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .paramlayouts import LAYOUTS

TIMER_MODES = {"elapsed", "remaining"}


class Incomplete(ValueError):
    pass


def _num(value, name: str) -> int:
    if value is None or isinstance(value, bool) or (isinstance(value, str) and not str(value).strip()):
        raise Incomplete(f"{name} is not set")
    if isinstance(value, int):
        n = value
    else:
        try:
            n = int(str(value), 0)
        except ValueError:
            raise Incomplete(f"{name}: not a number: {value!r}") from None
    if n < 0:
        raise Incomplete(f"{name}: negative")
    return n


@dataclass(frozen=True)
class EntryLayout:
    id: int
    next: int
    duration: int
    timer: int
    timer_mode: str


@dataclass(frozen=True)
class SpEffectLayout:
    player_to_sp_effect: int
    head: int
    entry: EntryLayout


@dataclass(frozen=True)
class AnimLayout:
    player_to_modules: int
    modules_to_time_act: int
    time_act_read_idx: int
    time_act_queue: int
    queue_entry_size: int


@dataclass(frozen=True)
class VitalsLayout:
    player_to_modules: int
    modules_to_data: int
    data_to_vitals: int


@dataclass(frozen=True)
class AtGraceConfig:
    source: str
    equals: tuple[int, ...]


PARAM_TYPES = {"f32": "<f", "s32": "<i"}
_ROW_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_ROW_ID = re.compile(r"^(0|[1-9][0-9]*)$")


@dataclass(frozen=True)
class ParamFileLayout:
    """How a param file looks in memory (measured on 1.17.1, see docs/experiments/params)."""
    row_count: int              # u16 at head + this
    data_start: int             # u64 at head + this; must equal descriptors + row_count * descriptor_size
    descriptors: int            # where the row descriptor table starts
    descriptor_size: int
    descriptor_id: int          # u32 row id inside a descriptor
    descriptor_data_offset: int  # u64 offset of the row data (from head) inside a descriptor


@dataclass(frozen=True)
class ParamChain:
    """[...[[base + rva] + o1] + o2 ...] + oN is the param file head (every step reads an 8-byte pointer)."""
    rva: int
    offsets: tuple[int, ...]


@dataclass(frozen=True)
class ParamField:
    name: str
    offset: int
    type: str                   # f32 | s32
    writable: bool
    min: float | int | None = None
    max: float | int | None = None


@dataclass(frozen=True)
class ParamRow:
    id: int
    name: str                   # for people (`"name"` in the document); not read from the game
    defaults: dict              # writable field -> the game's own value (what `write --reset` puts back)

    @property
    def key(self) -> str:       # a row is addressed by its id: `params.<table>.<id>.<field>`
        return str(self.id)


@dataclass(frozen=True)
class ParamTable:
    key: str                    # the name in disk-state.json (`params.<key>.<id>.<field>`)
    table: str                  # the game's name of the param (SpEffectParam)
    row_size: int
    chains: tuple[ParamChain, ...]
    fields: dict[str, ParamField]
    rows: dict[str, ParamRow]   # by str(id)


@dataclass(frozen=True)
class ParamsProfile:
    layout: ParamFileLayout
    tables: dict[str, ParamTable]
    catalog: dict[str, ParamChain] = field(default_factory=dict)   # table name (paramlayouts.LAYOUTS) -> chain to its file


@dataclass(frozen=True)
class EquipmentLayout:
    """Where PlayerGameData keeps the equipment (1.7.2; measured on 1.17.1, read-only, with the game running): the spells memorised in the
    magic slots ([PlayerGameData + game_data_to_magic] + magic_slots + n * magic_slot_size: the Magic id, -1 for an empty slot) and the
    slot that is selected (a 32-bit number at magic_selected, 0 = the first slot)."""
    game_data_to_magic: int
    magic_slots: int
    magic_slot_size: int
    magic_slot_count: int
    magic_selected: int


@dataclass(frozen=True)
class TextProfile:
    """The text tables `write --text` changes (measured on 1.17.1, tools/probe_text.py; writer/text.py says how they are found). `files`:
    table name -> the number of its text file (the pointer to the table sits at `array + number * 8`). `sizes`: table name -> the size of
    the game's own file of that table, in bytes, in the language the game is played in."""
    files: dict[str, int]
    sizes: dict[str, int]


@dataclass(frozen=True)
class Profile:
    sha256: str
    label: str
    world_chr_man_rva: int
    world_chr_man_to_player: int
    player_to_game_data: int
    level: int
    runes: int
    attributes: int
    sp_effect: SpEffectLayout | None  # None -> buffs unsupported (stats still work)
    anim: AnimLayout | None = None
    vitals: VitalsLayout | None = None
    at_grace: AtGraceConfig | None = None
    buffs_note: str | None = None
    params: ParamsProfile | None = None   # None -> params unsupported for this exe
    text: TextProfile | None = None       # None -> `write --text` unsupported for this exe
    equipment: EquipmentLayout | None = None   # None -> character.equipment is not read for this exe


def _parse_sp_effect(d: dict) -> tuple[SpEffectLayout | None, str | None]:
    try:
        sp = d.get("sp_effect") or {}
        e = sp.get("entry") or {}
        mode = e.get("timer_mode")
        if mode not in TIMER_MODES:
            raise Incomplete(f"sp_effect.entry.timer_mode must be one of {sorted(TIMER_MODES)}, got {mode!r}")
        layout = SpEffectLayout(
            player_to_sp_effect=_num(d.get("player_to_sp_effect"), "player_to_sp_effect"),
            head=_num(sp.get("head"), "sp_effect.head"),
            entry=EntryLayout(
                id=_num(e.get("id"), "sp_effect.entry.id"),
                next=_num(e.get("next"), "sp_effect.entry.next"),
                duration=_num(e.get("duration"), "sp_effect.entry.duration"),
                timer=_num(e.get("timer"), "sp_effect.entry.timer"),
                timer_mode=mode,
            ),
        )
        return layout, None
    except Incomplete as exc:
        return None, f"buffs disabled: {exc}"


def _parse_anim(d: dict) -> AnimLayout | None:
    anim = d.get("anim") or d.get("animation")
    if not isinstance(anim, dict):
        return None
    try:
        if "player_to_modules" in anim:
            return AnimLayout(
                player_to_modules=_num(anim.get("player_to_modules"), "anim.player_to_modules"),
                modules_to_time_act=_num(anim.get("modules_to_time_act"), "anim.modules_to_time_act"),
                time_act_read_idx=_num(anim.get("time_act_read_idx"), "anim.time_act_read_idx"),
                time_act_queue=_num(anim.get("time_act_queue"), "anim.time_act_queue"),
                queue_entry_size=_num(anim.get("queue_entry_size"), "anim.queue_entry_size"),
            )
        elif "player_to_anim_module" in anim:
            mod = _num(anim.get("player_to_anim_module"), "animation.player_to_anim_module")
            raw_offsets = anim.get("offsets") or []
            offsets = tuple(_num(o, f"animation.offsets[{i}]") for i, o in enumerate(raw_offsets))
            return AnimLayout(
                player_to_modules=mod,
                modules_to_time_act=offsets[0] if len(offsets) > 0 else 0x18,
                time_act_read_idx=0xC4,
                time_act_queue=offsets[1] if len(offsets) > 1 else 0x20,
                queue_entry_size=0x10,
            )
        return None
    except Incomplete:
        return None


def _parse_vitals(d: dict) -> VitalsLayout:
    """Required: a profile is pinned to one exe, so offsets are never borrowed from another version."""
    vit = d.get("vitals")
    if not isinstance(vit, dict):
        raise Incomplete("vitals is not set (add a 'vitals' block, see docs/adding-a-profile.md)")
    return VitalsLayout(
        player_to_modules=_num(vit.get("player_to_modules"), "vitals.player_to_modules"),
        modules_to_data=_num(vit.get("modules_to_data"), "vitals.modules_to_data"),
        data_to_vitals=_num(vit.get("data_to_vitals"), "vitals.data_to_vitals"),
    )


def _parse_at_grace(d: dict) -> AtGraceConfig | None:
    ag = d.get("at_grace")
    if ag is None:
        return None  # feature off: at-grace is never detected, so the baseline never re-locks at a Grace
    if not isinstance(ag, dict):
        raise Incomplete("at_grace must be an object {source, equals} or null")
    eq_raw = ag.get("equals")
    if eq_raw is None or eq_raw == []:
        raise Incomplete("at_grace.equals is not set")
    items = eq_raw if isinstance(eq_raw, list) else [eq_raw]
    return AtGraceConfig(source=str(ag.get("source", "anim")),
                         equals=tuple(_num(v, "at_grace.equals") for v in items))


def _number(value, name: str, lo=None, hi=None) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Incomplete(f"{name}: not a number: {value!r}")
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        raise Incomplete(f"{name}: {value} outside {lo}..{hi}")
    return value


def _parse_catalog(raw) -> dict[str, ParamChain]:
    """`params.catalog`: one chain per table of paramlayouts.LAYOUTS, found with `read --probe-params`. Absent = none."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise Incomplete("params.catalog must be an object")
    out: dict[str, ParamChain] = {}
    for name, c in raw.items():
        where = f"params.catalog.{name}"
        if name not in LAYOUTS:
            raise Incomplete(f"{where}: not a table of the workbench (one of {', '.join(LAYOUTS)})")
        if not isinstance(c, dict) or not c.get("offsets"):
            raise Incomplete(f"{where} must be {{rva, offsets}} with at least one offset")
        out[name] = ParamChain(_num(c.get("rva"), f"{where}.rva"), tuple(_num(o, f"{where}.offsets") for o in c["offsets"]))
    return out


def _parse_text(d: dict) -> TextProfile | None:
    """Absent block -> None (text unsupported). A block that is there must be complete."""
    t = d.get("text")
    if t is None:
        return None
    if not isinstance(t, dict):
        raise Incomplete("text must be an object")
    files, sizes = t.get("files"), t.get("sizes")
    if not isinstance(files, dict) or not files:
        raise Incomplete("text.files must be an object: table name -> text file number")
    if not isinstance(sizes, dict) or set(sizes) != set(files):
        raise Incomplete("text.sizes must be an object: the same table names -> the size of the game's own file in bytes")
    return TextProfile({str(n): _number(v, f"text.files.{n}", 0, 255) for n, v in files.items()},
                       {str(n): _number(v, f"text.sizes.{n}", 0x28, 64 * 1024 * 1024) for n, v in sizes.items()})


def _parse_equipment(d: dict) -> EquipmentLayout | None:
    """Absent block -> None (no character.equipment). A block that is there must be complete."""
    e = d.get("equipment")
    if e is None:
        return None
    if not isinstance(e, dict):
        raise Incomplete("equipment must be an object")
    lay = EquipmentLayout(**{k: _num(e.get(k), f"equipment.{k}") for k in (
        "game_data_to_magic", "magic_slots", "magic_slot_size", "magic_slot_count", "magic_selected")})
    if lay.magic_slot_size < 4 or not 1 <= lay.magic_slot_count <= 64:
        raise Incomplete("equipment: magic_slot_size must be at least 4 and magic_slot_count 1 to 64")
    return lay


def _parse_params(d: dict) -> ParamsProfile | None:
    """Absent block -> None (params unsupported). A block that is there must be complete and consistent."""
    pr = d.get("params")
    if pr is None:
        return None
    if not isinstance(pr, dict):
        raise Incomplete("params must be an object")
    fl = pr.get("file_layout") or {}
    layout = ParamFileLayout(**{k: _num(fl.get(k), f"params.file_layout.{k}") for k in (
        "row_count", "data_start", "descriptors", "descriptor_size", "descriptor_id", "descriptor_data_offset")})
    if layout.descriptor_size < max(layout.descriptor_id + 4, layout.descriptor_data_offset + 8):
        raise Incomplete("params.file_layout: descriptor_size is too small for the id and the data offset")
    tables: dict[str, ParamTable] = {}
    for key, raw in (pr.get("tables") or {}).items():
        where = f"params.tables.{key}"
        if not isinstance(raw, dict):
            raise Incomplete(f"{where} must be an object")
        if not _ROW_NAME.match(str(key)):
            raise Incomplete(f"{where}: the name must be lower-case letters, digits and _")
        row_size = _num(raw.get("row_size"), f"{where}.row_size")
        if row_size <= 0:
            raise Incomplete(f"{where}.row_size must be positive")
        chains = []
        for i, c in enumerate(raw.get("head_chains") or []):
            chains.append(ParamChain(_num(c.get("rva"), f"{where}.head_chains[{i}].rva"),
                                     tuple(_num(o, f"{where}.head_chains[{i}].offsets") for o in c.get("offsets") or [])))
        if not chains:
            raise Incomplete(f"{where}.head_chains is empty")
        fields: dict[str, ParamField] = {}
        for fname, f in (raw.get("fields") or {}).items():
            if str(fname).lower() == "name":
                raise Incomplete(f"{where}.fields.name: `name` is the row's own text in the document, pick another field name")
            ftype = f.get("type")
            if ftype not in PARAM_TYPES:
                raise Incomplete(f"{where}.fields.{fname}.type must be one of {sorted(PARAM_TYPES)}, got {ftype!r}")
            offset = _num(f.get("offset"), f"{where}.fields.{fname}.offset")
            if offset + 4 > row_size:
                raise Incomplete(f"{where}.fields.{fname}: offset 0x{offset:X} is outside a row of {row_size} bytes")
            writable = f.get("writable", False)
            if not isinstance(writable, bool):
                raise Incomplete(f"{where}.fields.{fname}.writable must be true or false")
            lo = _number(f["min"], f"{where}.fields.{fname}.min") if "min" in f else None
            hi = _number(f["max"], f"{where}.fields.{fname}.max") if "max" in f else None
            if writable and (lo is None or hi is None or lo > hi):
                raise Incomplete(f"{where}.fields.{fname}: a writable field needs min and max (min <= max)")
            fields[fname] = ParamField(fname, offset, ftype, writable, lo, hi)
        if not fields:
            raise Incomplete(f"{where}.fields is empty")
        if len({f.name.lower() for f in fields.values()}) != len(fields):
            raise Incomplete(f"{where}.fields: two names differ only in letter case")
        rows: dict[str, ParamRow] = {}
        for rkey, r in (raw.get("rows") or {}).items():
            if not _ROW_ID.match(str(rkey)):
                raise Incomplete(f"{where}.rows.{rkey}: a row is named by its id (digits only, no leading zero)")
            rname = r.get("name")
            if not isinstance(rname, str) or not rname.strip():
                raise Incomplete(f"{where}.rows.{rkey}.name must be a text")
            defaults = r.get("defaults") or {}
            for fname, f in fields.items():
                if f.writable:
                    if fname not in defaults:
                        raise Incomplete(f"{where}.rows.{rkey}.defaults.{fname} is not set (needed by --reset)")
                    _number(defaults[fname], f"{where}.rows.{rkey}.defaults.{fname}", f.min, f.max)
            extra = set(defaults) - {n for n, f in fields.items() if f.writable}
            if extra:
                raise Incomplete(f"{where}.rows.{rkey}.defaults: not a writable field: {', '.join(sorted(extra))}")
            rows[str(rkey)] = ParamRow(int(rkey), rname, dict(defaults))
        if not rows:
            raise Incomplete(f"{where}.rows is empty")
        tables[key] = ParamTable(key, str(raw.get("table") or key), row_size, tuple(chains), fields, rows)
    if not tables:
        raise Incomplete("params.tables is empty")
    return ParamsProfile(layout, tables, _parse_catalog(pr.get("catalog")))


def load_profile(path: Path, exe_sha256: str) -> tuple[Profile | None, str | None]:
    """Returns (profile, None) or (None, reason)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"cannot read {path}: {exc}"
    profiles = {str(k).lower(): v for k, v in (data.get("profiles") or {}).items()}
    raw = profiles.get(exe_sha256.lower())
    if raw is None:
        return None, f"no profile for exe sha256 {exe_sha256}"
    try:
        gd = raw.get("game_data") or {}
        sp, note = _parse_sp_effect(raw)
        anim = _parse_anim(raw)
        vitals = _parse_vitals(raw)
        at_grace = _parse_at_grace(raw)
        params = _parse_params(raw)
        text = _parse_text(raw)
        equipment = _parse_equipment(raw)
        return Profile(
            sha256=exe_sha256.lower(),
            label=str(raw.get("label") or exe_sha256[:12]),
            world_chr_man_rva=_num(raw.get("world_chr_man_rva"), "world_chr_man_rva"),
            world_chr_man_to_player=_num(raw.get("world_chr_man_to_player"), "world_chr_man_to_player"),
            player_to_game_data=_num(raw.get("player_to_game_data"), "player_to_game_data"),
            level=_num(gd.get("level"), "game_data.level"),
            runes=_num(gd.get("runes"), "game_data.runes"),
            attributes=_num(gd.get("attributes"), "game_data.attributes"),
            sp_effect=sp,
            anim=anim,
            vitals=vitals,
            at_grace=at_grace,
            buffs_note=note,
            params=params,
            text=text,
            equipment=equipment,
        ), None
    except Incomplete as exc:
        return None, f"profile incomplete: {exc}"


@dataclass(frozen=True)
class StateConfig:
    """What the tool knows about one buff or one animation id (the entry of `chr_state_ids.json`)."""
    name: str
    categories: str | None = None
    abilities: str | None = None


@dataclass(frozen=True)
class StateIds:
    """`chr_state_ids.json`: the names of buff ids and of animation ids (two tables; the same number may be in both)."""
    buffs: dict[int, StateConfig]
    animations: dict[int, StateConfig]


def _state_table(data, kind: str, where: Path) -> dict[int, StateConfig]:
    if not isinstance(data, dict):
        raise ValueError(f"malformed {where}: {kind!r} must be an object {{id: {{name, ...}}}}")
    table: dict[int, StateConfig] = {}
    for k, v in data.items():
        if str(k).startswith("_"):
            continue
        if not isinstance(v, dict) or "name" not in v:
            raise ValueError(f"malformed {kind} item {k}: missing name")
        cat, ab = v.get("categories"), v.get("abilities")
        table[int(k)] = StateConfig(str(v["name"]), str(cat) if cat is not None else None,
                                    str(ab) if ab is not None else None)
    return table


def load_state_ids(path: Path) -> StateIds:
    """A missing file means empty tables. Malformed content raises ValueError."""
    p = Path(path)
    if not p.exists():
        return StateIds({}, {})
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not ({"buffs", "animations"} & set(data)):
            raise ValueError('expected an object with "buffs" and "animations" (an old flat file? '
                             'python tools/convert_state_ids.py FILE converts it)')
        return StateIds(_state_table(data.get("buffs", {}), "buffs", p),
                        _state_table(data.get("animations", {}), "animations", p))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"malformed {p}: {exc!r}") from exc

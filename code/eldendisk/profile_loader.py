"""Loads offsets.json (per exe version) and effects.json (SpEffect ID tables)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

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
class AtGraceConfig:
    source: str
    equals: tuple[int, ...]


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
    at_grace: AtGraceConfig | None = None
    buffs_note: str | None = None


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


def _parse_at_grace(d: dict) -> AtGraceConfig | None:
    ag = d.get("at_grace")
    if isinstance(ag, dict):
        src = str(ag.get("source", "anim"))
        eq_raw = ag.get("equals") or [68011]
        if isinstance(eq_raw, list):
            eq = tuple(_num(v, "at_grace.equals") for v in eq_raw)
        else:
            eq = (_num(eq_raw, "at_grace.equals"),)
        return AtGraceConfig(source=src, equals=eq)
    elif ag is not None:
        return AtGraceConfig(source="anim", equals=(68011,))
    return None


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
        at_grace = _parse_at_grace(raw)
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
            at_grace=at_grace,
            buffs_note=note,
        ), None
    except Incomplete as exc:
        return None, f"profile incomplete: {exc}"


@dataclass(frozen=True)
class EffectConfig:
    name: str
    category: str | None = None
    ability: str | None = None


@dataclass(frozen=True)
class Effects:
    table: dict[int, EffectConfig]


def load_effects(path: Path) -> Effects:
    """A missing file means empty tables. Malformed content raises ValueError."""
    p = Path(path)
    if not p.exists():
        return Effects({})
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"malformed {p}: expected JSON object")
        table: dict[int, EffectConfig] = {}
        for k, v in data.items():
            if str(k).startswith("_"):
                continue
            if not isinstance(v, dict) or "name" not in v:
                raise ValueError(f"malformed effect item {k}: missing name")
            table[int(k)] = EffectConfig(
                name=str(v["name"]),
                category=str(v["category"]) if v.get("category") is not None else None,
                ability=str(v["ability"]) if v.get("ability") is not None else None,
            )
        return Effects(table)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"malformed {p}: {exc!r}") from exc

"""Loads offsets.json (per exe version) and effects.json (SpEffect ID tables)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

TIMER_MODES = {"elapsed", "remaining"}


class Incomplete(ValueError):
    pass


def _num(value, name: str) -> int:
    if value is None or isinstance(value, bool) or (isinstance(value, str) and not value.strip()):
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
class AnimationLayout:
    player_to_anim_module: int
    offsets: tuple[int, ...]
    grace_anim_id: int


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
    animation: AnimationLayout | None = None
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


def _parse_animation(d: dict) -> AnimationLayout | None:
    anim = d.get("animation")
    if not isinstance(anim, dict):
        return None
    try:
        mod = _num(anim.get("player_to_anim_module"), "animation.player_to_anim_module")
        raw_offsets = anim.get("offsets")
        if not isinstance(raw_offsets, list) or not raw_offsets:
            return None
        offsets = tuple(_num(o, f"animation.offsets[{i}]") for i, o in enumerate(raw_offsets))
        grace_id = int(anim.get("grace_anim_id", 68011))
        return AnimationLayout(player_to_anim_module=mod, offsets=offsets, grace_anim_id=grace_id)
    except Incomplete:
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
        anim = _parse_animation(raw)
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
            animation=anim,
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

"""Sampling: pointer chain -> validated snapshot (a character dict).

Rule: one failed check discards the whole sample (correct-or-silent).
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..game.layout import ATTR_NAMES, ATTR_RANGE, LEVEL_RANGE, RUNES_MAX, Layout, parse_vitals_block
from ..game.memory import is_user_ptr, read_ptr, read_u32
from ..game.profile import Effects, Profile

MAX_EFFECTS = 512
WORLD_LOST_RESET_S = 10.0  # title screen / long load this long -> forget baseline + animation


def iso(dt: datetime) -> str:
    """'YYYY-MM-DD HH:MM:SS.ffffff+HH:MM'. The UTC offset is always present (naive input is taken as local time)."""
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.isoformat(sep=" ", timespec="microseconds")


@dataclass
class Sample:
    state: str  # WAITING_FOR_WORLD | CONNECTED | IDLE
    character: dict | None = None
    ignored_effects: int = 0
    ignored_animations: int = 0
    error: str | None = None  # diagnostic only; None for the normal title-screen case
    runes: int | None = None


class Sampler(Layout):
    def __init__(self, mem, profile: Profile, effects: Effects, module_base: int):
        super().__init__(mem, profile, module_base)
        self.effects = effects
        self.baseline_runes: int | None = None
        self._was_at_grace: bool = False
        self._last_animation: dict[str, dict] = {}
        self._activations: dict[int, tuple[datetime, float]] = {}  # eid -> (activation_time, last_remaining)
        self._world_lost_at: datetime | None = None

    def _reset_session(self) -> None:
        """Forget per-character state (the player left the world, possibly to load another character)."""
        self.baseline_runes = None
        self._was_at_grace = False
        self._last_animation = {}
        self._activations.clear()

    def reset_baseline(self, runes: int) -> None:
        """Lock in a new farming cycle baseline."""
        self.baseline_runes = runes

    def _read_vitals(self, player: int) -> tuple[dict | None, str | None]:
        addr, err = self.vitals_address(player)
        if addr is None:
            return None, err
        raw = self.mem.read(addr, 40)
        if raw is None:
            return None, "read failed: CSChrDataModule vitals block"
        v, err = parse_vitals_block(raw)
        if v is None:
            return None, err
        hp, max_hp, _, base_hp, fp, max_fp, base_fp, stamina, max_stamina, base_stamina = v
        return {
            "hit_point": {"current": hp, "maximum": max_hp, "base": base_hp},
            "focus_point": {"current": fp, "maximum": max_fp, "base": base_fp},
            "stamina": {"current": stamina, "maximum": max_stamina, "base": base_stamina},
        }, None

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _wait(error: str | None = None) -> Sample:
        return Sample("WAITING_FOR_WORLD", error=error)

    def _follow(self, addr: int, name: str) -> tuple[int | None, Sample | None]:
        v, w = self.follow(addr, name)
        return v, (None if w is None else self._wait(w.error))

    # -- main ------------------------------------------------------------
    def sample(self, now: datetime | None = None) -> Sample:
        now = now or datetime.now(timezone.utc)
        s = self._sample(now)
        if s.state == "CONNECTED":
            self._world_lost_at = None
        elif s.error is None:  # normal title-screen / loading wait (not a read failure)
            if self._world_lost_at is None:
                self._world_lost_at = now
            elif (now - self._world_lost_at).total_seconds() >= WORLD_LOST_RESET_S:
                self._reset_session()
        return s

    def _sample(self, now: datetime) -> Sample:
        p = self.profile

        wcm, w = self._follow(self.base + p.world_chr_man_rva, "WorldChrMan")
        if w is not None:
            return w
        player, w = self._follow(wcm + p.world_chr_man_to_player, "PlayerIns")
        if w is not None:
            return w
        gd, w = self._follow(player + p.player_to_game_data, "PlayerGameData")
        if w is not None:
            return w

        level = read_u32(self.mem, gd + p.level)
        runes = read_u32(self.mem, gd + p.runes)
        raw = self.mem.read(gd + p.attributes, 32)
        if level is None or runes is None or raw is None:
            return self._wait("read failed: PlayerGameData fields")
        attrs = struct.unpack("<8I", raw)

        if not LEVEL_RANGE[0] <= level <= LEVEL_RANGE[1]:
            return self._wait(f"level={level} outside {LEVEL_RANGE} (PlayerGameData+0x{p.level:X})")
        if runes > RUNES_MAX:
            return self._wait(f"runes={runes} outside 0..{RUNES_MAX} (PlayerGameData+0x{p.runes:X})")
        for name, v in zip(ATTR_NAMES, attrs):
            if not ATTR_RANGE[0] <= v <= ATTR_RANGE[1]:
                return self._wait(f"{name}={v} outside {ATTR_RANGE} (PlayerGameData+0x{p.attributes:X})")

        vitals, err = self._read_vitals(player)
        if err is not None:
            return self._wait(err)

        effects: dict[str, dict] = {}
        ignored = 0
        if p.sp_effect is not None:
            entries, err = self._read_effect_list(player)
            if err is not None:
                return self._wait(err)
            effects, ignored = self._classify(entries, now)

        # Read Site of Grace interaction/resting state directly from CSChrTimeActModule in game memory
        anim_id = self.read_animation_id(player)
        is_at_grace = anim_id is not None and self.profile.at_grace is not None and anim_id in self.profile.at_grace.equals

        ignored_anim = 0
        if anim_id is not None and anim_id > 0:
            cfg = self.effects.table.get(anim_id)
            if cfg is not None:
                anim_obj = {
                    "name": cfg.name,
                    "categories": cfg.categories or "MANNER",
                }
                if cfg.abilities:
                    anim_obj["abilities"] = cfg.abilities
                self._last_animation = {str(anim_id): anim_obj}
            else:
                ignored_anim = 1
                self._last_animation = {
                    str(anim_id): {
                        "name": f"Animation {anim_id}",
                        "categories": "MANNER",
                    }
                }

        # Event: Entered Site of Grace (state transition: False -> True)
        entered_grace = is_at_grace and not self._was_at_grace

        # Baseline snapshot & freeze conditions:
        # 1. Initial Connect: read total -> set baseline = total -> freeze baseline
        # 2. Enter Site Of Grace: read total -> set baseline = total -> freeze baseline
        if self.baseline_runes is None or entered_grace:
            self.reset_baseline(runes)

        self._was_at_grace = is_at_grace

        baseline = self.baseline_runes
        delta = runes - baseline

        runes_obj = {
            "total": runes,
            "baseline": baseline,
            "delta": delta,
        }

        character = {
            "level": level,
            "vitals": vitals,
            "runes": runes_obj,
            "attributes": dict(zip(ATTR_NAMES, attrs)),
            "effects": effects,
            "animations": self._last_animation,
        }
        return Sample("CONNECTED", character, ignored, ignored_anim, None, runes)

    def raw_effects(self) -> tuple[list[tuple[int, float, float]] | None, str | None]:
        """Unclassified (id, duration, timer) entries, for the `effects` discovery command."""
        if self.profile.sp_effect is None:
            return None, "profile has no complete sp_effect layout"
        player, reason = self.locate_player()
        if player is None:
            return None, reason
        return self._read_effect_list(player)

    # -- SpEffect linked list -------------------------------------------
    def _read_effect_list(self, player: int):
        lay = self.profile.sp_effect
        e = lay.entry
        sp = read_ptr(self.mem, player + lay.player_to_sp_effect)
        if sp is None:
            return None, "read failed: SpecialEffect pointer"
        if sp == 0:
            return [], None
        if not is_user_ptr(sp):
            return None, f"invalid pointer SpecialEffect=0x{sp:X}"
        cur = read_ptr(self.mem, sp + lay.head)
        if cur is None:
            return None, "read failed: SpEffect list head"

        span = max(e.id, e.next, e.duration, e.timer) + 8
        seen: set[int] = set()
        out: list[tuple[int, float, float]] = []
        while cur != 0:
            if len(out) >= MAX_EFFECTS:
                return None, f"SpEffect list longer than {MAX_EFFECTS} entries"
            if cur in seen:
                return None, "cycle in SpEffect list"
            if not is_user_ptr(cur):
                return None, f"invalid SpEffect entry pointer 0x{cur:X}"
            seen.add(cur)
            blob = self.mem.read(cur, span)
            if blob is None:
                return None, f"read failed: SpEffect entry 0x{cur:X}"
            eid = struct.unpack_from("<I", blob, e.id)[0]
            nxt = struct.unpack_from("<Q", blob, e.next)[0]
            dur = struct.unpack_from("<f", blob, e.duration)[0]
            timer = struct.unpack_from("<f", blob, e.timer)[0]
            out.append((eid, dur, timer))
            cur = nxt
        return out, None

    def _classify(self, entries, now: datetime) -> tuple[dict[str, dict], int]:
        mode = self.profile.sp_effect.entry.timer_mode
        effects: dict[str, dict] = {}
        ignored = 0
        active_eids: set[int] = set()

        for eid, dur, timer in entries:
            cfg = self.effects.table.get(eid)
            if cfg is None or cfg.sources == "ANIMATIONS" or not (math.isfinite(dur) and math.isfinite(timer)):
                ignored += 1
                continue

            if dur <= 0:
                kind = "PERMANENT"
                times = None
            else:
                remaining = timer if mode == "remaining" else dur - timer
                if remaining <= 0 or remaining > dur + 1.0:
                    ignored += 1
                    continue
                kind = "TIMED"

                # Stable activation timestamp (remains unchanged until re-cast/re-activated)
                if eid in self._activations:
                    act_time, prev_rem = self._activations[eid]
                    if remaining > prev_rem + 2.0:
                        act_time = now - timedelta(seconds=dur - remaining)
                else:
                    act_time = now - timedelta(seconds=dur - remaining)

                self._activations[eid] = (act_time, remaining)
                active_eids.add(eid)

                times = {
                    "buff_duration": round(remaining, 2),
                    "max_duration": round(dur, 2),
                    "last_activated_at": iso(act_time),
                }

            key = str(eid)
            eff = {
                "name": cfg.name,
                "categories": cfg.categories or "CONSUMABLES",
            }
            if cfg.abilities:
                eff["abilities"] = cfg.abilities
            if kind == "TIMED":
                eff["times"] = times

            if key in effects:
                existing = effects[key]
                has_times = "times" in existing
                if not has_times and kind == "TIMED":
                    effects[key] = eff
                elif has_times and kind == "TIMED":
                    if times["buff_duration"] > existing["times"]["buff_duration"]:
                        effects[key] = eff
            else:
                effects[key] = eff

        # Prune expired or inactive buffs from activation tracking
        for stale_eid in list(self._activations.keys()):
            if stale_eid not in active_eids:
                del self._activations[stale_eid]

        return effects, ignored

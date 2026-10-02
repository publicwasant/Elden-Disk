"""Sampling: pointer chain -> validated snapshot -> JSON document.

Rule: one failed check discards the whole sample (correct-or-silent).
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .memory_reader import is_user_ptr, read_ptr, read_u32
from .profile_loader import Effects, Profile

MAX_EFFECTS = 512
LEVEL_RANGE = (1, 713)
RUNES_MAX = 999_999_999
ATTR_RANGE = (1, 99)
ATTR_NAMES = ("vigor", "mind", "endurance", "strength", "dexterity", "intelligence", "faith", "arcane")


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class Sample:
    state: str  # WAITING_FOR_WORLD | CONNECTED | IDLE
    character: dict | None = None
    ignored_effects: int = 0
    error: str | None = None  # diagnostic only; None for the normal title-screen case
    runes: int | None = None


class Sampler:
    def __init__(self, mem, profile: Profile, effects: Effects, module_base: int):
        self.mem = mem
        self.profile = profile
        self.effects = effects
        self.base = module_base
        self.session_start_runes: int | None = None
        self._activations: dict[int, tuple[datetime, float]] = {}  # eid -> (activation_time, last_remaining)

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _wait(error: str | None = None) -> Sample:
        return Sample("WAITING_FOR_WORLD", error=error)

    def _follow(self, addr: int, name: str) -> tuple[int | None, Sample | None]:
        v = read_ptr(self.mem, addr)
        if v is None:
            return None, self._wait(f"read failed: {name}")
        if v == 0:
            return None, self._wait()  # normal on title screen / loading
        if not is_user_ptr(v):
            return None, self._wait(f"invalid pointer {name}=0x{v:X}")
        return v, None

    # -- main ------------------------------------------------------------
    def sample(self, now: datetime | None = None) -> Sample:
        now = now or datetime.now(timezone.utc)
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

        effects: dict[str, dict] = {}
        ignored = 0
        if p.sp_effect is not None:
            entries, err = self._read_effect_list(player)
            if err is not None:
                return self._wait(err)
            effects, ignored = self._classify(entries, now)

        if self.session_start_runes is None:
            self.session_start_runes = runes
        character = {
            "level": level,
            "runes": runes,
            "attributes": dict(zip(ATTR_NAMES, attrs)),
            "effects": effects,
        }
        return Sample("CONNECTED", character, ignored, None, runes)

    def raw_effects(self) -> tuple[list[tuple[int, float, float]] | None, str | None]:
        """Unclassified (id, duration, timer) entries, for the `effects` discovery command."""
        if self.profile.sp_effect is None:
            return None, "profile has no complete sp_effect layout"
        p = self.profile
        wcm, w = self._follow(self.base + p.world_chr_man_rva, "WorldChrMan")
        if w is None:
            player, w = self._follow(wcm + p.world_chr_man_to_player, "PlayerIns")
        if w is not None:
            return None, w.error or "world not loaded"
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
            if cfg is None or not (math.isfinite(dur) and math.isfinite(timer)):
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
                "kind": kind,
            }
            if cfg.category is not None:
                eff["category"] = cfg.category
            if cfg.ability is not None:
                eff["ability"] = cfg.ability
            eff["times"] = times

            if key in effects:
                existing = effects[key]
                if existing["kind"] == "PERMANENT" and kind == "TIMED":
                    effects[key] = eff
                elif existing["kind"] == "TIMED" and kind == "TIMED":
                    if times["buff_duration"] > existing["times"]["buff_duration"]:
                        effects[key] = eff
            else:
                effects[key] = eff

        # Prune expired or inactive buffs from activation tracking
        for stale_eid in list(self._activations.keys()):
            if stale_eid not in active_eids:
                del self._activations[stale_eid]

        return effects, ignored


def build_document(*, now: datetime | None = None, state: str, pid: int | None, anti_cheat: str,
                   exe_sha256: str | None, profile_label: str | None, buffs_supported: bool,
                   sample: Sample | None, session_start_runes: int | None,
                   note: str | None = None) -> dict:
    has_character = sample is not None and sample.character is not None
    is_connected = state == "CONNECTED" and has_character
    is_idle = state == "IDLE" and has_character
    game_connected = is_connected or is_idle
    character = sample.character if game_connected else None
    current_runes = sample.runes if sample else None
    delta = (current_runes - session_start_runes) if (game_connected and current_runes is not None and session_start_runes is not None) else None

    return {
        "system_status": {
            "state": state,
            "game_connected": game_connected,
            "pid": pid,
            "anti_cheat_status": anti_cheat,
            "read_only": True,
            "exe_sha256": exe_sha256,
            "profile": profile_label,
            "buffs_supported": buffs_supported,
            "ignored_effects": sample.ignored_effects if sample else 0,
            "last_error": note or (sample.error if sample else None),
        },
        "character": character,
        "telemetry": {"session_start_runes": session_start_runes, "rune_delta": delta},
    }

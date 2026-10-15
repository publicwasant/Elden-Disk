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
from ..game.inventory import InventoryError, read_inventory
from ..game.params import ParamError, ParamNameError
from ..game.paramtables import Tables
from ..game.profile import Profile, StateIds
from ..game.textmem import item_names

MAX_BUFFS = 512
WORLD_LOST_RESET_S = 10.0  # title screen / long load this long -> forget baseline + animation
INVENTORY_EVERY_S = 1.0    # the inventory is read about once a second, not every frame (1.8.1)
NAMES_BUDGET_S = 20.0      # the look for the item names' text tables gives up after this (then every name is null)


def iso(dt: datetime) -> str:
    """'YYYY-MM-DD HH:MM:SS.ffffff+HH:MM'. The UTC offset is always present (naive input is taken as local time)."""
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.isoformat(sep=" ", timespec="microseconds")


@dataclass
class Sample:
    state: str  # WAITING_FOR_WORLD | CONNECTED | IDLE
    character: dict | None = None
    ignored_buffs: int = 0
    ignored_animations: int = 0
    error: str | None = None  # diagnostic only; None for the normal title-screen case
    runes: int | None = None


class Sampler(Layout):
    def __init__(self, mem, profile: Profile, state_ids: StateIds, module_base: int):
        super().__init__(mem, profile, module_base)
        self.state_ids = state_ids
        self.baseline_runes: int | None = None
        self._was_at_grace: bool = False
        self._last_animation: dict[str, dict] = {}
        self._activations: dict[int, tuple[datetime, float]] = {}  # eid -> (activation_time, last_remaining)
        self._world_lost_at: datetime | None = None
        self._inventory: dict | None = None
        self._inventory_at: datetime | None = None
        self._inventory_gd: int | None = None
        self.inventory_error: str | None = None   # why character.inventory is null now
        self._goods_types: dict[int, int] | None = None
        self._goods_types_tried = False
        self.item_names: dict | None = None        # (table, row id) -> the game's name of the item (names(); a test may set it)
        self._names_tried = False
        self.names_error: str | None = None
        self.inventory_wanted = True              # a `read` of other names turns it off: the inventory (and its names) is not read

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

        buffs: dict[str, dict] = {}
        ignored = 0
        if p.sp_effect is not None:
            entries, err = self._read_buff_list(player)
            if err is not None:
                return self._wait(err)
            buffs, ignored = self._classify(entries, now)

        # Read Site of Grace interaction/resting state directly from CSChrTimeActModule in game memory
        anim_id = self.read_animation_id(player)
        is_at_grace = anim_id is not None and self.profile.at_grace is not None and anim_id in self.profile.at_grace.equals

        ignored_anim = 0
        if anim_id is not None and anim_id > 0:
            cfg = self.state_ids.animations.get(anim_id)
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
            "buffs": buffs,
            "animations": self._last_animation,
        }
        equipment = self._read_equipment(gd)
        if equipment is not None:
            character["equipment"] = equipment
        if self.profile.inventory is not None and self.inventory_wanted:
            character["inventory"] = self._read_inventory(gd, now)
        return Sample("CONNECTED", character, ignored, ignored_anim, None, runes)

    def _read_inventory(self, gd: int, now: datetime) -> dict | None:
        """`character.inventory` (1.8.1), read at most every INVENTORY_EVERY_S (a few thousand places, tens of KB): what the character
        carries. None while it cannot be read (the reason in the log once); the rest of the sample is not held back by it."""
        if self._inventory_at is not None and (now - self._inventory_at).total_seconds() < INVENTORY_EVERY_S \
                and self._inventory_gd == gd:
            return self._inventory
        self._inventory_at, self._inventory_gd = now, gd
        try:
            self._inventory = read_inventory(self.mem, gd, self.profile.inventory, self.goods_types(), self.names())
            self.inventory_error = None
        except InventoryError as exc:
            self._inventory, self.inventory_error = None, str(exc)
        return self._inventory

    def names(self) -> dict | None:
        """{(param table, row id): the game's name of the item}, found once (the look for the text tables takes about a second);
        None when they cannot be found (then every `name` is null; the reason in `names_error`)."""
        if self.item_names is None and not self._names_tried and self.profile.text is not None:
            self._names_tried = True
            try:
                found, why = item_names(self.mem, self.profile.text, budget=NAMES_BUDGET_S)
            except Exception as exc:          # the names are extras: no failure of the look may stop the read
                found, why = {}, f"the look for the text failed: {exc}"
            self.item_names, self.names_error = (found or None), (why or None)
        return self.item_names

    def goods_types(self) -> dict[int, int] | None:
        """{goods id: EquipParamGoods.goodsType} of the running game, read once (the table's goodsType field only); None when the
        tables cannot be read (then `type` is left out)."""
        if self._goods_types is None and not self._goods_types_tried:
            self._goods_types_tried = True
            try:
                rows = Tables(self.mem, self.profile, self.base).read_table("EquipParamGoods", "goodsType")
                self._goods_types = {rid: row["goodsType"] for rid, row in rows.items()}
            except (ParamError, ParamNameError):
                pass
        return self._goods_types

    def _read_equipment(self, gd: int) -> dict | None:
        """`character.equipment` (1.7.2): {"magic": {"selected": {"slot", "id"}, "slots": {"1": id, ...}}}: the spells memorised in the
        magic slots (numbered from 1, as the game shows them; empty slots left out) and the one that is selected. None when the profile
        has no equipment block or the data cannot be read now (the rest of the sample is not held back by it)."""
        lay = self.profile.equipment
        if lay is None:
            return None
        magic = read_ptr(self.mem, gd + lay.game_data_to_magic)
        if magic is None or not is_user_ptr(magic):
            return None
        lo = min(lay.magic_slots, lay.magic_selected)          # the slots and the selected one in ONE read (116 bytes on 1.17.1)
        hi = max(lay.magic_slots + lay.magic_slot_count * lay.magic_slot_size, lay.magic_selected + 4)
        raw = self.mem.read(magic + lo, hi - lo)
        if raw is None or len(raw) < hi - lo:
            return None
        sel = struct.unpack_from("<I", raw, lay.magic_selected - lo)[0]
        slots = {}
        for n in range(lay.magic_slot_count):
            mid = struct.unpack_from("<i", raw, lay.magic_slots - lo + n * lay.magic_slot_size)[0]
            if mid > 0:
                slots[str(n + 1)] = mid
        if sel >= lay.magic_slot_count:
            return None
        chosen = slots.get(str(sel + 1))
        return {"magic": {"selected": {"slot": sel + 1, "id": chosen}, "slots": slots}}

    def raw_buffs(self) -> tuple[list[tuple[int, float, float]] | None, str | None]:
        """Unclassified (id, duration, timer) entries, for the `read monitor-buffs` monitor."""
        if self.profile.sp_effect is None:
            return None, "profile has no complete sp_effect layout"
        player, reason = self.locate_player()
        if player is None:
            return None, reason
        return self._read_buff_list(player)

    # -- SpEffect linked list -------------------------------------------
    def _read_buff_list(self, player: int):
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
            if len(out) >= MAX_BUFFS:
                return None, f"SpEffect list longer than {MAX_BUFFS} entries"
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
        buffs: dict[str, dict] = {}
        ignored = 0
        active_eids: set[int] = set()

        for eid, dur, timer in entries:
            cfg = self.state_ids.buffs.get(eid)
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
            buff = {
                "name": cfg.name,
                "categories": cfg.categories or "CONSUMABLES",
            }
            if cfg.abilities:
                buff["abilities"] = cfg.abilities
            if kind == "TIMED":
                buff["times"] = times

            if key in buffs:
                existing = buffs[key]
                has_times = "times" in existing
                if not has_times and kind == "TIMED":
                    buffs[key] = buff
                elif has_times and kind == "TIMED":
                    if times["buff_duration"] > existing["times"]["buff_duration"]:
                        buffs[key] = buff
            else:
                buffs[key] = buff

        # Prune expired or inactive buffs from activation tracking
        for stale_eid in list(self._activations.keys()):
            if stale_eid not in active_eids:
                del self._activations[stale_eid]

        return buffs, ignored

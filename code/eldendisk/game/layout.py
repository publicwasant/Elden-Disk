"""Where things are in the game's memory: pointer chains resolved fresh on every call (never cached).

Used by the reader (Sampler) and the writer. Read-only: it only calls `mem.read`.
"""
from __future__ import annotations

import struct
from typing import NamedTuple

from .memory import is_user_ptr, read_ptr, read_u32
from .profile import Profile

LEVEL_RANGE = (1, 713)
RUNES_MAX = 999_999_999
ATTR_RANGE = (1, 99)
ATTR_NAMES = ("vigor", "mind", "endurance", "strength", "dexterity", "intelligence", "faith", "arcane")


class Wait(NamedTuple):
    """Why a chain could not be followed. `error` is None for the normal title-screen / loading case (null pointer)."""
    error: str | None


class Layout:
    def __init__(self, mem, profile: Profile, module_base: int):
        self.mem = mem
        self.profile = profile
        self.base = module_base

    def follow(self, addr: int, name: str) -> tuple[int | None, Wait | None]:
        v = read_ptr(self.mem, addr)
        if v is None:
            return None, Wait(f"read failed: {name}")
        if v == 0:
            return None, Wait(None)  # normal on title screen / loading
        if not is_user_ptr(v):
            return None, Wait(f"invalid pointer {name}=0x{v:X}")
        return v, None

    def locate_player(self) -> tuple[int | None, str | None]:
        """(PlayerIns address, None), or (None, reason) while the world/player is not available."""
        p = self.profile
        wcm, w = self.follow(self.base + p.world_chr_man_rva, "WorldChrMan")
        if w is None:
            player, w = self.follow(wcm + p.world_chr_man_to_player, "PlayerIns")
            if w is None:
                return player, None
        return None, w.error or "world not loaded"

    def locate_game_data(self) -> tuple[int | None, str | None]:
        """(PlayerGameData address, None), or (None, reason)."""
        player, reason = self.locate_player()
        if player is None:
            return None, reason
        gd, w = self.follow(player + self.profile.player_to_game_data, "PlayerGameData")
        return (gd, None) if w is None else (None, w.error or "world not loaded")

    def locate_vitals(self) -> tuple[int | None, str | None]:
        """(vitals block address, None), or (None, reason)."""
        player, reason = self.locate_player()
        if player is None:
            return None, reason
        return self.vitals_address(player)

    def vitals_address(self, player: int) -> tuple[int | None, str | None]:
        """Address of the 40-byte vitals block (CSChrDataModule + data_to_vitals), or (None, reason)."""
        vit = self.profile.vitals
        if vit is None:
            return None, "profile has no vitals layout"
        modules = read_ptr(self.mem, player + vit.player_to_modules)
        if modules is None or modules == 0 or not is_user_ptr(modules):
            return None, "read failed: ChrInsModuleContainer pointer"
        data_mod = read_ptr(self.mem, modules + vit.modules_to_data)
        if data_mod is None or data_mod == 0 or not is_user_ptr(data_mod):
            return None, "read failed: CSChrDataModule pointer"
        return data_mod + vit.data_to_vitals, None

    def read_animation_id(self, player: int) -> int | None:
        anim = self.profile.anim
        if anim is None:
            return None
        modules = read_ptr(self.mem, player + anim.player_to_modules)
        if modules is None or modules == 0 or not is_user_ptr(modules):
            return None
        time_act = read_ptr(self.mem, modules + anim.modules_to_time_act)
        if time_act is None or time_act == 0 or not is_user_ptr(time_act):
            return None
        read_idx = read_u32(self.mem, time_act + anim.time_act_read_idx)
        if read_idx is None:
            return None
        entry_addr = time_act + anim.time_act_queue + (read_idx * anim.queue_entry_size)
        return read_u32(self.mem, entry_addr)



def parse_vitals_block(raw: bytes) -> tuple[tuple[int, ...] | None, str | None]:
    """Unpack + validate the 10-int vitals block: (hp, max_hp, uncapped_max, base_hp, fp, max_fp, base_fp, st, max_st, base_st)."""
    v = struct.unpack("<10i", raw)
    hp, max_hp, _, base_hp, fp, max_fp, base_fp, stamina, max_stamina, base_stamina = v
    if hp < 0 or max_hp <= 0 or base_hp <= 0:
        return None, f"invalid HP vitals: hp={hp}, max_hp={max_hp}, base_hp={base_hp}"
    if fp < 0 or max_fp <= 0 or base_fp <= 0:
        return None, f"invalid FP vitals: fp={fp}, max_fp={max_fp}, base_fp={base_fp}"
    if max_stamina <= 0 or base_stamina <= 0:
        return None, f"invalid Stamina vitals: stamina={stamina}, max_stamina={max_stamina}, base_stamina={base_stamina}"
    return v, None

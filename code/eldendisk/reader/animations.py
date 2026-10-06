"""`read --live-animations`: the character's animation ids over time (for chr_state_ids.json)."""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from .monitor import LedgerMonitor
from .sampler import Sampler


class AnimationsMonitor(LedgerMonitor):
    name = "animations"

    def __init__(self, sampler: Sampler, out: Callable[[str], None] | None = None, *, show: str = "all",
                 now: Callable[[], datetime] = lambda: datetime.now().astimezone()):
        super().__init__(sampler, out, show=show, now=now)

    @staticmethod
    def unsupported(profile) -> str | None:
        return None if profile.anim is not None else "anim layout incomplete in profile"

    def is_mapped(self, eid: int) -> bool:
        return eid in self.sampler.effects.table

    def read(self):
        player, reason = self.sampler.locate_player()
        if player is None:
            return None, reason
        cur = self.sampler.read_animation_id(player)
        if cur is None or cur <= 0:
            return None, None   # nothing new to record this tick
        return {cur: None}, None

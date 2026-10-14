"""`read monitor-buffs`: the character's buff ids (the game's SpEffects) over time (for names.json)."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Callable

from .monitor import LedgerMonitor
from .sampler import Sampler


class BuffsMonitor(LedgerMonitor):
    name = "buffs"

    def __init__(self, sampler: Sampler, out: Callable[[str], None] | None = None, *, quiet: bool = False,
                 show: str = "all", now: Callable[[], datetime] = lambda: datetime.now().astimezone()):
        super().__init__(sampler, out, show=show, now=now)
        self.quiet = quiet

    @property
    def table(self):
        return self.sampler.state_ids.buffs

    @staticmethod
    def unsupported(profile) -> str | None:
        return None if profile.sp_effect is not None else (profile.buffs_note or "sp_effect layout incomplete in profile")

    def is_mapped(self, eid: int) -> bool:
        return eid in self.table

    def read(self):
        entries, err = self.sampler.raw_buffs()
        if entries is None:
            return None, err
        return {eid: (dur, timer) for eid, dur, timer in entries if not self.quiet or dur < 0 or dur >= 1.0}, None

    def detail_text(self, detail) -> str:
        """`remaining / total s` for a timed buff, `permanent` for one without a duration."""
        if not detail:
            return ""
        dur, timer = detail
        if not (math.isfinite(dur) and math.isfinite(timer)):
            return "?"
        if dur <= 0:
            return "permanent"
        remaining = timer if self.sampler.profile.sp_effect.entry.timer_mode == "remaining" else dur - timer
        return f"{max(remaining, 0.0):.1f} / {dur:.1f} s"

"""What `--live-effects` and `--live-animations` have in common: a ledger of ids, a filter, and two views of it.

A monitor reads the game once per tick and updates its ledger. A console that cannot redraw gets the transitions as
lines through `out` (`+ id  name  time`); a terminal gets `lines(now)` and `summary()` to draw as a table.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from .ledger import Ledger, Line, stamp
from .sampler import Sampler

UNKNOWN = "Unknown"
SHOW = ("all", "mapped", "unmapped")


class LedgerMonitor:
    name = "ids"

    def __init__(self, sampler: Sampler, out: Callable[[str], None] | None, *, show: str = "all",
                 now: Callable[[], datetime] = lambda: datetime.now().astimezone()):
        if show not in SHOW:
            raise ValueError(f"show must be one of {SHOW}")
        self.sampler, self.out, self.show, self._now = sampler, out, show, now
        self.ledger = Ledger()
        self.waiting: str | None = None
        self._said: str | None = None

    # -- what a subclass provides ----------------------------------------
    def read(self) -> tuple[dict[int, object] | None, str | None]:
        """(ids present now with their detail, None) | (None, why not) | (None, None) = nothing new this tick."""
        raise NotImplementedError

    def is_mapped(self, eid: int) -> bool:
        raise NotImplementedError

    def detail_text(self, detail) -> str:
        return ""

    # -- shared -----------------------------------------------------------
    def start(self) -> None:
        if self.out:
            self.out("Format: + appeared, - disappeared | id | name (Unknown = not in chr_state_ids.json) | time")

    def _shown(self, eid: int) -> bool:
        return self.show == "all" or (self.show == "mapped") == self.is_mapped(eid)

    def name_of(self, eid: int) -> str | None:
        cfg = self.sampler.effects.table.get(eid) if self.is_mapped(eid) else None
        return cfg.name if cfg is not None else None

    def tick(self) -> None:
        present, reason = self.read()
        if present is None:
            if reason is not None:
                self.waiting = reason
                if self.out and reason != self._said:
                    self.out(f"[waiting] {reason}")
                    self._said = reason
            return
        self.waiting = self._said = None
        now = self._now()
        for kind, e in self.ledger.update(present, now):
            if self.out and self._shown(e.id):
                self.out(self.event_line(kind, e))

    def event_line(self, kind: str, e) -> str:
        when = e.since if kind == "+" else e.last_seen
        detail = self.detail_text(e.detail) if kind == "+" else ""
        parts = [f"{kind} {e.id:>9}", f"{self.name_of(e.id) or UNKNOWN:<24}"]
        if detail:
            parts.append(f"{detail:<16}")
        parts.append(stamp(when))
        return "  ".join(parts)

    def lines(self, now: datetime) -> list[Line]:
        out = []
        for e in self.ledger.ordered():
            if not self._shown(e.id):
                continue
            out.append(Line(e.active, e.id, self.name_of(e.id), self.detail_text(e.detail) if e.active else "",
                            stamp(e.since if e.active else e.last_seen), self.ledger.is_hot(e, now)))
        return out

    def summary(self) -> str:
        entries = self.ledger.entries.values()
        active = sum(1 for e in entries if e.active)
        unmapped = sum(1 for e in entries if not self.is_mapped(e.id))
        text = f"{active} active · {len(self.ledger.entries)} seen · {unmapped} unmapped"
        return text + ("" if self.show == "all" else f" · showing {self.show}")

"""A ledger of ids seen over time, for the buff and animation monitors (pure: no console, no memory).

Every id is one row, whatever number of times it comes and goes. An id is *active* while it is present and stops being
active only after it has been absent for `SETTLE_S` (the game flips some animation ids every frame; without the delay
those rows would blink). Rows are ordered active first (newest activation on top), then the rest (most recently seen
on top), at one-second resolution so that a flipping id does not reshuffle the list every frame.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import NamedTuple

SETTLE_S = 0.25   # absent this long before an id counts as gone
HOLD_S = 1.0      # how long a row that just changed stays highlighted


@dataclass
class Entry:
    id: int
    order: int                  # first-seen order (tie-break, so rows keep their place)
    active: bool
    since: datetime             # when it became active (the last time, if it came back)
    last_seen: datetime
    changed: datetime           # last +/- transition (drives the highlight)
    detail: object = None       # what the monitor wants to show while active


class Line(NamedTuple):
    """One row of the table, ready to draw."""
    active: bool
    id: int
    name: str | None            # None = not mapped in names.json
    detail: str
    stamp: str                  # HH:MM:SS.mmm of the last change
    hot: bool


def stamp(when: datetime) -> str:
    """Human readable time for the live displays (the documents keep the ISO form)."""
    return f"{when:%H:%M:%S}.{when.microsecond // 1000:03d}"


class Ledger:
    def __init__(self):
        self.entries: dict[int, Entry] = {}

    def update(self, present: dict[int, object], now: datetime) -> list[tuple[str, Entry]]:
        """Record what is present now; returns the transitions as ("+" | "-", entry), ids ascending."""
        events: list[tuple[str, Entry]] = []
        for eid in sorted(present):
            e = self.entries.get(eid)
            if e is None:
                e = self.entries[eid] = Entry(eid, len(self.entries), True, now, now, now)
                events.append(("+", e))
            elif not e.active:
                e.active, e.since, e.changed = True, now, now
                events.append(("+", e))
            e.last_seen, e.detail = now, present[eid]
        for e in self.entries.values():
            if e.active and e.id not in present and (now - e.last_seen).total_seconds() >= SETTLE_S:
                e.active, e.changed, e.detail = False, now, None
                events.append(("-", e))
        return events

    def forget(self) -> int:
        """`reset` (1.8.0): the history starts again from now: what has ended is dropped, what is active stays. -> how many were dropped."""
        gone = [eid for eid, e in self.entries.items() if not e.active]
        for eid in gone:
            del self.entries[eid]
        return len(gone)

    def ordered(self) -> list[Entry]:
        return sorted(self.entries.values(),
                      key=lambda e: (not e.active, -int((e.since if e.active else e.last_seen).timestamp()), e.order))

    def is_hot(self, e: Entry, now: datetime) -> bool:
        return (now - e.changed).total_seconds() < HOLD_S

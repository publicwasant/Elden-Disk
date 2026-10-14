"""The great-enemies table (spec 1.8.0 section 4): great_enemies.json, made by tools/gen_great_enemies.py from the game's own files.
Pure: the rows, the flags each boss is brought back with, and names -> ids. Standard library only.

A row: name, place, map, flags {defeated, playlog, drop, cutscene}, runes, drop (item names), grace {id, name, meters} | null, story,
dlc. To bring a boss back every flag of `flags` is turned off (the defeat, the play-log trigger of its Remembrance, the drops' flags,
the intro's flags); the achievement flags are never in the table.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

TABLE_FILE = Path(__file__).resolve().parent / "great_enemies.json"
ALL = ("all", "*")


class TableError(Exception):
    """A wrong or ambiguous name, or a table that cannot be read."""


def _key(text: str) -> str:
    return re.sub(r"[^0-9a-z]+", " ", str(text).lower()).strip()


@dataclass
class Table:
    rows: dict[int, dict]
    game: str = ""
    _names: dict[str, list[int]] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        for rid, r in self.rows.items():
            for n in [r.get("name", ""), *r.get("aliases", [])]:
                self._names.setdefault(_key(n), []).append(rid)

    def label(self, rid: int) -> str:
        r = self.rows[rid]
        return f"{r['name']}, {r['place']} ({rid})" if r.get("place") else f"{r['name']} ({rid})"

    def _one_boss(self, name: str, rids: list[int]) -> list[int]:
        """Rows that share a name are one great enemy only when they share the defeat flag (a boss in two rows); otherwise the name is
        ambiguous: the place or the id tells them apart."""
        if len({self.rows[r]["flags"]["defeated"] for r in rids}) == 1:
            return list(rids)
        shown = "; ".join(self.label(r) for r in rids[:8])
        raise TableError(f"{name}: {len(rids)} great enemies: {shown}; name one (its id, or the name with its place)")

    # ---- flags
    def flags_of(self, rid: int) -> list[int]:
        """Every flag that brings `rid` back, the defeat flag first."""
        f = self.rows[rid]["flags"]
        return list(dict.fromkeys([f["defeated"], *f.get("playlog", []), *f.get("drop", []), *f.get("cutscene", [])]))

    def allowed(self) -> set[int]:
        """Every flag of the table: the only flags the tool may turn off."""
        return {x for rid in self.rows for x in self.flags_of(rid)}

    def defeated_flags(self) -> dict[int, int]:
        return {rid: r["flags"]["defeated"] for rid, r in self.rows.items()}

    # ---- names
    def resolve(self, names) -> list[int]:
        """Names or ids -> row ids, in the order given (each once). `all` / `*` alone: every row. TableError (with what a name fits,
        or the closest names) when any name is wrong: then nothing is chosen."""
        names = [str(n).strip() for n in names if str(n).strip()]
        if len(names) == 1 and names[0].lower() in ALL:
            return list(self.rows)
        if any(n.lower() in ALL for n in names):
            raise TableError("`all` stands alone")
        out, problems = [], []
        for n in names:
            try:
                for rid in self.one(n):
                    if rid not in out:
                        out.append(rid)
            except TableError as exc:
                problems.append(str(exc))
        if problems:
            raise TableError("; ".join(problems))
        return out

    def one(self, name: str) -> list[int]:
        """One name -> the rows it means (a list: rows that share a name, like a boss fought twice, are one great enemy)."""
        if re.fullmatch(r"\d+", name):
            rid = int(name)
            if rid in self.rows:
                return [rid]
            hits = [r for r, row in self.rows.items() if row["flags"]["defeated"] == rid]
            if hits:
                return hits
            raise TableError(f"{name}: no great enemy has this id")
        k = _key(name)
        if k in self._names:
            return self._one_boss(name, self._names[k])
        words = k.split()
        hits: dict[int, list[int]] = {}         # defeat flag -> rows (one great enemy may be two rows)
        for rid, r in self.rows.items():
            hay = _key(f"{r.get('name', '')} {' '.join(r.get('aliases', []))} {r.get('place') or ''}").split()
            if all(w in hay or any(x.startswith(w) for x in hay) for w in words):
                hits.setdefault(r["flags"]["defeated"], []).append(rid)
        if len(hits) == 1:
            return next(iter(hits.values()))
        if len(hits) > 1:
            firsts = [v[0] for v in hits.values()]
            shown = "; ".join(self.label(r) for r in firsts[:8])
            more = f" and {len(hits) - 8} more" if len(hits) > 8 else ""
            raise TableError(f"{name}: {len(hits)} great enemies: {shown}{more}; name one (its id, or the name with its place)")
        close = sorted(self._names, key=lambda nk: -_overlap(k, nk))[:3]
        raise TableError(f"{name}: no great enemy has this name (closest: {', '.join(self.rows[self._names[c][0]]['name'] for c in close)})")


def _overlap(a: str, b: str) -> int:
    return sum(1 for w in a.split() if any(w[:4] in x for x in b.split()))


def load(path: Path | str | None = None) -> Table:
    p = Path(path) if path else TABLE_FILE
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        rows = {int(k): v for k, v in doc["great_enemies"].items()}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise TableError(f"{p}: the great-enemies table cannot be read ({exc})") from None
    return Table(rows, str(doc.get("game", "")))


def creative_list(design: dict) -> list[str] | None:
    """creative.json's `resurrect.great_enemies.activate` (spec 1.8.0): a list of names, or ["all"]; None without one."""
    block = ((design or {}).get("resurrect") or {}).get("great_enemies")
    if block is None:
        return None
    if not isinstance(block, dict):
        raise TableError("resurrect.great_enemies must be an object")
    act = block.get("activate")
    if act is None:
        return None
    if isinstance(act, str):
        return [act]
    if isinstance(act, list) and all(isinstance(x, (str, int)) for x in act):
        return [str(x) for x in act]
    raise TableError("resurrect.great_enemies.activate must be a list of names or ids, or \"all\"")

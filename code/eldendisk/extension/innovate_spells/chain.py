"""The chain of rows a spell is made of: which rows a Magic row reaches, and how many spells share each row.

A Magic row calls rows of three tables (`refCategory1..10` / `refId1..10`: 0 AtkParam_Pc, 1 Bullet, 2 SpEffect); a Bullet calls
other Bullets, an AtkParam_Pc and SpEffects; an AtkParam_Pc calls SpEffects; a SpEffect can call other SpEffects. A row that
many spells reach (SpEffect 500 and 505 are used by 19 and more) is a generic row the game's scripts know by its id: a copy of it would be
a different row, so such rows are shared, never copied. Only the offsets of the pointers of Bullet and AtkParam_Pc are known here
(`BULLET`, `ATK`: from the layouts of the params workbench, checked against them in the tests); Bullet and AtkParam_Pc rows cannot be
added yet. Read only."""
from __future__ import annotations

import struct

from .container import Param

DUMMY = 999999999
# row size and the byte offsets of the s32 fields that hold the id of another row
BULLET = {"size": 272, "bullet": (104, 172), "atk": (0,), "sp": (96, 108, 112, 116, 120, 124)}   # HitBulletID, intervalCreateBulletId | atkId_Bullet | spEffectIDForShooter, spEffectId0-4
ATK = {"size": 456, "sp": (24, 28, 32, 36, 40)}                                                  # spEffectId0-4
SP_LINKS = ("cycleOccurrenceSpEffectId", "atkOccurrenceSpEffectId", "replaceSpEffectId")
# the fields that call another row, by name, as (table called, field): what the builder remaps in a copy (the offsets above are checked
# against these names in the tests)
SP_PAIRS = tuple(("sp", n) for n in SP_LINKS)
BULLET_LINKS = (("bullet", "HitBulletID"), ("bullet", "intervalCreateBulletId"), ("atk", "atkId_Bullet"), ("sp", "spEffectIDForShooter"),
                ("sp", "spEffectId0"), ("sp", "spEffectId1"), ("sp", "spEffectId2"), ("sp", "spEffectId3"), ("sp", "spEffectId4"))
ATK_PAIRS = tuple(("sp", "spEffectId%d" % n) for n in range(5))
CATEGORY = {0: "atk", 1: "bullet", 2: "sp"}
TABLES = ("atk", "bullet", "sp")


def _s32(row, off):
    return struct.unpack_from("<i", row, off)[0]


class Chain:
    """P: key -> Param (at least magic and sp), bullet / atk: Param of the Bullet and AtkParam_Pc tables, D: key -> Def."""

    def __init__(self, P: dict, D: dict, bullet: Param, atk: Param):
        if bullet.row_size != BULLET["size"] or atk.row_size != ATK["size"]:
            raise ValueError("the Bullet or AtkParam_Pc table has another row size than this version knows")
        self.D = D
        self.rows = {"magic": {r[0]: r[2] for r in P["magic"].rows}, "sp": {r[0]: r[2] for r in P["sp"].rows},
                     "bullet": {r[0]: r[2] for r in bullet.rows}, "atk": {r[0]: r[2] for r in atk.rows}}
        self._reach = None

    def real(self, table: str, rid: int) -> bool:
        return rid > 0 and rid != DUMMY and rid in self.rows[table]

    def refs(self, magic_id: int) -> list:
        """[(n, table, id)] the Magic row calls: table is 'atk', 'bullet' or 'sp'; empty slots and ids that are not rows are left out."""
        m, d, out = self.rows["magic"][magic_id], self.D["magic"], []
        for n in range(1, 11):
            table, rid = CATEGORY.get(d.get(m, "refCategory%d" % n)), d.get(m, "refId%d" % n)
            if table and self.real(table, rid):
                out.append((n, table, rid))
        return out

    def links(self, table: str, rid: int) -> list:
        """[(table, id)] the row calls (real rows only)."""
        row, found = self.rows[table][rid], []
        if table == "sp":
            found = [("sp", self.D["sp"].get(row, n)) for n in SP_LINKS]
        elif table == "bullet":
            found = [(t, _s32(row, off)) for t in ("bullet", "atk", "sp") for off in BULLET[t]]
        else:
            found = [("sp", _s32(row, off)) for off in ATK["sp"]]
        return [(t, i) for t, i in found if self.real(t, i)]

    def closure(self, magic_id: int) -> dict:
        """{'atk': set, 'bullet': set, 'sp': set}: every row the spell reaches."""
        got = {t: set() for t in TABLES}
        stack = [(t, i) for _n, t, i in self.refs(magic_id)]
        while stack:
            t, i = stack.pop()
            if i in got[t]:
                continue
            got[t].add(i)
            stack.extend(self.links(t, i))
        return got

    def copy_set(self, magic_id: int, shared_above: int = 3) -> dict:
        """{'atk': set, 'bullet': set, 'sp': set}: the rows a copy of this spell takes along: the spell's own AtkParam_Pc, Bullet and
        SpEffect rows (reached by no more than `shared_above` Magic rows of the game) that the spell reaches through such rows. The walk
        stops at a generic row (it stays shared): what hangs below it is called by the game's rows, not by the copy."""
        got = {"atk": set(), "bullet": set(), "sp": set()}
        own = lambda t, i: t in got and self.reach(t, i) <= shared_above
        stack = [(t, i) for _n, t, i in self.refs(magic_id) if own(t, i)]
        while stack:
            t, i = stack.pop()
            if i in got[t]:
                continue
            got[t].add(i)
            stack.extend((t2, i2) for t2, i2 in self.links(t, i) if own(t2, i2))
        return got

    def reach(self, table: str, rid: int) -> int:
        """How many Magic rows of the game reach this row (counted on the game's own Magic table)."""
        if self._reach is None:
            self._reach = {}
            for mid in self.rows["magic"]:
                for t, ids in self.closure(mid).items():
                    for i in ids:
                        self._reach[(t, i)] = self._reach.get((t, i), 0) + 1
        return self._reach.get((table, rid), 0)


def load(bnd, P: dict, D: dict) -> Chain:
    """The chain reader for the tables of an opened BND4 (`P`: the tables as the recipes see them)."""
    return Chain(P, D, Param(bnd.get("Bullet").data), Param(bnd.get("AtkParam_Pc").data))

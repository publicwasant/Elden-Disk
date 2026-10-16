"""`character.buffs` (1.8.2): which item the character holds gives each buff.

A buff of the character is one of the game's SpEffects. The game's own tables say which SpEffects an item gives: a goods item through
`refId_default` / `refId_1` when its `refCategory` is 2 (an SpEffect), a spell through its Magic row (the spell's goods id is its Magic
id), a talisman through `refId` and `residentSpEffectId1` ... `4`, a weapon (its row: the id without its level), a piece of armor and an
ash of war through their resident SpEffects. A `refCategory` of 1 is a Bullet: the bullet's own SpEffects count, one step, not further
(spec 1.8.2 section 7.3). Only the items held (`quantity.held` 1 or more) give a buff: the storage chest gives none.

The rows are read from the game once per table (only the fields above); a table is read again when a held item's row is not in it (a
build added rows), at most every AGAIN_S.
"""
from __future__ import annotations

import time
from typing import Callable

from ..game.inventory import GROUPS, LEVEL_STEP, TABLES
from ..game.params import ParamError, ParamNameError

AGAIN_S = 10.0             # a table that failed, or that lacks a held item's row, is read again after this many seconds
SP_EFFECT, BULLET = 2, 1   # the game's refCategory values

FIELDS = {
    "EquipParamGoods": ("refCategory", "refId_default", "refId_1"),
    "Magic": tuple(f"refCategory{n}" for n in range(1, 11)) + tuple(f"refId{n}" for n in range(1, 11)),
    "EquipParamAccessory": ("refCategory", "refId", "residentSpEffectId1", "residentSpEffectId2", "residentSpEffectId3",
                            "residentSpEffectId4"),
    "EquipParamWeapon": ("residentSpEffectId", "residentSpEffectId1", "residentSpEffectId2"),
    "EquipParamProtector": ("residentSpEffectId", "residentSpEffectId2", "residentSpEffectId3"),
    "EquipParamGem": ("spEffectId0", "spEffectId1", "spEffectId2"),
    "Bullet": ("spEffectIDForShooter", "spEffectId0", "spEffectId1", "spEffectId2", "spEffectId3", "spEffectId4"),
}
RESIDENT = {"EquipParamAccessory": FIELDS["EquipParamAccessory"][2:], "EquipParamWeapon": FIELDS["EquipParamWeapon"],
            "EquipParamProtector": FIELDS["EquipParamProtector"], "EquipParamGem": FIELDS["EquipParamGem"],
            "Bullet": FIELDS["Bullet"]}
REFS = {"EquipParamGoods": [("refCategory", "refId_default"), ("refCategory", "refId_1")],
        "Magic": [(f"refCategory{n}", f"refId{n}") for n in range(1, 11)],
        "EquipParamAccessory": [("refCategory", "refId")]}


def _ids(values) -> list[int]:
    return [v for v in values if isinstance(v, int) and v > 0]


def row_refs(table: str, row: dict) -> tuple[list[int], list[int]]:
    """(the SpEffect ids, the Bullet ids) one decoded row of `table` names."""
    sp = _ids(row.get(f) for f in RESIDENT.get(table, ()))
    bullets = []
    for cat, ref in REFS.get(table, ()):
        if row.get(cat) == SP_EFFECT:
            sp += _ids([row.get(ref)])
        elif row.get(cat) == BULLET:
            bullets += _ids([row.get(ref)])
    return sp, bullets


def table_reader(tables) -> Callable[[str, tuple], dict[int, dict]]:
    """`read(table, fields)` -> {row id: {field: value}} from the game's tables (a `paramtables.Tables`), only those fields decoded."""
    from ..game.paramtables import decode_row

    def read(table: str, fields: tuple) -> dict[int, dict]:
        return {rid: decode_row(table, raw, fields) for rid, raw in tables.all_rows(table).items()}
    return read


class ItemEffects:
    """{(table, row id): the SpEffect ids that row gives}, from the game's tables, read once per table."""

    def __init__(self, read: Callable[[str, tuple], dict[int, dict]] | None, clock: Callable[[], float] = time.monotonic):
        self.read, self.clock = read, clock
        self._rows: dict[str, dict[int, dict]] = {}
        self._read_at: dict[str, float] = {}
        self.errors: dict[str, str] = {}          # table -> why it cannot be read (for the log)

    def _table(self, table: str, row_id: int | None = None) -> dict[int, dict]:
        rows = self._rows.get(table)
        stale = rows is None or (row_id is not None and row_id not in rows)
        if stale and self.read is not None and self.clock() - self._read_at.get(table, -1e9) >= AGAIN_S:
            self._read_at[table] = self.clock()
            try:
                self._rows[table] = rows = self.read(table, FIELDS[table])
                self.errors.pop(table, None)
            except (ParamError, ParamNameError, OSError) as exc:
                self.errors[table] = str(exc)
        return rows or {}

    def of(self, table: str, row_id: int) -> tuple[int, ...]:
        """The SpEffect ids the row `row_id` of `table` gives, a Bullet it names followed one step; () when the row is unknown."""
        row = self._table(table, row_id).get(row_id)
        if row is None:
            return ()
        sp, bullets = row_refs(table, row)
        for b in bullets:
            brow = self._table("Bullet", b).get(b)
            if brow is not None:
                sp += row_refs("Bullet", brow)[0]
        return tuple(dict.fromkeys(sp))

    def of_item(self, group: str, iid: int) -> tuple[int, ...]:
        """The SpEffect ids an item of the inventory gives: a goods item through its goods row and, a spell, its Magic row too."""
        if group == "weapons":
            return self.of(TABLES[group], iid - iid % LEVEL_STEP)
        got = self.of(TABLES[group], iid)
        if group in ("goods", "key_items"):
            got = tuple(dict.fromkeys(got + self.of("Magic", iid)))
        return got


def held_key(inventory: dict | None) -> tuple:
    """What the index depends on: the (group, id) of every item held."""
    if not inventory:
        return ()
    return tuple((g, k) for g in GROUPS for k, e in (inventory.get(g) or {}).items() if (e.get("quantity") or {}).get("held"))


def build_index(inventory: dict | None, effects: ItemEffects, spell_buffs: dict[int, int] | None = None) -> dict[int, list]:
    """{SpEffect id: [(group, id key), ...]}: the held items that give it, in the order goods, key items, talismans, weapons, armor, ashes
    of war. `spell_buffs` ({SpEffect id: goods id}): the copied SpEffect rows of the design's spells (innovate-spells), given by their
    goods item when it is held."""
    index: dict[int, list] = {}
    held = held_key(inventory)
    for group, key in held:
        for sp in effects.of_item(group, int(key)):
            index.setdefault(sp, []).append((group, key))
    held_set = set(held)
    for sp, goods in (spell_buffs or {}).items():
        for group in ("goods", "key_items"):
            ref = (group, str(goods))
            if ref in held_set and ref not in index.get(sp, ()):
                index.setdefault(sp, []).append(ref)
    return index


def path_of(ref: tuple[str, str]) -> str:
    return f"character.inventory.{ref[0]}.{ref[1]}"

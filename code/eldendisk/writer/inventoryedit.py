"""`write inventory....quantity.held|stored=N` (1.8.1 part 2): the count of an item the character already has, in the game's memory.

Only an entry that is there is changed, and only its quantity (the 4 bytes at entry_quantity); the handle, the id and the place in the
menu are not touched (spec 1.8.1 P2). Goods and key items only; a count is 1 to the game's own cap, read from the item's
EquipParamGoods row (`maxNum` held, `maxRepositoryNum` stored). The entry is found again just before the write, its handle and id
checked, the count written and read back (P3). The first value of each count is remembered in the params' snapshot (`=default`).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

from ..game.inventory import InventoryError, entry, list_address, read_inventory
from ..game.layout import Layout
from ..game.params import ParamError, ParamNameError
from ..game.paramtables import Tables
from ..game.textmem import item_names
from ..game.profile import InventoryLayout, InventoryList
from ..game.values import normalize

ROOT = "character.inventory"
SNAP = "inventory"                       # snapshot keys: inventory.<held|stored>.<group>.<id>
WRITABLE_GROUPS = ("goods", "key_items")
CAP_FIELD = {"held": "maxNum", "stored": "maxRepositoryNum"}


class InventoryEditError(ValueError):
    """A name or a value that cannot be written; nothing may be written."""


@dataclass(frozen=True)
class InventoryEdit:
    name: str                 # as the person typed it
    group: str                # goods | key_items
    item: int                 # the id
    where: str                # held | stored
    value: int | None         # None: back to the value before the first change (=default)

    @property
    def key(self) -> str:
        return f"{SNAP}.{self.where}.{self.group}.{self.item}"

    @property
    def path(self) -> str:
        return f"{ROOT}.{self.group}.{self.item}.quantity.{self.where}"


def name_key(text: str) -> str:
    """An item's name as it is typed in a path: lower case, words joined by `_` (`Smithing Stone [1]` -> `smithing_stone_1`), as `read`
    finds it (reader/view.py)."""
    return "_".join(w for w in "".join(c if c.isalnum() else " " for c in str(text).lower()).split())


def is_inventory_name(name: str) -> bool:
    path = normalize(name)
    return path == ROOT or path.startswith(ROOT + ".")


def resolve(name: str, inventory: dict | None, by_name) -> tuple[str, int, str]:
    """(group, id, held|stored) of `name` (`inventory.goods.1200.quantity.held`, `inventory.gold_pickled_fowl_foot.quantity`, ...);
    `by_name(name) -> [(group, id)]` finds an item by its name. InventoryEditError when it is not a count that can be written."""
    path = normalize(name)
    parts = path[len(ROOT) + 1:].split(".") if path.startswith(ROOT + ".") else []
    if not parts or not parts[0]:
        raise InventoryEditError(f"{name.strip()}: name one count, e.g. inventory.goods.1200.quantity.held")
    if parts[0] in ("goods", "key_items", "talismans", "weapons", "armor", "ashes_of_war"):
        group = parts[0]
        if len(parts) < 2 or not parts[1].isdigit():
            raise InventoryEditError(f"{name.strip()}: give the item's id after {group} (e.g. inventory.{group}.1200.quantity.held)")
        hits, rest = [(group, int(parts[1]))], parts[2:]
    else:
        hits, rest = by_name(parts[0]), parts[1:]
        if not hits:
            raise InventoryEditError(f"{name.strip()}: no item of that name is held or stored now (`read inventory` lists them)")
        if len(hits) > 1:
            raise InventoryEditError(f"{name.strip()}: {len(hits)} items have that name ("
                                     + ", ".join(f"{g}.{i}" for g, i in hits) + "); give the kind and the id")
    group, item = hits[0]
    if not rest or rest[0] != "quantity":
        raise InventoryEditError(f"{name.strip()}: only the quantity can be written (quantity.held or quantity.stored)")
    where = rest[1] if len(rest) > 1 else "held"
    if where == "total":
        raise InventoryEditError(f"{name.strip()}: total is held + stored, computed; write held or stored")
    if where not in ("held", "stored") or len(rest) > 2:
        raise InventoryEditError(f"{name.strip()}: write quantity.held or quantity.stored")
    if group not in WRITABLE_GROUPS:
        raise InventoryEditError(f"{name.strip()}: a count of {group.replace('_', ' ')} cannot be written (one entry is one item; only "
                                 "goods and key items have counts to change)")
    if group == "key_items" and where == "stored":
        raise InventoryEditError(f"{name.strip()}: key items are not kept in the storage chest")
    if inventory is not None:
        have = ((inventory.get(group) or {}).get(str(item)) or {}).get("quantity") or {}
        if not have.get(where):
            raise InventoryEditError(f"{name.strip()}: the character has no {group.replace('_', ' ')} {item} {where} now; only a count that "
                                     "is there can be changed (adding an item is not in 1.8.1)")
    return group, item, where


def check_value(name: str, raw: str, cap: int | None) -> int:
    try:
        value = int(raw.strip().replace("_", ""))
    except ValueError:
        raise InventoryEditError(f"{name.strip()}={raw.strip()}: a count is a whole number") from None
    if value < 1:
        raise InventoryEditError(f"{name.strip()}={value}: a count is 1 or more (an item is not removed by a count of 0)")
    if cap is not None and value > cap:
        raise InventoryEditError(f"{name.strip()}={value}: the game holds at most {cap} of this item here")
    return value


def find_entry(mem, game_data: int, lay: InventoryLayout, lst: InventoryList, kind: str, item: int) -> tuple[int, bytes]:
    """(address of the entry, its bytes) of the one entry of `kind` and `item` in the list. InventoryEditError when there is
    none, or more than one (two places: which count was meant is not clear)."""
    addr = list_address(mem, game_data, lst)
    if addr is None:
        raise InventoryEditError("the list's pointer is unreadable or empty")
    raw = mem.read(addr, lst.capacity * lay.entry_size)
    if raw is None:
        raise InventoryEditError("the list is unreadable")
    hits = [n for n in range(lst.capacity)
            if (e := entry(raw, n * lay.entry_size, lay)) is not None and e[0] == kind and e[1] == item]
    if not hits:
        raise InventoryEditError(f"{kind} {item} is not in the list now (used up, moved or sorted meanwhile)")
    if len(hits) > 1:
        raise InventoryEditError(f"{kind} {item} is in {len(hits)} places of the list; which one was meant is not clear")
    o = hits[0] * lay.entry_size
    return addr + o, raw[o:o + lay.entry_size]


def list_of(lay: InventoryLayout, edit: InventoryEdit) -> InventoryList:
    if edit.where == "stored":
        if lay.storage is None:
            raise InventoryEditError("this game version's profile has no storage chest")
        return lay.storage
    return lay.key_items if edit.group == "key_items" else lay.items


@dataclass(frozen=True)
class Result:
    name: str
    value: int
    wrote: bool
    note: str | None = None


def apply(mem, game_data: int, lay: InventoryLayout, edits: list[InventoryEdit], gate, snapshot=None) -> list[Result]:
    """Write every edit: the entry found again, its handle and id checked, the count written and read back. A count already at its
    value is not written. InventoryEditError for the first edit that cannot be made (the ones before it were made)."""
    out = []
    for e in edits:
        if not gate.allowed:
            raise InventoryEditError(f"{e.name}: writes are not allowed ({gate.reason})")
        lst = list_of(lay, e)
        at, head = find_entry(mem, game_data, lay, lst, "goods", e.item)
        q_at = at + lay.entry_quantity
        current = head[lay.entry_quantity:lay.entry_quantity + 4]
        target = e.value
        if target is None:
            remembered = snapshot.get(e.key) if snapshot is not None else None
            if remembered is None:
                out.append(Result(e.name, struct.unpack("<I", current)[0], False, "no earlier value in this game process"))
                continue
            target = struct.unpack("<I", remembered)[0]
        if struct.unpack("<I", current)[0] == target:
            if e.value is None and snapshot is not None:
                snapshot.drop(e.key)
            out.append(Result(e.name, target, False, "already so"))
            continue
        again = mem.read(at, lay.entry_size)
        if again != head:
            raise InventoryEditError(f"{e.name}: the entry changed while the write was prepared (the game used or moved it); nothing written")
        if snapshot is not None and e.value is not None:
            snapshot.record(e.key, current)
        raw = struct.pack("<I", target)
        if not mem.write(q_at, raw) or mem.read(q_at, 4) != raw:
            raise InventoryEditError(f"{e.name}: the write failed or did not stick")
        if e.value is None and snapshot is not None:
            snapshot.drop(e.key)
        out.append(Result(e.name, target, True))
    return out


def write_counts(mem, target, gate, snapshot, items: list[tuple[str, str]]) -> list[Result]:
    """[(name, value as typed)] -> what was written: every name resolved and every value checked first (an item by its name, the cap
    from its EquipParamGoods row), then the counts written (`apply`). `inventory=default` puts back every count changed in this game
    process. InventoryEditError: the first name or value that cannot be written (nothing is written then)."""
    lay = target.profile.inventory
    if lay is None:
        raise InventoryEditError("this game version's profile has no inventory block")
    gd, why = Layout(mem, target.profile, target.base).locate_game_data()
    if gd is None:
        raise InventoryEditError(f"the inventory cannot be written now ({why})")
    names: dict = {}

    def by_name(key: str):
        if not names and target.profile.text is not None:
            names.update(item_names(mem, target.profile.text, game=(target.pid, target.started))[0] or {("", 0): ""})
        return [(g, int(i)) for g, its in inv.items() if g in WRITABLE_GROUPS for i in its
                if names.get(("EquipParamGoods", int(i))) and name_key(names[("EquipParamGoods", int(i))]) == key]

    try:
        inv = read_inventory(mem, gd, lay)
        tables = Tables(mem, target.profile, target.base)
        edits = []
        for name, raw in items:
            if normalize(name) == ROOT and raw.strip().lower() == "default":
                for key in (snapshot.keys() if snapshot is not None else []):
                    if key.startswith(SNAP + "."):
                        _s, where, group, iid = key.split(".")
                        edits.append(InventoryEdit(f"{ROOT}.{group}.{iid}.quantity.{where}", group, int(iid), where, None))
                continue
            group, iid, where = resolve(name, inv, by_name)
            if raw.strip().lower() == "default":
                edits.append(InventoryEdit(name.strip(), group, iid, where, None))
                continue
            cap = tables.read_row("EquipParamGoods", iid).get(CAP_FIELD[where])
            edits.append(InventoryEdit(name.strip(), group, iid, where, check_value(name, raw, cap)))
        return apply(mem, gd, lay, edits, gate, snapshot) if edits else []
    except (InventoryError, ParamError, ParamNameError) as exc:
        raise InventoryEditError(str(exc)) from None

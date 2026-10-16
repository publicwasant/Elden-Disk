"""`character.inventory` (1.8.1): what the character carries, as the game's Inventory menu shows it. Read-only.

Measured on 1.17.1 with `probe inventory` (spec 1.8.1 section 4): PlayerGameData keeps two lists of 24-byte entries, the items (behind
the pointer at +0x418, 2,688 places) and the key items (inline at +0xB10, 384 places). An entry is the item's handle, its id, the
quantity, its place in the menu and two more words. The handle's top four bits say the kind (0x8 weapon, 0x9 armor, 0xA talisman,
0xB goods, 0xC ash of war) and agree with the id's (0x0, 0x1, 0x2, 0x4, 0x8); for goods and talismans the rest of the two is the same
number. An entry that does not pass these checks is not an item (an empty place, or not yet written): it is left out, never guessed.
"""
from __future__ import annotations

import struct

from .profile import InventoryLayout, InventoryList

KINDS = {0x8: "weapons", 0x9: "armor", 0xA: "talismans", 0xB: "goods", 0xC: "ashes_of_war"}       # by the handle's top four bits
ID_TOP = {0x8: 0x0, 0x9: 0x1, 0xA: 0x2, 0xB: 0x4, 0xC: 0x8}
TABLES = {"weapons": "EquipParamWeapon", "armor": "EquipParamProtector", "talismans": "EquipParamAccessory", "goods": "EquipParamGoods",
          "key_items": "EquipParamGoods", "ashes_of_war": "EquipParamGem"}
GROUPS = ("goods", "key_items", "talismans", "weapons", "armor", "ashes_of_war")
QTY_MAX = 999_999          # the game's own counts stay far below; a larger number is not a quantity
LEVEL_STEP = 100           # a weapon's id is its row (affinity in the hundreds) plus its level

# EquipParamGoods.goodsType -> the word `type` shows (the numbers the game uses; the words are the Inventory menu's kinds). A value not
# here is shown as its number.
GOODS_TYPES = {0: "consumable", 1: "key item", 2: "crafting material", 3: "remembrance", 5: "sorcery", 7: "spirit ash",
               8: "spirit ash", 9: "physick", 10: "physick tear", 11: "regenerative material", 12: "info", 14: "upgrade material",
               15: "great rune", 16: "incantation", 17: "sorcery", 18: "incantation"}


class InventoryError(Exception):
    pass


def entry(raw: bytes, o: int, lay: InventoryLayout) -> tuple[str, int, int] | None:
    """(kind, id, quantity) of the entry at `o`, or None when it is not an item."""
    handle = struct.unpack_from("<I", raw, o + lay.entry_handle)[0]
    iid = struct.unpack_from("<I", raw, o + lay.entry_id)[0]
    qty = struct.unpack_from("<I", raw, o + lay.entry_quantity)[0]
    top = handle >> 28
    if top not in KINDS or iid >> 28 != ID_TOP[top] or not 1 <= qty <= QTY_MAX:
        return None
    if top in (0xA, 0xB) and handle & 0x0FFFFFFF != iid & 0x0FFFFFFF:
        return None
    return KINDS[top], iid & 0x0FFFFFFF, qty


def list_address(mem, game_data: int, lst: InventoryList) -> int | None:
    """Where the list's first place is: the chain of pointers followed from PlayerGameData, then `start`; None when a pointer is
    unreadable or empty."""
    base = game_data
    for p in lst.pointers:
        raw = mem.read(base + p, 8)
        if raw is None:
            return None
        base = struct.unpack("<Q", raw)[0]
        if not base:
            return None
    return base + lst.start


def read_list(mem, game_data: int, lay: InventoryLayout, lst: InventoryList) -> list[tuple[str, int, int]]:
    """The items of one list, in the order of its places. InventoryError when the list cannot be read."""
    addr = list_address(mem, game_data, lst)
    if addr is None:
        raise InventoryError("the list's pointer is unreadable or empty")
    raw = mem.read(addr, lst.capacity * lay.entry_size)
    if raw is None:
        raise InventoryError(f"{lst.capacity} places at 0x{addr:X} are unreadable")
    if lay.entry_size % 4 or lay.entry_handle % 4 or lay.entry_id % 4 or lay.entry_quantity % 4:
        return [e for n in range(lst.capacity) if (e := entry(raw, n * lay.entry_size, lay)) is not None]
    # 1.8.1 part 3: the same checks as `entry`, on 32-bit words (a few thousand places a second; about three times quicker)
    words = memoryview(raw).cast("I")
    step, h_at, i_at, q_at = lay.entry_size // 4, lay.entry_handle // 4, lay.entry_id // 4, lay.entry_quantity // 4
    out = []
    for b in range(0, lst.capacity * step, step):
        handle = words[b + h_at]
        top = handle >> 28
        if top not in KINDS:
            continue
        iid, qty = words[b + i_at], words[b + q_at]
        if iid >> 28 != ID_TOP[top] or not 1 <= qty <= QTY_MAX:
            continue
        if top in (0xA, 0xB) and handle & 0x0FFFFFFF != iid & 0x0FFFFFFF:
            continue
        out.append((KINDS[top], iid & 0x0FFFFFFF, qty))
    return out


def build(items, key_items, goods_types: dict[int, int] | None = None, names: dict[tuple[str, int], str] | None = None,
          storage=None) -> dict:
    """`character.inventory` from the entries of the lists: {group: {id: {name, (type), (upgrade), quantity: {total, held, stored}}}}.
    `held`: in the items and key items; `stored`: in the storage chest (an item only there has `held` 0); `total`: the two added (the
    game keeps no total). An id in two places of a list is one entry with the quantities added. `storage` None (the chest not read):
    `stored` and `total` are null."""
    names = names or {}
    out: dict[str, dict] = {g: {} for g in GROUPS}
    sources = [("items", items, "held"), ("key_items", key_items, "held")]
    if storage is not None:
        sources.append(("storage", storage, "stored"))
    for source, entries, where in sources:
        for kind, iid, qty in entries:
            group = "key_items" if source == "key_items" and kind == "goods" else kind
            key = str(iid)
            e = out[group].get(key)
            if e is None:
                row = iid - iid % LEVEL_STEP if group == "weapons" else iid
                e = {"name": names.get((TABLES[group], row))}
                if group in ("goods", "key_items") and goods_types is not None:
                    t = goods_types.get(iid)
                    e["type"] = GOODS_TYPES.get(t, t) if t is not None else None
                if group == "weapons":
                    e["upgrade"] = iid % LEVEL_STEP
                e["quantity"] = {"total": 0, "held": 0, "stored": 0}
                out[group][key] = e
            e["quantity"][where] += qty
    for items_of in out.values():
        for e in items_of.values():
            q = e["quantity"]
            if storage is None:
                q["stored"] = q["total"] = None
            else:
                q["total"] = q["held"] + q["stored"]
    return out


def read_inventory(mem, game_data: int, lay: InventoryLayout, goods_types=None, names=None) -> dict:
    """`character.inventory` now. InventoryError when the items or the key items cannot be read; the storage chest that cannot be
    read (or a profile without it) leaves `stored` and `total` null, the rest is still read."""
    stored = None
    if lay.storage is not None:
        try:
            stored = read_list(mem, game_data, lay, lay.storage)
        except InventoryError:
            stored = None
    return build(read_list(mem, game_data, lay, lay.items), read_list(mem, game_data, lay, lay.key_items), goods_types, names, stored)

> [!NOTE]
> **Version:** `1.8.1`  
> **Status:** Part 1 (reading the inventory): IMPLEMENTED (closed) on 2026-10-15. Tried in the real game the same day: the layout of
> section 4 (`probe inventory`),
> `read inventory` and `export --disk` with every kind, the counts (Gold-Pickled Fowl Foot 10, Smithing Stone [1] 16, Stonesword Key 6)
> and the names in the game's language, after `innovate-spells apply` had replaced GoodsName (section 5); `quantity.stored` from the
> storage chest (Gold-Pickled Fowl Foot: total 562, held 10, stored 552, as the menu shows). One read soon after the world was
> loaded gave `stored` 0 for it; the reads after gave 552 (not explained; to watch).
> Part 2 (writing the inventory): IMPLEMENTED (closed) on 2026-10-15, decided by the author the same day (P5: the defaults); tried
> in the real game the same day (a held count written, read back and put back: passed). Part 3 (optimization): IMPLEMENTED on
> 2026-10-16 (unit tests); the time of the first and later `read inventory` to be seen in a game's log (`-v`).  
> **Last Updated:** _2026-10-16_

# Elden-Disk spec 1.8.1: `character.inventory`

Reads on top of [spec 1.8.0](elden-disk-spec-v1.8.0.md). Only what changes is written here. Branch `feat/character-inventory`.

- **Part 1:** reading the inventory (`character.inventory`): sections 1 to 10.
- **Part 2:** writing the inventory (the counts): sections P1 to P7.
- **Part 3:** optimization of parts 1 and 2: sections O1 to O4.

# Part 1: reading the inventory (2026-10-15)

## 1. Idea

Asked by the author (2026-10-15): read what the character carries, as the game's Inventory menu shows it: every item and how many,
in a block of its own, `character.inventory` (not `character.equipment`, which is what is equipped: the magic slots). For example the
number of Gold-Pickled Fowl Foot the character has now.

- **Read-only.** Nothing is written; there is no `write` name for the inventory in 1.8.1.
- **What the character carries**, key items included, and how many of each are in the storage chest (`quantity.stored`, section 10).
- A path of `disk.json`: `read disk.character.inventory...`, `export`, a script's `x.character.inventory`.

## 2. In the disk

```text
disk.character.inventory
  goods          the items: consumables, materials, sorceries and incantations, spirit ashes, remembrances ...
    "<id>": { "name": "Gold-Pickled Fowl Foot", "type": "consumable", "quantity": { "total": 562, "held": 10, "stored": 552 } }
  key_items      what the game keeps in its list of key items (keys, maps, great runes ...)
    "<id>": { "name": "...", "quantity": { "total": 1, "held": 1, "stored": 0 } }
  talismans
    "<id>": { "name": "...", "quantity": { "total": 1, "held": 1, "stored": 0 } }
  weapons        a weapon with its affinity and level is its own id (Heavy Dagger +3: 1000103)
    "<id>": { "name": "Heavy Dagger", "upgrade": 3, "quantity": { "total": 1, "held": 1, "stored": 0 } }
  armor
    "<id>": { "name": "...", "quantity": { "total": 1, "held": 1, "stored": 0 } }
  ashes_of_war
    "<id>": { "name": "...", "quantity": { "total": 1, "held": 1, "stored": 0 } }
```

- **The id** is the row id of the item's table in the game (`EquipParamGoods`, `EquipParamAccessory`, `EquipParamWeapon`,
  `EquipParamProtector`, `EquipParamGem`): what `read params.EquipParamGoods.<id>` reads. A weapon's id is its row plus its level, as
  the game counts it (`9000110` is row `9000100`, Heavy Uchigatana, at +10; the table has no row 9000110).
- **`quantity`** (the author's shape, 2026-10-15), as the Inventory menu shows held / stored:
  - `held`: how many the character carries;
  - `stored`: how many are in the storage chest (an item only in the chest is listed too, with `held` 0);
  - `total`: the two added. The game keeps no total; it is computed.
  Two copies of one weapon at the same level are one entry with `held` 2. When the chest cannot be read, `stored` and `total` are null.
- **`name`**: the game's own name of the item, in the language the game is played in (section 5); `null` when it cannot be read.
- **`upgrade`** (weapons only): the level, `+0` to `+25` (`+10` for somber weapons), from the id: the last two digits; the affinity is in the
  hundreds (the name of the id already says it: "Heavy Dagger").
- A kind with nothing in it is `{}`. No character in the world: `character` is `null`, as now.

### Example (`disk.json`)

The ids are the game's own rows (1.17.1); the quantities, and which items the character has, are only an example.

```json
{
  "systems": { "...": "..." },
  "character": {
    "level": 386,
    "vitals": { "...": "..." },
    "runes": { "...": "..." },
    "attributes": { "...": "..." },
    "buffs": { "...": "..." },
    "animations": { "...": "..." },
    "equipment": { "magic": { "selected": { "slot": 3, "id": 6240 }, "slots": { "1": 6230, "2": 6250, "3": 6240, "4": 6210 } } },
    "inventory": {
      "goods": {
        "810":    { "name": "Rowa Raisin", "type": "consumable", "quantity": { "total": 12, "held": 12, "stored": 0 } },
        "1200":   { "name": "Gold-Pickled Fowl Foot", "type": "consumable", "quantity": { "total": 562, "held": 10, "stored": 552 } },
        "2900":   { "name": "Golden Rune [1]", "type": "consumable", "quantity": { "total": 25, "held": 25, "stored": 0 } },
        "4000":   { "name": "Glintstone Pebble", "type": "sorcery", "quantity": { "total": 1, "held": 1, "stored": 0 } },
        "10100":  { "name": "Smithing Stone [1]", "type": "upgrade material", "quantity": { "total": 40, "held": 40, "stored": 0 } },
        "207000": { "name": "Mimic Tear Ashes", "type": "spirit ash", "quantity": { "total": 1, "held": 1, "stored": 0 } }
      },
      "key_items": {
        "8000":   { "name": "Stonesword Key", "quantity": { "total": 4, "held": 4, "stored": 0 } },
        "8158":   { "name": "Spirit Calling Bell", "quantity": { "total": 1, "held": 1, "stored": 0 } }
      },
      "talismans": {
        "1040":   { "name": "Erdtree's Favor", "quantity": { "total": 1, "held": 1, "stored": 0 } },
        "1150":   { "name": "Green Turtle Talisman", "quantity": { "total": 1, "held": 1, "stored": 0 } }
      },
      "weapons": {
        "9000000": { "name": "Uchigatana", "upgrade": 0, "quantity": { "total": 1, "held": 1, "stored": 0 } },
        "9000110": { "name": "Heavy Uchigatana", "upgrade": 10, "quantity": { "total": 1, "held": 1, "stored": 0 } }
      },
      "armor": {
        "50000":  { "name": "Kaiden Helm", "quantity": { "total": 1, "held": 1, "stored": 0 } },
        "140100": { "name": "Bull-Goat Armor", "quantity": { "total": 1, "held": 1, "stored": 0 } }
      },
      "ashes_of_war": {
        "10000":  { "name": "Ash of War: Lion's Claw", "quantity": { "total": 1, "held": 1, "stored": 0 } }
      }
    }
  },
  "creative": { "...": "..." }
}
```

`read disk.character.inventory.gold_pickled_fowl_foot --flat`:

```text
disk.character.inventory.goods.1200.name       Gold-Pickled Fowl Foot
disk.character.inventory.goods.1200.type       consumable
disk.character.inventory.goods.1200.quantity.total    562
disk.character.inventory.goods.1200.quantity.held     10
disk.character.inventory.goods.1200.quantity.stored   552
```

### Reading it

```text
read disk.character.inventory                       everything carried
read disk.character.inventory.goods                 one kind
read disk.character.inventory.goods.<id>            one item by id: { name, quantity }
read disk.character.inventory.gold_pickled_fowl_foot one item by its name (as `margit` finds a boss); every kind is looked in
read disk.character.inventory.*.quantity.* --flat   every count, one line each
read inventory.gold_pickled_fowl_foot.quantity      the short name (`inventory` is a head of `character`, like `runes`): total, held, stored
```

- **By name**: lower case, words joined by `_` (`gold_pickled_fowl_foot`, `Smithing Stone [1]` -> `smithing_stone_1`), as the great
  enemies are found by name in 1.8.0. A name that two items share (two weapons of one name at different levels) gives all of them.
- `read --live` shows a count change when it happens (an item used, picked up, bought).

## 3. When it is read

The inventory is two lists of 3,072 places (section 4), 72 KB. It is read **about once a second** while a
character is in the world (the way `params` was before 1.8.0 part 4), and at every one-shot `read` and `export`; not at every frame.
`read --live` and `export --live` show it within a second of a change.

## 4. Where it is in memory (measured on 1.17.1, 2026-10-15)

The profile already reaches `PlayerGameData` (`player_to_game_data`, the same object as the magic slots). `probe inventory` (below), run
three times in the game, showed the inventory there as **two lists of 24-byte entries**:

| **Bytes** | **What**                                                                                          |
|:---------:|:--------------------------------------------------------------------------------------------------|
| 0-3       | the handle: its top four bits are the kind (`0x8` weapon, `0x9` armor, `0xA` talisman, `0xB` goods, `0xC` ash of war) |
| 4-7       | the item id: the same kind in its top four bits (`0x0`, `0x1`, `0x2`, `0x4`, `0x8`), the rest the id (a weapon: row + level) |
| 8-11      | the quantity                                                                                      |
| 12-15     | the place in the menu                                                                             |
| 16-23     | two more words (the last `FFFFFFFF`)                                                              |

| **List**  | **Where**                                  | **Places** | **In the probe's game**                                        |
|:----------|:-------------------------------------------|-----------:|:---------------------------------------------------------------|
| items     | `[PlayerGameData + 0x418] + 0`             | 2,688      | 479: weapons 79, armor 120, talismans 23, goods 242, ashes 15  |
| key items | `PlayerGameData + 0xB10` (inline; `0x180` in front of it) | 384 | 79 goods                                          |
| the storage chest (`stored`) | `[[PlayerGameData + 0x5F0] + 0x8] + 0x6020` (`0x780` in front) | 1,920 | 65 (Gold-Pickled Fowl Foot 552) |

The 2,688 places of the items: the next data behind the list starts 2,688 × 24 bytes after it (the save file has the same number).
For goods and talismans the handle's low bits are the id; for weapons, armor and ashes of war the handle is the game's own number of
that one item, and the entry still holds its id (with a weapon's level), so all kinds are read from the entry alone (no `GaItem`).

An entry is an item only when the two kinds agree, the low bits agree for goods and talismans, and the quantity is 1 to 999,999;
anything else (an empty place) is left out. An id held in two places of one list is one item with the quantities added
(the probe saw Smithing Stone [1] twice: 16 and 1).

The profile block (offsets.json):

```json
"inventory": {
  "entry_size": "0x18", "entry_handle": "0x0", "entry_id": "0x4", "entry_quantity": "0x8",
  "items": { "pointer": "0x418", "start": "0x0", "capacity": 2688 },
  "key_items": { "start": "0xB10", "capacity": 384 },
  "storage": { "pointers": ["0x5F0", "0x8"], "start": "0x6020", "capacity": 1920 }
}
```

Without the block (another game version) there is no `character.inventory`.

### `probe inventory` (read-only)

A data command, like `probe` of 1.8.0: it looks through `PlayerGameData` (32 KB of it, and two levels of the objects its first 8 KB
points to) for runs of goods entries and for lists of the 24-byte entries above; for each it prints where it is, the entry size, the
quantity's place, the kinds, and the bytes around the first entries. `--find ID` (again for more) prints every place a goods id is, with
the 32-bit words around it. This is how the layout above was read (the second and third runs, with `--find` for Gold-Pickled Fowl Foot,
Smithing Stone [1] and Stonesword Key).

## 5. The names

The names are the game's own text, read from the game's memory: the same array of text tables `innovate-spells apply` finds for
`GoodsName` (writer/text.py says how: the tables by their shape and size, the array by three pointers at the right distances). So the
names are in the language the game runs in, and a renamed spell of a build shows with its new name.

- The name tables are the profile's `text.names`, by their numbers in the game's `item.msgbnd` (tools/dump_msgbnd.py lists them):
  `EquipParamGoods` 10, 319, 419 (GoodsName and its DLC versions), `EquipParamWeapon` 11, 310, 410, `EquipParamProtector` 12, 313, 413,
  `EquipParamAccessory` 13, 316, 416, `EquipParamGem` 35, 322, 422. A later table wins for the ids it has. That the array holds the DLC's
  tables at these numbers too is to be seen in the game (an item of the DLC with a name shows it).
- The array is found by tables a build never replaces (`text.name_files`: WeaponName, ProtectorName, AccessoryName, with their sizes):
  in the game, after `innovate-spells apply` had replaced GoodsName, GoodsInfo and GoodsCaption, a look by those found no array and
  every name was null. GoodsName is then read through the array, so a renamed spell shows with its new name.
- They are found once per command (once per game process for `--live`, `export --live` and the scripts): the look takes about a second.
  A `read` of names that do not reach the inventory (`read hp`, `read disk.character.level`) reads neither the inventory nor the names.
- An item with no text (a cut item, an empty row) has `"name": null`; it is still listed with its id and quantity. When the tables are
  not found (a language other than the profile's sizes), every `name` is `null`.
- The look for the text moved from the writer to the game package (`game/textmem.py`, `game/scan.py`), so the reader can use it; the
  writer keeps the one write (`swap`).

## 6. Failures

| **What**                                         | **Then**                                                                                       |
|:-------------------------------------------------|:-----------------------------------------------------------------------------------------------|
| no `inventory` block in the profile              | no `character.inventory`; `read inventory` says there is no such value                          |
| an entry that does not add up (kinds that disagree, a quantity of 0 or too large) | that entry is left out (an empty place); the others are read |
| a list cannot be read (its pointer empty, its places unreadable) | `character.inventory` is `null` this time; the rest of `character` is read as always |
| the names cannot be found                        | every `name` is `null`, the ids and quantities are still there                                  |
| no character in the world                        | `character` is `null`, as now                                                                  |

Correct-or-silent, as everywhere: a value that does not pass its checks is not shown.

## 7. Commands and names

- No new read command: `read disk.character.inventory...` and the short `read inventory...` (section 2). `write` has no `inventory`
  name: nothing of it can be written.
- `probe inventory` (section 4), next to `probe`; reads only.
- The document's schema gets `character.inventory`.

## 8. Tests

- `tests/test_inventory.py`: a fake `PlayerGameData` with both lists (the measured entries, empty places, the kinds in the top bits):
  every kind, the quantities (an id in two places added), weapons with their level, entries that do not add up left out, an unreadable
  list `null`; once a second, not every frame; the schema; by-name lookup (`gold_pickled_fowl_foot`, `smithing_stone_1`, in key items
  too); which commands read it; the names from a fake text array (a DLC table wins); the profile block.
- `tests/test_inventory_probe.py`: `probe inventory` on a fake game (runs, lists of 24-byte entries with their header, `--find`); it
  never writes.

## 9. Not in 1.8.1

- Writing the inventory (adding, removing, changing a count).
- What is equipped beyond the magic slots (`character.equipment`: weapons in hand, armor worn, talismans in their slots).

## 10. Decided by the author (2026-10-15)

1. **The storage chest**: first not in 1.8.1; then (the same day, after `read` gave 10 Gold-Pickled Fowl Foot where the menu says held 10,
   stored 552) read as `quantity.stored`, with `quantity: {total, held, stored}`.
2. **Goods**: one `goods` group, each entry with its `type`: the game's own type of the item (`EquipParamGoods.goodsType`, read from the
   game's row), as a word where the value is known (consumable, key item, crafting material, remembrance, sorcery, incantation, spirit
   ash, physick tear, great rune, upgrade material ...; the words checked against the Inventory menu's tabs when it is measured), the
   number otherwise.
3. **The names' language**: the game's (the text the running game holds).


# Part 2: writing the inventory (2026-10-15)

Asked by the author: `character.inventory` reads every item; it should be written the same way, as every other value of the disk.
Implemented the same day, with the author's choices of P5 (all three defaults).

## P1. The names

The same paths that are read, through the same portal and gate as every write (`write`, a script's `tools.write`):

```text
write inventory.gold_pickled_fowl_foot.quantity.held=20
write disk.character.inventory.goods.1200.quantity.stored=600
write inventory.smithing_stone_1.quantity.held=default        the count before the first change in this game process
write inventory=default                                        every count changed in this game process back
```

- **Writable:** `quantity.held` and `quantity.stored` (section P2 says of which items). `quantity` alone means `held`, as `runes` means
  `runes.total`.
- **Read-only:** `quantity.total` (computed: held + stored), `name`, `type`, `upgrade`, and the ids themselves (an id is not changed into
  another item).
- **`=default`:** the value the game had before the first change in this game process, kept with the params' snapshot
  (`<vault>\params-snapshot.json`, tied to the game's pid and start time).

## P2. What can be written (by kind)

| **Kind**                               | **`held`**                           | **`stored`**                     | **Why**                                                    |
|:---------------------------------------|:-------------------------------------|:---------------------------------|:-----------------------------------------------------------|
| goods (consumables, materials ...)     | 1 to the item's `maxNum`             | 1 to its `maxRepositoryNum`      | the game's own caps, read from the item's `EquipParamGoods` row |
| key items                              | 1 to `maxNum`                        | (none: key items are not stored) | the same row                                               |
| talismans, armor, ashes of war         | read-only                            | read-only                        | one of each is one item; a count of 2 is two items          |
| weapons: arrows and bolts              | (P5.3)                               | (P5.3)                           | stackable; their caps are not in a param field             |
| other weapons                          | read-only                            | read-only                        | each is its own item (its level, its affinity)              |

- **Only an entry that is already there** (the item is held, or stored) is changed: its quantity, the 4 bytes at +8. The handle, the id
  and the place in the menu are not touched (P5.1: adding an item the character does not have).
- **Never 0:** a count is 1 or more; taking the last one out (an entry with 0) is not how the game removes an item (P5.2).
- A value out of range is an error (exit `2`, nothing written), not a clamp, as the params.

## P3. How a write is made safe

1. The session check, the gate, the record of the first value (for `=default`), as every write.
2. The entry is found **again** just before the write: the list read now, the entry with that kind and id, its handle and id as they were
   when the value was planned. If it moved (the game sorted or used the item meanwhile), the write is not made and the reason is shown.
3. One aligned 4-byte write, read back. A count that the game changed between the read and the write (an item used in that moment)
   is reported, not overwritten blindly.

## P4. The save and the vault

The inventory is part of the save: when the game saves (it does so often), a changed count goes into `ER0000.sl2`. That is why
writing it is a portal write, like `runes` and `level`:

- **Vault ON** (`run`): the vault puts the save back when the session ends; the counts written are gone with it, the real world is
  as it was. `vault keep` takes the changed save as the new baseline (the author's choice, `--yes`).
- **Vault OFF**: nothing is written (the portal is closed), as every write.

## P5. Decided by the author (2026-10-15: the three defaults)

1. **Adding an item the character does not have** (a goods or a talisman: their handle is their id): a new entry in an empty place,
   with a place in the menu and the list's count of items. Where the game keeps that count and the next place number is not measured
   yet (a probe in the game first). Default: **not in part 2**; only counts of what is already there.
2. **Removing an item** (`held=0`): the game clears the entry and its place; doing that by hand risks a half-removed item in the save.
   Default: **refused**; `held` is 1 or more.
3. **Arrows and bolts**: change their count too (caps by the game's rules: 99 held per kind ... to be measured), or leave them
   read-only. Default: **read-only in part 2**.

## P6. Tests

- A fake game with the three lists: `held`/`stored` written for goods and key items, the caps from a fake `EquipParamGoods` row, values
  out of range refused, read-only kinds and fields refused with the reason.
- The entry found again before the write: moved, used up or changed meanwhile, nothing written.
- `=default` and `inventory=default` from the snapshot; the session check and the gate, as every write; a script's `tools.write`.

`tests/test_inventory_write.py`: held, stored and a key item written and put back; only the 4 bytes of the quantity change; twelve
refusals (a cap, 0, total, a name, a talisman, a weapon, a key item stored, an item not held, an item only in the chest written as held,
not a number, an unknown name); by name; an entry that changed meanwhile; no session; a script's `tools.write`.

## P7. Implemented (2026-10-15)

- `writer/inventoryedit.py`: `resolve` (a path or an item's name -> kind, id, held or stored, with every refusal of P2), `check_value`
  (1 to the cap of the item's `EquipParamGoods` row), `find_entry` (the one entry of that id in the list, read now), `apply` (the entry
  read again just before the write: unchanged, or nothing is written; 4 bytes written and read back; the first value remembered under
  `inventory.<held|stored>.<kind>.<id>` in the params' snapshot), `write_counts` (all names and values checked before the first write).
- `write` (`commands/write.py`) and a script's `tools.write` (`creative/scripts/backend.py`) both go through `write_counts`, after the
  session check and with the open gate; `params=default` leaves the inventory's values alone, `inventory=default` puts them back.
- `write` alone lists the inventory's names.

# Part 3: optimization of parts 1 and 2 (2026-10-16)

Asked by the author once parts 1 and 2 passed in the game. Rule, as in 1.8.0 part 3: nothing that keeps a read correct or a write safe is
made weaker (every list still read whole and checked entry by entry, every write still finds its entry again).

## O1. Measured (before)

| **What**                                                    | **Time**             | **Where it goes**                                                     |
|:------------------------------------------------------------|---------------------:|:----------------------------------------------------------------------|
| a `read` that shows the inventory (`read inventory...`)     | about 0.95 s         | the look for the text tables and their array for the names: 0.5 s + 0.3 s of memory read (the logs of 2026-10-15), at every command |
| a `write` of a count by an item's name                      | about 1 s            | the same look                                                          |
| reading the three lists (5,000 places), once a second       | 2.7 ms               | a struct unpack of three words per place                              |

## O2. Made quicker

| **What**                                   | **Before**          | **After**                                         | **How** |
|:-------------------------------------------|--------------------:|--------------------------------------------------:|:--------|
| the item names in a later command          | about 1 s           | three small reads, then the name tables (a few hundred KB) | the array of the text tables is remembered for the game process (`%LOCALAPPDATA%\EldenDisk\text-array.json`: the game's pid and start time, the array's address); a later command only checks that it still points at the tables the profile's `name_files` / `name_sizes` say, and looks again when it does not (another game process, a moved array) |
| reading the three lists                    | 2.7 ms              | 1.0 ms                                            | the entries checked on 32-bit words of one view of the bytes (the same checks as `entry`; a profile whose offsets are not 4-byte aligned keeps the old way) |

`read -v` says in the log how long the names took (`item names: N in X s`), so the first command of a game process (the look) and the
later ones (the remembered array) can be told apart in a game's log.

## O3. Not changed

- `read hp`, `read disk.character.level` and every `read` that does not show the inventory already read neither the lists nor the names
  (part 1, section 3).
- The goods' types: one read of the `goodsType` field of EquipParamGoods per command (the decoder of 1.8.0 part 4 for that field only).
- A write: the inventory read once, the entry found again before each write; already a few milliseconds.

## O4. Tests

`tests/test_inventory.py`: the array found once per game process and only checked after (another game process or an array that no
longer holds: looked for again); the quick parse gives what `entry` gives.

> [!NOTE]
> **Version:** `1.8.2` (fix)  
> **Status:** IMPLEMENTED (closed). Tried in the real game on 2026-10-17: `read disk.character.buffs.*` named 5 buffs by their items (Gold-Pickled Fowl Foot with its times, Gold Scarab and three more talismans), `read monitor-buffs` showed mapped and unmapped together; passed. The author's decisions: section 7.  
> **Last Updated:** _2026-10-17_

# Elden-Disk spec 1.8.2: `character.buffs` from the inventory

Reads on top of [spec 1.8.1](elden-disk-spec-v1.8.1.md). Only what changes is written here.

## 1. Idea

Asked by the author (2026-10-16). Until now a buff is named by hand: the reader reads the active effects of the character (an
SpEffect id, its duration and its timer), looks the id up in the `buffs` section of `names.json`, and shows the ones it finds
(`name`, `categories`, `abilities`, and `times` for a timed one); every other id is counted in `systems.status.ignored.buffs`.

Since 1.8.1 the disk knows every item the character carries (`character.inventory`), and most buffs come from using or wearing one of
them. So a buff is named by **the item it comes from**: its object in `character.buffs` is that item's object of the inventory, with
`times` added for a timed buff. The `buffs` section of `names.json` goes; its `animations` section stays.

## 2. From an effect to an item

The game's own tables say which effect an item gives. Checked on the game's original 1.17.1 rows (2026-10-16):

| **Item**                 | **Field of its row**                                                       | **Example**                                             |
|:-------------------------|:---------------------------------------------------------------------------|:--------------------------------------------------------|
| goods (consumables ...)  | `EquipParamGoods.refId_default` when `refCategory` is 2 (an SpEffect)     | Gold-Pickled Fowl Foot 1200 → SpEffect 3971              |
| sorceries, incantations  | `Magic.refId1` ... `refId10` when the `refCategory` of the same number is 2 (the spell's goods id is its Magic id) | Flame, Grant Me Strength 6050 → 1605000 |
| talismans                | `EquipParamAccessory.refId` when `refCategory` is 2, and `residentSpEffectId1` ... `4` | Gold Scarab 1110 → 311100                |
| weapons                  | `EquipParamWeapon.residentSpEffectId`, `residentSpEffectId1`, `2` (the row: the weapon's id without its level) | |
| armor                    | `EquipParamProtector.residentSpEffectId`, `2`, `3`                          |                                                         |
| ashes of war             | `EquipParamGem.spEffectId0` ... `2`                                         |                                                         |
| through a bullet         | a `refCategory` of 1 (a Bullet): `Bullet.spEffectId0` ... `4` and `spEffectIDForShooter` of that row | Golden Vow 6600 → Bullet 10660000 → 1660000 (one step, not further) |

- **The index** is made from the items the character holds now (`quantity.held` 1 or more; the chest gives no buff): {SpEffect id →
  the items that give it}. It is made again only when the held items change (a count that changes is not a change). The rows are read
  from the game's tables once per table, only the fields above (`reader/buffitems.py`); a table is read again when a held item's row is
  not in it (a build added rows), at most every 10 s.
- **Not followed** (section 7.3): a bullet's next bullet (`HitBulletID`) and an SpEffect that starts another. Seen on the game's rows:
  Magic 6500 gives its SpEffect 1650000 only through the bullet after its first one, so that buff stays unmapped in 1.8.2.
- **A buff whose effect no held item gives** (a Site of Grace, an enemy's effect, the game's own effects, an effect an item gives
  through more than one step) is not named by an item: section 7.1.

## 3. In the disk

```json
"buffs": {
  "3971": {
    "name": "Gold-Pickled Fowl Foot", "type": "consumable",
    "quantity": { "total": 562, "held": 10, "stored": 552 },
    "reference": ["character.inventory.goods.1200"],
    "times": { "buff_duration": 154.2, "max_duration": 180.0, "last_activated_at": "2026-10-16 15:20:01.123456+07:00" }
  },
  "311100": {
    "name": "Gold Scarab", "quantity": { "total": 1, "held": 1, "stored": 0 },
    "reference": ["character.inventory.talismans.1110"]
  }
}
```

- **The key** stays the effect's id (as today; `read monitor-buffs` shows the same ids).
- **The object** is the item's object of `character.inventory` (its `name`, `type`, `upgrade`, `quantity`, whatever that kind has),
  read in the same sample, so the two never disagree.
- **`reference`**: the path of every held item that gives this effect (a few greases or two talismans can give the same one); the object is
  the first one's, in the order goods, key items, talismans, weapons, armor, ashes of war.
- **`times`**: as before (`buff_duration`, `max_duration`, `last_activated_at`), only for a timed buff.
- `categories` and `abilities` go (they were the hand-written fields of `names.json`; `type` says the kind of a goods item).

## 4. `names.json`

- The `buffs` section is removed from `code/eldendisk/reader/names.json`; a `names.json` next to the exe that still has one: the
  section is not read (a note in the log once).
- `animations` stays as it is.
- The creative spells (`innovate-spells`): the copied SpEffect rows of a design's spell are given by the spell's goods item (its object
  and `reference`) when the character holds it, besides what its rows name (`spell_buffs` in place of `with_spell_buffs`).

## 5. The monitors

- `read monitor-buffs` (and `read monitor`): an id is **mapped** when a held item gives it, and shown with that item's name; the others
  are `Unknown` ("no held item gives it").
- **Both kinds by default** (asked by the author, 2026-10-16), for `read monitor`, `monitor-buffs` and `monitor-animations`: as if
  `--mapped --unmapped` were given. `--mapped` alone shows only the mapped ids, `--unmapped` alone only the others; the two together are
  the default (they were one or the other before).
- `names.json` is still re-read while a monitor runs, for the animations.

## 6. Failures

| **What**                                         | **Then**                                                                 |
|:-------------------------------------------------|:-------------------------------------------------------------------------|
| no `inventory` block, or the inventory cannot be read | every buff is unmapped (section 7.1); the character is read as always |
| an item's row cannot be read                     | that item gives no buff in the index; the others do                       |

## 7. Decided by the author (2026-10-16)

1. **A buff no held item gives:** left out of `character.buffs` and counted in `systems.status.ignored.buffs`
   (`read monitor-buffs --unmapped` shows it).
2. **The paths of the items:** kept, named **`reference`** (not `from`).
3. **An effect given through more than one step:** not followed in 1.8.2 (one step: an item's row, and a Bullet it names).
4. **The monitors:** both kinds by default (section 5).

## 8. Tests

`tests/test_buff_items.py`:

- The index from fake rows of each kind (goods, a spell, a talisman, a weapon without its level, armor, an ash of war, a bullet step);
  the chest gives none; a `refCategory` 0 (an attack) is no buff.
- A buff named by its item, with the item's object and `times`; two items giving one effect (`reference` both); an effect no item gives.
- The index made again only when the held items change; a table read once and again only for a row it lacks, after a while; no tables:
  every buff unmapped, the rest read; a design's spell; the game's tables end to end.

`tests/test_disk.py`, `test_ledger.py`, `test_read_command.py`, `test_main.py`: `names.json` without `buffs`, and one with it (not
read); the animations unchanged; the monitors' mapped, unmapped and both (the default).

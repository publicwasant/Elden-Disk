> [!NOTE]
> **Version:** `1.8.1`  
> **Status:** IMPLEMENTED (closed; unit tests: 1,770+). Tried in the real game on 2026-10-15: `probe inventory`, `read inventory`,
> `export --disk`, the counts (held and stored) and the names.  
> **Last Updated:** _2026-10-15_

**Summary:** **What the character carries.** `character.inventory`: every item the Inventory menu shows (goods, key items, talismans,
weapons with their level, armor, ashes of war), each with its id, its name in the game's language and how many, read-only, about once
a second. `read inventory.gold_pickled_fowl_foot.quantity` gives one count by the item's name.

_(baseline: **[changes-version-1.8.0.md](changes-version-1.8.0.md)**; design: **[elden-disk-spec-v1.8.1.md](../specs/elden-disk-spec-v1.8.1.md)**)_

| # | Change | Where |
|:-:|:---|:---|
| 1 | **`character.inventory`**: two lists of PlayerGameData (the items behind the pointer at +0x418, 2,688 places; the key items at +0xB10, 384), 24-byte entries (handle, id, quantity, place); an entry is an item only when its kinds agree; an id in two places is one item with the quantities added. Grouped as `goods` (with `type`, from `EquipParamGoods.goodsType`), `key_items`, `talismans`, `weapons` (with `upgrade`), `armor`, `ashes_of_war`. | `game/inventory.py`, `reader/sampler.py`, `disk.schema.json` |
| 2 | **Read about once a second**, and only when the command shows it (`read hp` reads neither the inventory nor its names). | `reader/sampler.py`, `commands/read.py` |
| 3 | **The names** from the game's own text in memory (`text.names`: the name tables of goods, weapons, armor, talismans and ashes of war, the DLC's last), found once per command or game process. The look for the text tables moved from the writer to the game package. | `game/textmem.py`, `game/scan.py` (was `writer/scan.py`), `writer/text.py` |
| 4 | **By name**: `read inventory.<name>` / `disk.character.inventory.<name>` finds the item in any kind (`smithing_stone_1`). | `reader/view.py`, `game/values.py` |
| 5 | **`probe inventory [--find ID ...]`**: where the inventory is, how an entry is laid out, the bytes around it (read-only). | `game/invprobe.py`, `__main__.py`, `commands/read.py` |
| 6 | **The profile**: the `inventory` block, `text.names`. | `offsets.json`, `game/profile.py` |
| 7 | **Tests** (`test_inventory.py`, `test_inventory_probe.py`); spec 1.8.1. | `tests/`, `docs/` |
| 8 | **Found in the game**: the read handle could not list the game's memory regions (`regions` was the writer's; the read handle now asks for `PROCESS_QUERY_INFORMATION` too, read-only); the names' array is found by tables a build never replaces (`text.name_files`); a look for the names that fails never stops `read`, and `read` says why the names are missing. | `game/memory.py`, `writer/writer.py`, `game/textmem.py`, `reader/sampler.py`, `commands/read.py` |
| 9 | **Held and stored**: `quantity` is `{total, held, stored}` (the author's shape): `stored` from the storage chest (`[[PlayerGameData+0x5F0]+0x8]+0x6020`, 1,920 places, the same entries), an item only in the chest listed with `held` 0, `total` computed. | `game/inventory.py`, `game/profile.py` (a list reached by a chain of pointers), `offsets.json`, `disk.schema.json` |

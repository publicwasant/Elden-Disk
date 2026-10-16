> [!NOTE]
> **Version:** `1.8.2` (fix)  
> **Status:** IMPLEMENTED (closed; unit tests: 1,810). Tried in the real game on 2026-10-17 and passed; no further optimization needed (`read disk.character.buffs.*` in about 0.4 s, attach included).  
> **Last Updated:** _2026-10-17_

**Summary:** **A buff is named by the item that gives it.** `character.buffs` no longer needs names written by hand in `names.json`: the
game's own tables say which SpEffect each item gives, so a buff is the object of the held item in `character.inventory` (its name in the
game's language, its type, its quantity) with `reference` and `times`. The monitors show the mapped and the unmapped ids together by
default.

_(baseline: **[changes-version-1.8.1.md](changes-version-1.8.1.md)**; design: **[elden-disk-spec-v1.8.2.md](../specs/elden-disk-spec-v1.8.2.md)**)_

| # | Change | Where |
|:-:|:---|:---|
| 1 | **`character.buffs` from the inventory**: an index {SpEffect id: the held items that give it} from the game's rows (goods `refId_default` / `refId_1`, a spell's Magic row, talismans' `refId` and resident effects, weapons' (by row, without the level), armor's and ashes of war's resident effects; a Bullet one step), read once per table and made again only when the held items change. | `reader/buffitems.py` (new), `reader/sampler.py` |
| 2 | **The buff object**: the item's object of `character.inventory` (`name`, `type`, `upgrade`, `quantity`), `reference` (the inventory paths of every held item that gives it), `times` for a timed buff; `categories` and `abilities` are gone. A buff no held item gives is counted in `systems.status.ignored.buffs`. | `reader/sampler.py`, `disk.schema.json` |
| 3 | **`names.json`: animations only.** Its `buffs` section removed; one left in a file next to the exe is not read (a note in the log). | `reader/names.json`, `game/profile.py` (`StateIds`), `commands/read.py`, `commands/scripts.py` |
| 4 | **The design's spells**: their copied SpEffect rows are given by the spell's goods item when it is held (`spell_buffs` in place of `with_spell_buffs`). | `creative/scripts/backend.py`, `commands/read.py` |
| 5 | **The monitors**: both kinds by default (`--mapped --unmapped`); `--mapped` or `--unmapped` alone filters; a buff is mapped when a held item gives it, shown with the item's name. `read character.buffs...` / `systems...` read the inventory too. | `commands/read.py`, `__main__.py`, `reader/buffs.py`, `reader/monitor.py` |
| 6 | **Docs**: the CLI guides, the profile handbook. | `docs/guilde/cli-commands*.md`, `docs/guilde/README-exe.md`, `docs/handbook/adding-a-profile.md` |

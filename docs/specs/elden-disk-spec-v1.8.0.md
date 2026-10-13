> [!NOTE]
> **Version:** `1.8.0`  
> **Status:** DRAFT. Nothing implemented. Section 12 lists the read-only checks in the real game that must pass before any code.  
> **Last Updated:** _2026-10-13_

# Elden-Disk spec 1.8.0: `resurrect-unit great-enemies`

Reads on top of [spec 1.7.2](elden-disk-spec-v1.7.2.md). Only what changes is written here. The research is in the thread notes
`research-1.8.0-resurrect-great-enemies.md` (2026-10-13).

## 0. `extension` is `design` now (2026-10-13)

Before any of the rest, the word `extension` is gone from the tool: what it builds and runs next to the game is the **design**.

| Before (1.7.x) | 1.8.0 |
|:--|:--|
| `eldendisk extension --list` | `eldendisk design` (`--list` still accepted) |
| `eldendisk extension innovate-items spells ...` | `eldendisk innovate-items spells ...` |
| `eldendisk extension external-scripts ...` | `eldendisk external-scripts ...` |
| `--extension-dir DIR` | `--design-dir DIR` |
| `code/extension.json` (and next to the exe) | `code/design.json` |
| `code/eldendisk/extension/` | `code/eldendisk/design/` |
| `<vault>\extension\` | `<vault>\design\`: an older vault's folder is renamed once, the first time a command needs it (the builds, the secured file and the scripts' status keep working) |
| the document's block `extension.innovate_items...` (read, write, `tools.read()`) | `design.innovate_items...` |
| buffs of the design's spells: category `EXTENSION` | `DESIGN` |
| `ExtensionError`, `ExtensionLive`, `EXT_TAG`, tests `test_ext_*` | `DesignError`, `DesignLive`, `DESIGN_TAG`, `test_design_*` |

The log tag was `design` already. A `design.json` the user keeps next to the exe must be renamed by hand (an `extension.json` there is no longer read).
The versioned specs, changes and manual plans of 1.7.x keep the words of their time.

## 1. Idea

A boss you have beaten stays dead. 1.8.0 brings it back for one session, so you can fight it again (for practice, for a video, for its
drop) without touching your real playthrough:

```text
eldendisk resurrect-unit great-enemies --activate margit godrick
 ✓  design  2 great enemies alive again; each appears when its area loads (travel there, or rest away and come back)
   Margit, the Fell Omen        Stormveil Castle · Limgrave      grace: Castleward Tunnel    12,000 runes · Talisman Pouch
   Godrick the Grafted          Stormveil Castle · Limgrave      grace: Secluded Cell        20,000 runes · Remembrance of the Grafted
 !  design  Godrick the Grafted is a story boss: what his death started (his Great Rune, the people who speak of him) may look
            odd until the game closes; the vault puts your save back then
```

**Principle (spec 1.7.0, section 1): the other world never touches the real one.** The game remembers a defeated boss in an *event flag*
of the save. 1.8.0 turns those flags off **in the game's memory only**, inside a session `run` started with the vault ON. When the game
closes, the vault puts the save back byte for byte: the boss is dead again, and the runes and the items the second fight gave are gone.
Nothing is written to any file. There is no warp and no window: the tool says where the boss is, you travel there (CLI only, by design).

**A great enemy** is every enemy that is fought under the big health bar at the bottom of the screen: every row of the game's
`GameAreaParam` with a defeat flag. In 1.17.1 that is **212** (40 of them in Shadow of the Erdtree).

## 2. What brings a boss back (the game's own rules)

| What | In the game | 1.8.0 |
|:--|:--|:--|
| **Defeated** | `GameAreaParam.defeatBossFlagId` (for example `10000850`, Margit) is ON. The event script of the boss's map reads it **when the map loads**: ON = the boss and its fog are left out. | turned **OFF** |
| **Its drop** | the item lot given at the defeat (the Remembrance, a key item, a weapon) has its own flag: ON = already given. In the legacy dungeons the lot has the boss's id and the flag is the defeat flag with `7` for its fourth last digit (Godrick: lot `10000800`, flag `10007800`). | turned **OFF**, so the drop comes again |
| **First encounter** | the intro cutscene plays once: a flag of the boss's map event remembers that it played. | turned **OFF**, so the cutscene plays again |
| **Runes** | `GameAreaParam.bonusSoul_single` is given by the game at every defeat. | nothing to do |
| **Play log, achievements** | `61xxx` / `9xxx` flags ("boss defeated" for the play log); a Steam achievement stays earned. | **never touched** |

The boss appears **when its area loads** again: travel to any grace, or rest at a grace away from it and come back. A boss whose area is
loaded while its flag is turned off (the player stands in it) appears only after the next load; the console says so (section 6).

## 3. The event flags in memory

From the game's own structure (`CSEventFlagMan`, whose first member is `CSFD4VirtualMemoryFlag`; the layout is the one of the MIT crate
`eldenring`, `cs/event_flag.rs`; to be confirmed on 1.17.1, section 12):

```text
CSFD4VirtualMemoryFlag
  +0x1C u32 divisor            1000: a group of flags is flag // 1000
  +0x20 u32 holder size        125: the bytes of one group (1000 flags)
  +0x24 u32 holder count
  +0x28 ptr blocks             the groups laid one after another
  +0x30     the descriptors    a tree (std::map) group -> FlagBlockDescriptor
FlagBlockDescriptor { u32 mode; union { u32 index; ptr block } }
  mode 1: blocks + index * 125        mode 2: the block's own pointer        other: the group is not held (refused)
bit of a flag: byte (flag % 1000) // 8 of the block, bit 7 - (flag % 8)      (the highest bit first)
```

- `game/eventflags.py` (new, read-only): finds the manager (the profile's `event_flags` block, section 9), checks it (`divisor` 1000,
  `holder size` 125, else refused with what was read), walks the tree **once per game process and world load** to find the block of each
  group it is asked about, and reads a flag. A block address is kept until the next load screen; before it is used again the manager is
  checked again (same divisor and size, the same tree root).
- `writer/eventflags.py` (new): changes **one bit** of a block, reads the byte back, and refuses any flag that is not in the great-enemies
  table (section 4): there is no general event flag writer. It goes through the session gate like every write (`WriteGate`, the session
  `run` started, the game offline).
- Flags are written by the game too (a boss dying sets its flag). The tool writes one byte at a time and reads it back; the window is a
  few microseconds and only bits of a boss that is dead are changed.

## 4. The great-enemies table

`code/eldendisk/design/resurrect_unit/great_enemies/great_enemies.json` (embedded in the exe like `design.json`, about 30 KB), one
entry per great enemy, keyed by its `GameAreaParam` row id (the defeat flag, runes, map and drop flag below are the game's; the grace id
and the cutscene flag are illustrative until the generator writes them):

```json
"10000850": {
  "name": "Margit, the Fell Omen",
  "aliases": ["margit"],
  "place": "Stormveil Castle", "region": "Limgrave", "map": "m10_00_00",
  "flags": { "defeated": 10000850, "drop": [10007850], "cutscene": [10000851] },
  "runes": 12000,
  "drop": ["Talisman Pouch"],
  "grace": { "id": 10002, "name": "Castleward Tunnel" },
  "story": false,
  "dlc": false
}
```

- **Made by a developer tool, checked by tests, never by hand alone.** `tools/gen_great_enemies.py` (not shipped) reads the game's own
  `regulation.bin` (`GameAreaParam`, `BonfireWarpParam`, `ItemLotParam_map`, `ItemLotParam_enemy`) and, for names, the game's text
  (`PlaceName`, `GoodsName`, `WeaponName`... through `tools/gamearchive.py`, read-only) and writes the table. The boss names are written by
  us in English (the game has no link from a `GameAreaParam` row to a name); Paramdex's list of row names is only a reference, it is not
  copied (its license is not clear).
- **The nearest grace** is the `BonfireWarpParam` row closest to `bossPos`, in world coordinates (a map tile `m60_XX_YY` is 256 m;
  `m61` the same), **not the grace in the arena that is lit after the fight**: a grace whose `clearedEventFlagId` is the boss's defeat flag
  is left out (to be confirmed by the generator on all 212, section 12). The name is the grace's `textId1` in `PlaceName`.
- **The drop flags** are the flags of the item lots given at the defeat: the lot with the boss's id (legacy dungeons, 38 found), else the
  lots of the boss's `NpcParam` (`ItemLotParam_enemy`), else none (the console says `drop: (unknown)`; the fight still works).
- **The cutscene flags** come from the boss's map event script (`emevd`, read by the generator from the game's archives); a boss without
  an intro has none.
- **`story: true`** (the list accepted by the author on 2026-10-13) for the bosses whose death the story waits on (Margit, Godrick, Rennala, Radahn, Morgott, Rykard, Malenia, Mohg, the
  Fire Giant, Godskin Duo, Maliketh, Gideon, Godfrey/Hoarah Loux, Radagon and the Elden Beast, Messmer, Romina, Midra, Bayle, Consort
  Radahn...; the list is part of the table and reviewed with it).
- **Tests** (golden, with `ELDENDISK_REGULATION_ORIG`): every entry's defeat flag, runes, map and position are the game's; every
  `GameAreaParam` row with a defeat flag has an entry; every drop flag is the flag of a lot the boss gives; every grace exists and is not
  an arena grace. A table that does not match the game's file is a failed test, not a warning.

## 5. Command

```text
eldendisk resurrect-unit great-enemies --list [--defeated | --alive] [--area NAME] [--story] [--dlc] [--json]
eldendisk resurrect-unit great-enemies --activate NAME|ID [NAME|ID ...]
eldendisk resurrect-unit great-enemies --activate --all          (or `*`, or `all`: every great enemy that is defeated)
eldendisk resurrect-unit great-enemies --when-loaded             (what `run` starts: the design's list, section 7)
```

| Option | Does |
|:--|:--|
| *(none)* | where the table comes from, how many great enemies, and the design's list |
| `--list` | one row per great enemy: id, name, place · region, grace, runes, drop, story/DLC marks. With a session and a character in the world, also `defeated` / `alive` (read from the game); without one, the table only |
| `--defeated`, `--alive` | only those (needs the game) |
| `--area NAME` | only those whose place or region matches (`limgrave`, `stormveil`, `caelid`, `catacombs`) |
| `--story`, `--dlc` | only story bosses / only Shadow of the Erdtree |
| `--json` | the rows as JSON on stdout (for other tools) |
| `--activate NAME\|ID ...` | brings them back (section 6) |
| `--all`, `*`, `all` | every great enemy that is defeated now; stands alone |

**Names.** A great enemy is named by its id (`10000850`) or by its name, in any letter case, without punctuation: `margit`,
`"Margit, the Fell Omen"`, `fell omen`, an alias of the table. A name that fits several (`dragonkin soldier`: three) is refused with the
list of what it fits (`dragonkin soldier: 3 great enemies: 12010800 Dragonkin Soldier of Nokstella, 12010850 Dragonkin Soldier (Lake of
Rot), 12020830 Dragonkin Soldier of Nokron; name one`); a name that fits none gets the closest names. Nothing is written when any name is
wrong.

**Needs:** the game `run` started with the vault ON, a character in the world, and the profile's `event_flags` block. `--list` without
them shows the table. Exit codes: `0` done (also when every boss named was alive already), `1` a wrong name or a flag that did not stick,
`2` this game version has no `event_flags` block, `5` no valid session (as `write`).

## 6. `--activate`: what happens

For every great enemy named, in the order given:

1. **read** its defeat flag. OFF: `already alive` (nothing written).
2. **write** OFF: the defeat flag, its drop flags, its cutscene flags; each read back. One that does not stick: that boss is reported
   `not resurrected` with the flag, the ones written before stay written (they are harmless alone: the vault restores the save), exit `1`.
3. **say** the result, one line per boss (section 1): name, place · region, nearest grace, runes, drop. If the boss's map is the one the
   player is in now: `you are in its area: it appears after the next load`.
4. a story boss: the warning of section 1, once per command.

`--all` asks nothing more: the console says how many and that the vault restores the save; the session is the confirmation.

## 7. In the design: `design.json`

```json
"resurrect_unit": {
  "great_enemies": {
    "__info__": "Brought back at every run, once a character is in the world (memory only; the vault restores the save).",
    "activate": ["margit", "10000800"]
  }
}
```

`"activate": "all"` (or `"*"`) brings every defeated great enemy back. The names are checked like the command's when the design is read
(a wrong name is an error of the design, named where it is written, as in 1.7.1). With the vault ON and a list in the design, `run` starts
`eldendisk resurrect-unit great-enemies --when-loaded` as a step of its own, like the text and colour steps: it waits for a
character in the world, activates the list once and ends. The list is not part of the regulation build: changing it rebuilds nothing.
`spells.schema.json`'s sibling `resurrect_unit.schema.json` describes the block.

## 8. Read and write: `design.resurrect_unit.great_enemies`

The document (`read`, `--export`, `tools.read()`) has a block next to the spells:

```text
design.resurrect_unit.great_enemies.<id>
  name, place, region, grace, runes, drop, story, dlc     from the table
  defeated                                                from the game (null without a character in the world)
```

- `read --query "design.resurrect_unit.great_enemies.10000850.*"`, and the boss by its name like a spell by its label
  (`...great_enemies.margit.defeated`).
- **Write:** only `defeated`, only to `false`: `write --set design.resurrect_unit.great_enemies.margit.defeated=false` or
  `x....great_enemies.margit.defeated = False; tools.write(x)`. It is `--activate` for that boss (section 6). `true` is refused (`only the
  game marks a great enemy defeated`); the other fields are the table's.
- **Cost:** the flags are read only when the block is asked for (`read` with no flag shows the count of defeated great enemies; `--query`
  and `tools.read()` read what the name asks). All 212 flags lie in about 170 groups; reading every group once is about 170 reads of 125
  bytes (to be measured, section 12; the goal is under 5 ms per read). The block addresses are kept per load (section 3).
- An external script can make a boss rush: when `defeated` of the boss of the arena turns `true`, write it `false`, and the next load
  brings it back.

## 9. The profile: `event_flags`

```json
"event_flags": { "man_rva": "0x...", "divisor": 1000, "holder_size": 125 }
```

Optional like `text` and `equipment`. Absent = unsupported for that exe: `--activate`, `--list --defeated|--alive` and the `defeated`
values say so (exit `2`); the table is still shown. `divisor` and `holder_size` are what the manager must hold; a manager that holds other
values is refused with what it holds (a new game version moved it). `docs/handbook/adding-a-profile.md` gets the block and how it was found.

## 10. Layout

```text
code/eldendisk/design/resurrect_unit/
 ├─ __init__.py
 └─ great_enemies/
     ├─ great_enemies.json        the table (section 4), embedded in the exe by dev_pipeline
     ├─ table.py                  loads and checks the table; names -> ids (standard library only, like the other design packages)
     └─ resurrect_unit.schema.json   the design block (section 7)
code/eldendisk/game/eventflags.py      the manager, the tree, reading a flag (read-only)
code/eldendisk/writer/eventflags.py    one bit off, read back, only the table's flags
code/eldendisk/commands/resurrect.py   the command (section 5) and the `run` step (section 7)
code/tools/gen_great_enemies.py        the table from the game's files (developer tool, not shipped)
```

The design package touches no game memory (`test_architecture.py`); the command and the scripts' backend do, through
`game/eventflags.py` and `writer/eventflags.py`. The console and the log tag is the design's own, `design` (`logbook.DESIGN_TAG`; decided 2026-10-13).

## 11. Failures

| Case | What is said |
|:--|:--|
| no session / vault OFF | as `write`: refused, exit `5` |
| no character in the world | `waiting for a character in the world` with `--when-loaded`; else refused, exit `1` |
| no `event_flags` block | `this game version has no event_flags block in offsets.json`, exit `2` |
| the manager holds other values | `the event flag manager at ... holds divisor ..., size ... (expected 1000, 125): this game version moved it`, exit `2` |
| a group the game does not hold (mode not 1 or 2) | that boss: `its flags are not held by the game now (an area not loaded yet?)`, the others go on, exit `1` |
| a wrong or ambiguous name | the list of what it fits or the closest names; nothing written, exit `1` |
| a flag that does not stick | that boss `not resurrected` with the flag and the byte read back, exit `1` |

## 12. Before any code: checks in the real game (read-only first)

1. **The manager** on 1.17.1: find `CSEventFlagMan` (a pointer in the exe's data to an object with `+0x1C` = 1000 and `+0x20` = 125;
   compare with the AOB of the cheat tables) and note its RVA for the profile.
2. **The tree:** walk it; the number of groups; the mode of each (1 or 2).
3. **Known flags:** read `10000800` (Godrick) and `10000850` (Margit) on the author's character; they must say what the game shows.
4. **Cost:** time to read the groups of all 212 bosses.
5. **The generator, offline:** the nearest graces of all 212 (and that `clearedEventFlagId` marks the arena graces), the drop lots, the
   cutscene flags from the map scripts.
6. **Then one write, in a vault-ON session:** a catacomb boss the author has beaten: `--activate`, travel, fight: the boss, the cutscene
   (if it has one), the drop, the runes. Then Margit. Then close the game: the save restored byte for byte, the boss dead again.

Each result goes into this spec (section 13) before the code that depends on it is written.

## 13. Measured

_(empty until section 12 is done)_

## 14. Not done (decided)

- **No warp and no window.** The tool is CLI only; it prints where the boss is and the nearest grace, the player travels (ER's travel is
  quick). Calling the game's warp would need code in the game, which the tool never runs.
- **Never marks a boss defeated** (`defeated = true` is refused; agreed 2026-10-13) and never touches the play log or achievement flags.
- **No other flags.** Only the flags of the table can be written; there is no general event flag editor.
- Enemies without the big health bar (the field's elite enemies, the NPC invaders) are not great enemies.

## 15. Tests

`test_great_enemies_table.py` (the table loads, names and aliases resolve, ambiguous names refused, every flag in range; golden: the table
agrees with the game's file, section 4), `test_eventflags.py` (the tree walk, modes 1 and 2, the bit order, a moved manager refused, on a
fake memory built like the game's), `test_resurrect_command.py` (--list with and without the game, --activate: already alive, written and
read back, a flag that does not stick, a wrong name writes nothing, --all, the story warning, the `run` step), additions to
`test_extension_live.py` (the block in read, `defeated=false` written, `true` refused), `test_profile_policy.py` (`event_flags`),
`test_architecture.py`, `test_dev_pipeline.py` (the table embedded).

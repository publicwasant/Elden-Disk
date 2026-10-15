> [!NOTE]
> **Version:** `1.8.0`  
> **Status:** Part 1 IMPLEMENTED (unit tests; the checks of section 12 passed in the real game on 2026-10-13: the event flags found and
> read, Mohg brought back with his intro, runes and Remembrance, the save restored byte for byte). Part 2 IMPLEMENTED on 2026-10-14 (unit
> tests: 1,700+; not yet tried in the game): the commands, the names and the document as Part 2 says; the notes at its end say what the
> code decided where Part 2 left a choice. Part 3 (optimization) IMPLEMENTED on 2026-10-15 for what needs no decision and no
> game; the rest is listed there. Part 4 (every param table in the disk) IMPLEMENTED on 2026-10-15; the walk of the list checked in
> the game the same day (`probe`: 194 tables, every one named).  
> **Last Updated:** _2026-10-15_

# Elden-Disk spec 1.8.0: `resurrect great-enemies`

Reads on top of [spec 1.7.2](elden-disk-spec-v1.7.2.md). Only what changes is written here. The research is in the thread notes
`research-1.8.0-resurrect-great-enemies.md` (2026-10-13).

# Part 1: `resurrect great-enemies` (as first built, 2026-10-13)

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
eldendisk resurrect great-enemies --activate margit godrick
 ✓  design  2 great enemies alive again; each appears once its area loads again: warp to another region, then come back
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
| **Its drop** | two ways (section 13). **The Remembrance** (and the main drop of 50 bosses): the defeat event sets the boss's play-log flag (`9xxx`, Godrick `9101`), and the game's common event 1100 gives a lot when that flag turns ON (Godrick: lot `10010`, the Remembrance of the Grafted; the lot's flag `510010` = given). **Other drops** (90 bosses): the boss's own events give a lot (`AwardItemsIncludingClients`), flagged by the lot. | the play-log flag and the lot flags turned **OFF**, so the next defeat gives them again |
| **First encounter** | the intro cutscene plays once: a flag of the boss's map event remembers that it played. | turned **OFF**, so the cutscene plays again |
| **Runes** | `GameAreaParam.bonusSoul_single` is given by the game at every defeat. | nothing to do |
| **Achievements** | `61xxx` flags ("boss defeated" for the achievements); a Steam achievement stays earned. | **never touched** (the `9xxx` play-log flag is turned off with the drop, above; the next defeat sets it again) |

The boss appears **when its area loads** again: warp to a grace in another region, then come back (seen with Mohg on 2026-10-13:
walking to the arena, or staying in the area, was not enough; after a warp to another region and back he was there). The console
says so after every `--activate` (section 6).

## 3. The event flags in memory

From the game's own structure (`CSEventFlagMan`, whose first member is `CSFD4VirtualMemoryFlag`; the layout is the one of the MIT crate
`eldenring`, `cs/event_flag.rs`; to be confirmed on 1.17.1, section 12):

```text
CSFD4VirtualMemoryFlag
  +0x1C u32 divisor            1000: a group of flags is flag // 1000
  +0x20 u32 holder size        125: the bytes of one group (1000 flags)
  +0x24 u32 holder count
  +0x28 ptr blocks             the groups laid one after another
  +0x30     the descriptors    a tree (std::map): +0x30 its allocator, +0x38 the head node, +0x40 the count; group -> FlagBlockDescriptor
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

`code/eldendisk/design/resurrect/great_enemies/great_enemies.json` (embedded in the exe like `design.json`, about 30 KB), one
entry per great enemy, keyed by its `GameAreaParam` row id (Margit's row as the generator wrote it from the game's files):

```json
"10000850": {
  "name": "Margit, the Fell Omen",
  "place": "Stormhill",
  "map": "m10_00_00",
  "flags": { "defeated": 10000850, "playlog": [9100], "drop": [60510], "cutscene": [10000851] },
  "runes": 12000,
  "drop": ["Talisman Pouch"],
  "grace": { "id": 100002, "name": "Castleward Tunnel", "meters": 59 },
  "story": true,
  "dlc": false
}
```

- **Made by a developer tool, checked by tests, never by hand alone.** `tools/gen_great_enemies.py` (not shipped) reads the game's own
  `regulation.bin` (`GameAreaParam`, `BonfireWarpParam`, `BonfireWarpSubCategoryParam`, `ItemLotParam_map`, `ItemLotParam_enemy`), the
  maps' event scripts and the game's text (through `tools/gamearchive.py`, read-only) and writes the table. The boss's name is the one
  its health bar shows (the NpcName text of the boss's `2003[11]` in its events): 196 of 212; the others are named by their id until a
  person names them in the tool's `OVERRIDES`. The place is the map menu's (`GR_MenuText` of the grace's sub-category).
- **The nearest grace** is the `BonfireWarpParam` row closest to `bossPos`, in world coordinates (a map tile `m60_XX_YY` is 256 m;
  `m61` the same), **not the grace in the arena that is lit after the fight**. The params do not mark that grace (section 13: no
  `clearedEventFlagId` is set) and it is usually the nearest one (Godrick 5 m: the grace "Godrick the Grafted"), so the generator leaves
  out the grace whose name is the boss's or that lies in the arena, proposes the next nearest, and the table's grace of every boss is
  reviewed once by a person; the golden test then keeps it. A boss whose map has no grace (13, for example the Chapel of Anticipation)
  gets the grace outside its entrance, written in the table by hand. The name is the grace's `textId1` in `PlaceName`.
- **The drop flags** come from the event scripts (section 13): the play-log flag the boss's defeat event sets (`9xxx`), the lot and lot
  flag the common event 1100 gives for it (`common.emevd` event 0 lists 68 such chains: play-log flag, lot, lot flag), and the flags of
  the lots the boss's own events give (`2003[36]` / `2003[4]`). A boss whose drop is not found: `drop: (unknown)` (the fight still works).
- **The cutscene flags** are the flags the boss's intro event sets after its cutscene (`2002[...]` then `2003[66/69] ON`), read from the
  map's event script: often the row's `foundBossFlagId` (Margit `10000851`), but not always (Mohg: `12050801` and `12050802`, his row
  says `30020800`, a flag many rows share). A boss without an intro has none.
- **`story: true`** (the list accepted by the author on 2026-10-13) for the bosses whose death the story waits on (Margit, Godrick, Rennala, Radahn, Morgott, Rykard, Malenia, Mohg, the
  Fire Giant, Godskin Duo, Maliketh, Gideon, Godfrey/Hoarah Loux, Radagon and the Elden Beast, Messmer, Romina, Midra, Bayle, Consort
  Radahn...; the list is part of the table and reviewed with it).
- **Tests** (golden, with `ELDENDISK_REGULATION_ORIG`): every entry's defeat flag, runes, map and position are the game's; every
  `GameAreaParam` row with a defeat flag has an entry; every drop flag is the flag of a lot the boss gives; every grace exists and is not
  an arena grace. A table that does not match the game's file is a failed test, not a warning.

## 5. Command

```text
eldendisk resurrect great-enemies --list [--defeated | --alive] [--area NAME] [--story] [--dlc] [--json]
eldendisk resurrect great-enemies --activate NAME|ID [NAME|ID ...]
eldendisk resurrect great-enemies --activate --all          (or `*`, or `all`: every great enemy that is defeated)
eldendisk resurrect great-enemies --when-loaded             (what `run` starts: the design's list, section 7)
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
"resurrect": {
  "great_enemies": {
    "__info__": "Brought back at every run, once a character is in the world (memory only; the vault restores the save).",
    "activate": ["margit", "10000800"]
  }
}
```

`"activate": "all"` (or `"*"`) brings every defeated great enemy back. The names are checked like the command's when the design is read
(a wrong name is an error of the design, named where it is written, as in 1.7.1). With the vault ON and a list in the design, `run` starts
`eldendisk resurrect great-enemies --when-loaded` as a step of its own, like the text and colour steps: it waits for a
character in the world, activates the list once and ends. The list is not part of the regulation build: changing it rebuilds nothing.
`spells.schema.json`'s sibling `resurrect.schema.json` describes the block.

## 8. Read and write: `design.resurrect.great_enemies`

The document (`read`, `--export`, `tools.read()`) has a block next to the spells:

```text
design.resurrect.great_enemies.<id>
  name, place, region, grace, runes, drop, story, dlc     from the table
  defeated                                                from the game (null without a character in the world)
```

- `read --query "design.resurrect.great_enemies.10000850.*"`, and the boss by its name like a spell by its label
  (`...great_enemies.margit.defeated`).
- **Write:** only `defeated`, only to `false`: `write --set design.resurrect.great_enemies.margit.defeated=false` or
  `x....great_enemies.margit.defeated = False; tools.write(x)`. It is `--activate` for that boss (section 6). `true` is refused (`only the
  game marks a great enemy defeated`); the other fields are the table's.
- **Cost:** the flags are read only when the block is asked for (`read` with no flag shows the count of defeated great enemies; `--query`
  and `tools.read()` read what the name asks). All 212 flags lie in 179 groups: read whole, 1.0 ms; one read per flag, 1.3 ms
  (measured, section 13). The block addresses are kept per load (section 3).
- An external script can make a boss rush: when `defeated` of the boss of the arena turns `true`, write it `false`, and the next load
  brings it back.

## 9. The profile: `event_flags`

```json
"event_flags": { "man_rva": "0x3D6C4B8", "divisor": 1000, "holder_size": 125 }        (1.17.1, found 2026-10-13, section 13)
```

Optional like `text` and `equipment`. Absent = unsupported for that exe: `--activate`, `--list --defeated|--alive` and the `defeated`
values say so (exit `2`); the table is still shown. `divisor` and `holder_size` are what the manager must hold; a manager that holds other
values is refused with what it holds (a new game version moved it). `docs/handbook/adding-a-profile.md` gets the block and how it was found.

## 10. Layout

```text
code/eldendisk/design/resurrect/
 ├─ __init__.py
 └─ great_enemies/
     ├─ great_enemies.json        the table (section 4); in the exe next to its package (dev_pipeline --add-data, also with --no-embed)
     └─ table.py                  loads the table; names -> ids; the design's list (standard library only)
code/eldendisk/game/eventflags.py      the manager, the tree, reading flags (read-only)
code/eldendisk/writer/eventflags.py    flags OFF only, read back, only the table's flags
code/eldendisk/commands/resurrect.py   the command (section 5); `run` starts it with --when-loaded (commands/run.py)
code/tools/gen_great_enemies.py        the table from the game's files (developer tool, not shipped)
```

The design package touches no game memory (`test_architecture.py`); the command and the scripts' backend do, through
`game/eventflags.py` and `writer/eventflags.py`. The console and the log tag is the design's own, `design` (`logbook.DESIGN_TAG`;
decided 2026-10-13). The names of the bosses, the graces and the drops are the game's own text (the health bar's name from the boss's
`2003[11]`, `PlaceName`, `GR_MenuText`, the item names), so the table has no list copied from elsewhere.

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

**Offline, the game's own regulation.bin (1.17.1), 2026-10-13 (check 5, the params part):**

- `GameAreaParam`: 216 rows of 96 bytes, **212** with a defeat flag (40 in the DLC maps). Ends of the defeat flags: `…800` 175, `…850`
  26, `…340` 4, `…830` 2, `…860` 2, `…810` 2, `…390` 1; 14 rows whose id is not their defeat flag (`30200800` → `30200810`).
- `BonfireWarpParam`: 422 graces (236 bytes a row). `clearedEventFlagId` is **0 on every grace**: the params do not say which grace a
  fight lights. The nearest grace is often the arena's own: Godrick 5 m ("Godrick the Grafted", grace 100000), Margit 12 m ("Margit, the
  Fell Omen", 100001), Radahn 4 m ("Starscourge Radahn", 64523800). Distance from a boss to the nearest grace of its map: median 116 m,
  90 % within 240 m, at most 908 m. 13 bosses have no grace in their own map (the Chapel of Anticipation, three catacombs, caves...).
- `ItemLotParam_map`: 37 bosses have a lot with their own id; 34 of those flag it as the defeat flag + 7000 (Godrick: lot 10000800,
  flag 10007800, Margit 10000850 → 10007850). The other 175 bosses' drops are given by event scripts.

**Offline, the map event scripts (`/event/<map>.emevd.dcx` from the game's archives, read-only), 2026-10-13 (check 5, the scripts
part):** 179 maps and `common_func` (257 events) read in 0.8 s after the archive indexes (28 s, once).

- **The cutscene flag is often `foundBossFlagId`, not always** (Mohg's intro, event 12052810, plays cutscene 12050020 and sets
  `12050801` and `12050802`; his row's `foundBossFlagId` is `30020800`). Margit's intro (event 10002860) plays cutscene 10000010 and then sets `10000851`
  (`2003[69]`), Godrick's (event 10002810) cutscene 10000020 and `10000801`: the row's `foundBossFlagId`. Turning it off plays the intro
  again; nothing more is needed from the scripts for it.
- **The defeat event sets the defeat flag and the play-log flags** (Godrick, event 10002800: `10000800`, `9101`, `61101`, and
  `10000802`; Margit, 10002850: `10000850`, `9100`, `61100`). The `61xxx` flags stay ON; the `9xxx` play-log flag is the trigger of the
  Remembrance (next point) and is turned off with the drop (section 2).
- **The drops** (corrected after a first look that missed them): the map defeat event gives no lot itself; it sets the boss's **play-log
  flag** (Godrick `9101`, Margit `9100`; 184 of 212 bosses set one), and `common.emevd` event 0 starts event 1100 once per Remembrance
  boss with (play-log flag, lot, 0, lot flag): Godrick `9101` -> lot `10010` (goods 2950, the Remembrance of the Grafted), flag `510010`;
  Margit `9100` -> lot `10000`, flag `60510`; Radahn `9130` -> `10300` / `510300`; Bayle `9163` -> `10630` / `510630`: 68 chains, 50
  bosses. Other drops are given by the bosses' own events with `AwardItemsIncludingClients` (`2003[36]`) or `AwardItemLot` (`2003[4]`):
  90 bosses (Rykard 16000800 -> lot 16000690; a field boss 1043360800 -> lot 30110). The lot that has the boss's id (Godrick's
  `10000800`, flag `10007800` OFF on a character that killed him) is not his drop. The NPCs of the bosses (map enemy lists, MSB, read by
  their entity) have no item lot of their own.

**In the game, read-only (checks 1-4), 1.17.1, the author's character in the world, 2026-10-13:**

- **The manager:** the one static of the exe's `.data` that points at an object shaped like `CSFD4VirtualMemoryFlag` (its vftable in the
  exe, `+0x1C` = 1000, `+0x20` = 125) is at **RVA `0x3D6C4B8`**: one candidate in 13.3 MB of `.data`, looked through in 1.9 s (once, by the
  developer; the tool reads the RVA from the profile). Its vftable is at RVA `0x2A74660`, the holder count is 14,667.
- **The tree:** the head node at `+0x38` (`+0x30` is the map's allocator, `+0x40` the count); 11,929 groups, walked in 0.10 s;
  **every descriptor has mode 1** (the block at `blocks + index * 125`); node layout as in section 3 (left, parent, right, colour, nil
  at `+0x19`; the key at `+0x20`, the mode at `+0x28`, the index at `+0x30`).
- **Known flags:** `10000800` Godrick defeated ON, `10000850` Margit defeated ON, `10000801` / `10000851` (their "found" flags) ON, grace
  `71000` ON: what the game shows. **`10007850` (Margit's drop) is ON but `10007800` (Godrick's lot) is OFF** although he is dead: the lot
  with Godrick's id is not what his defeat gives, so the drop flags must come from the event scripts (section 4), not from the id.
- **All 212 bosses:** they have 207 distinct defeat flags (a few rows share one): 43 defeated, 164 alive on this character, none in a group
  the game does not hold.
- **Cost:** the 212 defeat flags, one read each, 1.3 ms; the 179 groups read whole, 1.0 ms.

**One real write (check 6), the same day, a `run` session with the vault ON** (a developer script that checks the session as `write`
does, turns the flags off one bit at a time and reads each back; nothing else written):

- **Margit**, first: her 4 flags (`10000850`, `10000851`, `9100`, `60510`) turned off, then on again before anything was loaded (the
  author chose another boss): the turn back works the same way.
- **Mohg, Lord of Blood** (`12050800`): defeat `12050800`, intro `12050801` and `12050802`, play log `9112`, Remembrance lot flag
  `510120` turned off and read back. Walking to his arena from the same area: **no Mohg, no fog** (the flags stayed off: the game had not
  loaded the area again). **After a warp to another region and back: Mohg was there** (the author, "ได้ผล").
- **The fight, the same session:** the intro cutscene played, the defeat gave **420,000 runes** (`bonusSoul_single`) and **the
  Remembrance of the Blood Lord** again (lot `10120`). All three as the spec says.
- **The save after the session:** the vault put `regulation.bin` back byte for byte at once; the save could not be put back then (C:
  was full: `[WinError 112]` while the changed files were archived), so the record stayed `RESTORE_PENDING` and nothing was deleted, as
  the vault is made to do. With space again, `eldendisk vault restore` archived the changed files (`contaminated-2`) and restored all
  five files **byte-identical to the snapshot**: Mohg is dead again, the second Remembrance and the runes are gone. Unrelated to 1.8.0;
  it showed that a failed restore of a resurrect session is recovered like any other.

All the checks of section 12 passed on 2026-10-13: the spec is ready for the code.

## 14. Not done (decided)

- **No warp and no window.** The tool is CLI only; it prints where the boss is and the nearest grace, the player travels (ER's travel is
  quick). Calling the game's warp would need code in the game, which the tool never runs.
- **Never marks a boss defeated** (`defeated = true` is refused; agreed 2026-10-13) and never touches the achievement flags (`61xxx`).
- **No other flags.** Only the flags of the table can be written; there is no general event flag editor.
- Enemies without the big health bar (the field's elite enemies, the NPC invaders) are not great enemies.

## 15. Tests

`test_eventflags.py` (the tree walk on a fake memory built like the game's, modes 1 and 2, the bit order, a moved manager refused, the
blocks dropped when the tree changes; flags OFF only, the table's only, read back, a closed gate), `test_great_enemies.py` (the table,
names, ambiguous names refused, `all`, the design's list; golden: the table agrees with the game's `GameAreaParam`),
`test_resurrect_command.py` (--activate, already alive, a wrong name writes nothing, no session or no world, a flag that does not stick,
--all, --list with and without the game, the options that do not go together, --when-loaded, the `run` step, the block of read / write /
the scripts, `defeated = true` refused, the count in a plain `read`), additions to `test_profile_policy.py` (`event_flags`),
`test_design_live.py` (a script's write routed), `test_dev_pipeline.py` (the table in the exe), `test_architecture.py` and
`test_disk.py` (`commands/resurrect.py` may write).

---

# Part 2: Redefine & Restructure (the big refactor)

Written 2026-10-14 from `docs/experiments/extensional/resurrect-unit/great-enemies/redefine-and-restructuring.md`. Part 1 is what was
built first, with the names of that day (`design`, `resurrect great-enemies --activate`, `external-scripts`, ...). **Part 2 is the target
the refactor builds**: where the two differ (the names, the commands, the document's blocks), Part 2 wins; the Remarks at its end list
every difference and why.

_(Purpose: make the tool consistent and its foundation strong, before more is built on it.)_

## Definition

**Elden-Disk is the Elden Ring Memory Disk I/O Tools.** It works as **CLI commands in a console** (Windows 10/11, 64-bit) and has no
user interface it does not need: you open a terminal, run a command, it does its work and ends. Everything the tool can do is a command,
and every command reads the same way (section "Commands").

**Philosophy: the portal.** Elden-Disk is a **portal into a parallel world** of the real game world (Elden Ring, the Lands Between).
Through the portal the world mirrors everything of the game, and you can play with it in **creative ways** (new items you design, great
enemies brought back, scripts that change the game while it runs, and more). When you leave through the portal, the real world is back
exactly as it was: **nothing you did inside comes back with you.** The vault is the portal: it keeps the real world (the save files `ER0000.sl2`, `ER0000.sl2.bak`, `ER0000.err`, `ER0000.err.bak`, `steam_autocloud.vdf`, and the
game's own files) before you go in, and puts it back, byte for byte, when you come out.

## Backbone: running the game ⟶ loading the world ⟶ playing ⟶ quitting the game

```text
vault: back up ER0000.sl2, ER0000.sl2.bak, ER0000.err, ER0000.err.bak, steam_autocloud.vdf (and swap in the regulation.bin built from creative.json)   `run`, the portal opens
 │
 ├─ read      reads the game's memory (RAM): the pointer chains of the profile (offsets.json), or a small scan when the chain is not
 │   │        known; every value is a name in ONE document, the single source of truth (below)
 │   ├─ [nothing | * | all]        all of the document
 │   └─ [NAME | ID | PATH ...]     a part of it: `hp`, `creative.resurrect.great_enemies.margit`, `params.Magic.6230.mp`
 │       └─ [--live | --tree (default) | --flat | --json]     what to do with what is read
 │
 ├─ write     writes the game's memory through the same chains, only inside the session `run` started (vault ON)
 │   ├─ [NAME | ID | PATH = VALUE ...]   a name that `read` shows: `write creative.resurrect.great_enemies.margit.defeated=false`
 │   └─ [NAME | ID | PATH = default]       the game's own value back
 │
 ├─ creative  what is built and run next to the game (it depends on the vault, like `write`)
 │   ├─ scripts                 your Python scripts, running next to the game while it runs
 │   │   ├─ defaults            the scripts the exe carries (creative/scripts/defaults)
 │   │   └─ added               the scripts added after the build (`scripts add PATH`)
 │   ├─ innovate-spells         new spells: creative.json -> a regulation.bin judged by a gate -> secured
 │   └─ resurrect               a boss you have beaten (a great enemy), alive again for the session
 │
 ├─ data      export, reset, check, probe: the document to a file, the baselines, a regulation.bin compared, the param tables found
 │
vault: restore ER0000.sl2, ER0000.sl2.bak, ER0000.err, ER0000.err.bak, steam_autocloud.vdf and the game's own files (byte for byte)   the game closes, the portal closes
```

Rules every branch follows:

1. **One document.** Whatever the tool knows of the running game is a path in the single source of truth (`systems`, `character`,
   `params`, `creative`). `read` shows it, `write` and `tools.write` change it, `export` writes it as `output\disk.json`. Nothing
   has a second name somewhere else.
2. **Read anywhere, write only through the portal.** Reading needs no session. Every write (a value, a param, a text, a colour, a flag)
   needs the session `run` started with the vault ON, for this very game process, and goes through the same gate.
3. **Memory only.** Nothing is written to the game folder or to `ER0000.sl2`, `ER0000.sl2.bak`, `ER0000.err`, `ER0000.err.bak`, `steam_autocloud.vdf`; what is built from `creative.json` (regulation.bin) is swapped in and put
   back by the vault.
4. **One command, one job, then it ends.** The things that stay open are the ones that must: `run` (the session), `read --live`, the
   scripts' host.
5. **The game's own data first.** Ids, names, flags and places come from the game's files (its params, event scripts and text); a list
   made by hand is the exception, and a test checks it against the game.

## Commands

**Beginning with `run` (or `run --vault-on -v`) to enter the Portal**

**Mechanism:**
1. Snapshot `ER0000.sl2`, `ER0000.sl2.bak`, `ER0000.err`, `ER0000.err.bak`, `steam_autocloud.vdf` from **The Real Game Save** into
   **The Vault**, each file hashed.
2. Copy the game's own `regulation.bin` into **The Vault**, build a new one with **Creative** (`innovate-spells`, ...) and swap it
   into **The Real Game Files** for the session.
3. Launch `eldenring.exe` in offline mode.
4. Once a character is in **The Game World**: the advanced designs (the spells' texts and colours, the great enemies to bring back) are
   found in **The Real Game Memory** by a quick scan or the profile's pointer chains, checked, and written.
5. The external scripts (the defaults and the added ones) start, each in a thread of its own.
6. While you play in **The Game World**, open another terminal and run the commands of the **1st**, **2nd** and **3rd** levels and the **Data** commands below.
7. Quit the game: **The Vault** puts the save files and the game's own `regulation.bin` back into **The Real Game Files**, byte for byte.
   That keeps **The Parallel Dimension World** apart from the real one and, above all, keeps your account safe: nothing edited stays.

### 1st Level: Vault Coverage

| **Commands** | **Functions** | **Mechanism**                                                                                                                                                           |
|:-------------|:--------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `vault`      | `status`      | Show the session record, the last snapshot, the vault's size                                                                                                            |
| `vault`      | `list`        | List the snapshots: time, size, verified                                                                                                                                |
| `vault`      | `verify`      | Hash a snapshot again against its manifest                                                                                                                              |
| `vault`      | `restore`     | Finish an unended session: archive `ER0000.sl2`, `ER0000.sl2.bak`, `ER0000.err`, `ER0000.err.bak`, `steam_autocloud.vdf`, put the snapshot back, verify; safe to repeat |
| `vault`      | `keep`        | Take the current `ER0000.sl2`, `ER0000.sl2.bak`, `ER0000.err`, `ER0000.err.bak`, `steam_autocloud.vdf` as the new baseline (`--yes`)                                    |
| `vault`      | `prune`       | Delete old snapshots, keep `--keep N`; refused while a session is open                                                                                                  |

### 2nd Level: Core Feature

| **Commands** | **Parameters**      | **Options**                 | **Outputs**                            | **Mechanism**                                                                                  |
|:-------------|:--------------------|:----------------------------|:---------------------------------------|:-----------------------------------------------------------------------------------------------|
| `read`       | `EMPTY`, `*`, `all` | `EMPTY (default)`, `--live` | `--tree (default)`, `--flat`, `--json` | Follow the profile's pointer chains ⟶ build the whole document; `--live` repeats at `--hz`     |
| `read`       | `[NAME\|ID\|PATH]`  | `EMPTY (default)`, `--live` | `--tree (default)`, `--flat`, `--json` | Resolve the name to its path ⟶ read only that part; `--live` repeats at `--hz`                 |

| **Commands** | **Functions**        | **Outputs**                        | **Mechanism**                                                                           |
|:-------------|:---------------------|:-----------------------------------|:----------------------------------------------------------------------------------------|
| `read`       | `monitor`            | `--mapped`, `--unmapped (default)` | Both monitors in one view                                                               |
| `read`       | `monitor-buffs`      | `--mapped`, `--unmapped (default)` | Poll the active `SpEffects` ⟶ one `+` / `-` row per id, named from `names.json` |
| `read`       | `monitor-animations` | `--mapped`, `--unmapped (default)` | Poll the active `anim` ⟶ one `+` / `-` row per id, named from `names.json`      |

| **Commands** | **Parameters**             | **Mechanism**                                                                                                                |
|:-------------|:---------------------------|:-----------------------------------------------------------------------------------------------------------------------------|
| `write`      | `EMPTY`                    | List the writable names and their ranges; write nothing                                                                      |
| `write`      | `[NAME\|ID\|PATH]=[VALUE]` | Check the portal ⟶ resolve the name ⟶ check the range ⟶ write through the gate ⟶ read back; `default` = the game's own value |

### 3rd Level: Creative Feature

_(`design` was removed)_

| **Commands** | **Parameters**      | **Outputs**                            | **Mechanism**                                         |
|:-------------|:--------------------|:---------------------------------------|:------------------------------------------------------|
| `scripts`    | `EMPTY`, `*`, `all` | `--tree (default)`, `--flat`, `--json` | List every script (defaults and added) with its state |

_(`defaults` was removed)_

| **Commands** | **Functions** | **Parameters**                         | **Options**                        | **Mechanism**                                                                                 |
|:-------------|:--------------|:---------------------------------------|:-----------------------------------|:----------------------------------------------------------------------------------------------|
| `scripts`    | `start`       | `[NAME[:ID[:PROCESS_ID]]]`, `*`, `all` | `EMPTY (default)`, `--when-loaded` | Start the host if none ⟶ run the script in a thread: `setup()`, then `loop()` every `every` s |
| `scripts`    | `restart`     | `[NAME[:ID[:PROCESS_ID]]]`, `*`, `all` |                                    | `stop` ⟶ load the file again ⟶ `start`                                                        |
| `scripts`    | `stop`        | `[NAME[:ID[:PROCESS_ID]]]`, `*`, `all` |                                    | Ask it to stop ⟶ `teardown()`; a stuck one ends only with the host                            |

| **Commands** | **Functions** | **Parameters**                         | **Outputs**                            | **Mechanism**                          |
|:-------------|:--------------|:---------------------------------------|:---------------------------------------|:---------------------------------------|
| `scripts`    | `status`      | `[NAME[:ID[:PROCESS_ID]]]`, `*`, `all` | `--tree (default)`, `--flat`, `--json` | Ask the host: state, loops, last error |

| **Commands** | **Functions** | **Parameters**             | **Mechanism**                                                       |
|:-------------|:--------------|:---------------------------|:--------------------------------------------------------------------|
| `scripts`    | `add`         | `[FILE_PATH\|FOLDER_PATH]` | Check the file loads ⟶ put it in the list of added scripts of `creative.json` |
| `scripts`    | `remove`      | `[FILE_PATH\|FOLDER_PATH]` | Take it out of the list (stop it first if it runs)                  |
| `scripts`    | `change`      | `[FILE_PATH\|FOLDER_PATH]` | Point the entry at the new file ⟶ `restart` it if it runs           |

| **Commands**      | **Functions** | **Parameters**                        | **Options**                                     | **Mechanism**                                                                    |
|:------------------|:--------------|:--------------------------------------|:------------------------------------------------|:---------------------------------------------------------------------------------|
| `innovate-spells` | `EMPTY`       |                                       |                                                 | Show the spells with their ids, built or secured                                 |
| `innovate-spells` | `build`       | `EMPTY`, `*`, `all`, `[NAME\|ID ...]` | `EMPTY (default)`, `--dry-run`, `--source FILE` | Copy the template rows ⟶ apply the design ⟶ re-encode ⟶ the gate judges the file |
| `innovate-spells` | `secure`      | `EMPTY`                               |                                                 | Gate again ⟶ keep it as `regulation.secured.bin` (game closed)                   |
| `innovate-spells` | `apply`       | `EMPTY`                               | `EMPTY (default)`, `--when-loaded`              | Put the texts and colours into the running game (memory only)                    |

| **Commands** | **Parameters**                              | **Options**                                     | **Mechanism**                                                                                        |
|:-------------|:--------------------------------------------|:------------------------------------------------|:-----------------------------------------------------------------------------------------------------|
| `resurrect`  | `[NAME\|ID\|PATH ...]`, `*`, `all`          | `EMPTY (default)`, `--dry-run`, `--when-loaded` | Check the portal ⟶ turn the boss's event flags OFF ⟶ read back; it returns when its area loads again |

### Data

| **Commands** | **Options**                 | **Mechanism**                                                                 |
|:-------------|-----------------------------|:------------------------------------------------------------------------------|
| `export`     | `EMPTY (default)`, `--live` | Export the data (the single source of truth) into `<TOOLS-DIR>\output\disk.json`; `--live`: again each time it changes |


| **Commands** | **Parameters**                          | **Mechanism**                                                                                                                 |
|:-------------|:----------------------------------------|:------------------------------------------------------------------------------------------------------------------------------|
| `reset`      | `EMPTY`, `*`, `all`, `[NAME\|ID\|PATH]` | Take the game's values now as the new baseline (`runes.delta` = 0, the monitors' history cleared); writes nothing to the game |
| `check`      | `[FILE_PATH]`                           | Decode a `regulation.bin` ⟶ compare its tables with the game's, row by row                                                    |
| `probe`      | `EMPTY`                                 | Find where the game's param tables lie in memory ⟶ check them against the profile's chains (for a new game version)           |

### Flags & Options (every command)

| **Flags & Options**         | **Definition**         | **Working on Commands**                                                         | **Mechanism**                                                                           |
|:----------------------------|:-----------------------|:--------------------------------------------------------------------------------|:----------------------------------------------------------------------------------------|
| `-v`, `--verbose`           | the log, live          | **ALL**                                                                         | shows the log lines themselves instead of the concise view                              |
| `--vault DIR`               | the vault              | **ALL**                                                                         | the vault to use (remembered once given)                                                |
| `--save-dir DIR`            | the save folder        | `run`, `vault`                                                                  | the game's save folder, for several Steam accounts (remembered)                         |
| `--game-dir DIR`            | the game folder        | `run`, `check`, `innovate-spells`                                               | where `eldenring.exe` is (found through Steam otherwise)                                |
| `--offsets FILE`            | the profile            | `read`, `write`, `scripts`, `innovate-spells apply`, `resurrect`, `export`     | the pointer chains of each game version (`offsets.json`; the one in the exe by default) |
| `--spec FILE`               | the creative file      | `run`, `scripts`, `innovate-spells`, `resurrect`                               | the creative file (`creative.json` next to the exe, else the one in the exe)                |
| `--creative-dir DIR`          | the creative files     | `run`, `scripts`, `innovate-spells`                                            | where builds, secured files and the scripts' status are kept (`<vault>\creative`)         |
| `--vault-on`, `--vault-off` | the portal             | `run`                                                                           | open the portal (default) / play without it: nothing is backed up, swapped or written   |
| `--regulation FILE`         | another world          | `run`                                                                           | swaps this `regulation.bin` instead of the one built from `creative.json`                                     |
| `--keep N`                  | snapshots kept         | `run`, `vault prune`                                                            | the newest snapshots kept                                                               |
| `--yes`                     | confirm                | `vault keep`                                                                    | what cannot be undone is done only with it                                              |
| `--hz N`                    | the pace               | `read --live`, `export --live`                                                  | reads per second (1 to 120)                                                             |
| `--version`                 | the version            | `eldendisk`                                                                     | prints the version and ends                                                             |

### Tooling

| **Commands** | **Parameters** | **Mechanism**                                                                                        |
|:-------------|:---------------|:-----------------------------------------------------------------------------------------------------|
| `hash`       | `EMPTY`        | SHA-256 of `eldenring.exe` ⟶ the key of its profile in `offsets.json` (a new game version needs one) |
| `--version`  | `EMPTY`        | The tool's version                                                                                   |

**Exit codes (every command)**

| **Code** | **Meaning**                                                                                          |
|:---------|:-----------------------------------------------------------------------------------------------------|
| `0`      | done (also when there was nothing to do: a boss already alive, a value already set)                  |
| `1`      | an error, or not applied (a wrong name, a value that did not stick, no character in the world)       |
| `2`      | not supported: no profile for this `eldenring.exe`, or the profile lacks the block the command needs |
| `3`      | the anti-cheat is running: the tool refuses to touch the game                                        |
| `4`      | a restore is pending: run `vault restore` first                                                      |
| `5`      | no portal: no session of `run` with the vault ON for this game process (every write)                 |
| `130`    | interrupted (Ctrl+C)                                                                                 |

**Naming (`NAME | ID | PATH`).** Everywhere a thing is named, the same three forms work: the **path** in the document
(`creative.resurrect.great_enemies.12050800`), the **id** (`12050800`, the game's own number) and the **name** in any letter case or a part
of it (`mohg lord`). A name that fits several is refused with the list; a wrong name changes nothing. `*` and `all` mean every one, and
stand alone.

**Addressing a script (`NAME:ID:PROCESS_ID`).** `NAME` is the script's class (`RctColoursFollowTheSpell`), `ID` its number in the host
(1, 2, ...: two scripts may share a class name in different files), `PROCESS_ID` the host's process (all the scripts of a session run in
ONE host process, each in a thread). `RctColoursFollowTheSpell` alone is enough while it is unique. **A limit to know:** Python cannot kill
a thread, so `stop` asks the script to stop (its loop ends, `teardown()` runs); a script stuck inside its own code ends only with the host
process (`scripts stop *`, or the game closing). There is no `kill` for one script.

## The creative file (`creative.json`)

What you edit to shape the parallel world. `run` reads it at every session (`--spec FILE`, else next to the exe, else the copy in the
exe); one section per creative feature, each optional:

```json
{
  "innovate_spells": {
    "maximum": 20,
    "slots": {
      "reverse_cursed_technique": { "kind": "projectile", "from": 6421, "requires": {}, "locations": {}, "customs": {} }
    }
  },
  "scripts": {
    "added": ["D:\\my-scripts\\boss_rush.py", "D:\\my-scripts\\colours\\"]
  },
  "resurrect": {
    "great_enemies": { "activate": ["margit", "12050800"] }
  }
}
```

| **Section**                  | **`run` does with it**                                                                            |
|:-----------------------------|:--------------------------------------------------------------------------------------------------|
| `innovate_spells`            | builds `regulation.bin` when the spells changed (or swaps the secured one), then `apply` in the world |
| `scripts.added`              | starts these scripts with the defaults, in the world (`scripts add / remove / change` edit the list) |
| `resurrect.great_enemies`    | `activate` in the world: `"all"` / `"*"`, or names and ids                                          |

A wrong name or value in `creative.json` is an error that names its place in the file; nothing is built or started from a file with an
error.

## Where things live

```text
%LOCALAPPDATA%\EldenDisk\   (<TOOLS-DIR>)        everything the tool keeps (never next to the exe: a new build cannot delete it)
 ├─ vault\ 
 │   ├─ <time>\                                 a snapshot: ER0000.sl2, ER0000.sl2.bak, ER0000.err, ER0000.err.bak, steam_autocloud.vdf,
 │   │   │                                       their manifest (hashes), bin\regulation.bin (the game's own), contaminated\ (the
 │   │   │                                       session's changed save, archived at the restore)
 │   ├─ session.json                            the session record: open while the portal is open; a record left open = a restore pending
 │   ├─ creative\                               the creative files: builds, the secured regulation.bin, the scripts' status
 │   ├─ memory-cache.json                       where this game process holds what was written (texts, colours): no second search
 │   └─ eldendisk.log                           the log of every command
 └─ output\disk.json                           what `export` writes
<exe folder>\                                   eldendisk.exe; offsets.json, names.json, creative.json when you put them next to it
                                                (they win over the copies in the exe)
```

`offsets.json` holds one **profile** per `eldenring.exe` (by its SHA-256, see `hash`): the pointer chains and the blocks each feature needs
(`text`, `equipment`, `event_flags`, ...). `names.json` names the buffs and the animations the game gives no readable name for (`311100` "Gold Scarab", `TALISMANS`;
`26030000` "Attacking (R1)", `MANNER`). It belongs to the reader and lives in its package, `code/eldendisk/reader/names.json`
(always in the exe; one next to the exe still wins, so names can be added without a new build). The buffs of the spells in
`creative.json` are named by the build, not by this file.

## Safety

- **Offline only.** The game is launched offline; with the anti-cheat running the tool refuses (exit `3`).
- **Steam Cloud** may sync the save when the game exits: `run` says so when Steam is running (use Steam's offline mode).
- **The portal checks itself.** Every write checks that the session record names this very game process (pid, start time, exe hash);
  a record left open (the game killed, a full disk) blocks the next `run` until `vault restore`.
- **The game's files are never edited.** Only `regulation.bin` is swapped, and the game's own copy is checked against the known original
  on every path; a modified one is refused.

## The single source of truth

`export` writes it as `<TOOLS-DIR>\output\disk.json`; `tools.read()` gives it to a script; every name above is a path in it.

```json
{
  "systems": {
    "profile": { "sha256": "1a3547101327f65d0c76da2f9190ac0aa66871ea42bae2aecc61e11a8b597891", "game": "eldenring.exe", "version": "1.17.1" },
    "features": { "buffs_supported": true, "animations_supported": true, "creative_supported": true },
    "status": {
      "pid": 46224, "tool_state": "IDLE", "anti_cheat_state": "DISABLED_OFFLINE", "game_connected": true,
      "ignored": { "buffs": 11, "animations": 0 }
    },
    "session": { "mode": "creative", "read_only": false, "creative": true }
  },
  "character": {
    "level": 386,
    "vitals": {
      "hit_point": { "current": 1914, "maximum": 1914, "base": 2015 },
      "focus_point": { "current": 350, "maximum": 350, "base": 350 },
      "stamina": { "current": 178, "maximum": 178, "base": 158 }
    },
    "runes": { "total": 55214603, "baseline": 55214603, "delta": 0 },
    "attributes": { "vigor": 80, "mind": 60, "endurance": 60, "strength": 90, "dexterity": 90, "intelligence": 15, "faith": 60, "arcane": 10 },
    "equipment": { "magic": { "selected": { "slot": 1, "id": 2230000 }, "slots": { "1": 2230000, "2": 6420 } } },
    "buffs": {
      "311100": { "name": "Gold Scarab", "categories": "TALISMANS", "abilities": "Permanently increases Runes gained by 20% while equipped." }
    },
    "animations": {
      "26030000": { "name": "Attacking (R1)", "categories": "MANNER" }
    }
  },
  "params": {
    "effects": {
      "1621000": { "name": "Black Flame", "effectEndurance": 2.0, "motionInterval": 0.1, "changeHpRate": 0.1, "changeHpPoint": 1, "atkOccurrenceSpEffectId": -1, "vfxId": 9010 },
      "1623000": { "name": "Scouring Black Flame", "effectEndurance": 2.0, "motionInterval": 0.1, "changeHpRate": 0.1, "changeHpPoint": 1, "atkOccurrenceSpEffectId": -1, "vfxId": 9010 },
      "1625000": { "name": "Black Flame Ritual", "effectEndurance": 2.0, "motionInterval": 0.1, "changeHpRate": 0.1, "changeHpPoint": 1, "atkOccurrenceSpEffectId": -1, "vfxId": 9010 },
      "1626001": { "name": "Black Flame Blade", "effectEndurance": 2.0, "motionInterval": 0.1, "changeHpRate": 0.1, "changeHpPoint": 1, "atkOccurrenceSpEffectId": -1, "vfxId": 9010 }
    }
  },
  "creative": {
    "scripts": {
      "host": { "process_id": 26528, "state": "running", "started": "2026-10-13 21:49:03", "scripts": 1 },
      "defaults": {
        "RctColoursFollowTheSpell": {
          "id": 1,
          "file": "rct_colours_follow_the_spell.py",
          "state": "live",
          "every": 0.2,
          "loops": 10243,
          "slow": false,
          "last_error": null
        }
      },
      "added": {}
    },
    "innovate_spells": {
      "2230000": {
        "id": "reverse_cursed_technique",
        "slot": 1,
        "rows": {
          "goods": 2230000,
          "magic": 2230000,
          "sp_effect": [21951000, 21951001],
          "bullet": [500000000, 500000001],
          "atk": [710000000, 710000001],
          "shop": 100508
        },
        "design": {
          "kind": "projectile",
          "from": 6421,
          "requires": {
            "status": { "intelligence": 0, "faith": 60, "arcane": 10 },
            "cost": { "focus_point": 120 }
          },
          "locations": {
            "kale": { "price": 34590, "stock": 1 }
          },
          "customs": {
            "basic": {
              "SpEffect.1642100.effectEndurance": 20.0,
              "SpEffect.1642100.motionInterval": 0.5,
              "SpEffect.1642100.changeHpPoint": -45,
              "SpEffect.1642100.changeMpPoint": -15,
              "SpEffect.1642100.staminaRecoverChangeSpeed": 100,
              "SpEffect.1642100.vfxId": -1,
              "Magic.6421.refType": 32,
              "Magic.6421.castSfxId": 524400,
              "Magic.6421.fireSfxId": 524401,
              "Bullet.10642100.sfxId_Bullet": -1,
              "Goods.6421.iconId": 6806
            },
            "advanced": {
              "texts": {
                "goods_name": "Reverse Cursed Technique",
                "goods_info": "An anomalous art left behind by an Unknown Sorcerer from another reality. Forces the concept of ruin to consume itself, commanding shattered flesh to remember its whole and unbroken state.",
                "goods_caption": "The nature of a curse is to erode, corrupt, and destroy. (...)"
              },
              "colors": {
                "Magic.6421.castSfxId": { "main": "#90D5FF", "accent": "#FF909E" },
                "SpEffect.1642100": "#90D5FF"
              }
            }
          }
        }
      }
    },
    "resurrect": {
      "great_enemies": {
        "12050800": {
          "name": "Mohg, Lord of Blood",
          "place": "Mohgwyn Palace",
          "grace": "Dynasty Mausoleum Midpoint",
          "runes": 420000,
          "drop": ["Remembrance of the Blood Lord", "Mohg's Great Rune"],
          "story": true,
          "dlc": false,
          "defeated": true
        },
        "10000850": {
          "name": "Margit, the Fell Omen",
          "place": "Stormhill",
          "grace": "Castleward Tunnel",
          "runes": 12000,
          "drop": ["Talisman Pouch"],
          "story": true,
          "dlc": false,
          "defeated": true
        }
      }
    }
  }
}
```

### `creative.scripts`

- `host`: the one process that runs the scripts of the session: its process id (the `PROCESS_ID` of a script's address), `running` /
  `stopped`, when it started, how many scripts it holds. `null` when no host runs (no session, or no script).
- `defaults`: the scripts the exe carries; `added`: the scripts added after the build. Each is keyed by its `NAME` (the class), with:
  - `id`: its number in the host (the `ID` of its address);
  - `file`: the file it was loaded from;
  - `state`: `loaded`, `setup`, `live`, `waiting` (no character in the world), `stopped`, `dead` (an exception), `failed` (the file
    could not be loaded), `off` (`enabled = False`), `stuck` (a loop that has not returned for 10 s);
  - `every`, `loops`, `slow` (a loop longer than its pace was seen), `last_error` (the last line of the traceback, or `null`).
- Writable: `state` = `"stopped"` (ask it to stop) or `"live"` (start it again, `setup()` first): the same as
  `scripts stop|start NAME`.

### The scripts' interface (`edstdlib`)

```python
from edstdlib import *

class BossRush(Interface):
    every = 1.0                                                   # seconds between two loop()

    def loop(self):
        x = tools.read()                                          # the single source of truth, as an object
        for boss in x.creative.resurrect.great_enemies.values():   # the defeated ones
            if boss.name.startswith("Mohg"):
                boss.defeated = False                             # bring him back
        tools.write(x)                                            # writes only what changed
```

| **Name**                 | **Does**                                                                                    |
|:-------------------------|:--------------------------------------------------------------------------------------------|
| `Interface`              | the base of a script: `setup()` once, `loop()` every `every` s, `teardown()` at the end; `enabled = False` keeps it off |
| `tools.read()`           | the single source of truth as an object (`x.character.runes.total`, `x.params.effects[1621000]`) |
| `tools.write(x)`         | writes what changed in it, through the portal, as `write` does; `True` when everything stuck |
| `tools.log(text, level)` | a line in the log and on the `run` console, under the script's name                        |
| `tools.dead()`           | ends this script now                                                                        |

### `creative.resurrect.great_enemies` (defeated only)

- **Only the great enemies that are defeated now** are in the document: they are the ones that can be brought back, and the list stays
  short (43 on the author's character, not 212). `read creative.resurrect.great_enemies` shows them; a boss that is alive is not in it.
- Each is keyed by its id, with what the table knows (`name`, `place`, the nearest `grace`, `runes`, `drop`, `story`, `dlc`) and
  `defeated: true`.
- Writable: `defeated` = `false` brings it back (the same as `--activate`); it then leaves the list until it is beaten again. `true` is
  refused: only the game marks a boss defeated.
- When the game holds no save yet (title screen), the block is `{}`.

## Open questions

1. ~~`stop` of one script and `restart`: they need a way to reach the host from another terminal.~~ **Decided (2026-10-14): the file.**
   Each request is a file of its own in `<vault>\creative\scripts.requests\`; the host looks once a second, does it and answers in
   `scripts.status.json` (`replies`). No port is opened.
2. Should `creative.innovate_spells.<id>.design` also be writable as a whole (a new build from the running session), or stay the
   values only (each field written to the game's rows)? **For now: the values only** (`write creative.innovate_spells.<id>.design.<path>=...`).

## Implementation notes (2026-10-14)

What the code decided where the text above left a choice:

| **Where**                                     | **What was built**                                                                                                                                                                                                                                                                 |
|:----------------------------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `write` alone                                 | lists the writable names with their ranges (level, runes, the attributes, hp / fp / stamina, `params...`, `creative...`) and writes nothing                                                                                                                                        |
| `write NAME=default`                          | for `params` names only (`params=default`: every one changed in this game process); a character value has no default of the game                                                                                                                                                   |
| `write creative.scripts.<group>.<NAME>.state` | `stopped` / `live`: a request to the running host; with no host it is an error (`write` never becomes the host)                                                                                                                                                                    |
| `scripts start`                               | when no host runs, the command **becomes the host** in its terminal (as `run` starts it); when one runs, a request. `stop *` ends the host                                                                                                                                         |
| `scripts add / remove / change`               | edit `scripts.added` of `creative.json` (`--spec`, else the one next to the exe, made from the copy in the exe the first time, else `code/creative.json`); a running host loads / unloads at once. `change NEW` finds the entry with the same file name; `change OLD NEW` names it |
| the scripts' status                           | `scripts.status.json` (was `external-scripts.status.json`): `pid`, `state`, `started`, `scripts` (`name`, `id`, `file`, `path`, `added`, `state`, `every`, `loops`, `slow`, `started`, `last_error`), `replies`                                                                    |
| `read monitor...`                             | `--unmapped` is the default, as the table says (it was "all" before)                                                                                                                                                                                                               |
| `reset`                                       | the baselines live in `<TOOLS-DIR>\baselines.json`, for one game process (pid and start time); `runes` (the total now), `buffs`, `animations` (`monitor`: both); a reader takes them at its start (the runes) and every 2 s while it runs                                          |
| `innovate-spells build NAME \| ID`            | NAME is the key of the slot; ID the goods id (2230000 + slot - 1); `creative.innovate_spells.<goods id>` works too                                                                                                                                                                 |
| `innovate-spells apply`                       | the texts, then the colours, one process (the second step looks at the world once, the first waited)                                                                                                                                                                               |
| `--names FILE`                                | a flag for `read`, `scripts`, `export`, `reset` (`--state-ids` before)                                                                                                                                                                                                             |
| the exe                                       | `names.json` and the great-enemies table are always in it (package data); the default scripts sit in its `scripts\` (was `external-scripts\`)                                                                                                                                      |
| an older vault                                | `<vault>\design` (or `extension`) is renamed `<vault>\creative` once, and its `innovate-items\spells\` becomes `innovate-spells\`                                                                                                                                                  |

## Remarks

What this document changes from the tool as it was (1.7.2 and the first build of 1.8.0), and why.

| **Before**                                                                                                           | **After**                                                                                                      | **Why**                                                                                                                                                                                                                                                   |
|:---------------------------------------------------------------------------------------------------------------------|:---------------------------------------------------------------------------------------------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `extension ...` in front of the creative commands                                                                    | no prefix: `scripts`, `innovate-spells`, `resurrect`                                                           | one level less to type; `extension` became `design`, then `creative` (below)                                                                                                                                                                              |
| `design` (the overview of `design.json`)                                                                             | removed                                                                                                        | `read creative` shows that part of the document; `creative.json` is described once (The design file)                                                                                                                                                      |
| `external-scripts`                                                                                                   | `scripts`                                                                                                      | shorter; the scripts are the only external thing                                                                                                                                                                                                          |
| `external-scripts --run`, `--scripts-dir PATH`                                                                       | `scripts start / restart / stop / status`, `add / remove / change`                                             | control one script while the game runs; the added scripts are kept in `creative.json`, not typed every run                                                                                                                                                |
| `external-scripts defaults`                                                                                          | removed                                                                                                        | `scripts` lists the defaults and the added ones together                                                                                                                                                                                                  |
| `innovate-items spells`                                                                                              | `innovate-spells`                                                                                              | one word: spells are the one kind of item so far                                                                                                                                                                                                          |
| `innovate-items spells --add all\|PATH ...`                                                                          | `innovate-spells build [all \| NAME \| ID ...]`                                                                | a function word, like `vault status`                                                                                                                                                                                                                      |
| `innovate-items spells --secure`                                                                                     | `innovate-spells secure`                                                                                       | the same                                                                                                                                                                                                                                                  |
| `write --text`, `write --flame-color`                                                                                | `innovate-spells apply`                                                                                        | they put the spells' design into the game: creative work, not core                                                                                                                                                                                        |
| `resurrect great-enemies --activate NAME`                                                                            | `resurrect NAME \| ID \| PATH`                                                                                 | one word: great enemies are the one kind so far                                                                                                                                                                                                           |
| `resurrect great-enemies --list` (and its filters)                                                                   | removed                                                                                                        | `creative.resurrect.great_enemies` in the document holds **only the defeated bosses**: `read creative.resurrect.great_enemies.*` shows their ids, and `resurrect 12050800` brings one back. The list a person needs is the one the document already gives |
| `creative.resurrect.great_enemies`: all 212, `defeated` true / false / null                                          | the defeated ones only                                                                                         | the bosses that can be brought back; short (43 on the author's character); a boss leaves the set when it is brought back and comes back when it is beaten                                                                                                 |
| a spell's node: `id`, `slot`, `rows`, `kind`, `from`, ... side by side                                               | `id`, `slot`, `rows` apart from `design: {...}`                                                                | the build's facts apart from what you designed                                                                                                                                                                                                            |
| `read --export`, `disk-state.json` next to the tool                                                                  | `export`, `<TOOLS-DIR>\output\disk.json`                                                                       | the document to a file is a job of its own (Data)                                                                                                                                                                                                         |
| `read --param-check FILE`                                                                                            | `check FILE`                                                                                                   | Data, not reading the game                                                                                                                                                                                                                                |
| `read --probe-params`                                                                                                | `probe`                                                                                                        | the same                                                                                                                                                                                                                                                  |
| `read --param Table.ID`                                                                                              | `read params.Table.ID`                                                                                         | a path in the document like every other name                                                                                                                                                                                                              |
| `read --live-buffs`, `read --live-animations`                                                                        | `read monitor`, `monitor-buffs`, `monitor-animations`                                                          | function words; `monitor` shows both                                                                                                                                                                                                                      |
| `write --set NAME=VALUE`                                                                                             | `write NAME=VALUE`                                                                                             | `--set` said nothing more than `write` does                                                                                                                                                                                                               |
| `write --reset NAME`                                                                                                 | `write NAME=default`                                                                                           | one form for every write                                                                                                                                                                                                                                  |
| `write --refill LIST`                                                                                                | removed                                                                                                        | `write hp=<maximum>` does the same                                                                                                                                                                                                                        |
| (none)                                                                                                               | `reset`                                                                                                        | the read baselines (`runes.delta`, the monitors) start again from now; nothing written to the game                                                                                                                                                        |
| (none)                                                                                                               | `scripts status`, `creative.scripts` in the document                                                           | how each script is doing, from the host itself, as data                                                                                                                                                                                                   |
| `run` also took `--scripts-dir`                                                                                      | `run` starts what `creative.json` names                                                                        | everything the session does is in `creative.json`                                                                                                                                                                                                         |
| `chr_state_ids.json` next to `offsets.json` (`code/`)                                                                | `names.json` in the reader's package (`code/eldendisk/reader/`)                                                | what it is in one word (the names of the buffs and the animations); it belongs to `read`, the one that uses it                                                                                                                                            |
| the group `design`: package `eldendisk/design/`, `design.json`, the block `design`, `<vault>\design`, `--design-dir` | `creative`: `eldendisk/creative/`, `creative.json`, the block `creative`, `<vault>\creative`, `--creative-dir` | `design` now means one thing only, the values you designed (`creative.innovate_spells.<id>.design`); `creative`, like Minecraft's creative mode, says what the group is: the things that exist only in the parallel world, played with freely             |
| `design.innovate_items.spells`                                                                                       | `creative.innovate_spells`                                                                                     | the same name as the command `innovate-spells`; one level less                                                                                                                                                                                            |
| `design.external_scripts`                                                                                            | `creative.scripts`                                                                                             | the same name as the command `scripts`                                                                                                                                                                                                                    |
| `systems.session.mode`: `"sandbox"`                                                                                  | `"creative"`                                                                                                   | the same word for the same thing                                                                                                                                                                                                                          |

The names of the document follow the commands: `creative.innovate_spells` is `innovate-spells`, `creative.scripts` is `scripts`,
`creative.resurrect` is `resurrect` (`great_enemies` stays under it as its first kind).


# Part 3: Optimization (everything)

Written 2026-10-15. Where the time of the tool goes, measured, and what was made quicker. Rule: **nothing that keeps the portal safe is
made weaker** (the gate keeps its two decoders, `run` hashes the game's exe afresh, every write checks the session).

## Measured (2026-10-15, before)

| **What**                                                                       |            **Time** | **Where it goes**                                                                                                                                                    |
|:-------------------------------------------------------------------------------|--------------------:|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| one command of `eldendisk.exe` (`--version`, `read --help`)                    |              0.97 s | the one-file exe unpacks itself into a temporary folder at every start (a one-folder exe: 0.16 s; `python -m eldendisk`: 0.27 s)                                     |
| the Python side of a command                                                   |  0.18 s\nof imports | every command imported the code of every other command (the build, the scripts, the reader)                                                                          |
| attaching to the game (every `read`, `write`, `resurrect`, step)               | 0.08 s\n1.7 s\ncold | `eldenring.exe` (87 MB) hashed at every attach                                                                                                                       |
| a build (`run`, `innovate-spells build`), one spell                            |               5.5 s | prepare 2.0 (the game's file decoded by our pure-Python decoder) + make 1.3 + gate 2.2 (the new file decoded again, by both decoders)                                |
| from a character in the world to the scripts being live (`run -v`, 2026-10-14) |                11 s | the text 1.4 s, a fixed 3 s watch of the text tables, a second attach for the colours 1.4 s, the colours 3.2 s, the scripts' process 1.5 s (exe start, attach, hash) |

## Made quicker

| #  | **What**                    |             **Before** |              **After** | **How**                                                                                                                                                                                                                                                                                                                |
|:--:|:----------------------------|-----------------------:|-----------------------:|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1  | the first decode of a build |                 1.64 s |                 1.07 s | compression.zstd gives the bytes (0.05 s); our decoder only follows its state from block to block (repeat offsets, Huffman trees), which the re-encoder needs; the result is the same as a full decode (tested on frames of every kind and on the game's file). The gate still decodes the new file with both decoders |
| 2  | the CLI's own start         |                 0.27 s |                 0.17 s | a command imports only its own code (`__main__.py`: `_lazy`); the build tools collect the whole package (`--collect-submodules eldendisk`, nuitka `--include-package`)                                                                                                                                                 |
| 3  | the exe's hash at attach    |     0.08 s(1.7 s cold) |                      0 | remembered in `<TOOLS-DIR>\exe-sha256.json` by the file's path, size and time; `run` hashes afresh (the anchor of the session record) and remembers it for the steps and the other terminals                                                                                                                           |
| 1b | a whole build, one spell    |                  5.5 s |                  4.9 s | prepare 2.0 → 1.4 s (make 1.3, gate 2.2 unchanged)                                                                                                                                                                                                                                                                     |
| 4  | `innovate-spells apply`     | 2 attaches, a 3 s wait | 1 attach, no idle wait | the texts and the colours in one process, one session check, one write handle, one wait for the world; the colours are painted during the 3 s the text step watches the game keep its tables                                                                                                                           |

All tests pass, the 92 golden ones on the game's original `regulation.bin` included (1,818 passed).

## Decided not to do (2026-10-15)

| **What**                                                                                        | **Gain**                                                       | **Decision**                                                                      |
|:------------------------------------------------------------------------------------------------|:---------------------------------------------------------------|:----------------------------------------------------------------------------------|
| a one-folder exe (`eldendisk.exe` + its `_internal\`)                                           | 0.8 s at every command, 2.4 s at every `run` (its three steps) | the one-file exe stays: one file is what is shipped                               |
| the decoded game file's state kept between builds (`base.state.json`, keyed by the file's hash) | 1 s per build (1.07 s → 0.08 s, tried)                         | not kept: no more files in the vault; a build happens only when the spells change |

## Still open

| **What**                                                                                         | **Gain**   | **What it needs**                                                                                                                 |
|:-------------------------------------------------------------------------------------------------|:-----------|:----------------------------------------------------------------------------------------------------------------------------------|
| `read`, `read --live`, `export --live`, the creative block, the scans of `apply` inside the game | unknown    | the logs of a session (`run -v`, then `read -v`, `export --live -v`, `read monitor -v` from another terminal), sent by the author |
| the tests (1,700+, about 50 s)                                                                   | about half | `pytest-xdist` (not installed)                                                                                                    |


# Part 4: Every param table in the disk

Written 2026-10-15. Until now the disk's `params` held four rows of one table (`params.effects`: Black Flame), and six tables of the
workbench could be read and written by name outside it. The game holds far more: its `regulation.bin` (1.17.1) has **194 tables,
179,367 rows** (49 MB of row data): every weapon, armour, item, spell, effect, bullet, attack, enemy, drop, shop line, grace, cutscene ...
Part 4 puts **all of them** in the disk, to read and write freely, as every other value.

Decided by the author (2026-10-14): every table; read when named (lazy); `params.effects` folded into the tables; the layouts from
Paramdex.

## The names

`params.<Table>.<row id>.<field>`, the same as every path of the disk.

- **Table:** the game's own name, as in its `regulation.bin` (`EquipParamWeapon`, `EquipParamGoods`, `Magic`, `SpEffectParam`, `Bullet`,
  `AtkParam_Pc`, `NpcParam`, `ItemLotParam_map`, `ShopLineupParam`, `BonfireWarpParam` ...), in any letter case. The short names of the
  workbench still work (`Goods`, `SpEffect`, `ShopLineup`), as do Paramdex's (`MagicParam`, `BulletParam`, `AtkParam`, and `AtkPc`,
  `AtkNpc`) (`eldendisk/game/paramnames.py`).
- **Row:** the row's id in the game, a number.
- **Field:** Paramdex's name (`effectEndurance`, `mp`, `hp`, `iconId`), in any letter case; `*` and `?` work.

`params.effects` is gone: `params.SpEffectParam.1621000.effectEndurance` is Black Flame's duration, and a name under `params.effects`
says so. (The four rows had a hand-made range and two locked fields each; a field of the tables is checked by its type and bit width, and
an id that points at another row gets a note.)

## Read when named (lazy)

All the rows of all the tables would be hundreds of MB to gigabytes of JSON: the disk cannot build that every second, nor write it in one
file. So the disk holds every table, and reads its rows only when they are named.

| **Name**                                        | **What `read` gives**                                                                                                  |
|:------------------------------------------------|:-----------------------------------------------------------------------------------------------------------------------|
| `params`                                        | every table found with its number of rows (`{"NpcParam": {"rows": 7045}, ...}`): what the disk holds before a table is named |
| `params.NpcParam`                               | every row of the table (all its fields)                                                                                |
| `params.NpcParam.10000000`                      | one row                                                                                                                |
| `params.NpcParam.10000000.hp`                   | one field                                                                                                              |
| `params.NpcParam.*.hp`, `params.Magic.6230.mp*` | a field of every row, the fields that match                                                                            |

- `read` of the whole disk and `export` hold the index (the tables and their rows), not the rows themselves. The index is looked at about
  once a second, like the rest of `params` before.
- A script reads a row when it touches it: `x.params.NpcParam[10000000].hp`; `tools.write(x)` writes what it changed. A row that is not
  in the table says so in one line (not the list of every id).
- A row is read again at every `read`: a value `write` changed shows at once.

## The tables leave `disk.json` (2026-10-15)

Asked by the author once `params.json` existed: `disk.json` has no `params` block any more (it held each table's number of rows). The
tables are read from the game when they are named and written whole by `export --params`; the disk is `systems`, `character`,
`creative`.

- `read params` and `read params.*`: every table of the game with its rows, read from the game (no longer the disk's index).
- `read params.<Table>...`, `write params...`: unchanged (the game).
- A script's `tools.read()` still has `x.params.<Table>[id]`: the scripts' backend adds the tables to its own copy of the document,
  each row read when it is touched. That copy is not `disk.json`.
- The reader no longer looks at the tables about once a second (the index it kept for the disk): `read`, `read --live` and
  `export --live` read no param file at all.
- The schema no longer describes `params`.

The sections above that speak of the disk's index of the tables ("Read when named": `params` -> every table with its number of rows)
are replaced by this.

## `read disk...` and `read params...` (2026-10-15)

Asked by the author: the names say which file they belong to. `read disk.<path>` reads a path of `disk.json` (`disk.character.level`,
`disk.creative.resurrect.great_enemies.margit`), `read params.<path>` the game's tables (what `params.json` holds). `read disk` and
`read disk.*` are the whole document (as `read`). The values show with their prefix (`disk.character.level  386`), so a name read is the
name written in the file. The short names stay (`level`, `hp`, `attrs.*`, `margit`): the same values, shown as before. `write` takes
`disk.` names too (`write disk.character.level=150`).

## `export --params`: every row in a file (2026-10-15)

Asked by the author: the rows of the tables, all of them, in a file of their own next to `disk.json`.

```commandline
eldendisk.exe export              the document to output\disk.json (as before; --disk says it)
eldendisk.exe export --params     every row of every table to output\params.json
eldendisk.exe export --disk --params   both
```

- `params.json`: `{"profile": {...}, "written": time, "params": {Table: {row id: {field: value}}}, "skipped": {Table: why}}`, every
  table found in the game, every row, every field, read now (the same decoder as `read`). One row a line: `findstr "10000000"` gives a row.
- A table no layout decodes (6) has each row as its bytes: `{"_raw": "hex"}`. A table that cannot be read is under `skipped` with why.
- Once, never `--live`: about 490 MB, about 11 s (measured on the game's rows). Written table by table to a temp file that then replaces
  `params.json` (never held whole in memory). Not inside the game folder, like `disk.json`. It needs no vault (`disk.json` does).
- `read params...` and the scripts never read this file: they read the game (the file is for other tools and for looking through).
- `RandomAppearParam` has 26 ids used twice (different rows); a JSON object keeps one row per id (the last), as `read` of the table does.

## Write

`write params.<Table>.<id>.<field>=VALUE`, `=default` (the value of the first change in this game process), `write params=default`
(every one). The same portal, gate and checks as every write: the field's type and bit width, the row must be in the file. What a row
change does in the game is the game's: a Magic row is read at the cast, a Bullet row when the bullet is created (Part 1 of spec 1.6.3).

## The layouts

`tools/gen_paramdefs.py <Paramdex>/ER/Defs <the game's regulation.bin>` writes `eldendisk/game/paramlayouts.py`: for each table of the
file its param type, its row size, its rows, its first and last id in the original 1.17.1 file, the digest of its rows (tables of 64 KB
or less), and its fields (name, type, offset, bits, array) from the Paramdex def of its param type. Only the facts are copied, not the
descriptions.

- **188 of the 194 tables** have a def whose size is the file's row size (single-row tables padded up to 16 bytes included).
- **6 do not** (the game's rows are longer than the def: fields the def does not know yet): `BuddyParam`, `ChrModelParam`,
  `GameSystemCommonParam`, `PostureControlParam_WepRight`, `SignPuddleParam`, `SoundCutsceneParam`. They are in the index with their
  rows; reading a row of one says why it cannot be decoded, and nothing of them can be written.

## Finding the tables in memory

The game keeps every table in one list. The six chains of `params.catalog` are slots of it: one global (`exe + 0x3D85F58`), the slot
(`0x88 + n * 0x48`: Goods n = 3, AtkParam_Pc 8, Bullet 10, Magic 14, SpEffect 15, ShopLineup 27), then `+0x80`, `+0x80` to the file.
The profile gets the list as a block of its own:

```json
"repository": { "rva": "0x3D85F58", "first": "0x88", "stride": "0x48", "slots": 256, "tail": ["0x80", "0x80"] }
```

Each slot that ends in a valid param file (the same header checks as every read) is named, in this order:

1. by the param type the file gives (at `+0x10`) and its rows: a table that a build grew (Goods, Magic, SpEffect, Bullet, AtkParam_Pc,
   ShopLineup) has up to 200 rows more;
2. tables of the same type (`AtkParam_Pc` / `AtkParam_Npc`, `ItemLotParam_map` / `_enemy`, `GrassTypeParam_Lv1` / `_Lv2` ...) by their
   rows, row size, first and last row id;
3. then by the digest of their rows (`HPEstusFlaskRecoveryParam` / `MPEstusFlaskRecoveryParam`);
4. then by the table's name, in UTF-16, in the slot's object or behind a pointer in it.

What is left is not guessed: a slot that fits no table, or more than one, is left out with the reason, and two slots that look like one
table are both left out. Tables whose rows are the same byte for byte need step 4: `KeyAssignParam_TypeB` / `_TypeC`, the
`LoadBalancer...` tables of the other platforms, `MultiHPEstusFlaskBonusParam` / `MultiMPEstusFlaskBonusParam`, and
`WwiseValueToStrParam_Switch_PlayerEquipmentBottoms` / `_Tops`. Whether the PC game loads the tables of the other platforms at all is
for `probe` to show.

- The list is walked once (about 200 small reads); a walk that found nothing (the game was still loading) is made again after 5 s.
- The six chains of `params.catalog` stay: they win for their tables.
- **To check in the game:** `probe` lists every slot with the table it was named as, the reason for the ones left out with the texts next
  to their slot, and the tables of the game not found.

**Checked in the game (2026-10-15, `probe`, 1.17.1 with a build of one spell):** the list is as above: 194 slots (0 to 193), each a param
file, the six of `catalog` at their slots, the grown tables with their extra rows (Goods 2330, Magic 318, SpEffect 11356, Bullet 15477,
AtkParam_Pc 11019, ShopLineup 1297). 182 were named by type, rows, ids and digest alone. The other 12 (identical rows) all had their own
name as the **first** table name next to the slot, the names of the slots around it after it (slot 94: `..._ps4`, then `..._ps5`;
slot 95: `..._ps5`, then `..._xb1`). Step 4 now takes that first name only (a name further on is a neighbour's), which names all 194.
The PC game does load the tables of the other platforms (`_ps4`, `_xb1` ...).

## Tests

`tests/test_param_walk.py`: a fake list with files that say their type; a table named by type and rows, a grown one, one type told apart
by rows and ids, by digest, by the name next to the slot; identical tables and two slots of one table left out; the walk again after
5 s; `read params.<Table>` and `params.<Table>.*.<field>` through the list; `probe` (text and JSON, read-only); a script's table read
row by row. The tests of `params.effects` became tests of `params.SpEffectParam` (the same rows, the same checks).

## Optimization (2026-10-15)

Measured on the game's own rows (1.17.1, the rows of `regulation.bin`, outside the game) and a fake game. A whole table is big:
`read params.SpEffectParam` is 11,354 rows of 359 fields, 4 million values.

| **What** | **Before** | **After** | **How** |
|:---|---:|---:|:---|
| decoding a row (SpEffectParam) | 156 us | 46 us | a function made once per table: one `struct.unpack` of the whole row, the values put in a dict; an f32 is rounded for the document once per value (`_SHOWN`) |
| decoding every row of every table (178,361) | 7.4 s | 2.0 s | the same; the result is the same as field by field for every row of the game (checked once, and by the golden test) |
| `params.<Table>.*.<field>` | every field decoded, then picked | only the fields that match | a decoder for those fields |
| the tree of `read params.SpEffectParam` | 8.6 s | 5.7 s | the rows into one list (no nested generators, no dict per level) |
| printing it | 17 s | 3.6 s | the console asked once whether it takes colours and links, not per line; the lines written 2,000 at a time |
| `read params.SpEffectParam` in all | about 27 s | about 10 s | |
| a table's slot | the walk's list scanned per table (the index: 194 tables a second) | one look-up | `{table: slot}` kept with the walk |

**The layouts were made from a build (fixed 2026-10-15).** `paramlayouts.py` of the first Part 4 commit was generated while a `run`
had the build in the game folder: Goods, Magic, SpEffect, Bullet, AtkParam_Pc and ShopLineup had the build's rows (one or two more) and
Magic the build's digest. A game without that build would then not have its six tables named by the walk (fewer rows than the layout;
the six chains of `catalog` still found them). Made again from the original (the vault's backup, sha256 checked), and
`tools/gen_paramdefs.py` now refuses a file that is not the game's original.

Not changed: `--json` of a whole table (0.5 s), the import of the layouts (2 ms), the walk (once). A whole table in a terminal is still
millions of lines: `--json` or a file (`> table.txt`) is the quick way to look through one.

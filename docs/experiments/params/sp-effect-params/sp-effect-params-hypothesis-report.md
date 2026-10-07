# SpEffectParam in memory: finding and editing the Black Flame burn duration (Elden Ring 1.17.1)

Project: Elden-Disk (offline, Python)
Game build: Elden Ring 1.17.1 (`eldenring.exe` SHA-256 `1a3547101327f65d0c76da2f9190ac0aa66871ea42bae2aecc61e11a8b597891`)
Tools used: Smithbox (view/export only, nothing saved or imported into the game), Cheat Engine, Elden Ring started with `eldendisk run` (offline, no EAC), Paramdex definitions
Period: 2026-10-07 to 2026-10-08
Status: **H1 to H7 confirmed on the real game (H7 reported by the author on 2026-10-08, no log kept). H8 not tested yet** (section 6).

## 1. Goal

Find out whether Elden-Disk can change a game **param** (a row of one of the game's data tables) while the game runs, using the Black Flame spells as the sample: make their burn last forever instead of about 2 seconds. This is the first stage of "modify item abilities" and tells us how a `params` block in `offsets.json` has to look. No code was written for this report.

## 2. Result in one paragraph

The game keeps `SpEffectParam` as one contiguous file in memory (11,354 rows of 912 bytes). The field `effectEndurance` (f32 at offset `0x8` of a row) is the effect duration: `-1` means permanent. The file head can be reached from `eldenring.exe` with three pointer chains that stayed valid across two game restarts; a row is `head + data offset from the row descriptor table`. Writing `-1` into row 1621000 (Black Flame) through one of these chains made the burn stay on a frog in Mogwyn Palace until it died. The other three Black Flame rows were located by calculation and **not** tried in the game.

## 3. Hypotheses and outcome

| ID | Hypothesis | Test | Outcome |
|:--|:--|:--|:--|
| H1 | The Black Flame burn is a row of `SpEffectParam` and its duration is `effectEndurance` | Smithbox view of the rows, CSV export, Paramdex definition; `-1` = permanent, `0` = instant | Confirmed on paper (section 4) |
| H2 | That row exists in the game's memory as a byte copy of the CSV row | AOB scan of the first 320 bytes of row 1621000 (`blackflame-aob.txt`) | Confirmed: 16 hits (`ce-first-scan-for-blackflame-group.png`) |
| H3 | Writing `effectEndurance` there changes the burn in the game | Set B addresses (rows 1621000, 1623000, 1624010, 1625000, 1626001), value set to `-1`, Black Flame cast on a frog | **Confirmed**: one cast, the burn never ends and the black-fire effect stays on the target (`buring.png`) |
| H4 | The table has the file structure we assumed | Read in Cheat Engine: row count (u16 at head+0xA) = 11,354; data start (u64 at head+0x30) = 272,560 | Confirmed: both equal the CSV; 272,560 = 0x40 + 11,354 × 24 |
| H5 | A static pointer chain from `eldenring.exe` reaches the file head | Pointer scan on the head | Confirmed: three chains X, Y, Z (section 5) |
| H6 | The chains still work after restarting the game, and writing through one is enough | Closed and restarted the game twice; wrote `-1` through X | Confirmed: all three still pointed to the same cell after both restarts; changing X changed Y and Z (they are one memory cell); the frog test repeated with `-1` written through X gave the same permanent burn |
| H7 | The same works for Scouring Black Flame (1623000), Black Flame Ritual (1625000) and Black Flame Blade (1626001) | run by the author with the tool, 2026-10-08 | **Confirmed (reported)**: all four rows burn without end, enemies burn to death, the effect bar stays lit. The addresses were calculated (section 5), not measured |
| H8 | The other fields (`motionInterval`, `changeHpRate`, `changeHpPoint`, `atkOccurrenceSpEffectId`, `vfxId`) can be read and written the same way | not run | **Open**: offsets taken from Paramdex only |

A note on scope: when `-1` was written for Black Flame (1621000), Black Flame Ritual was unchanged. Each row has to be edited on its own.

## 4. What the data says (Smithbox, CSV, Paramdex)

Sources: the CSV exports of `SpEffectParam` (11,354 rows, 370 columns), `Magic`, `Bullet` and `AtkParam_Pc`, and `ER/Defs/SpEffect.xml` from Paramdex.

- A `SpEffectParam` row is **912 bytes**.
- `effectEndurance`: f32 at `0x8`. `-1` = permanent, `0` = instant one-shot. All burn rows below have `2`.
- Black Flame rows used by the player's spells (NPC rows start at 29000, so these rows are not shared with enemies):

| Row | Meaning | `effectEndurance` |
|:--|:--|:--|
| 1621000 | Black Flame | 2 |
| 1623000 | Scouring Black Flame | 2 |
| 1625000 | Black Flame Ritual | 2 |
| 1626001 | Black Flame Blade, the burn put on the enemy (applied through `atkOccurrenceSpEffectId` of buff row 1626000) | 2 |
| 1624010 | Noble Presence (same byte pattern, left out of the Black Flame group) | 2 |

- Related rows that are **not** burns of the spells: 1627000 / 1627001 (Black Flame's Protection), 835 (Black Flame Tornado weapon art), 855 / 860 (weapon burns).
- Common burn values in these rows: `motionInterval` 0.1, `changeHpRate` 0.1, `changeHpPoint` 1, `spCategory` 20, `isHpBurnEffect` 1, `vfxId` 9010.
- `atkOccurrenceSpEffectId` is "apply this other SpEffect to whoever is hit"; `-1` = none. Only row 1626000 points to a row (1626001); all four rows edited here have `-1`. `vfxId` is the visual effect (`-1` = none); all four use 9010.
- Field offsets used (reliable for the first 343 fields of the Paramdex layout; columns added to the CSV after that definition have unknown offsets):

| Field | Type | Offset in the row |
|:--|:--|:--|
| `effectEndurance` | f32 | `0x8` |
| `motionInterval` | f32 | `0xC` |
| `changeHpRate` | f32 | `0x9C` |
| `changeHpPoint` | s32 | `0xA0` |
| `atkOccurrenceSpEffectId` | s32 | `0x12C` |
| `vfxId` | s32 | `0x170` |

A searchable list of all 370 fields (with the value in row 1621000 and the most common value over all rows) is `SpEffect Field Reference.html` in this folder.

## 5. How the table is laid out in memory, and how to reach it

### 5.1 File structure (measured)

```
head                      start of the param file
head + 0x0A   u16         row count               = 11354
head + 0x30   u64         data start              = 272560 (0x428B0) = 0x40 + 11354 * 24
head + 0x40               row descriptor table, 24 bytes per row:
                            +0x00 u32 row id (+4 padding)
                            +0x08 u64 data offset, counted from head
                            +0x10 u64 name offset
head + <data offset>      row data, contiguous, 912 bytes per row
```

Row 1621000 is row index 8437 of the CSV: `0x428B0 + 8437 × 912 + 8 = 0x799188`, which is the address of its `effectEndurance` counted from the head (matches Cheat Engine).

### 5.2 `effectEndurance` of the Black Flame rows, counted from the head

| Row | Offset from head | Tested in game |
|:--|:--|:--|
| 1621000 Black Flame | `0x799188` | yes |
| 1623000 Scouring Black Flame | `0x799518` | no (calculated) |
| 1624010 Noble Presence | `0x799C38` | no (calculated) |
| 1625000 Black Flame Ritual | `0x799FC8` | no (calculated) |
| 1626001 Black Flame Blade | `0x79A6E8` | no (calculated) |

The differences between them are whole multiples of 912 bytes (0x390), as expected for contiguous rows.

### 5.3 Pointer chains to the head (valid on 1.17.1)

Offsets are applied in order from the module base; the chain ends at the file head. In Cheat Engine, "Add Address Manually" with "Pointer" ticked lists the offsets from the last applied to the first, and the final entry (`799188`) is the row field offset.

| Chain | Base | Then |
|:--|:--|:--|
| X | `eldenring.exe + 0x4861FB0` | `+0x98` → `+0xE8` → `+0x130` |
| Y | `eldenring.exe + 0x3D7D568` | `+0x148` → `+0xE8` → `+0x130` |
| Z | `eldenring.exe + 0x3D85F58` | `+0x4C0` → `+0x80` → `+0x80` |

All three were checked after two game restarts and always gave the same address (`7FF466E87298` in one run, `7FF45E186C28` in another; the base address moves, the chains do not). Candidate chains that started at `+0458F910` or ended in `+0x3010` were not valid after a restart and were discarded. The chains are in `ce-spEffectParam.CT` (entries Path X / Y / Z).

### 5.4 Copies of the table in memory

The row-index AOB (`blackflame-rowtable-aob.txt`, three consecutive descriptors for ids 1621000, 1623000, 1624000) found **three copies** of the table. In both runs observed, the copy the chains lead to was the one at the **highest address**; Set B (the higher addresses in the 16-hit scan) is the set that changed the game. Whether the lower copies (Set A) have any effect was not recorded. Do not write to copies found by scanning; always go through a chain.

For debugging only: the head of a copy is `hit address − 0x31738` for the row-index AOB. The tool must not scan.

## 6. Not yet tested

- H8: any field other than `effectEndurance`.
- Behaviour at the title screen (before a character is loaded): not checked.
- A burn that is already on an enemy keeps its old duration; this was not tested but follows from the effect being copied onto the target when it is applied. Treat as unverified.
- Restoring the default: the default value (`2` for all four rows) comes from the CSV; writing it back with the tool was not tried.

## 7. Method notes and pitfalls

What worked:
1. Identify the rows in Smithbox / CSV, take the first 320 bytes of one row as an AOB, scan in Cheat Engine.
2. Add the hits as addresses, set the field, test on a target that does not die at once.
3. Read row count and data start next to the first row to prove the file structure.
4. Pointer scan for the head with "static address only" and "8-byte aligned" on; level 3 with max offset 4095 found 0 paths, **level 4 with max offset 16383 found 32 paths**.
5. Validate paths after restarting the game; the "Points to" column of the pointer scan window is evaluated live, so no rescan is needed.

Cheat Engine notes:
- AOB scan needs Value Type "Array of byte"; after "New Scan" the type falls back to "4 Bytes" and has to be set again.
- Open a saved pointer scan with Memory View > Tools > Pointer scan > File > Open (the main window's "Open file" opens a binary file dialog).
- The pointer scan was heavy on a 16 GB machine with the game and an IDE running (the PC froze for a while). Close other programs, use fewer threads, stop the scan with the Stop button rather than killing it.
- Use the game offline only (`eldendisk run`); with a Steam-started game EAC blocks the read.

## 8. What this means for Elden-Disk

- Params can be read and written by name through an `offsets.json` block: chains, file layout, field offsets and a name → row id list. See `docs/implementations/implementation_plan_v1.6.3.md`.
- Edits are lost when the game closes, so they never touch the save; a `write` still requires a valid `run` session like every other edit.
- `atkOccurrenceSpEffectId` and `vfxId` are locked read-only in the first version because a wrong id can break the game (section 4).
- Safe use: offline only.

## 9. Evidence in this folder

| File | What it is |
|:--|:--|
| `blackflame-aob.txt`, `blackflame-row-320.txt` | AOB (first 320 bytes of row 1621000) used for the first scan |
| `blackflame-rowtable-aob.txt` | descriptor-table AOB used to locate the file head |
| `ce-first-scan-for-blackflame-group.png`, `ce-first-scaning-for-blackflame-aob.png`, `first-scaning-for-blackflame-aob.png`, `first-scaning-for-blackflame-aob-2.png` | first scans (16 hits) |
| `ce-add-address-manually-for-blackflames-set-effectEndurance.png` | Sets A and B, five rows each, all `effectEndurance` = 2 (Set B marked as the working one) |
| `ce-add-address-manually-for-starter-addr.png` | head address entry |
| `buring.png` | in-game: the burn stays on the target after `-1` |
| `pointer-chain/poiter-scan-paths-32.png` | pointer scan result, 32 paths |
| `pointer-chain/poiter-scan-paths-xyz.png`, `pointer-chain/poiter-scan-paths-xyz-(re-open game).png` | chains X, Y, Z before and after restarting the game |
| `pointer-chain/sp2.PTR` (+ `sp2.PTR.results.*`) | saved Cheat Engine pointer scan (the `.results.*` files are its result chunks, most are empty) |
| `ce-spEffectParam.CT` | Cheat Engine table: row count, data start, head, Path X / Y / Z |
| `SpEffect Field Reference.html` | all 370 SpEffectParam fields: type, offset, description, value in row 1621000 |

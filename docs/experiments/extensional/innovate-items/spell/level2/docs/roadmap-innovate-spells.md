# Roadmap: innovate spells (all spell kinds) and the params workbench

_Status: Phase 1 and Phase 2 CLOSED 2026-10-11 with **7 slots available**; the rest (slots 8 and above, step 2.6) is deferred, not removed. Last updated 2026-10-11. Update the checkboxes as work is done; do not delete finished items._

## Core purpose

Make `extension.json` able to **describe and build every kind of spell the game has**, in up to **64 slots**, as a `regulation.bin` that the game accepts. The number of slots each kind allows is not assumed: it is **measured in the game**.

To get there safely, the live **read/write params** tool (Phase 1) becomes the **workbench** that tests ideas in the running game first, without building a file. The **extension** (Phase 2) then bakes what worked into `regulation.bin`.

Principles that hold throughout:
- Nothing is called "works" until the user has seen it in the game. Unit tests and the gate only say "nothing we know the game rejects".
- The gate's envelope (`MAX_CHANGED_BLOCKS` 27 and `MAX_FRAME_GROWTH` 292,000 since T10, `MAX_BODY_GROWTH` 219,000) is raised only after a bigger file has passed in the game. No bypass; a separate test tool builds the bigger file.
- Existing rows are never changed or removed; spells are new rows.
- Discuss the design before each large change. The user tests in the game and makes the commits.
- Every step ends with tests and updated docs (spec, cli-commands, changes, manual test plan).

## Where we are (baseline)

- ✓ Spells built as new rows appended to Goods, Magic, SpEffect, ShopLineup (`grow.py`), all slots the same way.
- ✓ Gate (R1-R7, G5, G11-G16) judging the file read back from disk.
- ✓ Slot 1 (`reverse_curse_technique`, a self buff) passed in the real game.
- ✓ Live read/write for 4 Black Flame SpEffect rows; the reader accepts a table that was grown by an extension (gap between descriptors and data). Since Phase 1: live read/write of any row of six tables, and a check of a built file against the game (below).
- ✓ Survey of the game's spell kinds from the real Magic table (below).
- ✓ The T7 test (fifth table, Bullet; encoder fix for repeat-offset states) was built, then reverted by the author before use; re-applied in Phase 2.3 (2026-10-10).

## What the game's data says about spell kinds

Magic table of 1.17.1: 317 rows; 217 are player spells (127 incantations, 90 sorceries), the rest belong to NPCs and bosses (usable as templates).

| Kind | What the Magic row calls (`refCategory1`) | Player spells | Examples |
|:--|:--|:-:|:--|
| projectile / area | Bullet (1) | 172 | Flame Sling, Glintstone Pebble, Lightning Spear, mists, beams, breaths |
| direct attack | Attack row (0) | 19 | Dragonclaw, Dragonmaw, Scarlet Aeonia, Gavel of Haima |
| buff | SpEffect (2) | 15 | Flame Grant Me Strength, Fortification, Starlight, Unseen Form |
| weapon enchant | SpEffect (2) + `isEnchant` | 9 | Black Flame Blade, Electrify Armament, Scholar's Armament |
| shield enchant | SpEffect (2) + `isShieldEnchant` | 2 | Immutable Shield, Scholar's Shield |

Also true in the data:
- The cast motion (`refType`, 135 values over 217 spells) is an animation plus a script in the game's own files. It cannot be changed from the regulation; a spell can only pick one that exists, and the motion decides which of the ref slots (`refId1-4`) it fires.
- `goodsType` of the Goods row follows attack vs support: 5 attack sorcery, 17 support sorcery, 16 attack incantation, 18 support incantation (inferred, not yet tested).
- Heals (Heal, Great Heal, ...) are Bullet spells that apply a SpEffect; they share one cast motion (34).

Rows a kind needs (all kinds also need Goods + Magic; Shop is optional):

| Kind | Extra tables | Bytes per new row (with 24 B record) |
|:--|:--|:--|
| buff | SpEffect | 936 |
| enchant | SpEffect (to be checked) | 936 |
| clone | none | 0 |
| projectile | Bullet (+ SpEffect for another on-hit effect) | 296 per bullet, a spell uses 2-4 |
| attack | AtkParam_Pc + Bullet | 480 per attack |

What limits the number of slots (to be measured, not guessed):
- a fixed cost per table that grows (its record array is rewritten: Bullet about 6-7 blocks, AtkParam_Pc about 4-5, SpEffect about 4);
- bytes added per slot; proven in the game: decoded +219 KB, frame +234,768 B, 20 re-encoded blocks (T7, with a grown Bullet table; T6 had 13); 466 KB failed;
- the merchant has only 7 free shop lines (slots 8 and above cannot be sold).

## Phase 1: read/write params as the workbench

Goal: read and write the rows and fields a spell uses, in the running game, for the tables Goods, Magic, SpEffect, Bullet, AtkParam_Pc, ShopLineup; and check a built `regulation.bin` against the game.

- ✓ **1.0 Study.** Done: see [phase1-params-workbench.md](phase1-params-workbench.md) (facts, open questions A-C, design, decisions for the author). Whether the other tables can be found without a Cheat Engine measurement is decided by the probe in 1.2a.
- ✓ **1.1 Quick experiment** (2026-10-09, passed in the game). `changeHpRate` set to -1 (with `effectEndurance` -1 and `changeHpPoint` 10 at the same time) on the Black Flame rows: the bullet hits and damages, then the burn **raises** the target's health until it is full. A negative `changeHpRate` heals even with `isHpBurnEffect` set. Second run (same day): `changeHpRate` -10 on the burn and `effectEndurance` -1 (never ends): the target's health jumps up again and again, strongly, and it cannot be killed. So the value is probably a percent of max health per tick (`motionInterval` 0.1 s; the original 0.1 is a small percent per tick, as Black Flame burns by max health), and -1 for the duration means the effect never ends. Still to measure: the exact unit, and the strength and duration that give a useful heal (step 2.3).
- ✓ **1.2a Probe.** `read --probe-params`: read-only, lists where the other tables are in memory (answers question A). First run in the game (2026-10-09): 191 param files reachable from the global of chain Z, all with the same tail `+0x80 -> +0x80`, one entry every 0x48 bytes. **Found: BulletParam at selector 0x358 and AtkParam_Pc at 0x2C8** (chains `0x3D85F58 -> 0x358 -> 0x80 -> 0x80` and `... -> 0x2C8 -> ...`). Goods, Magic and ShopLineup were not recognised because the reader refused their gap (the slot-1 build has gaps of 184, 168 and 56 bytes, not a multiple of 16); the rule is now a multiple of 4 and the probe has to be run again. Second run: all six tables found (Goods `0x160`, Magic `0x478`, Shop `0x820`, Bullet `0x358`, AtkParam_Pc `0x2C8`, SpEffect `0x4C0`; chains in phase1-params-workbench.md).
- ✓ **1.2b Generic read.** Any row of the six tables, any field by name (field layouts from `paramdefs.py`). Matches the original file field for field. Coded and tested (`read --param`, `params.catalog` in `offsets.json`, `game/paramlayouts.py`, golden test against the real file); run in the game 2026-10-09: Magic 6230, Bullet 10621001, SpEffect 1621000 and the extension's own Magic row 2230000 all read correctly.
- ✓ **1.3 Generic write.** Numeric fields only; the first read of a value keeps the game's own value for `--reset` (no hand-written defaults); offline and vault rules as today. `write --set params.<Table>.<id>.<field>`, `--reset` from `params-snapshot.json`. Passed in the game 2026-10-09: `Magic.6230.mp` 21 → 10 → reset → 21, each confirmed by `read`. Question B, first answers (2026-10-09): see 1.3b.
- ✓ **1.3b Which table the game reads live** (2026-10-09, passed in the game). **Magic** is read when the spell is cast: `Magic.6230.mp=0` makes Scouring Black Flame cost 0 FP, other spells cost the normal FP, and the value is still in force after Quit Game → Title Screen → Continue → Enter World (the tables are not reloaded on a character load; a restart of the game process does reset them). **Bullet** is read when the bullet is spawned: `Bullet.10621000.life` 1.5 → 0.2 makes the fireball vanish after 0.2 s before it reaches the target, `life=10` lets it arrive as before; so `life` is the bullet's lifetime in seconds. `write --reset all` put `life` back to 1.5 from the snapshot. Black Flame Ritual (Magic 6240, flame bullet 10625002, life 4.0): `life=12` keeps the flame around the caster much longer; `life=-1` never ends, not even after resting at a grace. A bullet that already exists keeps the life it was born with: `write --reset` (back to 4.0) changed only the next cast, the old flame stayed until Quit to Title → Continue. So a changed row acts on what is created afterwards, never on what is already in the world. Not measured yet: Goods in the menu, and a SpEffect that is already on a target.
- ✓ **1.4 Check against the build** (`read --param-check`). Compare the rows of a built `regulation.bin` with the same rows in the running game; report differences. Coded and tested (`commands/paramcheck.py`, `Tables.all_rows`; the file side opens the container with the extension's own code and matches rows by id, byte for byte, then names the fields that differ); Passed in the game 2026-10-09: the slot-1 build (`extension/innovate-items/spells/regulation.bin`) against the game started with it: Goods 2330, Magic 318, SpEffect 11356, Bullet 15475, AtkParam_Pc 11017, ShopLineup 1297 rows, every row equal. So the game does not change the param data when it loads the file, and the rows the extension added are in the game exactly as built.
- [ ] Tests (fake memory layer) and docs for each step.

## Phase 2: extension innovate spells, all kinds (CLOSED 2026-10-11)

Goal: `extension.json` accepts and builds the five kinds; the number of slots per kind is known from the game.

**Closed by the author 2026-10-11: **7 slots are available** (slots 1-7, the ones with a shop line); slots 8-20 stay in the design file (`code/extension.json` has 20 slots: what the gate lets one build, T10) and are built, but cannot be bought yet; the format still allows up to 64 (raise `maximum`), and how to obtain slots 8 and above is deferred (decided 2026-10-11).** Not run in the game, optional: P3-P5, E2-E4, CL4-CL5.

- ✓ **2.0 Spec.** Design the file: `kind`, the template (`from`), fields per kind, how row ids follow the slot, what a slot above 7 may contain. Approved by the author before code. Draft written 2026-10-09: [phase2-spells-spec-draft.md](phase2-spells-spec-draft.md) (one engine: copy the chain's own rows, then `set`; decisions: `from` = numeric Magic id, slots 8-64 later, names stored only). Approved by the author 2026-10-09 (all six decisions); the one change made while building 2.1 is noted in the draft (section 9).
- ✓ **2.1 `clone`.** Coded, tested and passed in the game (2026-10-09): copy a game spell's Goods and Magic rows (it keeps the template's chain), change cost, requirements, shop and single numbers with `set`; `kind` defaults to `buff`, so Z4 and the secured files are unchanged; `check_clone` in the gate; 66 new tests. Game, 2026-10-09: a file with slot 1 (buff) and a Black Flame clone built (13 blocks), the game loaded it, and `read --param-check` found every row equal (Goods 2331, Magic 319, ShopLineup 1298). Bought, memorized and cast: the same as the normal Black Flame, at the new cost of 5 FP and with the new requirements (CL1). `set` also passed (CL3, 2026-10-10: `Magic.6210.slotLength` written to the copy). Still open, optional: CL4 (a sorcery in the incantation merchant), CL5 (type refusal). Spec 1.7.0 section 4b.
- ✓ **2.2 `buff` and `enchant`.** Coded and tested 2026-10-10 (42 new tests); E1 passed in the game 2026-10-10 (E2-E4 optional): `enchant` and `buff` with `from` copy the template's own SpEffect rows (rows reached by more than 3 spells stay shared) into a block of 8 ids per slot, and `set` takes `SpEffect.<id>.<field>`; the heal-over-time `buff` without `from` is unchanged. Enchant needs no other table: it is a Magic row with `isEnchant` / `isShieldEnchant` plus SpEffect rows. Spec 1.7.0 section 4c.
- ✓ **2.3 `projectile`.** New Bullet rows (fifth table): ✓ re-applied the T7 work (encoder fix for repeat-offset states, Bullet definitions, `tools/envelope_test.py`, 2026-10-10); ✓ T7 passed in the game 2026-10-10 (a grown fifth table, 20 re-encoded blocks); ✓ gate `MAX_CHANGED_BLOCKS` 13 -> 20; ✓ the kind: coded 2026-10-10 (41 new tests), P1 and P2 passed in the game 2026-10-10 (a Black Flame copy with a 30 s burn; every row equal), P3-P5 optional: copies the template's own Bullet and SpEffect rows; the attack rows stay the game's until 2.4. Spec 1.7.0 section 4d. A Black Flame whose burn becomes a heal (Magic 6210 -> Bullets 10621000 and 10621050, burn SpEffect 1621000 (to be confirmed: the bullet rows that hold it are 10621001 and 10621051)) is the first target.
- ✓ **2.4 `attack`.** New AtkParam_Pc rows (sixth table) with its own damage. T8 did NOT pass in the game (2026-10-10): the table grown backwards had to move the 6.17 MB AtkParam_Npc in front of it (body +6.27 MB, stopped at the title screen). T9 PASSED (2026-10-10): AtkParam_Pc grown at its end (`grow._grow_end`: body +124,560, frame +242,464, 26 blocks); the gate went to 26 blocks / 243,000. Coded and tested: `projectile` copies the template's own Atk rows (Black Flame: 62101, 62106), kind `attack` for the 5 player spells that make a direct attack (4430, 4440, 4450, 7080, 7510), `AtkParam_Pc.<id>.<field>` keys, block of 8 per slot, ids from 710000000, the live reader accepts the new layout. In-game tests A0-A6 all passed 2026-10-11 (exe from `dev_pipeline.py`, 5 slots, gate passed with 26 blocks each time): the Black Flame copy with its own Atk rows (A0) and the `attack` copy of 4440 (A1) were bought, memorized and cast as the original; `read --param-check` found every row equal (AtkParam_Pc 11025 = 11017 + 8, A2); `AtkParam_Pc.710000032.atkMag` read 180, and 1800 after `set` made the copy hit about ten times as hard while the original 4440 stayed 180 (A3, A4); `attack` from 6210 and `projectile` from 4440 stop with an error and build nothing (A5, A6). Results: [test-group-a.md](../testing/test-group-a.md). Spec 1.7.0 section 4e.
- ✓ **2.5 Capacity experiments.** Target decided 2026-10-11: **16-20 slots in all** (not 64 of every kind). ✓ `tools/capacity.py` (offline: slots of each kind and mixes against the gate) and the table in spec 1.7.0 section 10b: a design without `projectile` fits 20 slots; with one `projectile` it needs 27 blocks and a frame of about 291,000 (gate 26 / 243,000); 16 or more of one `attack` / `projectile` kind move a table (not needed for the target). ✓ `envelope_test.py --no-copies` builds a design exactly. ✓ T10 passed in the game 2026-10-11: the 20-slot design (2 projectile + 2 attack + 16 buff; 27 blocks, frame +291,040; prices 1001-1007 in the shop) loaded and the merchant's list was complete; the gate went to 27 blocks / 292,000 frame, and the per-kind limits are in spec 1.7.0 section 10b (20 slots with up to 8 `projectile`; 64 `buff`/`enchant` and 16+ of one `attack`/`projectile` kind stay beyond it). Not tested in the game: slots 8-20 (they have no shop line; 2.6 is deferred).
- [ ] ~~**2.6 Slots 8-64.** Decide how a spell without a shop line is obtained (for example a replaced item lot, a starting item, or a different shop); implement the one chosen.~~ **Deferred by the author 2026-10-11, not removed**: slots 8-20 stay in the design file and the format keeps its 64; the survey of the merchants' free shop lines (and the other options) is for later.
- ✓ **2.7 Build selection** (asked 2026-10-11, after Phase 2 was closed). `--add spells.slots.<id> [...]` builds only the spells named; the choice is kept in `spells.build.json`; `run` builds the same selection (every spell without one), reuses the latest build while nothing changed, and `--secure` secures what the build holds. Offline: 39 new tests and 3 golden builds of a template spell alone in a late slot pass the gate. [ ] S1 in the game (manual test plan): a spell built without the slots before it.
- ✓ **2.8 `cast_motion` and `effect.visual` by number** (asked 2026-10-11). Each takes a name or the game's own number (`Magic.refType` 0-999, `SpEffect.vfxId` -1 to 99,999,999); the build refuses a number the game does not use; the handbook has a Motion Finder (135 numbers), a Visual Finder (72) and a Cast Finder (the four cast numbers of each of the 217 player spells; usable through `set` on a remixed spell). [ ] M1, M2, M4 in the game (manual test plan): a number other than the named ones.
- ✓ Tests, docs, golden hash anchors for each kind; manual test plan entries.

## Open decisions

- ✓ How `from` names a template: a numeric Magic id (author, 2026-10-09; a short name would need Paramdex, whose licence has not been checked).
- [ ] ~~How slots 8-64 are obtained in the game (2.6).~~ Deferred 2026-10-11; to be discussed later.
- ✓ Names and descriptions (1.7.1, Level 3 step 1): not by archive files but by rebuilding the game's text tables in memory (handbook Chapter 19). Decided 2026-10-11: the `text` object replaces `name`/`description`; applied automatically after the swap.
- ✓ A new colour of the fire (1.7.1, Level 3 step 3, first part): `flame_color` recolours the fire of Flame, Grant Me Strength (the cast and the burst) in the running game (handbook 19.7).
- [ ] Icons (Level 3 step 2): to be discussed.

## Risks

- ✓ (Phase 1) The other tables did not need a Cheat Engine measurement: `read --probe-params` found them all from the known global.
- Live edits only take effect where the game reads the row: measured Magic at the cast, Bullet at spawn, and a changed row acts on what is created afterwards; Goods in the menu and SpEffect on a target are not measured.
- A cast motion may fire ref slots in a way that does not match a new spell's rows; found only by trying.
- The envelope may be lower than hoped for five or six tables; the answer is a smaller number of slots, not a gate bypass.

## Phase 3: Item Customization Level 3 (version 1.7.1)

Level 3 = items that never existed in the game: their own name, text, icon, colour/effect. Order agreed 2026-10-11: (1) name and description text, (2) icon, (3) new colour/effect.

- ✓ **3.1a Where the text lives and how to read it.** `tools/dump_msgbnd.py` (the game's archive: RSA index, AES-128, DCX KRAK) dumped `item`/`menu` `msgbnd` and their FMG tables.
- ✓ **3.1b Does the game read a loose file?** No (tried 2026-10-11, with the files in the right folder the old name still showed).
- ✓ **3.1c A rebuilt table in the game's memory.** `tools/probe_text.py` and a first experiment (since removed): renamed an item and added the new item's name, short line and long description in the real game.
- ✓ **3.1d A fixed chain from the exe** (`eldenring.exe + 0x3D61FB8` → object, slot at `+ 0x1F20 + N * 8`) was found and tried: it led to the right object in 3 of 5 runs of the same game and to memory given back in 2. **Dropped** (2026-10-11): the tables and the array are found by shape and size with a game-friendly scan (`writer/scan.py`).
- ✓ **3.1e In the tool.** `text` object in the spell design (replaces `name`/`description`, before `set`), profile block `text` (`files`, `sizes`), `writer/scan.py`, `writer/text.py`, `write --text [--wait | --when-loaded]`, and `run` starts it by itself once a character is in the world (`Hooks.on_running`). Three `run` sessions of 2026-10-11: written and read back every time, ~75 s after the character appears.
- [ ] **3.1f In the game: what is seen** (manual plan 1.7.1, TX): the name, the short line and the long description show; a secured build is unchanged by a text edit.
- [ ] **3.1g Thai (and other scripts).** Not tried; the font may lack the glyphs.
- [ ] **3.2 Icon.** After the text work is finished. First try: reuse an existing `iconId` through `set` (probably possible already, untried); a truly new picture needs the menu texture archive.
- ✓ **3.3a The colour of the fire** (1.7.1): the effect files `524400` (cast) and `524401` (burst) are found in memory by their colours and recoloured with `flame_color`; `write --flame-color [--wait | --when-loaded]`, started by `run`. Three sessions of 2026-10-11: 68 places written and read back, ~7 s after the character appears.
- [ ] **3.3b What is seen** (manual plan 1.7.1, FL): the fire in the game is the design's colour.
- [ ] **3.3c The colour of the fire on the body** (effect `524402`) and a new effect, not only a colour.

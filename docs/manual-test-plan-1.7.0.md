# Manual test plan 1.7.0 (real game, Windows): extensions and `innovate-items spells`

Only what is new in 1.7.0. The swap itself is [manual-test-plan-1.6.4.md](manual-test-plan-1.6.4.md) (RG/RH checks still apply, with the file now coming from the extension). Tick `[ ]` as you go and write what you saw next to anything unexpected.

> [!IMPORTANT]
> **Before anything:** copy the save folder (`%APPDATA%\EldenRing\<SteamID64>`) **and** the game's own `regulation.bin` (`...\ELDEN RING\Game\regulation.bin`) somewhere safe; `vault status` must say no unresolved session. Offline only.

`<ext>` = `<vault>\extension`. The design is `code\extension.json` in the source (the Z4 item); `build -c -em` embeds it in the exe. With the vault ON, `run` swaps `regulation.secured.bin` when the design is unchanged and secured; otherwise it builds (about 20-30 s) and the gate must pass before the host starts.

## EX. The build (`extension innovate-items spells`, the same build `run` does)

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| EX1 | `eldendisk.exe extension --list` (nothing built yet) | the spec path with `(embedded)`, `1 item in the design`, `secured  none yet …`, `last build  none yet`; exit `0`; nothing is created on disk | [ ] |
| EX2 | `extension innovate-items spells --add all` | about 20-30 s; `✓ … built, gate passed (13 blocks re-encoded)`; rows `sha256`, `content 0ef6b851…`, path of `regulation.bin`; `<ext>\innovate-items\spells\` holds only `regulation.bin` (no manifest, no base copy, no `.tmp`); the game's `regulation.bin` is unchanged | [ ] |
| EX3 | Same command again | built again (20-30 s), the same `sha256` and `content` as EX2 | [ ] |
| EX4 | Use a copy of the design with an `extension.json` whose 64 slots are all `null` and `--spec` it | `nothing to build`, exit `0` | [ ] |
| EX5 | Put `"fp_cost": -1` in a design copy; build with `--spec` | exit `1`, the message names `$.innovate_items.spells.slots[reverse_curse_technique].fp_cost`; the old `regulation.bin` is unchanged (hash) | [ ] |
| EX6 | `--dry-run` | `built, gate passed`, "would write", nothing changes on disk | [ ] |
| EX7 | Add `"icon_file": "a.png"` to a design copy | refused, the message says Level 3 | [ ] |
| EX8 | Put an `extension.json` next to `eldendisk.exe`, change `shop.price`, build | the `spec:` debug line (`-v`) says `external`; the output differs from EX2 | [ ] |
| EX9 | While the game's `regulation.bin` is NOT the original (copy any other file there, or use `--source` with one) | exit `1`, "not a regulation.bin this version knows", hint `vault restore`; nothing written. Put the original back | [ ] |

## SW. The swap with a tool-built file (this is the open risk)

Spec for the Z4 file: `price 34590, stock 1`, Int 45 / Fai 15 / Arc 10, FP 80, Black Flame Blade cast. Where it is sold and how it behaved: handbook Part VI.

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| SW1 | Nothing secured yet. `run --vault-on` (or `python code\tools\dev_pipeline.py --vault-on`) | the log shows `building because no secured build yet`, then `building … (about 20 s)`, then `built, gate passed`, then the host lines (PREFLIGHT, vault ON, SNAPSHOTTING, backup, READY); banner row `regulation  <ext>\innovate-items\spells\regulation.bin (new build, gate passed) replaces the game's regulation.bin …`; the game starts | [x] 2026-10-09 |
| SW2 | Load a character, buy and cast the incantation | **the same behaviour as the Z4 file tested before**: sold at the merchant line, requirements 45/15/10, FP 80, Black Flame Blade cast, heals over time, flame visuals; the cast flinches but is not cancelled | [x] 2026-10-09 |
| SW3 | Quit the game | `✓ vault save restored, byte-identical`, `✓ … regulation.bin restored, byte-identical`; `Get-FileHash Game\regulation.bin` equals your copy | [x] 2026-10-09 |
| SW4 | Kill the host while the game runs (as RH1 of 1.6.4); quit the game; `vault restore` | the original `regulation.bin` is back, hash equal to your copy | [ ] |
| SW5 | After SW4, before `vault restore`: `run --vault-on` | no build; the host refuses to start and says to run `vault restore` | [ ] |
| SW6 | Run again after a clean SW3 (still not secured) | builds again (the same hashes as EX2), swaps, restores; a hint after the session says to run `--secure` | [ ] |
| SW7 | Put any file at `<vault>\regulation\regulation.bin`; `run` | one warning `… is no longer read (since 1.7.0) …`; the file is not used. `vault status` says the same | [ ] |
| SW8 | `run --vault-on --regulation <the Z4 subject .bin from docs\experiments>` | that file is swapped (banner row); same result as SW2 | [ ] |
| SW9 | `run --vault-off` | an info line says the extension is not run; no build; the game's file is not replaced (check the hash while it runs) | [ ] |
| SW10 | Optional: with the item cast, `read --live-buffs` | a short (about 2.0 s) buff entry for the poise effect (id `102006`) while casting: evidence for the poise part | [ ] |

## SC. Secured (design → built → secured)

Do these after SW2 passed (the item works in the game).

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| SC1 | Game closed. `extension innovate-items spells --secure` | `✓ … secured`; `<ext>\innovate-items\spells\` holds `regulation.bin`, `regulation.secured.bin` (same hash) and `spells.commit.json`; no `.tmp` | [ ] |
| SC2 | `extension --list` | `secured  <time>`, `design vs secured  same: run swaps the secured file, no build` | [ ] |
| SC3 | `run --vault-on` | `unchanged since it was secured: using …regulation.secured.bin (no build)`; starts in seconds, not 20; banner `(secured copy, not rebuilt)`; no `--secure` hint afterwards; the item behaves as in SW2; restore byte-identical | [ ] |
| SC4 | Change only `name` in the design; `run` | still the secured copy, no build | [ ] |
| SC5 | Change `shop.price` to 40000; `run` | `building because the design changed since it was secured (1 field)` and the line `reverse_curse_technique.shop.price  34590 -> 40000`; builds; the merchant sells at 40000; the hint to `--secure` appears after the session | [ ] |
| SC6 | Put the price back to 34590; `run` | the old secured file is used again (the secure of SC5 was not done) | [ ] |
| SC7 | Edit one byte of a copy of `regulation.secured.bin` and put it back in place; `run` | `building because regulation.secured.bin is not the file that was secured (its hash differs)`; builds | [ ] |
| SC8 | Delete `spells.commit.json`; `run` | `no secured build yet`; builds | [ ] |
| SC9 | With the game's `regulation.bin` modified (as after SW4, before `vault restore`) | even with a secured file: exit 1, "not a regulation.bin this version knows" (the game's file is checked on every path) | [ ] |
| SC10 | Change `fp_cost` in the design after a build (do not rebuild); `extension innovate-items spells --secure` | refused: gate R1, "build again first"; nothing secured | [ ] |

A failed gate on a real build cannot be provoked from the design (the recipe always writes a valid file); the unit and golden tests cover it.

## PW. The params workbench (`read --param`, `write --set params.<Table>...`, `--param-check`; done 2026-10-09)

Game offline, started by `run` (vault ON), a character loaded. Details: [phase1-params-workbench.md](phase1-params-workbench.md).

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| PW1 | `read --probe-params` | the six tables found, each with a chain for `offsets.json` | ✓ |
| PW2 | `read --param Magic.6230 Bullet.10621001 SpEffect.1621000.change*` (tree), then `--flat` | rows by field name; `--flat` gives `params.<Table>.<id>.<field>  value` | ✓ |
| PW3 | `write --set params.Magic.6230.mp=10`; `read --param Magic.6230.mp --flat`; `write --reset params.Magic.6230.mp`; `read` again (one game process, no restart) | 10, then 21 (the game's own value) | ✓ |
| PW4 | `write --set params.Magic.6230.mp=0`; cast Scouring Black Flame and another spell | the Black Flame costs no FP, the other spell its normal FP | ✓ |
| PW5 | After PW4: Quit Game, Title Screen, Continue, Enter World; cast again | still free: the written value survives a character load (a restart of the game process clears it) | ✓ |
| PW6 | `write --set params.Bullet.10621000.life=0.2`; cast Black Flame; then `life=10` | 0.2: the fireball vanishes before the target; 10: it arrives as usual; `write --reset all` puts 1.5 back | ✓ |
| PW7 | `write --set params.Bullet.10625002.life=12` (and `-1`); cast Black Flame Ritual; `write --reset ...` | the flame around the caster lasts much longer (-1: never ends, even after resting at a grace); the reset changes only the next cast | ✓ |
| PW8 | `write --set params.effects.1626001.changeHpRate=-10` with `effectEndurance=-1` on the burn; hit an enemy | the target is healed instead of burnt and cannot be killed | ✓ |
| PW9 | `read --param-check` (the build is in the game folder) with no `write` made, or after `write --reset all` | every row of the six tables equal (Goods 2330, Magic 318, SpEffect 11356, Bullet 15475, AtkParam_Pc 11017, ShopLineup 1297); exit 0 | ✓ |
| PW10 | `write --set params.Magic.6230.mp=5`, then `read --param-check` | exit 1, one difference named: `Magic.6230  mp: file 21, game 5` | [ ] |
| PW11 | `write --set params.Magic.6230.refId1=999` | accepted with a note that the field looks like the id of another row; do not cast it | [ ] |

## CL. `kind: clone` (Phase 2.1; CL1-CL3 passed in the game; CL4 and CL5 open)

Put the spell in slot 2 of `extension.json` (slot 1 stays the tested spell; slot 2 sells on shop line 100509). `extension innovate-items spells --add all --dry-run` must pass the gate before `run`.

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| CL1 | Slot 2: `"black_flame_copy": {"kind": "clone", "from": 6210, "fp_cost": 5, "requires": {"intelligence": 0, "faith": 0}, "shop": {"price": 1000, "stock": -1}}`; `run`; buy it; memorize; cast | a second incantation in the merchant's list (named `?GoodsName?` like slot 1); it casts Black Flame (fireball and burn) and costs 5 FP; the real Black Flame is unchanged. 2026-10-09: the build (13 blocks, gate passed, second decoder agrees) loaded and the world opened; Passed in the game 2026-10-09: the new entry is in the merchant's list (price 1000, `?GoodsName?`, FP cost 5, slots used 1, requirements Int 0 / Fai 0 / Arc 0), it can be bought and memorized, and the cast is the same as the normal Black Flame | ✓ |
| CL2 | After CL1, `read --param-check` (before any `write`) | every row equal; Goods and Magic show 2 new rows each (2331 / 319 rows with slots 1 and 2; passed 2026-10-09: Goods 2331, Magic 319, SpEffect 11356, Bullet 15475, AtkParam_Pc 11017, ShopLineup 1298, all equal) | ✓ |
| CL3 | Add `"set": {"Magic.6210.slotLength": 1}` to the clone and `run` | the memory slots the copy takes change from the original's number to 1 (menu); the original is unchanged. Passed in the game 2026-10-10: `set` of `Magic.6210.slotLength` reached the copy | ✓ |
| CL4 | Exploratory: slot 3 `{"kind": "clone", "from": 4000, "fp_cost": 3, "shop": {"price": 1000}}` (Glintstone Pebble, a sorcery) | does the incantation merchant list a sorcery, and can it be memorized and cast? Either answer is a finding; write it in the roadmap | [ ] |
| CL5 | `"type": "sorcery"` on the Black Flame clone, then `--add all --dry-run` | error: `` `from` 6210 is an incantation: a clone cannot change `type` ``, nothing is built | [ ] |

## E. `kind: enchant` and `buff` with `from` (Phase 2.2; E1 passed in the game 2026-10-10; E2-E4 open)

Slot 3 (slot 1 the tested spell, slot 2 the Black Flame clone). `extension innovate-items spells --add all --dry-run` must pass the gate before `run`.

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| E1 | Slot 3: `"black_flame_blade_copy": {"kind": "enchant", "from": 6250, "fp_cost": 5, "shop": {"price": 1000, "stock": -1}, "set": {"SpEffect.1626000.effectEndurance": 600}}`; `run`; buy, memorize, cast with a weapon | the weapon burns with the Black Flame Blade effect for about 10 minutes (the original 7 s); the real Black Flame Blade still lasts 7 s. Passed in the game 2026-10-10: the copy is in the merchant's list (5 FP, Fai 17, slots used 1), can be bought, memorized and cast | ✓ |
| E2 | Add slot 4 `{"kind": "enchant", "from": 6740, "fp_cost": 5, "shop": {"price": 1000, "stock": -1}}` and slot 5 `{"kind": "buff", "from": 6050, "fp_cost": 5, "shop": {...}}`; `run` | the shield enchant copy and the Flame, Grant Me Strength copy are bought, memorized and cast like the originals | [ ] |
| E3 | `read --param-check` after E1 | every row equal; SpEffect shows the new rows (2 for the blade copy) | [ ] |
| E4 | `"kind": "enchant", "from": 6050`, then `--add all --dry-run` | error: `from` 6050 is not a weapon or shield enchant, nothing built | [ ] |

## P. `kind: projectile` (Phase 2.3; P1 and P2 passed in the game 2026-10-10; P3-P5 open)

Slot 4 (slots 1-3: the tested spell, the Black Flame clone, the Black Flame Blade copy). `extension innovate-items spells --add all --dry-run` must pass the gate before `run`.

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| P1 | Slot 4: `"black_flame_long_burn": {"kind": "projectile", "from": 6210, "fp_cost": 5, "shop": {"price": 1000, "stock": -1}, "set": {"SpEffect.1621000.effectEndurance": 30}}`; `run`; buy, memorize, cast at an enemy | the fireball flies and hits like the normal Black Flame, and the enemy burns for about 30 s (the normal Black Flame: about 2 s); the normal Black Flame is unchanged. This is the first test of Bullet rows that the game really calls. Passed in the game 2026-10-10: the build (20 blocks, gate passed) loaded, the copy is in the merchant's list (FP 5, Fai 20), can be bought and memorized, and the cast is Black Flame with a burn of about 30 s; the normal Black Flame is unchanged | ✓ |
| P2 | After P1, `read --param-check` (before Phase 2.4; with the Atk copies AtkParam_Pc shows 2 more rows, see A2) | every row equal; Bullet shows 4 new rows, SpEffect 1 more than before. Passed 2026-10-10: Goods 2333, Magic 321, SpEffect 11359, Bullet 15479 (+4), AtkParam_Pc 11017, ShopLineup 1300, all equal | ✓ |
| P3 | Change P1's set to `{"Bullet.10621000.life": 0.3}` | the first fireball (10621000) vanishes soon after leaving the hand; a different, visible change of a Bullet field | [ ] |
| P4 | Change P1's set to `{"SpEffect.1621000.changeHpRate": -0.05}` and hit a damaged enemy | the burn heals instead of damaging (check the enemy's health bar); the direct hit damage is still dealt | [ ] |
| P5 | `"kind": "projectile", "from": 6250` (an enchant) then `--add all --dry-run` | error: `from` 6250 calls SpEffect and no Bullet row, nothing built | [ ] |

## A. `kind: attack` and the attack rows of a projectile (Phase 2.4; coded and tested, not run in the game yet)

Needs the exe or `python -m eldendisk` rebuilt from the new code. Since 2.4, **slot 4 (P1's Black Flame projectile) also copies its two AtkParam_Pc rows**, so the file of the design re-encodes 26 blocks (the gate's limit since T9): `extension innovate-items spells --add all --dry-run` must say `gate passed (26 blocks re-encoded)`. Slot 5 below is one more spell, so the limit may be reached (checked on the build here: the design with slot 5 as in A1 and as in A4 passes the gate with 26 blocks); if the gate stops it (R2/R7 say the numbers), tell me the numbers.

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| A0 | Repeat P1 with the new code (slot 4 unchanged), `run`, cast the copy of Black Flame | works like P1: the fireball flies and hits like the original, burns for 30 s | [ ] |
| A1 | Slot 5 (the `"<id-5>": null` line of `extension.json` becomes this entry): `"strike_copy": {"kind": "attack", "from": 4440, "fp_cost": 4, "shop": {"price": 1000, "stock": -1}}` (4440 is a sorcery that makes a direct attack with six AtkParam_Pc rows); `--add all --dry-run`, then `run`; buy, memorize, cast | the gate passes; the copy casts and hurts like the original 4440 (same hits, same damage) | [ ] |
| A2 | After A1, `read --param-check` | every row equal; AtkParam_Pc shows 6 + 2 = 8 new rows (slot 4: 2, slot 5: 6), Goods and Magic one more each | [ ] |
| A3 | `read --param AtkParam_Pc.710000032.atkMag` (the first copy of slot 5; the original `AtkParam_Pc.44400.atkMag` is 180) | the copy reads 180, the original 180 | [ ] |
| A4 | Add to slot 5: `"set": {"AtkParam_Pc.44400.atkMag": 1800, "AtkParam_Pc.44401.atkMag": 1800, "AtkParam_Pc.44405.atkMag": 1800, "AtkParam_Pc.44406.atkMag": 1800, "AtkParam_Pc.44407.atkMag": 1840, "AtkParam_Pc.44408.atkMag": 1840}`; `run`; cast the copy and the original on the same enemy | the copy hits about ten times as hard; the original 4440 is unchanged (`read --param AtkParam_Pc.44400.atkMag` still 180) | [ ] |
| A5 | `"kind": "attack", "from": 6210` (Black Flame throws a Bullet) then `--add all --dry-run` | error: kind attack needs a spell that makes a direct attack and throws nothing; nothing built | [ ] |
| A6 | `"kind": "projectile", "from": 4440` then `--add all --dry-run` | error: `from` 4440 calls AtkParam_Pc and no Bullet row ... a direct attack is kind attack | [ ] |

If A1 stops at the title screen with "Failed to save game", say so with the screenshot: that is the layout of the grown table (T9 passed with the same layout, so it would be something the recipe does differently).

## T7. The envelope test (Phase 2.3; beyond the gate on purpose; passed in the game 2026-10-10)

Does the game load a file with a **fifth table that grows** (Bullet, 4.5 MB) and about **20 re-encoded blocks** (the gate allows 13)? Nothing in the file uses the new rows: four unreferenced copies of the Black Flame bullets.

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| T7a | In the `code` folder: `python tools\envelope_test.py --source "<game folder>\regulation.bin" --out regulation.envelope-test.bin` (the source must be the game's own, untouched file; the tool refuses any other) | `written ...`, `re-encoded blocks 20`, body growth about 93,000, frame growth about 171,000, and the only warning is R2 (more than 13 blocks). Passed 2026-10-10: written, 20 blocks, body +96,176, frame +174,944, only R2 | ✓ |
| T7b | `run --regulation regulation.envelope-test.bin` (vault ON): reach the title screen, load a character, walk around, cast a spell, quit | the game loads like normal (no crash, no stuck loading, no black screen); on quit the vault restores the original. Passed 2026-10-10: Continue, the world loaded, played, exit to desktop | ✓ |
| T7c | After T7b, `read --param-check` is not meaningful (the file is the experiment); check instead that `vault status` shows the original back in place | original restored, hash equal. Passed 2026-10-10: `vault status` shows no unresolved session, the original regulation.bin restored byte-identical | ✓ |

If the game stops at the title screen or crashes, tell me when (the loading screen, the title, after loading the character): the answer decides whether more blocks or a fifth table is the problem.

## T8. The envelope test with a sixth table (Phase 2.4; did NOT pass in the game 2026-10-10)

Does the game load a file with **AtkParam_Pc grown** (4 unreferenced copies of Black Flame attack rows, ids 710002000-710002003) next to 4 unreferenced Bullet copies (500002000-500002003)? The tool says: 25 re-encoded blocks, body growth 6,266,672, frame growth 6,387,296 (the gate: 20 blocks, 219,000 and 235,000), because AtkParam_Npc (6.17 MB), the entry in front of AtkParam_Pc, has to move.

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| T8a | `python tools\envelope_test.py --source "<game folder>\regulation.bin" --out regulation.envelope-test.bin` | `written ...`; warnings R2 and R7 only. Passed 2026-10-10: written, 25 blocks | ✓ |
| T8b | `python -m eldendisk run --regulation regulation.envelope-test.bin --vault-on -v`: reach the title screen, Continue | the world loads. 2026-10-10: the game stopped at the title screen with "Failed to save game. Save data is corrupted."; the game did not touch the save | ✗ |
| T8c | Control: `run --vault-on -v` with the normal build right after | the game loads like normal. 2026-10-10: played normally, so the failure is the T8 file, not the save or Steam | ✓ |
| T8d | `vault status` after T8b | original restored. 2026-10-10: save and regulation.bin restored byte-identical | ✓ |

Result: a 6.3 MB growth is beyond what the game accepts (the gate keeps its numbers from T7).

## T9. The envelope test with a sixth table grown at its end (Phase 2.4; passed in the game 2026-10-10)

T8 failed because AtkParam_Pc had to be grown backwards and the 6 MB table in front of it moved. T9 grows it at its END instead (the entry behind it is 28 KB): the records grow into the front of the data, the first 5 rows (one more than the 4 new rows) are copied behind the strings, nothing else moves. The same eight unreferenced rows as T8 (4 Bullet, 4 AtkParam_Pc).

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| T9a | `python tools\envelope_test.py --source "<game folder>\regulation.bin" --out regulation.envelope-test.bin` | `written ...`, re-encoded blocks 26, body growth 124,560, frame growth 242,464; warnings R2 and R7 (frame) only. Passed 2026-10-10 | ✓ |
| T9b | `python -m eldendisk run --regulation regulation.envelope-test.bin --vault-on -v`: Continue, walk around, quit | the game loads like normal. Passed 2026-10-10: played normally | ✓ |
| T9c | `vault status` / the log after T9b | original restored. Passed 2026-10-10: save and regulation.bin restored byte-identical | ✓ |

Result: the game accepts a table whose rows lie behind its strings, 26 re-encoded blocks and a frame that grew by 242,464 bytes. The gate went to 26 blocks and 243,000 frame bytes.

## T. Table move (several items, not built yet)

Written when T1 exists (spec 1.7.0 section 10b): the game must reach the title screen and load a character with the Goods table moved to the end of `regulation.bin`; no item is added.

## Automated tests (no game)

`python -m pytest code` -> see the last run in the changes file (Linux, golden tests skipped without the original). With the pristine file: `ELDENDISK_REGULATION_ORIG=<path> python -m pytest code/tests/test_ext_golden.py` (about 2 min) checks the Z4 hash `1aa16ee0…db5277b`.

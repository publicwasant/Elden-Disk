# Manual test plan 1.7.0 (real game, Windows): extensions and `innovate-spells`

Only what is new in 1.7.0. The swap itself is [manual-test-plan-1.6.4.md](manual-test-plan-1.6.4.md) (RG/RH checks still apply, with the file now coming from the extension). Tick `[ ]` as you go and write what you saw next to anything unexpected.

> [!IMPORTANT]
> **Before anything:** copy the save folder (`%APPDATA%\EldenRing\<SteamID64>`) **and** the game's own `regulation.bin` (`...\ELDEN RING\Game\regulation.bin`) somewhere safe; `vault status` must say no unresolved session. Offline only.

`<ext>` = `%LOCALAPPDATA%\EldenDisk\extension`. The design is `code\extension.json` in the source (the Z4 item); `build -c -em` embeds it in the exe. With the vault ON, `run` swaps `regulation.secured.bin` when the design is unchanged and secured; otherwise it builds (about 20-30 s) and the gate must pass before the host starts.

## EX. The build (`extension innovate-spells`, the same build `run` does)

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| EX1 | `eldendisk.exe extension --list` (nothing built yet) | the spec path with `(embedded)`, `1 item in the design`, `secured  none yet …`, `last build  none yet`; exit `0`; nothing is created on disk | [ ] |
| EX2 | `extension innovate-spells --add all` | about 20-30 s; `✓ … built, gate passed (13 blocks re-encoded)`; rows `sha256`, `content 0ef6b851…`, path of `regulation.bin`; `<ext>\innovate-spells\` holds only `regulation.bin` (no manifest, no base copy, no `.tmp`); the game's `regulation.bin` is unchanged | [ ] |
| EX3 | Same command again | built again (20-30 s), the same `sha256` and `content` as EX2 | [ ] |
| EX4 | Use a copy of the design with an `extension.json` whose 64 slots are all `null` and `--spec` it | `nothing to build`, exit `0` | [ ] |
| EX5 | Put `"fp_cost": -1` in a design copy; build with `--spec` | exit `1`, the message names `$.innovate_spells.slots[reverse_curse_technique].fp_cost`; the old `regulation.bin` is unchanged (hash) | [ ] |
| EX6 | `--dry-run` | `built, gate passed`, "would write", nothing changes on disk | [ ] |
| EX7 | Add `"icon_file": "a.png"` to a design copy | refused, the message says Level 3 | [ ] |
| EX8 | Put an `extension.json` next to `eldendisk.exe`, change `shop.price`, build | the `spec:` debug line (`-v`) says `external`; the output differs from EX2 | [ ] |
| EX9 | While the game's `regulation.bin` is NOT the original (copy any other file there, or use `--source` with one) | exit `1`, "not a regulation.bin this version knows", hint `vault restore`; nothing written. Put the original back | [ ] |

## SW. The swap with a tool-built file (this is the open risk)

Spec for the Z4 file: `price 34590, stock 1`, Int 45 / Fai 15 / Arc 10, FP 80, Black Flame Blade cast. Where it is sold and how it behaved: handbook Part VI.

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| SW1 | Nothing secured yet. `run --vault-on` (or `python code\tools\dev_pipeline.py --vault-on`) | the log shows `building because no secured build yet`, then `building … (about 20 s)`, then `built, gate passed`, then the host lines (PREFLIGHT, vault ON, SNAPSHOTTING, backup, READY); banner row `regulation  <ext>\innovate-spells\regulation.bin (new build, gate passed) replaces the game's regulation.bin …`; the game starts | [x] 2026-10-09 |
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
| SC1 | Game closed. `extension innovate-spells --secure` | `✓ … secured`; `<ext>\innovate-spells\` holds `regulation.bin`, `regulation.secured.bin` (same hash) and `spells.commit.json`; no `.tmp` | [ ] |
| SC2 | `extension --list` | `secured  <time>`, `design vs secured  same: run swaps the secured file, no build` | [ ] |
| SC3 | `run --vault-on` | `unchanged since it was secured: using …regulation.secured.bin (no build)`; starts in seconds, not 20; banner `(secured copy, not rebuilt)`; no `--secure` hint afterwards; the item behaves as in SW2; restore byte-identical | [ ] |
| SC4 | Change only `name` in the design; `run` | still the secured copy, no build | [ ] |
| SC5 | Change `shop.price` to 40000; `run` | `building because the design changed since it was secured (1 field)` and the line `reverse_curse_technique.shop.price  34590 -> 40000`; builds; the merchant sells at 40000; the hint to `--secure` appears after the session | [ ] |
| SC6 | Put the price back to 34590; `run` | the old secured file is used again (the secure of SC5 was not done) | [ ] |
| SC7 | Edit one byte of a copy of `regulation.secured.bin` and put it back in place; `run` | `building because regulation.secured.bin is not the file that was secured (its hash differs)`; builds | [ ] |
| SC8 | Delete `spells.commit.json`; `run` | `no secured build yet`; builds | [ ] |
| SC9 | With the game's `regulation.bin` modified (as after SW4, before `vault restore`) | even with a secured file: exit 1, "not a regulation.bin this version knows" (the game's file is checked on every path) | [ ] |
| SC10 | Change `fp_cost` in the design after a build (do not rebuild); `extension innovate-spells --secure` | refused: gate R1, "build again first"; nothing secured | [ ] |

A failed gate on a real build cannot be provoked from the design (the recipe always writes a valid file); the unit and golden tests cover it.

## T. Table move (several items, not built yet)

Written when T1 exists (spec 1.7.0 section 10b): the game must reach the title screen and load a character with the Goods table moved to the end of `regulation.bin`; no item is added.

## Automated tests (no game)

`python -m pytest code` -> see the last run in the changes file (Linux, golden tests skipped without the original). With the pristine file: `ELDENDISK_REGULATION_ORIG=<path> python -m pytest code/tests/test_ext_golden.py` (about 2 min) checks the Z4 hash `1aa16ee0…db5277b`.

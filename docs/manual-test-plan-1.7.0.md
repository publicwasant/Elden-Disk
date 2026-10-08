# Manual test plan 1.7.0 (real game, Windows): extensions and `customize-items`

Only what is new in 1.7.0. The swap itself is [manual-test-plan-1.6.4.md](manual-test-plan-1.6.4.md) (RG/RH checks still apply, with the file now coming from the extension). Tick `[ ]` as you go and write what you saw next to anything unexpected.

> [!IMPORTANT]
> **Before anything:** copy the save folder (`%APPDATA%\EldenRing\<SteamID64>`) **and** the game's own `regulation.bin` (`...\ELDEN RING\Game\regulation.bin`) somewhere safe; `vault status` must say no unresolved session. Offline only.

`<ext>` = `%LOCALAPPDATA%\EldenDisk\extension`. The spec is `code\eldendisk\extension\customize_items\sources\items.json` in the source (the Z4 item); `build -c -em` embeds it in the exe. With the vault ON, `run` builds it every time (about 15-30 s) before the host starts.

## EX. The build (`extension customize-items`, the same build `run` does)

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| EX1 | `eldendisk.exe extension --list` (nothing built yet) | the spec path with `(embedded)`, `1 item in the spec`, `last output  none yet`; exit `0`; nothing is created on disk | [ ] |
| EX2 | `extension customize-items --add all` | about 15-30 s; `✓ … built and checked (11 blocks re-encoded)`; rows `sha256`, `content 1aa16ee0…`, path of `regulation.bin`; `<ext>\customize-items\` holds only `regulation.bin` (no manifest, no base copy, no `.tmp`); the game's `regulation.bin` is unchanged | [ ] |
| EX3 | Same command again | built again (15-30 s), the same `sha256` and `content` as EX2 | [ ] |
| EX4 | Use a copy of the spec with `{"format": 1, "items": []}` and `--spec` it | `nothing to build`, exit `0` | [ ] |
| EX5 | Put `"fp_cost": -1` in a spec copy; build with `--spec` | exit `1`, the message names `$.items[0].fp_cost`; the old `regulation.bin` is unchanged (hash) | [ ] |
| EX6 | `--dry-run` | `built and checked`, "would write", nothing changes on disk | [ ] |
| EX7 | Add `"icon_file": "a.png"` to a spec copy | refused, the message says Level 3 | [ ] |
| EX8 | Put an `items.json` next to `eldendisk.exe`, change `shop.price`, build | the `spec:` debug line (`-v`) says `external`; the output differs from EX2 | [ ] |
| EX9 | While the game's `regulation.bin` is NOT the original (copy any other file there, or use `--source` with one) | exit `1`, "not a regulation.bin this version knows", hint `vault restore`; nothing written. Put the original back | [ ] |

## SW. The swap with a tool-built file (this is the open risk)

Spec for the Z4 file: `price 34590, stock 1`, Int 45 / Fai 15 / Arc 10, FP 80, Black Flame Blade cast. Where it is sold and how it behaved: handbook Part VI.

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| SW1 | `run --vault-on` (or `python code\tools\dev_pipeline.py --vault-on`) | the log shows `extension customize-items: building … (about 15 s)`, then `built and checked`, then the host lines (PREFLIGHT, vault ON, SNAPSHOTTING, backup, READY); banner row `regulation  <ext>\customize-items\regulation.bin replaces the game's regulation.bin …`; the game starts | [ ] |
| SW2 | Load a character, buy and cast the incantation | **the same behaviour as the Z4 file tested before**: sold at the merchant line, requirements 45/15/10, FP 80, Black Flame Blade cast, heals over time, flame visuals; the cast flinches but is not cancelled | [ ] |
| SW3 | Quit the game | `✓ vault save restored, byte-identical`, `✓ … regulation.bin restored, byte-identical`; `Get-FileHash Game\regulation.bin` equals your copy | [ ] |
| SW4 | Kill the host while the game runs (as RH1 of 1.6.4); quit the game; `vault restore` | the original `regulation.bin` is back, hash equal to your copy | [ ] |
| SW5 | After SW4, before `vault restore`: `run --vault-on` | no build; the host refuses to start and says to run `vault restore` | [ ] |
| SW6 | Run again after a clean SW3 | builds again (the same hashes as EX2), swaps, restores | [ ] |
| SW7 | Put any file at `<vault>\regulation\regulation.bin`; `run` | one warning `… is no longer read (since 1.7.0) …`; the file is not used. `vault status` says the same | [ ] |
| SW8 | `run --vault-on --regulation <the Z4 subject .bin from docs\experiments>` | that file is swapped (banner row); same result as SW2 | [ ] |
| SW9 | `run --vault-off` | an info line says the extension is not run; no build; the game's file is not replaced (check the hash while it runs) | [ ] |
| SW10 | Optional: with the item cast, `read --live-buffs` | a short (about 2.0 s) buff entry for the poise effect (id `102006`) while casting: evidence for the poise part | [ ] |

## Automated tests (no game)

`python -m pytest code` -> 765 passed, 14 skipped on Linux. With the pristine file: `ELDENDISK_REGULATION_ORIG=<path> python -m pytest code/tests/test_ext_golden.py` (about 2 min) checks the Z4 hash `1aa16ee0…db5277b`.

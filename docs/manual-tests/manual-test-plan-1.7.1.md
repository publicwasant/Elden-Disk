# Manual test plan 1.7.1 (real game, Windows): the text and the fire colour of a spell

Only what is new in 1.7.1; everything else is [manual-test-plan-1.7.0](../experiments/extensional/innovate-items/spell/level2/docs/manual-test-plan-1.7.0.md). Tick `[ ]` as you go and write what you saw next to anything unexpected.

> [!IMPORTANT]
> **Before anything:** the save folder and the game's own `regulation.bin` copied somewhere safe; `vault status` says no unresolved session. Offline only. The design is `code\extension.json` (slot 1, `reverse_cursed_technique`, with a `text` object and a `flame_color`); the dev pipeline embeds it in the exe.

**Already seen in the logs of 2026-10-11 (three `run -v` sessions, no ticks needed for these):** both steps start by themselves, wait for a character in the world, and finish with `✓`: the three text tables written and read back about 75 s after the character appears, the two fire effects (68 places) about 7 s after. The ticks below are for what is **seen in the game**.

## TX. Text

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| TX1 | `run -v` (vault ON), load a character | `text: waiting for a character to be in the world`, then `a character is in the world`, then `text: looked for the tables: … MB read in … s`, `looked for the array …`, `text: array at …`, three `text Goods…: … bytes, now at …` lines and `text: 1 spell named in the game …`; the 2026-10-11 runs (16 MB pieces, whole-memory array look) took about 75 s after the character appears; the lighter look (seen on 2026-10-12: tables 1.6 s, array 0.3 s) ends in a few seconds, with `(near; N pieces, the slowest … ms, … s resting)` in the log; no extra window | [ ] |
| TX2 | Visit Kalé; look at the new spell in the list | the name is `goods_name` of the design, the short line `goods_info` (not `?GoodsName?`) | [ ] |
| TX3 | Buy it; Inventory → select it → controller square button | the long description is `goods_captions`; `\n` is a new line | [ ] |
| TX4 | Other items' text (e.g. the name of Flame, Grant Me Strength, a weapon) | unchanged | [ ] |
| TX5 | While the game runs, run `eldendisk write --text` by hand | exit `1`: `the text was set already in this session …` (known limit); the text stays as written | [ ] |
| TX6 | Empty `goods_info` in the design, quit the game, `run` again | the short line is gone in the game, the name stays | [ ] |
| TX7 | Quit the game; `run` again | the text is there again (it is put in at every start); the save and `regulation.bin` are restored byte-identical as before | [ ] |
| TX8 | Secured build: `extension innovate-items spells --secure`, then edit only `text`, `run` | `unchanged since it was secured: using …` (no build), and the new text shows | [ ] |
| TX9 | `run --vault-off` | no text step (the vault is off); the log has no `write` line | [ ] |
| TX10 | `run --regulation <a file>` | no text step | [ ] |
| TX11 | `write --text` with no game running | `eldenring.exe is not running`, exit `1` | [ ] |
| TX12 | `write --text` in a game started from Steam (anti-cheat) | refused, exit `3` | [ ] |
| TX13 | Load the character, then Quit to Title and load it again | the text is still there (the game does not reload its text) — note what you see | [ ] |
| TX14 | Optional: Thai in `goods_captions` | write what the game shows (boxes, blanks, or Thai) | [ ] |
| TX15 | Optional: `read --live` while the text step runs | not disturbed; the game does not stutter during the look (the log says the slowest piece; ~75 s before the lighter look); also `scan: background priority and 1 ms timer` in the log | [ ] |

## FL. Fire colour

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| FL1 | `run -v`, load a character | `flame colour: a character is in the world`, then `look 1/5: … MB read in … s (stopped in the … of the blocks, all found); found 524400, 524401`, a line for each effect and `✓ … the fire of Flame, Grant Me Strength is now (0.2, 0.65, 1.0) in 2 effects (68 places written)`; within ~10 s of the character appearing | [ ] |
| FL2 | Cast Flame, Grant Me Strength (and the new spell) | the fire while casting and the burst are the design's colour (blue for `[0.2, 0.65, 1.0]`); the burning on the body keeps its own colour | [ ] |
| FL3 | Edit `flame_color` in the design (e.g. `[1, 0.2, 0.2]`), quit the game, `run` again | the new colour in the next game; no rebuild happened (nothing about a build) | [ ] |
| FL4 | Remove `flame_color` from every spell, `run` | no fire step; the fire is the game's own orange | [ ] |
| FL5 | Two spells with different `flame_color` | a warning says which slot's colour is used | [ ] |
| FL6 | `flame_color` with a number above 2, or two numbers | the design is refused with the path (`….flame_color: must be three numbers …`) | [ ] |
| FL7 | `write --flame-color` by hand after the step, in the same game | `✓ …` again (the copies are found painted: `already`), exit `0` | [ ] |
| FL8 | `write --flame-color` with no game running / with anti-cheat | `eldenring.exe is not running` exit `1` / refused exit `3` | [ ] |
| FL9 | Quit the game; `run` again | the fire is coloured again (it is done at every start) | [ ] |

## IC. Icon (an existing icon reused)

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| IC1 | `run` with `"Goods.6421.iconId": 6806` in the spell's `set`; visit Kalé | the spell's line in the shop list shows the icon of Gravitational Missile (not Heal's) | [ ] |
| IC2 | Buy it; open the Inventory and the memory (spells) menu | the same icon in the inventory list and in the memory-slot list; if the memory screen still shows Heal's, note it (then `Magic.6421.iconId` is the one to set) | [ ] |
| IC3 | A game without the DLC (or an `iconId` the game has no picture for) | the icon is blank or missing, nothing else breaks — note what you see | [ ] |

## Console (seen in a real terminal, Windows Terminal or the IDE run window)

| # | Do | Expect | Seen |
|---|---|---|---|
| UX1 | Change one number in the design, `eldendisk run` (no `-v`) in Windows Terminal | the reason for the build, the changes as a `├─ └─` tree, a spinning line with the seconds while it builds, then one `✓` line with the time, then a card per spell | [ ] |
| UX2 | The same in the IDE run window (`FORCE_COLOR`) and with `> file` (a pipe) | no spinner: a start line and an end line; nothing garbled | [ ] |
| UX3 | `run` (no `-v`) to the point where a character is in the world | the lines `write  text: waiting …`, `a character is in the world` and the `✓` lines of the text and the flame step appear in the same console | [ ] |
| UX4 | The log file after UX1 | plain text only (no escape codes); the build lines are there with their times | [ ] |

## Automated tests (no game)

`python -m pytest code` (golden tests need `ELDENDISK_REGULATION_ORIG`). The tests are `test_write_text.py`, `test_write_flame.py` and the additions listed in spec 1.7.1 section 11.

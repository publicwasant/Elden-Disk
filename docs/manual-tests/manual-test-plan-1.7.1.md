# Manual test plan 1.7.1 (real game, Windows): the text of a spell

Only what is new in 1.7.1; everything else is [manual-test-plan-1.7.0](../experiments/extensional/innovate-items/spell/level2/docs/manual-test-plan-1.7.0.md). Tick `[ ]` as you go and write what you saw next to anything unexpected.

> [!IMPORTANT]
> **Before anything:** the save folder and the game's own `regulation.bin` copied somewhere safe; `vault status` says no unresolved session. Offline only. The design is `code\extension.json` (slot 1, `reverse_curse_technique`, with a `text` object); the dev pipeline embeds it in the exe.

## TX. Text (the author's checks of 2026-10-11 were made by hand with `tools/patch_text.py`; these test the tool)

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| TX1 | `run` (vault ON), wait for the title screen, load a character | after the host lines, a line `text: 1 spell named in the game (name, short line, description); it lasts until the game closes` appears in the same console, within about 5-10 s of the game starting to load; no extra window | [ ] |
| TX2 | Visit Kalé; look at the new spell in the list | the name is `goods_name` of the design, the short line `goods_info` (not `?GoodsName?`) | [ ] |
| TX3 | Buy it; Inventory → select it → controller square button | the long description is `goods_captions`; `\n` is a new line | [ ] |
| TX4 | Other items' text (e.g. the name of Flame, Grant Me Strength, a weapon) | unchanged | [ ] |
| TX5 | While the game runs, edit `goods_name` in the design (the file `run` used: `--spec`, or the one next to the exe), then `eldendisk write --text` | `✓ write  text: 1 spell named …`; open the shop again: the new name; no rebuild happened (nothing about a build) | [ ] |
| TX6 | Run `write --text` again without changes | `✓ …` again, exit `0` (nothing changes; no growth in the game's memory is visible) | [ ] |
| TX7 | Empty `goods_info` in the design; `write --text` | the short line is gone in the game, the name stays | [ ] |
| TX8 | Quit the game; `run` again | the text is there again (it is put in at every start); the save and `regulation.bin` are restored byte-identical as before | [ ] |
| TX9 | Secured build: `extension innovate-items spells --secure`, then edit only `text`, `run` | `unchanged since it was secured: using …` (no build), and the new text shows | [ ] |
| TX10 | `run --vault-off` | no text step (the vault is off); the log has no `write` line | [ ] |
| TX11 | `run --regulation <a file>` | no text step | [ ] |
| TX12 | `write --text` with no game running | `eldenring.exe is not running`, exit `1` | [ ] |
| TX13 | `write --text` in a game started from Steam (anti-cheat) | refused, exit `3` | [ ] |
| TX14 | While `run` is starting the game (logo screen), type `write --text --wait` in a second terminal | it waits, then reports the text once the game has loaded it (or the clear message after 300 s) | [ ] |
| TX15 | If the text vanishes after loading a character or changing a setting | note when; `write --text` brings it back (open question: does the game reload its text?) | [ ] |
| TX16 | Optional: Thai in `goods_captions` | write what the game shows (boxes, blanks, or Thai) | [ ] |
| TX17 | Optional: `read --live` and `write --set level=…` while the text step runs | not disturbed | [ ] |

## Automated tests (no game)

`python -m pytest code` (golden tests need `ELDENDISK_REGULATION_ORIG`). The text tests are `test_write_text.py` and the additions listed in spec 1.7.1 section 8.

# Manual test plan 1.6.4 (real game, Windows): the `regulation.bin` swap

Only what is new in 1.6.4. The rest is [manual-test-plan-1.6.3.md](manual-test-plan-1.6.3.md) (P1 now expects `eldendisk 1.6.4`). Tick `[ ]` as you go and write what you saw next to anything unexpected.

> [!IMPORTANT]
> **Before anything:** copy the save folder (`%APPDATA%\EldenRing\<SteamID64>`) **and** the game's own `regulation.bin` (`...\ELDEN RING\Game\regulation.bin`) somewhere safe. Offline only. Do not run the build pipeline while a session record exists (`vault status` first).

Legend: `T0` = terminal running `eldendisk.exe run`, `T1` = a second terminal. The "other world" is a `regulation.bin` you saved with an external editor (Smithbox or similar) **outside the game folder**, with one visible change (a spell, a row, a value you can see in the game).

## RG. The swap

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| RG0 | `vault status` with nothing in `<vault>\regulation\` | a line `regulation  no file: put yours at <vault>\regulation\regulation.bin to swap it in …` (with the full path); the folder is not created for you; exit `0` | [ ] |
| RG1 | Put your file at `<vault>\regulation\regulation.bin`. `vault status` | `regulation  <path> (x MiB, sha256 …): the next run with the vault ON swaps it in` | [ ] |
| RG2 | T0: `run`. Read the banner, then wait for the game | a `regulation` row in the banner; `✓ vault game's regulation.bin backed up …`; `✓ vault regulation.bin: your file replaces the game's for this session`; the game starts offline | [ ] |
| RG3 | Load a character; look for the change you made | **the game shows the other world** (the new row / value). If the game does not start or crashes: note it, quit, go to RG5 | [ ] |
| RG4 | While the game runs, T1: `vault status` and `write --set level=120` | status: session `RUNNING`; write works as before (a swapped file does not change the gate) | [ ] |
| RG5 | Quit the game | `✓ vault save restored, byte-identical …` then `✓ vault regulation.bin restored, byte-identical to the game's own file`; exit `0`. Compare `Game\regulation.bin` with your copy (`Get-FileHash`): **identical**. `Game\` has no `regulation.bin.eldendisk-tmp` | [ ] |
| RG6 | `vault list` and look in the newest snapshot | `save\`, `bin\regulation.bin` (equals your copy), `manifest.json` with a `regulation` key; verified | [ ] |
| RG7 | Remove your file from `<vault>\regulation\`, `run`, quit | no `regulation` line anywhere; nothing in `bin\`; the game ran with its own file | [ ] |
| RG8 | File back in place: `run --vault-off` | warning `… is ignored: with the vault OFF …`; the game's `regulation.bin` is **not** replaced (check the hash while the game runs) | [ ] |
| RG9 | A 0-byte `regulation.bin` in the vault, then `run` | refused, exit `1`: "… is empty"; nothing changed | [ ] |

## RH. Recovery

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| RH1 | T0: `run` with the file in place, load a character, then kill the host (Task Manager) | the game keeps running; `Game\regulation.bin` is the other world | [ ] |
| RH2 | Quit the game, `vault status` | `RESTORE_PENDING` or `RUNNING`, a line that the restore puts the original back; exit `4` | [ ] |
| RH3 | `vault restore` | save restored, `regulation.bin restored, byte-identical`; the hash of `Game\regulation.bin` equals your copy; `vault status` trusted | [ ] |
| RH4 | Repeat RH1 and run `vault keep --yes` | the game's own `regulation.bin` is put back first, the current save is kept (`-kept` snapshot) | [ ] |
| RH5 | Repeat RH1, quit the game, then **damage** `<snapshot>\bin\regulation.bin` (change a byte) and `vault restore` | the save is restored; the file is **not** copied back; exit `4`; `vault verify <snapshot>` names `bin/regulation.bin`. Then copy your own copy of the original `regulation.bin` into `Game\` and run `vault restore` again: exit `0`, record removed (the hash in the record is what counts) | [ ] |
| RH6 | Start the game from Steam **after** a pending restore (do not do this online) | the game's file is still the other world: this is the risk the exit-4 message is for. Run `vault restore` first, always | [ ] |

## Automated tests (no game)

`python -m pytest code` -> 657 passed, 1 skipped on Linux; `tests/test_regulation.py` is the swap.

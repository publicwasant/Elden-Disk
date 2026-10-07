# Manual test plan 1.6.2 (real game, Windows)

For the checks the unit tests cannot make: the real game, a real terminal, Steam. Tick `[ ]` as you go and write what you saw next to anything that is not as expected. Exit codes: `echo $LASTEXITCODE` (PowerShell).

> [!IMPORTANT]
> **Before anything:** copy the save folder (`%APPDATA%\EldenRing\<SteamID64>`) somewhere safe. Do not run the build pipeline while a session record exists (`vault status` first).

Legend: `T0` = terminal running `eldendisk.exe run` (leave it open), `T1` = a second terminal, `T2` = a third. "Loaded" = a character is in the world, not the title screen.

Already seen on the real game (spec section 9): `run` restore, hard-kill recovery, `write` by name, `read --live`, the two monitors. They are listed again so a release run is complete; tick them quickly.

---

## 0. Preparation

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| P1 | `eldendisk.exe --version` | `eldendisk 1.6.2` | [ ] |
| P2 | `eldendisk.exe -h`, then `read -h`, `write -h`, `vault -h`, `run -h` | each page lists the 1.6.2 flags; `read` shows `--query --export --live --live-effects --live-animations --mapped --unmapped --json --timeout` | [ ] |
| P3 | `eldendisk.exe hash` | the SHA-256 of `eldenring.exe` only on stdout | [ ] |
| P4 | `eldendisk.exe vault status` (no session) | no record, trusted, exit `0` | [ ] |
| P5 | Old names are gone: `sandbox status`, `effects`, `animations`, `read effects`, `read export`, `read --once`, `write set vigor=9`, `run --hz 30` | each is a usage error (exit `2`), nothing runs | [ ] |

---

## 1. `run` (host)

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| R1 | T0: `run`. Load a character, play a minute, quit the game | banner (vault, save, game); `✓ vault snapshot … verified`; `· game launching eldenring.exe offline`; `✓ game running, pid N; write is now allowed`; on exit `✓ vault save restored, byte-identical to the snapshot`; exit `0`; the save equals the one before | [ ] |
| R2 | Same, with several Steam accounts: `run --save-dir "<folder>"`, then `run` again without it | the folder is remembered (Registry) | [ ] |
| R3 | T0: press Ctrl+C **once** while the game runs | warning "the game keeps running; the save is restored when it exits (press again to postpone the restore)"; the game keeps running; restore happens when you quit | [ ] |
| R4 | T0: Ctrl+C **twice** | `RESTORE_PENDING`, exit `4`, the game is **not** killed. Then in T1: `run` is refused (exit `4`, names `vault restore`); `write --set level=100` exits `5`; `vault status` exits `4` | [ ] |
| R5 | Continue R4: quit the game, `vault restore` | the modified save is archived in the vault, the snapshot is restored, `byte-identical`, record removed; `vault status` trusted | [ ] |
| R6 | Close the T0 console window (X) during a session | the game keeps running; the record is `RESTORE_PENDING`; after quitting the game `vault restore` works | [ ] |
| R7 | Kill the host (red button in the IDE / Task Manager) with the game open | the game keeps running (detached); `write` exits `5`; `vault restore` after quitting the game | [ ] |
| R8 | Start the game from Steam first, then `run` | refused: "eldenring.exe is already running; close it first" | [ ] |
| R9 | `run` while Steam is running | a Steam Cloud reminder is printed | [ ] |
| R10 | `run --keep 1` twice (two finished sessions) | only the newest snapshot remains (`vault list`) | [ ] |
| R11 | `run -v` | the logcat lines instead of the concise view; same lines in `<vault>/eldendisk.log` | [ ] |
| R12 | `run --vault-off`; the banner | `mode  vault OFF (no backup, no restore)`; no snapshot is created (`vault list` unchanged); log has `D vault : status OFF`; the game launches offline as usual (`run` without the flag logs `status ON`) | [ ] |
| R13 | Farming with OFF: T0 `run --vault-off`, T1 `read --live --query runes`; kill some enemies, quit the game | the rune count rises in T1; after the game exits **nothing is restored** (`ER0000.sl2` keeps the progress after a grace save); `vault status` shows no record; exit `0` | [ ] |
| R14 | OFF: T2 `write --set level=150` | refused, exit `5`, message mentions `--vault-off` / no valid session; nothing written | [ ] |
| R15 | A record is owed (R4/R7), then `run --vault-off` | still refused, exit `4`, names `vault restore` | [ ] |
| R16 | OFF: Ctrl+C in T0 while the game runs | the host stops waiting, exit `130`; the game keeps running; no record is left; `read` still works | [ ] |
| R17 | `run --vault-on --vault-off` | usage error (exit `2`): mutually exclusive | [ ] |

---

## 2. `vault`

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| V1 | `vault status` / `vault list` / `vault list --fast` / `vault verify <snapshot>` | sizes, verification results; exit `0` | [ ] |
| V2 | Default location: no `--vault` anywhere | `%LOCALAPPDATA%\EldenDisk\vault`; not inside `build\` | [ ] |
| V3 | `run --vault D:\x\vault` once, then `vault status` without the flag | the remembered vault is used | [ ] |
| V4 | `vault restore` while the game runs | refused | [ ] |
| V5 | **keep:** T0 `run`, `write --set level=150`, rest at a grace (game saves), stop T0 (Ctrl+C twice), quit the game, `vault keep`, then `vault keep --yes` | first call only explains; second makes a `<ts>-kept` snapshot, keeps the pre-session one, removes the record; the live save is unchanged and still has level 150; `vault status` trusted | [ ] |
| V6 | `vault keep --yes` while the game runs / while the host runs | refused | [ ] |
| V7 | `vault prune` | reclaims space; never while a record exists | [ ] |

---

## 3. `read`, one shot (T0 `run` + a loaded character, or any game without EAC)

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| Q1 | `read` | a tree: `systems` (profile, features, status, session) and `character` (level, vitals, runes, attributes); numbers with thousands separators; with `character.effects` and `character.animations` as in `disk-state.json`; exit `0`, returns at once | [ ] |
| Q2 | `read --query level` / `runes` / `hp` / `hp.max` / `hit_point.maximum` / `fp` / `stamina` / `vigor` / `attrs.*` | the value or group; `runes` and `hp` show the whole group | [ ] |
| Q3 | `read --query vitals.*.current` / `character.*` | the matching values (`character.*` includes the effects and animations) | [ ] |
| Q4 | `read --query vigr` | exit `1`, "unknown name 'vigr'; did you mean … vigor" | [ ] |
| Q5 | `read --query runes --json \| ConvertFrom-Json` | valid JSON, only that value | [ ] |
| Q6 | `read --query effects`, `read --query character.effects.*`, `read --query animations` | just the lists (also with `--live`) | [ ] |
| Q7 | game not running: `read --timeout 3` | "waiting for eldenring.exe …" then exit `1` after about 3 s | [ ] |
| Q8 | game at the title screen: `read --timeout 3` | "no loaded world after 3 s …; load a character first", exit `1` | [ ] |
| Q9 | game started from Steam (EAC): `read` | exit `3` with the hint to use `eldendisk run` (not "module not found") | [ ] |
| Q10 | `read --hz 500`, `--timeout 0`, `--json --live`, `--export --query hp`, `--live-effects --live` | each a usage error, exit `2` | [ ] |
| Q11 | `read --query character.runes.* character.effects.*`, then the same with `--live` | one tree: `character` once, `runes` with its values, `effects` with each id; `--live` redraws and highlights in place; a typo in any name stops with exit `1` | [ ] |
| Q12 | `read --flat`, `read --query character.runes.* attrs.vigor --flat`, then the same with `--live` | one `full.path  value` row per value, aligned, no headings; `--live` redraws in place and highlights changes; `--flat --export` / `--json` / `--live-effects` are usage errors (exit `2`) | [ ] |

---

## 4. `read --export`

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| X1 | `read --export` | `✓ export disk-state.json (N KB) written to <dir>`, exit `0`; the file has `systems` and `character` with effects and animations; valid against `reader/disk.schema.json` | [ ] |
| X2 | `read --export --out D:\tmp\x` | the file lands there | [ ] |
| X3 | `read --export --out "<game folder>"` | refused (never into the game folder) | [ ] |
| X4 | Inside a `run` session vs. without one | `systems.session.sandbox` is `true` inside, `false` outside | [ ] |
| X5 | `read --live --export` in T1; take damage, gain runes | the file changes when values change, at most every 0.5 s; the console says only the state changes | [ ] |
| X6 | Same; alt-tab away from the game | state `IDLE` is written; back in the game it returns to `CONNECTED`. With `--no-idle` it keeps reading | [ ] |
| X7 | Same; `--export-interval 2 --timer-interval 0` | writes at most every 2 s; buff countdowns alone never trigger a write | [ ] |
| X8 | Same; Ctrl+C | one last write, exit `130`, the game keeps running | [ ] |
| X9 | Same; quit the game | a `DISCONNECTED` document, exit `0` | [ ] |
| X10 | Open the json in an editor/another program while X5 runs | no corruption, no crash (temp file + replace) | [ ] |
| X11 | Vault unavailable (`--vault Z:\nope`): `read --export` / `read --query level` | export is an error (exit `1`); the query only warns and works | [ ] |

---

## 5. `read --live`

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| L1 | `read --live` in a real terminal (Windows Terminal / PowerShell) | banner, `✓ read attached, reading (Ctrl+C to stop)`, the same tree as `read`, **redrawn in place**; changed values highlighted yellow for about a second; nothing scrolls | [ ] |
| L2 | Take damage, spend stamina, gain runes, level up, rest at a grace | the numbers follow the game; `runes.delta` returns to `+0` after a grace rest (new baseline) | [ ] |
| L3 | `read --live --query hp` / `--query attrs.*` / `--query runes` | a small block, same behaviour | [ ] |
| L4 | `read --live --query nonsense` | exit `1` before any drawing | [ ] |
| L5 | Ctrl+C | the last frame stays, the cursor is visible again, exit `130`, the game keeps running | [ ] |
| L6 | Quit the game while `--live` runs | it ends on its own, exit `0`, the cursor is back | [ ] |
| L7 | Quit to the title screen, then load again | "waiting for a loaded world", then "world loaded", drawing resumes below | [ ] |
| L8 | Start `read --live` first, then the game | waits for the game (one message), then continues | [ ] |
| L9 | Window about 30 rows tall | the tree is cut with "… N more lines (make the window taller, or use --query)" | [ ] |
| L10 | Make the window narrow while it runs (about 50 columns) | lines are cut with `…`, no wrapping garbage | [ ] |
| L11 | Run it in a console that cannot redraw (Android Studio run window, or `read --live \| more`) | the tree once, then one line per changed value `HH:MM:SS  path  old → new`; the effects/animations counters do not flood it | [ ] |
| L12 | `NO_COLOR=1`; `FORCE_COLOR=1` | no colours / colours; same layout | [ ] |
| L13 | `--hz 1`, `--hz 120` | accepted; slower / smoother; CPU stays low | [ ] |
| L14 | `read --live -v` | the log lines on stderr; the tree still on stdout | [ ] |

---

## 6. `--live-effects` / `--live-animations`

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| M1 | `read --live-animations`; stand, run, roll, attack, sit at a grace | a table, one row per animation id; `+` green active, `-` dim gone; name or `Unknown`; time `HH:MM:SS.mmm`; the title counts active / seen / unmapped | [ ] |
| M2 | Run or walk for 10 s | rows do **not** blink or reshuffle every frame (ids that flip are settled); the newest activation is on top, the ones that left are below, latest first | [ ] |
| M3 | A row that changes | highlighted for about a second | [ ] |
| M4 | `read --live-effects`; eat a boost, equip a talisman, cast a buff, wait for it to end | `+` appears with `remaining / total s` counting down (`permanent` for talismans); `-` when it ends; the row stays | [ ] |
| M5 | `read --live-effects -q` | short internal effects (0 ≤ duration < 1 s) are hidden | [ ] |
| M6 | `read --live-effects --live-animations` | two tables in one screen; a short window shares the space (the smaller table first) and says "… N more" | [ ] |
| M7 | `--unmapped` / `--mapped` on each monitor | only rows that are / are not in `chr_state_ids.json`; the counts in the title stay | [ ] |
| M8 | `--mapped --unmapped`; `read --mapped`; `read --live --unmapped` | usage errors (exit `2`) | [ ] |
| M9 | While a monitor runs, add a name for an `Unknown` id in `chr_state_ids.json` and save | within about 2 s: `✓ read chr_state_ids.json reloaded (N ids)`, the row shows the name, the unmapped count drops | [ ] |
| M10 | Save a broken `chr_state_ids.json` (missing comma) | a warning "changed but cannot be read, keeping the old names"; fix it → reloaded | [ ] |
| M11 | Console that cannot redraw | lines `+ 2020110  Running  04:06:12.766`; with both monitors prefixed `[effects]` / `[animations]`; `-` lines after a short gap | [ ] |
| M12 | Ctrl+C; quit the game; title screen | as L5 / L6 / L7 | [ ] |
| M13 | An exe without an animation or effect layout (not testable on 1.17.1) | "…: layout incomplete in profile", exit `1` (unit-tested only) | [ ] |

---

## 7. `write` (needs `run` in T0 and a loaded character)

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| W1 | `write --set level=150` | `✓ write level = 150`; in game after reloading the area / resting the level is 150; `read --query level` agrees | [ ] |
| W2 | `write --set vigor=90 faith=40 runes=100000` | three `✓` lines | [ ] |
| W3 | Names: `--set attrs.vigor=50`, `character.attributes.mind=40`, `rune=5`, `hit_point=1`, `hp.current=2`, `stamina=10`, `Vigor=60` | all accepted (case-insensitive, full and short forms) | [ ] |
| W4 | Wildcards: `--set attrs.*=20`, `--set vitals.*.current=1` | every attribute / every current vital set | [ ] |
| W5 | `--set level=9999`, `--set vigor=500`, `--set runes=2000000000`, `--set hp=999999` | applied with "clamped to …" (713, 99, 999,999,999, max HP) | [ ] |
| W6 | `write --refill hp,fp,stamina` after taking damage | all three at their maximum | [ ] |
| W7 | `--set vigor=<current value>` | "values already match" | [ ] |
| W8 | Refused, **nothing written**, exit `1`, with the reason: `--set hp.max=1`, `fp.base=1`, `runes.delta=5`, `runes.baseline=5`, `effects=1`, `systems.status.pid=1`, `attributes=5`, `vitals=5`, `'*=1'`, `character.*=1`, `ALL=1`, `vigr=5`, `vigor=abc`, `vigor=-1`, `vigor=1 vigor=2`, `--set hp=1 --refill hp`, `--refill banana` | each with an explanatory message (computed by the game / by the tool / not a stored value / is a group / pattern must name a group / unknown name with suggestions / …) | [ ] |
| W9 | `write` with nothing, `write --set bogus` | usage error / `unknown name` | [ ] |
| W10 | Without a session: game started from Steam (no `run`); host killed (R7); no game running | exit `3` (EAC) / `5` / `1`; no write handle opened | [ ] |
| W11 | `write -v --set level=150` and `write --set level=150 -v` | both accepted; raw log lines | [ ] |
| W12 | **Parallel dimension:** after W1–W6 quit the game, T0 restores | the save is as before the session; `read` shows the old values next time | [ ] |
| W13 | Rapid repeated `write` runs (10 times) | no crash, no stuck state; the game stays stable | [ ] |

---

## 8. Log and console

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| G1 | Run any command, open `<vault>\eldendisk.log` | logcat lines `MM-DD HH:MM:SS.mmm PID L tag : msg`; the command line first, `exit N` last; every command appends | [ ] |
| G2 | Concise view on every command | ` time  symbol  tag  message`; symbols `✓ · ! ✖`; warnings and errors coloured | [ ] |
| G3 | On a Thai code page (cp874) console | symbols fall back to ASCII (`+ - ! x`), no `\u2713` | [ ] |
| G4 | Android Studio run window with `FORCE_COLOR=1` | colours shown; live views use the line fallback | [ ] |
| G5 | `-v` after the subcommand on every command | the log replaces the concise view | [ ] |
| G6 | Make the vault unavailable and run `hash` / `build` | the command works; the log is simply not written | [ ] |
| G7 | T0 `run -v`; in T1 run `read --query runes`, in T2 `write --set level=150`, `vault status` | T0 shows the other terminals' lines in the log format (`D cli : eldendisk 1.6.2 read --query runes`, `... exit 0`, the writer's events) as they happen; T0's own lines appear once, not twice | [ ] |
| G8 | T0 `run -v`: lines written **before** it started | not replayed (the tail starts at the end of the file) | [ ] |
| G9 | Several terminals logging at once for a few minutes (e.g. `read --live` + `write` loops), optionally with a small rotation size | no command fails; no garbled lines in `eldendisk.log`; after a rotation `run -v` keeps showing new lines | [ ] |
| G10 | `run` **without** `-v` while other terminals run commands | the concise view shows only its own events (no foreign lines) | [ ] |

---

## 9. Steam Cloud (T10, open)

Use a throwaway or backed-up save.

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| C1 | Steam online, Cloud on for Elden Ring. `run`, `write --set level=150`, quit the game | the host restores the old save; check Steam Cloud afterwards: does it hold the **edited** or the **restored** save? | [ ] |
| C2 | Steam offline mode or Cloud off, same | no sync; restored save only | [ ] |
| C3 | Record the result in spec section 9 | | [ ] |

---

## 10. Build and exe

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| B1 | `python -m eldendisk build -c -em` (no record present) | `build\dist\eldendisk\eldendisk.exe` | [ ] |
| B2 | The exe: P1–P5, Q1, L1, M1, W1, V1 | same behaviour as Python | [ ] |
| B3 | `build -c` while a record exists in a vault **under `build\`** | refused, exit `4`; with the default vault a rebuild never touches it | [ ] |
| B4 | `python code\tools\dev_pipeline.py --dry-run` | tests, build, dry run pass (no session record!) | [ ] |
| B6 | `python code\tools\dev_pipeline.py --vault-off` (no session record!) | tests, build, then `run -v --vault-off`: banner `mode vault OFF`; a typo such as `--vault-of` stops at once with a usage error before the tests | [ ] |
| L15 | T1 `read --query character.effects.* --live` with an effect active (e.g. Gold Scarab), then take it off | the rows turn into `none active` (no error, no exit); equip again: the rows come back; Ctrl+C exits `130` | [ ] |
| B7 | After `build -c -em`: open `build\dist\eldendisk\README.md` | starts with `# Elden-Disk 1.6.2 (eldendisk.exe)`, the quick start, then `# Command reference` with every command; no `{version}` left; renders in a Markdown viewer / Notepad is readable | [ ] |
| B5 | `python code\tools\soak_check.py` while `read --live --export` runs for 10+ minutes | no anomalies reported | [ ] |

---

## Automated tests (Linux or Windows, no game)

```commandline
python -m pytest          # 490 passed, 1 skipped
python -m pyflakes eldendisk tests tools
```

| File | Covers |
|:--|:--|
| `test_architecture` | import rules between host / vault / reader / writer / game, console modules |
| `test_save_vault`, `test_vault_command`, `test_vault_location`, `test_gamefolder` | snapshots, verify, restore, keep, prune, vault location, game-folder guard |
| `test_host` | host lifecycle H1–H9, fault injection at every boundary, interrupts |
| `test_run_command`, `test_launcher` | `run`, offline launch |
| `test_read_command` | print, `--query`, `--json`, `--export`, `--live` (terminal and fallback), monitors, filters, names reload, EAC, Ctrl+C, timeouts |
| `test_values` | names, aliases, wildcards, write targets, view / select / rows / changes |
| `test_ledger` | id ledger (settling, order, highlight), monitor lines, table drawing |
| `test_ui`, `test_logbook`, `test_cli_logging`, `test_console` | concise view, `-v`, log file, symbols, in-place screen |
| `test_write_command`, `test_memory_writer`, `test_profile_policy` | authorisation, edits, clamping, refusals |
| `test_disk`, `test_export`, `test_attach` | sampling, document and schema, EAC-aware attach |
| `test_main` | every flag, usage errors, help pages, removed names |
| `test_soak_check` | the soak helper |

What no unit test can show, and this plan is for: real memory layouts, EAC and Steam behaviour, real terminals (colours, redraw, code pages), timing against a live game, Steam Cloud.

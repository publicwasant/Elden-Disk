# Manual test plan 1.6.3 (real game, Windows)

For the checks the unit tests cannot make: the real game, a real terminal, Steam. Tick `[ ]` as you go and write what you saw next to anything that is not as expected. Exit codes: `echo $LASTEXITCODE` (PowerShell).

> [!IMPORTANT]
> **Before anything:** copy the save folder (`%APPDATA%\EldenRing\<SteamID64>`) somewhere safe. Do not run the build pipeline while a session record exists (`vault status` first).

Legend: `T0` = terminal running `eldendisk.exe run` (leave it open), `T1` = a second terminal, `T2` = a third. "Loaded" = a character is in the world, not the title screen.

Already seen on the real game (spec 1.6.2 section 9): `run` restore, hard-kill recovery, `write` by name, `read --live`, the two monitors. They are listed again so a release run is complete; tick them quickly. New in 1.6.3 (section 7A): game params. On the real game, `effectEndurance = -1` has been written into all four Black Flame rows (author's report, 2026-10-08: every configured spell burns without end, enemies burn to death, the effect bar stays lit). Not yet tried: the other fields, `--reset`, the title screen, the buffs rename.

---

## 0. Preparation

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| P1 | `eldendisk.exe --version` | `eldendisk 1.6.3` | [ ] |
| P2 | `eldendisk.exe -h`, then `read -h`, `write -h`, `vault -h`, `run -h` | each page lists the 1.6.3 flags (`write` shows `--set --reset --refill`); `read` shows `--query --export --live --live-buffs --live-animations --mapped --unmapped --json --timeout` | [ ] |
| P3 | `eldendisk.exe hash` | the SHA-256 of `eldenring.exe` only on stdout | [ ] |
| P4 | `eldendisk.exe vault status` (no session) | no record, trusted, exit `0` | [ ] |
| P5 | Old names are gone: `sandbox status`, `effects`, `animations`, `read effects`, `read --live-effects`, `read export`, `read --once`, `write set vigor=9`, `run --hz 30` | each is a usage error (exit `2`), nothing runs | [ ] |

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
| Q1 | `read` | a tree: `systems` (profile, features, status, session) and `character` (level, vitals, runes, attributes); numbers with thousands separators; with `character.buffs` and `character.animations` as in `disk-state.json`; exit `0`, returns at once | [ ] |
| Q2 | `read --query level` / `runes` / `hp` / `hp.max` / `hit_point.maximum` / `fp` / `stamina` / `vigor` / `attrs.*` | the value or group; `runes` and `hp` show the whole group | [ ] |
| Q3 | `read --query vitals.*.current` / `character.*` | the matching values (`character.*` includes the buffs and animations) | [ ] |
| Q4 | `read --query vigr` | exit `1`, "unknown name 'vigr'; did you mean … vigor" | [ ] |
| Q5 | `read --query runes --json \| ConvertFrom-Json` | valid JSON, only that value | [ ] |
| Q6 | `read --query buffs`, `read --query character.buffs.*`, `read --query animations` | just the lists (also with `--live`) | [ ] |
| Q7 | game not running: `read --timeout 3` | "waiting for eldenring.exe …" then exit `1` after about 3 s | [ ] |
| Q8 | game at the title screen: `read --timeout 3` | "no loaded world after 3 s …; load a character first", exit `1` | [ ] |
| Q9 | game started from Steam (EAC): `read` | exit `3` with the hint to use `eldendisk run` (not "module not found") | [ ] |
| Q10 | `read --hz 500`, `--timeout 0`, `--json --live`, `--export --query hp`, `--live-buffs --live` | each a usage error, exit `2` | [ ] |
| Q11 | `read --query character.runes.* character.buffs.*`, then the same with `--live` | one tree: `character` once, `runes` with its values, `buffs` with each id; `--live` redraws and highlights in place; a typo in any name stops with exit `1` | [ ] |
| Q12 | `read --flat`, `read --query character.runes.* attrs.vigor --flat`, then the same with `--live` | one `full.path  value` row per value, aligned, no headings; `--live` redraws in place and highlights changes; `--flat --export` / `--json` / `--live-buffs` are usage errors (exit `2`) | [ ] |

---

## 4. `read --export`

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| X1 | `read --export` | `✓ export disk-state.json (N KB) written to <dir>`, exit `0`; the file has `systems`, `character` (with `buffs` and `animations`) and `params`; valid against `reader/disk.schema.json` | [ ] |
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
| L7 | In a real terminal: warp, die, or quit to the title screen and load again | the tree stays in place with a dim `waiting for a loaded world …` line under it; when the world is back the tree is redrawn over it, **no second copy** is printed below; the reason shows only with `-v` / in the log. Without a terminal (`\| more`): two events once each | [ ] |
| L8 | Start `read --live` first, then the game | waits for the game (one message), then continues | [ ] |
| L9 | Window about 30 rows tall | the tree is cut with "… N more lines (make the window taller, or use --query)" | [ ] |
| L10 | Make the window narrow while it runs (about 50 columns) | lines are cut with `…`, no wrapping garbage | [ ] |
| L11 | Run it in a console that cannot redraw (Android Studio run window, or `read --live \| more`) | the tree once, then one line per changed value `HH:MM:SS  path  old → new`; the buffs/animations counters do not flood it | [ ] |
| L16 | `read --query character.buffs.* --live` with a timed buff active (e.g. Golden Vow) | `buff_duration` counts down in magenta, other values (`max_duration`, names) stay plain; a change elsewhere is still yellow | [ ] |
| L12 | `NO_COLOR=1`; `FORCE_COLOR=1` | no colours / colours; same layout | [ ] |
| L13 | `--hz 1`, `--hz 120` | accepted; slower / smoother; CPU stays low | [ ] |
| L14 | `read --live -v` | the log lines on stderr; the tree still on stdout | [ ] |

---

## 6. `--live-buffs` / `--live-animations`

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| M1 | `read --live-animations`; stand, run, roll, attack, sit at a grace | a table, one row per animation id; `+` green active, `-` dim gone; name or `Unknown`; time `HH:MM:SS.mmm`; the title counts active / seen / unmapped | [ ] |
| M2 | Run or walk for 10 s | rows do **not** blink or reshuffle every frame (ids that flip are settled); the newest activation is on top, the ones that left are below, latest first | [ ] |
| M3 | A row that changes | highlighted for about a second | [ ] |
| M4 | `read --live-buffs`; eat a boost, equip a talisman, cast a buff, wait for it to end | `+` appears with `remaining / total s` counting down (`permanent` for talismans); `-` when it ends; the row stays | [ ] |
| M5 | `read --live-buffs -q` | short internal buffs (0 ≤ duration < 1 s) are hidden | [ ] |
| M6 | `read --live-buffs --live-animations` | two tables in one screen; a short window shares the space (the smaller table first) and says "… N more" | [ ] |
| M7 | `--unmapped` / `--mapped` on each monitor | only rows that are / are not in `chr_state_ids.json`; the counts in the title stay | [ ] |
| M8 | `--mapped --unmapped`; `read --mapped`; `read --live --unmapped` | usage errors (exit `2`) | [ ] |
| M9 | While a monitor runs, add a name for an `Unknown` id in `chr_state_ids.json` and save | within about 2 s: `✓ read chr_state_ids.json reloaded (N buffs, N animations)`, the row shows the name, the unmapped count drops | [ ] |
| M10 | Save a broken `chr_state_ids.json` (missing comma) | a warning "changed but cannot be read, keeping the old names"; fix it → reloaded | [ ] |
| M11 | Console that cannot redraw | lines `+ 2020110  Running  04:06:12.766`; with both monitors prefixed `[buffs]` / `[animations]`; `-` lines after a short gap | [ ] |
| M12 | Ctrl+C; quit the game; title screen | as L5 / L6 / L7 | [ ] |
| M13 | An exe without an animation or buff layout (not testable on 1.17.1) | "…: layout incomplete in profile", exit `1` (unit-tested only) | [ ] |
| M14 | Your own old (1.6.2, flat, with `sources`) `chr_state_ids.json` in place: `read --live-buffs` | exit `1` / a clear error "expected an object with "buffs" and "animations" (an old flat file? python tools/convert_state_ids.py FILE converts it)". Then `python code/tools/convert_state_ids.py chr_state_ids.json`: a `.bak` copy, the new file has `buffs` and `animations` and no `sources`; `read --live-buffs --live-animations` name the same ids as before | [ ] |
| M15 | `read --live-buffs --state-ids <other file>` | the names come from that file (`--effects` no longer exists: usage error) | [ ] |
| M16 | `read --export` while a buff is active, open `disk-state.json` | the buff is under `character.buffs` (not `effects`), `systems.features.buffs_supported` and `systems.status.ignored.buffs` exist, nothing is called `effects` outside `params.effects` | [ ] |

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
| W8 | Refused, **nothing written**, exit `1`, with the reason: `--set hp.max=1`, `fp.base=1`, `runes.delta=5`, `runes.baseline=5`, `buffs=1`, `systems.status.pid=1`, `attributes=5`, `vitals=5`, `'*=1'`, `character.*=1`, `ALL=1`, `vigr=5`, `vigor=abc`, `vigor=-1`, `vigor=1 vigor=2`, `--set hp=1 --refill hp`, `--refill banana` | each with an explanatory message (computed by the game / by the tool / not a stored value / is a group / pattern must name a group / unknown name with suggestions / …) | [ ] |
| W9 | `write` with nothing, `write --set bogus` | usage error / `unknown name` | [ ] |
| W10 | Without a session: game started from Steam (no `run`); host killed (R7); no game running | exit `3` (EAC) / `5` / `1`; no write handle opened | [ ] |
| W11 | `write -v --set level=150` and `write --set level=150 -v` | both accepted; raw log lines | [ ] |
| W12 | **Parallel dimension:** after W1–W6 quit the game, T0 restores | the save is as before the session; `read` shows the old values next time | [ ] |
| W13 | Rapid repeated `write` runs (10 times) | no crash, no stuck state; the game stays stable | [ ] |

---

## 7A. Game params (new in 1.6.3; needs `run` in T0, offline, a loaded character with the Black Flame incantation)

Set-up: T0 `eldendisk.exe run`. Target: an enemy that does not die at once (the frog in Mogwyn Palace worked). Names are `params.effects.<id>.<field>`; rows (ids): `1621000` Black Flame, `1623000` Scouring Black Flame, `1625000` Black Flame Ritual, `1626001` Black Flame Blade; every row also shows `name` (text, never written); writable fields: `effectEndurance` (`-1` = permanent, default `2`), `motionInterval`, `changeHpRate`, `changeHpPoint`; locked (read-only): `atkOccurrenceSpEffectId`, `vfxId`. Edits are in the game's memory only: they are gone when the game closes.

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| PA1 | `read --query params` | a tree `params` > `effects` > the four ids (1621000, 1623000, 1625000, 1626001), each with `name` (e.g. `Black Flame`) and the six fields; `effectEndurance 2.0`, `motionInterval 0.1`, `changeHpRate 0.1`, `changeHpPoint 1`, `atkOccurrenceSpEffectId -1`, `vfxId 9010` (no thousands separator); exit `0` | [ ] |
| PA2 | `read --query params.effects.1621000.effectEndurance`, then with `--json` | `2.0`; valid JSON `{"params.effects.1621000.effectEndurance": 2.0}`; the name works in any letter case (`PARAMS.effects.1621000.effectendurance`) | [ ] |
| PA3 | `read --export` | the file has `systems`, `character`, `params` (in that order); valid against `reader/disk.schema.json`; `character` and `systems` as before | [ ] |
| PA4 | T1 `write --set params.effects.1621000.effectEndurance=-1`, then cast Black Flame on the enemy | `✓ write params.effects.1621000.effectEndurance = -1.0`; the burn never ends and the black fire stays on the enemy until it dies (seen on the real game with this value) | [ ] |
| PA5 | `read --query params.effects.1621000` | `effectEndurance -1.0`, the other five fields unchanged; the other rows still `2.0` | [ ] |
| PA6 | Reset (PA9), then PA4 for each of `1623000`, `1625000`, `1626001`, one at a time, with its own spell (Blade: apply the buff, then hit) | each burns without end with its own spell and **only** with it. **Reported working for all four rows by the author (2026-10-08)**; tick it when you have seen each one with this build. Write down which fail: ______ | [ ] |
| PA7 | `write --set "params.effects.*.effectEndurance=-1"` | a line `… matches 4 values: 1621000.effectEndurance, …`, then four `✓` lines; `read --query "params.effects.*.effectEndurance" --flat` shows `-1.0` four times | [ ] |
| PA8 | `write --set params.effects.1621000.motionInterval=1 params.effects.1621000.changeHpRate=0.5 params.effects.1621000.changeHpPoint=3` | the three values read back (`1.0`, `0.5`, `3`); in game the burn ticks slower / harder as set (note what you see) | [ ] |
| PA9 | `write --reset params.effects.1621000.effectEndurance`; then `--reset params.effects.1621000` (a whole row); then `--reset all` | the game's own values (`2.0`, `0.1`, `0.1`, `1`) return field, row, everything; a new cast burns about 2 seconds again. With nothing to reset: `values already match`, exit `0` | [ ] |
| PA10 | A burn already on the enemy when you edit | it keeps the duration it had; a **new** cast uses the new value (expected, because the effect is copied to the target when it is applied) | [ ] |
| PA11 | `write --set params.effects.1621000.vfxId=0`, `...atkOccurrenceSpEffectId=0`, `...VFXID=1`, `...name=x` | `✖ … is locked (read-only); nothing was written`, exit `2`; `read` still shows `9010` / `-1`; same result with no valid session (e.g. after `run --vault-off`, the game running) because the name is checked before the session | [ ] |
| PA12 | `write --set "params.effects.1621000.*=1"` | the four writable fields are written; a line `skipped (locked): … vfxId …` (the row's `name` is not listed); `name` and `vfxId` unchanged; `vfxId` still `9010` | [ ] |
| PA13 | `--set params.effects.1621000.effectEndurance=-5`; `...motionInterval=0`; `...changeHpPoint=100000` | applied with `(clamped from … to the allowed …)`: `-1.0`, `0.01`, `999` | [ ] |
| PA14 | Refused, **nothing written**, exit `1`: `...effectEndurance=abc`, `...changeHpPoint=1.5`, `...changeHpPoint=`, `params.effects.1621000.effectEndurence=-1` (suggestion `did you mean`), `params.effects.1621000=1` (is a group), the same field twice, `--set X=-1 --reset <the row of X>` | each with an explanatory message | [ ] |
| PA15 | `--reset level`, `--reset hp`, `--reset params.effects.1621000.effectEndurance=2`, `--reset bogus` | refused, exit `1`: `--reset` takes `params.…` names or `all` only | [ ] |
| PA16 | `read --query buffs`, `read --query effects` and `read --query character.*` | `buffs` is the character's active buffs; plain `effects` is **not** a name any more (unknown name; params are always `params.effects…`); `character.*` shows no `params` | [ ] |
| PA17 | Params edit without a session: game started from Steam; host killed (R7); `run --vault-off`; no game running | exit `3` (EAC) / `5` / `5` / `1`; no write handle opened; nothing changed. A params edit is covered by the same session gate as every other `write` | [ ] |
| PA18 | T1 `read --live --query params.effects.1621000.effectEndurance`, T2 `write` the value | the value changes in T1 within about a second, highlighted | [ ] |
| PA19 | Leave `-1` set, quit the game, start it with `run` again, `read --query params…` | back to the defaults (`2.0` ...). `read --export` while the game is closed (live export, then quit the game) writes `"params": null` | [ ] |
| PA20 | At the title screen (no character loaded): `read --query params` and `write --set params…=…` | note what happens (values or a clear "not readable" / "world" message). No crash. Result: ______ | [ ] |
| PA21 | `read --live --export` for 10+ minutes with `params` present | CPU low; the file is not rewritten while nothing changes; no warnings in `eldendisk.log` | [ ] |
| PA22 | Regression: repeat Q1-Q3, X1, L1, W1, W4 | unchanged; `read` with no flag now ends with the `params` tree | [ ] |
| PA23 | `write -h`, README, `docs/cli-commands-exe.md` | `--reset` is documented; warnings present: offline `run` only (online play risks a ban), edits vanish when the game closes, a burn that is already on keeps its old duration | [ ] |

Checks that cannot be made by hand (unit tests only): a file head that fails its self-check, a row id that is missing, a row offset off the grid, an unreadable row, a broken first chain falling back to the next (the three chains X, Y, Z all lead to the same file on 1.17.1).

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
| G7 | T0 `run -v`; in T1 run `read --query runes`, in T2 `write --set level=150`, `vault status` | T0 shows the other terminals' lines in the log format (`D cli : eldendisk 1.6.3 read --query runes`, `... exit 0`, the writer's events) as they happen; T0's own lines appear once, not twice | [ ] |
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
| L15 | T1 `read --query character.buffs.* --live` with a buff active (e.g. Gold Scarab), then take it off | the rows turn into `none active` (no error, no exit); equip again: the rows come back; Ctrl+C exits `130` | [ ] |
| B7 | After `build -c -em`: open `build\dist\eldendisk\README.md` | starts with `# Elden-Disk 1.6.3 (eldendisk.exe)`, the quick start, then `# Command reference` with every command; no `{version}` left; renders in a Markdown viewer / Notepad is readable | [ ] |
| B5 | `python code\tools\soak_check.py` while `read --live --export` runs for 10+ minutes | no anomalies reported | [ ] |

---

## Automated tests (Linux or Windows, no game)

```commandline
python -m pytest          # 624 passed, 1 skipped
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
| `test_write_command`, `test_memory_writer`, `test_profile_policy` | authorisation, edits, clamping, refusals; params edits, `--reset`, locked fields |
| `test_params` | params: the file layout (11,354 rows, measured offsets), the three chains, rows by id, self-checks, names and patterns, the profile block, the `params` block of the document |
| `test_disk`, `test_export`, `test_attach` | sampling, document and schema, EAC-aware attach |
| `test_main` | every flag, usage errors, help pages, removed names |
| `test_soak_check` | the soak helper |

What no unit test can show, and this plan is for: real memory layouts, EAC and Steam behaviour, real terminals (colours, redraw, code pages), timing against a live game, Steam Cloud.

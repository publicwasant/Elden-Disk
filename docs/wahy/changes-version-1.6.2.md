> [!NOTE]
> **Version:** `1.6.2`  
> **Status:** IMPLEMENTED (unit tests only; real-game verification still open, see spec 1.6.2 section 9)  
> **Last Updated:** _2026-10-06_

**Summary:** Foundation release, no new game features. The tool is split into four bounded parts: **host** (`run`), **vault**, **reader** (`read`), **writer** (`write`). The vault is the one part that must never fail; the writer only works inside a session the host has verified.

_(baseline: **[changes-version-1.6.1.md](changes-version-1.6.1.md)**; design: **[elden-disk-spec-v1.6.2.md](../specs/elden-disk-spec-v1.6.2.md)**)_

---

## Wahy

| # | Change | Where |
|:-:|:---|:---|
| 1 | **Four commands, one job each.** `run` (host), `read` (reader), `write --set\|--refill` (writer), `vault status\|list\|verify\|restore\|prune`. `sandbox`, `effects`, `animations` and the flags `--attach`, `--out`, `--hz`, `--timer-interval`, `--no-idle` on `run` are gone. | `__main__.py`, `commands/` |
| 2 | **Package layout.** `__main__.py` only parses and dispatches. New packages `vault/`, `host/`, `game/`, `reader/`, `writer/`, `commands/`; the 1.6.1 modules `disk`, `game_launcher`, `json_logger`, `memory_reader`, `memory_writer`, `profile_loader`, `sandbox`, `save_vault` are removed. | `eldendisk/` |
| 3 | **Enforced boundaries.** `test_architecture.py` parses the imports of every module: the host and the vault never import game memory, reader and writer never import each other, the write capability exists only in `writer/writer.py`. Verified by breaking each rule on purpose. | tests |
| 4 | **Session record replaces the marker.** `session.json` (v2): state, `snapshot_verified`, host and game pid with process start times, exe hash. Present exactly while a restore is owed. A 1.6.0/1.6.1 `PENDING_RESTORE.json` is read as `RESTORE_PENDING`. | `vault/session.py` |
| 5 | **Writer authorisation.** `write` proceeds only if the record is readable, `RUNNING`, snapshot verified, the attached game is the recorded process (pid and start time), the exe hash matches and the host is alive. Otherwise exit `5`, no write handle opened. A record left by a dead host authorises nothing. | `vault/session.py`, `commands/write.py` |
| 6 | **Host never touches game memory.** It only queries a process start time. JSON output and the 60 Hz loop are removed from `run`. | `host/` |
| 7 | **Host lifecycle H1-H9 with invariants.** I1 (live save equals snapshot, or a verified record exists), I2 (host never opens the game for memory access), I3 (a modified save is archived before it is overwritten, default on). First Ctrl+C is absorbed, second leaves `RESTORE_PENDING` (exit 4). Console close, logoff and shutdown mark `RESTORE_PENDING`. Launch timeout 120 s; the restore retries locked files for 30 s. | `host/host.py`, `host/interrupts.py` |
| 8 | **One restore path.** The host and `vault restore` both call `restore_from_record`: archive only if the live save differs, restore, verify, game-folder cleanup, remove the record. Safe to repeat. `run` does not auto-recover; it refuses and prints the command. | `vault/recover.py` |
| 9 | **Fault-injection test.** The host is killed at 8 boundaries; each time the invariant holds and `vault restore` returns the live folder byte-identical. | `tests/test_host.py` |
| 10 | **Reader.** One attach and one loop for several features (`read --live-effects --live-animations`, `--export`). Waits for the game instead of failing. Stops on EAC. Labels the export as in-session while a valid record covers the game. | `commands/read.py`, `reader/` |
| 11 | **Export write policy.** Write only when the document changed, at most every `--export-interval` (0.5 s), buff countdowns at most every `--timer-interval` (2 s, `0` = never), final write on exit; the one-shot `--export` replaced `--once`. Replaces 60 Hz disk writes. | `reader/export.py` |
| 12 | **Writer renamed.** `sandbox --set/--refill` is `write --set NAME=VALUE...` / `write --refill LIST`. | `commands/write.py`, `writer/` |
| 13 | **Tests.** 279 pass, 1 skipped (Linux, fake Windows and memory layers): new `test_architecture`, `test_host`, `test_write_command`, `test_read_command`, `test_vault_command`, `test_export`, `test_gamefolder`. | tests |

## Behaviour changes

- `run` no longer writes `disk-state.json`; use `eldendisk read --export` (once) or `read --live --export` in another terminal.
- `read` works with or without `run`; `write` always needs a session.
- `run` while a record exists exits `4` instead of recovering by itself.
- The modified save is archived into the vault before every restore (`--no-archive-contaminated` to skip); `vault prune` reclaims the space.
- Exit codes: `0` ok, `1` error / not applied, `2` unsupported exe, `3` EAC, `4` restore pending, `5` no valid session, `130` interrupted.
- `systems.session.mode` / `sandbox` in the export keep their names (schema unchanged); they mean "a valid session covers this game".

## Decisions taken while implementing

- The session record carries process start times, so a reused pid is never mistaken for the game or the host.
- Windows gives a console handler only a few seconds, so closing the window marks `RESTORE_PENDING` and does not try to restore; the game is not killed.
- Steam Cloud is assumed harmless (offline launch, frozen save); the README keeps one line saying it is not verified.

## Not done / open

- Nothing here was run against the real game. Check on a copy of the save: normal run and restore, Ctrl+C once and twice, closing the console window, killing the host, `write` after killing the host (expect exit 5), `vault restore` afterwards.
- Spec test T10 (Steam Cloud) is still not run.

## Fix after first Windows run

- `tools/dev_pipeline.py`: starting the freshly built `eldendisk.exe` sometimes failed with `PermissionError: [WinError 5] Access is denied` (the scanner still holds the new file). Step 3 now retries up to 10 times, 1.5 s apart, and prints a hint about antivirus exclusions if it still fails.
- `host/launcher.py`: the game was started on the host's console, so Ctrl+C in the host terminal also reached `eldenring.exe` (it quit with the host) and closing the console window would have killed it. It is now started `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` with null stdio. "First Ctrl+C keeps the game running" now holds on real Windows. New `tests/test_launcher.py` (281 passed, 1 skipped).
- **Vault wiped by a rebuild (found in real use).** The built exe's default vault is `<exe folder>/backup/vault`, i.e. inside `build/`, and `dev_pipeline` runs `build -c`, which deletes `build/`. A host killed from the IDE (stop button, no handler can run) left a session record and the only clean snapshot there; the next pipeline run deleted both, so the next session snapshotted the already modified save as "clean" and `vault restore` found nothing. Fixes: `build -c` now refuses (exit 4) while a session record or a v1 marker exists under `build/`; `tools/dev_pipeline.py` runs the host with a fixed `--vault code/backup/vault` that survives rebuilds and prints the matching `vault restore` command; every "run `vault restore`" message (host, vault status, preflight) now includes `--vault "<path>"`, because the vault must be the same one. Tests: 284 passed, 1 skipped.
- **Vault location (decided after the incident above).** The vault no longer defaults to `<exe folder>/backup/vault`. Resolution for every command: `--vault` > the path remembered in the Registry (`run --vault X` remembers X, like `--save-dir`) > `%LOCALAPPDATA%\EldenDisk\vault`. An unavailable remembered path is an error, not a new empty vault. New `vault/location.py`, `tests/test_vault_location.py`.
- **Build output** is now `./build/dist/eldendisk/eldendisk.exe` (version removed from the path); `dev_pipeline.py` no longer passes `--vault` (the default is stable). The `build -c` guard stays for vaults placed under `build/` by hand. Tests: 293 passed, 1 skipped.
- Migration: a vault left in an old `build/dist/<version>/.../backup/vault` is not seen by the new default; point `--vault` at it once (`eldendisk vault status --vault <old path>`) if it still holds an unresolved session.

## Added after the incident (approved proposals)

| # | Change | Where |
|:-:|:---|:---|
| A | **`vault keep [--yes]`**: keep the current save as the new baseline and end an unresolved session (the supported way to keep `write` edits). Refused while the game or the host runs, or after an interrupted restore. Current save backed up first as `<ts>-kept`; pre-session snapshot kept. | `commands/vault.py`, `vault/recover.py` |
| B | **`run --keep N`** (default 5): prune old snapshots after a finished session, never while a record exists; `0` = never. `-kept` snapshots are recognised by `vault list` / `prune`. | `commands/run.py`, `vault/vault.py` |
| C | **Steam Cloud note** printed by `run` when `steam.exe` is running; README says to use Steam offline mode or turn Steam Cloud off for Elden Ring. | `commands/run.py`, README |
| D | **Real-game evidence** recorded in spec section 9. | spec |
| E | **Console fallback**: `OK` / `FAILED` instead of a literal `\u2713` on cp874 / cp1252 consoles (IDE run windows). | `console.py` |

Tests: 308 passed, 1 skipped (`test_vault_command` keep cases, `test_run_command`, `test_console`, `test_every_help_page_renders`: a bare `%` in `--vault`s help text crashed `run -h` until it was escaped).

## CLI UX and log (requested after the incident)

| # | Change | Where |
|:-:|:---|:---|
| 1 | **Concise console view** for every command: ` time  symbol  tag  message` (`✓ done`, `· info`, `! warning`, `✖ error`), banner for `run` / `read`, aligned result tables for `vault status` / `list`, shorter messages (no glyphs in the message text, paths moved to the banner and the log). Colour on terminals; `NO_COLOR` / `FORCE_COLOR`; `+ - ! x` instead of the symbols on legacy code pages. | `ui.py`, `commands/*`, `host/host.py`, `vault/recover.py` |
| 2 | **Logcat-style log file** `<vault>/eldendisk.log` with every event of every command, all levels, rotated at 2 MiB (3 files); command line and exit code included. `session.log` in the snapshot keeps the per-session copy. | `logbook.py`, `logsetup.py`, `vault/session.py` |
| 3 | **`-v` = the log, live**: on every command (also after the subcommand) it replaces the concise view and the banner with the log lines themselves. | `commands/common.py` (`add_verbose`), `__main__.py` |
| 4 | **No `-v` needed** to see results: `write` prints the applied values, `read` and `vault` their events and results. `hash` still prints only the digest on stdout. | `commands/*` |
| 5 | `vault`, `host`, `game`, `reader`, `writer` report through injected callables and never import the console modules (new architecture test). `tools/dev_pipeline.py` sets `FORCE_COLOR=1` for the exe it starts. | `test_architecture.py`, `tools/dev_pipeline.py` |

Decisions to confirm: the log lives in the vault folder even for `hash` / `build` (a command with an unavailable remembered vault logs nothing); the concise view hides debug events such as `state RUNNING` (they are in the file and in `-v`); `read --live-effects` / `--live-animations` data lines stay on stdout in both modes.

Tests: 338 passed, 1 skipped (new `test_logbook`, `test_ui`, `test_cli_logging`; older command tests re-pointed at the new lines). Not run on real Windows: colours in the IDE run window, the banner width and the symbols on cp874.

## Fix: `read` under EasyAntiCheat said "module not found"

Real use: the game started from Steam (even in Steam's offline mode, which does not switch EAC off) made `read` print `eldenring.exe module not found`, because EAC hides the module list from other processes and the EAC check was never reached. `locate` now reports exit `3` with "started with EasyAntiCheat ... start the game with `eldendisk run`" when the module list is unreadable and anti-cheat processes (`start_protected_game`, `EasyAntiCheat*`) are running; otherwise a plain "cannot list the modules" error. New `tests/test_attach.py` (338 passed, 1 skipped). The EAC cause is the most likely one from the symptom, not confirmed on the user's machine.

## Read/write redesign (round 1)

Same version: no bump. The interface now says what it does by name, and a read is one shot unless asked to continue.

| # | Change | Where |
|:-:|:---|:---|
| 1 | `read` with no flag prints every value once and exits. `--query NAME [--json]` prints one value or group. `--export` writes `disk-state.json` once (schema unchanged). | `commands/read.py`, `reader/view.py` |
| 2 | `--live` = do not stop: alone the full list, redrawn in place on a terminal with changed values highlighted (elsewhere: the list once, then one line per change); with `--query` that value; with `--export` the old loop (sample at `--hz`, default 60, write on change, `--export-interval`, `--timer-interval`, `--no-idle`). | `commands/read.py` |
| 3 | `--live-effects` / `--live-animations` replace the verbs `effects` / `animations`; they stand alone and combine with each other. Now **one row per id** (not a stream of repeats): `+` active / `-` gone, name or `Unknown`, time `HH:MM:SS.mmm`, active first then latest first, changed rows highlighted, redrawn in place on a terminal; ids that flip every frame are settled (0.25 s). `--mapped` / `--unmapped` filter; `chr_state_ids.json` is re-read when it changes. | `reader/ledger.py`, `reader/monitor.py`, `commands/read.py`, `ui.py` |
| 4 | `--timeout` (default 15 s) for one-shot modes waiting for the game and a loaded world; live modes wait for ever. `--once` is gone. | `commands/read.py`, `__main__.py` |
| 5 | **Names only.** `game/values.py`: the paths of `disk-state.json` with short forms and aliases (`attrs`, `rune`, `hp`, `fp`, `max`); unknown names fail with suggestions. No addresses, offsets, chains, scans or raw writes (decided: over-engineering for a one-person tool; new writable values go into `offsets.json`). | `game/values.py` |
| 6 | `write --set NAME=VALUE ...` (repeatable) and `--refill LIST` replace `write set` / `write refill`. Group wildcards (`attrs.*`, `vitals.*.current`); bare `*`, `character.*`, `ALL` refused. Everything `read` shows can be named; derived values (`hp.maximum`, `hp.base`, ...) are refused with the reason. | `writer/writer.py`, `commands/write.py` |
| 7 | `ExportWriter` builds the document without a file (`build`), so `read` and `--export` share one source. | `reader/export.py` |
| 8 | **Values only.** `read` without a name and `--live` show the values of `disk-state.json` without the long effect and animation lists; ask for them by name (`--query effects`, `--query character.effects.*`, also `--live`). The file itself is unchanged. | `reader/view.py` |

Decisions to confirm: a bare `hp` / `runes` reads as the whole group but writes as `...current` / `...total`; the 13 stored values are the only settable ones; a vault that cannot be resolved is fatal only for `--export`; `--live` redraws in place on a terminal and falls back to a change stream elsewhere; a tree taller than the window is cut with a summary line; the monitors use the same screen (one table per monitor); no bars and no `q` / `p` keys.

Tests: 456 passed, 1 skipped (rewritten `test_read_command`; new `test_values`; `test_write_command`, `test_main`, `test_cli_logging`, `test_architecture` updated). **Not run on real Windows.**

Also recorded in the spec (section 9): the real-game hard-kill recovery (`vault restore`, byte-identical), normal Steam play followed by a host run, and the Steam Cloud upload seen online (T10 still open).

Real-game check (author, 2026-10-07): `read --live`, `--live-effects` / `--live-animations` and `write --set` with the new names work. Still unreported: `--export`, `--mapped` / `--unmapped`, the names reload, `write --refill` and the refusal messages; T10 (Steam Cloud sync on exit) is untested.

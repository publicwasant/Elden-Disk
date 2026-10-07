# Implementation Plan v1.6.2

See [changes-version-1.6.2.md](../wahy/changes-version-1.6.2.md) and [elden-disk-spec-v1.6.2.md](../specs/elden-disk-spec-v1.6.2.md).

## Proposed Changes
- **[MODIFY] `__main__.py`**: parser and dispatch only; commands `run`, `read`, `write`, `vault`, `build`, `hash`; validation of `--hz` (1-120), intervals, `--timeout`, flag combinations of `read`, `--launch-timeout`.
- **[NEW] `paths.py`, `console.py`**: runtime dirs and resources; logging and the Windows/x64 check.
- **[NEW] `commands/`**: one module per command (`run`, `read`, `write`, `vault`, `build`, `common`).
- **[NEW] `vault/`**: `saves`, `vault`, `session` (record v2 + `authorise`), `gamefolder`, `recover` (from `save_vault.py`).
- **[NEW] `vault/location.py`**: vault resolution (`--vault` > Registry > `%LOCALAPPDATA%\\EldenDisk\\vault`).
- **[MODIFY] `commands/build.py`**: output `./build/dist/eldendisk/`; `-c` guard.
- **[MODIFY] `commands/vault.py`, `vault/recover.py`, `vault/session.py`**: `vault keep`, `keep_from_record`, `host_alive`.
- **[MODIFY] `commands/run.py`**: `--keep`, `auto_prune`, Steam note. **[MODIFY] `console.py`**: ASCII fallback.
- **[NEW] `host/`**: `host` (lifecycle, from `sandbox.py`), `launcher`, `interrupts`.
- **[NEW] `game/`**: `_win`, `processes`, `memory`, `profile`, `layout`, `attach`.
- **[NEW] `reader/`**: `sampler`, `effects`, `animations`, `export`, `view` (names -> rows / JSON / changes), `ledger` and `monitor` (the effect / animation tables), `disk.schema.json`. **[NEW] `game/values.py`**: value names, aliases, write targets.
- **[NEW] `writer/`**: `writer.py` (from `memory_writer.py`).
- **[DELETE]** `disk.py`, `game_launcher.py`, `json_logger.py`, `memory_reader.py`, `memory_writer.py`, `profile_loader.py`, `sandbox.py`, `save_vault.py`.
- **Tests:** new `test_architecture`, `test_host` (incl. fault injection), `test_write_command`, `test_read_command`, `test_vault_command`, `test_export`, `test_gamefolder`; old sandbox tests removed; remaining tests re-pointed at the new modules.
- **Docs:** README, `cli-commands*.md`, spec/plan/changes 1.6.2.

## Verification Plan
1. `python -m pytest` (483 passed, 1 skipped).
2. `python -m eldendisk -h` and each subcommand's `-h`; removed flags and `sandbox` are rejected.
3. On Windows, on a **copy** of the save: T0 `eldendisk run -v`, T1 `eldendisk read --live -v` (then `read`, `read --query attrs.*`, `read --export`, `read --live --export`, `read --live-effects`, `read --live-animations --unmapped`), T2 `eldendisk write --set level=150 -v` (also `--set vigor=40 faith=40`, `--set attrs.*=20`, `--refill hp,fp`, and a refusal such as `--set hp.maximum=1`); close the game and confirm the byte-identical restore and the `[vault] verification passed` line.
4. Kill the host (Task Manager) with the game open: `write` must exit 5; after closing the game `vault status` shows the record and `vault restore` restores and clears it.
5. Close the console window during a session: the record is `RESTORE_PENDING`; `vault restore` after the game exits.
6. `python -m eldendisk build -c -em`, then `build/dist/eldendisk/eldendisk.exe vault status` (vault in `%LOCALAPPDATA%\\EldenDisk\\vault`).
7. Rebuild while a session record exists in a vault under `build/`: expect the refusal; with the default vault the rebuild must not touch it.
7. T10 Steam Cloud dry run on a throwaway save.
8. `vault keep`: write, let the game save, stop the host, close the game, `vault keep --yes`; the live save must be unchanged and `vault status` trusted.
9. Run twice with `--keep 1`: only one snapshot remains and the newest is the last session's.
10. Log and view: run any command, then open `<vault>/eldendisk.log` (logcat lines, command line first, `exit N` last); `run -v` prints exactly those lines live instead of the banner; `write --set level=150` prints `✓ write level = 150` without `-v`; in the IDE run window check colours (`FORCE_COLOR=1`) and the symbols on cp874.
11. Vault OFF and client log: `run --vault-off` (no snapshot, `write` exits 5, farming with `read --live --query runes`, progress kept); `run -v` in T0 shows the command lines of `read` / `write` in T1 / T2; an owed record still blocks `run --vault-off` (exit 4).

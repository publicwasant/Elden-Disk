# Implementation Plan v1.6.4 (IMPLEMENTED, unit tests only)

Feature: **the other world**, a `regulation.bin` kept in the vault and swapped into the game folder for one session. Design: [spec 1.6.4](../specs/elden-disk-spec-v1.6.4.md). Implemented on 2026-10-08, 657 tests.

## 1. Why this way

| Question | Answer |
|:--|:--|
| Why a file swap and not memory | The param tables are one fixed block in memory (row count, data start, no free space, cross-references), so rows cannot be added there. A `regulation.bin` with the rows already in it needs no tool support at all. |
| Why in the vault | The vault already does backup, record, restore and verify with all the failure handling. The swap is one more thing to undo. |
| Why no option | The file's presence is the switch (the author's design). `vault status` and the `run` banner show it. |

## 2. Code

| File | Change |
|:--|:--|
| `vault/vault.py` | constants `BIN_SUBDIR`, `REGULATION_DIR`, `REGULATION_NAME`; `Snapshot.bin_dir`; `regulation_world`, `world_info`, `regulation_problems`, `backup_regulation`, `install_regulation`, `restore_regulation`; `verify_snapshot` = `_save_problems` + `_bin_problems`; `restore` uses the save part only; list size and status include the file |
| `vault/session.py` | `SessionRecord.regulation`; `SessionLog.detach()` |
| `vault/recover.py` | `_restore_regulation` used by `restore_from_record` (after the save) and `keep_from_record` (before everything) |
| `host/host.py` | preflight asks the vault; `_prepare`: backup before the record, swap after READY, any failure goes through `_restore`; `_discard` replaces three `rmtree` calls (log fix) |
| `commands/run.py` | banner row, warning with `--vault-off` |
| `commands/vault.py` | `status` and `keep` text |
| `eldendisk/__init__.py` | `1.6.4` |

The host still never touches a file itself: it calls the vault. The architecture test is unchanged and passes.

## 3. Order of operations (why a crash is safe)

1. Save snapshot (verified) -> game's `regulation.bin` copied to `bin\` and hashed (still nothing owed).
2. `session.json` READY with `regulation`. From here a restore is owed.
3. Swap. A crash before this line: restore finds the original in place and writes nothing. A crash during: the `.tmp` is removed and the original written back.
4. Launch.

## 4. Tests

`tests/test_regulation.py` (30): flow, order, no file, vault off, preflight, failed and interrupted backup, file changed during preparation, failed and interrupted swap, tool killed before and after the swap, failed restore then `vault restore`, a failed save restore that still puts the game's file back, damaged backup, `keep` (both ways), list/status/prune, record round trip, command output. Plus `test_run_command.py` (2) and `test_host.py` (1, the log fix). The fix was checked by removing it: three tests fail.

## 5. Not done

Real-game check (manual plan 1.6.4). A version check of the user's file. Editing `regulation.bin` in the tool (not planned).

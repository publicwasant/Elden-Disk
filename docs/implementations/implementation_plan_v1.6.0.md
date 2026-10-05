# Implementation Plan v1.6.0

See [changes-version-1.6.0.md](../wahy/changes-version-1.6.0.md) and [elden-disk-spec-v1.6.0.md](../specs/elden-disk-spec-v1.6.0.md).

## Proposed Changes
- **[NEW] `save_vault.py`**: `scan`, `find_save_dir`, `check_live_dir`, `SessionLog`, `SaveVault` (preflight, snapshot, marker, restore, verify_live, archive, list, verify, prune, status).
- **[NEW] `sandbox.py`**: `State`, `Hooks`, `SandboxSession.run`, `restore_pending`, `EXIT_RESTORE_PENDING = 4`.
- **[NEW] `memory_writer.py`**: `WritableProcessMemory`, `WriteGate`, `parse_policy`, `MemoryWriter`; only module using `WriteProcessMemory`.
- **[MODIFY] `memory_reader.py`**: `list_process_names()`, `ProcessMemory(pid, access=ACCESS_MASK)`; still read-only.
- **[MODIFY] `game_launcher.py`**: `anticheat_processes`, `listing`, `cleanup_recorded`, `GameFolderGuard`.
- **[MODIFY] `disk.py`**: `locate_game_data`, `locate_vitals`, `vitals_address`, `parse_vitals_block`, `build_document(read_only=)`.
- **[MODIFY] `__main__.py`**: `cmd_run(args, gate, policy)`, lazy `_writer_api()`, `Monitor.read_only`, `sandbox` parsers and handlers; updated build layout (`build/dist/<ver>/eldendisk-v<ver>-x64/eldendisk/`) and dynamic vault scoping (`backup/vault`).
- **[MODIFY] `disk.schema.json`, `tools/soak_check.py`**: `systems` block (`{profile, features, status, session, errors?}`).
- **Tests (new):** `test_memory_writer.py`, `test_save_vault.py`, `test_sandbox_session.py`; `test_disk.py` safety test rewritten.
- **Docs:** README, `cli-commands.md`, `cli-commands-exe.md`, spec/plan/changes 1.6.0.

## Verification Plan
1. `python -m pytest` (145 tests).
2. On Windows, on a **copy** of the save: spec tests T1-T9, T11 (`--save-dir`, `--vault` overrides).
3. T10 Steam Cloud dry run on a throwaway save; record the result in the README.
4. `python -m eldendisk build -c -em`, then `eldendisk.exe sandbox status`.

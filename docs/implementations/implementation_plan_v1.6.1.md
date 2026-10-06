# Implementation Plan v1.6.1

See [changes-version-1.6.1.md](../wahy/changes-version-1.6.1.md) and [elden-disk-spec-v1.6.1.md](../specs/elden-disk-spec-v1.6.1.md).

## Proposed Changes
- **[MODIFY] `__main__.py`**: `EXIT_NO_SESSION = 5`; `cmd_sandbox_edit` checks the marker and exe hash before opening a write handle and reports unapplied edits; `_run_loop(args, sandbox=)` / `cmd_run(args, sandbox=)` read-only; `_writer_api` removed; `sandbox` parser trimmed; subcommand `--vault` uses `default=SUPPRESS`; `--write-hz` validation removed.
- **[MODIFY] `sandbox.py`**: no `WriteGate`; `Hooks.run_game: Callable[[], int]`.
- **[MODIFY] `memory_writer.py`**: `MemoryWriter.skipped`; docstring for the client-only handle.
- **[MODIFY] `save_vault.py`**: registry helpers without test-specific filters.
- **Tests:** new `test_sandbox_edit.py`, new `conftest.py`; `test_sandbox_session.py` and `test_disk.py` (safety test) updated.
- **Docs:** README, `cli-commands.md`, `cli-commands-exe.md`, spec/plan/changes 1.6.1.

## Verification Plan
1. `python -m pytest` (154 tests).
2. On Windows, on a **copy** of the save: `run`, then `sandbox --set level=150 -v` in a second terminal; close the game and confirm the byte-identical restore. Then try `sandbox --set level=150` with no `run` (expect exit 5 and no change).
3. `sandbox --vault <custom> status` / `restore` with a custom vault (expect the custom vault to be used).
4. T10 Steam Cloud dry run on a throwaway save; record the result in the README.
5. `python -m eldendisk build -c -em`, then `eldendisk.exe sandbox status`.

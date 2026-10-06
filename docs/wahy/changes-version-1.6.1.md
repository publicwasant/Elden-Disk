> [!NOTE]
> **Version:** `1.6.1`  
> **Status:** IMPLEMENTED (real-game verification still open, see spec 1.6.1 section 5)  
> **Last Updated:** _2026-10-06_

**Summary:** One tool instead of two processes. `run` is the only host (telemetry + save guard, read-only); `sandbox --set/--refill` is a small client for the running session. This release makes code, tests and docs follow that design and fixes the findings of the 1.6.0 review.

_(baseline: **[changes-version-1.6.0.md](changes-version-1.6.0.md)** and **[elden-disk-spec-v1.6.0.md](../specs/elden-disk-spec-v1.6.0.md)**)_

---

## Wahy

| # | Change | Where |
|:-:|:---|:---|
| 1 | **`sandbox` edits need a session.** `cmd_sandbox_edit` reads the vault marker first; no marker, unreadable marker, or an `eldenring.exe` whose hash differs from the marker's gives exit `5` and no write handle is opened. | `__main__.py` |
| 2 | **`--vault` survives a subcommand.** Subcommands declare it with `default=SUPPRESS`; `sandbox --vault V restore/status/list/verify/prune` now uses V (before, the default vault was used silently). | `__main__.py` |
| 3 | **Host is read-only.** `run` always uses `ProcessMemory`; `SandboxSession` no longer owns a `WriteGate`; `_run_loop(args, sandbox=)` / `cmd_run(args, sandbox=)` replace `gate`/`policy`; the unused writer path and `_writer_api` are gone. | `__main__.py`, `sandbox.py` |
| 4 | **No silent success.** An edit that cannot be applied (not in a world, unreadable field, write did not stick) prints an error and exits `1` even without `-v` (`MemoryWriter.skipped`). | `memory_writer.py`, `__main__.py` |
| 5 | **Client CLI trimmed to what it uses.** `sandbox` keeps `--vault --set --refill --offsets --effects -v`. Removed from it: `--write-hz` (never used, edits are applied once), `--hz`, `--out`, `--timer-interval`, `--no-idle`, `--game-dir`, `--save-dir` and `--archive-contaminated` (the last two stay on `sandbox restore`). | `__main__.py` |
| 6 | **Validation fixed.** The misplaced `--write-hz` check (dead code under `if cmd == "run"`) is removed together with the flag. | `__main__.py` |
| 7 | **Registry code without test hacks.** `PYTEST_CURRENT_TEST` and the "tmp"/"temp" path filters are gone from `save_vault.py`; `tests/conftest.py` stubs the registry for all tests. | `save_vault.py`, tests |
| 8 | **Tests.** `test_sandbox_edit.py` (9 tests: marker, exe hash, EAC, title screen, handle closed, `--vault` order); session and `cmd_run` tests updated; the safety test also asserts that only the client opens a write handle. 154 tests. | tests |
| 9 | **Docs aligned.** README, `cli-commands*.md`, spec and plan 1.6.1; Steam Cloud caveat in the README; "100% clean" wording removed until T10 is done. | docs |

## Behaviour changes

- `session.read_only` in `disk-state.json` is now always `true` (it describes `run`); `session.mode: "sandbox"` and `session.sandbox: true` still mark a save-guarded run.
- `sandbox` without a running `run` session now fails with exit `5` instead of writing.
- `sandbox --write-hz`, `--hz`, `--out`, `--timer-interval`, `--no-idle`, `--game-dir` are rejected (they never did anything there).
- Exit code `5` = no active sandbox session.

## Decisions taken while implementing

- The marker is the authorisation, not a process id: it exists exactly when a snapshot exists that `sandbox restore` can roll back to, which is the property that matters. After a crash the marker stays, so edits remain covered until `sandbox restore` is run.
- `MemoryWriter` keeps its rate limiter and `hold` loop (`tick`) as a library feature with its tests; the CLI uses `apply_once` only.
- `_wait_game_exit` still returns only when the game is gone (no timeout, second Ctrl+C postpones), so the `not gone` branch of the session only matters for other hook implementations.

## Not done / open

- **T10 Steam Cloud, A1-A6 and T1-T5 against the real game, real `WriteProcessMemory` on 1.17.1:** not run. Keep Steam Cloud off and use a copy of the save first.
- Settings or other files outside the save folder are not part of the snapshot.

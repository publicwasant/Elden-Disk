# EldenDisk Telemetry Tool
> **Document Version:** 1.6.1 (revised from 1.6.0)
> **Date of Issue:** 2026-10-04
> **Target Platform:** Windows 10 / 11 (x64), Python 3.11+ (64-bit) · **Game:** Elden Ring 1.17.1

Implementation spec for **Save Sandbox Mode** as one tool: `run` is the host (telemetry + save guard, read-only), `sandbox --set/--refill` is a small client that edits the running session. (1.6.0 described a separate `sandbox start` process; it was dropped.) The design, rationale and requirement IDs (G, FR, MW, NFR, SC, GF, T) are in **[save_sandbox_spec.md](../experiments/sandbox/save_sandbox_spec.md)**; this document records how 1.6.1 realises them. Everything else is as in [1.6.0](elden-disk-spec-v1.6.0.md) and [1.5.2](elden-disk-spec-v1.5.2.md).

## 1. Components
| Spec component | Module | Notes |
|:---|:---|:---|
| SaveVault | `save_vault.py` | snapshot, manifest, marker, restore, verify, archive, list, prune, `SessionLog`, `find_save_dir` |
| SessionManager | `sandbox.py` | `SandboxSession` (driven by `run`) and `restore_pending` (FR-9/10) |
| GameLauncher | `game_launcher.py`, `__main__.py` | offline launch (unchanged), `GameFolderGuard`, `anticheat_processes`, `_wait_game_exit` |
| MemoryWriter | `memory_writer.py` | `WritableProcessMemory`, `WriteGate`, `EditPolicy`, `MemoryWriter`; used only by `cmd_sandbox_edit` |

## 2. Requirement map
| ID | Where |
|:---|:---|
| FR-1 | `SaveVault.preflight` (marker, vault writable, 3x free space, no overlap, save folder valid) + `SandboxSession.preflight` (game not running, no anti-cheat, profile for this exe) + `find_save_dir` (exactly one) |
| FR-2 | `anticheat_processes` at preflight; `run` stops on EAC modules (at start and on the 2 s re-scan); `sandbox` refuses to write when EAC modules are loaded |
| FR-3 | `SaveVault.snapshot` (copy2 keeps mtimes, SHA-256 of source and copy, re-hash of source to detect changes during copy) |
| FR-4 | `write_marker` only after `snapshot` returned; marker holds snapshot dir, live dir, hashes, game dir, created game files, exe hash |
| FR-5 | `cmd_run(args, sandbox=True)` (called by `SandboxSession`); read handle only. Edits are made by `cmd_sandbox_edit` |
| FR-6 | `_wait_game_exit` (no `eldenring.exe` process, then 1 s grace) |
| FR-7 | `SaveVault.restore` (deletes files not in manifest, copies back via temp + `os.replace`, bounded retry with backoff, 30 s) |
| FR-8 | `verify_live`; marker removed only when empty problem list |
| FR-9 / FR-10 | preflight refuses with a marker; `sandbox restore` = `restore_pending` |
| FR-11 | `GameFolderGuard` records before creating and persists to the marker; cleanup also in `restore_pending` |
| FR-12 | no automatic deletion; `prune` explicit and refused with a marker |
| FR-13 | `--archive-contaminated` |
| FR-14 | `cmd_sandbox_edit` opens the `WriteGate` only after it found a readable restore marker (a `run` session exists), the running exe hash matches the marker's, no EAC module is loaded and a profile matches |
| MW-1 | `WritableProcessMemory` is created inside `cmd_sandbox_edit` only, per command, and closed in `finally`; `run` / `effects` / `animations` use `ProcessMemory` |
| MW-2 | `MemoryWriter.tick` calls `locate_game_data` / `locate_vitals` each time |
| MW-3 | null/invalid pointer or unreadable field: skipped, logged once per transition |
| MW-4 | only stored values and current vitals; vitals block validated by `parse_vitals_block` |
| MW-5 | rate limit inside `MemoryWriter` (library use; the CLI applies once), per-field clamping (`level` 1-713, `runes` 0-999,999,999, attributes 1-99, hp 1..max, fp/stamina 0..max) |
| MW-6 | profile loaded from the exe hash; no profile = preflight refusal |
| NFR-3 | ordering: snapshot verified > marker > launch; marker cleared only after verification |
| NFR-4 | `session.log` in the snapshot directory (timestamps, decisions, verification result) |
| SC-3 | warning printed at every session start; SC-1 **not done** |

## 3. Behaviour details
- **States:** `IDLE, PREFLIGHT, SNAPSHOTTING, RUNNING, RESTORING, VERIFYING, CLEANUP, RESTORE_PENDING`. Failure before the marker: back to `IDLE`, snapshot discarded. After the marker: `RESTORE_PENDING` (exit 4), marker and snapshot kept.
- **Interrupts:** Ctrl+C in RUNNING waits for the game to exit, then restores. A second Ctrl+C while waiting leaves `RESTORE_PENDING`. An exception in the run phase still restores.
- **Damaged snapshot:** restore verifies the snapshot against its manifest first and refuses to touch the live folder if it differs.
- **Folder sanity:** restore deletes files not in the manifest, so `check_live_dir` refuses drive roots, the home folder and empty folders.
- **`systems`:** structured block in `disk-state.json` (`{profile, features, status, session, errors?}`); `session.sandbox: true` while `run` is inside a save-guarded session. `session.read_only` describes this process and is always `true`: the write handle belongs to the short-lived `sandbox` client.
- **`sandbox --set/--refill`:** applied once and the command exits. `0` applied or already equal, `1` not applied (not in a world, field unreadable, write did not stick), `3` EAC, `5` no session (no marker, unreadable marker, or a different `eldenring.exe` than the snapshot's). Without `--set`/`--refill` it does nothing.
- **Options:** `--vault` is declared on `sandbox` and is kept when given before a subcommand (`sandbox --vault V restore`); subcommands only override it when they receive their own.
- **Exit codes added:** `4` restore pending, `5` no active sandbox session.

## 4. Marker (`PENDING_RESTORE.json`, version 1)
Spec 11.2 plus `game_dir`.

## 5. Verification status
| Test | Status |
|:---|:---|
| T6, T7, T8, T9 and crash/interrupt paths (T4, T5 equivalents), T11 (guard), FR/MW unit behaviour | **Automated** (`pytest`, 154 tests; fake filesystem/memory layers) |
| `cmd_run` in a sandbox session (read handle only, EAC stops it, `session` object) and `cmd_sandbox_edit` (marker required, exe hash, EAC, title screen, handle closed) | Automated with a fake Win32 layer |
| T1, T2, T3, T4, T5 against the real game | **Manual, not yet run** |
| T10 Steam Cloud, assumptions A1-A6 | **Manual, not yet run** (README tells users to disable Steam Cloud meanwhile) |
| Real `WriteProcessMemory` on `eldenring.exe` 1.17.1 | **Not yet run** |

Release criterion from the design: T1-T9 and T11 pass and T10 has a documented answer. The automated part is met; the real-game part is open.

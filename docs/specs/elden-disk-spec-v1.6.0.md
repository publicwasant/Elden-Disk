# EldenDisk Telemetry Tool
> **Document Version:** 1.6.0 (revised from 1.5.2)
> **Date of Issue:** 2026-10-04
> **Target Platform:** Windows 10 / 11 (x64), Python 3.11+ (64-bit) · **Game:** Elden Ring 1.17.1

Implementation spec for **Save Sandbox Mode**. The design, rationale and requirement IDs (G, FR, MW, NFR, SC, GF, T) are in **[save_sandbox_spec.md](../experiments/sandbox/save_sandbox_spec.md)**; this document records how 1.6.0 realises them. Everything else is as in [1.5.2](elden-disk-spec-v1.5.2.md).

## 1. Components
| Spec component | Module | Notes |
|:---|:---|:---|
| SaveVault | `save_vault.py` | snapshot, manifest, marker, restore, verify, archive, list, prune, `SessionLog`, `find_save_dir` |
| SessionManager | `sandbox.py` | `SandboxSession` (start) and `restore_pending` (FR-9/10) |
| GameLauncher | `game_launcher.py`, `__main__.py` | offline launch (unchanged), `GameFolderGuard`, `anticheat_processes`, `_wait_game_exit` |
| MemoryWriter | `memory_writer.py` | `WritableProcessMemory`, `WriteGate`, `EditPolicy`, `MemoryWriter` |

## 2. Requirement map
| ID | Where |
|:---|:---|
| FR-1 | `SaveVault.preflight` (marker, vault writable, 3x free space, no overlap, save folder valid) + `SandboxSession.preflight` (game not running, no anti-cheat, profile for this exe) + `find_save_dir` (exactly one) |
| FR-2 | `anticheat_processes` at preflight; `cmd_run` closes the gate on EAC modules (at start and on the 2 s re-scan) |
| FR-3 | `SaveVault.snapshot` (copy2 keeps mtimes, SHA-256 of source and copy, re-hash of source to detect changes during copy) |
| FR-4 | `write_marker` only after `snapshot` returned; marker holds snapshot dir, live dir, hashes, game dir, created game files, exe hash |
| FR-5 | `cmd_run(args, gate, policy)` with a write handle |
| FR-6 | `_wait_game_exit` (no `eldenring.exe` process, then 1 s grace) |
| FR-7 | `SaveVault.restore` (deletes files not in manifest, copies back via temp + `os.replace`, bounded retry with backoff, 30 s) |
| FR-8 | `verify_live`; marker removed only when empty problem list |
| FR-9 / FR-10 | preflight refuses with a marker; `sandbox restore` = `restore_pending` |
| FR-11 | `GameFolderGuard` records before creating and persists to the marker; cleanup also in `restore_pending` |
| FR-12 | no automatic deletion; `prune` explicit and refused with a marker |
| FR-13 | `--archive-contaminated` |
| FR-14 | `WriteGate` opened by `SandboxSession` in RUNNING, closed in `finally` |
| MW-1 | `WritableProcessMemory` is created inside `cmd_run` only when a gate is passed |
| MW-2 | `MemoryWriter.tick` calls `locate_game_data` / `locate_vitals` each time |
| MW-3 | null/invalid pointer or unreadable field: skipped, logged once per transition |
| MW-4 | only stored values and current vitals; vitals block validated by `parse_vitals_block` |
| MW-5 | `--write-hz` 1-30, per-field clamping (`level` 1-713, `runes` 0-999,999,999, attributes 1-99, hp 1..max, fp/stamina 0..max) |
| MW-6 | profile loaded from the exe hash; no profile = preflight refusal |
| NFR-3 | ordering: snapshot verified > marker > launch; marker cleared only after verification |
| NFR-4 | `session.log` in the snapshot directory (timestamps, decisions, verification result) |
| SC-3 | warning printed at every session start; SC-1 **not done** |

## 3. Behaviour details
- **States:** `IDLE, PREFLIGHT, SNAPSHOTTING, RUNNING, RESTORING, VERIFYING, CLEANUP, RESTORE_PENDING`. Failure before the marker: back to `IDLE`, snapshot discarded. After the marker: `RESTORE_PENDING` (exit 4), marker and snapshot kept.
- **Interrupts:** Ctrl+C in RUNNING waits for the game to exit, then restores. A second Ctrl+C while waiting leaves `RESTORE_PENDING`. An exception in the run phase still restores.
- **Damaged snapshot:** restore verifies the snapshot against its manifest first and refuses to touch the live folder if it differs.
- **Folder sanity:** restore deletes files not in the manifest, so `check_live_dir` refuses drive roots, the home folder and empty folders.
- **`systems`:** structured block in `disk-state.json` (`{profile, features, status, session, errors?}`); `session.read_only: false` and `session.sandbox: true` only while a sandbox session holds a write handle.
- **Exit codes added:** `4` restore pending.

## 4. Marker (`PENDING_RESTORE.json`, version 1)
Spec 11.2 plus `game_dir`.

## 5. Verification status
| Test | Status |
|:---|:---|
| T6, T7, T8, T9 and crash/interrupt paths (T4, T5 equivalents), T11 (guard), FR/MW unit behaviour | **Automated** (`pytest`, 145 tests; fake filesystem/memory layers) |
| `cmd_run` with a gate (writes through the write handle, EAC closes the gate, `session` object) | Automated with a fake Win32 layer |
| T1, T2, T3, T4, T5 against the real game | **Manual, not yet run** |
| T10 Steam Cloud, assumptions A1-A6 | **Manual, not yet run** (README tells users to disable Steam Cloud meanwhile) |
| Real `WriteProcessMemory` on `eldenring.exe` 1.17.1 | **Not yet run** |

Release criterion from the design: T1-T9 and T11 pass and T10 has a documented answer. The automated part is met; the real-game part is open.

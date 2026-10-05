> [!NOTE]
> **Version:** `1.6.0`  
> **Status:** IMPLEMENTED (needs real-game verification, see spec section 9)  
> **Last Updated:** _2026-10-04_

**Summary:** From read-only telemetry to **read + write**. Adds the Save Sandbox described in **[save_sandbox_spec.md](../experiments/sandbox/save_sandbox_spec.md)**: memory edits are allowed only inside a session that snapshots the save folder first and restores and verifies it afterwards.

_(baseline: **[changes-version-1.5.2.md](changes-version-1.5.2.md)** and **[elden-disk-spec-v1.5.2.md](../specs/elden-disk-spec-v1.5.2.md)**)_

---

## Wahy

| # | Change | Where |
|:-:|:---|:---|
| 1 | **`sandbox` command group**: `start`, `restore`, `status`, `list`, `verify`, `prune`. | `__main__.py` |
| 2 | **SaveVault** (snapshot, SHA-256 manifest, marker, restore with bounded lock retry, verify, archive, prune). The only component that touches save files; pure filesystem. | `save_vault.py` |
| 3 | **SandboxSession** state machine `IDLE > PREFLIGHT > SNAPSHOTTING > RUNNING > RESTORING > VERIFYING > CLEANUP`, plus the stable `RESTORE_PENDING`. Restore runs on every exit path; marker ordering per spec 8.2. | `sandbox.py` |
| 4 | **MemoryWriter + WriteGate**: write handle only in a session, gate open only in RUNNING, pointers re-resolved on every write, clamped values, rate-limited, null/invalid pointer = skip. Fields: `level`, `runes`, 8 attributes, current `hp`/`fp`/`stamina`. | `memory_writer.py` |
| 5 | **Game-folder hygiene**: `GameFolderGuard` (record-then-create, cleanup, listing diff) and anti-cheat process detection. | `game_launcher.py`, `memory_reader.py` |
| 6 | **`systems` block introduced in `disk-state.json`**: replaces flat `system_status` with `systems: {profile, features, status, session, errors?}` (`features: {effects_supported, animations_supported, sandbox_supported}`, `status.ignoreds: {effects, animations}`, `errors` appended only when present). Schema and `soak_check.py` updated. | `disk.py`, schema |
| 7 | **Refactors for the writer**: `Sampler.locate_game_data()`, `locate_vitals()`, `vitals_address()`, `parse_vitals_block()`. | `disk.py` |
| 8 | **Safety test rewritten**: `WriteProcessMemory` may appear only in `memory_writer.py`, which only `sandbox` / `__main__` (lazily) may import; `memory_reader.ACCESS_MASK` is still `0x1010`. | tests |

## Behaviour changes

- `system_status` is replaced by structured `systems` (`{profile, features, status, session, errors?}`).
- The README's "zero memory writes" guarantee now applies to `effects` and `animations`; writes exist only in `sandbox` edits.

## Decisions taken while implementing the spec

- Edits come from `--set` / `--refill` (held at a bounded rate). No interactive editor and no edit file in 1.6.0.
- The vault defaults to `<tool-root>/backup/vault` (relative to tool directory: `code/backup/vault` in dev mode, `<dist>/backup/vault` for standalone exe); override with `--vault`.
- Marker gains `game_dir` (needed to clean the game folder in crash recovery). Everything else follows spec 11.2.
- `restore --snapshot NAME` first keeps the current save as `<ts>-pre-restore`.
- No `--attach` for sandbox: FR-1 requires the game not to be running, so the tool always launches it offline itself.
- A restore never starts from a snapshot whose hashes do not match its manifest.

## Not done / open (spec sections 9, 14, 16)

- **T10 Steam Cloud dry run, A1-A6 verification and T1-T9, T11 against the real game** have not been run. Recommendation until then: Steam Cloud off, first runs on a copy of the save.
- Settings or other files outside the save folder (spec Q4) are not part of the snapshot.

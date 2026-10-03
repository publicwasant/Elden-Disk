# Save Sandbox Mode: Specification

| | |
|---|---|
| Project | Elden-Disk (formerly Elden-Ring-Telemetry-Tools; offline, Python) |
| Document | Functional and technical specification, draft 0.1 |
| Date | 2026-10-04 |
| Target game build | Elden Ring 1.17.1 |
| Status | Design only. No sandbox code exists yet. |

---

## 1. Purpose

Elden-Disk can already read live game state (level, runes, attributes, SpEffects, animation ID, and therefore "resting at a Site of Grace"). Because it can read process memory, it can also write to it, which makes experiments possible: raising level and stats, changing HP/FP/stamina, testing builds.

The problem is persistence. Anything written into memory can be saved into the character's save file by the game's own autosave or on quit. A player who experiments on their real character risks bringing those changes back into normal Steam play.

**Save Sandbox Mode** removes that risk. A session is a self-contained excursion:

> Take the real character into a parallel "dimension", change anything there, and when the session ends, nothing from that dimension comes back.

## 2. The concept in one picture

```
   REAL WORLD (normal Steam play)                 SANDBOX DIMENSION (tool session)
   ------------------------------                 --------------------------------
   save files as they are today
              |
              |  1. snapshot (copy + hash)
              v
        [ snapshot vault ]  ---------------------> 2. game launched offline through the tool
              ^                                       memory edits allowed
              |                                       game autosaves into the live save folder
              |                                       (the live save is now "contaminated")
              |  4. restore originals,                |
              |     verify hashes                     |  3. game exits
              +---------------------------------------+
   save files identical to step 0,
   byte for byte
```

The sandbox never tries to undo individual edits. It does not need to know what was changed. It guarantees one thing only: **the save folder after the session is byte-identical to the save folder before it.**

## 3. Goals and non-goals

### Goals

| ID | Goal |
|---|---|
| G1 | After any session, the save folder is byte-identical to its state before the session. |
| G2 | The game installation folder is left exactly as found. |
| G3 | The guarantee holds when the tool crashes, the game crashes, the machine loses power, or the user kills processes. |
| G4 | The original save can never be lost by the tool itself (no destructive overwrite of backups). |
| G5 | The session never touches the online experience: offline only, with explicit guards. |
| G6 | Simple to use: one command starts a session and the rest is automatic. |

### Non-goals

- Merging anything from the sandbox session back into the real save (no "keep my changes" path in v1).
- Editing save files directly (this is a memory tool, not a save editor).
- Defeating, bypassing or hiding from anti-cheat. The tool is for offline use only.
- Supporting multiple simultaneous games or multiple save slots with different policies.
- Cloud backup of snapshots.

## 4. Definitions

| Term | Meaning |
|---|---|
| Live save folder | The directory the game reads and writes saves in. Expected to be `%APPDATA%\EldenRing\<SteamID64>\`, containing `ER0000.sl2` and `ER0000.sl2.bak` (to be confirmed on the target machine). |
| Snapshot | A full copy of the live save folder plus a manifest of SHA-256 hashes, taken before a session. |
| Vault | The directory that holds all snapshots, on a drive other than C:. |
| Session | The period from snapshot to verified restore. |
| Marker | A small file that exists only while a session is unresolved. Its presence means "the live save folder cannot be trusted." |
| Contaminated | The state of the live save folder from the moment the game may write to it until restore is verified. |

## 5. Assumptions (to be verified, not facts)

| ID | Assumption | How to verify |
|---|---|---|
| A1 | Values written to game memory can be persisted by the game into the save files via autosave or quit. | Dry run: write level via the tool, quit, compare hashes of the save folder. |
| A2 | The save folder consists of a small set of top-level files. | List the folder on the target machine. |
| A3 | The game does not hold the save files open after the process exits. | Restore immediately after exit and watch for locking errors. |
| A4 | Launching the game offline through the tool does not trigger a Steam Cloud upload of the modified save. | See section 9, the highest-risk item. |
| A5 | There is exactly one `<SteamID64>` folder with a save. | Enumerate on startup (the tool refuses to guess if there are several). |
| A6 | The existing offline launch method does not require modifying the game folder, or requires only files the tool can create and remove. | Inspect the current launch procedure. |

If any assumption fails, the affected requirement must be revisited before release.

## 6. Requirements

### 6.1 Functional requirements

| ID | Requirement |
|---|---|
| FR-1 | **Preflight.** Before a session starts, the tool must confirm that the game process is not running, no marker exists, the vault is writable and has enough free space (at least 3x the size of the save folder), and exactly one save folder is found. |
| FR-2 | **Offline guard.** The tool must refuse to start a session, or to write memory, if anti-cheat processes are running or if the game was not started through the tool's offline procedure. (Exact process names to be determined.) |
| FR-3 | **Snapshot.** Copy every file in the live save folder into a new timestamped vault directory, preserving modification times, and compute a SHA-256 for each file. |
| FR-4 | **Marker.** Write the marker only after the snapshot has been fully written and verified. The marker records the snapshot path, the live save path, and the hash manifest. |
| FR-5 | **Launch and attach.** Start (or attach to) the game using the existing offline procedure and attach the telemetry/write layer. |
| FR-6 | **Wait for exit.** Detect that the game process has fully exited. Restoration must not begin while the process exists. |
| FR-7 | **Restore.** Delete any file in the live save folder that is not in the manifest, copy every snapshot file back with timestamps preserved, retrying on file-lock errors for a bounded time. |
| FR-8 | **Verify.** After restore, recompute hashes of the live save folder and compare to the manifest. Remove the marker only if every hash matches and no extra files exist. |
| FR-9 | **Crash recovery.** If a marker exists at startup, the tool must refuse to begin a new session and offer `restore` (see 8.3). |
| FR-10 | **Standalone restore.** A command that performs FR-7 and FR-8 using the marker, usable without launching anything. |
| FR-11 | **Game folder hygiene.** Any file the tool places in the game installation folder must be recorded and removed at session end, including after a crash (cleanup is part of recovery). |
| FR-12 | **Retention.** Snapshots are never deleted automatically while a marker refers to them. Optionally keep the last N verified snapshots; deletion of older ones is explicit. |
| FR-13 | **Contaminated-save archive (optional).** Before restoring, optionally archive the contaminated save into the vault for inspection. It is never restored. |
| FR-14 | **Memory writes are gated.** Write operations are only enabled while a session is in the RUNNING state. |

### 6.2 Memory-write requirements

| ID | Requirement |
|---|---|
| MW-1 | Open the process with write rights only for the duration of a session; use read-only rights otherwise. |
| MW-2 | Resolve the pointer chain from the module base on every write. Cached addresses are not allowed, because player structures are recreated on map load and death. |
| MW-3 | Treat null or invalid pointers as "skip this write", never as an error that crashes the game. |
| MW-4 | Write only fields that have been verified to be current values (e.g. current HP, not a derived maximum). The game recomputes derived values and may overwrite them. |
| MW-5 | Writes that must persist are applied in a loop at a bounded rate and clamped to sane ranges. |
| MW-6 | Offsets come only from the profile in `offsets.json` matching the SHA-256 of the running `eldenring.exe`. Unknown hash means no writes. |

### 6.3 Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | **Safety over speed.** A slow, careful restore is acceptable; a lost save is not. |
| NFR-2 | **Idempotence.** Running restore twice, or after a successful restore, is harmless. |
| NFR-3 | **Atomicity of intent.** At every moment, either no marker exists (live save trusted) or a marker exists together with a complete snapshot. There is no state where the marker exists without a snapshot, or where the live save is contaminated without a marker. |
| NFR-4 | **Observability.** Every step is logged with timestamps to a session log in the vault, including hashes and decisions. |
| NFR-5 | **Windows-first.** Target is Windows with Python; no assumptions about other platforms. |
| NFR-6 | **Minimal dependencies.** Standard library plus what the tool already uses. |

## 7. Architecture

Four small components, each with one responsibility.

```
+------------------+     +------------------+     +------------------+
|  SessionManager  |---->|   SaveVault      |     |  GameLauncher    |
|  state machine,  |     |  snapshot,       |     |  offline start,  |
|  orchestration   |     |  restore, verify,|     |  process watch,  |
|                  |---->|  marker          |     |  game-folder     |
|                  |     +------------------+     |  hygiene         |
|                  |------------------------------>                  |
|                  |     +------------------+     +------------------+
|                  |---->|  MemoryWriter    |
+------------------+     |  gated writes,   |
                         |  pointer resolve |
                         +------------------+
```

| Component | Responsibility | Must not |
|---|---|---|
| SessionManager | Owns the lifecycle in section 8, calls the other components in order, guarantees restore runs in a `finally` path. | Touch files or memory directly. |
| SaveVault | Snapshot, marker, restore, verify, retention. The only component that touches save files. | Know anything about the game process. |
| GameLauncher | Offline start, process monitoring, exit detection, creating and removing temporary files in the game folder. | Touch save files. |
| MemoryWriter | Gated, validated writes using the existing profile and pointer-chain reader. | Run outside the RUNNING state. |

Keeping the save logic isolated in SaveVault matters: it is small enough to test thoroughly, and it is the one part where a bug can lose data.

## 8. Session lifecycle

### 8.1 States

```
 IDLE
   |  start
   v
 PREFLIGHT ----fail----> IDLE (nothing changed)
   |  ok
   v
 SNAPSHOTTING ---fail---> IDLE (snapshot discarded, no marker written)
   |  snapshot verified, marker written
   v
 RUNNING  <-- memory writes allowed only here
   |  game process exited (or tool interrupted)
   v
 RESTORING ---fail---> RESTORE_PENDING (marker stays)
   |  files copied
   v
 VERIFYING ---fail---> RESTORE_PENDING (marker stays)
   |  all hashes match
   v
 CLEANUP (remove marker, game-folder temp files)
   |
   v
 IDLE
```

`RESTORE_PENDING` is a stable state: the tool refuses new sessions, reports what is wrong and offers `restore` again. Nothing is deleted from the vault in this state.

### 8.2 Ordering guarantees

1. The snapshot is complete and hash-verified **before** the marker is written.
2. The marker is written **before** the game is launched.
3. The marker is removed **only after** verification succeeds.

These three rules give NFR-3: the live save is only ever at risk while a marker and a valid snapshot both exist.

### 8.3 Crash and interruption handling

| Event | Outcome |
|---|---|
| Tool exits normally or via exception | The restore path runs in `finally`. |
| User presses Ctrl+C | Same as above; restore waits for the game to exit if it is still running. |
| Tool process killed or machine loses power | Marker remains. Next start detects it, refuses a new session, and runs or offers `restore`. |
| Game crashes | Process exit is detected; restore proceeds normally. |
| Game still running when restore is requested | Restore is refused with a clear message; the tool waits or asks the user to close the game. |
| Restore hits file locks | Retry with bounded backoff (for example up to 30 seconds); if it still fails, enter RESTORE_PENDING. |
| Hash mismatch after restore | Do not remove the marker; keep the snapshot; report which file differs. |

## 9. Steam Cloud: the main open risk

Elden Ring is expected to use Steam Cloud. The danger scenario:

```
 session ends -> Steam syncs the CONTAMINATED save to the cloud
              -> tool restores the original local save
              -> next normal launch: Steam sees "cloud is newer" and pulls the contaminated save back
```

Whether Steam syncs at the end of a session depends on how the game is started, which this specification does not yet know. Therefore:

| ID | Requirement |
|---|---|
| SC-1 | Before the first real use, determine empirically whether a sandbox session causes a cloud upload (use a throwaway copy of the save and a dry run). |
| SC-2 | Until SC-1 is answered, document and recommend turning off Steam Cloud for the game while the sandbox is in use. |
| SC-3 | The tool should warn at session start that Steam Cloud status is unknown or enabled. It cannot reliably read the setting, so this is a user-facing reminder, not an automated check. |
| SC-4 | Because snapshots are kept locally, a wrongly synced cloud save is recoverable by restoring the snapshot and resolving the Steam conflict in favour of the local file. Snapshots are therefore the last line of defence and must be retained. |

## 10. Game folder hygiene

Memory edits do not modify the game executable or its data files. The only possible footprint in the game folder comes from the launch method (for example a helper file needed to start the game outside the normal launcher).

| ID | Requirement |
|---|---|
| GF-1 | The tool keeps a list of every file it creates in the game folder, stored in the marker, so cleanup can happen even after a crash. |
| GF-2 | At session end (or in recovery) those files are removed and the folder is compared against a pre-session listing of names and sizes. |
| GF-3 | The tool never modifies or deletes pre-existing game files. |

## 11. Data model

### 11.1 Vault layout

```
D:\ER_SaveBackups\
  PENDING_RESTORE.json              (exists only while a session is unresolved)
  20261004-213015\                  (one directory per session)
    save\                           (copy of the live save folder)
      ER0000.sl2
      ER0000.sl2.bak
    manifest.json
    session.log
    contaminated\                   (optional archive, FR-13)
```

### 11.2 Marker (`PENDING_RESTORE.json`)

```json
{
  "version": 1,
  "created": "2026-10-04T21:30:15+07:00",
  "snapshot_dir": "D:\\ER_SaveBackups\\20261004-213015",
  "live_save_dir": "C:\\Users\\<user>\\AppData\\Roaming\\EldenRing\\<SteamID64>",
  "hashes": { "ER0000.sl2": "<sha256>", "ER0000.sl2.bak": "<sha256>" },
  "game_folder_files_created": [],
  "exe_sha256": "<sha256 of eldenring.exe>"
}
```

### 11.3 Manifest

Same hash map as the marker, plus file sizes and modification times, kept inside the snapshot directory so a snapshot is self-describing even if the marker is lost.

## 12. Command-line surface

| Command | Behaviour |
|---|---|
| `sandbox start` | Preflight, snapshot, launch, attach, wait, restore, verify, cleanup. |
| `sandbox restore` | Restore from the marker (or from a named snapshot) and verify. Safe to run repeatedly. |
| `sandbox status` | Report marker presence, last snapshot, vault size and the verification result. |
| `sandbox list` | List snapshots with date, size and whether they are verified. |
| `sandbox verify <snapshot>` | Re-hash a snapshot against its manifest. |
| `sandbox prune --keep N` | Explicitly delete old snapshots (refuses if a marker exists). |

## 13. Safety rules

1. **Offline only.** The sandbox exists for offline experiments. Writes are disabled if anti-cheat is detected, and the documentation must state clearly that going online while attached is not supported and risks account action.
2. **Never trust the live save while a marker exists.**
3. **Never delete a snapshot that a marker references.**
4. **Never write memory outside RUNNING.**
5. **Never guess** which save folder to use; if the folder count is not exactly one, stop.
6. **Fail closed.** On any uncertainty in preflight, do not start.

## 14. Test plan and acceptance criteria

| # | Test | Pass criterion |
|---|---|---|
| T1 | Dry run with no edits: start, play briefly, quit. | Hashes after restore equal hashes before. |
| T2 | Write level and stats via the tool, quit. | Contaminated save differs from the snapshot (proves A1); after restore, hashes equal the originals. |
| T3 | Normal Steam launch after T2. | Character shows original level and stats. |
| T4 | Kill the tool during RUNNING, then start again. | Marker detected; new session refused; `restore` succeeds. |
| T5 | Kill the game during RUNNING. | Exit detected; restore succeeds. |
| T6 | Power-loss simulation (kill all processes right after the marker is written). | Snapshot intact; `restore` succeeds. |
| T7 | Corrupt one restored file on purpose. | Verification fails; marker retained; clear error. |
| T8 | Try to start with the game already running. | Preflight refuses. |
| T9 | Run `restore` twice in a row. | Second run is a no-op. |
| T10 | Steam Cloud dry run on a throwaway save (SC-1). | Documented outcome: does the cloud receive the contaminated save or not. |
| T11 | Game folder listing before and after a session. | Identical. |

Release criterion: T1 to T9 and T11 pass, and T10 has a documented answer.

## 15. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Steam Cloud pulls the contaminated save back | Unknown | High | SC-1 to SC-4; disable cloud while testing; keep snapshots. |
| Restore attempted while the game still holds the files | Medium | Medium | Wait for process exit; bounded retries; RESTORE_PENDING state. |
| Snapshot overwritten or deleted by mistake | Low | Critical | Timestamped directories; marker blocks pruning; no automatic deletion. |
| Game structure changes with a patch | Medium | Medium | Profile keyed by exe hash; unknown hash means no writes. |
| User goes online while attached | Low | Critical | Offline guard; explicit documentation; refuse writes if anti-cheat is present. |
| Wrong save folder selected | Low | High | Exactly-one rule; no guessing. |
| Disk full during snapshot | Low | Medium | Free-space check; snapshot failure leaves no marker and no changes. |

## 16. Open questions

1. What exactly does the current offline launch procedure do, and does it place files in the game folder?
2. Does Steam attribute a tool-launched session to the game and therefore sync it (SC-1)?
3. Which anti-cheat process names should the offline guard look for?
4. Are there other files outside the save folder that the game writes and that matter (for example settings)? If so, should they be part of the snapshot?
5. Should a "keep last N snapshots" policy be on by default?

## 17. Suggested milestones

| Milestone | Content | Exit criterion |
|---|---|---|
| M1 | SaveVault: snapshot, marker, restore, verify, with tests T6 to T9. | Passes without launching the game. |
| M2 | SessionManager and GameLauncher integration; T1, T4, T5, T8. | Full start-to-restore flow on a throwaway save. |
| M3 | MemoryWriter gating and write policies (MW-1 to MW-6); T2, T3. | Edits visible in-game and gone after the session. |
| M4 | Steam Cloud investigation (T10) and documentation of the result. | Written conclusion in the README. |
| M5 | Hardening: logging, `status`/`list`/`prune`, game-folder hygiene (T11). | All release criteria met. |

## 18. Summary

The idea is simple to state and safe to build if one rule is respected: **the sandbox does not try to undo changes; it replaces the save folder with a verified copy of what it was.** Everything else in this document (marker ordering, crash recovery, verification, Steam Cloud handling) exists to make that one guarantee hold under failure.

# EldenDisk Memory I/O Tools
> **Document Version:** 1.6.2 (revised from 1.6.1) · **Status:** DRAFT for review
> **Date of Issue:** 2026-10-06
> **Target Platform:** Windows 10 / 11 (x64), Python 3.11+ (64-bit) · **Game:** Elden Ring 1.17.1

1.6.2 is a **foundation release**: no new game features. It splits the tool into four clearly bounded parts (host, vault, reader, writer), makes the save vault the one component that must never fail, and makes every write to the game depend on a verified session. Everything not mentioned here behaves as in [1.6.1](elden-disk-spec-v1.6.1.md).

## 1. Roles and commands

| Command | Role | Game memory | Needs a session |
|:---|:---|:---|:---|
| `run` | **Host.** preflight → snapshot → session record → offline launch → wait → restore → verify | never opens the game with memory access | creates it |
| `read <feature...>` | **Reader.** `effects`, `animations`, `export` | read-only | no (labels the export when one exists) |
| `write <feature>` | **Writer.** `set NAME=VALUE...`, `refill LIST` | read + write | **yes** |
| `vault status\|list\|verify\|restore\|prune` | vault tools | none | `restore` refused while the game runs |
| `build`, `hash` | tooling | none | no |

Changes of name: `sandbox --set/--refill` → `write set` / `write refill`; `sandbox restore|status|list|verify|prune` → `vault ...`; `effects` / `animations` → `read effects` / `read animations`. The old names are removed, no aliases. `run` no longer writes `disk-state.json`; that is `read export`.

Typical use: terminal 0 `eldendisk run`, terminal 1 `eldendisk read effects`, terminal 2 `eldendisk write set vigor=99`.

## 2. Modules and dependency rules

```
eldendisk/
  __main__.py      argparse and dispatch only
  paths.py         runtime dirs, resource lookup, default vault path          (from __main__)
  vault/           saves.py (find / check live save dir, registry)            (from save_vault)
                   vault.py (SaveVault: snapshot, restore, verify, prune)
                   session.py (SessionRecord, states, SessionLog)
  host/            host.py (lifecycle)                                        (from sandbox.py)
                   launcher.py (offline launch, GameFolderGuard, wait)        (from game_launcher)
  game/            processes.py (find_pid, process names, start time, window) (from memory_reader)
                   memory.py (read-only ProcessMemory, list_modules)
                   profile.py (offsets.json, chr_state_ids.json)              (from profile_loader)
                   layout.py (locate_game_data, locate_vitals, ranges)        (split out of disk.py)
                   attach.py (pid, base, exe hash, EAC check, profile)        (new, replaces 4 copies)
  reader/          sampler.py, effects.py, animations.py, export.py           (from disk, json_logger, __main__)
  writer/          writer.py (WritableProcessMemory, WriteGate, policy)       (from memory_writer)
tools/             dev_pipeline.py, soak_check.py (outside the package)
```

| Package | May import | Must not import |
|:---|:---|:---|
| `vault` | stdlib, `paths` | everything else |
| `host` | `vault`, `paths`, `game.processes` | `game.memory`, `reader`, `writer` |
| `reader` | `game`, `paths`, `vault.session` (read) | `writer`, `host` |
| `writer` | `game`, `vault.session` (check) | `reader`, `host` |

Why `game/layout.py`: today `memory_writer` imports `Sampler` from `disk.py` (the reader's module) only to locate the player data; the pointer-chain resolution moves to `layout.py` and both sides use it.

Enforced by `test_architecture.py` (AST over the imports of every module) plus the existing write-isolation test: `WriteProcessMemory` / `PROCESS_VM_WRITE` appear only in `writer/`, and `host` / `vault` never reference `ProcessMemory`.

## 3. Session record (`vault/session.py`)

One file in the vault, `session.json` (version 2), written atomically, present **iff a restore is owed**. It replaces `PENDING_RESTORE.json`; a version-1 marker found by `vault restore` is treated as `RESTORE_PENDING`.

| Field | Meaning |
|:---|:---|
| marker v1 fields | snapshot dir, live dir, hashes, game dir, created game files, exe hash |
| `state` | `READY` · `RUNNING` · `RESTORING` · `RESTORE_PENDING` |
| `snapshot_verified` | true once the snapshot matched its manifest (set before the record exists) |
| `host_pid`, `host_started` | the host process and its start time |
| `game_pid`, `game_started` | the game process and its start time (set at `RUNNING`) |

**Authorisation (writer, every command).** Allowed only when all hold, otherwise refuse with the list of reasons and exit `5`: record readable; `state == RUNNING`; `snapshot_verified`; attached process pid and start time equal `game_pid` / `game_started`; its exe hash equals the record's; the host process (`host_pid` + `host_started`) is alive. A record left behind by a dead host therefore authorises nothing.

**Reader.** Optional. When a valid `RUNNING` record exists, `systems.session` in the export is `{mode: "sandbox", sandbox: true}`, otherwise telemetry. `read_only` stays `true` (the reader never writes).

## 4. Host lifecycle

`H1` preflight (no record, vault writable, 3x free space, save folder valid, game not running, no anti-cheat process by name) → `H2` snapshot + verify → `H3` record `READY` → `H4` offline launch → `H5` game pid found, record `RUNNING` → `H6` wait for exit → `H7` record `RESTORING`, restore (contaminated tree archived first) → `H8` verify live == snapshot → `H9` game-folder cleanup, record removed.

**Invariants**
- **I1** at every instant either live save == snapshot and there is no record, or a record exists whose snapshot is verified.
- **I2** the host never opens the game with `VM_READ` / `VM_WRITE` (it may use limited query access for the start time).
- **I3** restore never destroys data it has not archived: the contaminated tree is copied into the snapshot directory first (**default on**, `--no-archive-contaminated` to skip; `vault prune` reclaims space).

| Event | Result | Recovery |
|:---|:---|:---|
| Ctrl+C while running | host keeps waiting for the game, then restores | none |
| Second Ctrl+C while waiting | `RESTORE_PENDING`, exit 4 | `vault restore` |
| Console window closed, logoff, shutdown (`CTRL_CLOSE/LOGOFF/SHUTDOWN`) | handler sets `RESTORE_PENDING`; the game is not killed; Windows allows only a few seconds, so the host cannot wait | `vault restore` after the game exits |
| Host killed, power loss | record stays; writer refused (host dead) | `vault restore` |
| Game crash / quits | normal `H6 → H9` | none |
| Game process never appears (default `--launch-timeout` 120 s) | treated as exit: restore, verify, remove record | none |
| Restore blocked (locked file) | bounded retry 30 s, then `RESTORE_PENDING`, exit 4, snapshot and record kept | `vault restore` |
| `run` while a record exists | refused (exit 4) with the one command to run; **no auto-recovery** | `vault restore` |
| Damaged snapshot | restore refuses to touch the live folder | `vault verify` / archived copy |

**Fault-injection test.** For every boundary `H1..H9`, inject a kill or exception, then assert I1 and that `vault restore` returns the live folder byte-identical. One table-driven test replaces case-by-case tests for the lifecycle.

## 5. Reader

`read <feature...> [options]`: one attach and one 60 Hz loop shared by the chosen features (several features can run in one process, or one per terminal). Options of the current `effects` / `animations` commands carry over unchanged (`-q` etc.). Refuses when EAC is loaded. Works with or without a session.

| Feature | Output |
|:---|:---|
| `effects` | `+` appeared / `-` disappeared character effect IDs with addresses (feeds `chr_state_ids.json`) |
| `animations` | same for animation IDs |
| `export` | the JSON document of 1.6.1 (schema unchanged, `systems.session` as in section 3) |

**Export write policy** (replaces 60 Hz file writes): sample at the loop rate, write only when `doc_signature` changed, never more often than `--export-interval` (default **0.5 s**), temp file + replace, final write on exit; `--once` writes one document and exits. Buff countdowns alone do not trigger a write (existing `timer_interval` rule).

## 6. Writer

`write set NAME=VALUE...` (`level`, `runes`, 8 attributes, `hp`, `fp`, `stamina`) and `write refill LIST` (`hp,fp,stamina`), same names, ranges and clamping as 1.6.1. Flow: authorise (section 3) → attach (EAC refused, profile for this exe) → open `WritableProcessMemory` → apply once → read back → close. A value that cannot be applied or does not stick is an error, never silence. Options: `--vault`, `--offsets`, `--effects`, `-v`.

## 7. Exit codes

`0` ok · `1` error / not applied · `2` unsupported exe · `3` EAC loaded · `4` restore pending · `5` no valid session · `130` interrupted.

## 8. Implementation order (tests green after each step)

1. Split `__main__.py` and move code to the packages above (behaviour unchanged).
2. Extract `game/layout.py` and `game/attach.py`; writer stops importing the reader.
3. Add `test_architecture.py`.
4. Session record v2 and writer authorisation.
5. Host: no memory loop, interrupt handling, launch timeout, archive by default, fault-injection test.
6. `read` (multi-feature, export policy) and `write` (renames), `vault` command group.
7. README, CLI docs, plan, changes; version 1.6.2.

## 9. Assumptions and open items

- **Steam Cloud:** assumed not to interfere because the game is launched offline and the save is frozen then restored. **Not verified** (T10 not run); the README keeps one line saying so.
- **Real-game checks still open:** console-close handling, launch-timeout, `RESTORE_PENDING` recovery on the real save folder (on a copy first).
- **Proposed defaults to confirm:** `write set` / `write refill` verbs, `--export-interval 0.5`, `--launch-timeout 120`.
- **Out of scope here:** JSON export contents, new writer features, anything outside the save folder.

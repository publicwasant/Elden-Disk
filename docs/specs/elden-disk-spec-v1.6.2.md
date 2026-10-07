# EldenDisk Memory I/O Tools
> **Document Version:** 1.6.2 (revised from 1.6.1) · **Status:** IMPLEMENTED (tests only; real-game verification open, section 9)
> **Date of Issue:** 2026-10-06
> **Target Platform:** Windows 10 / 11 (x64), Python 3.11+ (64-bit) · **Game:** Elden Ring 1.17.1

1.6.2 is a **foundation release**: no new game features. It splits the tool into four clearly bounded parts (host, vault, reader, writer), makes the save vault the one component that must never fail, and makes every write to the game depend on a verified session. Everything not mentioned here behaves as in [1.6.1](elden-disk-spec-v1.6.1.md).

## 1. Roles and commands

| Command | Role | Game memory | Needs a session |
|:---|:---|:---|:---|
| `run` | **Host.** preflight → snapshot → session record → offline launch → wait → restore → verify | never opens the game with memory access | creates it |
| `read [--query NAME [NAME ...]] [--export] [--live] [--live-effects] [--live-animations]` | **Reader.** every value once; one value or group; `disk-state.json`; continuous modes (section 5) | read-only | no (labels the export when one exists) |
| `write --set NAME=VALUE... --refill LIST` | **Writer.** by value name (section 6) | read + write | **yes** |
| `vault status\|list\|verify\|restore\|keep\|prune` | vault tools | none | `restore` and `keep` refused while the game runs |
| `build`, `hash` | tooling | none | no |

Changes of name: `sandbox --set/--refill` → `write --set` / `write --refill`; `sandbox restore|status|list|verify|prune` → `vault ...`; `effects` / `animations` → `read --live-effects` / `read --live-animations`. The old names are removed, no aliases. `run` no longer writes `disk-state.json`; that is `read --export`.

Typical use: terminal 0 `eldendisk run`, terminal 1 `eldendisk read --live`, terminal 2 `eldendisk write --set vigor=99`.

## 2. Modules and dependency rules

```
eldendisk/
  __main__.py      argparse and dispatch only
  paths.py         runtime dirs, resource lookup, default vault / output dirs
  console.py       printable() (ASCII fallback for legacy code pages), require_windows_x64()
  logbook.py       the one log: logcat-style events, rotating file, console sink hook (no console code)
  ui.py            the console view: concise lines, banner, result helpers, colour; and the raw `-v` sink
  logsetup.py      starts the logbook for a command (log file next to the vault, sink choice)
  commands/        run.py read.py write.py vault.py build.py common.py        (one module per command)
  vault/           saves.py      find / check the live save dir, registry
                   location.py   where the vault lives (`--vault` > Registry > %LOCALAPPDATA%)
                   vault.py      SaveVault: snapshot, restore, verify, prune, session helpers
                   session.py    SessionRecord, states, authorise(), SessionLog
                   gamefolder.py GameFolderGuard (listing, cleanup of files the game created)
                   recover.py    restore_from_record(), recover() (shared by host and `vault restore`)
  host/            host.py       lifecycle state machine (Session, Hooks)
                   launcher.py   offline launch via Steam
                   interrupts.py console close / logoff / shutdown handler
  game/            _win.py       ctypes bindings (the only module that declares them)
                   processes.py  find_pid, process names, start time, window focus, sha256
                   memory.py     read-only ProcessMemory, list_modules
                   profile.py    offsets.json, chr_state_ids.json
                   layout.py     pointer chains, vitals, ranges (shared by reader and writer)
                   attach.py     Target: pid, start time, base, exe hash, EAC check, profile
  reader/          sampler.py effects.py animations.py export.py disk.schema.json
  writer/          writer.py     WritableProcessMemory, WriteGate, EditPolicy, MemoryWriter
tools/             dev_pipeline.py (options it does not know are passed to `run`), soak_check.py (outside the package)
```

| Package | May import | Must not import |
|:---|:---|:---|
| `vault` | stdlib, `paths` | everything else |
| `host` | `vault`, `paths`, `game.processes` | `game.memory`, `game.layout`, `reader`, `writer` |
| `game` | stdlib, `game` | everything else |
| `reader` | `game`, `paths`, `vault.session` (read) | `writer`, `host`, rest of `vault` |
| `writer` | `game`, `vault.session` (check) | `reader`, `host`, rest of `vault` |
| `commands` | everything (they wire the parts together) | - |

`vault`, `host`, `game`, `reader` and `writer` never import `logbook`, `ui` or `logsetup`: they report through an injected callable (`SessionLog(emit=...)`, the writer's and the export's `log`), and the commands connect those to the logbook. Enforced by `test_architecture.py`.

`commands/read.py` and `commands/write.py` are the only places where `vault.session` meets the reader / writer: the command loads the record and calls `authorise()`; the reader and writer packages themselves do not use sessions.

Why `game/layout.py`: in 1.6.1 `memory_writer` imported `Sampler` from `disk.py` (the reader's module) only to locate the player data; the pointer-chain resolution now lives in `layout.py` and both sides use it.

Enforced by `test_architecture.py` (AST over the imports of every module, mutation-checked) plus the write-isolation test: the write capability (`WriteProcessMemory`, `PROCESS_VM_WRITE`) appears only in `writer/writer.py` (and `commands/write.py` as its only user), and `host` / `vault` never reference `ProcessMemory`.

### 2.1 Vault location and build layout

- **Vault.** Every command resolves it the same way: `--vault` > path remembered in the Registry (`HKCU\Software\EldenDisk\VaultDir`, written by `run --vault X` only) > `%LOCALAPPDATA%\EldenDisk\vault`. It is never placed next to the exe: the exe lives in `build/dist`, which `build -c` deletes, and the vault holds the only clean copy of the save. A remembered path whose folder is unavailable is an error (never a silent fresh vault, which would hide an owed restore).
- **Build output.** `./build/dist/eldendisk/eldendisk.exe` (no version in the path, so IDE run configurations and the vault survive a version bump); work files in `./build/work`. `build` also writes `README.md` there: `docs/README-exe.md` (intro, `{version}` filled in) + `docs/cli-commands-exe.md` without its title; a missing `docs/` is a warning, not a failure. `build -c` refuses (exit 4) while a vault under `build/` holds a session record.

### 2.2 Log and console output

- **One event model.** `Event(when, pid, level, tag, msg, ok)`; levels `V D I W E` (logcat), `ok` marks an info event that reports something done. Tags name the source (`cli host vault game read write export build config steam`).
- **Log file.** Every command writes every event, all levels, to `<vault>/eldendisk.log` (vault resolved as in 2.1, but never remembered by the log itself), line format `MM-DD HH:MM:SS.mmm PID L tag   : message`, one line per event, rotation at 2 MiB keeping 3 files. The command line and the exit code are logged (`D cli`). A log that cannot be opened or written is dropped silently; logging never fails a command. If the remembered vault is unavailable there is no file (the command reports the vault error itself).
- **Shared bus (client log).** The log file is shared by every terminal: each command logs `D cli : eldendisk <version> <argv>` first and `D cli : exit N` last (format unchanged). `run -v` starts a `Tail` (`logbook.Tail`: polls every 0.2 s, starts at the end of the file, hands over whole lines only, skips lines of its own PID, follows rotation by `(st_dev, st_ino)` / shrinking size) and prints other processes' lines in the log format through `ui.raw_line`. Without `-v` nothing is tailed.
- **Concurrent writers.** Several processes append to one file; a rotation that cannot rename the file (another process holds it, Windows) is skipped and the sink reopens, so logging never fails a command.
- **Session log.** `session.log` in the snapshot directory keeps the same events of one session (ISO time, level, tag, message).
- **Console, no flag.** All commands render events concisely on stderr: ` [time]  symbol  tag  message`, symbols `✓ · ! ✖` (`+ - ! x` when the code page cannot show them), time only for `run` and `read`, debug and verbose events hidden, warnings and errors coloured. `run` and `read` print a banner (title, rule, key/value rows). Results of queries (`vault status`, `vault list`, `vault keep` without `--yes`, `hash`) go to stdout. Colour: `NO_COLOR` off, `FORCE_COLOR` on, else only on a terminal.
- **`-v` on every command** (also after the subcommand) replaces that view, banner included, with the log lines themselves, live, debug included.
- Messages carry no glyphs; the view adds them (`ok` -> `✓`).

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

**Reader.** Optional; it re-checks the record every 2 s. When a valid `RUNNING` record covers the attached game process, `systems.session` in the export is `{mode: "sandbox", sandbox: true}`, otherwise telemetry. `read_only` stays `true` (the reader never writes).

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
| `run` while a record exists | refused (exit 4) with the one command to run; **no auto-recovery**, also with `--vault-off` | `vault restore` |
| Damaged snapshot | restore refuses to touch the live folder | `vault verify` / archived copy |

**Vault ON / OFF (per run).** `run --vault-on` (default) / `run --vault-off`, mutually exclusive, fixed for the life of the host (no toggling while it runs); logged as `D vault : status ON|OFF` and shown as the banner row `mode`. OFF is for read-only farming (e.g. runes delta, buff durations while keeping the progress made in the game): no snapshot, no session record, no restore, no game-folder guard, no pruning (the `RESTORING` state is never entered). Unchanged: the owed-record refusal (exit 4), the game-running and anti-cheat checks. Because no record exists, `authorise()` refuses `write` (exit 5; the message names `--vault-off`), which keeps invariant "every edit is covered by a snapshot". Ctrl+C only stops waiting (exit 130); the game keeps running. `--vault DIR` (location) is unrelated to `--vault-off`. Restoring the save under a running game and a snapshot taken mid-run were rejected as unsafe.

**Fault-injection test.** For every boundary `H1..H9`, inject a kill or exception, then assert I1 and that `vault restore` returns the live folder byte-identical. One table-driven test replaces case-by-case tests for the lifecycle.

## 5. Reader

Values are addressed by **name** only: the paths of `disk-state.json` (`character.attributes.vigor`), with short forms and aliases (section 5.1). There are no memory addresses, offsets or chains in the interface, no scan and no raw read or write; new writable values are added in `offsets.json`.

| Command | Does |
|:---|:---|
| `read` | prints every value once, exits |
| `read --query NAME [NAME ...] [--json]` | prints those values or groups once, exits; the selection is shown in its place in the tree (one single value: one `path  value` row); `--json`: flat `{path: value}` |
| `read --export` | writes `disk-state.json` once (schema unchanged, `systems.session` as in section 3), exits |
| `read --live` | the same as `read`, continuously: the full list once, kept current (below) |
| `read --live --query NAME [NAME ...]` | follows those values or groups |
| `read ... --flat` | the printed views (print, `--query`, `--live`) as one `full.path  value` row per value, no headings, instead of the tree; refused with `--export`, `--json`, the monitors |
| `read --live --export` | the 1.6.2 loop: sample at `--hz` (default 60, the game's frame rate; 1-120), write on change |
| `read --live-effects`, `--live-animations` | the monitors (5.2); stand alone, combinable with each other; `--mapped` / `--unmapped` filter them |

One attach and one loop serve every mode. One-shot modes wait for the game and for a loaded world for `--timeout` seconds (default 15) and then fail with exit 1; live modes wait for ever. `--export` and `--live` combine; `--export` and `--query` do not; `--json` is one-shot only. Stops with exit 3 when EAC is loaded or appears later. Works with or without a session. It never opens a write handle. Options: `--hz`, `--timeout`, `-q` (effects), `--no-idle`, `--out`, `--export-interval`, `--timer-interval`, `--offsets`, `--effects`, `--vault`, `-v`. A vault that cannot be resolved is an error for `--export` (the export is labelled by the session record) and a warning otherwise.

**Whole document.** `read` without a name and `--live` show the export document exactly as `disk-state.json` holds it, `character.effects` and `character.animations` included (decided 2026-10-07; an earlier 1.6.2 build left the lists out and showed values only). `character.*` includes them. A name inside the lists that matches nothing right now is empty, not unknown (`--live` shows `none active`, a one-shot query exits 0 with `nothing matches`); a misspelt list name is still refused.

**Live display.** On a terminal (`isatty`, VT sequences available, `TERM` not `dumb`) `--live` redraws the value tree where it stands (cursor up, rewrite every line, one write per frame, at most 30 frames a second; the cursor is hidden meanwhile); a value that changed is highlighted for 1 s; lines are cut to the window width and, if the tree is taller than the window, the rest is summarised in one line. Elsewhere (IDE run window, pipe) the tree is printed once, then one line per changed value. Buff countdowns and the counters of ignored effects / animations are not changes. Ctrl+C stops. Bars and `q` / `p` keys are not planned.

### 5.1 Names (`game/values.py`)

A name is a path into the export document. `character.` is optional; `attrs`, `rune`, `animation`, `hp`, `fp`, `max` abbreviate `attributes`, `runes`, `animations`, `hit_point`, `focus_point`, `maximum`; a bare `vigor` or `hp` is searched under `attributes` / `vitals`. A bare `hp` or `runes` **reads** as the whole group and **writes** as `...current` / `...total`. Group wildcards (`attrs.*`, `vitals.*.current`) match with `fnmatch`; a bare `*`, `character.*` and `ALL` are refused. An unknown name fails with the closest candidates.

### 5.2 Monitors (`reader/ledger.py`, `reader/monitor.py`, `reader/effects.py`, `reader/animations.py`)

Purpose: discover ids for `chr_state_ids.json` and see which are not mapped yet. A *ledger* keeps one row per id (effect or animation) for the whole run: `active`, `since`, `last_seen`, and the time of the last transition.

- **Settling.** An id becomes active when first present and inactive only after `SETTLE_S` = 0.25 s without it, because the game flips some animation ids every frame (`2020110 ↔ 2022100`); without it rows would blink and the log would be unreadable.
- **Order.** Active rows first, newest activation on top; then the rest, most recently seen first; at one-second resolution with first-seen order as the tie-break, so flipping ids do not reshuffle the table every frame.
- **Mapped.** An effect id is mapped when it is in `chr_state_ids.json` with a source other than `ANIMATIONS`; an animation id when it is in the table at all (as `sampler` names it). Unmapped rows show `Unknown`; the title line counts them. `--mapped` / `--unmapped` filter rows and events (the counts stay).
- **Display.** On a terminal one table per monitor, redrawn in place (same rules as 5, at most 30 frames a second); a row that changed is highlighted for 1 s, `+` green, `-` dim, `Unknown` cyan. Effects add a timer column (`remaining / total s`, `permanent`). The window is shared between tables (smaller first) and rows that do not fit are summarised. Elsewhere each transition is a line: `+ id  name  [timer]  HH:MM:SS.mmm`.
- **Time.** The live displays use `HH:MM:SS.mmm`; `disk-state.json` and the log keep the ISO form with offset.
- **Names reload.** `chr_state_ids.json` is re-checked every 2 s (size and mtime); a valid new file replaces the names, an unreadable one is a warning and the old names stay.

**Export write policy** (live export): sample at the loop rate, write only when `doc_signature` changed, never more often than `--export-interval` (default **0.5 s**; a change inside the window is written at its end), temp file + replace, final write on exit. A change that is only a buff countdown is written at most every `--timer-interval` (default **2 s**, `0` = never). No document is written before the first sample, and never into the game folder. The one-shot `--export` writes the first `CONNECTED` document and exits.

## 6. Writer

`write --set NAME=VALUE [NAME=VALUE ...]` (repeatable) and `write --refill LIST` (`hp,fp,stamina`), same ranges and clamping as 1.6.1. Names follow 5.1. Every value that `read` shows can be named; only the 13 stored values are settable: `level`, `runes`, the 8 attributes, `hp`, `fp`, `stamina`. Anything else is refused with its reason: computed by the game (`hp.maximum`, `hp.base`), computed by the tool, not a stored character value, a group, or a wildcard that matches nothing settable. A name given twice, a name in both `--set` and `--refill`, a non-integer or negative value are usage errors (exit 1, nothing written).

Flow: authorise (section 3) → attach (EAC refused, profile for this exe) → open `WritableProcessMemory` → apply once → read back → close. A value that cannot be applied or does not stick is an error, never silence. Options: `--vault`, `--offsets`, `-v`. Prints one `✓ write NAME = VALUE` line per applied edit (or `values already match`) without `-v`.

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

Done in this order; 490 tests passing, 1 skipped (Linux, fake Windows and memory layers), including the read/write redesign (5, 6).

## 9. Real-game evidence and open items

**Seen on the real game (1.17.1, reported by the author, 2026-10-06)**
- `run`: snapshot, offline launch, game exit, restore, `byte-identical` verification, all in `session.log`.
- `write` of vigor / faith / runes takes effect in the running game; the game's own autosave (site of grace warp) writes the values into `ER0000.sl2`, and they survive a restart.
- **Hard kill (reported 2026-10-07).** Ctrl+C / the IDE's red button kills the host: the record stays, the next `run` is refused (exit 4), and `vault restore` archives the contaminated save and restores the snapshot byte-identically.
- **Read/write redesign (reported 2026-10-07).** `read --live` (tree redrawn in place, highlight), `--live-effects` / `--live-animations` (tables), and `write --set` with the new names passed on the real game. `--export`, `--query`, wildcards and `--refill` were not reported one by one.
- **Vault OFF and client log (reported 2026-10-07).** `run -v --vault-off` through `dev_pipeline.py`: banner row `mode`, `status OFF`, exit 0, save left as the game wrote it; `run -v` printed the `read` command lines of other terminals live.
- **Normal Steam play.** A session played from Steam outside the host persists; the next `run` snapshots it (the "parallel dimension" behaviour is as designed).
- **Steam Cloud upload** was seen online after the corrected save; T10 (sync on exit during a session) is still untested.
- A host killed from the IDE (stop button) leaves the session record and the snapshot; the live save keeps whatever the game last wrote. In the first 1.6.2 build the game died with the host (shared console, process-tree kill).
- Incident: the vault lived in `build/`, `build -c` deleted it together with an owed record, and the next session snapshotted the modified save as "clean". Fixed by section 2.1 and `vault keep`.
- **Steam Cloud is supported by Elden Ring** and accepted the corrected local save after going online. The earlier assumption "Steam Cloud cannot interfere" was wrong; whether it syncs on exit during a host session is untested (T10).

**Added after that incident**
- `vault keep [--yes]`: ends an unresolved session by *keeping* the current save. Needs: game closed, host not running, record not `RESTORING`. Snapshots the current save (`<ts>-kept`, verified) first, keeps the pre-session snapshot, then removes the record; a failure leaves the record. This is the supported way to keep `write` edits (before: kill the host and delete the vault by hand).
- `run --keep N` (default 5): after a finished session only the newest N snapshots stay; never while a record exists; `0` disables.
- `run` prints a Steam Cloud note when `steam.exe` runs.
- The game is started detached (`DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`, null stdio): the host's Ctrl+C and a closed console window do not reach it.
- `log()` prints plain words instead of `\u2713` on legacy code pages (superseded by the symbol fallback of the console view, 2.2).
- Logcat-style log file next to the vault, concise console view for every command, `-v` = live log (section 2.2).
- `read` under EAC: when the module list is unreadable and anti-cheat processes run (a game started from Steam, offline mode included), `locate` exits 3 and points to `eldendisk run`; it no longer says "module not found".
- **Read/write redesign, round 1** (sections 5, 6): the verbs `read effects|animations|export` and `write set|refill` became flags; `read` by name, one-shot by default, `--live` for continuous; `write --set` by name with aliases and group wildcards. Unit tests only, **not run on real Windows**.

**Still open**
- On the real game: console-close handling, `--launch-timeout`, the second-Ctrl+C `RESTORE_PENDING` path, `vault keep`, the detached launch, and the Registry vault path (all covered by unit tests only).
- T10: does Steam Cloud sync the save when the game exits during a session?
- Not yet reported on the real game: `read --export` (one-shot and `--live`), `--query` with every name form, `write --refill`, the refusal messages of `write`.
- `--mapped` / `--unmapped` and the names reload of the monitors on the real game.
- **Out of scope here:** JSON export contents, memory addresses, scans, anything outside the save folder.

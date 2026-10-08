> [!NOTE]
> **Version:** `1.6.4`  
> **Status:** IMPLEMENTED (unit tests only; the real game has not loaded a swapped `regulation.bin` yet, see section 8)  
> **Last Updated:** _2026-10-08_

# Elden-Disk spec 1.6.4: the other world (`regulation.bin` swap)

Reads on top of [spec 1.6.2](elden-disk-spec-v1.6.2.md) (host, vault, session record) and [spec 1.6.3](elden-disk-spec-v1.6.3.md) (params). Only what changes is written here.

## 1. Idea

The vault already keeps *the world as it was*: the save, restored byte for byte when the game closes. 1.6.4 lets it also hold *the world you want to play in*: a `regulation.bin` of your own (rows added or changed with an external editor), swapped into the game folder for one session and taken out again with the save.

Nothing about the tool's memory features changes. A swapped file and `write --set params.…` work together: the file can carry new rows, `write` tunes them live.

## 2. Layout

```
<vault>\
  regulation\
    regulation.bin          the other world; put there by the user; the tool never writes, edits or deletes it
  20261008-0800\
    save\                   the save as it was (unchanged since 1.6.0)
    bin\regulation.bin      the game's own regulation.bin (only when the session swapped one)
    manifest.json           + "regulation": {original_sha256, world_sha256} when bin\ exists
    session.log
  session.json              + "regulation": {game_file, world_file, original_sha256, world_sha256} while a swap is owed
```

`regulation\` is not a snapshot (its name is not a timestamp), so `vault list`, `vault prune` and `--keep` ignore it.

## 3. Behaviour

There is no new option. `run` with the vault ON swaps when `<vault>\regulation\regulation.bin` exists; without the file nothing changes. With `--vault-off` the file is ignored (warning), because nothing would put the game's file back.

Host lifecycle (spec 1.6.2 section 4), additions in bold:

| Step | What happens |
|:--|:--|
| H1 preflight | **the user's file must not be empty and the game's `regulation.bin` must exist** |
| H2 snapshot | save snapshot as before, **then the game's `regulation.bin` is copied to `bin\` and both files are hashed; a failed copy discards the whole snapshot** |
| H3 record READY | session record written, **now carrying `regulation`** |
| H3b swap | **the user's file is re-hashed (must equal the hash in the record), copied beside the game's file as `regulation.bin.eldendisk-tmp`, then `os.replace`d over it; the result is hashed again** |
| H4..H6 | launch and wait, unchanged |
| H7..H9 restore | save restored and verified as before, **then `bin\regulation.bin` is copied back the same way and hashed against `original_sha256`**, then cleanup and record removal. The two restores do not depend on each other: if the save cannot be restored, `bin\regulation.bin` is still put back, so the swapped file never waits in the game folder |

`vault restore` and `vault keep` use the same code. `keep` adopts the current *save* only; the game's own `regulation.bin` is always put back first, and if that fails nothing else changes (exit `1`).

## 4. Invariants

| ID | Statement |
|:--|:--|
| RG1 | After a finished or recovered session, the game folder's `regulation.bin` is byte-identical to the one backed up at H2. |
| RG2 | The swap happens only after the session record that owes its undo exists. Every failure after H3 ends in the restore path. |
| RG3 | The tool never modifies or deletes the user's file in `<vault>\regulation\`. |
| RG4 | The vault OFF never swaps. A swap without a record cannot exist. |
| RG5 | The backup in `bin\` is hash-checked before it is copied back. A damaged one is never used and never blocks the restore of the save (`save\` and `bin\` are verified separately). |
| RG6 | Restoring is idempotent: if the game folder already holds the original (by the hash in the record), nothing is written, even when the backup is damaged. A stale `regulation.bin.eldendisk-tmp` is removed. |
| RG7 | The only game file the tool ever replaces is `regulation.bin`, and only through this path. This amends GF-3 ("pre-existing game files are never modified") of the sandbox spec. |

## 5. Failures

| Situation | Result |
|:--|:--|
| user's file empty, or no `regulation.bin` in the game folder | refused at H1, exit `1`, nothing changed |
| backup fails or is interrupted | snapshot discarded, exit `1` / `130`, game folder untouched |
| user's file changed between the hash and the swap | nothing swapped, restore path, exit `1` |
| swap fails or is interrupted | restore path (the record exists), exit `1` / `130`, game not launched |
| tool killed before the swap | record remains; `vault restore` finds the original in place and writes nothing |
| tool killed while the game runs | record `RUNNING`; after the game closes `vault restore` puts the original back |
| restore of the file fails | record `RESTORE_PENDING`, exit `4`; the save has already been restored; the next `run` is refused until `vault restore` succeeds |
| backup in `bin\` damaged | `vault verify` reports it; the file is not touched, exit `4`, the save is restored regardless. If the user puts the original back by hand, the next `vault restore` finishes (exit `0`) |

## 6. Other changes

- **Fix:** when the session record could not be written, the host deleted the new snapshot and then tried to log into its (deleted) `session.log`, which raised. `SessionLog.detach()` now stops the file logging before the snapshot is discarded. Test added.
- `vault status` shows the file in the vault (path, size, short hash) or that there is none, and, for an owed session, that a different `regulation.bin` is in the game folder.
- `vault list` counts `bin\` in the size of a snapshot; `vault verify` checks it.
- `run` prints the file in its banner when it will be swapped.

## 7. Tests

657 pass, 1 skipped on Linux: `tests/test_regulation.py` (30: normal flow, the game's own file as the user's file, no file, vault off, order, preflight, failed backup, Ctrl+C at each step, file changed during preparation, tool killed before and after the swap, failed and damaged restore, a failed save restore that still puts the game's file back, `keep`, list/status/prune, record round trip, command output), two in `test_run_command.py`, one in `test_host.py`. Checked by breaking the fix on purpose.

## 8. Open

- **Not verified on the real game:** that 1.17.1 starts and loads a swapped `regulation.bin` through `-eac-nop-loaded`. The community does this with a mod loader or a plain replacement; here only the plain replacement is used (manual plan 1.6.4, RG1-RG3).
- No check that the user's file belongs to 1.17.1. The author turned Steam auto update off; a Steam update or *Verify integrity* between sessions would replace the game's file, and the next backup would then take the new one.
- The file stays in effect for every `run` until it is moved out of `<vault>\regulation\`; `vault status` and the `run` banner say so.
- Online play with a changed `regulation.bin` risks a ban, as with any param change. Use `run` (offline) only.
- Editing the file: out of scope. The tool swaps a file somebody else made. (Smithbox must be allowed to *save* a `regulation.bin` for this, outside the game folder; the author may relax the earlier "view / export only" rule for that.)

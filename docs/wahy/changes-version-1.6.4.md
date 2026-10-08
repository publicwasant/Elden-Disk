> [!NOTE]
> **Version:** `1.6.4`  
> **Status:** IMPLEMENTED (unit tests only; real-game verification still open, see spec 1.6.4 section 8)  
> **Last Updated:** _2026-10-08_

**Summary:** **The other world.** If you keep a `regulation.bin` in `<vault>\regulation\`, `run` (vault ON) swaps it into the game folder for the session and `vault` puts the game's own file back with the save. Everything else of 1.6.3 is unchanged.

_(baseline: **[changes-version-1.6.3.md](changes-version-1.6.3.md)**; design: **[elden-disk-spec-v1.6.4.md](../specs/elden-disk-spec-v1.6.4.md)**)_

---

## Wahy

| # | Change | Where |
|:-:|:---|:---|
| 1 | **Swap by presence.** No new option: `<vault>\regulation\regulation.bin` exists + `run` with the vault ON = swapped for the session. No file = nothing changes. With `--vault-off` it is ignored and a warning says so. | `vault/vault.py`, `host/host.py`, `commands/run.py` |
| 2 | **The game's own file is kept in the snapshot** as `<snapshot>\bin\regulation.bin`, hash-checked; the manifest gets a `regulation` key (the `files` of `save\` are unchanged). | `vault/vault.py` |
| 3 | **Session record** gets `regulation` (game file, user's file, both hashes) while a swap is owed. Records of 1.6.3 read as "no swap". | `vault/session.py` |
| 4 | **One restore path.** `restore_from_record` (host and `vault restore`) puts the file back after the save and checks its hash; idempotent; a stale `.eldendisk-tmp` is removed. A failure is `RESTORE_PENDING` (exit `4`) like a failed save restore. The two restores are independent: if the save cannot be restored, the game's `regulation.bin` is still put back first, so the swapped file never waits in the game folder. | `vault/recover.py` |
| 5 | **`vault keep`** adopts the current save only: the game's `regulation.bin` is put back first, and a failure there changes nothing (exit `1`). | `vault/recover.py` |
| 6 | **Separate checks.** `save\` and `bin\` are verified apart: a damaged `bin\` shows in `vault verify` / `list` and is never used, but does not stop the save from being restored. | `vault/vault.py` |
| 7 | **Visible.** `run` banner row `regulation`; `vault status` shows the file (path, size, short hash) or, when there is none, the exact path to put it at (the folder is not created for you), and a pending swap; `vault keep` mentions it; `vault list` counts `bin\`. | `commands/` |
| 8 | **Preflight.** An empty file, or no `regulation.bin` in the game folder, refuses the run (exit `1`) before anything changes. | `vault/vault.py`, `host/host.py` |
| 9 | **Fix (older bug).** If the session record could not be written, the host deleted the new snapshot and then raised while logging into its deleted `session.log`. Fixed with `SessionLog.detach()`. | `host/host.py`, `vault/session.py` |
| 10 | **Tests.** 657 pass, 1 skipped (was 624): new `tests/test_regulation.py` (30), two in `test_run_command.py`, one in `test_host.py`. | tests |
| 11 | **Docs.** Spec 1.6.4, this file, implementation plan, manual test plan 1.6.4 (new checks only), README, CLI references. | `docs/` |

## Behaviour changes

- GF-3 of the sandbox spec ("pre-existing game files are never modified") has one exception now: `regulation.bin`, through this path only (RG7).
- `session.json` and `manifest.json` have one new optional key each. Nothing reads them differently when it is absent.
- A leftover file in `<vault>\regulation\` is swapped in on **every** `run --vault-on`. Move it out to go back to the game's own file.

## Decisions taken while implementing

- **No `--regulation` option.** The file lives in the vault, as the author asked; the vault is the "other world".
- **`bin\` holds the original**, not the new file: the original is what has to come back. The user's file is already in `regulation\`, so only its hash goes in the record.
- **No separate module.** The methods are in `SaveVault`, next to snapshot and restore, so they share the retry on locked files and the hash helper.
- **Swap by copy + `os.replace`** through a `.eldendisk-tmp` file in the game folder, like the save restore.
- **No version check** of the user's file against 1.17.1 (auto update is off); the hashes are in the log and the record.

## Not done / open

- The real game has not loaded a swapped file through this path yet (manual plan 1.6.4, RG1-RG3).
- Everything open in 1.6.3 stays open (PA8-PA10, PA20, M14-M16) and in 1.6.2 (T10).
- Creating the rows (Smithbox or another editor) is outside the tool.

# Standalone Executable CLI Commands Reference (`eldendisk.exe`)

Complete reference for the command line of **EldenDisk** (`eldendisk.exe <command> [options]`). Tool names: **Elden-Disk** / `eldendisk` / Elden-Disk Memory I/O (Read/Write) Tools.

---

## Architecture: four parts, three terminals

| Part | Command | Job | Game memory |
|:---|:---|:---|:---|
| **Host** | `run` | back up the save, launch the game offline, wait, restore the save | never opened |
| **Vault** | `vault ...` | snapshots, session record, restore, recovery | none |
| **Reader** | `read ...` | print, query, export and live view of the game's values | read-only |
| **Writer** | `write ...` | edit values in the running game | read + write, **only inside a session** |

```commandline
Terminal 0:  eldendisk.exe run
Terminal 1:  eldendisk.exe read --live
Terminal 2:  eldendisk.exe write --set vigor=99
```

> [!IMPORTANT]
> While `run` is open, the game's save folder is a temporary "parallel dimension": when the game exits, `run` restores the save taken before launch, byte for byte, and verifies it. If a restore could not finish, the session record stays and the next `run` refuses to start until `vault restore` has been run.
>
> **Log.** Everything the tool does is also written to `<vault>/eldendisk.log`; add `-v` to any command to watch that log live.
>
> **Steam Cloud** has not been verified against the real game (spec test T10). The game runs offline and the save is restored afterwards, so it is assumed harmless.

**Exit codes:** `0` ok · `1` error / not applied · `2` unsupported `eldenring.exe` (or a read-only `params` field named in `write`) · `3` EasyAntiCheat loaded · `4` restore pending · `5` no valid session · `130` interrupted.

---

## 1. `run` (host)

```commandline
eldendisk.exe run [options]
```

Preflight → snapshot (SHA-256 verified) → session record → launch offline → wait for the game → restore → verify → clean up. `run` prints its events only; it does not read the game and writes no JSON (use `read --export`).

| Flag | Default | Description |
|:---|:---|:---|
| `--save-dir DIR` | auto / Windows Registry | Live save folder (`%APPDATA%\EldenRing\<SteamID64>`). Remembered in `HKCU\Software\EldenDisk` after first use. |
| `--vault DIR` | remembered, else `%LOCALAPPDATA%\EldenDisk\vault` | Snapshot vault and `session.json`. An explicit value is **remembered** (Registry, like `--save-dir`), so `read`, `write` and `vault` use the same vault without the flag. |
| `--game-dir DIR` | auto (Steam) | Folder containing `eldenring.exe`. |
| `--offsets FILE` | `offsets.json` | Checked before launching: the exe must have a profile. |
| `--no-archive-contaminated` | off | Do not keep a copy of the modified save in the vault before restoring. |
| `--launch-timeout SEC` | `120` | Seconds to wait for `eldenring.exe` to appear. |
| `--keep N` | `5` | After a finished session keep only the newest N snapshots (never while a restore is owed); `0` = never prune. |
| `--regulation FILE` | none | Swap this `regulation.bin` in for the session instead of building one from the spec (an experiment). Needs the vault ON. |
| `--spec FILE` | embedded `items.draft.json` | The draft: the items `run` builds into a `regulation.bin` (vault ON only). With a valid secured copy and an unchanged draft `run` swaps `regulation.secured.bin` and builds nothing; otherwise it builds (about 20 s) and the gate must pass. See `extension`. |
| `--extension-dir DIR` | `%LOCALAPPDATA%\EldenDisk\extension` | Where the built and secured files are. |
| `--vault-on` / `--vault-off` | `--vault-on` | Per run, never toggled while the host runs. **ON**: snapshot before, restore after. **OFF**: no snapshot, no session record, no restore; see below. |
| `-v`, `--verbose` | off | Show the full log live instead of the concise view; also shows the command lines other terminals log (`read`, `write`, ...). |

**Steam.** If `steam.exe` is running, `run` prints one note: Steam Cloud can sync the save when the game exits (not verified), so use Steam's offline mode or turn Steam Cloud off for Elden Ring during a session.

**Vault OFF** (`run --vault-off`) is for read-only farming: you read runes, buff durations ... with `read` and the progress you make in the game is **kept**, because nothing is backed up and nothing is restored. The banner shows `mode  vault OFF (no backup, no restore)` and the log has `D vault : status OFF` (`status ON` otherwise). Consequences, all deliberate:

- `write` is **refused** (exit `5`): with no session record no edit would be covered by a snapshot.
- An owed restore from an earlier session still blocks `run` (exit `4`), also with `--vault-off`; run `vault restore` or `vault keep` first.
- Game-running and anti-cheat checks stay; nothing is written to the save or the game folder (except the `regulation.bin` swap, see `vault` and `extension`); no automatic pruning of snapshots.
- Ctrl+C only stops the host (exit `130`); the game keeps running.
- `--vault DIR` (where the vault lives) and `--vault-off` (no protection) are unrelated.

```commandline
eldendisk.exe run --vault-off -v
eldendisk.exe read --live --query runes        (other terminal)
eldendisk.exe read --live-buffs               (other terminal)
```

**Vault location.** Resolved the same way by every command: `--vault` → the path remembered by an earlier `run --vault X` → `%LOCALAPPDATA%\EldenDisk\vault`. It is deliberately not next to the exe (a rebuild deletes `build/`). If the remembered folder is unavailable (drive missing) the command stops with an error instead of creating a fresh, empty vault.

**Interrupts.** First Ctrl+C: the game keeps running and the save is restored after it exits. Second Ctrl+C: stop waiting, leave `RESTORE_PENDING` (exit 4). Closing the console window, logoff or shutdown marks `RESTORE_PENDING` too; the game is not killed. Recover with `vault restore` after the game is closed.

```commandline
 Elden-Disk 1.6.2 · run
 ────────────────────────────────────────────────────────────────
   vault  %LOCALAPPDATA%\EldenDisk\vault
   save   C:\Users\<User>\AppData\Roaming\EldenRing\<SteamID64>
   game   C:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game
   mode   vault ON (backup before, restore after)
 ────────────────────────────────────────────────────────────────
 12:00:00  ✓  vault  snapshot 20261006-120000, 2 files verified
 12:00:01  ·  game   launching eldenring.exe offline
 12:00:09  ✓  game   running, pid 8812; `write` is now allowed
 ...                                      (game exits)
 12:31:40  ·  game   exited
 12:31:42  ✓  vault  save restored, byte-identical to the snapshot
```

With `-v` the banner and these lines are replaced by the log itself (see "Log and output" below).

---

## 2. `read` (reader)

```commandline
eldendisk.exe read [--query NAME [NAME ...]] [--flat] [--export] [--live] [--live-buffs] [--live-animations] [options]
```

Read-only: it never opens a write handle. Works with or without `run` (a game started from Steam's Play button has EasyAntiCheat, which hides the game from `read`: exit `3`, start it with `run`). Stops with exit `3` if EasyAntiCheat is or becomes loaded.

| Command | Does |
|:---|:---|
| `read` | print **every** value once, then exit |
| `read --query NAME [NAME ...]` | print those values or groups once, then exit |
| `read --export` | write `disk-state.json` once, then exit |
| `read --live` | the same as `read`, but keep going: on a terminal the tree is redrawn where it stands and a value that just changed is highlighted for a second; in an IDE run window or a pipe the tree is printed once, then one line per changed value |
| `read --query NAME [NAME ...] --live` | keep following those values or groups |
| `read --export --live` | keep writing `disk-state.json` for other programs (sampled at `--hz`, written only when the content changed, at most every `--export-interval`) |
| `read --live-buffs` | buffs monitor: one row per buff id, kept current (see below) |
| `read --live-animations` | animation monitor: one row per animation id; with both, two tables |

`--live` means "do not stop"; Ctrl+C ends it and the game keeps running. One-shot commands wait up to `--timeout` seconds for the game and for a loaded world, then exit `1`; the live commands wait for ever.

**Names.** A name is a path into `disk-state.json`: `character.level`, `character.runes.total`, `character.attributes.vigor`, `character.vitals.hit_point.current`, `character.buffs`, `systems.status.pid`. Short forms work: `character.` can be left out, `attrs` = `attributes`, `hp` = `hit_point`, `fp` = `focus_point`, `max` = `maximum`. A group name shows the whole group; `*` selects several values. A wrong name is an error with suggestions. The game's own tables are under `params` (`params.effects.1621000.effectEndurance`; typed in full, any letter case; `read` with no flag shows them last, `character.*` never includes them). They are read about once a second, and `params` is `null` (and `read --query params...` says why) when the table cannot be found or checked. `--export` writes them as the third block `params`, `null` when no game is attached.

**Several names, and the tree.** `--query` takes any number of names (`--query runes hp attrs.vigor`); the result is one selection, in the order asked, each value once. Whatever is selected (a group, a wildcard, several names) is printed **in its place in the tree**, the same layout as `read` itself (`character` > `runes` > `total`), so `--live` redraws and highlights it the same way. Exactly one single value is the exception: it stays one `path  value` line (handy in scripts). `--json` prints a flat object `{"path": value, ...}` for the selection.

**`--flat`** switches every printed view (`read`, `--query`, with or without `--live`) from the tree to one `full.path  value` row per value, no headings: easy to read across groups and to filter (`read --flat | findstr vigor`). It combines with `--query` and `--live` (redrawn and highlighted the same way); it is refused with `--export`, `--json` and the two monitors, which have their own layouts.

```commandline
eldendisk.exe read --query character.runes.* attrs.vigor --flat --live
 character.runes.total       40,402,709
 character.runes.baseline    40,401,505
 character.runes.delta       +1,204
 character.attributes.vigor  80
```

```commandline
eldendisk.exe read --query runes
 character
   runes
     total     40,402,709
     baseline  40,401,505
     delta     +1,204
eldendisk.exe read --query hp.max
 character.vitals.hit_point.maximum  1,460
eldendisk.exe read --query attrs.*
 character
   attributes
     vigor  80
     mind   60
     ...
eldendisk.exe read --query character.runes.* character.buffs.* --live
 character
   runes
     total     40,402,709
     ...
   buffs
     311100
       name        Gold Scarab
       categories  TALISMANS
eldendisk.exe read --query vigr
 ✖  read   unknown name 'vigr'; did you mean character.attributes.vigor, ...
```

Results go to **stdout**, events to stderr; `--json` prints the result as JSON instead (one-shot only), so `read --query runes --json` can be piped.

A terminal that cannot move the cursor (IDE run window, pipe, `TERM=dumb`) gets the change lines. If the tree is taller than the window the rest is summarised in one line (make the window taller, or use `--query`). **Loading screens** (warp, death, quit to title): on a terminal the last tree stays where it is with one dim line `waiting for a loaded world …` below it, and the next frame redraws over both (the details go to the log only); elsewhere the two events `waiting for a loaded world` / `world loaded` are printed once each. Ctrl+C stops; the last frame stays on screen.

`read` with no name and `--live` show the whole document of `disk-state.json`: `systems` and `character` (level, vitals, runes, attributes) **including `character.buffs` and `character.animations`**, the same content as the file. With many buffs the tree is long: a live view taller than the window is cut with a `… N more lines` line (make the window taller, or ask for a part with `--query`). `--query buffs`, `--query character.buffs.*`, `--query animations` show just the lists, also with `--live`; `character.*` includes them. The lists come and go, so a name inside them that matches nothing **right now** is not an error: `--live` shows `none active` (and keeps running, rows reappear when something starts), a one-shot query says `nothing matches` and exits `0`. A misspelt list name (`character.buffz.*`) is still an unknown name. `--live-buffs` / `--live-animations` are the monitors (one row per id: what appeared / disappeared, with times). Buff countdowns (`buff_duration`) tick in the live tree in their own colour (magenta) so they stand out from constants; they do not count as changes, so they are not highlighted as such. The file schema is unchanged.

**`--export`** writes `disk-state.json` (to `--out`, never inside the game folder) and says where: `✓ export  disk-state.json (4.1 KB) written to <dir>`. The document and its schema are unchanged. `systems.session` is `{"mode": "sandbox", "sandbox": true}` while a valid `RUNNING` session covers the game, otherwise `{"mode": "telemetry", "sandbox": false}`; `read_only` is always `true`. With `--live` the writing loop is the 1.6.2 one: `IDLE` while the game window is unfocused (`--no-idle` to keep reading), a countdown-only change is written at most every `--timer-interval`, one more write on exit.

| Flag | Default | Applies to | Description |
|:---|:---|:---|:---|
| `--query NAME [NAME ...]` | all values | print, `--live` | One or more values or groups to show. |
| `--flat` | off (tree) | print, `--live` | One `full.path  value` row per value instead of the tree. |
| `--export` / `--live` / `--live-buffs` / `--live-animations` | off | | Modes above. `--export` and `--query` cannot be combined; the two monitors stand alone (together is fine). |
| `--json` | off | one-shot | Print as JSON. |
| `--timeout SEC` | `15` | one-shot | Seconds to wait for the game and a loaded world. |
| `--offsets FILE` | `offsets.json` | all | Profiles. |
| `--state-ids FILE` | `chr_state_ids.json` | all | Names for buff and animation IDs (`{"buffs": {id: {...}}, "animations": {id: {...}}}`) (monitors re-read it when it changes). |
| `--vault DIR` | remembered, else `%LOCALAPPDATA%\EldenDisk\vault` | all | Where to look for the session record (labels the export). |
| `--hz N` | `60` (1-120) | live | Reads per second. 60 matches the game's frame lock; up to 120 samples every frame. |
| `-q`, `--quiet` | off | `--live-buffs` | Hide short-lived internal buffs (0 ≤ duration < 1 s). |
| `--mapped` / `--unmapped` | off | `--live-buffs`, `--live-animations` | Show only ids that are / are not in `chr_state_ids.json`. |
| `--out DIR` | `<tool>/output` | `--export` | Directory of `disk-state.json`. |
| `--no-idle` | off | `--export --live` | Keep reading while the game window is unfocused. |
| `--export-interval SEC` | `0.5` | `--export --live` | Minimum seconds between file writes. |
| `--timer-interval SEC` | `2` | `--export --live` | Seconds between writes that only change a buff countdown; `0` = never. |
| `-v`, `--verbose` | off | all | Show the full log live instead of the concise view. |

**`--live-buffs` / `--live-animations`** are the discovery monitors: what is active right now, and everything that came and went, so ids can be named in `chr_state_ids.json`. One row per id, however often it comes back; a terminal gets a table that is redrawn where it stands:

```commandline
 buffs   3 active · 5 seen · 2 unmapped
           id  name         timer            time
 +     311100  Gold Scarab  permanent        04:06:12.750
 +       3971  Unknown      141.2 / 180.0 s  04:06:12.750
 -    1660000  Golden Vow                    04:06:07.512

 animations   1 active · 4 seen · 1 unmapped
           id  name      time
 +    2020110  Running   04:06:12.766
 -    2022100  Unknown   04:06:12.750
 -    2000000  Standing  04:06:07.512
```

- `+` (green) is active now, `-` (dim) has gone; `time` is when it appeared, or when it was last seen. A row that just changed is highlighted for a second.
- **Order:** active first (newest on top), then the ones that left (latest first). The order is refreshed at most once a second, so ids that flip every frame (the game does that with some animations) do not shuffle the list. An id counts as gone only after 0.25 s without it.
- `Unknown` (cyan) is an id that is not in `chr_state_ids.json`; the title line counts them. `--unmapped` shows only those, `--mapped` only the others (the counts stay).
- `chr_state_ids.json` is re-read when it changes (`✓ read  chr_state_ids.json reloaded (N buffs, N animations)`), so a name you just added shows at once. If the file cannot be read the old names stay and a warning says why.
- Rows are kept for the whole run. If the table is taller than the window the oldest are summarised in one line; with both flags the window is shared (the smaller table first).
- Buffs: the timer is `remaining / total s`, or `permanent`; `-q` hides short-lived internal buffs.
- Timestamps here are `HH:MM:SS.mmm`; `disk-state.json` and the log keep the ISO form.
- In a console that cannot redraw (IDE run window, pipe) each change is a line instead: `+ 2020110  Running  04:06:12.766` (`[buffs]` / `[animations]` prefix when both run).

---

## 3. `write` (writer)

```commandline
eldendisk.exe write [--vault DIR] [--offsets FILE] [-v] --set NAME=VALUE [NAME=VALUE ...] [--refill LIST] [--reset NAME [NAME ...]]
```

Applies edits **once**, reads them back, closes and exits. Run it again to re-apply. `--set` may be repeated; `--vault`, `--offsets` and `-v` can come before or after. Prints one `✓ write  NAME = VALUE` line per applied edit (or `values already match`), no `-v` needed.

It works only inside a session. Exit `5` and no write handle if any of these fails: record readable · state `RUNNING` · snapshot verified · the game is the recorded process (pid and start time) · same exe hash · the host is alive. Also refused when EasyAntiCheat is loaded (exit `3`). A value that cannot be applied, or does not stick, exits `1` and prints an error.

**Names** are the ones of `read --query` (section 2), full or short, case-insensitive:

| Value | Names | Range |
|:---|:---|:---:|
| level | `level`, `character.level` | 1 - 713 |
| runes | `runes`, `rune`, `runes.total` | 0 - 999,999,999 |
| attributes | `vigor`, `mind`, `endurance`, `strength`, `dexterity`, `intelligence`, `faith`, `arcane` (also `attrs.vigor`, `attributes.vigor`) | 1 - 99 |
| current HP | `hp`, `hit_point`, `hp.current` | 1 - max HP |
| current FP / stamina | `fp`, `focus_point`, `stamina` | 0 - max |

A pattern that names a group sets all of it: `--set attrs.*=50`, `--set vitals.*.current=1`. Not everything at once: `*` and `character.*` are refused. `--refill` takes the vitals (`hp,fp,stamina`) and sets them to their maximum.

**Game params (1.6.3).** Names under `params.` edit the game's own tables: `params.<table>.<row>.<field>`, typed in full (no short forms), in any letter case; a row is its game id. Today the table is `effects` (SpEffectParam) and the rows are the four Black Flame spells listed in `offsets.json`. Each row also shows `name` (its text from `offsets.json`, e.g. `Black Flame`): it is shown, never written (`--set ...name=...` is refused like a locked field).

| Field | Type | Range | Writable | Meaning |
|:---|:---:|:---:|:---:|:---|
| `effectEndurance` | f32 | -1 - 9999 | yes | seconds the effect lasts; `-1` = until removed, `0` = one instant tick; the game's value is `2` |
| `motionInterval` | f32 | 0.01 - 999 | yes | seconds between ticks (game: `0.1`) |
| `changeHpRate` | f32 | -100 - 100 | yes | size of each tick (game: `0.1`) |
| `changeHpPoint` | s32 | -9999 - 999 | yes | size of each tick (game: `1`) |
| `atkOccurrenceSpEffectId` | s32 | - | **no** | another effect applied to whoever is hit (`-1` = none) |
| `vfxId` | s32 | - | **no** | visual effect (game: `9010` for the Black Flame burns) |

Rows: `1621000` Black Flame, `1623000` Scouring Black Flame, `1625000` Black Flame Ritual, `1626001` Black Flame Blade. `--set` takes one field (`params.effects.1621000.effectEndurance=-1`) or a pattern (`"params.effects.*.effectEndurance=-1"`, quote it so the shell leaves the `*` alone); a pattern says how many values it matched and skips read-only fields (`skipped (locked): ...`). A read-only field named exactly, or a name that matches nothing, a group (`params.effects.1621000`), a value of the wrong kind (`changeHpPoint=1.5`) or a field set twice stops the command before anything is written (exit `2` for the read-only field, `1` for the rest). A value outside the range is clamped and the line says `(clamped from ...)`.

**`--reset NAME ...`** puts the game's own values back (they are in `offsets.json`): `params.effects.1621000.effectEndurance` (one field), `params.effects.1621000` (one row, its writable fields), a pattern, or `all` (every param). It takes no `=VALUE`, and only `params` names or `all`. Nothing to reset prints `values already match`. A param edit goes through the same session check as every other edit, and every call finds the table again through the pointer chains in `offsets.json` and checks it (the header must add up, the row id must be in the file) before it writes; a failed check is reported as `not applied: ...` (exit `1`).

Params exist only in the game's memory: they are gone when the game closes. A burn already on an enemy keeps the duration it had. **Offline only** (`run` starts the game offline): changing params online or with anti-cheat active can get an account banned.

Values the game or the tool computes cannot be set, and the error says why: `hp.max` / `fp.base` ... (the game recomputes them from your stats; set the attribute), `runes.delta` / `runes.baseline` (computed by the tool), buffs, animations and `systems.*`. Bare group names (`attributes`, `vitals`) are refused as groups.

```commandline
eldendisk.exe write --set vigor=90 hit_point=1 --refill fp
 ✓  write  vigor = 90
 ✓  write  hp = 1
 ✓  write  fp = 350
eldendisk.exe write --set params.effects.1621000.effectEndurance=-1
 ✓  write  params.effects.1621000.effectEndurance = -1.0
eldendisk.exe write --set "params.effects.*.effectEndurance=-1"
 ·  write  params.effects.*.effectEndurance matches 4 values: 1621000.effectEndurance, 1623000.effectEndurance, 1625000.effectEndurance, 1626001.effectEndurance
 ✓  write  params.effects.1621000.effectEndurance = -1.0
 ...
eldendisk.exe write --set params.effects.1621000.vfxId=0
 ✖  write  params.effects.1621000.vfxId is locked (read-only); nothing was written
eldendisk.exe write --reset all
 ✓  write  params.effects.1621000.effectEndurance = 2.0
 ...
eldendisk.exe write --set hp.max=9999
 ✖  write  'hp.max' cannot be set: computed by the game from your stats (set the attribute, or use hp/fp/stamina for the current value)
```

---

## 4. `vault` (save vault tools)

```commandline
eldendisk.exe vault [--vault DIR] status | list | verify | restore | keep | prune
```

| Subcommand | Description |
|:---|:---|
| `status` | Session record, snapshot count, last snapshot and its check, vault size and folder. Exit `4` while a restore is owed. |
| `keep [--yes]` | Accept the **current** save as the new baseline and end an unresolved session (for keeping edits made with `write`). Needs the game closed and the host stopped. Backs the current save up as `<ts>-kept`, keeps the pre-session snapshot, removes the record. Without `--yes` it only explains what would happen. Refused while a restore was interrupted (`RESTORING`). |
| `list [--fast]` | Snapshots with size and verification result (`--fast` skips re-hashing). |
| `verify SNAPSHOT` | Re-hash one snapshot against its manifest. |
| `restore [--snapshot NAME] [--save-dir DIR] [--no-archive-contaminated]` | Finish an owed restore from the session record (safe to repeat). Refused while the game runs. `--snapshot` restores a chosen snapshot instead; the current save is kept as `<ts>-pre-restore`. |
| `prune --keep N` | Delete older snapshots (refused while a restore is owed). |

```commandline
eldendisk.exe vault status
 ✖  session RESTORE_PENDING: the live save is NOT trusted until it is restored
     since      2026-10-06T12:00:00+07:00
     snapshot   %LOCALAPPDATA%\EldenDisk\vault\20261006-120000
     next       close the game, then run `eldendisk vault restore`
     snapshots  3, last 20261006-120000, verified
     vault      14.2 MiB in %LOCALAPPDATA%\EldenDisk\vault
```

A record from 1.6.0 / 1.6.1 (`PENDING_RESTORE.json`) is read as `RESTORE_PENDING`.

**The other world (1.6.4, files from 1.7.0).** A `regulation.bin` named by `run` (the one it built from the spec when the vault is ON, or `--regulation FILE`) replaces the game's for a `run` with the vault ON; the game's own file is kept in each snapshot (`bin\regulation.bin`) and put back, with the save, by the same restore (`run`, `vault restore`; `vault keep` puts it back first). `--vault-off` ignores it (warning). The vault no longer looks in `<vault>\regulation\` (1.6.4): a file there is reported once and not used. `vault status` shows, for an owed session, that a different file is in the game folder; `vault verify` and `vault list` check `bin\`. A restore that cannot put the file back leaves `RESTORE_PENDING` (exit `4`). Specs: [1.7.0](specs/elden-disk-spec-v1.7.0.md), [1.6.4](specs/elden-disk-spec-v1.6.4.md).

---

## 4b. `extension` (build things for the game outside the game)

```commandline
eldendisk.exe extension --list
eldendisk.exe extension customize-items [--add all|ID | --secure] [--dry-run] [--spec FILE] [--source FILE] [--game-dir DIR] [--extension-dir DIR]
```

`extension` is a main command like `read`, `write` and `vault`. Because an extension changes game files, it depends on the vault's permission like `write` does: with the vault ON (the default) `run` also runs the extension; with `--vault-off` it does not. There is no flag to turn it on.

A file goes **draft → built → secured**. `items.draft.json` is what you edit. `run` builds a `regulation.bin` from it on the game's own file (never on a modified one) and a **gate** judges the finished file; if the gate fails, nothing is swapped and the game is not started. When the file worked in the game, close the game and run `extension customize-items --secure`: the build is kept as `regulation.secured.bin` with a record `items.secured.json`. From then on `run` swaps the secured copy without building (and without the gate) while the draft does not change. Files live in `%LOCALAPPDATA%\EldenDisk\extension\customize-items\` (`--extension-dir` changes the folder): `regulation.bin` (latest build), `regulation.secured.bin`, `items.secured.json`. The commands below do not start the game; the swap itself is the vault's job.

| Command | What it does |
|:--|:--|
| `extension --list` | The draft (path, and whether it is the embedded copy, one next to the exe, or the source), how many items it has, what is secured, the changes of the draft since it was secured, and the last build. |
| `extension customize-items` | Where the files are. |
| `--add all` / `--add ID` | Build the items of the draft into `<ext>\customize-items\regulation.bin` (about 20 s) and run the gate; always builds. One item per build in this version: with more in the draft, name one with `--add ID`. An empty list builds nothing. |
| `--dry-run` | With `--add`: build and run the gate in memory, write nothing. |
| `--secure` | Game closed. Runs the gate on `regulation.bin` against the current draft and the game's file, then keeps it as `regulation.secured.bin` and writes `items.secured.json`. Stands alone (not with `--add` / `--dry-run`). There is no `--force`: delete `items.secured.json` to make the next `run` build. |
| `--spec FILE` | The draft. Default: `items.draft.json` next to the exe, else the copy embedded by `build -c -em`, else `code/eldendisk/extension/customize_items/items.draft.json`. Also accepted by `extension --list` and `run`. |
| `--source FILE` / `--game-dir DIR` | The game's original `regulation.bin` to build on (default: the one in the auto-detected game folder). It is checked against the known original on every path. |
| `--extension-dir DIR` | Where the files go. |

**`items.draft.json`** (format 1) is the draft of the item(s) you want in the game: `items` is a list of incantations, for example the tested `reverse-curse-technique` in `code/eldendisk/extension/customize_items/items.draft.json`: `requires` (`intelligence`, `faith`, `arcane`), `fp_cost`, `stamina_cost`, `cast_motion` (`flame-grant-me-strength` or `black-flame-blade`), `effect` (heal over time), `poise_while_casting_seconds`, `shop` (`price`, `stock`), plus `name` and `description` (stored only; they do not count as a change). Unknown fields are errors; colour, icon and text need files inside the game's archives and are refused. Every problem is listed with its path. `items.schema.json` next to it is the JSON schema for editors.

**`run` uses the secured copy** only when the draft equals the secured one, the secured file has the recorded hash, the game's file is the recorded base, and the recipes are the same version. Otherwise it prints why it builds and a field-by-field diff (`reverse-curse-technique.shop.price  34590 -> 40000`). After a session that built, it hints to run `--secure`.

**In `run`:** `run --vault-on` shows either `using …regulation.secured.bin (no build)` or `building because …` with the diff, then `built, gate passed`, then the host lines (PREFLIGHT, SNAPSHOTTING, READY); the vault swaps the file in and puts the game's own back. A failed gate: `GATE FAILED … nothing was swapped`, exit 1, the game is not started. A vault that still owes a restore: no build. Spec: [elden-disk-spec-v1.7.0](specs/elden-disk-spec-v1.7.0.md).

Exit codes: `0` ok, `1` error, `2` usage.

---

## 5. `hash` and `build`

```commandline
eldendisk.exe hash [--game-dir DIR]
```

Prints the SHA-256 of `eldenring.exe`, the profile key in `offsets.json` (alone on stdout).

```commandline
eldendisk.exe build [-e pyinstaller|nuitka] [-c] [-em] [-i ICON]
```

Builds `./build/dist/eldendisk/eldendisk.exe` (no version in the path); progress and the result are log events. `-c` cleans `./build` first (refused with exit `4` while a vault under `./build` still owes a restore; the vault is never kept there by default), `-em` embeds `offsets.json` and `chr_state_ids.json`. It also writes `./build/dist/eldendisk/README.md` next to the exe: the intro `docs/README-exe.md` followed by this reference (`docs/cli-commands-exe.md` is the only source of the commands); without a `docs/` folder the build only warns.

---

## Log and output

Every command logs **every event** to `<vault>/eldendisk.log` (the folder of `vault status`), in the style of Android's logcat, at all levels:

```text
10-07 12:00:00.123  4242 D cli   : eldendisk 1.6.2 run -v
10-07 12:00:00.981  4242 I vault : snapshot 20261006-120000, 2 files verified
10-07 12:00:09.411  4242 I game  : running, pid 8812; `write` is now allowed
10-07 12:31:42.007  4242 W host  : Ctrl+C: the game keeps running; the save is restored when it exits (press again to postpone the restore)
```

Format `MM-DD HH:MM:SS.mmm  PID L tag : message`; levels `V` verbose, `D` debug, `I` info, `W` warning, `E` error; one line per event. The file rotates at 2 MiB (`eldendisk.log`, `.1`, `.2`) and logging never stops a command: if the file cannot be written the command carries on.

**Console, no flag needed.** `run`, `read`, `write`, `vault`, `build` print concise lines: a symbol (`✓` done, `·` info, `!` warning, `✖` error), the source tag and a short message; `run` and `read` add a banner and the time. Events go to **stderr**, the result of a query (`vault status`, `vault list`, `hash`) to **stdout**, so `hash` and `read --query ... --json` stay pipeable. Warnings and errors are coloured on a terminal (`NO_COLOR=1` turns colour off, `FORCE_COLOR=1` forces it, e.g. in an IDE run window). Consoles whose code page cannot show `✓` / `✖` get `+` / `x`.

**`-v`, `--verbose`** (every command, also after the subcommand: `write --set level=150 -v`) forgets the concise view and shows the log itself, live: the very lines of `eldendisk.log`, debug included, nothing else.

**Every terminal is in the log.** Each command, in any terminal, writes `D cli : eldendisk 1.6.2 <arguments>` when it starts and `D cli : exit N` when it ends. `run -v` also follows the file and prints the lines of **other** terminals as they are written (from the moment `run -v` starts, own lines are not repeated, rotation is followed), so one window shows `read`, `write` and `vault` commands next to the host's events. The format is the same as above; several processes may write the file at once, and if a rotation cannot rename the file (another process holds it, Windows) logging simply carries on.

```text
10-07 13:53:07.306 14004 D cli   : eldendisk 1.6.2 write --set level=150
10-07 13:53:07.501 14004 D cli   : exit 0
```

---

## Examples

```commandline
# first run, several Steam accounts: pass the save folder once (remembered afterwards)
eldendisk.exe run --save-dir "C:\Users\<User>\AppData\Roaming\EldenRing\<SteamID64>" -v

# every value once / one value / a group
eldendisk.exe read
eldendisk.exe read --query runes
eldendisk.exe read --query attrs.*

# follow a value while playing
eldendisk.exe read --query runes --live

# find buff and animation IDs while playing
eldendisk.exe read --live-buffs -q
eldendisk.exe read --live-animations

# one JSON document and exit; or keep it fresh for another program (written at most every second)
eldendisk.exe read --export
eldendisk.exe read --export --live --export-interval 1

# edit while playing
eldendisk.exe write --set level=150 runes=999999999
eldendisk.exe write --set attrs.*=50 --refill hp,fp,stamina

# game params (offline only; gone when the game closes): Black Flame burns until the target dies
eldendisk.exe read --query params.effects.1621000
eldendisk.exe write --set "params.effects.*.effectEndurance=-1"
eldendisk.exe write --reset all

# keep the edits permanently: write, let the game save (grace / quit to title), stop the host, close the game, then
eldendisk.exe vault keep --yes

# after a crash, power loss or a closed console: close the game, then
eldendisk.exe vault status
eldendisk.exe vault restore
```

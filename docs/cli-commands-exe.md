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

**Exit codes:** `0` ok · `1` error / not applied · `2` unsupported `eldenring.exe` · `3` EasyAntiCheat loaded · `4` restore pending · `5` no valid session · `130` interrupted.

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
| `-v`, `--verbose` | off | Show the full log live instead of the concise view. |

**Steam.** If `steam.exe` is running, `run` prints one note: Steam Cloud can sync the save when the game exits (not verified), so use Steam's offline mode or turn Steam Cloud off for Elden Ring during a session.

**Vault location.** Resolved the same way by every command: `--vault` → the path remembered by an earlier `run --vault X` → `%LOCALAPPDATA%\EldenDisk\vault`. It is deliberately not next to the exe (a rebuild deletes `build/`). If the remembered folder is unavailable (drive missing) the command stops with an error instead of creating a fresh, empty vault.

**Interrupts.** First Ctrl+C: the game keeps running and the save is restored after it exits. Second Ctrl+C: stop waiting, leave `RESTORE_PENDING` (exit 4). Closing the console window, logoff or shutdown marks `RESTORE_PENDING` too; the game is not killed. Recover with `vault restore` after the game is closed.

```commandline
 Elden-Disk 1.6.2 · run
 ────────────────────────────────────────────────────────────────
   vault  %LOCALAPPDATA%\EldenDisk\vault
   save   C:\Users\<User>\AppData\Roaming\EldenRing\<SteamID64>
   game   C:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game
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
eldendisk.exe read [--query NAME] [--export] [--live] [--live-effects] [--live-animations] [options]
```

Read-only: it never opens a write handle. Works with or without `run` (a game started from Steam's Play button has EasyAntiCheat, which hides the game from `read`: exit `3`, start it with `run`). Stops with exit `3` if EasyAntiCheat is or becomes loaded.

| Command | Does |
|:---|:---|
| `read` | print **every** value once, then exit |
| `read --query NAME` | print that value or group once, then exit |
| `read --export` | write `disk-state.json` once, then exit |
| `read --live` | the same as `read`, but keep going: on a terminal the tree is redrawn where it stands and a value that just changed is highlighted for a second; in an IDE run window or a pipe the tree is printed once, then one line per changed value |
| `read --query NAME --live` | keep following that value or group |
| `read --export --live` | keep writing `disk-state.json` for other programs (sampled at `--hz`, written only when the content changed, at most every `--export-interval`) |
| `read --live-effects` | effects monitor: one row per effect id, kept current (see below) |
| `read --live-animations` | animation monitor: one row per animation id; with both, two tables |

`--live` means "do not stop"; Ctrl+C ends it and the game keeps running. One-shot commands wait up to `--timeout` seconds for the game and for a loaded world, then exit `1`; the live commands wait for ever.

**Names.** A name is a path into `disk-state.json`: `character.level`, `character.runes.total`, `character.attributes.vigor`, `character.vitals.hit_point.current`, `character.effects`, `systems.status.pid`. Short forms work: `character.` can be left out, `attrs` = `attributes`, `hp` = `hit_point`, `fp` = `focus_point`, `max` = `maximum`. A group name shows the whole group; `*` selects several values. A wrong name is an error with suggestions.

```commandline
eldendisk.exe read --query runes
 character.runes
   total     40,402,709
   baseline  40,401,505
   delta     +1,204
eldendisk.exe read --query hp.max
 character.vitals.hit_point.maximum  1,460
eldendisk.exe read --query attrs.*
 character.attributes.vigor         80
 character.attributes.mind          60
 ...
eldendisk.exe read --query vigr
 ✖  read   unknown name 'vigr'; did you mean character.attributes.vigor, ...
```

Results go to **stdout**, events to stderr; `--json` prints the result as JSON instead (one-shot only), so `read --query runes --json` can be piped.

A terminal that cannot move the cursor (IDE run window, pipe, `TERM=dumb`) gets the change lines. If the tree is taller than the window the rest is summarised in one line (make the window taller, or use `--query`). Ctrl+C stops; the last frame stays on screen.

The values views (`read` with no name, `--live`) show the **values** of `disk-state.json` (`systems`, level, runes, attributes, vitals) and leave out the long effect and animation lists, so they do not flood the screen. Ask for them by name: `read --query effects`, `--query character.effects.*`, `--query animations`, also with `--live`. A wildcard such as `character.*` does not pull them in. `--live-effects` / `--live-animations` are the monitors (what appeared / disappeared). `disk-state.json` carries the lists either way, schema unchanged.

**`--export`** writes `disk-state.json` (to `--out`, never inside the game folder) and says where: `✓ export  disk-state.json (4.1 KB) written to <dir>`. The document and its schema are unchanged. `systems.session` is `{"mode": "sandbox", "sandbox": true}` while a valid `RUNNING` session covers the game, otherwise `{"mode": "telemetry", "sandbox": false}`; `read_only` is always `true`. With `--live` the writing loop is the 1.6.2 one: `IDLE` while the game window is unfocused (`--no-idle` to keep reading), a countdown-only change is written at most every `--timer-interval`, one more write on exit.

| Flag | Default | Applies to | Description |
|:---|:---|:---|:---|
| `--query NAME` | all values | print, `--live` | Value or group to show. |
| `--export` / `--live` / `--live-effects` / `--live-animations` | off | | Modes above. `--export` and `--query` cannot be combined; the two monitors stand alone (together is fine). |
| `--json` | off | one-shot | Print as JSON. |
| `--timeout SEC` | `15` | one-shot | Seconds to wait for the game and a loaded world. |
| `--offsets FILE` | `offsets.json` | all | Profiles. |
| `--effects FILE` | `chr_state_ids.json` | all | Names for effect and animation IDs (monitors re-read it when it changes). |
| `--vault DIR` | remembered, else `%LOCALAPPDATA%\EldenDisk\vault` | all | Where to look for the session record (labels the export). |
| `--hz N` | `60` (1-120) | live | Reads per second. 60 matches the game's frame lock; up to 120 samples every frame. |
| `-q`, `--quiet` | off | `--live-effects` | Hide short-lived internal effects (0 ≤ duration < 1 s). |
| `--mapped` / `--unmapped` | off | `--live-effects`, `--live-animations` | Show only ids that are / are not in `chr_state_ids.json`. |
| `--out DIR` | `<tool>/output` | `--export` | Directory of `disk-state.json`. |
| `--no-idle` | off | `--export --live` | Keep reading while the game window is unfocused. |
| `--export-interval SEC` | `0.5` | `--export --live` | Minimum seconds between file writes. |
| `--timer-interval SEC` | `2` | `--export --live` | Seconds between writes that only change a buff countdown; `0` = never. |
| `-v`, `--verbose` | off | all | Show the full log live instead of the concise view. |

**`--live-effects` / `--live-animations`** are the discovery monitors: what is active right now, and everything that came and went, so ids can be named in `chr_state_ids.json`. One row per id, however often it comes back; a terminal gets a table that is redrawn where it stands:

```commandline
 effects   3 active · 5 seen · 2 unmapped
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
- `chr_state_ids.json` is re-read when it changes (`✓ read  chr_state_ids.json reloaded (N ids)`), so a name you just added shows at once. If the file cannot be read the old names stay and a warning says why.
- Rows are kept for the whole run. If the table is taller than the window the oldest are summarised in one line; with both flags the window is shared (the smaller table first).
- Effects: the timer is `remaining / total s`, or `permanent`; `-q` hides short-lived internal effects.
- Timestamps here are `HH:MM:SS.mmm`; `disk-state.json` and the log keep the ISO form.
- In a console that cannot redraw (IDE run window, pipe) each change is a line instead: `+ 2020110  Running  04:06:12.766` (`[effects]` / `[animations]` prefix when both run).

---

## 3. `write` (writer)

```commandline
eldendisk.exe write [--vault DIR] [--offsets FILE] [-v] --set NAME=VALUE [NAME=VALUE ...] [--refill LIST]
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

Values the game or the tool computes cannot be set, and the error says why: `hp.max` / `fp.base` ... (the game recomputes them from your stats; set the attribute), `runes.delta` / `runes.baseline` (computed by the tool), effects, animations and `systems.*`. Bare group names (`attributes`, `vitals`) are refused as groups.

```commandline
eldendisk.exe write --set vigor=90 hit_point=1 --refill fp
 ✓  write  vigor = 90
 ✓  write  hp = 1
 ✓  write  fp = 350
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

---

## 5. `hash` and `build`

```commandline
eldendisk.exe hash [--game-dir DIR]
```

Prints the SHA-256 of `eldenring.exe`, the profile key in `offsets.json` (alone on stdout).

```commandline
eldendisk.exe build [-e pyinstaller|nuitka] [-c] [-em] [-i ICON]
```

Builds `./build/dist/eldendisk/eldendisk.exe` (no version in the path); progress and the result are log events. `-c` cleans `./build` first (refused with exit `4` while a vault under `./build` still owes a restore; the vault is never kept there by default), `-em` embeds `offsets.json` and `chr_state_ids.json`.

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

# find effect and animation IDs while playing
eldendisk.exe read --live-effects -q
eldendisk.exe read --live-animations

# one JSON document and exit; or keep it fresh for another program (written at most every second)
eldendisk.exe read --export
eldendisk.exe read --export --live --export-interval 1

# edit while playing
eldendisk.exe write --set level=150 runes=999999999
eldendisk.exe write --set attrs.*=50 --refill hp,fp,stamina

# keep the edits permanently: write, let the game save (grace / quit to title), stop the host, close the game, then
eldendisk.exe vault keep --yes

# after a crash, power loss or a closed console: close the game, then
eldendisk.exe vault status
eldendisk.exe vault restore
```

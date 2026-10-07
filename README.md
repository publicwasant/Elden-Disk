# Elden-Disk

> **Elden-Disk Memory I/O (Read / Write) Tools: offline save guard + live memory reader and writer for Elden Ring 1.17.1**  
> **Version:** `1.6.3` | **Spec Version:** `1.6.3` | **Platform:** Windows 10/11 (x64) | **Runtime:** Standalone Executable (`eldendisk.exe`) or Python 3.11+

Four parts with one job each:

- **Host (`run`):** takes a SHA-256 verified snapshot of your save, launches `eldenring.exe` **offline**, waits, and restores the save **byte for byte** when the game exits. It never opens the game's memory and writes no JSON.
- **Vault (`vault`):** snapshots, the session record, restore and recovery. It is the part that must not fail: a restore that could not finish leaves a record, and the next `run` refuses until `vault restore` has been run.
- **Reader (`read`):** prints every value once and exits; `--query NAME [NAME ...]` values or groups, shown as the same tree (`--flat`: one `full.path  value` row each); `--export` writes `disk-state.json` once; `--live` keeps going; `--live-buffs` / `--live-animations` are the monitors: one row per id, mapped or `Unknown`, `--mapped` / `--unmapped` to filter. Values are addressed by **name** only. Read-only; works with or without `run`.
- **Writer (`write`):** `write --set NAME=VALUE ...` / `write --refill LIST` / `write --reset NAME ...`, applied once, by value name (`vigor`, `attrs.vigor`, `hp`, ...; and the game's own tables: `params.effects.1621000.effectEndurance`). It **refuses to write** unless `run`'s session record is valid for this very game process (exit code `5`), so every edit is covered by a snapshot.
- **Zero configuration files:** `--save-dir` and `--vault` are remembered in the Windows Registry (`HKCU\Software\EldenDisk`). The vault lives in `%LOCALAPPDATA%\EldenDisk\vault` by default, never next to the exe, so a rebuild cannot delete it.

> [!IMPORTANT]
> **Parallel dimension:** edits made through `write` exist only during the session. When the game closes, `run` restores the save taken before launch and verifies it.
>
> **Steam Cloud:** Elden Ring supports it, and it can sync the save when the game exits. Use Steam's offline mode or turn Steam Cloud off for Elden Ring during a session; `run` prints a reminder when Steam is running. Sync behaviour during a host session is **not verified** (spec test T10).
>
> **Real-game status (author, 1.17.1):** `run` restore (byte-identical), hard-kill recovery (`vault restore`), `write --set` by name, `read --live` and the two monitors have been used on the real game. Everything else is verified by unit tests with fake Windows and memory layers (624 tests); the Steam Cloud sync on exit (T10) is still untested. **Game params (1.6.3):** the file layout and the pointer chains were measured on the real game, and writing `effectEndurance = -1` into the Black Flame row (1621000) made the burn last until the enemy died; the other three Black Flame rows and the other fields have **not** been written in the game yet (manual plan section 7A). Keep a manual copy of your save folder.

---

## Three terminals

```mermaid
sequenceDiagram
    autonumber
    participant T0 as Terminal 0 (run)
    participant V as Vault
    participant G as eldenring.exe
    participant T1 as Terminal 1 (read)
    participant T2 as Terminal 2 (write)

    T0->>V: snapshot + verify, session record READY
    T0->>G: launch offline
    T0->>V: record RUNNING (game pid + start time)
    T1->>G: read --live / --live-buffs / --export
    T2->>V: authorised? (record RUNNING, same game, host alive)
    T2->>G: --set / --refill once, then exit
    G->>T0: game exits
    T0->>V: restore, verify byte-identical, remove record
```

```commandline
eldendisk.exe run                                      (Terminal 0, leave open)
eldendisk.exe read --live                              (Terminal 1: every value, redrawn in place)
eldendisk.exe write --set vigor=99 level=150           (Terminal 2)
eldendisk.exe write --refill hp,fp,stamina             (Terminal 2)
eldendisk.exe write --set params.effects.1621000.effectEndurance=-1   (Terminal 2: Black Flame burns until the target dies)
eldendisk.exe write --reset all                        (Terminal 2: the game's own params back)
eldendisk.exe read --query attrs.*                     (any terminal: print once, exit)
```

To **keep** what `write` changed instead of rolling it back: let the game save (rest at a grace or quit to title), stop the host, close the game, then `eldendisk.exe vault keep --yes`.

If the session is cut short (power loss, host killed, console closed, second Ctrl+C), close the game and run `eldendisk.exe vault restore`.

---

## Safety architecture

1. **Host and vault never touch game memory.** `run` only queries a process start time; boundaries are enforced by `test_architecture.py` (module imports are checked by AST).
2. **Write capability lives in one file** (`writer/writer.py`) and is reached only from `write`, after `authorise()`.
3. **Invariant:** at every instant either the live save equals the snapshot and there is no record, or a record exists whose snapshot is verified.
4. **Restore never destroys unarchived data:** a modified save is copied into the vault before it is overwritten (`--no-archive-contaminated` to skip).
5. **Interrupts:** first Ctrl+C is absorbed (the game keeps running); second, console close, logoff or shutdown leave `RESTORE_PENDING`.
6. **No automatic recovery:** `run` with an owed restore exits `4` and prints the one command to run.
7. **Zero changes in the game folder;** `read --export` refuses to write there.
8. **EAC guard:** `read` and `write` stop when EasyAntiCheat is loaded; `run` refuses when anti-cheat processes are running.
9. **Few disk writes:** the export is written only when its content changed, at most every `--export-interval` (0.5 s); buff countdowns at most every `--timer-interval` (2 s).

---

## Quick start

Prerequisites: Windows 10/11 x64, Steam (offline mode is fine), Elden Ring 1.17.1 (included profile).

```commandline
# Terminal 0: back up, launch offline, restore afterwards
eldendisk.exe run
# several Steam accounts: pass the save folder once (remembered)
eldendisk.exe run --save-dir "C:\Users\<User>\AppData\Roaming\EldenRing\<SteamID64>"
```

```commandline
 Elden-Disk 1.6.3 · run
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

Every command prints concise lines like these without any flag. Every event is also logged, logcat style, to `<vault>/eldendisk.log` (every terminal's command line and exit code included); add **`-v`** to a command to see that log live instead (`run -v`, `write --set level=150 -v`, `vault status -v` ...). `run -v` also shows the lines other terminals log.

**Farming (keep the progress):** `eldendisk.exe run --vault-off`, then `eldendisk.exe read --live --query runes` in another terminal. Nothing is backed up or restored, and `write` is refused.

---

## CLI overview

Run via `eldendisk.exe <command> [options]` or `python -m eldendisk <command> [options]`.

| Command | Role | Description |
|:---|:---|:---|
| `run [--vault-on \| --vault-off]` | **Host** | Snapshot, offline launch, wait, restore, verify. `--vault-off`: no backup, no restore (farming with `read`; `write` is refused) |
| `read [--query NAME [NAME ...]] [--export] [--live] [--live-buffs] [--live-animations]` | **Reader** | No flag: every value once. `--query` one value or group; `--export` writes `disk-state.json` once; `--live` continuous (with `--export`: sample at `--hz`, write on change); `--live-buffs` / `--live-animations` monitors (`--mapped` / `--unmapped`); `--json`, `--timeout`, `--export-interval`, `--timer-interval` |
| `write --set NAME=VALUE...` / `write --refill LIST` / `write --reset NAME...` | **Writer** | One-shot edits (values, and `params.…` fields of the game's tables); `--reset` puts the game's own params back; exit `5` without a valid session |
| `vault status \| list \| verify \| restore \| keep \| prune` | **Vault** | Session record, snapshots, recovery; `keep --yes` adopts the current save as the new baseline |
| `hash` | Tool | SHA-256 of `eldenring.exe` (profile key) |
| `build` | Tool | Standalone `./build/dist/eldendisk/eldendisk.exe` plus a `README.md` next to it (quick start + the exe command reference) |

**Exit codes:** `0` ok · `1` error / not applied · `2` unsupported exe, or a read-only `params` field named in `write` · `3` EAC · `4` restore pending · `5` no valid session · `130` interrupted.

Removed in 1.6.2: `sandbox` (now `write` and `vault`), top-level `effects` / `animations` (now `read --live-buffs` / `--live-animations`), JSON output of `run` (now `read --export`), the verbs `read effects|animations|export`, `write set|refill` (now flags) and `--once` (a read without `--live` is already one shot). Values are addressed by name only; there are no memory addresses or scans.

**Full references:** [docs/cli-commands-exe.md](docs/cli-commands-exe.md) (executable) · [docs/cli-commands.md](docs/cli-commands.md) (Python source) · [spec 1.6.3](docs/specs/elden-disk-spec-v1.6.3.md) · [changes 1.6.3](docs/wahy/changes-version-1.6.3.md) · [manual test plan](docs/manual-test-plan-1.6.3.md) · [params report](docs/experiments/params/sp-effect-params/sp-effect-params-hypothesis-report.md)

---

## 🧪 Editable Attributes & Clamping Ranges

All edits supplied via `write --set` are clamped to valid game boundaries before writing:

| Attribute Name | Acceptable Range | Description |
|:---|:---:|:---|
| `level` | `1` – `713` | Character level number |
| `runes` | `0` – `999,999,999` | Current held Rune count |
| `vigor`, `mind`, `endurance`, `strength`, `dexterity`, `intelligence`, `faith`, `arcane` | `1` – `99` | Character stats |
| `hp` | `1` – `Max HP` | Current HP (cannot drop below 1) |
| `fp`, `stamina` | `0` – `Max` | Current FP / Stamina |
| `write --refill hp,fp,stamina` | — | Refills vitals to maximum |

Names: full path (`character.attributes.vigor`), short (`attrs.vigor`, `vigor`) or alias (`rune`, `hp`, `fp`). Groups with a wildcard (`attrs.*`, `vitals.*.current`) set several at once. Bare `*`, `character.*` and `ALL` are refused. Values the game or the tool computes (`hp.maximum`, `hp.base`, ...) are read-only, and the refusal says why. `read --query NAME` uses the same names.

---

## 🔥 Game params (`params.…`, new in 1.6.3)

The game keeps its own data tables in memory. `write` can change a field of one row of the `SpEffectParam` table (the game's table of effects: buffs, burns, ...) while the game runs; `read` shows them as the third block of `disk-state.json`, after `systems` and `character`:

```json
"params": {
  "effects": {
    "1621000": { "name": "Black Flame", "effectEndurance": 2.0, "motionInterval": 0.1, "changeHpRate": 0.1,
                 "changeHpPoint": 1, "atkOccurrenceSpEffectId": -1, "vfxId": 9010 },
    "1623000": { "name": "Scouring Black Flame", "...": "same fields" },
    "1625000": { "name": "Black Flame Ritual",    "...": "same fields" },
    "1626001": { "name": "Black Flame Blade",     "...": "same fields" }
  }
}
```

```commandline
eldendisk.exe read --query params.effects.1621000
eldendisk.exe write --set params.effects.1621000.effectEndurance=-1                 # one field
eldendisk.exe write --set "params.effects.*.effectEndurance=-1"                                  # all four rows
eldendisk.exe write --reset params.effects.1621000.effectEndurance                  # one field back
eldendisk.exe write --reset params.effects.1621000                                  # one row back
eldendisk.exe write --reset all                                                         # every param back
```

- **`effectEndurance`** is how long the effect lasts, in seconds: `-1` = until it is removed (Black Flame burns until the target dies), `0` = a single instant tick. The game's own value is `2`. `motionInterval` (seconds between ticks), `changeHpRate` and `changeHpPoint` (the size of each tick; see the field reference in the params report folder) can be set too. Values outside the allowed range are clamped and the output says so.
- **`atkOccurrenceSpEffectId` and `vfxId` are read-only** (`exit 2`): a wrong id can crash the game. A pattern skips them and says so.
- Names are typed in full, `params.effects.<id>.<field>` (a row is its game id), in any letter case; a `*` pattern sets several values. `name` is the row's text from `offsets.json`: shown, never written. `--reset` takes a field, a row, or `all`, and puts the **game's own values** (from `offsets.json`) back.
- The rows are listed in `offsets.json`: 1621000 Black Flame, 1623000 Scouring Black Flame, 1625000 Black Flame Ritual, 1626001 Black Flame Blade; another row is one line in the profile.
- Same safety gate as every `write`: only inside a valid `run --vault-on` session. The edit lives in the game's memory, **not in the save**, and is gone when the game closes.
- Every call finds the table again through pointer chains and checks it (the header must add up, the row id must be there) before it reads or writes; a check that fails stops the call.

> [!WARNING]
> **Offline only.** Params are what the game trusts: with anti-cheat active, or online, changing them can get an account banned. `run` starts the game offline for this reason. A burn already on an enemy keeps the duration it had; a new cast uses the new value.

How the table was found and what was and was not tested: [docs/experiments/params/sp-effect-params](docs/experiments/params/sp-effect-params/sp-effect-params-hypothesis-report.md).

---

## 📦 Building Standalone Executable & E2E Dev Pipeline

```commandline
# Build standalone executable with embedded configs
python -m eldendisk build -c -em

# Run E2E pipeline (pre-check tests + build + dry run)
python code/tools/dev_pipeline.py --dry-run

# Options the pipeline does not know go to `run`: ends in `eldendisk.exe run -v --vault-off`
python code/tools/dev_pipeline.py --vault-off
```

---

## 📊 Export document (`read --export` → `disk-state.json`)

```json
{
  "systems": {
    "profile": { "sha256": "...", "game": "eldenring.exe", "version": "1.17.1" },
    "features": { "buffs_supported": true, "animations_supported": true, "sandbox_supported": true },
    "status": { "pid": 1234, "tool_state": "CONNECTED", "anti_cheat_state": "DISABLED_OFFLINE", "game_connected": true, "ignored": { "buffs": 0, "animations": 0 } },
    "session": { "mode": "telemetry", "read_only": true, "sandbox": false }
  },
  "character": { "level": 386, "vitals": { ... }, "runes": { ... }, "attributes": { ... },
                 "buffs": { "3971": { "name": "Gold-Pickled Fowl Foot", "categories": "CONSUMABLES", "times": { ... } } },
                 "animations": { ... } },
  "params": { "effects": { "1621000": { "name": "Black Flame", ... } } }
}
```

`character.buffs` and `character.animations` are named from `chr_state_ids.json` (`buffs` and `animations` objects keyed by id; an entry is `name`, optional `categories` and `abilities`):

```json
{ "buffs":      { "3971":    { "name": "Gold-Pickled Fowl Foot", "categories": "CONSUMABLES", "abilities": "..." } },
  "animations": { "2020110": { "name": "Running", "categories": "MANNER" } } }
```

The 1.6.2 file was one flat list with a `sources` field; `python code/tools/convert_state_ids.py chr_state_ids.json` converts it (a backup is kept as `.bak`). `character.effects` is now `character.buffs`, `features.effects_supported` is `buffs_supported`, and `systems.status.ignored.effects` is `.buffs`.

---

## 🧪 Testing & Quality Assurance

```commandline
# Run unit test suite (624 tests)
python -m pytest

# Run soak stability check (V-06)
python code/tools/soak_check.py
```

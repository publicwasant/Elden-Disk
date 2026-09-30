# Elden Ring Telemetry (offline, read-only)

Launches Elden Ring **offline** (`eldenring.exe -eac-nop-loaded`) and writes live character data to
`output/telemetry-state.json`. Implements spec v1.1.0. Standard library only, Windows + 64-bit Python 3.11+.

## Guarantees
- Read-only: the only access mask requested is `PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION`.
- Nothing is written to the game folder (the logger refuses an output dir inside it).
- Never reads memory if EasyAntiCheat modules are loaded, or if the exe version has no profile.
- Any failed check (null pointer, unreadable memory, out-of-range value, cyclic/oversized effect list) discards the whole sample.
  Nothing is ever reported as `0` because a read failed.

## Quick start
1. Start the **Steam client** and log in (offline mode in Steam is fine).
2. `python -m elden_telemetry hash` → prints the SHA-256 of your `eldenring.exe`.
3. Add a profile for that hash in `offsets.json` (see [Adding a profile](#adding-a-profile-once-per-game-patch) and the [step-by-step guide](docs/adding-a-profile.md)). Until you do, `run` reports `UNSUPPORTED_VERSION`.
4. `python -m elden_telemetry run -v`
   - launches the game offline, waits for the main module, then polls at 10 Hz
   - `-v` prints state changes and the reason for the last discarded sample
5. Read `output/telemetry-state.json` from any other program (schema: `elden_telemetry/telemetry.schema.json`).

Already started the game yourself with `-eac-nop-loaded`? Use `python -m elden_telemetry run --attach`
(same EAC/read-only checks apply). Ctrl+C stops the tool and leaves the game running.

Every command and flag is documented in [CLI commands](#cli-commands).

## CLI commands

Run as `python -m elden_telemetry <command> [options]` from the folder that contains `elden_telemetry\` (the project
folder). `-h` works on the tool and on every command. Windows only, 64-bit Python 3.11+.

### Commands at a glance

| Command | What it does | Game state it needs | Steam client |
|---|---|---|---|
| `run` | Launches the game offline (or attaches to a running one), polls memory, writes `telemetry-state.json` | not running (launch mode) · running offline (`--attach`) | required in launch mode |
| `effects` | Live SpEffect viewer: prints active effects, then only what appears (`+`) / disappears (`-`) | running offline (in-world for useful output) | not needed |
| `hash` | Prints the SHA-256 of `eldenring.exe` (the key of a profile in `offsets.json`) | any (reads the file only) | not needed |

### `run`

`python -m elden_telemetry run [options]`

| Flag | Value | Default | Description |
|---|---|---|---|
| `--attach` | switch | off (launch mode) | Attach to an already-running `eldenring.exe` instead of launching it. Waits (`WAITING_FOR_PROCESS`) until the process exists. Same EAC and read-only checks as launch mode |
| `--game-dir DIR` | path | auto-detect via Steam (registry `SteamPath` + `libraryfolders.vdf` → `steamapps\common\ELDEN RING\Game`) | Folder that contains `eldenring.exe`. Required if auto-detect fails. With `--attach` a failed auto-detect is ignored and the real game folder is taken from the running process |
| `--out DIR` | path | `<project>\output` | Directory for `telemetry-state.json` (created if missing). Refused with an error if it is inside the game folder |
| `--offsets FILE` | path | `<project>\offsets.json` | Profiles keyed by exe SHA-256 |
| `--effects FILE` | path | `<project>\effects.json` | SpEffect ID tables. A missing file means empty tables; a malformed file is an error |
| `--hz N` | number, 1–30 | `10` | Polls per second (decimals allowed, e.g. `2.5`). Outside 1–30 is a usage error |
| `-v`, `--verbose` | switch | off | Print state changes and the reason for the last discarded sample (`last_error`) to stderr |
| `-h`, `--help` | switch | | Show help |

What it does, in order: (1) launch mode starts `eldenring.exe -eac-nop-loaded` with `SteamAppId` / `SteamGameId` set in the
child environment, attach mode finds the running process · (2) waits up to 60 s for the `eldenring.exe` module ·
(3) refuses to continue if EasyAntiCheat modules are loaded · (4) hashes the exe and loads the matching profile ·
(5) polls at `--hz`, writing the JSON every poll and re-scanning modules for EAC every 2 s. It ends when the game
exits, when an EAC module appears, on an error, or on Ctrl+C (the game keeps running).

### `effects`

`python -m elden_telemetry effects [options]`

| Flag | Value | Default | Description |
|---|---|---|---|
| `--offsets FILE` | path | `<project>\offsets.json` | Profiles keyed by exe SHA-256. The profile must have a complete `sp_effect` block |
| `-q`, `--quiet` | switch | off | Hide short-lived internal effects (`0 <= duration < 1 s`); keeps permanent (`-1`) and timed buffs |
| `-h`, `--help` | switch | | Show help |

Attaches to the first `eldenring.exe` it finds (never launches the game), refuses if EAC is loaded, polls every 0.5 s.
Output: `--- N effects now active ---` with one line per effect (`id | duration | timer`), then only changes:
`+ id | duration | timer` (appeared) and `- id` (disappeared). While the world is not loaded it prints `[waiting] <reason>`.
Stops on Ctrl+C or when the game exits. It does not read `effects.json` and writes no files.

### `hash`

`python -m elden_telemetry hash [options]`

| Flag | Value | Default | Description |
|---|---|---|---|
| `--game-dir DIR` | path | auto-detect via Steam | Folder that contains `eldenring.exe` |
| `-h`, `--help` | switch | | Show help |

Prints one line: the 64-character SHA-256 of `<game dir>\eldenring.exe`. Use it as the key of a new profile in
`offsets.json`.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Normal end: game closed (`DISCONNECTED`), `effects` stopped, `hash` printed |
| `1` | Error, message printed as `error: …` (game folder not found, `eldenring.exe` module not found within 60 s, game not running for `effects`, output directory inside the game folder, malformed `effects.json`, not Windows, not 64-bit Python) |
| `2` | `run`: `UNSUPPORTED_VERSION` (no complete profile for this exe hash). Also used by Python's argument parser for usage errors (unknown flag, `--hz` out of range): the printed message tells them apart |
| `3` | `run`: `EAC_ACTIVE` / `EAC_DETECTED`, EasyAntiCheat is loaded and the tool refused to read |
| `130` | `run`: stopped with Ctrl+C |

### Fixed behaviour (not configurable by flags)

| Item | Value |
|---|---|
| Output file | `<--out>\telemetry-state.json` (written via `telemetry-state.json.tmp` + atomic replace, 5 retries × 20 ms if a reader holds the file) |
| Paths | Defaults are inside the project folder. A relative path given on the command line is resolved against the current directory |
| Wait for the game module | up to 60 s |
| EAC re-scan while running | every 2 s |
| Effect list safety cap | 512 entries per sample (longer or cyclic list → sample discarded) |
| `effects` poll interval | 0.5 s |
| Memory access | `PROCESS_VM_READ \| PROCESS_QUERY_LIMITED_INFORMATION` only |

### Other scripts

| Script | Arguments | Default | Description |
|---|---|---|---|
| `python tools\soak_check.py` | `[path]` | `<project>\output\telemetry-state.json` | Watches the JSON file (spec V-06): prints state changes, flags invalid JSON, out-of-range values, inconsistent `rune_delta`, impossible buff timers and a stalled writer. Ctrl+C prints a summary and `RESULT: PASS` or `FAIL` (exit code `0` / `1`) |
| | `--interval S` | `0.1` | Seconds between reads |
| `python labs\toy_game.py` | none | | Lab 3 toy "game": prints `PID` and `ROOT`, then raises its own runes every second |
| `python labs\toy_reader.py PID ROOT` | `PID` (decimal), `ROOT` (hex) | required | Lab 3 reader: walks `ROOT → +0 → +0x580 → level/runes` with the project's own reader |

### Common recipes

| I want to… | Command |
|---|---|
| Get the exe hash for a new profile | `python -m elden_telemetry hash` |
| Play with telemetry on | `python -m elden_telemetry run -v` |
| Attach to a game I started offline myself | `python -m elden_telemetry run --attach -v` |
| Lower CPU use / write less often | `python -m elden_telemetry run --hz 2` |
| Write the JSON somewhere else | `python -m elden_telemetry run --out D:\overlay-data` |
| Find SpEffect IDs of buffs and talismans | `python -m elden_telemetry effects -q` |
| Use another profile file | `python -m elden_telemetry run --offsets D:\profiles\offsets.json` |
| Run the 30-minute soak test (V-06) | terminal A: `run -v` · terminal B: `python tools\soak_check.py` |

## Adding a profile (once per game patch)

A profile tells the tool where things live inside one specific build of `eldenring.exe`. Without one, `run` reports
`UNSUPPORTED_VERSION` and reads nothing (by design).

**Full step-by-step guide: [docs/adding-a-profile.md](docs/adding-a-profile.md)** — written for first-timers, with a
checkpoint and a troubleshooting table after every part.

| Part | Goal | Result |
|---|---|---|
| A | Hash, profile skeleton, game open in-world, Cheat Engine attached | ready to search |
| B | First/Next Scan for your runes | an address (temporary) |
| C | Pointer Scan | a permanent pointer path (4 numbers) |
| D | Fill `offsets.json`, compare with the in-game Status screen | **working stats telemetry** |
| E | Verify the SpEffect layout, fill `effects.json` | buffs telemetry |
| F | Back up, record, patch-day routine | done |

**Same exe as the reference build?** If `python -m elden_telemetry hash` prints
`1a3547101327f65d0c76da2f9190ac0aa66871ea42bae2aecc61e11a8b597891` (Elden Ring 1.17.1) you can skip Cheat Engine: the guide's
appendix contains the verified profile and a starter `effects.json`.

What the profile fields mean, in one table:

| Field | Comes from | Example (1.17.1) |
|---|---|---|
| `world_chr_man_rva` | Pointer Scan: *Base Address* `eldenring.exe + RVA` | `0x3B16E30` |
| `world_chr_man_to_player` | Pointer Scan: *Offset 0* | `0x0` |
| `player_to_game_data` | Pointer Scan: *Offset 1* | `0x580` |
| `game_data.runes` | Pointer Scan: *Offset 2* | `0x6C` |
| `game_data.level`, `.attributes` | starting values, verified against the Status screen | `0x68`, `0x3C` |
| `player_to_sp_effect`, `sp_effect.*` | starting values, verified with `effects -q` (buffs only) | `0x178`, head `0x8`, entry id `0x8` / next `0x30` / duration `0x48` / timer `0x40`, `remaining` |

If `sp_effect` is incomplete the tool still runs: `buffs_supported` is `false` and the buff arrays are empty.

## States
| `state` | Meaning |
|---|---|
| `WAITING_FOR_PROCESS` | game not running / not found |
| `EAC_ACTIVE`, `EAC_DETECTED` | EAC loaded; tool exits (code 3) without reading |
| `UNSUPPORTED_VERSION` | no complete profile for this exe hash; tool exits (code 2) |
| `WAITING_FOR_WORLD` | title screen, loading, or a check failed (see `last_error`) |
| `CONNECTED` | all checks passed; `character` filled |
| `DISCONNECTED` | game exited |

## Troubleshooting
- **Game won't start / Steam error on direct launch:** the tool passes `SteamAppId`/`SteamGameId` via environment. If that
  is not enough on your setup, create `steam_appid.txt` (containing `1245620`) in the game folder yourself; the tool never writes there.
- **`OpenProcess failed` (error 5):** the process is protected (EAC) or you need to run from the same user account.
- **Stuck in `WAITING_FOR_WORLD` in-game:** run with `-v` and read `last_error`; it names the failing pointer/field.

## Soak test helper (spec V-06)
While `run -v` is going, in a second terminal: `python tools\soak_check.py` watches `output\telemetry-state.json`, prints
state changes, flags invalid JSON / out-of-range values / a stalled writer, and prints `RESULT: PASS|FAIL` on Ctrl+C.

## Tests
`pip install -r requirements-dev.txt && python -m pytest` – covers pointer-chain logic, validation, linked-list safety,
profile loading, JSON schema and safety constraints using a fake process memory (the Windows API layer itself needs a real game to test).

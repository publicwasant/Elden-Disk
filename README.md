# Elden Ring Telemetry (offline, read-only)

Launches Elden Ring **offline** (`eldenring.exe -eac-nop-loaded`) and writes live character data to
`output/telemetry-state.json`. Implements spec v1.2.1. Standard library only, Windows + 64-bit Python 3.11+.

## Guarantees
- Read-only: the only access mask requested is `PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION`.
- Nothing is written to the game folder (the logger refuses an output dir inside it).
- Never reads memory if EasyAntiCheat modules are loaded, or if the exe version has no profile.
- Any failed check (null pointer, unreadable memory, out-of-range value, cyclic/oversized effect list) discards the whole sample.
  Nothing is ever reported as `0` because a read failed.

## Quick start
1. Start the **Steam client** and log in (offline mode in Steam is fine).
2. `python -m elden_telemetry hash` → prints the **SHA-256** of your `eldenring.exe`.
3. Check or add a profile for your hash under `"profiles"` in `offsets.json`:
   - **If on 1.17.1:** The profile is already included by default.
   - **For new game patches:** Add a block with your hash as key, specifying `world_chr_man_rva` (base pointer) and offsets (`player_to_game_data`, `game_data`, `sp_effect`).
   - *(Until a matching profile is set, `run` reports `UNSUPPORTED_VERSION`. See details in [**Adding a profile Section**](README.md#adding-a-profile-once-per-game-patch)).*
4. `python -m elden_telemetry run -v`
   - launches the game offline, waits for the main module, then polls at 10 Hz
   - `-v` prints state changes and the reason for the last discarded sample
5. Read `output/telemetry-state.json` from any other program (schema: `elden_telemetry/telemetry.schema.json`).

Already started the game yourself with `-eac-nop-loaded`? Use `python -m elden_telemetry run --attach`
(same EAC/read-only checks apply). Ctrl+C stops the tool and leaves the game running.

## CLI commands

Run as `python -m elden_telemetry <command> [options]` from the project folder. Every command supports `-h` / `--help`.

### Commands at a glance

| Command   | Usage                                     | Description                                                                                      |
|-----------|-------------------------------------------|--------------------------------------------------------------------------------------------------|
| `run`     | `python -m elden_telemetry run [options]` | Launches (or attaches via `--attach`) and writes live telemetry to `output/telemetry-state.json` |
| `effects` | `python -m elden_telemetry effects [-q]`  | Live SpEffect viewer: streams active buffs and status effects to stdout                          |
| `hash`    | `python -m elden_telemetry hash`          | Prints the SHA-256 hash of `eldenring.exe` (used as profile key in `offsets.json`)               |

### Common recipes

| Goal                           | Command                                                         |
|--------------------------------|-----------------------------------------------------------------|
| Get exe hash for a new profile | `python -m elden_telemetry hash`                                |
| Launch game + write telemetry  | `python -m elden_telemetry run -v`                              |
| Attach to already running game | `python -m elden_telemetry run --attach -v`                     |
| Lower CPU / poll rate          | `python -m elden_telemetry run --hz 2`                          |
| View active buffs / SpEffects  | `python -m elden_telemetry effects -q`                          |
| Run soak test (V-06)           | Terminal A: `run -v` · Terminal B: `python tools/soak_check.py` |

**Full reference:** For full flag tables, execution logic, exit codes, and auxiliary scripts, see **[cli-commands.md](docs/cli-commands.md)**.

---

## Adding a profile (once per game patch)

A **profile** tells the tool memory offsets for a specific build of `eldenring.exe`. Without a matching profile in `offsets.json`, `run` stops with `UNSUPPORTED_VERSION` to prevent reading wrong memory addresses.

### Process overview

| Part  | Goal               | Cheat Engine / Tool Step                                                               |
|-------|--------------------|----------------------------------------------------------------------------------------|
| **A** | Preparation        | Get exe hash (`hash`), create profile skeleton in `offsets.json`, attach Cheat Engine  |
| **B** | Find runes address | Scan for current rune value, change runes in-game, scan again until 1 address remains  |
| **C** | Pointer scan       | Run Pointer Scan on runes address to find static pointer path (`Base + RVA` → offsets) |
| **D** | Fill profile       | Put RVA and offsets into `offsets.json`, verify stats against in-game Status screen    |
| **E** | Verify buffs       | Confirm SpEffect layout with `effects -q`, complete `effects.json`                     |
| **F** | Finalize           | Back up configuration, test with `run -v`                                              |

### Key profile fields (`offsets.json`)

| Field                            | Description                                       | Example (1.17.1)   |
|----------------------------------|---------------------------------------------------|--------------------|
| `world_chr_man_rva`              | Pointer Scan Base Address (`eldenring.exe + RVA`) | `"0x3B16E30"`      |
| `world_chr_man_to_player`        | Pointer Offset 0                                  | `"0x0"`            |
| `player_to_game_data`            | Pointer Offset 1                                  | `"0x580"`          |
| `game_data.runes`                | Pointer Offset 2 (Runes)                          | `"0x6C"`           |
| `game_data.level`, `.attributes` | Stat offsets verified against Status screen       | `"0x68"`, `"0x3C"` |
| `player_to_sp_effect`            | Pointer to SpEffect list (buffs)                  | `"0x178"`          |

*If `sp_effect` is omitted or incomplete, stats telemetry still works (`buffs_supported` becomes `false`).*

**Full step-by-step guide:** **[adding-a-profile.md](docs/adding-a-profile.md)** — Includes Cheat Engine instructions, checkpoints, and troubleshooting for first-timers.

---

## States
| `state`                      | Meaning                                                     |
|------------------------------|-------------------------------------------------------------|
| `WAITING_FOR_PROCESS`        | game not running / not found                                |
| `EAC_ACTIVE`, `EAC_DETECTED` | EAC loaded; tool exits (code 3) without reading             |
| `UNSUPPORTED_VERSION`        | no complete profile for this exe hash; tool exits (code 2)  |
| `WAITING_FOR_WORLD`          | title screen, loading, or a check failed (see `last_error`) |
| `CONNECTED`                  | all checks passed; `character` filled                       |
| `DISCONNECTED`               | game exited                                                 |

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

# CLI Commands Reference

This document provides a comprehensive reference for all command-line interface (CLI) commands, flags, exit codes, and utility scripts in **EldenDisk**.

## Overview & Requirements

Run commands as:
```cmd
python -m eldendisk <command> [options]
```
from the root folder of the project (containing the `eldendisk/` package directory).

- **OS:** Windows 10/11 (64-bit)
- **Runtime:** 64-bit Python 3.11+
- **Help flag:** `-h` or `--help` works on the main module as well as on every subcommand.

---

## Commands at a Glance

| Command               | Primary Function                                                       | Game State Required                                       | Steam Client Required   |
|-----------------------|------------------------------------------------------------------------|-----------------------------------------------------------|-------------------------|
| [`run`](#run)         | Launches/attaches to game, polls memory, writes `disk-state.json`      | Not running (launch mode) or running offline (`--attach`) | Required in launch mode |
| [`effects`](#effects) | Live SpEffect viewer: monitors active effects/buffs                    | Running offline (in-world for useful data)                | Not needed              |
| [`animations`](#animations) | Live character animation state viewer: monitors animation IDs    | Running offline (in-world for useful data)                | Not needed              |
| [`hash`](#hash)       | Calculates SHA-256 hash of `eldenring.exe` for profile key             | Any (reads file on disk)                                  | Not needed              |

---

## Command Reference

### `run`

`python -m eldendisk run [options]`

Launches Elden Ring offline (or attaches to an already-running process), polls character memory at the specified frequency (default: 60FPS), and writes snapshots to `output/disk-state.json` using Event-Driven Persistence.

#### Flags & Options

| Flag              | Value Type     | Default                  | Description                                                                                                                                                                                                                                                                                                 |
|-------------------|----------------|--------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `--attach`        | switch         | off (launch mode)        | Attach to an existing `eldenring.exe` process instead of launching a new instance. Waits (`WAITING_FOR_PROCESS`) if the process is not yet running. Performs identical EAC and read-only memory checks.                                                                                                     |
| `--game-dir DIR`  | path           | auto-detect              | Path to folder containing `eldenring.exe`. Auto-detection reads Windows Registry `SteamPath` + `libraryfolders.vdf` → `steamapps\common\ELDEN RING\Game`. Required if auto-detect fails. (In `--attach` mode, a failed auto-detect is ignored and the path is retrieved directly from the running process). |
| `--out DIR`       | path           | `<project>/output`       | Output directory where `disk-state.json` is saved (created automatically if missing). **Refused with an error if located inside the game folder.**                                                                                                                                                         |
| `--offsets FILE`  | path           | `<project>/offsets.json` | Path to profiles JSON file, keyed by `eldenring.exe` SHA-256 hash.                                                                                                                                                                                                                                          |
| `--effects FILE`  | path           | `<project>/chr_state_ids.json` | Path to unified state IDs lookup table (`chr_state_ids.json` or legacy `effects.json`). A missing file is treated as empty tables; a malformed file triggers an error. |
| `--hz N`          | number (1–120) | `60`                     | Sampling rate in polls per second (decimals allowed, e.g. `60.0`). Values outside 1–120 trigger a usage error.                                                                                                                                                                                               |
| `-v`, `--verbose` | switch         | off                      | Enable verbose logging to stderr: logs state changes and the reason for discarded samples (`last_error`).                                                                                                                                                                                                   |
| `-h`, `--help`    | switch         | —                        | Display help message for `run`.                                                                                                                                                                                                                                                                             |

#### Execution Flow & Safety Logic

1. **Initialization:**
   - *Launch Mode:* Launches `eldenring.exe -eac-nop-loaded` with `SteamAppId` / `SteamGameId` set in the child environment.
   - *Attach Mode:* Searches for active `eldenring.exe` process.
2. **Module Verification:** Waits up to 60 seconds for the main `eldenring.exe` module to load.
3. **EAC Check:** Refuses to proceed and exits if EasyAntiCheat modules (`easyanticheat.dll`, `eac_sound_x64.dll`, etc.) are detected.
4. **Profile Loading:** Hashes `eldenring.exe` and loads the matching profile from `offsets.json`. If no matching profile exists, sets state to `UNSUPPORTED_VERSION` and exits.
5. **Polling Loop (60FPS Event-Driven):**
   - Checks active window focus (`is_window_active`). If out of focus, transitions to `IDLE` state and pauses reading/writing.
   - Polls memory at `--hz` frequency.
   - Re-scans process modules for EAC every 2 seconds.
   - Performs state differential check: atomically writes `output/disk-state.json` only when state/data changes or active timed buff durations update.
6. **Termination:** Exits when the game closes, if EAC is loaded/detected, on unrecoverable error, or on Ctrl+C (leaving the game process running).

---

### `effects`

`python -m eldendisk effects [options]`

Attaches to a running `eldenring.exe` instance (never launches the game) and streams live active SpEffects (buffs, debuffs, status effects) to standard output.

#### Flags & Options

| Flag             | Value Type | Default                        | Description                                                                                                           |
|------------------|------------|--------------------------------|-----------------------------------------------------------------------------------------------------------------------|
| `--offsets FILE` | path       | `<project>/offsets.json`       | Path to profiles JSON file. The active profile must contain a complete `sp_effect` block.                             |
| `--effects FILE` | path       | `<project>/chr_state_ids.json` | Path to state configuration file (`chr_state_ids.json`).                                                               |
| `-q`, `--quiet`  | switch     | off                            | Hide short-lived internal effects (`0 <= duration < 1s`). Retains permanent buffs (`duration == -1`) and timed buffs. |
| `-h`, `--help`   | switch     | —                              | Display help message for `effects`.                                                                                   |

---

### `animations`

`python -m eldendisk animations [options]`

Attaches to a running `eldenring.exe` instance and streams character animation state ID transitions with timestamps to standard output in real-time.

#### Flags & Options

| Flag             | Value Type | Default                        | Description                                                                                 |
|------------------|------------|--------------------------------|---------------------------------------------------------------------------------------------|
| `--offsets FILE` | path       | `<project>/offsets.json`       | Path to profiles JSON file. The active profile must contain a complete `anim` block.        |
| `--effects FILE` | path       | `<project>/chr_state_ids.json` | Path to state configuration file (`chr_state_ids.json`).                                   |
| `-q`, `--quiet`  | switch     | off                            | Quiet mode.                                                                                 |
| `-h`, `--help`   | switch     | —                              | Display help message for `animations`.                                                      |

---

### `hash`

`python -m eldendisk hash [options]`

Calculates and prints the SHA-256 hash of the target `eldenring.exe`.

---

## Exit Codes

| Code  | Meaning               | Details                                                                                                                                                                                                                |
|-------|-----------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `0`   | Normal Exit           | Game closed cleanly (`DISCONNECTED`), `effects` stopped by user, or `hash` completed successfully.                                                                                                                     |
| `1`   | Error                 | Unrecoverable error (e.g., game folder not found, main module timed out after 60s, game not running for `effects`, output directory inside game folder, malformed `effects.json`, unsupported OS/Python architecture). |
| `2`   | Profile / Usage Error | `run`: `UNSUPPORTED_VERSION` (no profile matching exe hash in `offsets.json`). Also returned by Python `argparse` for invalid flags or out-of-range `--hz`.                                                            |
| `3`   | EAC Detected          | `run`: `EAC_ACTIVE` or `EAC_DETECTED`. Tool refused to run due to EasyAntiCheat presence.                                                                                                                              |
| `130` | Interrupted           | Interrupted by user (`Ctrl+C`).                                                                                                                                                                                        |

---

## Other Utility Scripts

### Soak Test Helper (`tools/soak_check.py`)

Watches `disk-state.json` to validate continuous compliance with Specification V-06 (stability over long sessions).

```cmd
python tools/soak_check.py [path] [--interval S]
```

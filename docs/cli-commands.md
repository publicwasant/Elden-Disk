# CLI Commands Reference

This document provides a comprehensive reference for all command-line interface (CLI) commands, flags, exit codes, and utility scripts in **Elden Ring Telemetry**.

## Overview & Requirements

Run commands as:
```cmd
python -m elden_telemetry <command> [options]
```
from the root folder of the project (containing the `elden_telemetry/` package directory).

- **OS:** Windows 10/11 (64-bit)
- **Runtime:** 64-bit Python 3.11+
- **Help flag:** `-h` or `--help` works on the main module as well as on every subcommand.

---

## Commands at a Glance

| Command               | Primary Function                                                       | Game State Required                                       | Steam Client Required   |
|-----------------------|------------------------------------------------------------------------|-----------------------------------------------------------|-------------------------|
| [`run`](#run)         | Launches/attaches to game, polls memory, writes `telemetry-state.json` | Not running (launch mode) or running offline (`--attach`) | Required in launch mode |
| [`effects`](#effects) | Live SpEffect viewer: monitors active effects/buffs                    | Running offline (in-world for useful data)                | Not needed              |
| [`hash`](#hash)       | Calculates SHA-256 hash of `eldenring.exe` for profile key             | Any (reads file on disk)                                  | Not needed              |

---

## Command Reference

### `run`

`python -m elden_telemetry run [options]`

Launches Elden Ring offline (or attaches to an already-running process), polls character memory at the specified frequency, and writes telemetry snapshots to `output/telemetry-state.json`.

#### Flags & Options

| Flag              | Value Type    | Default                  | Description                                                                                                                                                                                                                                                                                                 |
|-------------------|---------------|--------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `--attach`        | switch        | off (launch mode)        | Attach to an existing `eldenring.exe` process instead of launching a new instance. Waits (`WAITING_FOR_PROCESS`) if the process is not yet running. Performs identical EAC and read-only memory checks.                                                                                                     |
| `--game-dir DIR`  | path          | auto-detect              | Path to folder containing `eldenring.exe`. Auto-detection reads Windows Registry `SteamPath` + `libraryfolders.vdf` → `steamapps\common\ELDEN RING\Game`. Required if auto-detect fails. (In `--attach` mode, a failed auto-detect is ignored and the path is retrieved directly from the running process). |
| `--out DIR`       | path          | `<project>/output`       | Output directory where `telemetry-state.json` is saved (created automatically if missing). **Refused with an error if located inside the game folder.**                                                                                                                                                     |
| `--offsets FILE`  | path          | `<project>/offsets.json` | Path to profiles JSON file, keyed by `eldenring.exe` SHA-256 hash.                                                                                                                                                                                                                                          |
| `--effects FILE`  | path          | `<project>/effects.json` | Path to SpEffect ID lookup table. A missing file is treated as empty tables; a malformed file triggers an error.                                                                                                                                                                                            |
| `--hz N`          | number (1–30) | `10`                     | Sampling rate in polls per second (decimals allowed, e.g. `2.5`). Values outside 1–30 trigger a usage error.                                                                                                                                                                                                |
| `-v`, `--verbose` | switch        | off                      | Enable verbose logging to stderr: logs state changes and the reason for discarded samples (`last_error`).                                                                                                                                                                                                   |
| `-h`, `--help`    | switch        | —                        | Display help message for `run`.                                                                                                                                                                                                                                                                             |

#### Execution Flow & Safety Logic

1. **Initialization:**
   - *Launch Mode:* Launches `eldenring.exe -eac-nop-loaded` with `SteamAppId` / `SteamGameId` set in the child environment.
   - *Attach Mode:* Searches for active `eldenring.exe` process.
2. **Module Verification:** Waits up to 60 seconds for the main `eldenring.exe` module to load.
3. **EAC Check:** Refuses to proceed and exits if EasyAntiCheat modules (`easyanticheat.dll`, `eac_sound_x64.dll`, etc.) are detected.
4. **Profile Loading:** Hashes `eldenring.exe` and loads the matching profile from `offsets.json`. If no matching profile exists, sets state to `UNSUPPORTED_VERSION` and exits.
5. **Polling Loop:**
   - Polls memory at `--hz` frequency.
   - Re-scans process modules for EAC every 2 seconds.
   - Atomically writes `output/telemetry-state.json` upon successful read.
6. **Termination:** Exits when the game closes, if EAC is loaded/detected, on unrecoverable error, or on Ctrl+C (leaving the game process running).

---

### `effects`

`python -m elden_telemetry effects [options]`

Attaches to a running `eldenring.exe` instance (never launches the game) and streams live active SpEffects (buffs, debuffs, status effects) to standard output.

#### Flags & Options

| Flag             | Value Type | Default                  | Description                                                                                                           |
|------------------|------------|--------------------------|-----------------------------------------------------------------------------------------------------------------------|
| `--offsets FILE` | path       | `<project>/offsets.json` | Path to profiles JSON file. The active profile must contain a complete `sp_effect` block.                             |
| `-q`, `--quiet`  | switch     | off                      | Hide short-lived internal effects (`0 <= duration < 1s`). Retains permanent buffs (`duration == -1`) and timed buffs. |
| `-h`, `--help`   | switch     | —                        | Display help message for `effects`.                                                                                   |

#### Output Behavior

- Initial output: `--- N effects now active ---` followed by one line per active effect (`id | duration | timer`).
- Dynamic updates:
  - `+ id | duration | timer` (effect applied)
  - `- id` (effect removed)
- While world/character is not loaded: prints `[waiting] <reason>`.
- Does not read `effects.json` and writes no files.
- Press `Ctrl+C` or exit the game to stop.

---

### `hash`

`python -m elden_telemetry hash [options]`

Calculates and prints the SHA-256 hash of the target `eldenring.exe`.

#### Flags & Options

| Flag             | Value Type | Default     | Description                                |
|------------------|------------|-------------|--------------------------------------------|
| `--game-dir DIR` | path       | auto-detect | Path to folder containing `eldenring.exe`. |
| `-h`, `--help`   | switch     | —           | Display help message for `hash`.           |

#### Output

Prints a single 64-character hexadecimal SHA-256 hash to standard output. Use this hash as the key for new profiles in `offsets.json`.

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

## Fixed Behavior (Non-Configurable)

| Feature                 | Behavior                                                                                                                                               |
|-------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Output File**         | `<--out>/telemetry-state.json` written via temporary file `telemetry-state.json.tmp` with atomic replace (retries 5 times × 20ms if file lock occurs). |
| **Path Resolution**     | Relative CLI paths resolve against the current working directory.                                                                                      |
| **Module Timeout**      | 60 seconds maximum wait time for `eldenring.exe` module initialization.                                                                                |
| **EAC Re-scan**         | Process module list is re-scanned for EAC every 2.0 seconds while polling.                                                                             |
| **Safety Cap**          | Maximum 512 entries per linked list sample (samples exceeding this or containing cyclic pointers are discarded).                                       |
| **`effects` Poll Rate** | Fixed at 0.5 seconds (2 Hz).                                                                                                                           |
| **Memory Rights**       | Opens process with `PROCESS_VM_READ                                                                                                                    | PROCESS_QUERY_LIMITED_INFORMATION` rights only (read-only access). |

---

## Other Utility Scripts

### Soak Test Helper (`tools/soak_check.py`)

Watches `telemetry-state.json` to validate continuous compliance with Specification V-06 (stability over long sessions).

```cmd
python tools/soak_check.py [path] [--interval S]
```

- **Arguments:**
  - `[path]`: Path to telemetry state JSON (default: `<project>/output/telemetry-state.json`).
  - `--interval S`: Seconds between file reads (default: `0.1`).
- **Features:** Monitors for invalid JSON, out-of-range attribute values, inconsistent `rune_delta`, impossible buff timers, or a stalled writer. Press `Ctrl+C` to display summary and pass/fail result (`RESULT: PASS` / `RESULT: FAIL`).

### Laboratory Scripts (`labs/`)

- `python labs/toy_game.py`: Simulated game server raising dummy rune values every second.
- `python labs/toy_reader.py PID ROOT`: Memory reader inspecting dummy process pointers (`ROOT -> +0 -> +0x580`).

---

## Common Recipes & Examples

| Scenario                                    | Command                                                                                        |
|---------------------------------------------|------------------------------------------------------------------------------------------------|
| **Get SHA-256 for a new patch profile**     | `python -m elden_telemetry hash`                                                               |
| **Run telemetry with live stderr logging**  | `python -m elden_telemetry run -v`                                                             |
| **Attach to game started manually offline** | `python -m elden_telemetry run --attach -v`                                                    |
| **Reduce CPU overhead (lower poll rate)**   | `python -m elden_telemetry run --hz 2`                                                         |
| **Save telemetry to custom directory**      | `python -m elden_telemetry run --out D:\overlay-data`                                          |
| **Inspect SpEffect IDs for active buffs**   | `python -m elden_telemetry effects -q`                                                         |
| **Use alternative offsets file**            | `python -m elden_telemetry run --offsets D:\profiles\offsets.json`                             |
| **Run 30-minute Soak Test (V-06)**          | *Terminal 1:* `python -m elden_telemetry run -v`<br>*Terminal 2:* `python tools/soak_check.py` |

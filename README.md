# EldenDisk Tool

> **Offline, Read-Only Memory Read Service & Standalone Executable for Elden Ring**  
> **Version:** `1.5.1` | **Spec Version:** `1.5.1` | **Platform:** Windows 10/11 (x64) | **Runtime:** Python 3.11+ or Standalone Executable

Launches Elden Ring **offline** (`eldenring.exe -eac-nop-loaded`) and writes real-time character state snapshots to `output/disk-state.json`. EldenDisk is designed from the ground up for high reliability, zero anti-cheat risk, minimal CPU/disk footprint, and effortless distribution.

---

## 🔑 Core Guarantees & Safety Architecture

1. **Strictly Read-Only Memory Access:** Requests only `PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION`. Performs zero memory writes (`WriteProcessMemory`), allocations, thread injections, or code modifications.
2. **Zero Disk Changes in Game Folder:** Never creates, modifies, renames, or deletes any file inside the Elden Ring installation directory.
3. **Anti-Cheat Guard (EAC Safe):** Continuously scans loaded modules. Refuses to attach and immediately exits if EasyAntiCheat modules (`easyanticheat.dll`, etc.) are present.
4. **Event-Driven Persistence Architecture:** Polling runs in RAM at a locked 60FPS. Atomic disk writes (`disk-state.json`) occur **only** when state data changes or active timed buff timers update, eliminating unnecessary SSD wear.
5. **Window Focus Detection (`IDLE` State):** Uses Windows API focus detection (`GetForegroundWindow`). Pauses polling and disk writes when the game is unfocused, preserving CPU resources while retaining character data.
6. **Correct-or-Silent Validation:** Discards incomplete or malformed memory samples (null pointers, unreadable addresses, out-of-range stats) and safely retains the last known valid state snapshot.
7. **Standalone Executable Distribution:** Compiles into a zero-dependency, single-file executable (`./dist/eldendisk.exe`) via PyInstaller.

---

## ⚡ Quick Start

### Prerequisites
1. Windows 10 or 11 (64-bit).
2. Steam Client running (Offline mode in Steam is supported).
3. Supported Elden Ring executable (Version 1.17.1 included out-of-the-box).

### 1. Running via Python
```cmd
# Get exe SHA-256 hash
python -m eldendisk hash

# Launch game offline + write state (verbose mode)
python -m eldendisk run -v

# Or attach to an already running offline game instance
python -m eldendisk run --attach -v
```

### 2. Building Standalone Executable (`.exe`)
```cmd
# Build single embedded executable into ./dist/eldendisk.exe
python -m eldendisk build -c -em
```

### 3. Running Standalone Executable
```cmd
# Launch game offline + write state via compiled binary
.\dist\eldendisk.exe run -v
```

### 4. Running End-to-End Pipeline (Test + Build + Run)
```cmd
# Run pre-check unit tests, build .exe, and verify execution
python code/tools/dev_pipeline.py
```

---

## 🛠️ CLI Commands & Recipes

Run via `python -m eldendisk <command> [options]` or `eldendisk.exe <command> [options]`. Every command supports `-h` / `--help`.

### Commands at a Glance

| Command | Usage | Description |
|:---|:---|:---|
| [`run`](#run) | `python -m eldendisk run [options]` | Launches (or attaches via `--attach`) and writes live state to `disk-state.json` |
| [`effects`](#effects) | `python -m eldendisk effects [-q]` | Live SpEffect viewer: streams active buffs and status effects to stdout |
| [`animations`](#animations) | `python -m eldendisk animations [-q]` | Live character animation state viewer: streams active animation IDs to stdout |
| [`hash`](#hash) | `python -m eldendisk hash` | Calculates SHA-256 hash of `eldenring.exe` (used as profile key in `offsets.json`) |
| [`build`](#build) | `python -m eldendisk build [options]` | Compiles project into standalone executable (`./dist/eldendisk.exe`) |

### Common Recipes

| Goal | Command |
|:---|:---|
| Get exe hash for a new game patch | `python -m eldendisk hash` |
| Launch game offline + write state | `python -m eldendisk run -v` |
| Attach to already running offline game | `python -m eldendisk run --attach -v` |
| Custom sampling rate (e.g. 30FPS) | `python -m eldendisk run --hz 30` |
| Stream active buffs / SpEffects | `python -m eldendisk effects -q` |
| Stream animation state transitions | `python -m eldendisk animations -q` |
| Build single embedded `.exe` file | `python -m eldendisk build -c -em` |
| Build `.exe` + external JSON configs | `python -m eldendisk build -c` |
| Run E2E pipeline (test + build + run) | `python code/tools/dev_pipeline.py --dry-run` |
| Run soak stability test (V-06) | Terminal A: `run -v` · Terminal B: `python code/tools/soak_check.py` |

**Full References:**  
- For Python CLI reference, see **[docs/cli-commands.md](docs/cli-commands.md)**  
- For Standalone Executable CLI reference, see **[docs/cli-commands-exe.md](docs/cli-commands-exe.md)**  

---

## 📦 Standalone Executable Build & E2E Pipeline

Version 1.5.1 introduces native compilation and end-to-end pipeline automation.

### Build Subcommand (`build`)
```cmd
python -m eldendisk build [OPTIONS]
```

- **Single Embedded Binary (`-em` / `--embed-configs`):**
  Embeds `offsets.json`, `chr_state_ids.json`, and `disk.schema.json` directly inside `eldendisk.exe`. Generates a single file in `./dist/eldendisk.exe` with no external dependencies.
  ```cmd
  python -m eldendisk build -c -em
  ```
- **Modular Distribution (External Configs):**
  Compiles `eldendisk.exe` and copies editable `offsets.json` and `chr_state_ids.json` into `./dist/` alongside the executable.
  ```cmd
  python -m eldendisk build -c
  ```

### End-to-End Development Pipeline (`code/tools/dev_pipeline.py`)
Automates pre-check unit testing, compilation, and state verification in a single command:
```cmd
python code/tools/dev_pipeline.py
```
- **Options:**
  - `--dry-run`: Runs tests, builds binary, and executes `--help` check on the compiled binary.
  - `--no-embed`: Disables config embedding during build step.
  - `--skip-tests`: Skips pre-check unit tests.

---

## 📊 Connection State Machine

| State | Description | Character Payload |
|:---|:---|:---:|
| `WAITING_FOR_PROCESS` | Game process not running or not found. | Retained last known |
| `EAC_ACTIVE` / `EAC_DETECTED` | EasyAntiCheat present; attachment refused for safety. | Retained last known |
| `UNSUPPORTED_VERSION` | Game SHA-256 hash not matched in `offsets.json`. | Retained last known |
| `WAITING_FOR_WORLD` | Process attached, but game pointers/world not initialized. | Retained last known |
| `CONNECTED` | Polling active; real-time character state live. | Live full object |
| `DISCONNECTED` | Game process closed cleanly or crashed. | Retained last known |
| `IDLE` | Game window out of focus; polling paused to save CPU. | Retained last known |

---

## 🎮 Adding a Profile (New Game Patches)

When FromSoftware updates Elden Ring, memory offsets change. Adding a profile allows EldenDisk to support the new game patch without updating source code.

### Summary Table

| Field | Description | Example (v1.17.1) |
|:---|:---|:---|
| `world_chr_man_rva` | Base Pointer scan RVA address (`eldenring.exe + RVA`) | `"0x3B16E30"` |
| `world_chr_man_to_player` | Pointer Offset 0 (`PlayerIns`) | `"0x0"` |
| `player_to_game_data` | Pointer Offset 1 (`PlayerGameData`) | `"0x580"` |
| `game_data.level`, `.attributes` | Level and Attribute stat offsets | `"0x68"`, `"0x3C"` |
| `game_data.runes` | Rune offset | `"0x6C"` |
| `vitals` | HP (`0x138`), FP (`0x148`), Stamina (`0x154`) offsets | `"0x190"`, `"0x0"`, `"0x138"` |
| `player_to_sp_effect` | SpEffect linked list head offset | `"0x178"` |

**Full Step-by-Step Guide:** **[docs/adding-a-profile.md](docs/adding-a-profile.md)** — Includes Cheat Engine scanning checkpoints and step-by-step instructions.

---

## 🧪 Testing & Quality Assurance

### Automated Unit Tests
Includes a comprehensive test suite using mock memory structures, covering pointer chains, linked list safety, schema validation, and state machines:
```cmd
python -m pytest
```

### Soak Stability Test (Spec V-06)
Monitors long-term state output stability and schema compliance:
```cmd
# Terminal 1: Run logger
python -m eldendisk run -v

# Terminal 2: Run soak validator
python code/tools/soak_check.py
```

---

## ❓ Troubleshooting

- **Steam AppId Error on Direct Launch:** EldenDisk passes `SteamAppId=1245620` in the child environment. If Steam fails to launch the game, create a `steam_appid.txt` file containing `1245620` inside the game folder (EldenDisk never modifies the game folder directly).
- **`OpenProcess failed` (Error 5):** The process is protected by EasyAntiCheat, or EldenDisk is running under a different Windows user account.
- **Stuck in `WAITING_FOR_WORLD`:** Run with `-v` flag to view `last_error` diagnostic output detailing which pointer failed to resolve.

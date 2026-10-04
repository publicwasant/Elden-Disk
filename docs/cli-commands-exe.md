# Standalone Executable CLI Commands Reference (`eldendisk.exe`)

This document provides the reference for command-line interface (CLI) interactions with the standalone executable build of **EldenDisk** (`eldendisk.exe`).

## Overview & Execution Context

Run commands directly via the compiled binary:
```cmd
eldendisk.exe <command> [options]
```
or from standard powershell/cmd:
```cmd
.\build\dist\<version>\eldendisk.exe <command> [options]
```

- **OS:** Windows 10/11 (64-bit)
- **Runtime Environment:** Standalone binary (No local Python installation required).
- **Help Flag:** `-h` or `--help` is supported on the main executable and all subcommands.

---

## Commands at a Glance

| Command | Primary Function | Game State Required | Steam Client Required |
|:---|:---|:---|:---|
| [`run`](#run) | Launches or attaches to game, polls memory, writes `disk-state.json` | Not running (launch mode) or running offline (`--attach`) | Required in launch mode |
| [`effects`](#effects) | Live SpEffect viewer: streams active effects/buffs to stdout | Running offline | Not needed |
| [`animations`](#animations) | Live character animation state viewer: streams animation IDs to stdout | Running offline | Not needed |
| [`hash`](#hash) | Calculates SHA-256 hash of `eldenring.exe` for profile verification | Any (reads file on disk) | Not needed |

---

## Command Reference

### `run`

```cmd
eldendisk.exe run [options]
```

Launches Elden Ring offline (or attaches to an active offline process), polls memory at 60FPS, and writes telemetry snapshots to `disk-state.json`.

#### Flags & Options

| Flag | Type | Default | Description |
|:---|:---:|:---|:---|
| `--attach` | switch | off | Attach to an existing `eldenring.exe` process instead of launching a new instance. |
| `--game-dir DIR` | path | auto-detect | Path to directory containing `eldenring.exe`. |
| `--out DIR` | path | `./output` | Output directory where `disk-state.json` is saved. |
| `--offsets FILE` | path | `./offsets.json` | Path to profiles JSON file. In embedded builds (`--embed-configs`), defaults to bundled resources if external file is missing. |
| `--effects FILE` | path | `./chr_state_ids.json` | Path to state IDs configuration file (`chr_state_ids.json` or `effects.json`). |
| `--hz N` | number (1–120) | `60` | Polling rate in samples per second. |
| `-v`, `--verbose` | switch | off | Enable verbose diagnostic logging to stderr. |
| `-h`, `--help` | switch | — | Display command help. |

---

### `effects`

```cmd
eldendisk.exe effects [options]
```

Attaches to active `eldenring.exe` and streams active character SpEffect IDs and durations in real-time.

#### Flags & Options

| Flag | Type | Default | Description |
|:---|:---:|:---|:---|
| `--offsets FILE` | path | `./offsets.json` | Path to profiles JSON file. |
| `--effects FILE` | path | `./chr_state_ids.json` | Path to state IDs JSON file. |
| `-q`, `--quiet` | switch | off | Hide internal short-duration effects (< 1s). |
| `-h`, `--help` | switch | — | Display help. |

---

### `animations`

```cmd
eldendisk.exe animations [options]
```

Attaches to active `eldenring.exe` and streams animation state ID transitions with timestamps.

#### Flags & Options

| Flag | Type | Default | Description |
|:---|:---:|:---|:---|
| `--offsets FILE` | path | `./offsets.json` | Path to profiles JSON file. |
| `--effects FILE` | path | `./chr_state_ids.json` | Path to state IDs JSON file. |
| `-q`, `--quiet` | switch | off | Quiet mode. |
| `-h`, `--help` | switch | — | Display help. |

---

### `hash`

```cmd
eldendisk.exe hash [options]
```

Calculates and prints the SHA-256 hash of the target `eldenring.exe`.

---

## Exit Codes

| Exit Code | Meaning | Details |
|:---:|:---|:---|
| `0` | Success / Normal Exit | Game closed cleanly, viewer command stopped, or hash printed. |
| `1` | Error | Unrecoverable error (file not found, process timeout, IO error). |
| `2` | Profile / Usage Error | `UNSUPPORTED_VERSION` (hash not in `offsets.json`) or invalid argument flags. |
| `3` | EAC Detected | EasyAntiCheat detected; process attachment refused. |
| `130` | Interrupted | User pressed `Ctrl+C`. |

---

## Configuration File Resolution in Standalone Mode

When running `eldendisk.exe`:
1. **External Configs (Default):** The application looks for `offsets.json` and `chr_state_ids.json` in the same directory as `eldendisk.exe`. This allows modifying offsets or state IDs without re-compiling the executable.
2. **Embedded Configs (`--embed-configs` build):** If built with embedded configurations, `eldendisk.exe` reads fallback configurations directly from its internal temporary bundle directory (`sys._MEIPASS`) when external JSON files are absent.

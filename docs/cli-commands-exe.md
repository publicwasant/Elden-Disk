# Standalone Executable CLI Commands Reference (`eldendisk.exe`)

Complete reference for command-line interface interactions when running the compiled standalone binary of **EldenDisk** (`eldendisk.exe`).

---

## Architecture Overview: Host / Client Workflow

> [!IMPORTANT]
> **🌌 Parallel Dimension Guarantee (100% Clean Save Safety):**  
> All memory edits exist **only during the active offline session (a temporary parallel dimension)**. When the game closes, `run` restores your live save folder byte-for-byte back to the exact pre-session snapshot taken before the game opened. Nothing from your sandbox modifications ever pollutes your real character save or account.

EldenDisk uses a **Host / Client Architecture**:

1. **Host Session (`run`):**
   - Automatically takes a clean save snapshot in `./backup/vault` before starting.
   - Remembers `--save-dir` in Windows Registry (`HKCU\Software\EldenDisk`) after first use (zero config files on disk!).
   - Launches `eldenring.exe` offline, writes live game state (`./output/disk-state.json`), and automatically restores the clean save when the game closes.
2. **On-The-Fly Memory Writer Client (`sandbox`):**
   - Does NOT launch the game or block.
   - Attaches on-the-fly to the active game process, applies `--set` or `--refill` memory edits instantly while you play, prints confirmation if `-v` is set, and terminates immediately (`[end]`).
   - Runs **100% silently** without output when `-v` is omitted.

---

## Subcommands

### 1. `run` (Host Launcher & Save Guard)

```commandline
eldendisk.exe run [options]
```

Launches Elden Ring offline with pre-session save protection, streams real-time game state to `disk-state.json`, and restores the clean save on exit.

#### Flags & Options

| Flag | Value Type | Default | Description |
|:---|:---:|:---|:---|
| `--save-dir DIR` | path | auto / Windows Registry | Path to live save folder (`%APPDATA%\EldenRing\<SteamID64>`). Remembered in Windows Registry after first use. |
| `--game-dir DIR` | path | auto-detect | Path to folder containing `eldenring.exe`. Auto-detected via Steam if omitted. |
| `--vault DIR` | path | `./backup/vault` | Directory where save snapshots and `PENDING_RESTORE.json` are stored. |
| `--attach` | switch | off | Attach to an existing `eldenring.exe` process (read-only mode). |
| `--out DIR` | path | `./output` | Output directory for `disk-state.json`. |
| `--offsets FILE` | path | `./offsets.json` | Path to offsets configuration file. |
| `--effects FILE` | path | `./chr_state_ids.json` | Path to state IDs configuration file. |
| `--hz N` | float (1–120) | `60.0` | Polling rate in samples per second. |
| `--timer-interval SEC` | float (≥0) | `0.5` | Minimum seconds between writes that change only a buff countdown. |
| `--no-idle` | switch | off | Continue polling when game window loses focus. |
| `-v`, `--verbose` | switch | off | Print detailed diagnostics to stderr (including `[vault]` backup/restore log lines). |

#### Expected Output Example (with `-v`)

```commandline
.\eldendisk.exe run --save-dir "C:\Users\<User>\AppData\Roaming\EldenRing\76561198296924569" -v
```

```commandline
[config] offsets=offsets.json (embedded)
[config] effects=chr_state_ids.json (embedded)
state -> PREFLIGHT
state -> SNAPSHOTTING
[vault] backup save C:\Users\<User>\AppData\Roaming\EldenRing\76561198296924569 (steamID: 76561198296924569) to D:\...\backup\vault\20261006-120000
snapshot 20261006-120000: 2 file(s) verified
state -> RUNNING
[CONNECTED]
...
(when game exits)
state -> RESTORING
[vault] restored save from D:\...\backup\vault\20261006-120000 to C:\Users\<User>\AppData\Roaming\EldenRing\76561198296924569
verification passed: [vault] restore verified; save folder is byte-identical to snapshot
state -> CLEANUP
state -> IDLE
```

---

### 2. `effects` (Live SpEffect Stream Viewer)

```commandline
eldendisk.exe effects [options]
```

Attaches to active offline `eldenring.exe` process and streams character SpEffect IDs, total duration, and remaining timers in real-time. Designed for discovering SpEffect IDs for mapping in `chr_state_ids.json`.

| Flag | Value Type | Default | Description |
|:---|:---:|:---|:---|
| `--offsets FILE` | path | `./offsets.json` | Path to profiles JSON file. |
| `-q`, `--quiet` | switch | off | Hide short-lived internal effects (< 1s duration); keeps permanent (-1) and timed buffs. |

#### Expected Output Example

```commandline
.\eldendisk.exe effects -q
```

```commandline
Ctrl+C to stop. Format: id | duration | timer   (+ = appeared, - = disappeared)
--- 2 effects now active ---
      311100 |     -1.00 |       0.00
      100100 |     80.00 |      45.20
+     100200 |     30.00 |      30.00
-     100200
```

---

### 3. `animations` (Live Character Animation State Viewer)

```commandline
eldendisk.exe animations [options]
```

Attaches to active offline `eldenring.exe` process and streams character animation ID state transitions with timestamps in real-time. Designed for mapping character action/animation IDs in `chr_state_ids.json`.

| Flag | Value Type | Default | Description |
|:---|:---:|:---|:---|
| `--offsets FILE` | path | `./offsets.json` | Path to profiles JSON file. |

#### Expected Output Example

```commandline
.\eldendisk.exe animations
```

```commandline
Ctrl+C to stop. Format: id | name
--- Animation active ---
  2020210 | Sprint
  0000000 | Idle
```

---

### 4. `sandbox` (On-The-Fly Memory Writer Client)

```commandline
eldendisk.exe sandbox [options]
```

Attaches on-the-fly to the active game running under `run`, applies memory edits instantly, and terminates immediately (`[end]`).

Edits are applied **once** (not held); run the command again to re-apply (e.g. `--refill hp,fp,stamina` after a fight). It needs the session of a running `run` (same `--vault`) and exits with code `5` without writing when there is none, when the running `eldenring.exe` differs from the one snapshotted, or when the vault marker is unreadable. Exit `1` means an edit could not be applied (e.g. not in a world yet, or the write did not stick); exit `3` means EAC is loaded.

> [!NOTE]
> **Silent Execution:** When `-v` / `--verbose` is omitted, `sandbox` runs completely silently without console output. Use `-v` to print detailed edit confirmations.

> [!CAUTION]
> **Offline Only:** The sandbox refuses to perform memory writes if Easy Anti-Cheat (EAC) is active.

> [!WARNING]
> **Unexpected Interruption Recovery (Power Loss / System Crash):**
> If the system or game is forcibly interrupted (power cut, BSOD), run `eldendisk.exe sandbox restore` after closing the game to restore your clean pre-session save snapshot and clear the marker.

#### Flags & Options

| Flag | Value Type | Default | Description |
|:---|:---:|:---|:---|
| `--vault DIR` | path | `<tool>/backup/vault` | Vault of the running session (must match the one `run` uses). Also valid before a subcommand: `sandbox --vault D:\v restore`. |
| `--set NAME=VALUE` | string | `None` | Set an attribute value once, on-the-fly. Repeatable. |
| `--refill LIST` | string | `None` | Comma-separated list (`hp`, `fp`, `stamina`) to refill current vitals to maximum once. |
| `--offsets FILE` | path | `./offsets.json` | Path to offsets configuration file. |
| `--effects FILE` | path | `./chr_state_ids.json` | Path to state IDs configuration file. |
| `-v`, `--verbose` | switch | off | Print diagnostic confirmation of applied edits (silent when omitted). |

#### Editable Attributes & Ranges

| Attribute Name | Acceptable Range | Description |
|:---|:---:|:---|
| `level` | `1` – `713` | Character level number |
| `runes` | `0` – `999,999,999` | Current held Rune count |
| `vigor`, `mind`, `endurance`, `strength`, `dexterity`, `intelligence`, `faith`, `arcane` | `1` – `99` | Character stats |
| `hp` | `1` – `Max HP` | Current HP (cannot drop below 1) |
| `fp`, `stamina` | `0` – `Max` | Current FP / Stamina |

#### Expected Output Example (with `-v`)

```commandline
.\eldendisk.exe sandbox --set vigor=90 -v
```

```commandline
[sandbox] vigor: set to 90
[sandbox] Applied 1 edit(s) on-the-fly successfully.
```

*(Without `-v`: silent execution, zero console output)*

---

### 5. `hash` (Executable Hash Calculation)

```commandline
eldendisk.exe hash [--game-dir DIR]
```

Calculates and prints the SHA-256 hash of `eldenring.exe`. Used as the profile lookup key in `offsets.json`.

#### Expected Output Example

```commandline
.\eldendisk.exe hash
```

```commandline
1a3547101327f65d0c76da2f9190ac0aa66871ea42bae2aecc61e11a8b597891
```

---

### 6. Vault & Recovery Subcommands (`sandbox <subcommand>`)

#### `sandbox restore`
Restores clean save snapshot after an interrupted session or restores a specific historical snapshot.
```commandline
eldendisk.exe sandbox restore [--snapshot NAME] [--archive-contaminated]
```

#### `sandbox status`
Displays active marker status, snapshot count, and vault size.
```commandline
eldendisk.exe sandbox status
```

##### Expected Output Example
```commandline
no unresolved session; live save trusted
snapshots: 3  last: 20261006-120000  vault size: 14.2 MiB
last snapshot: verified
```

#### `sandbox list` / `verify` / `prune`
Lists snapshots, verifies SHA-256 integrity, or cleans up older snapshots.
```commandline
eldendisk.exe sandbox list [--fast]
eldendisk.exe sandbox verify SNAPSHOT_NAME
eldendisk.exe sandbox prune --keep N
```

##### Expected Output Examples
```commandline
.\eldendisk.exe sandbox list
```
```commandline
20261006-120000    7.1 MiB  verified
20261005-183012    7.1 MiB  verified
```

```commandline
.\eldendisk.exe sandbox verify 20261006-120000
```
```commandline
OK: snapshot matches its manifest
```

```commandline
.\eldendisk.exe sandbox prune --keep 1
```
```commandline
deleted 1 snapshot(s): 20261005-183012
```

---

## Detailed Examples

### Example 1: Launching Host & Setting Save Dir
```commandline
# Terminal 1: Launch game offline with save protection
.\eldendisk.exe run --save-dir "C:\Users\<User>\AppData\Roaming\EldenRing\76561198296924569" -v
```

### Example 2: Stream Live SpEffects or Animations
```commandline
# Stream active character buffs
.\eldendisk.exe effects -q

# Stream active character animation IDs
.\eldendisk.exe animations
```

### Example 3: On-The-Fly Edit While Playing
```commandline
# Terminal 2: Apply Vigor=90 while game is open
.\eldendisk.exe sandbox --set vigor=90 -v

# Apply Level=150 and max Runes
.\eldendisk.exe sandbox --set level=150 --set runes=999999999 -v

# Refill HP and FP
.\eldendisk.exe sandbox --refill hp,fp -v
```

### Example 4: Recovery After Crash
```commandline
# Restore clean save after unexpected system crash
.\eldendisk.exe sandbox restore
```

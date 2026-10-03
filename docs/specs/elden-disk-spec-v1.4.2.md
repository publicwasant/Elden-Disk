# EldenDisk Telemetry Tool
> **Proof of Concept (PoC) Specification**
> **Document Version:** 1.4.2 (revised from 1.4.1)
> **Date of Issue:** 2026-10-04
> **Target Platform:** Windows 10 / 11 (x64), Python 3.11+ (64-bit)
> **Game:** Elden Ring (Steam). Supported exe versions are listed in `offsets.json` (see §4.1)

---

## 0. Changelog

### 1.4.1 → 1.4.2

| **#** | **Change** | **Reason** |
|:-----:|:-----------|:-----------|
|   1   | Retain `character` Data Across All Connection States | Retain the `character` object payload in `disk-state.json` across all connection states (`WAITING_FOR_PROCESS`, `EAC_ACTIVE`/`EAC_DETECTED`, `UNSUPPORTED_VERSION`, `WAITING_FOR_WORLD`, `CONNECTED`, `DISCONNECTED`, `IDLE`) holding the latest updated data, instead of clearing it to `null`. |
|   2   | Cold Boot Exception | On a fresh start of the tool, the `character` object is initially `null` until the game reaches the `CONNECTED` state for the first time in that session. |

---

## 1. Executive Summary

A lightweight, **read-only** memory read tool featuring an **Event-Driven Persistence Architecture** for **offline** Elden Ring sessions:

```text
[LAUNCH] → [READ MEMORY AND UPDATE STATE (In RAM) @ 60FPS LOCKED] → [JSON WRITE (To Disk)]
```

### Guarantees
1. **Offline only.** The game is started by running `eldenring.exe -eac-nop-loaded` directly. EAC is not loaded and online play is unavailable. The tool refuses to attach to any process it did not launch or that shows EAC modules loaded (§3.4).
2. **Read-only.** Only `PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION` is requested. No `WriteProcessMemory`, `VirtualAllocEx`, `CreateRemoteThread`, or injection.
3. **Zero disk changes in the game folder.** No file is created, modified, renamed, or deleted there. (Reading `eldenring.exe` to hash it is read-only.)
4. **Correct-or-silent.** If the exe version is unknown or any validation fails, the tool reports a status and retains the latest valid character object (or `null` if not yet connected).
5. **Resource-conscious (Event-Driven Persistence).** Memory read loops run in RAM locked at 60FPS. Disk writes are strictly event-driven—triggered only when data state changes or when active timed timers update.

---

## 2. Architecture

```mermaid
flowchart TD
    subgraph Tool["EldenDisk Service"]
        Launcher["game_launcher.py"]
        Profile["profile_loader.py\n(offsets.json, chr_state_ids.json)"]
        Mem["memory_reader.py\n(read-only)"]
        Out["json_logger.py\n(event-driven diff write)"]
    end
    Reg["HKCU\\Software\\Valve\\Steam + libraryfolders.vdf"] --> Launcher
    Launcher -->|"CreateProcessW\n-eac-nop-loaded\nenv SteamAppId=1245620"| Exe["eldenring.exe"]
    Exe -->|"SHA-256 of exe file"| Profile
    Profile -->|"offset profile or UNSUPPORTED_VERSION"| Mem
    Mem ==>|"ReadProcessMemory @ 60FPS"| Exe
    Mem -->|"RAM State Update & Diff Check"| Out
    Out -->|"write temp + os.replace on change"| File["disk-state.json"]
```

---

## 3. Offline Launcher

### 3.1 Command
```cmd
"<GameDir>\eldenring.exe" -eac-nop-loaded
```
`<GameDir>` is `...\steamapps\common\ELDEN RING\Game`.

### 3.2 Discovery
1. Read `HKCU\Software\Valve\Steam\SteamPath`.
2. Parse `<SteamPath>\steamapps\libraryfolders.vdf` for all library paths.
3. Pick the library where `steamapps\common\ELDEN RING\Game\eldenring.exe` exists.
4. Steam client must already be running (required for Steam API init).

### 3.3 Process creation
- `CreateProcessW` with `lpApplicationName` = full exe path, `lpCommandLine` = `"eldenring.exe" -eac-nop-loaded`, `lpCurrentDirectory` = `<GameDir>`.
- Child environment: copy of current env plus `SteamAppId=1245620` and `SteamGameId=1245620`.
- The PID returned by `CreateProcessW` is the game PID. The tool only attaches to this PID.

### 3.4 Safety checks before attaching
- Enumerate modules with `CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)`. If any module name contains `EasyAntiCheat`, abort with `EAC_DETECTED` and never read memory.
- If the user starts the game via Steam normally (EAC active), the tool must not attach. It reports `EAC_ACTIVE` and exits the read loop.

---

## 4. Configuration & Memory Reading

### 4.1 Unified State Configuration (`chr_state_ids.json`)
The configuration file `chr_state_ids.json` acts as the single source of truth for all mapped SpEffect IDs and Animation State IDs.

### 4.2 Version Pinning (`offsets.json`)
Specifies layout and pointer offsets for supported `eldenring.exe` versions.

### 4.3 Pointer Chain & Character State Reading
- **Player Stats & Attributes:** Read from `PlayerGameData` via `PlayerIns + 0x580`.
- **Special Effects:** Read linked list starting at `PlayerIns + 0x178 + head`.
- **Animation State:** Read active animation ID from `CSChrTimeActModule`.

---

## 5. Connection State Machine

| **State**                     | **Meaning**                                                  | **JSON `character`** | **Mechanism**     |
|:------------------------------|:-------------------------------------------------------------|:--------------------:|:------------------|
| `WAITING_FOR_PROCESS`         | Game not running                                             |   `<full-object>`    | Latest updated    |
| `EAC_ACTIVE` / `EAC_DETECTED` | EAC present; tool refuses to attach                          |   `<full-object>`    | Latest updated    |
| `UNSUPPORTED_VERSION`         | Exe hash not in `offsets.json`                               |   `<full-object>`    | Latest updated    |
| `WAITING_FOR_WORLD`           | Process up but pointer chain is null (title screen, loading) |   `<full-object>`    | Latest updated    |
| `CONNECTED`                   | All validations pass                                         |   `<full-object>`    | In the moment     |
| `DISCONNECTED`                | Process exited                                               |   `<full-object>`    | Latest updated    |
| `IDLE`                        | Game window is present but not in focus                      |   `<full-object>`    | Latest updated    |

> [!NOTE]
> **Cold Boot Exception:** On a fresh start of the tool, the `character` object will still initially be `null` until the game reaches the `CONNECTED` state for the first time in that session.

---

## 6. JSON Output Schema (v1.4.2)

### 6.1 Schema (Draft 2020-12)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "EldenDiskLiveState",
  "type": "object",
  "required": ["system_status", "character"],
  "properties": {
    "system_status": {
      "type": "object",
      "required": ["state", "game_connected", "pid", "anti_cheat_status", "read_only", "exe_sha256", "profile", "buffs_supported", "ignored_effects", "last_error"],
      "properties": {
        "state": {
          "type": "string",
          "enum": ["WAITING_FOR_PROCESS", "EAC_ACTIVE", "EAC_DETECTED", "UNSUPPORTED_VERSION", "WAITING_FOR_WORLD", "CONNECTED", "DISCONNECTED", "IDLE"]
        },
        "game_connected": { "type": "boolean" },
        "pid": { "type": ["integer", "null"] },
        "anti_cheat_status": { "type": "string", "enum": ["DISABLED_OFFLINE", "ACTIVE_EAC", "UNKNOWN"] },
        "read_only": { "type": "boolean", "const": true },
        "exe_sha256": { "type": ["string", "null"] },
        "profile": { "type": ["string", "null"] },
        "buffs_supported": { "type": "boolean" },
        "ignored_effects": { "type": "integer", "minimum": 0 },
        "last_error": { "type": ["string", "null"] }
      }
    },
    "character": {
      "type": ["object", "null"],
      "required": ["level", "runes", "attributes", "effects", "animations"],
      "properties": {
        "level": { "type": "integer", "minimum": 1, "maximum": 713 },
        "runes": {
          "type": "object",
          "required": ["total", "baseline", "delta"],
          "properties": {
            "total": { "type": "integer", "minimum": 0, "maximum": 999999999 },
            "baseline": { "type": "integer", "minimum": 0, "maximum": 999999999 },
            "delta": { "type": "integer" }
          }
        },
        "attributes": {
          "type": "object",
          "required": ["vigor", "mind", "endurance", "strength", "dexterity", "intelligence", "faith", "arcane"],
          "additionalProperties": { "type": "integer", "minimum": 1, "maximum": 99 }
        },
        "effects": {
          "type": "object",
          "additionalProperties": {
            "type": "object",
            "required": ["name", "categories"],
            "properties": {
              "name": { "type": "string" },
              "categories": { "type": "string" },
              "abilities": { "type": "string" },
              "times": {
                "type": "object",
                "required": ["buff_duration", "max_duration", "last_activated_at"],
                "properties": {
                  "buff_duration": { "type": ["number", "null"], "minimum": 0 },
                  "max_duration": { "type": ["number", "null"], "exclusiveMinimum": 0 },
                  "last_activated_at": { "type": ["string", "null"] }
                }
              }
            }
          }
        },
        "animations": {
          "type": "object",
          "additionalProperties": {
            "type": "object",
            "required": ["name", "categories"],
            "properties": {
              "name": { "type": "string" },
              "categories": { "type": "string" },
              "abilities": { "type": "string" }
            }
          }
        }
      }
    }
  }
}
```

### 6.2 Example Output (Retained Character Data while WAITING_FOR_WORLD)

```json
{
  "system_status": {
    "state": "WAITING_FOR_WORLD",
    "game_connected": false,
    "pid": 14208,
    "anti_cheat_status": "DISABLED_OFFLINE",
    "read_only": true,
    "exe_sha256": "1a3547101327f65d0c76da2f9190ac0aa66871ea42bae2aecc61e11a8b597891",
    "profile": "ER 1.17.1",
    "buffs_supported": true,
    "ignored_effects": 0,
    "last_error": null
  },
  "character": {
    "level": 386,
    "runes": {
      "total": 1050000,
      "baseline": 1000000,
      "delta": 50000
    },
    "attributes": {
      "vigor": 80,
      "mind": 60,
      "endurance": 60,
      "strength": 90,
      "dexterity": 90,
      "intelligence": 15,
      "faith": 60,
      "arcane": 10
    },
    "effects": {
      "311100": {
        "name": "Gold Scarab",
        "categories": "TALISMANS",
        "abilities": "Permanently increases Runes gained by 20% while equipped."
      }
    },
    "animations": {
      "68011": {
        "name": "Resting",
        "categories": "MANNER",
        "abilities": "Resets: HP, FP, Stamina, etc."
      }
    }
  }
}
```

---

## 7. CLI Commands Reference

CLI command name is `eldendisk.exe` (or `python -m eldendisk`):
- **`eldendisk.exe hash`**
- **`eldendisk.exe run -v`**
- **`eldendisk.exe run --attach`**
- **`eldendisk.exe effects -q`**
- **`eldendisk.exe animations -q`**

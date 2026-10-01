# Changes
_(Previous version: **[elden-telemetry-spec-v1.2.0.md](../specs/elden-telemetry-spec-v1.2.0.md)**)_

---

## Murmur

Once the `python -m elden_telemetry run -v` command is executed and the game is launched (in offline mode), the memory reading output is generated in `/elden_telemetry/output/telemetry-state.json`.

Regarding the **character buffs** section:
```json
{
  "active_buffs": [
    {
      "id": 1605000,
      "name": "Flame! Grant Me Strength",
      "remaining_seconds": 21.84,
      "max_duration_seconds": 30.0,
      "activation_timestamp_iso": "2026-09-30T03:27:15.191Z"
    },
    {
      "id": 1660000,
      "name": "Golden Vow",
      "remaining_seconds": 76.04,
      "max_duration_seconds": 80.0,
      "activation_timestamp_iso": "2026-09-30T03:27:19.391Z"
    }
  ],
  "passive_buffs": [
    {
      "id": 311100,
      "name": "Gold Scarab",
      "category": "TALISMAN",
      "source_name": "Gold Scarab"
    }
  ]
}
```

Both `active_buffs` and `passive_buffs` represent character buffs. Since they are essentially the same entity type, why are they separated?

I understand this might be due to timing limitations—where one includes a countdown, while the other remains active indefinitely as long as the item is equipped.

**However, separating them still feels unnecessary. They could easily be merged together, which would make the data structure more intuitive since both types of buffs originate from the same in-game status bar.**

---

## Wahyi 
_(Refactoring data structures)_

### 1. Proposed Data Structure Refactoring

#### 1.1 Merge `active_buffs` and `passive_buffs` into a single `effects` object set:

**Key-Object Pair:**

| Field   |   Type    | Mandatory | Not-Null | Description               | Example |
|:--------|:---------:|:---------:|:--------:|:--------------------------|:--------|
| `<KEY>` | `INTEGER` |     ✔     |    ✔     | Game's memory address ID. | 311100  |

**Major-Object:**

| Field    |   Type   | Mandatory | Not-Null | Description                                                                                                                                                                                                                                                                                                                      | Example                                             |
|:---------|:--------:|:---------:|:--------:|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:----------------------------------------------------|
| name     | `STRING` |     ✔     |    ✔     | In-game item/effect name.                                                                                                                                                                                                                                                                                                        | Gold-Pickled Fowl Foot                              |
| kind     | `STRING` |     ✔     |    ✔     | Effect type (referenced from the game community): <br> - `TIMED` <br> - `PERMANENT`                                                                                                                                                                                                                                              | TIMED                                               |
| category | `STRING` |           |          | Effect category (referenced from the game community): <br> - `CONSUMABLES` <br> - `PERFUME_BOTTLES` <br> - `FLASK_OF_WONDROUS_PHYSICK` <br> - `GREASES` <br> - `INCANTATIONS` <br> - `SORCERIES` <br> - `ASHES_OF_WAR` <br> - `TALISMANS` <br> - `ARMOR_WITH_SPECIAL_EFFECTS` <br> - `PASSIVE_WEAPON_BUFFS` <br> - `GREAT_RUNES` | CONSUMABLES                                         |
| ability  | `STRING` |           |          | Effect ability (referenced from the game community)                                                                                                                                                                                                                                                                              | Increases Runes gained by **30%** for **3 minutes** |
| times    | `OBJECT` |     ✔     |    ✔     | Object containing time-related metadata fields: <br> - `buff_duration` <br> - `max_duration` <br> - `activation_timestamp_iso`                                                                                                                                                                                                   | `<OBJECT>`                                          |

_We have also refactored the time-related fields by mapping `remaining_seconds` → `buff_duration`, `max_duration_seconds` → `max_duration`, and nesting them alongside `activation_timestamp_iso` into a new `times` **object**._

**Sub-Object (`times`):**

| Field                     |   Type   | Mandatory | Not-Null | Description                                     | Example                  |
|:--------------------------|:--------:|:---------:|:--------:|:------------------------------------------------|:-------------------------|
| buff_duration             | `FLOAT`  |     ✔     |          | Remaining duration of the effect in seconds.    | 67.16                    |
| max_duration              | `FLOAT`  |     ✔     |          | Maximum duration of the effect in seconds.      | 180.0                    |
| activation_timestamp_iso  | `STRING` |     ✔     |          | ISO timestamp of when the effect was activated. | 2026-09-30T14:36:15.598Z |

**Output (Json-Object):**

```json
{
  "effects": {
    "311100": {
      "name": "Gold Scarab",
      "kind": "PERMANENT",
      "category": "TALISMANS",
      "ability": "Permanently increases Runes gained by 20% while equipped.",
      "times": {
        "buff_duration": null,
        "max_duration": null,
        "activation_timestamp_iso": null
      }
    },
    "3971": {
      "name": "Gold-Pickled Fowl Foot",
      "kind": "TIMED",
      "category": "CONSUMABLES",
      "ability": "Increases Runes gained by 30% for 3 minutes.",
      "times": {
        "buff_duration": 67.16,
        "max_duration": 180.0,
        "activation_timestamp_iso": "2026-09-30T14:36:15.598Z"
      }
    }
  }
}
```

#### 1.2 Restructured `effects.json` configuration file:

**Key-Object Pair:**

| Field     |   Type    | Mandatory | Not-Null | Description               | Example |
|:----------|:---------:|:---------:|:--------:|:--------------------------|:--------|
| `<KEY>`   | `INTEGER` |     ✔     |    ✔     | Game's memory address ID. | 311100  |

**Major-Object:**

| Field    |   Type   | Mandatory | Not-Null | Description                                          | Example                                             |
|:---------|:--------:|:---------:|:--------:|:-----------------------------------------------------|:----------------------------------------------------|
| name     | `STRING` |     ✔     |    ✔     | In-game item/effect name.                            | Gold-Pickled Fowl Foot                              |
| category | `STRING` |           |          | Effect category (referenced from the game community) | CONSUMABLES                                         |
| ability  | `STRING` |           |          | Effect ability (referenced from the game community)  | Increases Runes gained by **30%** for **3 minutes** |

**Output (Json-Object):**

```json
{
  "311100": {
    "name": "Gold Scarab",
    "category": "TALISMANS",
    "ability": "Permanently increases Runes gained by 20% while equipped."
  },
  "3971": {
    "name": "Gold-Pickled Fowl Foot",
    "category": "CONSUMABLES",
    "ability": "Increases Runes gained by 30% for 3 minutes."
  }
}
```

### 2. Requirements

#### Documentations
- **New Specification Version `1.2.1`:** 
  - Derived from _**[elden-telemetry-spec-v1.0.0.md](../specs/elden-telemetry-spec-v1.0.0.md) → [elden-telemetry-spec-v1.1.0.md](../specs/elden-telemetry-spec-v1.1.0.md) → [elden-telemetry-spec-v1.2.0.md](../specs/elden-telemetry-spec-v1.2.0.md) → elden-telemetry-spec-v1.2.1.md**_
  - Save at `./docs/specs/elden-telemetry-spec-v1.2.1.md`
- **New Implementation Plan:**
  - Scan the whole project, every details of source cods and design a **implementation_plan_v1.2.1.md**.
  - Save at `./docs/impls/implementation_plan_v1.2.1.md`

#### Integrations
- Development according to the **[elden-telemetry-spec-v1.2.1.md](../specs/elden-telemetry-spec-v1.2.1.md)** and the **[implementation_plan_v1.2.1.md](../impls/implementation_plan_v1.2.1.md)**
- Verification by **Unit-Test**
- Update **Tool-Version** and all the documentations that exist the **Changes.**

---
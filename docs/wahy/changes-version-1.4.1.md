> [!NOTE]
> **Version:** `1.4.1`  
> **Status:** APPROVED ✔     
> **Last Updated:** _2026-10-04_

**Summary:** Introduces `chr_state_ids.json` as the single source of truth, restructures `character.effects` (omitting the `kind` field), adds `character.animations` tracking to the JSON output, and implements the `animations` live-monitor CLI command.

_(baseline version: Wahy: **[changes-version-1.4.0.md](changes-version-1.4.0.md)** and the spec: **[elden-telemetry-spec-v1.4.0.md](../specs/elden-disk-spec-v1.3.0.md)**)_

---

## Murmur

**Animation State Verification.**

Now read this **[at_grace_report.md](../experiments/animation-state-verification/at_grace_report.md)**. This is the experimental report on the **Hypothesis Testing** that I spent several hours working on. You have no idea how hyped and proud I am! It was absolutely incredible—there were nearly 2.77 billion addresses floating around while the game was running, and I managed to pinpoint the exact single address containing the character's Animation ID!

To be completely honest, I didn't find it from scratch. After hours of scanning and monitoring address behaviors, all I got was pure garbage. I was about to lose my mind, so I searched GitHub and found some guy’s open-source repo claiming he had the offsets for the character's animation state. I dug through his code, grabbed the address, added it manually in **Cheat Engine 7.7**, and boom—he was absolutely right. That damn address and pointers worked flawlessly!

**Anyway, check out this table. The base is `"eldenring.exe"+3B16E30`, offsets `[slot, 18, 190, 0]`.**

| **In-game action**                       |  **Slot `+0x90`** |  **Slot `+0x50`** |
|:-----------------------------------------|------------------:|------------------:|
| _Just standing_                          |           2000000 |           2000000 |
| _Running_                                |           2020110 |           2020110 |
| _Sprinting_                              |           2020210 |           2020210 |
| _Rolling_                                |             27110 |             27110 |
| _Attacking (R1)_                         |          26030000 |          26030000 |
| _Pause menu while standing_              |           2000000 |           2000000 |
| _Resting at Palace Approach Ledge-Road_  |             68011 |             68011 |
| _Resting at Dynasty Mausoleum Entrance_  |             68011 |             68011 |
| _Resting at Dynasty Mausoleum Midpoint_  |             68011 |             68011 |
| _Resting at Church of Elleh_             |             68011 |             68011 |

In our current tool version, we have the `python -m eldendisk effects -q` command to live-monitor which effect IDs appear while playing the game. Why don't we have an `animations` function to live-track the character's animation state ID in real time too?

Imagine running the command `python -m eldendisk animations -q` and logging the character's animation state ID in real-time. We could monitor specific animation states and add them into a JSON configuration file, just like **[effects.json](../../code/effects.json)**.

This approach gives us the potential to archive every single character animation state ID in the game, allowing us to take full advantage of it later.

---

## Wahy

### 1. Introduce `chr_state_ids.json` configuration file

**Key-Object Pair:**

| Field  |   Type   | Mandatory | Not-Null | Description                                 | Example |
|:-------|:--------:|:---------:|:--------:|:--------------------------------------------|:--------|
| `<ID>` | `string` |     ✔     |    ✔     | Specific `sp_effect_id` or `anim_id` state. | 311100  |

**Value Descriptive-Object:**

| Field      |   Type   | Mandatory | Not-Null | Description                                                                                        | Example                                             |
|:-----------|:--------:|:---------:|:--------:|:---------------------------------------------------------------------------------------------------|:----------------------------------------------------|
| name       | `string` |     ✔     |    ✔     | In-game state or specific entity name (e.g., items, effects, animations).                          | Gold-Pickled Fowl Foot                              |
| sources    |  `enum`  |     ✔     |    ✔     | In-game offset source derived from **Approved Hypothesis Testing** by the developer/modder.        | **EFFECTS**                                         |
| categories |  `enum`  |     ✔     |    ✔     | In-game category classification (e.g., effect type, animation manner).                             | **CONSUMABLES**                                     |
| abilities  | `string` |           |          | In-game description of what it actually does to the character (e.g., buffs, i-frames, or nothing). | Increases Runes gained by **30%** for **3 minutes** |

**Declare `sources` Enum Definitions:**

| **Enum**     | **Definition**               |
|:-------------|:-----------------------------|
| `EFFECTS`    | Effect State Verification    |
| `ANIMATIONS` | Animation State Verification |

**Declare `categories` Enum Definitions:**

| **Enum**                     | **Definition**                                                                         |
|:-----------------------------|:---------------------------------------------------------------------------------------|
| `CONSUMABLES`                | Temporary effect states applied by consuming standard items.                           |
| `PERFUME_BOTTLES`            | Temporary effect states applied by using crafted perfume items.                        |
| `FLASK_OF_WONDROUS_PHYSICK`  | Temporary effect states applied by drinking the mixed Physick flask.                   |
| `GREASES`                    | Temporary effect states applied directly to weapons via greases.                       |
| `INCANTATIONS`               | Effect states applied by casting Faith-based incantation spells.                       |
| `SORCERIES`                  | Effect states applied by casting Intelligence-based sorcery spells.                    |
| `ASHES_OF_WAR`               | Effect states applied by activating weapon skills (Weapon Arts).                       |
| `TALISMANS`                  | Permanent passive effect states granted by equipped talismans.                         |
| `ARMOR_WITH_SPECIAL_EFFECTS` | Permanent passive effect states granted by specific equipped armor pieces.             |
| `PASSIVE_WEAPON_BUFFS`       | Permanent passive effect states granted by holding or equipping specific weapons.      |
| `GREAT_RUNES`                | Semi-permanent effect states granted by an active Great Rune until death.              |
| `MANNER`                     | Specific character physical actions, stances, or animation states.                     |

**JSON-Schema:**

```json
{
  "<id>": {
    "name": "String | Mandatory | Not-Null",
    "sources": "String | Mandatory | Not-Null",
    "categories": "String | Mandatory | Not-Null",
    "abilities": "String | Nullable"
  }
}
```

**JSON-Example:**

```json
{
  "311100": {
    "name": "Gold Scarab",
    "sources": "EFFECTS",
    "categories": "TALISMANS",
    "abilities": "Permanently increases Runes gained by 20% while equipped."
  },
  "3971": {
    "name": "Gold-Pickled Fowl Foot",
    "sources": "EFFECTS",
    "categories": "CONSUMABLES",
    "abilities": "Increases Runes gained by 30% for 3 minutes."
  },
  "2020210": {
    "name": "Sprint",
    "sources": "ANIMATIONS",
    "categories": "MANNER"
  },
  "27110": {
    "name": "Dodge",
    "sources": "ANIMATIONS",
    "categories": "MANNER",
    "abilities": "Provides invincibility frames (i-frames) for a few milliseconds."
  },
  "68011": {
    "name": "Resting",
    "sources": "ANIMATIONS",
    "categories": "MANNER",
    "abilities": "Resets: HP, FP, Stamina, etc."
  }
}
```
> [!IMPORTANT]
> The legacy `effects.json` file will be entirely replaced by this new `chr_state_ids.json` configuration file, serving as the single source of truth.

### 2. Restructuring `./output/disk-state.json`

**Key-Object Pair:**

| Field  |   Type   | Mandatory | Not-Null |
|:-------|:--------:|:---------:|:--------:|
| `<ID>` | `string` |     ✔     |    ✔     |

**Value Major-Object:**

| Field      |   Type   | Mandatory | Not-Null |
|:-----------|:--------:|:---------:|:--------:|
| name       | `string` |     ✔     |    ✔     |
| categories |  `enum`  |     ✔     |    ✔     |
| abilities  | `string` |           |          |


**2.1 `character.effects`:**

_**(Notice that the `kind` field is missing? Don't jump to conclusions—we aren't removing it from the core logic. We are simply omitting it from the final JSON output to keep the payload clean.)**_

**The presence of the `times` sub-object is now the sole indicator of whether an effect is `TIMED` or `PERMANENT`. If it's a `TIMED` effect, append the `times` sub-object; if it's `PERMANENT`, simply omit `times` entirely instead of emitting `null`.**

**Output (JSON Object):**

```json
{
  "effects": {
    "311100": {
      "name": "Gold Scarab",
      "categories": "TALISMANS",
      "abilities": "Permanently increases Runes gained by 20% while equipped."
    },
    "3971": {
      "name": "Gold-Pickled Fowl Foot",
      "categories": "CONSUMABLES",
      "abilities": "Increases Runes gained by 30% for 3 minutes.",
      "times": {
        "buff_duration": 67.16,
        "max_duration": 180.0,
        "last_activated_at": "2026-09-30 14:36:15.598000"
      }
    }
  }
}
```

**2.2 `character.animations`**

As seen in the table above, the `abilities` field is non-mandatory and nullable. This means if the value is null or empty, we simply omit the field from the output object entirely to keep the payload clean.

The output mechanism is pretty straightforward. The `character.animations` object will only ever contain **ONE** key-value pair at any given time. After all, the character cannot sprint, dodge, and rest at the exact same time, right? Therefore, the output is strictly 1:1 and remains frozen on the last active animation state.

**Output (JSON Object):**

**In-game Sprinting:**

```json
{
  "animations": {
    "2020210": {
      "name": "Sprint",
      "categories": "MANNER"
    }
  }
}
```

**In-game Dodging:**

```json
{
  "animations": {
    "27110": {
      "name": "Dodge",
      "categories": "MANNER",
      "abilities": "Provides invincibility frames (i-frames) for a few milliseconds."
    }
  }
}
```

**In-game Resting:**

```json
{
  "animations": {
    "68011": {
      "name": "Resting",
      "categories": "MANNER",
      "abilities": "Resets: HP, FP, Stamina, etc."
    }
  }
}
```

> [!IMPORTANT]
> Once the `animations` object is updated, the data remains frozen to reflect the last known active animation state until a new state overrides it.

### 3. Character's Animation State Live-Monitor

Inspired by the `effects` command—which live-prints effect IDs, remaining durations, and max durations in real-time at a 60FPS pacing—we are going to implement a similar CLI command for animations.

By running `python -m eldendisk animations -q` in another terminal, the tool will live-print the character's animation state IDs in the exact same manner:

```commandline
PS D:\StudioProjects\Elden-Disk\code> python -m eldendisk animations -q
Ctrl+C to stop. Format: id | timestamp (+ is appeared, - is disappeared)
--- 3 animations now active ---
+   2020210 |   2026-10-01 02:58:00.000000
-   2020210 |   2026-10-01 02:58:00.000000
+     27110 |   2026-10-01 02:58:00.000000
-     27110 |   2026-10-01 02:58:00.000000
+     68011 |   2026-10-01 02:58:00.000000
-     68011 |   2026-10-01 02:58:00.000000
```

> [!NOTE]
> The `timestamp` format is a standard human-readable string with fractional seconds.

---

## Requirements

### 1. Documentation
- **New Specification Version `1.4.1`:**
  - Write **[NEW] elden-disk-spec-v1.4.1.md**
  - Save at `./docs/specs/elden-disk-spec-v1.4.1.md`
- **New Implementation Plan:**
  - Scan the whole project and every detail of the source code to draft an **implementation_plan_v1.4.1.md**.
  - Save at `./docs/implementations/implementation_plan_v1.4.1.md`

### 2. Integration
- Develop features according to **elden-disk-spec-v1.4.1.md** and **implementation_plan_v1.4.1.md**.
- Verification via **Unit Tests**.
- Update the **Tool-Version** and all documentation affected by these **Changes**.

---
# Changes

> [!NOTE]
> **Version:** `1.4.0`  
> **Status:** APPROVED ✔     
> **Last Updated:** _2026-10-03_

**Summary:** Retains the `character` state after process exit and expands the `runes` object with real-time farming metrics (baseline, delta, RPM).

_(baseline version: Wahy: **[changes-version-1.3.0.md](changes-version-1.3.0.md)** and the spec: **[elden-telemetry-spec-v1.3.0.md](../specs/elden-disk-spec-v1.3.0.md)**)_

---

## Murmur

After running the tool and playing the game for a while, I've been monitoring the output in `output/disk-state.json`. It's such a satisfying moment to see my own project working flawlessly. The **60fps pacing**, the **IDLE** state behavior, and the **Event-Driven Persistence** mean I don't have to worry about disk I/O bottlenecks at all.

Looking back at the baseline version where buff duration timers were introduced—I totally agree that having a visual countdown is incredibly helpful. The base game doesn't include this feature, which is fine since the game is a masterpiece in its own right, but it's a great quality-of-life addition.

I'm the type of player who actually enjoys the long farming grinds and never gets bored of it. Having exact timings for buffs is cool because it lets me predict my next move, maintain the pacing, and manage my resources way more easily.

**Leveling up the `runes` object to make resource management even more satisfying.**

**In `./output/disk-state.json` under `character.runes`, we're going to change this:**

```json
{
  "runes": 1050000
}
```

**To something like this:**

```json
{
  "runes": {
    "total": 1050000,
    "baseline": 1000000,
    "delta": 50000,
    "metrics": {
      "elapsed_seconds": 150.0,
      "runes_per_minute": 20000
    }
  }
}
```

**Looks pretty cool, right?**

This new data structure in the runes section is going to be super helpful for build-addicted players. It shows exactly how much you've gained over a specific period and provides a great baseline for whatever min-maxing calculations you want to run.


**We're not done yet. There's one more thing we need to clear up. Check out this connection state machine:**

| **State**                     | **Meaning**                                                  | **JSON `character`** |
|:------------------------------|:-------------------------------------------------------------|:--------------------:|
| `WAITING_FOR_PROCESS`         | Game not running                                             |        `null`        |
| `EAC_ACTIVE` / `EAC_DETECTED` | EAC present; tool refuses to attach                          |        `null`        |
| `UNSUPPORTED_VERSION`         | Exe hash not in `offsets.json`                               |        `null`        |
| `WAITING_FOR_WORLD`           | Process up but pointer chain is null (title screen, loading) |        `null`        |
| `CONNECTED`                   | All validations pass                                         |   `<full-object>`    |
| `DISCONNECTED`                | Process exited                                               |        `null`        |
| `IDLE`                        | Game window is present but not in focus                      |   `<full-object>`    |

Each state has its own behavior that directly affects the `character` object in `./output/disk-state.json`. Take a look at the `DISCONNECTED` state: when we close the game, `eldenring.exe` is terminated, and the `character` object just vanishes (becomes `null`).

A bit annoying, right? What if I want to use the latest updated data after exiting the game? We should retain the `character` object even after the process is terminated.

---

## Wahy

### 1. Fix Connection State Machine

**Retain the `character` object in `./output/disk-state.json` after exiting the game:**

| **State**                     | **Meaning**                                                  | **JSON `character`** |
|:------------------------------|:-------------------------------------------------------------|:--------------------:|
| `WAITING_FOR_PROCESS`         | Game not running                                             |        `null`        |
| `EAC_ACTIVE` / `EAC_DETECTED` | EAC present; tool refuses to attach                          |        `null`        |
| `UNSUPPORTED_VERSION`         | Exe hash not in `offsets.json`                               |        `null`        |
| `WAITING_FOR_WORLD`           | Process up but pointer chain is null (title screen, loading) |        `null`        |
| `CONNECTED`                   | All validations pass                                         |   `<full-object>`    |
| **`DISCONNECTED`**            | **Process exited**                                           | **`<full-object>`**  |
| `IDLE`                        | Game window is present but not in focus                      |   `<full-object>`    |

### 2. Expanding the `runes` Value into an Object

**Major-Object:**

| **Field**  | **Type** | **Example Data** | **Description**                                                             |
|:-----------|:--------:|:-----------------|:----------------------------------------------------------------------------|
| `total`    | `uint32` | `1050000`        | Current runes held by the player.                                           |
| `baseline` | `uint32` | `1000000`        | Snapshot of runes at the start of the cycle (e.g., leaving a Grace).        |
| `delta`    | `int32`  | `50000`          | Net runes gained this cycle (`total - baseline`). Can be negative on death. |
| `metrics`  | `object` | `<object>`       | Container for farming analytics. `null` if inactive.                        |

**Expanding the `metrics` sub-object:**

| **Field**          | **Type** | **Example Data** | **Description**                               |
|:-------------------|:--------:|:-----------------|:----------------------------------------------|
| `elapsed_seconds`  | `float`  | `150.0`          | Seconds elapsed since the cycle started.      |
| `runes_per_minute` | `int32`  | `20000`          | Estimated runes gained per minute (RPM).      |

**Output (JSON Object):**

```json
{
  "runes": {
    "total": 1050000,
    "baseline": 1000000,
    "delta": 50000,
    "metrics": {
      "elapsed_seconds": 150.0,
      "runes_per_minute": 20000
    }
  }
}
```
**Breaking down how each value works:**

The **`baseline`** value acts as our farming cycle anchor. The exact millisecond you stand up or close the Site of Grace menu, the tool snapshots your total runes and locks them in. Mechanically, this requires monitoring the memory pointer tied to the Grace interaction event flag or animation ID. By triggering the snapshot on the exact state transition from "resting" to "idle," we guarantee it captures your true baseline after you've spent runes on leveling or shopping. This ensures clean data right before you engage the first mob.

The **`delta`** calculates the real-time difference **($\Delta = \text{total} - \text{baseline}$)** at our locked **60FPS pacing**. Every kill drives this number up, but since it's a signed **int32**, dying and dropping your runes will instantly plummet this value into the negatives. You can see exactly how deep in the hole you are without pulling out a calculator.

The **`metrics`** object is where we turn raw math into actual optimization. The moment **`baseline`** is set, a hidden stopwatch starts tracking **`elapsed_seconds`**. We then divide the live **`delta`** by this time to spit out your **`runes_per_minute` (RPM)**. This proves exactly which farming route at Mohgwyn Palace gives you the ultimate Time-to-Rune ratio.

> [!WARNING]
> Since we've expanded the `runes` data object above, the `telemetry` object in `./output/disk-state.json` is now redundant. Remove it entirely.

---

## Requirements

### 1. Documentation
- **New Specification Version `1.4.0`:**
  - Write **[NEW] elden-disk-spec-v1.4.0.md**
  - Save at `./docs/specs/elden-disk-spec-v1.4.0.md`
- **New Implementation Plan:**
  - Scan the whole project and every detail of the source code to draft an **implementation_plan_v1.4.0.md**.
  - Save at `./docs/implementations/implementation_plan_v1.4.0.md`

### 2. Integration
- Develop features according to **elden-disk-spec-v1.4.0.md** and **implementation_plan_v1.4.0.md**.
- Verification via **Unit Tests**.
- Update the **Tool-Version** and all documentation affected by these **Changes**.

---
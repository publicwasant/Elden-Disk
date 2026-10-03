> [!NOTE]
> **Version:** `1.4.2`  
> **Status:** APPROVED ✔     
> **Last Updated:** _2026-10-04_

**Summary:** Retains the `character` object data in `disk-state.json` across all connection states instead of clearing it to `null`.

_(baseline version: Wahy: **[changes-version-1.4.1.md](changes-version-1.4.0.md)** and the spec: **[elden-disk-spec-v1.4.1.md](../specs/elden-disk-spec-v1.3.0.md)**)_

---

## Murmur

I didn't even know what the last update of the `character` object looked like in the output JSON file, because we clear that damn `character` object to `null` whenever it's not in a connected or idle state...

Yeah, that's literally it.

---

## Wahy

**The single task we are going to do here is DO NOT CLEAR the `character` object in `./output/disk-state.json` across ANY state:**

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
> **Cold Boot Exception:** On a fresh start of the tool, the `character` object will still initially be `null` until the game reaches the `CONNECTED` state for the first time in that session. (We can't conjure character data out of thin air!)

---

## Requirements

### 1. Catch up with previous versions:
- **Changes:**
  - **[changes-version-1.2.1.md](changes-version-1.2.1.md)**
  - **[changes-version-1.3.0.md](changes-version-1.3.0.md)**
  - **[changes-version-1.4.0.md](changes-version-1.4.0.md)**
  - **[changes-version-1.4.1.md](changes-version-1.4.1.md)**
- **Specification:**
  - **[elden-telemetry-spec-v1.0.0.md](../specs/elden-telemetry-spec-v1.0.0.md)**
  - **[elden-telemetry-spec-v1.1.0.md](../specs/elden-telemetry-spec-v1.1.0.md)**
  - **[elden-telemetry-spec-v1.2.0.md](../specs/elden-telemetry-spec-v1.2.0.md)**
  - **[elden-disk-spec-v1.3.0.md](../specs/elden-disk-spec-v1.3.0.md)**
  - **[elden-disk-spec-v1.4.0.md](../specs/elden-disk-spec-v1.4.0.md)**
  - **[elden-disk-spec-v1.4.1.md](../specs/elden-disk-spec-v1.4.1.md)**
- **Implementation Plan:**
  - **[implementation_plan_v1.2.1.md](../implementations/implementation_plan_v1.2.1.md)**
  - **[implementation_plan_v1.3.0.md](../implementations/implementation_plan_v1.3.0.md)**
  - **[implementation_plan_v1.4.0.md](../implementations/implementation_plan_v1.4.0.md)**
  - **[implementation_plan_v1.4.1.md](../implementations/implementation_plan_v1.4.1.md)**

### 2. Documentation
- **New Specification Version `1.4.2`:**
  - Write **[NEW] elden-disk-spec-v1.4.2.md**
  - Save at `./docs/specs/elden-disk-spec-v1.4.2.md`
- **New Implementation Plan:**
  - Scan the whole project and every detail of the source code to draft an **implementation_plan_v1.4.2.md**.
  - Save at `./docs/implementations/implementation_plan_v1.4.2.md`

### 3. Integration
- Develop features according to **elden-disk-spec-v1.4.2.md** and **implementation_plan_v1.4.2.md**.
- Verification via **Unit Tests**.
- Update the **Tool-Version** and all documentation affected by these **Changes**.

---
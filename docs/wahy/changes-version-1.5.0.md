## Changes

> [!NOTE]
> **Version:** `1.5.0`  
> **Status:** APPROVED ✔     
> **Last Updated:** _2026-10-04_

**Summary:** Introduces the `vitals` object to the `disk-state.json` output, tracking the character's current, effective maximum, and base values for Hit Points, Focus Points, and Stamina.

---

## Murmur

**Character's Vitals Status Fields**

Before we start, catch up on the **Hypothesis Testing Results** and all the experimental files in `./docs/experiments/vitals/*`, especially **[elden-disk-vitals-pointer-spec.md](../experiments/vitals/elden-disk-vitals-pointer-spec.md)**, where all the crucial information is already documented.

To finalize the **Elden-Disk** foundation, we need to complete all the basic variable memory reading, and the final piece of the puzzle is the **Character's Vitals Status Fields**.

---

### 1. Add the `vitals` object to the `./output/disk-state.json` output

**Key-Object Pair:**

| **Field**     | **Type** | **Mandatory** | **Not-Null** | **Description**           | **Example**                           |
|:--------------|:--------:|:-------------:|:------------:|:--------------------------|:--------------------------------------|
| `<vital_key>` | `string` |       ✔       |      ✔       | Three major vital fields. | `hit_point`, `focus_point`, `stamina` |

**Core-Object Structure:**

| **Field** | **Type**  | **Mandatory** | **Not-Null** | **Description**                                | **Example** |
|:----------|:---------:|:-------------:|:------------:|:-----------------------------------------------|------------:|
| current   | `integer` |       ✔       |      ✔       | The character's current in-game vital value.   |         890 |
| maximum   | `integer` |       ✔       |      ✔       | The character's effective maximum vital value. |        1914 |
| base      | `integer` |       ✔       |      ✔       | The character's unmodified base vital value.   |        2015 |

**JSON Output:**

```json
{
  "vitals": {
    "hit_point": {
      "current": 890,
      "maximum": 1914,
      "base": 2015
    },
    "focus_point": {
      "current": 350,
      "maximum": 350,
      "base": 350
    },
    "stamina": {
      "current": 178,
      "maximum": 178,
      "base": 158
    }
  }
}
```

> [!NOTE]
> Insert the `vitals` object inside the `character` object in the `./output/disk-state.json` file, positioning it directly after the `level` field.

---

## Requirements

### 1. Catch up with previous versions

_**Read previous documentation to understand what is going on in depth.**_

- **Changes:**
  - **[changes-version-1.2.1.md](changes-version-1.2.1.md)**
  - **[changes-version-1.3.0.md](changes-version-1.3.0.md)**
  - **[changes-version-1.4.0.md](changes-version-1.4.0.md)**
  - **[changes-version-1.4.1.md](changes-version-1.4.1.md)**
  - **[changes-version-1.4.2.md](changes-version-1.4.2.md)**
- **Specification:**
  - **[elden-telemetry-spec-v1.0.0.md](../specs/elden-telemetry-spec-v1.0.0.md)**
  - **[elden-telemetry-spec-v1.1.0.md](../specs/elden-telemetry-spec-v1.1.0.md)**
  - **[elden-telemetry-spec-v1.2.0.md](../specs/elden-telemetry-spec-v1.2.0.md)**
  - **[elden-disk-spec-v1.3.0.md](../specs/elden-disk-spec-v1.3.0.md)**
  - **[elden-disk-spec-v1.4.0.md](../specs/elden-disk-spec-v1.4.0.md)**
  - **[elden-disk-spec-v1.4.1.md](../specs/elden-disk-spec-v1.4.1.md)**
  - **[elden-disk-spec-v1.4.2.md](../specs/elden-disk-spec-v1.4.2.md)**
- **Implementation Plan:**
  - **[implementation_plan_v1.2.1.md](../implementations/implementation_plan_v1.2.1.md)**
  - **[implementation_plan_v1.3.0.md](../implementations/implementation_plan_v1.3.0.md)**
  - **[implementation_plan_v1.4.0.md](../implementations/implementation_plan_v1.4.0.md)**
  - **[implementation_plan_v1.4.1.md](../implementations/implementation_plan_v1.4.1.md)**
  - **[implementation_plan_v1.4.2.md](../implementations/implementation_plan_v1.4.2.md)**

### 2. Documentation

_**Scan the whole project and every detail of the source code to draft perfectly new documentation.**_

- **New Specification Version `1.5.0`:**
  - Write **[NEW] elden-disk-spec-v1.5.0.md**
  - Save at `./docs/specs/elden-disk-spec-v1.5.0.md`
- **New Implementation Plan:**
  - Write **[NEW] implementation_plan_v1.5.0.md**.
  - Save at `./docs/implementations/implementation_plan_v1.5.0.md`

### 3. Integration (Take actions)
- Develop features according to **elden-disk-spec-v1.5.0.md** and **implementation_plan_v1.5.0.md**.
- Verification via **Unit Tests**.
- Update the **Tool-Version** and all documentation affected by these **Changes**.

---
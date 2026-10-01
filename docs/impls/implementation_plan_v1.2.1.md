# Implementation Plan v1.2.1

Refactoring telemetry data structures and configuration schemas according to specification `v1.2.1`.

## Overview
This plan details the code and schema updates required to transition the project from spec `v1.2.0` (`active_buffs` and `passive_buffs` array separation) to spec `v1.2.1` (unified `effects` object set with flat `effects.json` lookup configuration).

---

## Proposed Changes

### 1. Configuration & Metadata

#### [MODIFY] [effects.json](file:///D:/StudioProjects/Elden-Ring-Telemetry-Tools/code/effects.json)
- Restructure top-level JSON from `{"active": {...}, "passive": {...}}` into a flat dictionary keyed by SpEffect ID string (`"<ID>"`).
- Each entry contains `name`, `category` (optional), and `ability` (optional).

#### [MODIFY] [__init__.py](file:///D:/StudioProjects/Elden-Ring-Telemetry-Tools/code/elden_telemetry/__init__.py)
- Bump `__version__` to `"1.2.1"`.

---

### 2. Core Library

#### [MODIFY] [profile_loader.py](file:///D:/StudioProjects/Elden-Ring-Telemetry-Tools/code/elden_telemetry/profile_loader.py)
- Replace separate `ActiveEffect` and `PassiveEffect` dataclasses with a single `EffectConfig` dataclass:
  - `name: str`
  - `category: str | None = None`
  - `ability: str | None = None`
- Refactor `Effects` container: `table: dict[int, EffectConfig]`.
- Update `load_effects(path: Path) -> Effects` to parse the flat JSON dictionary structure, ignoring keys starting with `_`.

#### [MODIFY] [telemetry.py](file:///D:/StudioProjects/Elden-Ring-Telemetry-Tools/code/elden_telemetry/telemetry.py)
- Refactor `Sampler._classify(entries, now)`:
  - Returns `(effects_dict: dict[str, dict], ignored_count: int)`.
  - For each `(eid, dur, timer)`:
    - Lookup `eid` in `effects.table`. If absent or numbers are non-finite, increment `ignored`.
    - If `dur <= 0` or permanent:
      - `kind = "PERMANENT"`
      - `times = {"buff_duration": None, "max_duration": None, "activation_timestamp_iso": None}`
    - If `dur > 0`:
      - Calculate `remaining = timer if mode == "remaining" else dur - timer`.
      - If `remaining <= 0` or `remaining > dur + 1.0`, increment `ignored`.
      - Else:
        - `kind = "TIMED"`
        - `times = {"buff_duration": round(remaining, 2), "max_duration": round(dur, 2), "activation_timestamp_iso": iso(now - timedelta(seconds=dur - remaining))}`
    - Construct effect object keyed by string `str(eid)` with fields: `name`, `kind`, optional `category`, optional `ability`, and `times`.
- Update `Sampler.sample()`:
  - Populate `character["effects"]` instead of `active_buffs` and `passive_buffs`.

#### [MODIFY] [telemetry.schema.json](file:///D:/StudioProjects/Elden-Ring-Telemetry-Tools/code/elden_telemetry/telemetry.schema.json)
- Update JSON schema for `character`:
  - Required fields: `["level", "runes", "attributes", "effects"]`.
  - Define `effects` property as an object with additionalProperties representing effect entries matching `v1.2.1` schema.

---

### 3. Tooling & Tests

#### [MODIFY] [soak_check.py](file:///D:/StudioProjects/Elden-Ring-Telemetry-Tools/code/tools/soak_check.py)
- Update `check(doc)` to validate `ch.get("effects", {})` timed entries (`times.buff_duration` and `times.max_duration`).

#### [MODIFY] [test_soak_check.py](file:///D:/StudioProjects/Elden-Ring-Telemetry-Tools/code/tests/test_soak_check.py)
- Update mock test documents to use `effects` instead of `active_buffs`/`passive_buffs`.

#### [MODIFY] [test_telemetry.py](file:///D:/StudioProjects/Elden-Ring-Telemetry-Tools/code/tests/test_telemetry.py)
- Update test cases, mock data generators, and schema validation assertions to verify the new `effects` structure.

#### [MODIFY] [README.md](file:///D:/StudioProjects/Elden-Ring-Telemetry-Tools/README.md)
- Update spec version references to `v1.2.1` and update example JSON output snippet.

---

## Verification Plan

### Automated Tests
- Run `python -m pytest` across all unit tests to ensure 100% pass rate.
- Run `python tools/soak_check.py` against mock output file.

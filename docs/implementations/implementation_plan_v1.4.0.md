# Implementation Plan v1.4.0

Retaining `character` state on game process exit (`DISCONNECTED`), expanding `character.runes` into an object (`total`, `baseline`, `delta`), removing the redundant top-level `telemetry` block, integrating dynamic Animation State (`CSChrTimeActModule`) reading to detect Site of Grace resting, and updating schema and test suites according to specification `v1.4.0`.

## Overview
This plan details the full implementation steps for **EldenDisk v1.4.0** based on [elden-disk-spec-v1.4.0.md](../specs/elden-disk-spec-v1.4.0.md), [changes-version-1.4.0.md](../wahy/changes-version-1.4.0.md), and [at_grace_report.md](../experiments/animation-state-verification/at_grace_report.md).

Key Goals:
1. **Retain `character` Data on `DISCONNECTED`**:
   - Update `build_document()` and `Monitor.emit` to retain `<full-object>` character data when process transitions to `DISCONNECTED` after having been connected.
2. **Expand `character.runes` Structure**:
   - Change `character.runes` from a scalar integer to a JSON object:
     - `total`: `uint32` current runes held.
     - `baseline`: `uint32` snapshot of runes at the start of the farming cycle (e.g. resting at Grace or initial connection).
     - `delta`: `int32` net runes gained or lost (`total - baseline`).
3. **Remove Top-Level `telemetry` Block & `metrics`**:
   - Remove `"telemetry": {"session_start_runes": ..., "rune_delta": ...}` from document output and schema definitions.
   - Remove `metrics` (`elapsed_seconds`, `runes_per_minute`) to uphold the "Very Lightweight Memory Read Tool" Event-Driven Persistence Architecture (no continuous file writes when standing still).
4. **Site of Grace Memory Event Detection (`CSChrTimeActModule`)**:
   - Read player's dynamic Animation ID via `PlayerIns + 0x190` (`ChrInsModuleContainer`) -> `+0x18` (`CSChrTimeActModule`) -> `read_idx` at `+0xC4` -> `anim_id` at `+0x20 + (read_idx * 0x10)`.
   - Match `anim_id` against `at_grace.equals` (`0x109AB` / `68011`).
   - On `entered_grace` state transition (`False` -> `True`), reset `baseline_runes = total` and freeze `baseline_runes`.
5. **Schema & Version Updates**:
   - Bump package version to `1.4.0` in `code/eldendisk/__init__.py`.
   - Update `code/eldendisk/disk.schema.json` to reflect `runes` object structure and removal of `telemetry`.
   - Update `soak_check.py` and test suites (`test_disk.py`, `test_soak_check.py`).

---

## Proposed Changes

### 1. Core Service Logic, Profile Loader & Schema

#### [MODIFY] [__init__.py](file:///D:/StudioProjects/Elden-Disk/code/eldendisk/__init__.py)
- Bump `__version__ = "1.4.0"`.

#### [MODIFY] [profile_loader.py](file:///D:/StudioProjects/Elden-Disk/code/eldendisk/profile_loader.py)
- Add `AnimLayout` and `AtGraceConfig` dataclasses.
- Parse `anim` and `at_grace` profile configuration blocks from `offsets.json`.

#### [MODIFY] [disk.py](file:///D:/StudioProjects/Elden-Disk/code/eldendisk/disk.py)
- Update `Sampler` class:
  - Add `_read_anim_id(player)` helper to calculate dynamic `anim_id` from `time_act` queue using `read_idx`.
  - Add `_is_at_grace(player)` helper comparing `anim_id` against `at_grace.equals` (`0x109AB` / `68011`).
  - Maintain `baseline_runes` and `_was_at_grace`.
  - Reset and freeze `baseline_runes = total` under strictly two conditions: Initial Connect and Enter Site Of Grace (`is_at_grace` state transition from `False` to `True`).
  - Construct `runes` object in sample result with `total`, `baseline`, and `delta`.
- Update `build_document()`:
  - Retain `character` data when state is `CONNECTED`, `IDLE`, or `DISCONNECTED` (when `sample` or `last_sample` is provided).
  - Remove `telemetry` block from returned dictionary.

#### [MODIFY] [disk.schema.json](file:///D:/StudioProjects/Elden-Disk/code/eldendisk/disk.schema.json)
- Remove `"telemetry"` from top-level `required` list and `properties`.
- Update `character.properties.runes` from integer to object schema with `total`, `baseline`, and `delta`.

#### [MODIFY] [__main__.py](file:///D:/StudioProjects/Elden-Disk/code/eldendisk/__main__.py)
- Pass `last_sample` to `mon.emit("DISCONNECTED", sample=last_sample)` when process disconnects, enabling `character` retention on process exit.

---

### 2. Supporting Tooling & Test Suites

#### [MODIFY] [soak_check.py](file:///D:/StudioProjects/Elden-Disk/code/tools/soak_check.py)
- Remove top-level `telemetry` validation.
- Allow `character` to be present when state is `CONNECTED`, `IDLE`, or `DISCONNECTED`.
- Validate `ch["runes"]` object (`total`, `baseline`, `delta`).

#### [MODIFY] [test_disk.py](file:///D:/StudioProjects/Elden-Disk/code/tests/test_disk.py)
- Update assertions for `character["runes"]` object structure.
- Remove `telemetry` and `metrics` assertions.
- Add test case `test_grace_reset_baseline` verifying dynamic `CSChrTimeActModule` `read_idx` animation state reading and `DISCONNECTED` character retention.
- Validate generated documents against updated schema.

#### [MODIFY] [test_soak_check.py](file:///D:/StudioProjects/Elden-Disk/code/tests/test_soak_check.py)
- Update sample document generator to match version 1.4.0 document structure.

---

### 3. Output Files & Documentation

#### [MODIFY] [offsets.json](file:///D:/StudioProjects/Elden-Disk/code/offsets.json)
- Add `anim` and `at_grace` configurations for Elden Ring 1.17.1 profile.

#### [MODIFY] [output/disk-state.json](file:///D:/StudioProjects/Elden-Disk/code/output/disk-state.json)
- Update example state file to match version 1.4.0 format.

#### [MODIFY] [README.md](file:///D:/StudioProjects/Elden-Disk/README.md)
- Update schema examples and documentation references to version 1.4.0.

#### [MODIFY] [docs/cli-commands.md](file:///D:/StudioProjects/Elden-Disk/docs/cli-commands.md)
- Update schema and output examples for version 1.4.0.

#### [MODIFY] [docs/adding-a-profile.md](file:///D:/StudioProjects/Elden-Disk/docs/adding-a-profile.md)
- Update references to `runes` object structure and animation module offsets.

---

## Verification Plan

### Automated Tests
- Run `python -m pytest code/tests` to verify all unit tests pass under version 1.4.0.

### Manual & System Verification
- Validate `disk-state.json` against `disk.schema.json` using `jsonschema`.
- Verify `soak_check.py` against sample states.

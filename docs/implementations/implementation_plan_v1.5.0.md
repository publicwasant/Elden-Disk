# Implementation Plan v1.5.0

Introducing the `vitals` object (`hit_point`, `focus_point`, `stamina`) to `disk-state.json` inside the `character` object directly after `level`, updating profile loading, memory sampling, JSON schema, soak check, and test suites according to specification `v1.5.0`.

## Overview
This plan details the full implementation steps for **EldenDisk v1.5.0** based on [elden-disk-spec-v1.5.0.md](../specs/elden-disk-spec-v1.5.0.md) and [changes-version-1.5.0.md](../wahy/changes-version-1.5.0.md).

Key Goals:
1. **Add `vitals` Object to `character`**:
   - Track character Hit Points, Focus Points, and Stamina with `current`, `maximum`, and `base` integer fields.
   - Position `vitals` inside the `character` payload directly after `level`.
2. **Memory Sampling & Profile Configuration**:
   - Add `vitals` configuration (`player_to_modules`, `modules_to_data`, `data_to_vitals`) to `offsets.json`.
   - Update `profile_loader.py` to parse `VitalsLayout`.
   - Update `disk.py` to sample `CSChrDataModule` vitals block (`0x138` to `0x15C`) and validate values.
3. **JSON Schema & Validator Updates**:
   - Update `disk.schema.json` to require `vitals` under `character` and define properties for `hit_point`, `focus_point`, and `stamina`.
   - Update `soak_check.py` to validate `vitals` fields.
4. **Tool Versioning & Test Verification**:
   - Bump version to `1.5.0` in `code/eldendisk/__init__.py`.
   - Update unit test suites in `test_disk.py` and `test_soak_check.py` to cover vitals reading and validation.
   - Update `README.md` and `output/disk-state.json` example.

---

## Proposed Changes

### 1. Configuration & Profile Loader

#### [MODIFY] [offsets.json](file:///D:/StudioProjects/Elden-Disk/code/offsets.json)
- Add `vitals` object configuration to profile:
  - `player_to_modules`: `"0x190"`
  - `modules_to_data`: `"0x0"`
  - `data_to_vitals`: `"0x138"`

#### [MODIFY] [profile_loader.py](file:///D:/StudioProjects/Elden-Disk/code/eldendisk/profile_loader.py)
- Define `VitalsLayout` dataclass: `player_to_modules: int`, `modules_to_data: int`, `data_to_vitals: int`.
- Add `_parse_vitals(d: dict) -> VitalsLayout | None` helper with fallback to default offsets (`0x190`, `0x0`, `0x138`).
- Add `vitals: VitalsLayout | None = None` to `Profile` dataclass.

---

### 2. Memory Sampler & Core Logic

#### [MODIFY] [disk.py](file:///D:/StudioProjects/Elden-Disk/code/eldendisk/disk.py)
- Implement `_read_vitals(player: int) -> tuple[dict | None, str | None]` on `Sampler`.
  - Read `ChrInsModuleContainer` (`player + vitals.player_to_modules`).
  - Read `CSChrDataModule` (`modules + vitals.modules_to_data`).
  - Read 40 bytes at `data_mod + vitals.data_to_vitals` and unpack 10 signed integers.
  - Return formatted vitals dictionary (`hit_point`, `focus_point`, `stamina`).
- Call `_read_vitals()` in `sample()` and insert `vitals` into `character` dictionary directly after `level`.

#### [MODIFY] [disk.schema.json](file:///D:/StudioProjects/Elden-Disk/code/eldendisk/disk.schema.json)
- Add `"vitals"` to `character.required`.
- Define properties for `"vitals"` (`hit_point`, `focus_point`, `stamina`) with required `current`, `maximum`, `base` properties.

#### [MODIFY] [__init__.py](file:///D:/StudioProjects/Elden-Disk/code/eldendisk/__init__.py)
- Bump `__version__ = "1.5.0"`.

---

### 3. Supporting Tooling & Test Suites

#### [MODIFY] [soak_check.py](file:///D:/StudioProjects/Elden-Disk/code/tools/soak_check.py)
- Update `check()` function to validate `ch["vitals"]` structure and presence of `hit_point`, `focus_point`, `stamina`.

#### [MODIFY] [test_disk.py](file:///D:/StudioProjects/Elden-Disk/code/tests/test_disk.py)
- Update test memory mocks in `full_world()` and `world()` to include vitals block data in `FakeMem`.
- Add assertions for `c["vitals"]` in `test_connected_sample` and other state test cases.
- Add invalid vitals memory tests.

#### [MODIFY] [test_soak_check.py](file:///D:/StudioProjects/Elden-Disk/code/tests/test_soak_check.py)
- Update `doc()` helper to include `vitals` object in generated `character` payload.

---

### 4. Output Files & Documentation

#### [MODIFY] [output/disk-state.json](file:///D:/StudioProjects/Elden-Disk/code/output/disk-state.json)
- Update example state file to include `vitals` block following version 1.5.0 schema.

#### [MODIFY] [README.md](file:///D:/StudioProjects/Elden-Disk/README.md)
- Update documentation and references to version 1.5.0.

---

## Verification Plan

### Automated Tests
- Run `python -m pytest code/tests` to verify all unit tests pass under version 1.5.0.

### Manual & System Verification
- Validate `disk-state.json` against `disk.schema.json` using `jsonschema`.
- Verify `soak_check.py` against sample state documents.

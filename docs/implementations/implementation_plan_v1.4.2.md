# Implementation Plan v1.4.2

Retaining the `character` object data in `disk-state.json` across all connection states (`WAITING_FOR_PROCESS`, `EAC_ACTIVE`/`EAC_DETECTED`, `UNSUPPORTED_VERSION`, `WAITING_FOR_WORLD`, `CONNECTED`, `DISCONNECTED`, `IDLE`) instead of clearing it to `null`, handling the Cold Boot Exception, updating validation logic, and updating unit test suites according to specification `v1.4.2`.

## Overview
This plan details the full implementation steps for **EldenDisk v1.4.2** based on [elden-disk-spec-v1.4.2.md](../specs/elden-disk-spec-v1.4.2.md) and [changes-version-1.4.2.md](../wahy/changes-version-1.4.2.md).

Key Goals:
1. **Retain `character` Data Across All States**:
   - Update `build_document()` and `Monitor` class to cache and retain the latest valid `character` object across all connection state transitions.
   - Prevent resetting `character` to `null` when transitioning to `WAITING_FOR_WORLD`, `DISCONNECTED`, `WAITING_FOR_PROCESS`, `EAC_ACTIVE`, `EAC_DETECTED`, or `UNSUPPORTED_VERSION`.
2. **Cold Boot Exception**:
   - On a fresh start of the tool, `character` will remain `null` until the game reaches the `CONNECTED` state for the first time in that session.
3. **Soak Check & Verification Updates**:
   - Update `soak_check.py` to allow non-null `character` object across all states.
   - Update `test_soak_check.py` to test valid non-null character retention across states as well as cold boot behavior.
   - Add unit tests in `test_disk.py` to assert character retention behavior across state transitions and cold boot behavior.
4. **Tool-Version & Documentation Updates**:
   - Bump package version to `1.4.2` in `code/eldendisk/__init__.py`.
   - Update `README.md`, `docs/cli-commands.md`, and `code/output/disk-state.json`.

---

## Proposed Changes

### 1. Core Service Logic

#### [MODIFY] [__init__.py](file:///D:/StudioProjects/Elden-Disk/code/eldendisk/__init__.py)
- Bump `__version__ = "1.4.2"`.

#### [MODIFY] [disk.py](file:///D:/StudioProjects/Elden-Disk/code/eldendisk/disk.py)
- Update `build_document()` parameter signature to accept `last_character: dict | None = None`.
- In `build_document()`, set `character`:
  - Use `sample.character` if available.
  - Otherwise, fallback to `last_character` (if provided).
  - Otherwise, default to `None` (cold boot).

#### [MODIFY] [__main__.py](file:///D:/StudioProjects/Elden-Disk/code/eldendisk/__main__.py)
- Update `Monitor` class:
  - Add `self._last_character: dict | None = None`.
  - In `emit()`, update `self._last_character` whenever `sample` contains a non-null `character`.
  - Pass `last_character=self._last_character` when calling `build_document()`.

---

### 2. Supporting Tooling & Test Suites

#### [MODIFY] [soak_check.py](file:///D:/StudioProjects/Elden-Disk/code/tools/soak_check.py)
- Update `check()` function:
  - Remove restriction that flagged `character` present in non-CONNECTED states.
  - Allow `character` object to be present in any state.
  - Ensure `character` is validated if present.

#### [MODIFY] [test_disk.py](file:///D:/StudioProjects/Elden-Disk/code/tests/test_disk.py)
- Add `test_character_retained_across_all_states` to test retention across `WAITING_FOR_WORLD`, `DISCONNECTED`, `WAITING_FOR_PROCESS`, `EAC_ACTIVE`, `UNSUPPORTED_VERSION`, and `IDLE`.
- Add `test_cold_boot_character_is_null` to test initial `null` state before connection.

#### [MODIFY] [test_soak_check.py](file:///D:/StudioProjects/Elden-Disk/code/tests/test_soak_check.py)
- Update test helper document generator and test cases to reflect version 1.4.2 rules.

---

### 3. Output Files & Documentation

#### [MODIFY] [output/disk-state.json](file:///D:/StudioProjects/Elden-Disk/code/output/disk-state.json)
- Update example state file to reflect version 1.4.2 format.

#### [MODIFY] [README.md](file:///D:/StudioProjects/Elden-Disk/README.md)
- Update documentation and examples for version 1.4.2.

---

## Verification Plan

### Automated Tests
- Run `python -m pytest code/tests` to verify all unit tests pass under version 1.4.2.

### Manual & System Verification
- Validate `disk-state.json` against `disk.schema.json` using `jsonschema`.
- Verify `soak_check.py` against sample state documents.

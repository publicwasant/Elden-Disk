# Implementation Plan v1.3.0

Implementing project renaming to **EldenDisk**, module/file renames (`telemetry` → `disk`), window active focus detection (`IDLE` state), 60FPS pacing lock, Event-Driven Persistence architecture, and schema updates according to specification `v1.3.0`.

## Overview
This plan details the full implementation steps for **EldenDisk v1.3.0** based on [elden-disk-spec-v1.3.0.md](../specs/elden-disk-spec-v1.3.0.md) and [changes-version-1.3.0.md](../wahyi/changes-version-1.3.0.md).

Key Goals:
1. **Refactor naming across project**:
   - Rename package directory `code/elden_telemetry` → `code/eldendisk`.
   - Rename module `telemetry.py` → `disk.py`.
   - Rename schema file `telemetry.schema.json` → `disk.schema.json`.
   - Rename output file `telemetry-state.json` → `disk-state.json`.
   - Rename test file `test_telemetry.py` → `test_disk.py`.
   - Update binary references to `eldendisk.exe` and bump `__version__ = "1.3.0"`.
2. **Window Focus Detection & `IDLE` State**:
   - Detect foreground window using Windows Win32 API (`GetForegroundWindow`, `GetWindowThreadProcessId`).
   - Add `IDLE` connection state when game window is not active. In `IDLE` state, freeze memory polling and disk writes while retaining character data.
3. **60FPS Pacing**:
   - Default polling frequency `--hz` to `60.0`.
4. **Event-Driven Persistence**:
   - State differential checking in RAM. Only write `disk-state.json` to disk if state/data has changed or if active `TIMED` buff durations are ticking down.
5. **Schema Update**:
   - Remove top-level `timestamp` field from telemetry document output and schema definitions.
   - Add `"IDLE"` state to state enum.

---

## Proposed Changes

### 1. Renaming & Package Refactoring

#### [RENAME & MODIFY] [code/elden_telemetry](file:///D:/StudioProjects/Elden-Disk/code/elden_telemetry) → `code/eldendisk`
- Move directory `code/elden_telemetry` to `code/eldendisk`.
- Update `__init__.py`: `__version__ = "1.3.0"`.

#### [RENAME & MODIFY] [telemetry.py](file:///D:/StudioProjects/Elden-Disk/code/elden_telemetry/telemetry.py) → `code/eldendisk/disk.py`
- Rename to `disk.py`.
- Update `build_document()` to remove top-level `"timestamp"`.

#### [RENAME & MODIFY] [telemetry.schema.json](file:///D:/StudioProjects/Elden-Disk/code/elden_telemetry/telemetry.schema.json) → `code/eldendisk/disk.schema.json`
- Rename to `disk.schema.json`.
- Remove `"timestamp"` from top-level `required` list and `properties`.
- Add `"IDLE"` to `system_status.state` enum.
- Update schema title to `"EldenDiskLiveState"`.

#### [MODIFY] [memory_reader.py](file:///D:/StudioProjects/Elden-Disk/code/elden_telemetry/memory_reader.py) → `code/eldendisk/memory_reader.py`
- Add Win32 helper function `is_window_active(pid: int) -> bool` using `GetForegroundWindow` and `GetWindowThreadProcessId`.

#### [MODIFY] [json_logger.py](file:///D:/StudioProjects/Elden-Disk/code/elden_telemetry/json_logger.py) → `code/eldendisk/json_logger.py`
- Default filename to `disk-state.json`.

#### [MODIFY] [__main__.py](file:///D:/StudioProjects/Elden-Disk/code/elden_telemetry/__main__.py) → `code/eldendisk/__main__.py`
- Update imports from `.disk` instead of `.telemetry`.
- Update default output filename to `disk-state.json`.
- Update CLI parser prog name to `"eldendisk"`.
- Default `--hz` argument to `60.0` (matching 60FPS pacing).
- Implement window focus check and `IDLE` state transition in `cmd_run`.
- Implement event-driven persistence (state differential checking) before calling `logger.write()`.

---

### 2. Supporting Tooling & Tests

#### [RENAME & MODIFY] [test_telemetry.py](file:///D:/StudioProjects/Elden-Disk/code/tests/test_telemetry.py) → `code/tests/test_disk.py`
- Rename to `test_disk.py`.
- Update imports to `eldendisk` and `eldendisk.disk`.
- Remove `timestamp` checks and assertions.
- Add test cases for `IDLE` state handling and document validation without `timestamp`.

#### [MODIFY] [soak_check.py](file:///D:/StudioProjects/Elden-Disk/code/tools/soak_check.py)
- Default path to `disk-state.json`.
- Add `"IDLE"` to `STATES` set.
- Remove `STALE_AFTER` timestamp check.

#### [MODIFY] [test_soak_check.py](file:///D:/StudioProjects/Elden-Disk/code/tests/test_soak_check.py)
- Update mock documents for `soak_check.py` testing.

---

### 3. Documentation & Output Files

#### [RENAME] [code/output/telemetry-state.json](file:///D:/StudioProjects/Elden-Disk/code/output/telemetry-state.json) → `code/output/disk-state.json`

#### [MODIFY] [README.md](file:///D:/StudioProjects/Elden-Disk/README.md)
- Rename project references to **EldenDisk** and `eldendisk`.
- Update CLI command examples (`eldendisk.exe run -v`, etc.).
- Update schema description and example JSON snippet.

#### [MODIFY] [docs/cli-commands.md](file:///D:/StudioProjects/Elden-Disk/docs/cli-commands.md)
- Update command references and flags for version 1.3.0.

#### [MODIFY] [docs/adding-a-profile.md](file:///D:/StudioProjects/Elden-Disk/docs/adding-a-profile.md)
- Update package references from `elden_telemetry` to `eldendisk`.

---

## Verification Plan

### Automated Tests
- Run `python -m pytest` to execute unit test suite against `eldendisk`.
- Run `python tools/soak_check.py` against sample state outputs.

### Manual / System Verification
- Verify `eldendisk` package imports and CLI execution (`python -m eldendisk --help`, `hash`, `run -v`, `effects -q`).
- Verify schema validation of produced `disk-state.json`.

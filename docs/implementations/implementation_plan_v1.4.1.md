# Implementation Plan v1.4.1

Introducing `chr_state_ids.json` as the single source of truth, restructuring `character.effects` (omitting `kind` field, pluralizing metadata keys, omitting `times` when permanent), adding `character.animations` tracking strictly 1:1 frozen on the last active state, implementing the `animations` live-monitor CLI command, and updating schemas and test suites according to specification `v1.4.1`.

## Overview
This plan details the full implementation steps for **EldenDisk v1.4.1** based on [elden-disk-spec-v1.4.1.md](../specs/elden-disk-spec-v1.4.1.md) and [changes-version-1.4.1.md](../wahy/changes-version-1.4.1.md).

Key Goals:
1. **Single Source of Truth (`chr_state_ids.json`)**:
   - Replace legacy `effects.json` with `chr_state_ids.json` mapping both SpEffect IDs and Animation State IDs with metadata fields (`name`, `sources`, `categories`, `abilities`).
2. **Restructure `character.effects`**:
   - Remove `kind` field from output JSON.
   - Use `categories` and `abilities` as field names.
   - Omit `times` sub-object completely for `PERMANENT` effects instead of outputting `null`.
3. **Add `character.animations`**:
   - Track character animation state in real-time under `character.animations`.
   - Maintain strictly 1 active key-value object mapped from `chr_state_ids.json`.
   - Remain frozen on the last known active animation state until overridden.
4. **`animations` Live-Monitor CLI Command**:
   - Implement `python -m eldendisk animations -q` command to live-print character animation state ID transitions with timestamp formatting.
5. **Schema, Tooling & Test Suite Updates**:
   - Bump package version to `1.4.1` in `code/eldendisk/__init__.py`.
   - Update `code/eldendisk/disk.schema.json` to reflect version 1.4.1 schema changes.
   - Update `soak_check.py` and test suites (`test_disk.py`, `test_soak_check.py`).

---

## Proposed Changes

### 1. Unified Configuration & Profile Loader

#### [NEW] [chr_state_ids.json](file:///D:/StudioProjects/Elden-Disk/code/chr_state_ids.json)
- Create `chr_state_ids.json` as single source of truth for effects and animations.

#### [MODIFY] [profile_loader.py](file:///D:/StudioProjects/Elden-Disk/code/eldendisk/profile_loader.py)
- Update `ChrStateConfig` / `EffectConfig` dataclass to support `sources`, `categories`, and `abilities`.
- Update `load_effects` to load from `chr_state_ids.json` (with fallback to `effects.json`).

---

### 2. Core Service Logic & Schema

#### [MODIFY] [__init__.py](file:///D:/StudioProjects/Elden-Disk/code/eldendisk/__init__.py)
- Bump `__version__ = "1.4.1"`.

#### [MODIFY] [disk.py](file:///D:/StudioProjects/Elden-Disk/code/eldendisk/disk.py)
- Update `Sampler`:
  - Track `_last_animation` frozen object.
  - In `sample()`, update `_last_animation` when valid non-zero `anim_id` is read.
  - In `_classify()`, format effects output without `kind` field, with `categories` / `abilities` keys, omitting `times` when `PERMANENT`.
  - Include `animations` in `character` payload.

#### [MODIFY] [disk.schema.json](file:///D:/StudioProjects/Elden-Disk/code/eldendisk/disk.schema.json)
- Require `animations` under `character`.
- Update `effects` properties (`categories`, `abilities`, omit `kind`, optional `times`).
- Define `animations` properties (`name`, `categories`, optional `abilities`).

#### [MODIFY] [__main__.py](file:///D:/StudioProjects/Elden-Disk/code/eldendisk/__main__.py)
- Add `cmd_animations` CLI function for `python -m eldendisk animations -q`.
- Update default `--effects` path to `chr_state_ids.json`.

---

### 3. Supporting Tooling & Test Suites

#### [MODIFY] [soak_check.py](file:///D:/StudioProjects/Elden-Disk/code/tools/soak_check.py)
- Update validation logic for `character.effects` and `character.animations`.

#### [MODIFY] [test_disk.py](file:///D:/StudioProjects/Elden-Disk/code/tests/test_disk.py)
- Update test cases to assert `v1.4.1` document output format.
- Add test cases for `character.animations` tracking and frozen behavior.

#### [MODIFY] [test_soak_check.py](file:///D:/StudioProjects/Elden-Disk/code/tests/test_soak_check.py)
- Update sample document generator to match version 1.4.1 format.

---

### 4. Output Files & Documentation

#### [MODIFY] [output/disk-state.json](file:///D:/StudioProjects/Elden-Disk/code/output/disk-state.json)
- Update example state file to match version 1.4.1 format.

#### [MODIFY] [README.md](file:///D:/StudioProjects/Elden-Disk/README.md)
- Update documentation and examples for version 1.4.1.

#### [MODIFY] [docs/cli-commands.md](file:///D:/StudioProjects/Elden-Disk/docs/cli-commands.md)
- Document the `animations` command and updated schema.

#### [MODIFY] [docs/adding-a-profile.md](file:///D:/StudioProjects/Elden-Disk/docs/adding-a-profile.md)
- Update configuration references to `chr_state_ids.json`.

---

## Verification Plan

### Automated Tests
- Run `python -m pytest code/tests` to verify all unit tests pass under version 1.4.1.

### Manual & System Verification
- Validate `disk-state.json` against `disk.schema.json` using `jsonschema`.
- Verify `soak_check.py` against sample state documents.

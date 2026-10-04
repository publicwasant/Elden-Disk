# Implementation Plan v1.5.1

Introducing the `build` CLI command (`python -m eldendisk build`), executable resource path resolution (`sys._MEIPASS`), dedicated executable CLI documentation (`cli-commands-exe.md`), and the End-to-End development pipeline (`tools/dev_pipeline.py`).

## Overview
This plan details the full implementation steps for **EldenDisk v1.5.1** based on [elden-disk-spec-v1.5.1.md](../specs/elden-disk-spec-v1.5.1.md) and [changes-version-1.5.1.md](../wahy/changes-version-1.5.1.md).

Key Goals:
1. **`build` CLI Command**:
   - Add `python -m eldendisk build` with options `--engine` (`pyinstaller` | `nuitka`), `--clean`, `--embed-configs`, and `--icon`.
   - Support compilation into `./dist/eldendisk.exe`.
2. **Frozen Mode Resource Resolution**:
   - Update resource path resolution to dynamically handle PyInstaller's `sys._MEIPASS` when `--embed-configs` is used or fall back to the executable directory / package location.
3. **Executable CLI Reference**:
   - Write `docs/cli-commands-exe.md` reflecting `eldendisk.exe <command>` command usage.
4. **End-to-End Development Pipeline**:
   - Implement `tools/dev_pipeline.py` to automate unit tests, executable compilation, and execution.
5. **Tool Version & Specs**:
   - Bump version to `1.5.1` in `code/eldendisk/__init__.py`.

---

## Proposed Changes

### 1. CLI Core & Build Pipeline

#### [MODIFY] [__main__.py](file:///D:/StudioProjects/Elden-Disk/code/eldendisk/__main__.py)
- Implement `get_resource_path(filename: str, default_dir: Path | None = None) -> Path` to resolve files from `sys._MEIPASS` (if frozen and embedded) or `Path(sys.executable).parent` or project root.
- Implement `cmd_build(args) -> int`:
  - Perform artifact cleanup if `--clean` is set (removing `./build` and `./dist`).
  - Construct PyInstaller command or Nuitka command.
  - Handle `--embed-configs` by adding `--add-data` arguments for `offsets.json`, `chr_state_ids.json`, and `eldendisk/disk.schema.json`.
  - Log progress messages matching the required standard format.
- Add `build` parser to `main()` with flags `-e/--engine`, `-c/--clean`, `-em/--embed-configs`, `-i/--icon`.

#### [MODIFY] [__init__.py](file:///D:/StudioProjects/Elden-Disk/code/eldendisk/__init__.py)
- Bump version to `"1.5.1"`.

---

### 2. End-to-End Pipeline Script

#### [NEW] [dev_pipeline.py](file:///D:/StudioProjects/Elden-Disk/tools/dev_pipeline.py)
- Implement E2E development run pipeline script:
  1. Pre-check: Execute unit tests via `pytest`.
  2. Build: Execute `python -m eldendisk build -c`.
  3. Launch: Execute `./dist/eldendisk.exe run -v`.

#### [NEW] [dev_pipeline.py](file:///D:/StudioProjects/Elden-Disk/code/tools/dev_pipeline.py)
- Mirror/link script for invocation from both project root and `code/` directory.

---

### 3. Documentation

#### [NEW] [cli-commands-exe.md](file:///D:/StudioProjects/Elden-Disk/docs/cli-commands-exe.md)
- Write CLI reference for standalone executable (`eldendisk.exe`).

#### [MODIFY] [README.md](file:///D:/StudioProjects/Elden-Disk/README.md)
- Update version references to 1.5.1 and document `build` CLI command.

---

## Verification Plan

### Automated Tests
- Run `python -m pytest` inside `code/` directory to ensure 100% test pass rate.

### Executable Build & Execution Verification
- Run `python -m eldendisk build -c` and verify `./dist/eldendisk.exe` is created.
- Test `python tools/dev_pipeline.py` to verify the end-to-end cycle.
- Run `./dist/eldendisk.exe hash` to verify frozen executable command handling.

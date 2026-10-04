# Implementation Plan v1.5.2

Hardening release; see [changes-version-1.5.2.md](../wahy/changes-version-1.5.2.md) and [elden-disk-spec-v1.5.2.md](../specs/elden-disk-spec-v1.5.2.md).

## Proposed Changes
- **`code/eldendisk/__main__.py`**: `runtime_dirs()`, `get_resource_path()` (no ancestor walk), `describe_resource()`; `Monitor` (`_should_write` with `doc_signature`, one busy warning per streak); `cmd_run` (`--timer-interval`, `--no-idle`, `[config]` log); `cmd_animations` via `Sampler.locate_player()` / `read_animation_id()`; `build_command()` / `_build_layout()` / `_config_files()` / `cmd_build()` shared by both engines; deprecated hidden `effects --effects`, `animations -q`; `%(default)s` in `--offsets/--effects` help.
- **`code/eldendisk/disk.py`**: `iso()` with offset; `doc_signature()`; `Sampler._reset_session()` + `WORLD_LOST_RESET_S`; public `locate_player()`, `read_animation_id()`; removed `_is_at_grace`, `session_start_runes`.
- **`code/eldendisk/json_logger.py`**: whole-write retry on `PermissionError`, returns `False`.
- **`code/eldendisk/profile_loader.py`**: required `vitals`; strict `at_grace`.
- **`code/eldendisk/__init__.py`**: version `1.5.2`.
- **Tests**: `tests/test_main.py`, `tests/test_profile_policy.py` (new); `test_disk.py` timestamp assertion updated.
- **Docs**: README, `cli-commands.md`, `cli-commands-exe.md`, `adding-a-profile.md`, `offsets.json` `_readme`, `dev_pipeline.py` docstring.

## Verification Plan
1. `python -m pytest` → 68 passed.
2. `python -m eldendisk build -c -em`, then `eldendisk run -h` (embedded path), drop an `offsets.json` beside the exe and re-run (external path).
3. On Windows: V-07 from the spec (PyInstaller and Nuitka).

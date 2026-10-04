> [!NOTE]
> **Version:** `1.5.2`  
> **Status:** IMPLEMENTED  
> **Last Updated:** _2026-10-04_

**Summary:** Hardening release from the 1.5.1 code review. No new telemetry fields.

_(baseline: **[changes-version-1.5.1.md](changes-version-1.5.1.md)** and **[elden-disk-spec-v1.5.1.md](../specs/elden-disk-spec-v1.5.1.md)**)_

---

## Wahy

| # | Change | Where |
|:-:|:---|:---|
| 1 | **Nuitka parity.** `build -e nuitka` now honours `--embed-configs` (`--include-data-files`) and, without it, copies the editable configs next to the exe, exactly like PyInstaller. Nuitka output flag is `--output-filename`. Both engines share one config list and one command builder (`build_command`). | `__main__.py` |
| 2 | **Logger never kills the loop.** `JsonLogger.write` retries the whole write (tmp file **and** replace) on `PermissionError` and returns `False` instead of raising. Monitor warns once per busy streak. | `json_logger.py`, `__main__.py` |
| 3 | **Throttled countdown writes.** A change that only moves `buff_duration` is written at most every `--timer-interval` seconds (default 0.5; `0` = old behaviour). Every other change is written immediately. | `disk.py` (`doc_signature`), `__main__.py` |
| 4 | **No borrowed offsets.** `vitals` is required in a profile; `at_grace` is `null` or `{source, equals}` with a required `equals` (no default `68011`). Violations give `UNSUPPORTED_VERSION: profile incomplete: ...`. | `profile_loader.py` |
| 5 | **Config lookup policy.** Compiled exe: file next to the exe > embedded copy; the ancestor-folder walk is gone. `run -v` prints `embedded` / `external` / `source` for each config; `run -h` shows the resolved paths. Nuitka runtimes are detected too. | `__main__.py` |
| 6 | **`--no-idle`** keeps reading while the game window is unfocused. | `__main__.py` |
| 7 | **Unambiguous timestamps.** `last_activated_at` and the `animations` viewer now carry a UTC offset (`2026-10-04 11:00:00.000000+00:00`). **Format change** for consumers that parse the old naive string. | `disk.py` |
| 8 | **Session reset.** After the world is gone for 10 s (title screen / long load) the rune baseline, Grace flag, buff-activation memory and last animation are forgotten, so loading another character starts clean. Short loads (fast travel) keep them. | `disk.py` |
| 9 | **Cleanup.** Removed unused `_is_at_grace` and `session_start_runes`; `disk.schema.json` is no longer bundled (only tests use it); `effects --effects` and `animations -q` are deprecated no-ops (accepted, hidden). `animations`/`raw_effects` use new public `Sampler.locate_player()` / `read_animation_id()`. | various |
| 10 | **Docs aligned with code.** Output path is `./build/dist/<version>/` and `--clean` removes `./build` (spec 1.5.1 said `./dist`). `offsets.json` `_readme` names the right module. | docs |

Unchanged on purpose: while in the world, the last animation is retained through `anim_id <= 0` (covered by `test_grace_reset_baseline`).

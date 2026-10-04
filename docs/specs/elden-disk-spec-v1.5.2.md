# EldenDisk Telemetry Tool
> **Document Version:** 1.5.2 (revised from 1.5.1)
> **Date of Issue:** 2026-10-04
> **Target Platform:** Windows 10 / 11 (x64), Python 3.11+ (64-bit)

Only the differences from **[1.5.1](elden-disk-spec-v1.5.1.md)** are listed; everything else is unchanged.

## 0. Changelog (1.5.1 → 1.5.2)
See **[changes-version-1.5.2.md](../wahy/changes-version-1.5.2.md)** for the full table.

## 1. Build (`build`)
- Output: `./build/dist/<version>/eldendisk.exe`; work files in `./build/work`. `--clean` removes `./build` entirely. (Supersedes the `./dist` wording of 1.5.1.)
- Both engines use the same config list: `offsets.json` and `chr_state_ids.json` (from `code/` or the project root, whichever exists).
  - `--embed-configs`: PyInstaller `--add-data`, Nuitka `--include-data-files`. Nothing is copied next to the exe.
  - otherwise: the files are copied to `./build/dist/<version>/` for both engines.
- `disk.schema.json` is **not** bundled (tests only).
- Nuitka is invoked as `python -m nuitka --onefile --output-dir=<dist> --output-filename=eldendisk.exe [...]`.

## 2. Config resolution (`get_resource_path`)
| Context | Order |
|:---|:---|
| Compiled exe (PyInstaller `sys.frozen` or Nuitka `__compiled__`) | 1. file next to the exe, 2. embedded copy (`_MEIPASS` / Nuitka data dir), 3. source/project folders, 4. bare relative name |
| `python -m eldendisk` | `default_dir`, `code/`, project root |
`run -v` logs `[config] offsets=<path> (embedded|external|source|missing)` (same for effects).

## 3. Profiles (`offsets.json`)
- `vitals` **required** → otherwise `UNSUPPORTED_VERSION: profile incomplete: vitals is not set ...`.
- `at_grace`: `null` (feature off) or object with required non-empty `equals`; any other value is rejected. No default animation ID.

## 4. Persistence
- A document whose only difference from the last written one is a `times.buff_duration` value is written at most every `--timer-interval` seconds (default `0.5`, `0` = every change). All other differences are written immediately, including a buff appearing/expiring.
- `JsonLogger.write` returns `False` (never raises) when the file stays locked after 5 attempts; a failed write is retried naturally on the next changed document. One warning is printed per busy streak.

## 5. Timestamps
`times.last_activated_at` is `YYYY-MM-DD HH:MM:SS.ffffff±HH:MM` (UTC offset always present; the sampler uses UTC). The `animations` viewer prints local time with offset.

## 6. Session reset
`WAITING_FOR_WORLD` without an error (title screen / loading) for ≥ 10 s clears: rune baseline, `_was_at_grace`, buff activation times, last animation. Read failures (non-empty `last_error`) never start the clock.

## 7. CLI additions
`run --timer-interval SEC`, `run --no-idle`. Deprecated no-ops (hidden): `effects --effects`, `animations -q`.

## 8. Verification
- `python -m pytest` (68 tests): adds CLI, build-command, config-resolution, throttling, logger-lock, launcher, memory-helper, session-reset and profile-policy tests.
- PyInstaller build verified on Linux (`build -c -em`, embedded vs. external config lookup in the frozen binary). Windows `.exe` and Nuitka builds need a run on the target machine (V-07 below).
- **V-07 (manual, Windows):** `python -m eldendisk build -c -em` and `build -c -e nuitka -em`; run each `eldendisk.exe run -v` and confirm `[config] ... (embedded)`.

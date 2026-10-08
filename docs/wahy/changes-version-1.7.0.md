> [!NOTE]
> **Version:** `1.7.0`  
> **Status:** IMPLEMENTED (unit and golden tests; a tool-built file has not been swapped into the real game yet, see spec 1.7.0 section 10)  
> **Last Updated:** _2026-10-09_

**Summary:** **Extensions.** New main command `extension`; its first extension `customize-items` builds a `regulation.bin` with your own incantation from a JSON file (`sources/items.json`, embedded in the exe), offline, inside the tool. With the vault ON, `run` builds it every time and the vault swaps it in. The vault now swaps the file it is given instead of looking in its own folder.

_(baseline: **[changes-version-1.6.4.md](changes-version-1.6.4.md)**; design: **[elden-disk-spec-v1.7.0.md](../specs/elden-disk-spec-v1.7.0.md)**)_

---

## Wahy

| # | Change | Where |
|:-:|:---|:---|
| 1 | **`extension --list`** and **`extension customize-items --add all\|ID`** (`--dry-run`, `--spec`, `--source`, `--game-dir`, `--extension-dir`). | `commands/extension.py`, `__main__.py` |
| 2 | **Build in the tool, stdlib only.** AES-256-CBC, zstd frame reading/rewriting (block by block, as the game accepts), BND4/PARAM containers, field layouts of four tables (generated from Paramdex), recipe, preflight. | `extension/customize_items/` |
| 2b | **The spec is `customize_items/sources/items.json`** (renamed from `examples/z4.json`; the Z4 item). `build -c -em` embeds it like `offsets.json` / `chr_state_ids.json`; found as `--spec`, next to the exe, embedded, or in `sources/`. An empty item list is valid: nothing to build, nothing swapped. | `commands/build.py`, `commands/extension.py` |
| 3 | **One item per build** (Level 2a); `name`/`description` stored only; colour, icon and text refused as Level 3. | `spec.py`, `service.py` |
| 4 | **Build every time, no state.** No manifest, no verified copy, no skip logic, no base copy, no `--force`. The base is always the game's own `regulation.bin`, checked against the known 1.17.1 hash (a modified file is refused with a `vault restore` hint). A build takes about 15 s. | `service.py` |
| 5 | **Preflight R1-R6** on the finished bytes before anything is written; deterministic output (content-derived IV). | `preflight.py`, `container.py` |
| 6 | **Files moved.** The output lives in `%LOCALAPPDATA%\EldenDisk\extension\customize-items\`, not in the vault. | `extension/__init__.py` |
| 7 | **Vault takes the file from the caller:** `backup_regulation(snap, game_dir, world)`, `regulation_problems(game_dir, world)`, `world_info(world)`; `Hooks.regulation_world`. Backup, swap, restore and RG1-RG7 unchanged. | `vault/vault.py`, `host/host.py` |
| 8 | **`run` builds** (vault ON only; no `--extension-on` flag, the extension depends on the vault's permission like `write`): spec -> build on the game's file -> output -> `regulation_world`. A build or spec error stops `run` with exit 1 before any snapshot. Vault OFF: no build. A vault that owes a restore: no build. `--regulation FILE` overrides; `--spec`, `--extension-dir`. `<vault>\regulation\` (1.6.4) is no longer read, with one warning. | `commands/run.py` |
| 9 | **`vault status`** drops the "file to swap" row and reports the unused legacy file. | `commands/vault.py` |
| 10 | **Tests.** 765 pass, 14 skipped (was 659): five new files (spec, primitives, service, command, golden), `test_regulation.py` / `test_run_command.py` / `test_host.py` adapted, and architecture rules for the new package (own boundary, stdlib only). The golden tests (13) need the pristine `regulation.bin` (`ELDENDISK_REGULATION_ORIG`) and pass: Z4 comes out with SHA-256 `1aa16ee0…db5277b`. | `tests/` |
| 11 | **Dev pipeline** stays at 3 steps (tests, build with `-em`, `run -v`); the extension is built inside `run`. `--extension-dir` / `--spec` go to `run`. | `tools/dev_pipeline.py`, `tests/test_dev_pipeline.py` |
| 12 | **Docs.** Spec 1.7.0, this file, manual test plan 1.7.0, README, CLI references. | `docs/` |

## Behaviour changes

- `<vault>\regulation\regulation.bin` is **no longer swapped**. Edit `sources/items.json` (it is built on every `run --vault-on`), or pass `--regulation FILE`.
- `run --vault-on` starts about 15 s later (the build).
- `vault status` no longer lists a file to swap.
- Version `1.7.0`.

## Decisions taken while implementing

- **Exactly one item per file** (2a) until table growth is researched.
- **`run` builds every time** (vault ON): simple, and it exercises the customize code on every run; the vault guards the game's file. A failed build stops `run`.
- **Base = the game's file, always.** One item per file, so a modified file is never modified again.
- **Fixed ids** for the new rows (recipe constants); the spec cannot move them.
- **Data as Python modules** (`paramdefs.py`) so that the exe needs no extra data files.
- **Deterministic IV:** the same spec gives the same file, which makes the golden hash possible.

## Not done / open

- A tool-built file has not been swapped into the real game yet (manual plan 1.7.0 SW1-SW3); the swap of 1.6.4 is still unit-tested only.
- Level 2b (several items), Level 3 (text, icon, colour).
- Poise effect unproven in the game; Paramdex licence unchecked; only one runtime verifier.

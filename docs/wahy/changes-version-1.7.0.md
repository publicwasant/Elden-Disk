> [!NOTE]
> **Version:** `1.7.0`  
> **Status:** IMPLEMENTED (unit and golden tests; a tool-built file ran in the real game; the secured path and poise are not yet tried, see spec 1.7.0 section 10)  
> **Last Updated:** _2026-10-09_

**Summary:** **Extensions.** New main command `extension`; its first extension `customize-items` builds a `regulation.bin` with your own incantation from a JSON file (`items.draft.json`, embedded in the exe), offline, inside the tool. A file goes draft → built (gate passed) → secured (`--secure`, after you tried it). With the vault ON, `run` swaps the secured copy without building while the draft is unchanged; otherwise it builds, the gate judges the file, and the vault swaps it in. The vault now swaps the file it is given instead of looking in its own folder.

_(baseline: **[changes-version-1.6.4.md](changes-version-1.6.4.md)**; design: **[elden-disk-spec-v1.7.0.md](../specs/elden-disk-spec-v1.7.0.md)**)_

---

## Wahy

| # | Change | Where |
|:-:|:---|:---|
| 1 | **`extension --list`**, **`extension customize-items --add all\|ID`** (`--dry-run`, `--spec`, `--source`, `--game-dir`, `--extension-dir`) and **`--secure`**. | `commands/extension.py`, `__main__.py` |
| 2 | **Build in the tool, stdlib only.** AES-256-CBC, zstd frame reading/rewriting (block by block, as the game accepts), BND4/PARAM containers, field layouts of four tables (generated from Paramdex), recipe, preflight, gate. | `extension/customize_items/` |
| 2b | **The draft is `customize_items/items.draft.json`** and the schema `items.schema.json` sits next to it (no `sources/` or `schema/` folders; the Z4 item). `build -c -em` embeds the draft like `offsets.json` / `chr_state_ids.json`; found as `--spec`, next to the exe, embedded, or in the package. An empty item list is valid: nothing to build, nothing swapped. | `commands/build.py`, `commands/extension.py` |
| 3 | **One item per build** (Level 2a); `name`/`description` stored only; colour, icon and text refused as Level 3. | `spec.py`, `service.py` |
| 4 | **Draft → built → secured.** `regulation.bin` (latest build), `regulation.secured.bin` and `items.secured.json` (draft snapshot, hashes, recipe version, base). `run` swaps the secured copy without building when the draft (name/description/whitespace/key order ignored), the secured file's hash, the base and the recipe version all match; otherwise it prints the reasons and a field-by-field diff and builds. The game's file is checked against the known 1.17.1 original on every path. No `--force` (delete `items.secured.json`). | `service.py` |
| 5 | **The gate** (R1-R6 plus G5 independent recompute, G11 id chain, G12 shop range and unique stock flag, G13 heal sign, G16 optional second decoder `compression.zstd`) judges the file **read back from disk**; any problem or warning is a stop: the temporary file is deleted, nothing is swapped, `run` exits 1 and the game is not started. It replaces the old in-build preflight and decrypt round-trip, so the build time is the same. Deterministic output (content-derived IV). | `gate.py`, `preflight.py`, `recipes.py`, `container.py` |
| 6 | **Files moved.** The output lives in `%LOCALAPPDATA%\EldenDisk\extension\customize-items\`, not in the vault. | `extension/__init__.py` |
| 7 | **Vault takes the file from the caller:** `backup_regulation(snap, game_dir, world)`, `regulation_problems(game_dir, world)`, `world_info(world)`; `Hooks.regulation_world`. Backup, swap, restore and RG1-RG7 unchanged. | `vault/vault.py`, `host/host.py` |
| 8 | **`run` builds** (vault ON only; no `--extension-on` flag, the extension depends on the vault's permission like `write`): draft -> secured copy, or build + gate -> `regulation_world`. A build, draft or gate error stops `run` with exit 1 before any snapshot. After a session that built, a hint says to run `--secure`. Vault OFF: no build. A vault that owes a restore: no build. `--regulation FILE` overrides; `--spec`, `--extension-dir`. `<vault>\regulation\` (1.6.4) is no longer read, with one warning. | `commands/run.py` |
| 9 | **`vault status`** drops the "file to swap" row and reports the unused legacy file. | `commands/vault.py` |
| 10 | **Tests.** Six new files (spec, primitives, service, gate, command, golden), `test_regulation.py` / `test_run_command.py` / `test_host.py` adapted, and architecture rules for the new package (own boundary, stdlib only). The service matrix covers first run, unchanged, changed price with diff, name-only change, secured file missing/edited, recipe version, other base, damaged record, failed gate and half-done `--secure`. The golden tests need the pristine `regulation.bin` (`ELDENDISK_REGULATION_ORIG`): Z4 comes out with SHA-256 `1aa16ee0…db5277b` and passes the gate; damaged files do not. | `tests/` |
| 11 | **Dev pipeline** stays at 3 steps (tests, build with `-em`, `run -v`); the extension is built inside `run`. `--extension-dir` / `--spec` go to `run`. | `tools/dev_pipeline.py`, `tests/test_dev_pipeline.py` |
| 11b | **Console polish.** The vault backup debug line is short (`save <steamID> -> snapshot <name>`); existing Windows paths in console output are clickable hyperlinks (OSC 8) in Windows Terminal, VS Code and similar; `ELDENDISK_LINKS=1/0` forces on/off; `-v` logs `D client : clickable paths on|off: <why>`; the log file is never changed. | `host/host.py`, `ui.py` |
| 11c | **The `client` log line is the command (program name only).** `D client : version 1.7.0`, then `D client : eldendisk.exe run -v` (from `sys.orig_argv`; `python -m eldendisk …` from source). On the `-v` console the command is cyan; the log file stays plain. | `logsetup.py`, `ui.py` |
| 11d | **Status line names `read` too, words in backticks are cyan.** `game : running, pid N; \`read\` allowed, \`write\` allowed` (or `\`write\` not allowed`). On a colour console the `backticked` words are cyan (backticks hidden); the log file keeps them. | `host/host.py`, `ui.py` |
| 11e | **Log tags fit the column.** `cli` is now `client`, `extension` is now `ext` (the tag column is 6 wide, `extension` pushed the colon out). A bare `regulation.bin` is cyan on a colour console (not when it ends a path). | `logsetup.py`, `__main__.py`, `commands/extension.py`, `commands/run.py`, `ui.py` |
| 12 | **Docs.** Spec 1.7.0, this file, manual test plan 1.7.0, README, CLI references. | `docs/` |

## Principle

**Principle: the other world never touches the real one.** Everything done in a `run` session (the rules, the items, the values written, the changes to the save) exists for that session only. When the game exits, the vault puts back the save and the game's own `regulation.bin`, byte for byte, checked by hash. Nothing carries over: not the items, not the progress. The real playthrough stays exactly as it was, and it can be finished with no mod at all. The sandbox is for playing around on the days you want to; it is never required, and nothing in the real world can collapse because of it.

## Behaviour changes

- `<vault>\regulation\regulation.bin` is **no longer swapped**. Edit `items.draft.json`, or pass `--regulation FILE`.
- `run --vault-on` starts about 20 s later when it has to build; with a secured copy and an unchanged draft it does not build.
- `vault status` no longer lists a file to swap.
- Version `1.7.0`.

## Decisions taken while implementing

- **Exactly one item per file** (2a) until table growth is researched.
- **Securing is manual** (`--secure`): the host never reads game memory, so the tool cannot know the item worked in the game. Gate policy: any warning is a stop. All stored blocks are forbidden because the game's rule is unknown.
- **Base = the game's file, always.** One item per file, so a modified file is never modified again.
- **Fixed ids** for the new rows (recipe constants); the spec cannot move them.
- **Data as Python modules** (`paramdefs.py`) so that the exe needs no extra data files.
- **Deterministic IV:** the same spec gives the same file, which makes the golden hash possible.

## Not done / open

- Confirmed on Windows (2026-10-09): `run` built (16 s, gate passed, second decoder agreed on Python 3.14.5), the item worked in the game, restore byte-identical (SW1-SW3). Not yet tried: poise (SW10) and the secured path (SC1-SC10).
- Level 2b (several items): measured and planned (spec 1.7.0 section 10b), nothing built; first a small in-game test (T1: move the Goods table to the end of the body). Level 3 (text, icon, colour).
- Poise effect unproven in the game; Paramdex licence unchecked; only one runtime verifier.

> [!NOTE]
> **Version:** `1.7.0`  
> **Status:** IMPLEMENTED (unit and golden tests; a tool-built file ran in the real game; the params workbench was tried in the game 2026-10-09 (manual plan PW); the secured path and poise are not yet tried, see spec 1.7.0 section 10)  
> **Last Updated:** _2026-10-09_

**Summary:** **Extensions.** New main command `extension`; its first extension `innovate-spells` builds a `regulation.bin` with your own incantation from a JSON file (`extension.json`, embedded in the exe), offline, inside the tool. A file goes design → built (gate passed) → secured (`--secure`, after you tried it). With the vault ON, `run` swaps the secured copy without building while the design is unchanged; otherwise it builds, the gate judges the file, and the vault swaps it in. The vault now swaps the file it is given instead of looking in its own folder.

_(baseline: **[changes-version-1.6.4.md](changes-version-1.6.4.md)**; design: **[elden-disk-spec-v1.7.0.md](../specs/elden-disk-spec-v1.7.0.md)**)_

---

## Wahy

| # | Change | Where |
|:-:|:---|:---|
| 1 | **`extension --list`**, **`extension innovate-spells --add all\|ID`** (`--dry-run`, `--spec`, `--source`, `--game-dir`, `--extension-dir`) and **`--secure`**. | `commands/extension.py`, `__main__.py` |
| 2 | **Build in the tool, stdlib only.** AES-256-CBC, zstd frame reading/rewriting (block by block, as the game accepts), BND4/PARAM containers, field layouts of four tables (generated from Paramdex), recipe, preflight, gate. | `extension/innovate_spells/` |
| 2b | **The design is `code/extension.json`**, section `innovate_spells`: `maximum` (64) and `slots`, one key per slot in order; a filled slot is a spell keyed by its id, an empty slot is `null`. The slot's place fixes the rows it takes in the game (every slot is built, as rows appended to the four tables; `shop` optional, slots 1-7 only can have one). The schema `spells.schema.json` stays in the `innovate_spells` package. `build -c -em` embeds the design like `offsets.json` / `chr_state_ids.json`; found as `--spec`, next to the exe, embedded, or in `code/`. No filled slot is valid: nothing to build, nothing swapped. The commit record `spells.commit.json` (format 2) now also lists the rows each spell took. | `commands/build.py`, `commands/extension.py`, `innovate_spells/spec.py`, `service.py` |
| 3 | **One item per build** (Level 2a); `name`/`description` stored only; colour, icon and text refused as Level 3. | `spec.py`, `service.py` |
| 4 | **Design → built → secured.** `regulation.bin` (latest build), `regulation.secured.bin` and `spells.commit.json` (design snapshot, hashes, recipe version, base). `run` swaps the secured copy without building when the design (name/description/whitespace/key order ignored), the secured file's hash, the base and the recipe version all match; otherwise it prints the reasons and a field-by-field diff and builds. The game's file is checked against the known 1.17.1 original on every path. No `--force` (delete `spells.commit.json`). | `service.py` |
| 5 | **The gate** (R1-R6 plus G5 independent recompute, G11 id chain, G12 shop range and unique stock flag, G13 heal sign, G16 optional second decoder `compression.zstd`) judges the file **read back from disk**; any problem or warning is a stop: the temporary file is deleted, nothing is swapped, `run` exits 1 and the game is not started. It replaces the old in-build preflight and decrypt round-trip, so the build time is the same. Deterministic output (content-derived IV). | `gate.py`, `preflight.py`, `recipes.py`, `container.py` |
| 6 | **Files moved.** The output lives in `%LOCALAPPDATA%\EldenDisk\extension\innovate-spells\`, not in the vault. | `extension/__init__.py` |
| 7 | **Vault takes the file from the caller:** `backup_regulation(snap, game_dir, world)`, `regulation_problems(game_dir, world)`, `world_info(world)`; `Hooks.regulation_world`. Backup, swap, restore and RG1-RG7 unchanged. | `vault/vault.py`, `host/host.py` |
| 8 | **`run` builds** (vault ON only; no `--extension-on` flag, the extension depends on the vault's permission like `write`): design -> secured copy, or build + gate -> `regulation_world`. A build, design or gate error stops `run` with exit 1 before any snapshot. After a session that built, a hint says to run `--secure`. Vault OFF: no build. A vault that owes a restore: no build. `--regulation FILE` overrides; `--spec`, `--extension-dir`. `<vault>\regulation\` (1.6.4) is no longer read, with one warning. | `commands/run.py` |
| 9 | **`vault status`** drops the "file to swap" row and reports the unused legacy file. | `commands/vault.py` |
| 10 | **Tests.** Six new files (spec, primitives, service, gate, command, golden), `test_regulation.py` / `test_run_command.py` / `test_host.py` adapted, and architecture rules for the new package (own boundary, stdlib only). The service matrix covers first run, unchanged, changed price with diff, name-only change, secured file missing/edited, recipe version, other base, damaged record, failed gate and half-done `--secure`. The golden tests need the pristine `regulation.bin` (`ELDENDISK_REGULATION_ORIG`): Z4 comes out with SHA-256 `1aa16ee0…db5277b` and passes the gate; damaged files do not. | `tests/` |
| 11 | **Dev pipeline** stays at 3 steps (tests, build with `-em`, `run -v`); the extension is built inside `run`. `--extension-dir` / `--spec` go to `run`. | `tools/dev_pipeline.py`, `tests/test_dev_pipeline.py` |
| 11b | **Console polish.** The vault backup debug line is short (`save <steamID> -> snapshot <name>`); existing Windows paths in console output are clickable hyperlinks (OSC 8) in Windows Terminal, VS Code and similar; `ELDENDISK_LINKS=1/0` forces on/off; `-v` logs `D client : clickable paths on|off: <why>`; the log file is never changed. | `host/host.py`, `ui.py` |
| 11c | **The `client` log line is the command (program name only).** `D client : version 1.7.0`, then `D client : run: eldendisk.exe run -v` (from `sys.orig_argv`; `python -m eldendisk …` from source). On the `-v` console the command is cyan; the log file stays plain. | `logsetup.py`, `ui.py` |
| 11d | **Status line names `read` too, words in backticks are cyan.** `game : running, pid N; \`read\` allowed, \`write\` allowed` (or `\`write\` not allowed`). On a colour console the `backticked` words are cyan (backticks hidden); the log file keeps them. | `host/host.py`, `ui.py` |
| 11e | **Log tags fit the column.** `cli` is now `client`, `extension` is now `ext` (the tag column is 6 wide, `extension` pushed the colon out). A bare `regulation.bin` is cyan on a colour console (not when it ends a path). | `logsetup.py`, `__main__.py`, `commands/extension.py`, `commands/run.py`, `ui.py` |
| 11f | **`effect.visual: "none"` (or an explicit `null`).** The heal buff leaves no fire on the body (SpEffect `vfxId` -1); the cast flash of Flame! Grant Me Strength (Magic `castSfxId`/`fireSfxId`) is unchanged. The gate checks `vfxId` against the design. `flame` and `flask` build the same bytes as before (recipe version stays 1). | `spec.py`, `spells.schema.json`, `recipes.py` |
| 11g | **Log messages name the save files.** "save restored" is now `` `ER0000.sl2` restored, byte-identical to the snapshot``; with several files: `` `ER0000.sl2`, `ER0000.sl2.bak` ``, each cyan on a colour console. Same for the archive, keep, pre-restore and vault OFF messages. | `vault/vault.py`, `vault/recover.py`, `host/host.py`, `commands/vault.py` |
| 11h | **Spell ids are purple.** On a colour console the ids of the design's spells are purple in the lines of the `ext` tag (the list of names being built, a diff line `id.shop.price  1 -> 2`), in the concise view and in `-v`. The log file keeps plain text; an id inside a path or a longer word, an error line and other tags are left alone. | `ui.py`, `commands/extension.py`, `tests/test_ui.py` |
| 11i | **File names are orange.** On a colour console every file name with an extension (`regulation.bin`, `ER0000.sl2`, `ER0000.sl2.bak`, `ER0000.err`, `ER0000.err.bak`, `steam_autocloud.vdf`, `.json`, `.exe`, `.log`, ... : `ui.FILE_EXTENSIONS`) is orange (256-colour 208), with or without backticks, and so is the name at the end of a path (`...\Game\regulation.bin`); folders are not coloured and the OSC 8 link keeps a clean url (only the visible text is coloured). Warnings, errors and debug lines keep their own colour around it. Things that only look like files (`1.7.0`, `3.14.5`, `id.shop.price`) are left alone. The log file stays plain. | `ui.py`, `tests/test_ui.py` |
| 12 | **Docs.** Spec 1.7.0, this file, manual test plan 1.7.0, README, CLI references. | `docs/` |

## Wahy (params workbench, Phase 1, 2026-10-09)

| # | Change | Where |
|:-:|:---|:---|
| 12 | **`read --param TABLE.ID[.FIELD] ...`**: any row of Goods, Magic, SpEffect, Bullet, AtkParam_Pc, ShopLineup, every field by name (a tree; `--flat` one path per value; `--json`). The decoder takes the bytes of a row, so one decoder serves the game and a file. | `game/paramtables.py`, `game/paramlayouts.py` (generated by `tools/gen_paramdefs.py`), `commands/read.py` |
| 13 | **`read --probe-params`**: finds the param files of the other tables from the global of the known chain (the result is the `params.catalog` in `offsets.json`). | `game/probe.py` |
| 14 | **`write --set params.<Table>.<id>.<field>=VALUE`**: any numeric field of any row of the six tables; range checked by type and bit width (no clamp), a note for fields that hold another row's id; `--reset` takes a field, a row, a pattern or `all`. | `writer/paramedit.py`, `writer/writer.py`, `commands/write.py` |
| 15 | **`--reset` uses the game's own value**, kept in `<vault>\params-snapshot.json` at the first change in a game process (tied to pid and start time; a new game process starts empty). | `writer/paramedit.py` |
| 16 | **`read --param-check [FILE]`**: compares the six tables of a `regulation.bin` (default: the one in the game folder) with the game, row by row, byte for byte, and names the fields that differ; exit 0 only when all agree; `--json`. | `commands/paramcheck.py`, `game/paramtables.py` (`Tables.all_rows`) |
| 17 | The reader accepts a table whose gap before the data is any multiple of 4 bytes (the grown Goods, Magic and ShopLineup files have gaps of 184, 168 and 56). | `game/params.py` |
| 18 | **Tests:** `test_probe.py`, `test_param_tables.py`, `test_param_write.py`, `test_param_check.py` and additions to `test_params.py`, `test_main.py`, `test_read_command.py` (about 1,000 tests in all; the golden ones need the game's original `regulation.bin`). | `code/tests/` |

Measured in the game: a Magic row is read at the cast, a Bullet row when the bullet is created, a written value survives Quit to Title and Continue, a changed row acts on what is created afterwards; the slot-1 build equals the game on every row of the six tables. Manual plan: PW1-PW11. Plan and results: [phase1-params-workbench.md](../phase1-params-workbench.md); what comes next: [roadmap-innovate-spells.md](../roadmap-innovate-spells.md).

## Principle

**Principle: the other world never touches the real one.** Everything done in a `run` session (the rules, the items, the values written, the changes to the save) exists for that session only. When the game exits, the vault puts back the save and the game's own `regulation.bin`, byte for byte, checked by hash. Nothing carries over: not the items, not the progress. The real playthrough stays exactly as it was, and it can be finished with no mod at all. The sandbox is for playing around on the days you want to; it is never required, and nothing in the real world can collapse because of it.

## Behaviour changes

- `<vault>\regulation\regulation.bin` is **no longer swapped**. Edit `extension.json`, or pass `--regulation FILE`.
- `run --vault-on` starts about 20 s later when it has to build; with a secured copy and an unchanged design it does not build.
- `vault status` no longer lists a file to swap.
- Version `1.7.0`.

## Phase 2.1: `kind: clone` (2026-10-09)

`extension.json` can now hold a spell that is a copy of a game spell: `{"kind": "clone", "from": 6210, "fp_cost": 5, "requires": {...}, "shop": {...}, "set": {"Magic.6210.slotLength": 1}}`. Only the Goods row and the Magic row of the template are copied (the copy keeps calling the template's Bullet / attack / SpEffect rows), plus the shop line when sold; no new table. `kind` defaults to `buff`, and the canonical form of a buff is unchanged (the Z4 hash and the secured files stay valid). `type` follows the template; `set` takes numbers of the two copied rows; id fields are refused in this version. New gate check `check_clone`. Planned kinds (`enchant`, `projectile`, `attack`) are refused by name. Spec 1.7.0 section 4b. Tests: `test_ext_clone.py` (66). Passed in the game 2026-10-09 (CL1, CL2): bought, memorized and cast like the normal Black Flame at 5 FP; every row equal in `read --param-check`. CL3 (`set`: `Magic.6210.slotLength`) passed 2026-10-10; CL4-CL5 are optional.

## Phase 2.2: `kind: enchant` and `buff` with `from` (2026-10-10)

`{"kind": "enchant", "from": 6250, "set": {"SpEffect.1626000.effectEndurance": 600}}` copies Black Flame Blade **and the SpEffect rows it owns** (the rows that no more than 3 spells of the game reach; generic rows such as 500 and 505 stay shared), points the copies at each other and `set` can change them (`SpEffect.<template row id>.<field>`, link fields refused). `buff` with `from` is the same for a buff spell (6050); `buff` without `from` (the heal-over-time spell) and the Z4 hash are unchanged. A slot has a block of 8 SpEffect ids (`21951000 + (n-1)*8`). `chain.py` reads the Bullet and AtkParam_Pc tables only to count how many spells share each row. Gate `check_template` replaces `check_clone`. Tests: `test_ext_enchant.py` (42). E1 passed in the game 2026-10-10; E2-E4 are optional (manual test plan).

## Phase 2.3 (started 2026-10-10): the T7 test comes back

Re-applied from the copy kept earlier: the encoder fix for repeat-offset states (`reblock.encode_offsets_flex`, `rewrite_grow` carries the state to the next block; R3 allows that block to differ), `Bullet` as a fifth table in `TABLE_FILES` and `paramdefs.py` (`tools/gen_paramdefs.py` writes it), the recipe's `KEYS` / `NAME_FROM`, and `tools/envelope_test.py` (T7: the design plus 4 unreferenced Black Flame bullet copies; a file beyond the gate's numbers, checked in every other way). T7 passed in the game 2026-10-10 (a grown Bullet table, 20 re-encoded blocks, body +96,176, frame +174,944), so `MAX_CHANGED_BLOCKS` is now 20; the body and frame limits are unchanged. Two golden tests that expected the old limit now say that 16 spells pass and 64 are stopped by the growth (R7).

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

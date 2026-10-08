> [!NOTE]
> **Version:** `1.7.0`  
> **Status:** IMPLEMENTED (unit and golden tests; a tool-built file ran in the real game; the secured path (`--secure`) and poise are not yet tried, see section 10)  
> **Last Updated:** _2026-10-09_

# Elden-Disk spec 1.7.0: extensions and `customize-items` (draft → secured)

Reads on top of [spec 1.6.4](elden-disk-spec-v1.6.4.md) (the `regulation.bin` swap). Only what changes is written here. The research behind the build (why a frame is rewritten block by block, what the game rejected) is the [item-customization handbook](../experiments/item-customization/item-customization-handbook.md), Part VI.

## 1. Idea

**Principle: the other world never touches the real one.** Everything done in a `run` session (the rules, the items, the values written, the changes to the save) exists for that session only. When the game exits, the vault puts back the save and the game's own `regulation.bin`, byte for byte, checked by hash. Nothing carries over: not the items, not the progress. The real playthrough stays exactly as it was, and it can be finished with no mod at all. The sandbox is for playing around on the days you want to; it is never required, and nothing in the real world can collapse because of it.

1.6.4 swapped a `regulation.bin` that somebody else made. 1.7.0 makes it inside the tool, offline, from a small JSON file. A file goes through three states: **draft** (the JSON you edit) → **built** (a `regulation.bin` the gate passed; not yet tried in the game) → **secured** (a copy you confirmed in the game, kept next to a record of the draft it came from).

```
items.draft.json (embedded in the exe) --run: build on the game's own regulation.bin + gate--> regulation.bin --vault swaps--> the game (one session; the vault puts the game's file back)
                                       --extension customize-items --secure (game closed)--> regulation.secured.bin + items.secured.json
next run, draft unchanged: regulation.secured.bin is swapped; nothing is built, nothing is re-checked (about 20 s saved)
```

`extension` is a main feature like `read`, `write` and `vault`: a place for features that **build things for the game outside the game**. `customize-items` is the first. Because an extension touches game files, it **depends on the vault's permission**, like `write` needs the vault ON: with the vault ON (the default) `run` also runs the extension build; with the vault OFF it does not. There is no `--extension-on` flag. The vault is unchanged in purpose: it backs up, swaps the file it is given, and puts the original back.

The base is **always the game's own file**, checked against the known original on **every** path (also when the secured file is used); a modified file is never modified again.

Customize levels (the author's words): **L1** `write --set` (memory, live); **L2** a `regulation.bin` with copied/adapted rows under the game's own rules (this version, "2a": one item per file); **L3** truly new things (name, text, icon, colour): needs files inside the game's archives and a loader, not started.

## 2. Layout

```
code/eldendisk/extension/customize_items/items.draft.json    the draft: the item(s) you want in the game (you edit it)
code/eldendisk/extension/customize_items/items.schema.json   JSON schema of the draft (for editors; dev tests check it agrees with the validator)
%LOCALAPPDATA%\EldenDisk\extension\customize-items\          (--extension-dir overrides the folder)
    regulation.bin           the latest build (gate passed, not yet confirmed)
    regulation.secured.bin   a copy of the build you confirmed with --secure
    items.secured.json       the record: the draft snapshot, hashes of the secured file and of the base, recipe version
```

No base copy and no manifest are kept. `build -c -em` embeds `items.draft.json` in the exe like `offsets.json`; the draft is found as `--spec FILE`, else `items.draft.json` next to the exe, else the embedded copy, else the package in the source tree (`paths.get_resource_path`). Without `-em`, the file is copied next to the exe, where you can edit it without rebuilding the exe.

Code: `code/eldendisk/extension/` (registry) and `extension/customize_items/` (aes, zstd, fse, reblock, container, defs, paramdefs, bases, spec, recipes, preflight, **gate**, build, service). Standard library only. The package imports nothing else of the tool (`test_architecture.py`).

## 3. Commands

| Command | Does |
|:--|:--|
| `run` (vault ON) | **swaps `regulation.secured.bin` without building** when the secured state is valid (section 6); otherwise prints why and what changed, builds (about 20 s), and swaps the new `regulation.bin` after the gate passed |
| `run --vault-off` | no build, no swap (an info line says so) |
| `run --regulation FILE` | swaps that file instead (an experiment; vault ON only) |
| `run --spec FILE`, `--extension-dir DIR` | the draft; the folder of the files |
| `extension --list` | the draft (path, where it comes from, number of items), the secured state, the draft-vs-secured diff, the last build |
| `extension customize-items` | where the files are |
| `extension customize-items --add all` (or `--add <id>`) | builds like `run` does (always; never uses the secured file), without starting the game |
| &nbsp;&nbsp;`--dry-run` | build and run the gate in memory; write nothing |
| `extension customize-items --secure` | **game closed.** Runs the gate on `regulation.bin` against the current draft and the game's file; copies it to `regulation.secured.bin`, then writes `items.secured.json` (last). Stands alone (not with `--add` / `--dry-run`) |
| &nbsp;&nbsp;`--source FILE`, `--game-dir DIR` | the game's original `regulation.bin` (default: the one in the auto-detected game folder) |
| &nbsp;&nbsp;`--spec FILE`, `--extension-dir DIR` | as above |

There is no `--force`: delete `items.secured.json` to make the next `run` build. There is no automatic securing: the host never reads game memory, so it cannot know the item worked; you confirm it with `--secure`. After a session that **built**, `run` prints a hint to run `--secure`.

An empty `items` list is a valid draft: nothing to build, exit `0`, `run` swaps nothing. In `run`, a draft or build error (invalid draft, the game's file is not the known original) or a **failed gate** stops `run` with exit `1` **before** any snapshot or launch: nothing is swapped and the game is not started. If the vault still owes a restore from an earlier session, `run` does not build; the host refuses to start and says what to do.

Exit codes: `0` ok; `1` error (invalid draft, unknown base, gate failed); `2` usage.

## 4. The draft (`items.draft.json`, format 1)

One object, `items`: a list (empty = no items yet). Unknown fields are errors; every problem is listed with its path (`$.items[0].requires.faith: must be a whole number from 0 to 99`). `name` and `description` are **stored only**; `colour`, `icon_file`, `text` and similar are refused ("Level 3").

| Field | Meaning (Z4 value) |
|:--|:--|
| `id` | `[a-z0-9-]{1,40}`, unique (`reverse-curse-technique`) |
| `type` | `incantation` |
| `requires` | `intelligence`, `faith`, `arcane` 0-99 (45 / 15 / 10) |
| `fp_cost`, `stamina_cost` | 0-999 (80 / 0) |
| `cast_motion` | `flame-grant-me-strength` (default) or `black-flame-blade` (`Magic.refType` 31 / 32) |
| `effect` | heal over time: `heal_hp_per_tick`, `restore_fp_per_tick`, `stamina_regen_speed`, `tick_seconds`, `duration_seconds`, `visual` `flame`/`flask` (60 / 4 / 100 / 0.5 / 15 / flame) |
| `poise_while_casting_seconds` | optional; hyper armor (Endure-style poise buff, no damage reduction) while casting (2.0) |
| `shop` | `price` 1..99,999,999, `stock` -1 (unlimited) or 1..99 (34590 / 1) |

Ids of the new rows (Goods/Magic `2230000`, SpEffect `21950111`, shop line `100508`, stock flag `150080`, poise row `102006`) are fixed by the recipe in this version. Level 2a builds **exactly one item per file**; with more in the spec, `--add all` is an error and `--add <id>` builds that one (Level 2b, several items, needs table growth, which is untested).

## 5. How a file is built

1. validate the spec (an invalid spec stops here; the existing build is untouched);
2. read the base: the game's own `regulation.bin` (or `--source`), after checking its SHA-256 against the known original of 1.17.1; any other file is refused (hint: `vault restore`, or Steam *verify integrity*);
3. decrypt (AES-256-CBC), read the DCX/zstd frame, BND4 and the four PARAM tables (EquipParamGoods, Magic, SpEffectParam, ShopLineupParam); check that writing them back unchanged reproduces the original;
4. apply the recipe: the never-used dummy row at the end of each table becomes the new row (its id changes, it stays sorted; no table grows), cloned from real rows and then overwritten (section 4); the shop line is a free line of the merchant's range;
5. re-encode only the 64 KiB blocks whose bytes changed, as ordinary compressed blocks, steering the repeat-offset registers so the following original blocks stay decodable; shape the file tail like the original (handbook Chapters 9-11);
6. encrypt with an IV derived from the content (same input, same bytes; the game accepts any IV); 7. write a temporary file and fsync it; 8. read it back and run the **gate** (section 7) on those bytes; 9. only if the gate passes, `os.replace` it to `regulation.bin`. A failed gate deletes the temporary file; `regulation.bin` and the secured files stay as they were.

Reference result: the shipped `items.draft.json` (Z4) gives a container whose decrypted SHA-256 is `1aa16ee0dbcbc5902cef2b6eb29bd542f42b2158fcdb44c221c187280db5277b` (2,071,472 bytes), the Z4 file that passed in the real game.

## 6. When `run` builds and when it does not

`run` (vault ON) swaps `regulation.secured.bin` without building and without the gate **only if all of these hold**:

1. the draft equals the secured spec (`spec.build_view`: field by field; `name`, `description`, whitespace and key order do not count);
2. SHA-256 of `regulation.secured.bin` equals the record;
3. the SHA-256 of the game's `regulation.bin` equals the base recorded and is the known 1.17.1 original (this check also runs on the build path);
4. `RECIPE_VERSION` equals the record.

Otherwise it builds and prints **the reasons** (no secured build yet; the draft changed; the secured file is missing or its hash differs; the recipes changed; the base is another file; the record cannot be read) and, for a changed draft, the **diff** field by field, for example `reverse-curse-technique.shop.price  34590 -> 40000`, before the long step.

## 7. The gate (necessary, not sufficient)

The gate (`gate.py`) judges the **bytes of the file read back from disk**, not what the builder believes it wrote. It replaces the old in-build preflight and decrypt round-trip (same time). **Any problem, and any warning, is a stop** (including more than 11 re-encoded blocks). The only real test of a file is the game.

| Rule | Checks |
|:--|:--|
| G0 | the file decrypts |
| R1 | the frame decodes to exactly the intended body, recomputed independently from the draft and the game's file (G5) |
| R2 | no stored/RLE block that the original did not have in the same place; same block count and flags; edited blocks are compressed and < 128 KiB; **more than 11 re-encoded blocks is a stop** (11 is the most tested in the game) |
| R3 | blocks whose decoded bytes did not change are byte-identical (only the literal-size header form of raw-literal blocks, or the conversion of a Huffman-treeless follower to raw literals, may differ) |
| R4 | DCX header: only the two size fields differ and they are right; exactly 2 zero bytes after the frame; length 16 + a multiple of 16 |
| R5 | BND4: same entries; only the four tables differ |
| R6 | PARAM: same row size, row count, header and strings; sorted; the set of rows removed / added / changed equals the recipe's declared footprint |
| G5 | Magic and SpEffect fields (costs, requirements, cast motion, effect values, poise) equal the draft |
| G11 | the id chain: Goods, Magic, SpEffect and the shop line exist; Magic points to the SpEffect |
| G12 | the shop line is inside the merchant's range 100500-100524; the stock flag belongs to that line only |
| G13 | heal sign: `changeHpPoint` / `changeMpPoint` are negative for a heal (a positive value drains the player) |
| G16 | a second decoder (`compression.zstd`, Python 3.14), when this Python has one, decodes the frame to the same bytes. It is imported by name inside `try`; if it is missing the gate only notes it. Agreed on the author's Python 3.14.5 |

## 8. `run` and the vault

- `run` decides (section 6), builds if needed, then passes the path to the host (`Hooks.regulation_world`); the vault methods take that path (`backup_regulation(snap, game_dir, world)`, `regulation_problems(game_dir, world)`, `world_info(world)`). Backup, record, swap, restore and RG1-RG7 of spec 1.6.4 are unchanged. The extension only **reads** the game's file; the vault does the swap.
- The banner row `regulation` says whether the file is the secured copy or a new build.
- Log order: `extension ...` lines (draft, reasons, diff, building, gate passed or failed), then the host lines (PREFLIGHT, SNAPSHOTTING, READY).
- `--regulation FILE` wins over everything.
- **Legacy:** `<vault>\regulation\regulation.bin` (1.6.4) is no longer read; `run` and `vault status` say so.
- Vault OFF never swaps and never builds.

## 9. Failures

| Situation | Result |
|:--|:--|
| invalid `items.draft.json` | exit `1`, fields named; nothing written (`run` does not start) |
| the game's file is not the known original | exit `1`; nothing written; hint: close the game if it runs, `vault restore`, or Steam *verify integrity*; `run --vault-off` starts the game without the extension |
| a recipe row is missing | exit `1`: "not the 1.17.1 regulation.bin" |
| the gate fails (build) | `GATE FAILED: this regulation.bin is NOT safe for the game; nothing was swapped`, rules listed, exit `1`, the game is not started; the temporary file is deleted, `regulation.bin` and the secured files are untouched |
| the gate fails (`--secure`) | same message; nothing secured |
| `--secure` with no build, or a build made from another draft | exit `1` ("build it first" / rule R1) |
| killed during `--secure` | the bin may be written without the record = "not secured" = the next `run` builds |
| killed during a build | a temporary file only; the previous output is intact; the game's file was only read |

## 10. Open

- **Confirmed in the real game (2026-10-09, Windows, Python 3.14.5):** a tool-built Z4 swapped by `run --vault-on` (SW1-SW3): built in 16 s with the gate passed (11 blocks re-encoded), the item was sold and cast, healed, and beat a boss with infinite Black Flame via `write`; the save and `regulation.bin` were restored byte-identical. **Not yet tried in the game:** poise (SW10) and the secured path (SC1-SC10).
- The gate is a necessary condition. The rule the game uses to accept or reject a frame is unknown (stored blocks were rejected in several tests and accepted in others), so all stored blocks are forbidden.
- `compression.zstd` (G16) ran on a real Python 3.14.5 and agreed with our decoder. On Python 3.13 or older the gate only notes that it is not available.
- `SpEffect 102006` ("Unused" in community lists) is overwritten; the poise effect is not proven in the game.
- Level 2b (several items): measured and planned, see section 10b; Level 3 (text, icon, colour: archives and a loader).
- `Paramdex` field layouts are embedded (`paramdefs.py`, generated by `tools/gen_paramdefs.py`); its licence has not been checked.
- Build time (about 20 s) is pure Python.

## 10b. Next: several items (Level 2b), measured, not built

One item uses every spare row: Goods, Magic and SpEffect have one dummy row each (`999999999`), Shop has two (`9999001`, `9999002`). More items need more rows, so a table has to grow. Measured on the 1.17.1 original (decoded body 54,111,776 bytes = 826 blocks of 64 KiB):

| Table | Starts in block | Size | Rows x row size |
|:--|:-:|:-:|:--|
| EquipParamGoods | 426 | 465,889 | 2,329 x 176 |
| Magic | 515 | 60,947 | 317 x 168 |
| ShopLineupParam | 627 | 98,582 | 1,296 x 52 |
| SpEffectParam | 630 | 10,627,431 | 11,354 x 912 |

- **Inserting rows in place** shifts everything behind the table: about 400 blocks (from Goods on) would be re-encoded; the most that was tested in the game is 11, and the gate stops above 11.
- **Moving the small tables to the end of the body** (copies appended, BND4 entries repointed, the old copies left in place) changes only the header block and about 11 new blocks (Goods 8, Magic 1, Shop 2). It was tried before (handbook tests G2, H1) with stored blocks, which the game rejects for an unrelated reason, so it has **not** been tested with the final method. SpEffect (about 162 blocks) is too big to move.
- **Reusing unused existing rows** (as the poise effect does with SpEffect 102006) needs a list of unused rows; the file stores no row names (the strings area of each table holds only the table's type name), so it cannot be detected from the file alone.
- The merchant's range 100500-100524 has 7 free lines (100508 is the current item; 100509, 100512, 100521-100524 are free). That they all belong to the same merchant is an inference.
- **Plan:** T1 (smallest test): move Goods to the end unchanged, the game must reach the title and load the world; T2: a second item with Goods, Magic and Shop moved and SpEffect from a checked unused row; T3: the draft takes several items, an id allocator, and the gate, `decide` and `--secure` cover every item. If T1 fails: a `replaces` field that overwrites an existing item chosen by the author. Items with the same effect can share a SpEffect row.

## 11. Tests

`code/tests/test_ext_spec.py` (validation, schema agreement), `test_ext_primitives.py` (AES vectors, sequence coding, frame rewriting against `zstandard`, containers, field definitions), `test_ext_service.py` (the decision matrix: first run, unchanged, changed price with its diff, only a name changed, secured file missing or edited, recipe version, other base, damaged record, failed gate, `--secure`, half-done secure; deciding never builds), `test_ext_gate.py` (the optional second decoder), `test_extension_command.py` (CLI, `--secure`, `--list`, what `run` builds, swaps and says), `test_ext_golden.py` (needs `ELDENDISK_REGULATION_ORIG`: the Z4 hash, determinism, preflight and gate negatives, the whole flow with the real build); `test_regulation.py`, `test_run_command.py` and `test_host.py` adapted to a caller-named file.

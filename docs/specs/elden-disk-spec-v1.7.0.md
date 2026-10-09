> [!NOTE]
> **Version:** `1.7.0`  
> **Status:** IMPLEMENTED (unit and golden tests; a tool-built file ran in the real game; the secured path (`--secure`) and poise are not yet tried, see section 10)  
> **Last Updated:** _2026-10-09_

# Elden-Disk spec 1.7.0: extensions and `innovate-spells` (design → secured)

Reads on top of [spec 1.6.4](elden-disk-spec-v1.6.4.md) (the `regulation.bin` swap). Only what changes is written here. The research behind the build (why a frame is rewritten block by block, what the game rejected) is the [item-customization handbook](../experiments/item-customization/item-customization-handbook.md), Part VI.

## 1. Idea

**Principle: the other world never touches the real one.** Everything done in a `run` session (the rules, the items, the values written, the changes to the save) exists for that session only. When the game exits, the vault puts back the save and the game's own `regulation.bin`, byte for byte, checked by hash. Nothing carries over: not the items, not the progress. The real playthrough stays exactly as it was, and it can be finished with no mod at all. The sandbox is for playing around on the days you want to; it is never required, and nothing in the real world can collapse because of it.

1.6.4 swapped a `regulation.bin` that somebody else made. 1.7.0 makes it inside the tool, offline, from a small JSON file. A file goes through three states: **design** (the JSON you edit) → **built** (a `regulation.bin` the gate passed; not yet tried in the game) → **secured** (a copy you confirmed in the game, kept next to a record of the design it came from).

```
extension.json (embedded in the exe) --run: build on the game's own regulation.bin + gate--> regulation.bin --vault swaps--> the game (one session; the vault puts the game's file back)
                                       --extension innovate-spells --secure (game closed)--> regulation.secured.bin + spells.commit.json
next run, design unchanged: regulation.secured.bin is swapped; nothing is built, nothing is re-checked (about 20 s saved)
```

`extension` is a main feature like `read`, `write` and `vault`: a place for features that **build things for the game outside the game**. `innovate-spells` is the first. Because an extension touches game files, it **depends on the vault's permission**, like `write` needs the vault ON: with the vault ON (the default) `run` also runs the extension build; with the vault OFF it does not. There is no `--extension-on` flag. The vault is unchanged in purpose: it backs up, swaps the file it is given, and puts the original back.

The base is **always the game's own file**, checked against the known original on **every** path (also when the secured file is used); a modified file is never modified again.

Innovate levels (the author's words): **L1** `write --set` (memory, live); **L2** a `regulation.bin` with copied/adapted rows under the game's own rules (this version, "2a": one item per file); **L3** truly new things (name, text, icon, colour): needs files inside the game's archives and a loader, not started.

## 2. Layout

```
code/extension.json    the design of the extensions (you edit it); the section `innovate_spells` holds the spells
code/eldendisk/extension/innovate_spells/spells.schema.json   JSON schema of the design (for editors; dev tests check it agrees with the validator)
%LOCALAPPDATA%\EldenDisk\extension\innovate-spells\          (--extension-dir overrides the folder)
    regulation.bin           the latest build (gate passed, not yet confirmed)
    regulation.secured.bin   a copy of the build you confirmed with --secure
    spells.commit.json       the commit: the design snapshot, the rows each spell took, hashes of the secured file and of the base, recipe version (format 2)
```

No base copy and no manifest are kept. `build -c -em` embeds `extension.json` in the exe like `offsets.json`; the design is found as `--spec FILE`, else `extension.json` next to the exe, else the embedded copy, else the package in the source tree (`paths.get_resource_path`). Without `-em`, the file is copied next to the exe, where you can edit it without rebuilding the exe.

Code: `code/eldendisk/extension/` (registry) and `extension/innovate_spells/` (aes, zstd, fse, reblock, container, defs, paramdefs, bases, spec, recipes, preflight, **gate**, build, service). Standard library only. The package imports nothing else of the tool (`test_architecture.py`).

## 3. Commands

| Command | Does |
|:--|:--|
| `run` (vault ON) | **swaps `regulation.secured.bin` without building** when the secured state is valid (section 6); otherwise prints why and what changed, builds (about 20 s), and swaps the new `regulation.bin` after the gate passed |
| `run --vault-off` | no build, no swap (an info line says so) |
| `run --regulation FILE` | swaps that file instead (an experiment; vault ON only) |
| `run --spec FILE`, `--extension-dir DIR` | the design; the folder of the files |
| `extension --list` | the design (path, where it comes from, number of items), the secured state, the design-vs-secured diff, the last build |
| `extension innovate-spells` | where the files are |
| `extension innovate-spells --add all` (or `--add <id>`) | builds like `run` does (always; never uses the secured file), without starting the game |
| &nbsp;&nbsp;`--dry-run` | build and run the gate in memory; write nothing |
| `extension innovate-spells --secure` | **game closed.** Runs the gate on `regulation.bin` against the current design and the game's file; copies it to `regulation.secured.bin`, then writes `spells.commit.json` (last). Stands alone (not with `--add` / `--dry-run`) |
| &nbsp;&nbsp;`--source FILE`, `--game-dir DIR` | the game's original `regulation.bin` (default: the one in the auto-detected game folder) |
| &nbsp;&nbsp;`--spec FILE`, `--extension-dir DIR` | as above |

There is no `--force`: delete `spells.commit.json` to make the next `run` build. There is no automatic securing: the host never reads game memory, so it cannot know the item worked; you confirm it with `--secure`. After a session that **built**, `run` prints a hint to run `--secure`.

A design with no filled slot is valid: nothing to build, exit `0`, `run` swaps nothing. In `run`, a design or build error (invalid design, the game's file is not the known original) or a **failed gate** stops `run` with exit `1` **before** any snapshot or launch: nothing is swapped and the game is not started. If the vault still owes a restore from an earlier session, `run` does not build; the host refuses to start and says what to do.

Exit codes: `0` ok; `1` error (invalid design, unknown base, gate failed); `2` usage.

## 4. The design (`extension.json`, section `innovate_spells`)

```json
{"innovate_spells": {"maximum": 64, "slots": {"reverse_curse_technique": {...the spell...}, "<id-2>": null, "<id-3>": null, ...}}}
```

`maximum` is the number of slots (1-64; 64 is what the game accepted in test T6: 64 new rows in each of Goods, Magic, ShopLineup and SpEffect). `slots` has exactly `maximum` keys, in order. A **filled slot** is a spell and its key is the spell's id; an **empty slot** is `null` (any key, `<id-N>` by convention) and is not built. **The slot number (its place in the list, from 1) fixes the rows the spell takes in the game**, so moving a spell to another slot is a change of the build, and the file must keep every slot (use `null`, never delete a line). A key that appears twice in one object is an error (JSON would silently keep the second). Other sections of `extension.json` belong to other extensions and are ignored. Unknown fields are errors; every problem is listed with its path (`$.innovate_spells.slots[reverse_curse_technique].requires.faith: must be a whole number from 0 to 99`). `name` and `description` are **stored only**; `colour`, `icon_file`, `text` and similar are refused ("Level 3").

| Field | Meaning (Z4 value) |
|:--|:--|
| slot key (the `id`) | `[a-z0-9_-]{1,40}` (`_` is the usual separator), unique (`reverse_curse_technique`) |
| `type` | `incantation` |
| `requires` | `intelligence`, `faith`, `arcane` 0-99 (45 / 15 / 10) |
| `fp_cost`, `stamina_cost` | 0-999 (80 / 0) |
| `cast_motion` | `flame-grant-me-strength` (default) or `black-flame-blade` (`Magic.refType` 31 / 32) |
| `effect` | heal over time: `heal_hp_per_tick`, `restore_fp_per_tick`, `stamina_regen_speed`, `tick_seconds`, `duration_seconds`, `visual` `flame` (the burning body of Flame! Grant Me Strength) / `flask` (Heal's glow) / `none` or an explicit `null` (no lingering effect on the body; the cast flash stays; leaving the field out means `flame`) (60 / 4 / 100 / 0.5 / 15 / flame) |
| `poise_while_casting_seconds` | optional; hyper armor (Endure-style poise buff, no damage reduction) while casting (2.0) |
| `shop` | `price` 1..99,999,999, `stock` -1 (unlimited) or 1..99 (34590 / 1) |

Every spell is built as **new rows appended to the four tables** (section 10b); nothing existing is changed or removed. The ids of the rows are fixed by the slot (slot *n*, 1..64):

| Row | Id |
|:--|:--|
| Goods and Magic | `2230000 + n - 1` |
| SpEffect (heal over time) | `21950111 + n - 1` |
| SpEffect (poise buff; only when `poise_while_casting_seconds` is set) | `21950211 + n - 1` |
| ShopLineup line | slots 1-7 only: `100508, 100509, 100512, 100521, 100522, 100523, 100524` (the free lines of the merchant's group `100500-100524`) |
| stock flag | `150000 + (line - 100500) * 10` (slot 1: `150080`) |

A spell in slot 8 or higher has no shop line: it is built without `shop` (an error if it has one), and how to obtain it in the game is open. `shop` is optional in every slot. The poise buff is a row of its own (a copy of Endure's `1650` with the damage reduction stripped), no longer an overwrite of SpEffect `102006` as in the Z4 file that was tested.

## 5. How a file is built

1. validate the spec (an invalid spec stops here; the existing build is untouched);
2. read the base: the game's own `regulation.bin` (or `--source`), after checking its SHA-256 against the known original of 1.17.1; any other file is refused (hint: `vault restore`, or Steam *verify integrity*);
3. decrypt (AES-256-CBC), read the DCX/zstd frame, BND4 and the four PARAM tables (EquipParamGoods, Magic, SpEffectParam, ShopLineupParam); check that writing them back unchanged reproduces the original;
4. apply the recipe: every spell becomes new rows, each a copy of a real row with the fields of the spec written over it (section 4); `grow.py` makes room for them in front of each table (the entries just before the table are copied to the end of the body and repointed in the BND4), so the old rows and strings stay where they are and the new rows sit right after the table's record array; the declared **footprint** lists exactly which rows were added;
5. re-encode only the 64 KiB blocks whose bytes changed (about 13) and append the new blocks at the end, as ordinary compressed blocks, steering the repeat-offset registers so the following original blocks stay decodable; shape the file tail like the original (handbook Chapters 9-11);
6. encrypt with an IV derived from the content (same input, same bytes; the game accepts any IV); 7. write a temporary file and fsync it; 8. read it back and run the **gate** (section 7) on those bytes; 9. only if the gate passes, `os.replace` it to `regulation.bin`. A failed gate deletes the temporary file; `regulation.bin` and the secured files stay as they were.

Reference result: the Z4 spell in slot 1 (the fixed copy in `tests/z4.py`) gives a container whose decrypted SHA-256 is `0ef6b8519eca2fba8de16f3d3a76742606fcad9c9c280a43fb05953d12a1a9ac` (2,143,376 bytes, 828 blocks, 13 re-encoded, the decoded body +65,504 bytes). This is a regression anchor; **the game's verdict on appended rows is pending** (the earlier Z4 file, hash `1aa16ee0…`, used the dummy rows and passed, but is no longer built).

## 6. When `run` builds and when it does not

`run` (vault ON) swaps `regulation.secured.bin` without building and without the gate **only if all of these hold**:

1. the design equals the secured spec (`spec.build_view`: field by field; `name`, `description`, whitespace and key order do not count);
2. SHA-256 of `regulation.secured.bin` equals the record;
3. the SHA-256 of the game's `regulation.bin` equals the base recorded and is the known 1.17.1 original (this check also runs on the build path);
4. `RECIPE_VERSION` equals the record.

Otherwise it builds and prints **the reasons** (no secured build yet; the design changed; the secured file is missing or its hash differs; the recipes changed; the base is another file; the record cannot be read) and, for a changed design, the **diff** field by field, for example `reverse_curse_technique.shop.price  34590 -> 40000`, before the long step.

## 7. The gate (necessary, not sufficient)

The gate (`gate.py`) judges the **bytes of the file read back from disk**, not what the builder believes it wrote. It replaces the old in-build preflight and decrypt round-trip (same time). **Any problem, and any warning, is a stop** (including more than 11 re-encoded blocks). The only real test of a file is the game.

| Rule | Checks |
|:--|:--|
| G0 | the file decrypts |
| R1 | the frame decodes to exactly the intended body, recomputed independently from the design and the game's file (G5) |
| R2 | no stored/RLE block that the original did not have in the same place; same block count and flags; edited blocks are compressed and < 128 KiB; **more than 11 re-encoded blocks is a stop** (11 is the most tested in the game) |
| R3 | blocks whose decoded bytes did not change are byte-identical (only the literal-size header form of raw-literal blocks, or the conversion of a Huffman-treeless follower to raw literals, may differ) |
| R4 | DCX header: only the two size fields differ and they are right; exactly 2 zero bytes after the frame; length 16 + a multiple of 16 |
| R5 | BND4: same entries; only the four tables differ |
| R6 | PARAM: same row size, row count, header and strings; sorted; the set of rows removed / added / changed equals the recipe's declared footprint |
| G5 | Magic and SpEffect fields (costs, requirements, cast motion, effect values, poise) equal the design |
| G11 | the id chain: Goods, Magic, SpEffect and the shop line exist; Magic points to the SpEffect |
| G12 | the shop line is inside the merchant's range 100500-100524; the stock flag belongs to that line only |
| G13 | heal sign: `changeHpPoint` / `changeMpPoint` are negative for a heal (a positive value drains the player) |
| G16 | a second decoder (`compression.zstd`, Python 3.14), when this Python has one, decodes the frame to the same bytes. It is imported by name inside `try`; if it is missing the gate only notes it. Agreed on the author's Python 3.14.5 |

## 8. `run` and the vault

- `run` decides (section 6), builds if needed, then passes the path to the host (`Hooks.regulation_world`); the vault methods take that path (`backup_regulation(snap, game_dir, world)`, `regulation_problems(game_dir, world)`, `world_info(world)`). Backup, record, swap, restore and RG1-RG7 of spec 1.6.4 are unchanged. The extension only **reads** the game's file; the vault does the swap.
- The banner row `regulation` says whether the file is the secured copy or a new build.
- Log order: `extension ...` lines (design, reasons, diff, building, gate passed or failed), then the host lines (PREFLIGHT, SNAPSHOTTING, READY).
- `--regulation FILE` wins over everything.
- **Legacy:** `<vault>\regulation\regulation.bin` (1.6.4) is no longer read; `run` and `vault status` say so.
- Vault OFF never swaps and never builds.

## 9. Failures

| Situation | Result |
|:--|:--|
| invalid `extension.json` | exit `1`, fields named; nothing written (`run` does not start) |
| the game's file is not the known original | exit `1`; nothing written; hint: close the game if it runs, `vault restore`, or Steam *verify integrity*; `run --vault-off` starts the game without the extension |
| a recipe row is missing | exit `1`: "not the 1.17.1 regulation.bin" |
| the gate fails (build) | `GATE FAILED: this regulation.bin is NOT safe for the game; nothing was swapped`, rules listed, exit `1`, the game is not started; the temporary file is deleted, `regulation.bin` and the secured files are untouched |
| the gate fails (`--secure`) | same message; nothing secured |
| `--secure` with no build, or a build made from another design | exit `1` ("build it first" / rule R1) |
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

## 10b. Several items: rows appended to the tables (built; game verdict pending)

Measured on the 1.17.1 original (decoded body 54,111,776 bytes = 826 blocks of 64 KiB):

| Table | Starts in block | Size | Rows x row size |
|:--|:-:|:-:|:--|
| EquipParamGoods | 426 | 465,889 | 2,329 x 176 |
| Magic | 515 | 60,947 | 317 x 168 |
| ShopLineupParam | 627 | 98,582 | 1,296 x 52 |
| SpEffectParam | 630 | 10,627,431 | 11,354 x 912 |

Inserting rows in place would shift everything behind a table (about 400 blocks re-encoded). Instead `grow.py` grows a table **backwards**: the table is moved forward by *X* bytes (a multiple of 16) into the space of the entries directly in front of it, and those entries are first copied to the end of the body (BND4 offsets repointed; the old copies are left as dead space). The record array is rebuilt (old pointers + *X*, new rows placed right after the records, new rows share the name pointer of the table's dummy row); the old rows and strings are not touched. Tables are processed in file order, so a later table may evict an earlier one that has already grown.

What the game was seen to accept (handbook Part VI, test T6: 64 new inert rows in each of the four tables): decoded growth up to 219 KB, compressed frame growth up to +234,768 bytes, 13 re-encoded blocks, BND4 entries out of file order, appended blocks (literal and match-coded). 466 KB of growth failed. The gate (R7) holds these as limits: `MAX_BODY_GROWTH` 219,000, `MAX_FRAME_GROWTH` 235,000, `MAX_CHANGED_BLOCKS` 13; a warning counts as a stop; the numbers go up only after an in-game pass of a bigger file.

Measured with this recipe (spells with shop and poise, passing the gate): 1 spell 13 blocks / +65,504 bytes; 2, 7 and 8 spells 13 blocks; **16 spells already re-encode 14 blocks** and the gate stops. So more than about 8-15 spells need a new in-game test with a bigger file (T7), then new limits. Known limit of the encoder: 64 spells that all have a poise buff cannot be encoded (`rewrite_grow`: the repeat-offset state is not reachable).

- The merchant's range `100500-100524` has 25 lines, 18 used, 7 free (the table above): only slots 1-7 can be sold there; that they all belong to the same merchant is an inference.
- Names and descriptions need the text archives (not the regulation); a new spell shows with the name of the dummy row.
- **Plan:** (1) test slot 1 alone in the game (appended rows, real spell data); (2) add slots one at a time, the next with another effect; (3) T7 to raise the limits for more than about 8 spells; (4) decide how slots 8-64 are obtained (no shop line).

## 11. Tests

`code/tests/test_ext_spec.py` (validation, schema agreement), `test_ext_primitives.py` (AES vectors, sequence coding, frame rewriting against `zstandard`, containers, field definitions), `test_ext_service.py` (the decision matrix: first run, unchanged, changed price with its diff, only a name changed, secured file missing or edited, recipe version, other base, damaged record, failed gate, `--secure`, half-done secure; deciding never builds), `test_ext_gate.py` (the optional second decoder), `test_extension_command.py` (CLI, `--secure`, `--list`, what `run` builds, swaps and says), `test_ext_grow.py` (growth on synthetic archives: eviction, overlaps, order of tables, refusals), `test_ext_golden.py` (needs `ELDENDISK_REGULATION_ORIG`: the slot-1 hash, the rows against the Z4 rows, other slots, ids, the 16-spell stop, preflight and gate negatives, the whole flow with the real build); `test_regulation.py`, `test_run_command.py` and `test_host.py` adapted to a caller-named file.

> [!NOTE]
> **Version:** `1.7.0`  
> **Status:** IMPLEMENTED (unit and golden tests; the swap of a tool-built file is not yet run in the real game, see section 10)  
> **Last Updated:** _2026-10-09_

# Elden-Disk spec 1.7.0: extensions and `customize-items`

Reads on top of [spec 1.6.4](elden-disk-spec-v1.6.4.md) (the `regulation.bin` swap). Only what changes is written here. The research behind the build (why a frame is rewritten block by block, what the game rejected) is the [item-customization handbook](../experiments/item-customization/item-customization-handbook.md), Part VI.

## 1. Idea

1.6.4 swapped a `regulation.bin` that somebody else made. 1.7.0 makes it inside the tool, offline, from a small JSON file, **every time `run` starts**:

```
sources/items.json (embedded in the exe)  --build, on the game's own regulation.bin-->  regulation.bin  --vault swaps it in-->  the game, for one session  --vault puts the game's file back
```

`extension` is a main feature like `read`, `write` and `vault`: a place for features that **build things for the game outside the game**. `customize-items` is the first. Because an extension touches game files, it **depends on the vault's permission**, like `write` needs the vault ON: with the vault ON (the default) `run` also runs the extension build; with the vault OFF it does not. There is no `--extension-on` flag. The vault is unchanged in purpose: it backs up, swaps the file it is given, and puts the original back.

The build runs **every time**, with no "already built" shortcut: it is simple, and it exercises the customize code on every run. The base is **always the game's own file**; a modified file is never modified again.

Customize levels (the author's words): **L1** `write --set` (memory, live); **L2** a `regulation.bin` with copied/adapted rows under the game's own rules (this version, "2a": one item per file); **L3** truly new things (name, text, icon, colour): needs files inside the game's archives and a loader, not started.

## 2. Layout

```
code/eldendisk/extension/customize_items/sources/items.json   the spec: the item(s) you want in the game (you edit it)
%LOCALAPPDATA%\EldenDisk\extension\customize-items\regulation.bin   the output of the last build   (--extension-dir overrides the folder)
```

Nothing else is kept: no base copy, no manifest, no verified copy. `build -c -em` embeds `sources/items.json` in the exe like `offsets.json`; the spec is found as `--spec FILE`, else `items.json` next to the exe, else the embedded copy, else `sources/` in the source tree (`paths.get_resource_path`). Without `-em`, the file is copied next to the exe, where you can edit it without rebuilding the exe.

Code: `code/eldendisk/extension/` (registry) and `extension/customize_items/` (aes, zstd, fse, reblock, container, defs, paramdefs, bases, spec, recipes, preflight, build, service; `sources/items.json`, `schema/items.schema.json`). Standard library only. The package imports nothing else of the tool (`test_architecture.py`).

## 3. Commands

| Command | Does |
|:--|:--|
| `run` (vault ON) | **builds** the spec on the game's `regulation.bin` (about 15 s), writes the output, and passes it to the host to swap in |
| `run --vault-off` | no build, no swap (an info line says so) |
| `run --regulation FILE` | swaps that file instead of building (an experiment; vault ON only) |
| `run --spec FILE`, `--extension-dir DIR` | the spec to build; the folder of the output |
| `extension --list` | the spec (path, where it comes from, number of items) and the last output |
| `extension customize-items` | where the spec and output are |
| `extension customize-items --add all` (or `--add <id>`) | the same build as `run` does, without starting the game |
| &nbsp;&nbsp;`--dry-run` | build and check in memory; write nothing |
| &nbsp;&nbsp;`--source FILE`, `--game-dir DIR` | the game's original `regulation.bin` to build on (default: the one in the auto-detected game folder) |
| &nbsp;&nbsp;`--spec FILE`, `--extension-dir DIR` | as above |

An empty `items` list is a valid spec: the build says there is nothing to build and exits `0`; `run` swaps nothing. In `run`, a spec or build error (invalid spec, the game's file is not the known original, a failed check) stops `run` with exit `1` **before** any snapshot or launch. If the vault still owes a restore from an earlier session, `run` does not build; the host refuses to start and says what to do.

Exit codes: `0` ok; `1` error (invalid spec, unknown base, failed check); `2` usage.

## 4. The spec (`items.json`, format 1)

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
6. **preflight** (section 7); 7. encrypt with an IV derived from the content (same input, same bytes; the game accepts any IV); 8. write `regulation.bin` (through a temporary file and `os.replace`).

Reference result: the shipped `sources/items.json` (Z4) gives a container whose decrypted SHA-256 is `1aa16ee0dbcbc5902cef2b6eb29bd542f42b2158fcdb44c221c187280db5277b` (2,071,472 bytes), the Z4 file that passed in the real game.

## 6. Every time

There is no skip logic. Every `run` (vault ON) and every `--add` reads the spec and the game's file again and builds; the output is replaced atomically. A build takes about 15 s, so each `run --vault-on` starts that much later.

## 7. Preflight (necessary, not sufficient)

Run on the finished bytes before anything is written; any failure writes nothing. The only real test of a file is the game.

| Rule | Checks |
|:--|:--|
| R1 | the frame decodes to exactly the intended body |
| R2 | no stored/RLE block that the original did not have in the same place; same block count and flags; edited blocks are compressed and < 128 KiB; warning above 11 re-encoded blocks (the most tested in the game) |
| R3 | blocks whose decoded bytes did not change are byte-identical (only the literal-size header form of raw-literal blocks, or the conversion of a Huffman-treeless follower to raw literals, may differ) |
| R4 | DCX header: only the two size fields differ and they are right; exactly 2 zero bytes after the frame; length 16 + a multiple of 16 |
| R5 | BND4: same entries; only the four tables differ |
| R6 | PARAM: same row size, row count, header and strings; sorted; the set of rows removed / added / changed equals the recipe's declared footprint |

## 8. `run` and the vault

- `run` builds (vault ON), then passes the output path to the host (`Hooks.regulation_world`); the vault methods take that path (`backup_regulation(snap, game_dir, world)`, `regulation_problems(game_dir, world)`, `world_info(world)`). Backup, record, swap, restore and RG1-RG7 of spec 1.6.4 are unchanged. The build only **reads** the game's file; the vault does the swap.
- Log order: `extension ...` lines (spec, building, built and checked), then the host lines (PREFLIGHT, SNAPSHOTTING, READY).
- `--regulation FILE` wins over the build.
- **Legacy:** `<vault>\regulation\regulation.bin` (1.6.4) is no longer read; `run` and `vault status` say so.
- `vault status` no longer shows a "file to swap"; `extension --list` shows the last output.
- Vault OFF never swaps and never builds.

## 9. Failures

| Situation | Result |
|:--|:--|
| invalid `items.json` | exit `1`, fields named; nothing written (`run` does not start) |
| the game's file is not the known original | exit `1`; nothing written; hint: `vault restore`, or Steam *verify integrity*; `run --vault-off` starts the game without the extension |
| a recipe row is missing | exit `1`: "not the 1.17.1 regulation.bin" |
| a preflight rule fails | exit `1`, rules listed; **no file written** |
| killed during a build | a temporary file only; the previous output is intact; the game's file was only read |

## 10. Open

- **Not yet run in the real game through this path:** a tool-built Z4 swapped by `run --vault-on` (manual plan 1.7.0 SW1-SW3). The bytes equal the tested file (golden test), but the swap itself (1.6.4) has been tested by unit tests only.
- One verifier: our decoder. Dev tests cross-check with `zstandard` and `cryptography`; the runtime has no second opinion.
- `SpEffect 102006` ("Unused" in community lists) is overwritten; the poise effect is not proven in the game (`read --live-buffs` can show a 2.0 s entry).
- Level 2b (several items, table growth), Level 3 (text, icon, colour: archives and a loader).
- `Paramdex` field layouts are embedded (`paramdefs.py`, generated by `tools/gen_paramdefs.py`); its licence has not been checked.
- Build time (about 15 s) is pure Python.

## 11. Tests

`code/tests/test_ext_spec.py` (validation, schema agreement), `test_ext_primitives.py` (AES vectors, sequence coding, frame rewriting against `zstandard`, containers, field definitions), `test_ext_service.py` (build every time, base handling, empty spec), `test_extension_command.py` (CLI, what `run` builds and takes), `test_ext_golden.py` (needs `ELDENDISK_REGULATION_ORIG`: the Z4 hash, determinism, preflight negatives); `test_regulation.py`, `test_run_command.py` and `test_host.py` adapted to a caller-named file. Linux: 765 passed, 14 skipped without the original (all 13 golden tests pass with it).

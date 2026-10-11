> [!NOTE]
> **Version:** `1.7.1`  
> **Status:** IMPLEMENTED (unit tests); in the real game on 2026-10-11 `run` put the text and the fire colour in by itself in three sessions (written and read back every time); what is seen in the game is in manual plan 1.7.1  
> **Last Updated:** _2026-10-11_

# Elden-Disk spec 1.7.1: the text and the fire colour of a spell (Item Customization Level 3, steps 1 and 3)

Reads on top of [spec 1.7.0](elden-disk-spec-v1.7.0.md). Only what changes is written here. The research (where the text lives, why it is put into memory and not into a file, why a fixed chain from the exe was dropped, the tools) is [handbook Chapter 19](../handbook/innovate-items-handbook.md).

## 1. Idea

A new spell has a name, a short line and a long description in the game. The game reads them from FMG tables inside its archives; a loose file is not read and rewriting `Data0.bdt` is out of scope. So the text is given to the **running** game: after a character is in the world, the tool finds the game's three item-text tables in memory, rebuilds them with the spells' entries added and points the game at the new tables. The fire of *Flame, Grant Me Strength* is made of effect files the game keeps in memory as they are in the file; the tool finds them and writes new colours into the colour fields. Nothing is written to the game folder. Both last until the game closes, and both are done **once**: nothing watches the game afterwards.

Both steps find what they change by **looking through the game's memory** (section 5). No fixed address from the exe is used: the pointer chain that was measured for the text held the right object in 3 of 5 runs of the same game.

## 2. The design: `text` and `flame_color`

`name` and `description` (1.7.0, stored only) are **removed**; a spell has one optional object, placed before `set` in the canonical form and the schema:

```json
"text": { "goods_name": "", "goods_info": "", "goods_captions": "" }
```

| Field | Game table | Shown | Limit |
|:--|:--|:--|:-:|
| `goods_name` | GoodsName | the name | 80 |
| `goods_info` | GoodsInfo | the short line | 120 |
| `goods_captions` | GoodsCaption | the long description (Inventory, controller square); `\n` = new line | 1000 |

All three are optional; the canonical form always holds all three (empty = nothing is written for it). Any other key in `text` is an error. The old keys give `renamed in 1.7.1: use text.goods_name` (and `text.goods_info`).

A spell of any kind may also have

```json
"flame_color": [0.2, 0.65, 1.0]
```

three numbers, red, green, blue, each from 0 to 2 (1 = the full colour, above 1 shines brighter; anything else is an error with its path). The fire effects are the game's own and shared by every spell that uses them, so there is **one** colour for the whole design: `Spells.flame_color(selection)` gives the colour of the first spell (by slot) that names one, and a note when other spells name a different colour. The `LEVEL3_KEYS` refused by the design are now `icon`, `icon_file`, `colour`, `color` and `model`.

`build_view` leaves `text` and `flame_color` (and the 1.7.0 `name`/`description` of old records) out: an edit of either never changes the build, the gate, `decide` or `decide_last`, and never un-secures a secured build. `Spells.texts(selection)` gives `{goods id: text}` for **every** slot (the Goods id is `2230000 + slot - 1`), empty for a slot with no spell or a spell outside the selection.

## 3. `write --text [--wait [SEC] | --when-loaded] [--spec FILE] [--extension-dir DIR]`

Stands alone (an error with `--set`, `--refill`, `--reset` or `--flame-color`; `--wait`, `--when-loaded`, `--spec` and `--extension-dir` need `--text` or `--flame-color`; `--when-loaded` does not go with `--wait`). Same authorisation as every write (record readable, `RUNNING`, snapshot verified, the recorded game process, same exe hash, host alive; exit `5`); EAC loaded exit `3`; a profile without a `text` block exit `2`.

1. The design and the selection give the texts (as `extension` does).
2. The game is found. With `--when-loaded` the tool waits, without a time limit, until the game's modules can be read and a character is in the world (the player exists and has a level that makes sense) and has stayed there for 5 s (the loading screens flicker); if the game closes first nothing is written and the exit is `0`. With `--wait` a game that cannot be attached yet is tried again every second until SEC (default 300). Otherwise one try.
3. **Look.** `writer/text.py: find_tables` finds the tables: a place whose bytes start like a table (version-2 header, the `1` at `0x08`, the address at `0x18` equal to the place's own address + `0x28` + 16 × the group count, the size field in range) and whose size is the one `text.sizes` says for GoodsName, GoodsInfo or GoodsCaption. `find_arrays` then finds, through all the memory, the places that hold pointers to those tables at the distances of `text.files` (GoodsName at `A + 10 * 8`, GoodsInfo at `A + 20 * 8`, GoodsCaption at `A + 24 * 8`): an array. If no array is found and the look for the tables had stopped early, the tables are looked for again through all the memory (a second copy may exist). With `--when-loaded` or `--wait` a failed look is made again after 10, 20, 40 and 60 s of rest.
4. For each array found and each table: read the table the pointer leads to (the address at `0x18` turned back into an offset, the size checked), `Fmg.read`, put each non-empty text at its Goods id and take the entry away when the text is empty. If the entries are the same as now, nothing is done for this table.
5. `swap`: allocate memory in the game (`VirtualAllocEx`, read/write), write the whole new table in its live form (address at `0x18` = new base + offsets position), check that the slot still holds the old table, change the slot with one aligned 8-byte write, read it back. The old table is untouched. A failure leaves the table concerned on the game's own and exits `1` (a table already switched stays switched).
6. With `--when-loaded` or `--wait`: after 3 s the slots are read again; if the game replaced them, steps 4-5 run once more; a second miss is an error.

Not idempotent across calls in the same game: after the first `write --text` the array points at the new tables, which have not the sizes of the game's own, so a second call finds no array and says `the text was set already in this session`. The text stays as written. Emptying a text in the design and starting the game again removes the entry. The tables are the game's own plus the slot entries; every other text is kept.

`writer/writer.py` gains `WritableProcessMemory.alloc` and `regions` (`VirtualQueryEx`: the readable private blocks the look walks) and is still the only module that names `WriteProcessMemory` or `VirtualAllocEx` (`test_write_capability_is_confined_to_the_writer_package`). `writer/text.py` knows bytes only (the writer package may not import the extension); the tables are built in `commands/write.py` with `extension/innovate_items/fmg.py`.

## 4. `write --flame-color [--wait [SEC] | --when-loaded] [--spec FILE] [--extension-dir DIR]`

The same rules as section 3 for the options, the authorisation and the wait. The design gives the colour (`Spells.flame_color`); with no colour in the design: `no spell of the design names a flame_color: nothing to do`, exit `0`.

1. Two effect files make the fire that is recoloured: `524400` (the fire while casting; 18 colours) and `524401` (the burst when the cast ends; 54 colours). The third (`524402`, the fire on the body) is left alone. `writer/fxr_plans.py` lists, for each file, where every colour (four little-endian floats, RGBA) sits and whether it is a bloom colour.
2. **New colour.** With v = the biggest of R, G, B and w = 1 − (v − the smallest) / v: new RGB = v × (w + (1 − w) × target). White stays white, black stays black, alpha is never touched. A bloom colour becomes v × target.
3. **Look.** `writer/fxr.py: find_all` goes through the memory (section 5) and keeps a place where **every** colour of a plan matches the game's bytes, the original or the painted ones (so a second run finds its own work). The look stops when each effect has a copy. A copy that does not match entirely is not touched.
4. Each copy is written at its listed places and read back. A place that would not change (black) is not written. `already` counts the copies that were painted before.
5. If an effect is not found the look is made again after 10, 20, 40 and 60 s of rest (with `--when-loaded` or `--wait`); at the end: `the game does not hold the effect file(s) … : the game is still starting (use --wait), or it is not the version this was made for`, exit `1`.

Output: `✓ write  flame colour: the fire of Flame, Grant Me Strength is now (0.2, 0.65, 1.0) in 2 effects (68 places written); it lasts until the game closes`. The effect files are shared by every spell that uses them, so the game's own Flame, Grant Me Strength has the colour too while the game runs.

## 5. The look: `writer/scan.py`

One way of looking, shared by both steps; it never writes. The caller gives `visit(address, data, n)` for each piece and returns True when it has what it wants.

| Rule | Why (measured on 1.17.1) |
|:--|:--|
| The game's private, readable memory is read in pieces of 16 MB; after each piece the tool rests for half the time the piece took | the first versions rested a fixed 5 ms per MB, which Windows made ~15 ms: the time went into resting, not reading. A share of the piece's time keeps the game's share of the memory bus whatever the speed |
| First the first 128 MB of each private block of 256 MB or more (biggest first), then all the rest (biggest first) | the text tables lie ~43 MB into a block of 1530 MB (found in 0.6 s); the fire lies ~1312 MB into a block of 2560 MB (found in the rest, 6.5 s) |
| A piece also holds the first `overlap` bytes of the next one | something that begins in a piece and ends after it is seen whole |
| A piece that cannot be read whole is read again in parts of 256 KB | one page that is gone does not hide the rest |
| A look ends at 120 s | a bound; the logs of 2026-10-11 never came near it |

## 6. The profile: `text`

```json
"text": { "files": { "GoodsName": 10, "GoodsInfo": 20, "GoodsCaption": 24 }, "sizes": { "GoodsName": 114880, "GoodsInfo": 164208, "GoodsCaption": 975296 } }
```

Optional per exe hash (absent = `write --text` unsupported, exit `2`); a block that is there must be complete and `sizes` must name the same tables as `files` (each size from `0x28` bytes to 64 MB). `files` are the numbers of the text files (checked in the game); `sizes` are the sizes of the game's own tables in the language the game is played in (here the English tables of 1.17.1). No address is kept (the `rva` and `array` of the first version are gone).

## 7. `run` starts them

`Hooks.on_running(pid)` (new, default does nothing) is called once, right after the record says `RUNNING` and only with the vault ON; an exception in it is logged and never ends the session. `commands/run.py` sets it when all hold: vault ON, the regulation.bin swapped is the extension's (`secured`, `last` or `built`, not `--regulation FILE`). It then starts, each as a **separate process** (`python -m eldendisk` in the source tree, the exe itself when frozen) in its own console process group, stdout and stderr inherited (silenced under `-v`, where the log shows their lines):

- `eldendisk write --text --when-loaded --vault V --offsets O [--spec S] [--extension-dir D]` when the design has any text for the built spells;
- `eldendisk write --flame-color --when-loaded …` when a spell of the design names a `flame_color`.

`run` therefore still never opens the game's memory (the host and vault rules of spec 1.6.2 hold). A child still running when the session ends is stopped.

## 8. Failures

| Case | Result |
|:--|:--|
| tables not found (the game is still loading, another version or language) | `write --text` exits `1` with what was seen (the sizes of the tables it saw), the game goes on without the text |
| the tables were seen but no array points at all three | `the text was set already in this session …` or `the game keeps them differently than offsets.json describes`, exit `1` |
| the game replaces the tables again | one more try, then exit `1` |
| a fire effect is not in the game | exit `1` after the looks |
| a step fails inside `run` | the session is not affected; run it by hand |
| closing the game | everything vanishes (the memory was the game's) |

## 9. Measured (real game, 2026-10-11, three `run` sessions)

| | Text | Fire |
|:--|:--|:--|
| Found | all three tables in 0.6-0.7 s (176 MB read, the head); one array, about 6 MB before them, in a look through all the memory (7.3 GB, 70-73 s, 3 pointers) | one copy of each effect in 6.4-6.6 s (1712 MB read, the rest of the blocks) |
| Written | GoodsName 114880 → 114952 bytes, GoodsInfo 164208 → 164610, GoodsCaption 975296 → 977510; the pointers read back | 68 places (18 + 50), read back |
| After the character is in the world | ~75 s | ~7 s |

The earlier chain from the exe gave the right object in 3 of 5 runs and memory given back in 2 (an FMG groups table, UTF-16 text, whole numbers): the reason for section 1.

## 10. Not done (open)

Thai and other scripts (glyphs in the game's font untested); a game language other than English (the profile holds the English sizes); the colour of the fire on the body (`524402`); icons (Level 3 step 2); a faster look for the array (it is found by a look through all the memory, ~72 s; it lies near the tables); a second `write --text` in the same game.

## 11. Tests

`tests/test_write_text.py` (writer/text.py against a fake game memory: the shape of a table, `find_tables` and `find_arrays` with decoys and a stale copy of the array, swap and every failure of it; the command: three tables, idempotent, emptying, no session, other process, no profile block, waits and gives up with the sizes it saw, the game putting its tables back, command-line rules), `tests/test_write_flame.py` (`scan.walk`: borders, rest in proportion to the time and the budget, the head tier, unreadable parts; `find_all`; `paint_many`; the command step), additions to `test_ext_spec.py` (the object, limits, renamed keys, `flame_color`), `test_ext_service.py` (`texts`, `flame_color`, an edit of either decides nothing), `test_host.py` (`on_running`), `test_run_command.py` (the command lines, when the steps start, stopping them), `test_profile_policy.py` (the `text` block: files and sizes), `test_disk.py` (the one allocation), `test_gamearchive.py` and `test_ext_fmg.py` (tools/gamearchive.py, the FMG), `test_probe_text.py` (the research tool).

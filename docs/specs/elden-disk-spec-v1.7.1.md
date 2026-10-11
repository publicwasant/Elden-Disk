> [!NOTE]
> **Version:** `1.7.1`  
> **Status:** IMPLEMENTED (unit tests); the text mechanism ran in the real game by hand on 2026-10-11; `run` starting it by itself is not yet tried in the game (manual plan 1.7.1, TX)  
> **Last Updated:** _2026-10-11_

# Elden-Disk spec 1.7.1: the text of a spell (Item Customization Level 3, step 1)

Reads on top of [spec 1.7.0](elden-disk-spec-v1.7.0.md). Only what changes is written here. The research (where the text lives, why it is put into memory and not into a file, the chain from the exe, the tools) is [handbook Chapter 19](../handbook/innovate-items-handbook.md).

## 1. Idea

A new spell has a name, a short line and a long description in the game. The game reads them from FMG tables inside its archives; a loose file is not read and rewriting `Data0.bdt` is out of scope. So the text is given to the **running** game: after the game is up, the tool rebuilds the game's three item-text tables in memory with the spells' entries added and points the game at them. Nothing is written to the game folder. The text lasts until the game closes.

## 2. The design: the `text` object

`name` and `description` (1.7.0, stored only) are **removed**; a spell has one optional object, placed before `set` in the canonical form and the schema:

```json
"text": { "goods_name": "", "goods_info": "", "goods_captions": "" }
```

| Field | Game table | Shown | Limit |
|:--|:--|:--|:-:|
| `goods_name` | GoodsName | the name | 80 |
| `goods_info` | GoodsInfo | the short line | 120 |
| `goods_captions` | GoodsCaption | the long description (Inventory, controller square); `\n` = new line | 1000 |

All three are optional; the canonical form always holds all three (empty = nothing is written for it). Any other key in `text` is an error. The old keys give `renamed in 1.7.1: use text.goods_name` (and `text.goods_info`). `text` is removed from the refused Level 3 keys (colour, icon, `icon_file`, `flame_color`, `model` stay refused). The spelling `goods_captions` (plural) is the author's.

`build_view` leaves `text` (and the 1.7.0 `name`/`description` of old records) out: a text edit never changes the build, the gate, `decide` or `decide_last`, and never un-secures a secured build. `Spells.texts(selection)` gives `{goods id: text}` for **every** slot (the Goods id is `2230000 + slot - 1`), empty for a slot with no spell or a spell outside the selection.

## 3. `write --text [--wait [SEC]] [--spec FILE] [--extension-dir DIR]`

Stands alone (an error with `--set`, `--refill`, `--reset`; `--wait`, `--spec` and `--extension-dir` need `--text`). Same authorisation as every write (record readable, `RUNNING`, snapshot verified, the recorded game process, same exe hash, host alive; exit `5`); EAC loaded exit `3`; a profile without a `text` block exit `2`.

1. The design and the selection give the texts (as `extension` does).
2. The game is found (with `--wait`: a game that cannot be attached yet is tried again every second until SEC, default 300; a game that is not running ends it).
3. For each of GoodsName, GoodsInfo, GoodsCaption: follow the chain of the profile (`eldenring.exe + text.rva` → object; slot = object + `text.array` + N * 8), read the table the game holds (`writer/text.py: locate`: version-2 header, size field, the address at `0x18` inside the table), and keep it as a file (the address turned back into an offset). With `--wait` the tables must be the same twice in a row; without it a missing table is an error (exit `1`).
4. `Fmg.read` the table, put each non-empty text at its Goods id and take the entry away when the text is empty. If the entries are the same as now, nothing is done for this table.
5. `swap`: allocate memory in the game (`VirtualAllocEx`, read/write), write the whole new table in its live form (address at `0x18` = new base + offsets position), check that the slot still holds the old table, change the slot with one aligned 8-byte write, read it back. The old table is untouched. A failure leaves the table concerned on the game's own and exits `1` (a table already switched stays switched).
6. With `--wait`: after 3 s the tables are read again; if the game replaced them, steps 3-5 run once more; a second miss is an error.

Idempotent: the same text again allocates nothing. Emptying a text in the design and running again removes the entry. The tables are the game's own plus the slot entries; every other text is kept.

`writer/writer.py` gains `WritableProcessMemory.alloc` and is still the only module that names `WriteProcessMemory` or `VirtualAllocEx` (`test_write_capability_is_confined_to_the_writer_package`). `writer/text.py` knows bytes only (the writer package may not import the extension); the tables are built in `commands/write.py` with `extension/innovate_items/fmg.py`.

## 4. The profile: `text`

```json
"text": { "rva": "0x3D61FB8", "array": "0x1F20", "files": { "GoodsName": 10, "GoodsInfo": 20, "GoodsCaption": 24 } }
```

Optional per exe hash (absent = `write --text` unsupported, exit `2`); a block that is there must be complete. Measured on 1.17.1 with `tools/probe_chain.py`; the numbers are the author's checks in the game.

## 5. `run` starts it

`Hooks.on_running(pid)` (new, default does nothing) is called once, right after the record says `RUNNING` and only with the vault ON; an exception in it is logged and never ends the session. `commands/run.py` sets it when all hold: vault ON, the regulation.bin swapped is the extension's (`secured`, `last` or `built`, not `--regulation FILE`), and the design has any text for the built spells. It starts `eldendisk write --text --wait 300 --vault V --offsets O [--spec S] [--extension-dir D]` as a **separate process** (`python -m eldendisk` in the source tree, the exe itself when frozen) in its own console process group, stdout and stderr inherited (silenced under `-v`, where the log shows its lines). `run` therefore still never opens the game's memory (the host and vault rules of spec 1.6.2 hold). A child still running when the session ends is stopped.

## 6. Failures

| Case | Result |
|:--|:--|
| tables not found within the wait | `write --text` exits `1`, the game goes on without the text |
| the game replaces the tables again | one more try, then exit `1` |
| `write --text` fails inside `run` | the session is not affected; run `write --text` by hand |
| closing the game | everything vanishes (the memory was the game's) |

## 7. Not done (open)

Thai and other scripts (glyphs in the game's font untested); a game language other than English (the loaded tables are patched, untested); icons (Level 3 step 2); new colour/effect (step 3); `run` starting the step on the real game (TX in the manual plan).

## 8. Tests

`tests/test_write_text.py` (writer/text.py against a fake game memory: locate, not-ready cases, swap and every failure of it; the command: three tables, idempotent, emptying, no session, other process, no profile block, `--wait` retries and gives up, the game putting its tables back, command-line rules), additions to `test_ext_spec.py` (the object, limits, renamed keys), `test_ext_service.py` (`texts`, a text edit decides nothing), `test_host.py` (`on_running`), `test_run_command.py` (the command line, when the step starts, stopping it), `test_profile_policy.py` (the `text` block), `test_disk.py` (the one allocation), `test_gamearchive.py` and `test_ext_fmg.py` (tools/gamearchive.py, the FMG), `test_patch_text.py` / `test_probe_text.py` / `test_probe_chain.py` (the research tools).

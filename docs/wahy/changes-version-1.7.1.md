> [!NOTE]
> **Version:** `1.7.1`  
> **Status:** IMPLEMENTED (unit tests); the mechanism ran in the real game by hand on 2026-10-11; `run` starting it is not yet tried in the game (manual plan 1.7.1, TX)  
> **Last Updated:** _2026-10-11_

**Summary:** **The text of a spell.** A spell now has a name, a short line and a long description in the game. They are written in the design as `"text": {"goods_name", "goods_info", "goods_captions"}` (replacing `name` and `description`) and put into the running game by `write --text`, which `run` starts by itself once the game is up. Nothing is written to any file: the game's text tables are rebuilt in the game's memory and the game is pointed at them.

_(baseline: **[changes-version-1.7.0.md](changes-version-1.7.0.md)**; design: **[elden-disk-spec-v1.7.1.md](../specs/elden-disk-spec-v1.7.1.md)**; research: **[handbook Chapter 19](../handbook/innovate-items-handbook.md)**)_

---

## Wahy

| # | Change | Where |
|:-:|:---|:---|
| 1 | **`text` object** in the spell design: `goods_name` (80), `goods_info` (120), `goods_captions` (1000), before `set`. `name` and `description` are gone (an error that names the replacement). `text` is no longer a refused Level 3 key. It is not part of the build: a text edit never rebuilds or un-secures. `Spells.texts()` gives the text of every slot. | `spells/spec.py`, `spells.schema.json`, `service.py`, `code/extension.json` |
| 2 | **`write --text [--wait [SEC]] [--spec] [--extension-dir]`**: rebuilds the game's GoodsName, GoodsInfo and GoodsCaption tables in memory and points the game at them; idempotent; empty text removes an entry; waits for the game to load its text; checks that the game kept them. | `commands/write.py`, `__main__.py` |
| 3 | **`writer/text.py`** (bytes only): follow the chain, read and check the table, allocate, write, switch the pointer, read back. `WritableProcessMemory.alloc` (`VirtualAllocEx`) is the one new allocation; the safety test now allows that word in `writer/writer.py` only. | `writer/text.py`, `writer/writer.py`, `tests/test_disk.py` |
| 4 | **Profile block `text`** (`rva`, `array`, `files`) for 1.17.1; absent = unsupported (exit `2`). | `game/profile.py`, `offsets.json` |
| 5 | **`run` starts it by itself.** `Hooks.on_running` is called once the record says `RUNNING` (vault ON); `run` starts `write --text --wait 300` as a separate process when the swapped file is the extension's and the design has text. `run` still never opens the game's memory. A child still running at the end is stopped. | `host/host.py`, `commands/run.py` |
| 6 | **Cleanup of the research code.** `fmg.py` stays in the product. `archive.py`, `msgbnd.py` and the AES-128/ECB additions of `aes.py` are removed; the archive reader moved to `tools/gamearchive.py` (with its own AES-128), used by `tools/dump_msgbnd.py`; `tools/make_text_test.py` is gone. `dump_msgbnd.py`, `probe_text.py`, `probe_chain.py`, `patch_text.py` stay in `tools/` as the record of the research (handbook 19.5). | `tools/`, `extension/innovate_items/` |
| 7 | **Tests.** New `test_write_text.py`, `test_gamearchive.py`, `test_ext_fmg.py`, `test_patch_text.py`, `test_probe_text.py`, `test_probe_chain.py`; additions to the spec, service, host, run, profile and safety tests; the Z4 fixture and the expected canonical forms use `text`. | `tests/` |
| 8 | **Docs.** README, cli-commands (both), spells handbook (new 6.1b), item-customization handbook (new Part VI, Chapter 19), roadmap (Phase 3), spec and manual test plan 1.7.1. Version `1.7.1`. | `README.md`, `docs/` |

## Migration

Move the words of a spell into `text`: `name` → `text.goods_name`, `description` → `text.goods_info` (short) and/or `text.goods_captions` (long). A secured build stays valid: the text was never part of it.

## Not done

Thai and other scripts, other game languages, icons, colour/effect (see spec 1.7.1 section 7).

> [!NOTE]
> **Version:** `1.7.2`  
> **Status:** IMPLEMENTED (unit tests); in the real game on 2026-10-13: `read --query "*"` and `extension.*`, a text written back and read again, the external scripts BuffLogger, HangOnPurpose, PassiveIncome and RctColoursFollowTheSpell under `run`, `character.equipment` read while the magic slots were changed, the colours of Reverse Cursed Technique following the selected spell (eight switches in one session)  
> **Last Updated:** _2026-10-13_

**Summary:** **External scripts.** Your own Python scripts run next to the game: `run` (vault ON) starts them, each in a thread of its own, and they end when the game closes. A script imports **edstdlib** (`Interface`, `tools`): `tools.read()` gives the game as one document, `tools.write(x)` writes back what the script changed in it. For that the whole document can now be read and written: `read` has a fourth block, `extension` (the spells of the last build with the values the game holds now), every value `read` shows can be written except `systems` and what is computed, and a text or a colour changes at once because the steps that put them into the game remember where they did (the memory cache). `character.equipment` gives the spells in the magic slots and the selected one, so the colours of Reverse Cursed Technique can follow the spell in use.

_(baseline: **[changes-version-1.7.1.md](changes-version-1.7.1.md)**; design: **[elden-disk-spec-v1.7.2.md](../specs/elden-disk-spec-v1.7.2.md)**; draft: `docs/experiments/extensional/external-scripts/`)_

---

## Wahy

| # | Change | Where |
|:-:|:---|:---|
| 1 | **External scripts.** `extension external-scripts [--run [--when-loaded]] [--scripts-dir PATH ...]`. The default scripts are `defaults/*.py`, embedded in the exe by `dev_pipeline` (with `--no-embed` copied next to it); every `--scripts-dir PATH` adds more after the build (a folder or one `.py`, anywhere, several allowed). `run` (vault ON) starts the host when there is a script, **once the text and colour steps are done** (so a colour a script changes is painted already), and passes `--scripts-dir` on. | `extension/external_scripts/`, `commands/scripts.py`, `commands/run.py`, `tools/dev_pipeline.py` |
| 2 | **The host.** One daemon thread per script, the pace kept by the framework, a broken file never stops the others, no character in the world skips a loop, `tools.dead()` → `stopped`, an exception → `dead` (traceback in the log), a loop stuck for 10 s is reported, `teardown()` always runs, the host ends when the game closes. Status in `<vault>\extension\external-scripts.status.json`. A slow `loop()` is a debug line. | `external_scripts/host.py` |
| 3 | **edstdlib.** `Interface` (`setup`, `loop`, `teardown`; `every`, `name`, `enabled`) and `tools`: `read()` (the document as an object: attributes, `[ ]` for keys that are not names, a spell by its label), `write(obj)` (only what changed, True/False), `dead()`, `log()`. A group used as a number says which value to use. A refusal that repeats is logged once until a write goes through. | `external_scripts/edstdlib.py` |
| 4 | **The backend**, the one file of the extension package allowed to touch the game (`EXCEPTIONS` in the architecture test): one read shared for 50 ms, one write at a time, the session checked again every second. A colour change is one info line: `reverse_cursed_technique colours: main #90D5FF, accent #FF909E`. | `external_scripts/backend.py` |
| 5 | **The `extension` block** of `read`, `--export` and `tools.read()`: `extension.innovate_items.spells.<goods id>` with the label, slot, rows (`rows.copies`, now recorded by the build) and the design with the values the game holds now; the buffs of the extension's spells are named by the spell's label in `character.buffs`. | `reader/export.py`, `disk.schema.json`, `spells/build.py` |
| 6 | **Every block read and written by its own name.** `systems`, `character`, `params`, `extension`; `read --query "*"` is all of it; the short forms are for the character only; a name that names nothing is unknown (1.7.1 took `extension.*` as `character.extension.*`). `write --set extension....=VALUE` and `tools.write`: requires and locations → the spell's Magic row and shop line, `customs.basic` → the same field of the spell's own row, texts → the table rebuilt at the pointer `write --text` switched, colors → the painted copies repainted; `null` = the game's own. | `commands/read.py`, `commands/write.py`, `game/values.py`, `spells/live.py` |
| 7 | **The memory cache** (`<vault>\memory-cache.json`, tied to the game process): where the text step switched the tables and which copies the colour step painted. A save reads the file again and writes only what it changed, under a lock file, so the text step no longer wipes the colours (seen on 2026-10-13: the scripts could not change a colour). | `writer/cache.py` |
| 8 | **Hex colours.** Every colour of the design takes `"#RRGGBB"` (`"#RGB"`, with or without `#`); `[r, g, b]` stays valid. `code/extension.json`: `#90D5FF` and `#FF909E`. On a colour console a `#RRGGBB` in a log line is shown in that colour. | `spells/spec.py`, `spells.schema.json`, `ui.py`, `code/extension.json` |
| 9 | **`character.equipment`** (profile block `equipment`, found read-only in the running game on 2026-10-13: the magic slots at `[PlayerGameData+0x530]+0x10`, 14 of 8 bytes, the selected one at `+0x80`): `character.equipment.magic.selected.slot / .id` and `slots.1 ...`; read only; short form `equipment`. | `offsets.json`, `game/profile.py`, `reader/sampler.py`, `disk.schema.json`, `reader/view.py` |
| 10 | **Quicker.** The extension block 6.5 ms and 723 KB read per call → 1.3 ms and 3 KB (the row index of each table kept); a repaint reads each copy in one piece (about 250 reads → 4) and writes it in one piece (one write per copy, not one per place: a colour change by a script 0.74 s → under 0.1 s); `spells.resolved.json` and `memory-cache.json` are read again only when they change; the scripts `run` starts after the text and colour steps look at the world once instead of waiting 5 s again (they started about 8 s after the steps, now at once); `character.equipment` is one read of 116 bytes. | `game/paramtables.py`, `writer/fxr.py`, `external_scripts/backend.py`, `commands/scripts.py`, `commands/write.py`, `reader/sampler.py` |
| 11 | **A quieter log.** No `client: version` line; a step `run` starts does not log its command line again; `config` lines only for a file that is not the one built into the exe; `run` says when there are no external scripts; the scripts' lines and their wait for the world are tagged `scripts`. | `logsetup.py`, `commands/common.py`, `commands/run.py` |
| 12 | **Examples** (the tests run them; copy one into `defaults\` to try it): heartbeat, low_hp, buff_logger, keep_fp, eyes_follow_hp, dead_on_purpose, hang_on_purpose, rct_colours_follow_the_spell. The author's `defaults\passive_income.py`. | `code/tests/external_scripts/`, `external_scripts/defaults/` |
| 13 | **Tests.** New `test_scripts.py`, `test_extension_live.py`, `tests/fake_tools.py`; additions to the design, dev pipeline, architecture, disk, read, param tables, params, logging, profile, run, write-text and ui tests. | `tests/` |
| 14 | **Docs.** README, cli-commands (both: section 4c, the read names), adding-a-profile (`equipment`), spec 1.7.2, this file. Version `1.7.2`. | `README.md`, `docs/` |

## Measured (real game, 2026-10-13)

| What | Before | After |
|:--|:--|:--|
| the extension block, per read | 6.5 ms, 723 KB | 1.3 ms, 3 KB |
| a repaint of the fire, reads | about 250 | 4 |
| a script's colour change (main and accent, read included) | 0.74 s | 0.08 s |
| the scripts after the text and colour steps | 8.5 s (a second wait for the world) | one look |

## Not done (open)

- `character.equipment` holds the magic slots only and cannot be written.
- A text changed from a script allocates a new table in the game every time (about 1 MB for the descriptions).
- The colours follow a spell only in time: the effect files are shared.

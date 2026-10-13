> [!NOTE]
> **Version:** `1.7.2`  
> **Status:** IMPLEMENTED (closed). Tried in the real game on 2026-10-13: `read --query "*"` and `extension.*`, a text written back and read again, the external scripts BuffLogger, HangOnPurpose, PassiveIncome and RctColoursFollowTheSpell under `run`, `character.equipment` read with the slots changed, the colours following the selected spell (eight switches in one session). Changes: [changes-version-1.7.2.md](../wahy/changes-version-1.7.2.md).  
> **Last Updated:** _2026-10-13_

# Elden-Disk spec 1.7.2: external scripts, and the extension's spells in read and write

Reads on top of [spec 1.7.1](elden-disk-spec-v1.7.1.md). Only what changes is written here. The idea and its first draft are in
`docs/experiments/extensional/external-scripts/` (draft.md, draft.disk-state.json).

## 1. Idea

Until 1.7.1 the tool did fixed things: `run` built the spells, put their text and colours into the game once, and `write --set` changed one
value when a person typed it. 1.7.2 lets the people who use the tool (its author and the developers) add **their own behaviour**: a Python
script that runs next to the game, reads the game as one document and writes back what it changes, again and again, while the game runs.
The first use it was made for: the colours of Reverse Cursed Technique are shared effect files, so they can only follow the spell in time
(blue while it is the one in use, the game's own colours otherwise); a script decides when.

Two things make that possible:

- **external scripts** (section 2 to 4): a host that runs every script in a thread of its own, and **edstdlib**, the small library a script
  imports;
- **the whole document can be read and written** (section 5 and 6): `read` shows a fourth block, `extension`, with the spells of the last
  build as the game holds them now, and every value `read` shows can be written back except `systems` and what is computed. A text and a
  colour change at once, because the steps that put them into the game now remember where they did (the memory cache).

## 2. External scripts

```text
code/eldendisk/extension
 ├─ external_scripts
 │   ├─ defaults/      the scripts the exe carries (embedded by the build)
 │   ├─ edstdlib.py    the interface the scripts import
 │   ├─ host.py        finds the scripts, runs them, keeps their pace, watches them, ends them
 │   └─ backend.py     what edstdlib reads and writes the running game with
 └─ innovate_items     (1.7.0, 1.7.1)
code/tests/external_scripts/   the example scripts (the tests run them; copy one into defaults/ to try it)
```

**A script** is a Python file with one or more classes made from `Interface`:

```python
from edstdlib import *

class EyesFollowHp(Interface):
    every = 0.5                                              # seconds between two calls of loop()

    def loop(self):
        x = tools.read()                                     # the game now, as one object
        hp = x.character.vitals.hit_point
        rct = x.extension.innovate_items.spells.reverse_cursed_technique      # or spells[2230000]
        rct.customs.advanced.colors["SpEffect.1642100"] = "#FF909E" if hp.current < 0.3 * hp.maximum else "#90D5FF"
        tools.write(x)                                       # writes only what changed
```

**Which scripts run:** the default ones are the `*.py` of `external_scripts/defaults/` (not `_*.py`): `tools/dev_pipeline.py` embeds them in
the exe (`external-scripts` inside it; with `--no-embed` they are copied to `external-scripts\` next to the exe), a source run reads the
folder. **In addition** every `--scripts-dir PATH` (on `run` and on `extension external-scripts`) adds scripts written after the build: a
folder (its `*.py`) or one `.py` file, anywhere, several allowed; the same file twice runs once; a path that is neither is said and left out.

**When:** `run` (vault ON) starts the host as a process of its own once the text and colour steps are done (so a script that changes a
colour finds it painted; started side by side, its first writes were refused), `eldendisk extension external-scripts
--run --when-loaded`, when there is a script; the host waits until a character is in the world, starts every script and ends when the game
closes; started after those steps, it looks at the world once instead of waiting 5 s again (`ELDENDISK_WORLD_READY=1`; before, the scripts
began about 8 s after the steps). With no script `run` says so in the log and starts nothing. With the vault OFF nothing is started: scripts write through the
session.

## 3. The host (host.py)

One process holds every script, each in a **daemon thread** of its own. A Python thread cannot be killed, so the process is what ends for
sure: when the game closes the host asks every script to stop, waits up to 3 s for each and returns. Nothing a script does keeps the vault
from putting the save back: `run` does that, not the host (seen in the game: the restore began while a stuck script was still asleep).

The life of a script: `loaded -> setup -> live -> stopped | dead` (`off`: `enabled = False`; `failed`: the file could not be loaded).

| What happens | What the host does |
|:--|:--|
| a file that cannot be imported (a SyntaxError, a missing import, `SystemExit`) | that file is `failed`, the others load |
| `setup()` | once, in the script's thread, after a character is in the world |
| `loop()` | every `every` seconds (at least 0.05), from the start of one call to the start of the next; a call longer than the pace is followed at once and the log says so once (a debug line: a loop that changes a colour takes about half a second by nature; a hang has its own warning) |
| reading in `character` while no character is in the world (title screen, loading) | that call is skipped, the log says `waiting, no character in the world` once and `a character is in the world again` when it is back |
| `tools.dead()` | the script ends: `stopped (tools.dead())`; it ends it even inside `except Exception` |
| any exception from `setup()` or `loop()` | `dead`, its traceback in the log (debug); the others go on |
| a `loop()` that does not return for 10 s | reported once as stuck; it keeps its thread (it cannot be taken away), the others go on |
| the end, whatever caused it | `teardown()` |

The status of every script is kept in `<vault>\extension\external-scripts.status.json`; `eldendisk extension external-scripts` (without
`--run`) lists the scripts and how each ended the last time. The host's lines and the scripts' `tools.log` lines are tagged `scripts`;
without `-v` the `run` console shows them, with a check mark when a script starts.

## 4. edstdlib

`from edstdlib import *` gives three names: `Interface`, `Tools` and `tools` (the one object of `Tools`).

| | |
|:--|:--|
| `Interface` | `setup()`, `loop()` (required), `teardown()`; `every`, `name` (default: the class name), `enabled` |
| `tools.read()` | the document `read --export` writes (`systems`, `character`, `params`, `extension`), built in memory (never read back from `disk-state.json`), as an object |
| `tools.write(obj)` | writes what was changed in a snapshot of `tools.read()` (`obj` is the snapshot or a part of it: then only what changed under it). True when every change was written; what was refused is in the log |
| `tools.dead()` | ends this script now |
| `tools.log(text, level="info")` | a line in the log and on the `run` console, starting with the script's name; `ok`, `warn`, `error`, `debug` |

**The snapshot.** A name is read as an attribute (`x.character.attributes.vigor`); a key that is not a name is read with `[ ]`:
`spells[2230000]`, `params.effects[1621000]`, `colors["SpEffect.1642100"]` (or `colors.SpEffect[1642100]`: the first part of a dotted key);
a spell also by its label (`spells.reverse_cursed_technique`). A value is changed by assignment (`x.character.runes.total += 50`,
`rct.customs.basic["SpEffect.1642100.effectEndurance"] = 30`), which marks it for `tools.write`; a snapshot is a copy, another snapshot does
not change. A group used as a number says what to use: `character.runes is a group (total, baseline, delta), not a number: use one of its
values, e.g. character.runes.total`.

**Writes** go through the same checks as `write`: the session `run` started (checked again every second while the scripts run; when it is
no longer the one `run` started for this game, writes are closed for good), the game offline, the field writable, the value in range; a
value equal to the game's is not written again.

**The backend (backend.py)** is the one file of the extension package allowed to touch the game (`EXCEPTIONS` in
tests/test_architecture.py) and the second user of the writer after `commands/write.py` (tests/test_disk.py). It reads through the Sampler of
`read`, one read shared by every script for 50 ms, and writes through the MemoryWriter of `write`, one write at a time.

## 5. The `extension` block of the document

`read` (and `--export`, and `tools.read()`) has a fourth block, `extension`, `null` without a build in the vault:

```text
extension.innovate_items.spells.<goods id>
  id                 the spell's label in extension.json
  slot, rows         what the build made: goods, magic, sp_effect, bullet, atk, shop, and copies (each template row and its copy)
  kind, from         as the design says
  requires           status (intelligence, faith, arcane), cost (focus_point, stamina)
  locations          kale (price, stock)
  customs.basic      "<Table>.<template id>.<field>": the value the game holds now
  customs.advanced   texts (goods_name, goods_info, goods_caption), colors (as hex)
```

It is spells.resolved.json (written by every build) with the values the game holds now: a field of a row is read from the spell's own row
(the six tables of `read --param`), a text and a colour from the memory cache once `run` has put them in. The build now records each copied
row's template (`rows.copies`), so `customs.basic.SpEffect.1642100.effectEndurance` is the field of the spell's copy 21951000. The buffs of
the extension's spells are named by the spell's label in `character.buffs` (category `EXTENSION`).

## 6. Reading and writing every block

**Names.** A name is the path of the document as typed: `systems`, `character`, `params`, `extension`; `read --query "*"` is all of it. The
short forms are for the character only (`hp`, `vigor`, `attrs.faith`, `runes`, `buffs`: `character.` may be left out). A name that names
nothing is an unknown name, never read as a value of another block (1.7.1 read `extension.*` as `character.extension.*`). `params` and
`extension` are typed in full, in any letter case; a key with dots is found (`...basic.SpEffect.1642100.effectEndurance`); a spell is named
by its goods id or its label; ids in a list are printed without commas.

**Writing.** Everything `read` shows can be written except `systems` and what is computed (maxima, buffs, animations, the ids a build made):
`write --set NAME=VALUE` and `tools.write`. The `extension` block:

| Name | In the game |
|:--|:--|
| `requires.status.intelligence / faith / arcane` | `Magic.<the spell's row>.requirementIntellect / requirementFaith / requirementLuck` |
| `requires.cost.focus_point / stamina` | `Magic.<...>.mp / stamina` |
| `locations.kale.price / stock` | `ShopLineup.<the spell's shop line>.value / sellQuantity` |
| `customs.basic.<Table>.<template id>.<field>` | the same field of the spell's own row (Magic / Goods: the spell's rows; SpEffect / Bullet / AtkParam_Pc: their copies) |
| `customs.advanced.texts.goods_name / goods_info / goods_caption` | the text table rebuilt at the pointer `write --text` switched |
| `customs.advanced.colors."Magic.<from>.castSfxId"` (`.main` / `.accent`) | the fire (main), its accent and the ring of runes (accent): the painted copies repainted |
| `customs.advanced.colors."SpEffect.<id>"` | the Positive Curse Energy Eyes |

A value is typed as it is: a number, a hex colour (`"#90D5FF"`), a text in quotes, `null` (the game's own colour back). `id`, `slot`,
`rows`, `kind` and `from` are made by the build (change the design and build again).

**The memory cache** (writer/cache.py, `<vault>\memory-cache.json`, tied to the pid and the start time of the game process): the text step
keeps the addresses of the three table pointers it switched and the texts it wrote; the colour step keeps every copy of every effect file it
painted and the colours they carry. A later write in the same game needs no look through the memory: a colour is repainted from the colours
the copies carry to the new ones (writer/fxr.repaint; each copy read in one piece and checked first), a text table is rebuilt from the one the
pointer holds; a copy is written in one piece (one write per copy, from its first changed place to its last). An address is a hint: the
bytes are checked before anything is written; a copy the game reloaded is looked for again. Several processes save the cache in the same
game (the text and colour steps side by side, the scripts): a save reads the file again and writes only what it changed, under a lock file
(on 2026-10-13 the text step, done after the colour step, saved its older copy over the colours and the scripts could not change them).

**Measured** (read-only, the running game, 2026-10-13): the extension block 6.5 ms and 723 KB read per call before, 1.3 ms and 3 KB after
(game/paramtables keeps each table's row index: the chain and the header are followed every time and the row's own descriptor must still
name it; the whole descriptor table is read again only when the table changed); a repaint of the fire about 250 reads before, 4 after;
a colour change by a script (main and accent, the read included) 0.74 s with one write per place, 0.08 s with one write per copy.

## 7. The equipment: `character.equipment`

To make a colour follow the spell in use, a script must know which spell is selected **before** the cast: a buff only comes on after it,
when the fire and the ring have been shown. `character.equipment.magic` gives the spells memorised in the magic slots and the one that is
selected:

```text
character.equipment.magic.selected.slot   2           (numbered from 1, as the game shows the slots)
character.equipment.magic.selected.id     6250        (the Magic id; null when the selected slot is empty)
character.equipment.magic.slots.1         2230000     (the memorised spells; empty slots left out)
```

The offsets are a new optional block of the profile, `equipment` (offsets.json; docs/handbook/adding-a-profile.md), found in the running
game, read-only, on 2026-10-13: the magic slots at `[PlayerGameData+0x530]+0x10`, 8 bytes each (the Magic id, -1 when empty), 14 of them,
and the selected slot at `+0x80` (the slots and the selected one are read in one piece, 116 bytes). Without the block, or when it cannot be read at that moment, there is no `character.equipment` (the rest
of the sample is not held back by it). It is read, not written. `equipment` is a short form like `hp`: `read --query equipment`.

The example `rct_colours_follow_the_spell.py` (code/tests/external_scripts) uses it: the fire and the ring take the design's colours while
Reverse Cursed Technique is selected and the game's own colours when another spell is, so Flame, Grant Me Strength looks as the game made
it again (the effect files are shared: the colours follow the spell in time).

## 8. Log

No `client: version` line (that is `--version`). A step `run` starts (`ELDENDISK_STARTED_BY=run`) does not log its command line again: run's
`design: starting: ...` says it; its `client: exit` stays. `config: offsets / state ids / design` only when the file is not the one built
into the exe. The scripts' lines are tagged `scripts`, the wait for the world too. A refusal a script meets again and again is logged once,
until a write goes through. A colour change is one info line, `reverse_cursed_technique colours: main #90D5FF, accent #FF909E` (the
spell's label, then each colour or `the game's own`). On a colour console a colour `#RRGGBB` in a line is shown in that colour.

## 9. Not done (open)

- `character.equipment` holds the magic slots only (weapons, armour and the rest are not read yet) and cannot be written.
- A text changed from a script allocates a new table in the game every time (the description table is about 1 MB); a script that changes a
  text every loop makes the game's memory grow until it closes.
- The colours follow a spell only in time: the effect files are shared, so while they are painted every spell that uses them shows it.

## 10. Tests

`test_scripts.py` (edstdlib on a fake backend; the host: threads, pace, a script that fails, ends itself or hangs, the game closing, no
character in the world; the command; the examples), `test_extension_live.py` (what each name of the block is in the game; the memory cache;
a repaint and a text rewrite without a look; the routing of a snapshot's changes; the names of read), `tests/fake_tools.py`; additions to
`test_param_tables.py` (the row index), `test_dev_pipeline.py` (the default scripts embedded), `test_architecture.py`, `test_disk.py`,
`test_read_command.py`, `test_params.py`, `test_cli_logging.py`, `test_profile_policy.py` (the equipment block), `test_run_command.py` (the
scripts after the steps), `test_write_text.py` (one look at the world), `test_ui.py` (a colour in its colour).

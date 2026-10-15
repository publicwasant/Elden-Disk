# Python CLI Commands Reference (`python -m eldendisk`)

Every command of **Elden-Disk 1.8.0** (`python -m eldendisk <command> [options]`), written from [spec 1.8.0 part 2](../specs/elden-disk-spec-v1.8.0.md). Elden-Disk is the
**Elden Ring Memory Disk I/O Tools**: CLI commands in a console (Windows 10/11, 64-bit); you open a terminal, run a command, it does its
work and ends.

**The portal.** Elden-Disk is a portal into a parallel world of the game. Through it the world mirrors everything of the game and you can
play with it in creative ways: new spells you design, great enemies brought back, scripts that change the game while it runs. When you
leave, the real world is back exactly as it was: the vault keeps the save files (`ER0000.sl2`, `ER0000.sl2.bak`, `ER0000.err`,
`ER0000.err.bak`, `steam_autocloud.vdf`) and the game's own `regulation.bin` before you go in, and puts them back, byte for byte, when
the game closes. **Nothing you did inside comes back with you.**

---

## The backbone

```text
vault: back up the save files (and swap in the regulation.bin built from creative.json)      `run`: the portal opens
 │
 ├─ read      the game's memory (RAM) through the pointer chains of the profile (offsets.json); every value is a name in ONE document
 │   ├─ [nothing | * | all | disk] all of the document (disk.json)
 │   ├─ [disk.PATH ...]            a part of it: `disk.character.level`, `disk.creative.resurrect.great_enemies.margit`
 │   │                             (the short names still work: `hp`, `level`, `margit`)
 │   └─ [params.PATH ...]          the game's tables, read from the game: `params.Magic.6230.mp` (what export --params writes)
 │       └─ [--live | --tree (default) | --flat | --json]
 │
 ├─ write     the game's memory through the same chains, only inside the session `run` started (vault ON)
 │   ├─ [NAME | ID | PATH = VALUE ...]   a name `read` shows: `write creative.resurrect.great_enemies.margit.defeated=false`
 │   └─ [NAME | ID | PATH = default]       the game's own value back
 │
 ├─ creative  what is built and run next to the game (it depends on the vault, like `write`)
 │   ├─ scripts                 your Python scripts, running next to the game while it runs (the defaults and the added ones)
 │   ├─ innovate-spells         new spells: creative.json -> a regulation.bin judged by a gate -> secured
 │   └─ resurrect               a boss you have beaten (a great enemy), alive again for the session
 │
 ├─ data      export, reset, check, probe
 │
vault: restore the save files and the game's own files, byte for byte                       the game closes: the portal closes
```

Rules every command follows:

1. **One document.** Whatever the tool knows of the running game is a path in one document (`systems`, `character`,
   `creative`). `read` shows it, `write` and `tools.write` change it, `export` writes it as `output\disk.json`. The game's
   tables (`params`) are read from the game when named, and `export --params` writes all of them to `output\params.json`.
2. **Read anywhere, write only through the portal.** Reading needs no session. Every write (a value, a param, a text, a colour, a flag)
   needs the session `run` started with the vault ON, for this very game process, and goes through the same gate.
3. **Memory only.** Nothing is written to the game folder or to the save files; the `regulation.bin` built from `creative.json` is
   swapped in and put back by the vault.
4. **One command, one job, then it ends.** What stays open is what must: `run`, `read --live`, `read monitor...`, `export --live` and the
   scripts' host (`scripts start`).

---

## Every command at a glance

| **Level** | **Command** | **What it does** |
|:---|:---|:---|
| the portal | `run` | back up, swap in the build, launch offline; once a character is in the world: `innovate-spells apply`, `resurrect` (the list of `creative.json`) and `scripts start *`; restore when the game closes |
| 1st: vault | `vault status \| list \| verify \| restore \| keep \| prune` | the snapshots and the session record |
| 2nd: core | `read [* \| all \| NAME \| ID \| PATH ...] [--live] [--tree \| --flat \| --json]` | the document, or a part of it |
| 2nd: core | `read monitor \| monitor-buffs \| monitor-animations [--mapped \| --unmapped]` | one row per buff / animation id that appears |
| 2nd: core | `write NAME=VALUE ...`, `write NAME=default`, `write` | change values in the running game; `write` alone lists the names and their ranges |
| 3rd: creative | `scripts [* \| all]`, `scripts start \| restart \| stop \| status [NAME[:ID[:PROCESS_ID]] \| * \| all]`, `scripts add \| remove \| change PATH` | your scripts |
| 3rd: creative | `innovate-spells`, `innovate-spells build [* \| all \| NAME \| ID ...] \| secure \| apply` | new spells |
| 3rd: creative | `resurrect NAME \| ID \| PATH ... \| * \| all [--dry-run] [--when-loaded]` | a beaten boss alive again |
| data | `export [--disk] [--params] [--live]` | the document to `<TOOLS-DIR>\output\disk.json`; `--params`: every row of every table to `params.json` |
| data | `reset [* \| all \| runes \| buffs \| animations \| monitor]` | the read baselines start again from now |
| data | `check [FILE]` | a `regulation.bin` against the game, row by row |
| data | `probe [inventory]` | where the game's param tables (or the inventory) lie in memory |
| tooling | `hash`, `--version` | the SHA-256 of `eldenring.exe` (the key of its profile), the tool's version |

`<TOOLS-DIR>` is `%LOCALAPPDATA%\EldenDisk`: everything the tool keeps lives there, never next to the exe.

**Naming (`NAME | ID | PATH`).** Everywhere a thing is named, three forms work: the **path** in the document
(`creative.resurrect.great_enemies.12050800`), the **id** (`12050800`, the game's own number) and the **name** in any letter case or a part
of it (`mohg lord`). A name that fits several is refused with the list; a wrong name changes nothing. `*` and `all` mean every one and stand
alone. The character's values have short forms: `character.` may be left out, `attrs` = `attributes`, `hp` = `hit_point`, `fp` =
`focus_point`, `max` = `maximum`.

**Flags of every command**

| **Flag** | **What** | **Commands** |
|:---|:---|:---|
| `-v`, `--verbose` | the log lines themselves, live, instead of the concise view | all |
| `--vault DIR` | the vault to use (remembered once `run` is given it) | all but `hash` |
| `--save-dir DIR` | the game's save folder, for several Steam accounts (remembered) | `run`, `vault restore` |
| `--game-dir DIR` | where `eldenring.exe` is (found through Steam otherwise) | `run`, `innovate-spells`, `hash` |
| `--offsets FILE` | the profile: the pointer chains of each game version (`offsets.json`; the one in the exe by default) | `run`, `read`, `write`, `scripts`, `innovate-spells`, `resurrect`, data |
| `--names FILE` | `names.json`: the names of the buffs and the animations (the one next to the exe, else the one in it) | `read`, `scripts`, `export`, `reset` |
| `--spec FILE` | the creative file (`creative.json` next to the exe, else the one in the exe) | `run`, `read`, `write`, `scripts`, `innovate-spells`, `resurrect`, `export` |
| `--creative-dir DIR` | where builds, secured files and the scripts' status are kept (`<vault>\creative`) | the same |
| `--vault-on`, `--vault-off` | open the portal (default) / play without it | `run` |
| `--regulation FILE` | swap this `regulation.bin` in instead of the one built from `creative.json` | `run` |
| `--keep N` | the newest snapshots kept | `run`, `vault prune` |
| `--yes` | what cannot be undone is done only with it | `vault keep` |
| `--hz N` | reads per second, 1 to 120 (default 60) | `read`, `export` |
| `--version` | prints the version and ends | `python -m eldendisk` |

**Exit codes (every command)**

| **Code** | **Meaning** |
|:---|:---|
| `0` | done (also when there was nothing to do: a boss already alive, a value already set) |
| `1` | an error, or not applied (a wrong name, a value that did not stick, no character in the world) |
| `2` | not supported: no profile for this `eldenring.exe`, the profile lacks the block the command needs, or a read-only `params` field named in `write`; also a usage error of the command line |
| `3` | the anti-cheat is running: the tool refuses to touch the game |
| `4` | a restore is pending: run `vault restore` first |
| `5` | no portal: no session of `run` with the vault ON for this game process (every write) |
| `130` | interrupted (Ctrl+C) |

---

## 1. `run`: the portal

```commandline
python -m eldendisk run [--vault-on | --vault-off] [options]
```

1. Snapshot `ER0000.sl2`, `ER0000.sl2.bak`, `ER0000.err`, `ER0000.err.bak`, `steam_autocloud.vdf` into the vault, each file hashed.
2. Copy the game's own `regulation.bin` into the vault, build a new one from `creative.json` (`innovate-spells`) and swap it into the game
   folder for the session: the secured copy when the spells are unchanged since `innovate-spells secure`, else the latest build when it
   is unchanged, else a new build (a few seconds) that the gate must pass. A failed gate stops `run`: nothing is swapped, the game is not
   started.
3. Launch `eldenring.exe` offline.
4. Once a character is in the world, three steps start, each a process of its own (their lines appear in the same console):
   `innovate-spells apply --when-loaded` (the spells' texts and colours, when the build has any), `resurrect --when-loaded` (the list of
   `resurrect.great_enemies.activate` in `creative.json`, when it names any), and, once those two are done, `scripts start * --when-loaded`
   (the default scripts and `scripts.added`).
5. While you play, run the other commands in another terminal.
6. Quit the game: the vault puts the save files and the game's own `regulation.bin` back, byte for byte, and checks them by hash. If
   either cannot be restored, the session record stays and the next `run` refuses (exit `4`) until `vault restore`.

| **Flag** | **Default** | **What** |
|:---|:---|:---|
| `--save-dir DIR` | found / remembered | the save folder (`%APPDATA%\EldenRing\<SteamID64>`); remembered in `HKCU\Software\EldenDisk` |
| `--vault DIR` | remembered, else `%LOCALAPPDATA%\EldenDisk\vault` | the vault; an explicit value is remembered |
| `--game-dir DIR` | found through Steam | the folder of `eldenring.exe` |
| `--regulation FILE` | none | swap this file instead of the build (an experiment; vault ON only) |
| `--spec FILE`, `--creative-dir DIR` | see above | the creative file and its folder |
| `--offsets FILE` | the one in the exe | checked before launching: the exe must have a profile |
| `--vault-on` / `--vault-off` | `--vault-on` | OFF: no backup, no restore, nothing swapped or written (`write`, `resurrect`, `innovate-spells apply` and `scripts start` are refused); for reading while farming, when you want to keep what you earn |
| `--no-archive-contaminated` | off | do not keep a copy of the changed save in the vault before restoring it |
| `--keep N` | `5` | after a finished session keep the newest N snapshots; `0` = never prune |
| `--launch-timeout SEC` | `120` | seconds to wait for `eldenring.exe` |

**Steam Cloud** may sync the save when the game exits (not verified): `run` says so when Steam is running. Use Steam's offline mode or turn
Steam Cloud off for Elden Ring.

To **keep** what you changed instead: let the game save (rest at a grace or quit to title), close the game, end `run`, then
`vault keep --yes`. After a power loss, a killed `run` or a closed console: close the game and run `vault restore`.

---

## 2. `vault` (1st level)

```commandline
python -m eldendisk vault status | list | verify SNAPSHOT | restore | keep | prune --keep N
```

| **Function** | **What** |
|:---|:---|
| `status` | the session record, the last snapshot, the vault's size |
| `list [--fast]` | the snapshots: time, size, verified (`--fast` skips the hashing) |
| `verify SNAPSHOT` | hash a snapshot again against its manifest |
| `restore [--snapshot NAME] [--save-dir DIR]` | finish an unended session: archive the current save files, put the snapshot back, verify; safe to repeat |
| `keep --yes` | take the current save files as the new baseline and end an unresolved session (without `--yes` it only explains) |
| `prune --keep N` | delete old snapshots, keep the newest N; refused while a session is open |

---

## 3. `read` (2nd level)

```commandline
python -m eldendisk read [* | all | NAME | ID | PATH ...] [--live] [--tree | --flat | --json]
python -m eldendisk read monitor | monitor-buffs | monitor-animations [--mapped | --unmapped]
```

`read` follows the profile's pointer chains, builds the document and prints it, or the parts you name. Read-only: it never opens a write
handle and works with or without `run` (it waits for `eldenring.exe` and for a loaded world, `--timeout` seconds; 15 by default).

| **Form** | **What** |
|:---|:---|
| `read`, `read *`, `read all`, `read disk` | the whole document once (what `disk.json` holds) |
| `read inventory`, `read inventory.gold_pickled_fowl_foot.quantity`, `read inventory.goods.1200` | what the character carries (1.8.1); one item by its name in any kind, or by kind and id |
| `read disk.character.level`, `read disk.character.*` | a part of it, by its path in `disk.json`; shown as `disk.<path>`. Without `disk.` (`level`, `hp`, `attrs.*`) the same values, shown as before. `write` takes `disk.` names too |
| `read hp attrs.* character.runes` | one or several values or groups |
| `read creative.resurrect.great_enemies` | the great enemies defeated now; a boss by name: `read creative.resurrect.great_enemies.margit` |
| `read creative.innovate_spells.reverse_cursed_technique` | a spell of the last build (by its name or its goods id) |
| `read params` | every table of the game (194 in 1.17.1) with its number of rows, from the game (the tables are not in `disk.json`) |
| `read params.NpcParam`, `read params.SpEffectParam.1621000` | every row of a table, one row (Black Flame), read from the game now; once, not with `--live` |
| `read params.Magic.6230.mp*`, `read params.NpcParam.*.hp` | the fields of a row that match, a field of every row |
| `--live` | keep the values current at `--hz` (on a terminal the tree is redrawn and a changed value lights up; elsewhere one line per change) |
| `--tree` (default), `--flat`, `--json` | a tree; one `full.path  value` row per value; JSON (not with `--live`) |

**Monitors.** `read monitor-buffs` polls the active buffs (the game's SpEffects), `read monitor-animations` the animation, `read monitor`
both: one `+` / `-` row per id with its time, named from `names.json`. `--unmapped` (the default) shows only the ids `names.json` does not
name yet (what a monitor is for: finding new ids), `--mapped` only those it names. `-q` hides short internal buffs. `names.json` is read
again when it changes, so names added while a monitor runs show at once.

`names.json` names the buffs and the animations the game gives no readable name for (`311100` "Gold Scarab", `TALISMANS`; `26030000`
"Attacking (R1)", `MANNER`). It belongs to the reader (`code/eldendisk/reader/names.json`) and is always in the exe; a `names.json` next to
the exe wins, so names can be added without a new build. The buffs of the spells in `creative.json` are named by the build.

---

## 4. `write` (2nd level)

```commandline
python -m eldendisk write NAME=VALUE [NAME=VALUE ...]
python -m eldendisk write NAME=default
python -m eldendisk write
```

`write` alone lists the names that can be written and their ranges, and writes nothing. With pairs it checks the portal (the session
record names this very game process: its pid, start time and exe hash; exit `5` otherwise), resolves each name, checks the range, writes
through the gate and reads back.

| **Name** | **Values** | **What** |
|:---|:---|:---|
| `level` | 1 - 713 | the character's level |
| `runes` | 0 - 999,999,999 | the runes held (`character.runes.total`) |
| `vigor`, `mind`, `endurance`, `strength`, `dexterity`, `intelligence`, `faith`, `arcane` | 1 - 99 | the attributes (`attrs.*` for all) |
| `hp`, `fp`, `stamina` | 0 - maximum | the current value; a number above the maximum is the maximum (`write hp=99999` fills it) |
| `params.<Table>.<id>.<field>` | the field's type, or `default` | any numeric field of any row of any table of the game (`params.SpEffectParam.1621000.effectEndurance`; a pattern: `params.Magic.6230.mp*`) |
| `params=default` | | every `params` value changed in this game process back to the game's own |
| `creative.innovate_spells.<goods id>.design.<path>` | as `creative.json` says | the spells of the last build: `requires.*`, `locations.*`, `customs.basic.*`, `customs.advanced.texts.*`, `customs.advanced.colors.*` |
| `creative.resurrect.great_enemies.<id or name>.defeated` | `false` | brings a defeated boss back (`true` is refused: only the game marks a boss defeated) |
| `creative.scripts.<defaults or added>.<NAME>.state` | `stopped`, `live` | the same as `scripts stop | start NAME` (a host must run) |

- `NAME=default` puts back the value the game had **before the first change in this game process** (kept in `<vault>\params-snapshot.json`,
  tied to the game's pid and start time); a field, a row (`params.Magic.6230=default`), a pattern, or `params=default`. Only `params`
  names have a default; the character's values are your save's own (write the number).
- A `params` value is checked against the field's type and bit width (an error, not a clamp). A field that names another row
  (`vfxId`, `refId1` ...) is written with a note: an id that matches nothing can crash the game when the row is used.
- A table is the game's own name (`EquipParamWeapon`, `SpEffectParam`, `NpcParam`, `ItemLotParam_map` ...) in any letter case; the short
  names `Goods`, `SpEffect`, `ShopLineup`, `MagicParam`, `BulletParam`, `AtkParam` still work. `params.effects` is gone (1.8.0): its rows
  are `params.SpEffectParam.<id>`.
- What changes acts on what is created afterwards: a Magic row is read at the cast, a Bullet row when the bullet is created. A value stays
  through Quit to Title and is gone when the game process ends.
- **Offline only.** Params are what the game trusts; with anti-cheat active or online a change can get an account banned. `run` starts the
  game offline.

---

## 5. `scripts` (3rd level)

```commandline
python -m eldendisk scripts [* | all] [--tree | --flat | --json]
python -m eldendisk scripts start [NAME[:ID[:PROCESS_ID]] | * | all] [--when-loaded]
python -m eldendisk scripts restart | stop | status [NAME[:ID[:PROCESS_ID]] | * | all]
python -m eldendisk scripts add | remove | change PATH
```

Your own Python scripts run next to the game while it runs, each in a thread of its own, in **one host process** for the session. A script
reads the game as the document and writes back what it changes:

```python
from edstdlib import *

class BossRush(Interface):
    every = 1.0                                                   # seconds between two loop()

    def loop(self):
        x = tools.read()                                          # the document, as an object
        for boss in x.creative.resurrect.great_enemies.values():   # the defeated ones
            if boss.name.startswith("Mohg"):
                boss.defeated = False                             # bring him back
        tools.write(x)                                            # writes only what changed
```

| **Name** | **Does** |
|:---|:---|
| `Interface` | the base of a script: `setup()` once, `loop()` every `every` s, `teardown()` at the end; `enabled = False` keeps it off |
| `tools.read()` | the document as an object (`x.character.runes.total`, `x.params.SpEffectParam[1621000].effectEndurance`: a row of a table is read from the game when it is touched) |
| `tools.write(x)` | writes what changed in it, through the portal, as `write` does; `True` when everything stuck |
| `tools.log(text, level)` | a line in the log and on the `run` console, under the script's name |
| `tools.dead()` | ends this script now |

| **Function** | **What** |
|:---|:---|
| (none), `*`, `all` | every script (the defaults and the added ones) with its state, as the document's `creative.scripts` |
| `start [NAME]` | no host runs: this command becomes the host (it attaches to the game `run` started, checks the session as `write` does, and runs the scripts until the game closes; `NAME`: only that one at first). A host runs: it starts that script there (`setup()`, then `loop()`) |
| `restart NAME` | stop it, load its file again, start it (the id is kept) |
| `stop NAME` | ask it to stop: its loop ends, `teardown()` runs. `stop *` ends the host itself |
| `status [NAME]` | what the host says: state, loops, last error |
| `add PATH` | check the file (or every `*.py` of the folder) loads, put it in `scripts.added` of `creative.json`; a running host loads and starts it |
| `remove PATH` | take it out of the list (a running host stops it first) |
| `change NEW` or `change OLD NEW` | point the entry with the same file name (or `OLD`) at `NEW`; a running host loads it again |

- **Addressing.** `NAME` is the script's class (`RctColoursFollowTheSpell`, any letter case; or its file's name), `ID` its number in the host
  (1, 2, ...: two scripts of the same class name in different files), `PROCESS_ID` the host's process. The name alone is enough while it
  is unique.
- **Control from another terminal.** `start`, `restart`, `stop` and `add / remove / change` leave a small request file in
  `<vault>\creative\scripts.requests\`; the host looks once a second, does it and answers in its status file
  (`<vault>\creative\scripts.status.json`). No port is opened.
- **A limit to know.** Python cannot kill a thread: `stop` asks the script to stop; a script stuck in its own code ends only with the host
  (`scripts stop *`, or the game closing). There is no `kill` for one script.
- **States.** `loaded`, `setup`, `live`, `waiting` (no character in the world: that `loop()` is skipped), `stopped`, `dead` (an exception;
  `last_error` has its last line), `failed` (the file could not be loaded), `off` (`enabled = False`), `stuck` (a loop that has not
  returned for 10 s). `slow`: a loop longer than its pace was seen.
- **The scripts.** The defaults are `code/eldendisk/creative/scripts/defaults/*.py`, embedded in the exe by the build; the added ones are
  the files and folders of `scripts.added`. Examples to copy: `code/tests/external_scripts/`.

---

## 6. `innovate-spells` (3rd level)

```commandline
python -m eldendisk innovate-spells
python -m eldendisk innovate-spells build [* | all | NAME | ID ...] [--dry-run] [--source FILE]
python -m eldendisk innovate-spells secure
python -m eldendisk innovate-spells apply [--when-loaded]
```

| **Function** | **What** |
|:---|:---|
| (none) | the spells of `creative.json` with their ids, built or secured, and what changed since the secured copy |
| `build` | copy the template rows, apply the design, re-encode; the gate judges the file read back from disk. Nothing, `*` or `all`: every spell; names (the key of a slot in `creative.json`) or ids (the goods id: 2230000 + slot - 1): only those, and `run` goes on building the same selection until another `build` |
| `secure` | after you tried the build in the game (game closed): judged again and kept as `regulation.secured.bin`; `run` then swaps it without building while the spells do not change |
| `apply` | put the spells' texts (name, short line, description) and colours (the fire of Flame, Grant Me Strength, the ring, the eyes) into the running game: memory only, until the game closes. `--when-loaded`: wait for a character in the world (what `run` starts) |

- **The files:** `<vault>\creative\innovate-spells\`: `regulation.bin` (the latest build), `regulation.secured.bin` and `spells.commit.json`
  (the secured copy and what it was built from), `spells.build.json` (which spells the build holds), `spells.resolved.json` (the spells as
  they became in the game: the document's `creative.innovate_spells`).
- **Always on the game's own file.** The game's `regulation.bin` is checked against the known 1.17.1 original; a modified one is refused.
- **Spell kinds:** `buff`, `clone`, `enchant`, `projectile`, `attack` (see the item-customization handbook). Up to 64 slots in the format;
  slots 1-7 have a shop line in the game.
- `apply` finds what it changes by looking through the game's memory and remembers where in `<vault>\memory-cache.json` (that game
  process only), so a later change of a text or a colour (`write creative.innovate_spells...`, a script) writes at once.

---

## 7. `resurrect` (3rd level)

```commandline
python -m eldendisk resurrect NAME | ID | PATH ... | * | all [--dry-run] [--when-loaded]
```

A boss you have beaten (any of the 212 great enemies, the DLC included) alive again for the session: its event flags (the defeat, its
Remembrance's play-log trigger, its drops, its intro) are turned off in the game's memory only. It appears once its area loads again:
rest at a Site of Grace. When the game closes the vault puts the save back and the boss is dead again.

- `read creative.resurrect.great_enemies` shows the bosses that are defeated now (the ones that can come back), with the place, the nearest
  grace, the runes and the drop. There is no list command: the document is the list.
- `resurrect margit`, `resurrect "mohg lord"`, `resurrect 12050800`, `resurrect creative.resurrect.great_enemies.12050800`; `*` or `all`:
  every defeated one. `--dry-run` says what would come back and writes nothing.
- `write creative.resurrect.great_enemies.margit.defeated=false` does the same; `true` is refused.
- A story boss can leave the world looking odd (a Great Rune, the people who speak of the death) until the game closes.
- `creative.json` can name a list `run` brings back every session: `"resurrect": {"great_enemies": {"activate": ["margit", "12050800"]}}`
  (or `"all"`).

---

## 8. Data

```commandline
python -m eldendisk export [--disk] [--params] [--live] [--out DIR]
python -m eldendisk reset [* | all | runes | buffs | animations | monitor]
python -m eldendisk check [FILE] [--json]
python -m eldendisk probe [inventory [--find ID ...]] [--json]
```

| **Command** | **What** |
|:---|:---|
| `export --params` | every row of every table of the game, every field, read from the game now, to `<TOOLS-DIR>\output\params.json` (once, about 500 MB and 10 s; one row a line, so `findstr` finds a row; a table no layout decodes has its rows as bytes, `{"_raw": "hex"}`). `read params...` never reads this file: it reads the game |
| `export`, `export --disk` | the whole document to `<TOOLS-DIR>\output\disk.json`, once (no `params` in it; `--disk --params` writes both files). `--live`: again each time it changes (at most every `--export-interval` s, 0.5; a change that is only a buff countdown at most every `--timer-interval` s, 2; it pauses while the game window is not in front unless `--no-idle`) |
| `reset` | the game's values now become the read baselines: `runes` (`character.runes.baseline` = the total now, `delta` = 0), `buffs` / `animations` (`monitor`: both; the monitors' history of what has ended is cleared). Nothing is written to the game: a small file (`<TOOLS-DIR>\baselines.json`, for this game process) that every reader takes within a few seconds |
| `check` | decode a `regulation.bin` (the one in the game folder by default: what the game loaded) and compare the six tables with the game's, row by row; exit `0` only when they agree |
| `probe inventory` | where the inventory is in PlayerGameData and how an entry is laid out; `--find ID` prints every place a goods id is, with the bytes around it (for a new game version; read-only) |
| `probe` | find where the game's param tables lie in memory and check them against the profile's chains; then every slot of the game's list of tables with the table it was named as, and the tables not found (for a new game version) |

---

## 9. `hash` and the version

```commandline
python -m eldendisk hash [--game-dir DIR]
python -m eldendisk --version
```

`hash` prints the SHA-256 of `eldenring.exe`, the key of its profile in `offsets.json` (a new game version needs one). `--version` prints
the tool's version.

### Building `eldendisk.exe` (not a command)

```commandline
# all tests -> a clean build of build\dist\eldendisk.exe (offsets.json and creative.json embedded, names.json and the default scripts
# always) -> a status report (where the exe is, its size, SHA-256, version, the embedded files, the time of each step)
python code/tools/dev_pipeline.py
# --skip-tests, --no-embed (offsets.json and creative.json next to the exe), --engine nuitka, --icon ICO, --keep-app-data
```

The build writes a `README.md` next to the exe from `docs/guilde/README-exe.md` and `docs/guilde/cli-commands-exe.md`.

---

## `creative.json`

What you edit to shape the parallel world. `run` reads it at every session (`--spec FILE`, else next to the exe, else the copy in the
exe); one section per creative feature, each optional but `innovate_spells`:

```json
{
  "innovate_spells": {
    "maximum": 20,
    "slots": {
      "reverse_cursed_technique": { "kind": "projectile", "from": 6421, "requires": {}, "locations": {}, "customs": {} }
    }
  },
  "scripts": {
    "added": ["D:\\my-scripts\\boss_rush.py", "D:\\my-scripts\\colours\\"]
  },
  "resurrect": {
    "great_enemies": { "activate": ["margit", "12050800"] }
  }
}
```

| **Section** | **`run` does with it** |
|:---|:---|
| `innovate_spells` | builds `regulation.bin` when the spells changed (or swaps the secured one), then `innovate-spells apply` in the world |
| `scripts.added` | starts these scripts with the defaults, in the world (`scripts add / remove / change` edit the list) |
| `resurrect.great_enemies.activate` | `resurrect` in the world: `"all"` / `"*"`, or names and ids |

A wrong name or value is an error that names its place in the file; nothing is built from a file with an error.

---

## The document

`read` shows it, `export` writes it as `<TOOLS-DIR>\output\disk.json`, `tools.read()` gives it to a script. Three blocks
(the game's tables are not in it: `read params...` reads them from the game, `export --params` writes them to `params.json`; a script's
`tools.read()` has them too, as `x.params.<Table>[id]`):

| **Block** | **What** |
|:---|:---|
| `systems` | the profile, the features this game version supports (`buffs_supported`, `animations_supported`, `creative_supported`), the status, the session (`mode`: `creative` inside the portal, else `telemetry`; `read_only`; `creative`) |
| `character` | `level`, `vitals`, `runes` (`total`, `baseline`, `delta`), `attributes`, `buffs`, `animations`, `equipment.magic`, `inventory` (1.8.1: `goods`, `key_items`, `talismans`, `weapons`, `armor`, `ashes_of_war`; each item by id with `name`, `quantity` (`total`, `held`, `stored`: in the storage chest), goods' `type`, weapons' `upgrade`) |
| `creative` | `scripts` (`host` and every script), `innovate_spells.<goods id>` (`id`, `slot`, `rows`, and apart `design`), `resurrect.great_enemies.<id>` (the defeated ones only) |

The full example is in [spec 1.8.0 part 2, "The single source of truth"](../specs/elden-disk-spec-v1.8.0.md).

---

## Where things live

```text
%LOCALAPPDATA%\EldenDisk\   (<TOOLS-DIR>)        everything the tool keeps (never next to the exe: a new build cannot delete it)
 ├─ vault\
 │   ├─ <time>\                                 a snapshot: the save files, their manifest (hashes), bin\regulation.bin (the game's own),
 │   │                                           contaminated\ (the session's changed save, archived at the restore)
 │   ├─ session.json                            the session record: open while the portal is open; left open = a restore pending
 │   ├─ creative\                               innovate-spells\ (builds, the secured file), scripts.status.json, scripts.requests\
 │   ├─ memory-cache.json                       where this game process holds what was written (texts, colours)
 │   ├─ params-snapshot.json                    the game's own values of what `write` changed (for NAME=default)
 │   └─ eldendisk.log                           the log of every command
 ├─ baselines.json                              what `reset` set
 ├─ exe-sha256.json                             the hash of eldenring.exe, kept while the file stays the same
 └─ output\disk.json, params.json               what `export` and `export --params` write
<exe folder>\                                   eldendisk.exe; offsets.json, names.json, creative.json when you put them next to it
                                                (they win over the copies in the exe)
```

A vault of 1.7.x / 1.8.0 part 1 is moved once: `<vault>\design` (or `extension`) becomes `<vault>\creative`, and its
`innovate-items\spells\` becomes `innovate-spells\`.

---

## Log and output

Every command prints concise lines (a result, a warning, an error). Everything is also logged, logcat style, to `<vault>\eldendisk.log`
(every command line and exit code included); `-v` on any command shows that log live instead. `run -v` also shows the lines the steps it
started and the other terminals log.

---

## Examples

```commandline
# the portal (leave it open)
python -m eldendisk run
# several Steam accounts: pass the save folder once (remembered)
python -m eldendisk run --save-dir "C:\Users\<User>\AppData\Roaming\EldenRing\<SteamID64>"

# read: everything once, a part, kept current, as rows
python -m eldendisk read
python -m eldendisk read runes hp attrs.*
python -m eldendisk read character.runes --live
python -m eldendisk read creative --flat

# the monitors: the ids names.json does not name yet
python -m eldendisk read monitor
python -m eldendisk read monitor-buffs --mapped

# write (inside the portal)
python -m eldendisk write
python -m eldendisk write vigor=99 level=150 hp=99999
python -m eldendisk write params.SpEffectParam.1621000.effectEndurance=-1
python -m eldendisk write params.Magic.6230.mp=0
python -m eldendisk write params=default

# creative
python -m eldendisk innovate-spells build
python -m eldendisk innovate-spells secure
python -m eldendisk resurrect "mohg lord" margit
python -m eldendisk resurrect all --dry-run
python -m eldendisk scripts
python -m eldendisk scripts add D:\my-scripts\boss_rush.py
python -m eldendisk scripts restart BossRush

# data
python -m eldendisk export --live
python -m eldendisk reset runes
python -m eldendisk check

# keep the changes: let the game save, close it, end `run`, then
python -m eldendisk vault keep --yes
# after a crash, a power loss or a closed console: close the game, then
python -m eldendisk vault restore
```

---

## What changed in 1.8.0

| **Before** | **Now** |
|:---|:---|
| `design`, `design.json`, `<vault>\design`, `--design-dir`, the block `design` | `creative`: `creative.json`, `<vault>\creative`, `--creative-dir`, the block `creative` |
| `design --list` | `innovate-spells` (and `read creative`) |
| `innovate-items spells --add all \| PATH ...`, `--secure` | `innovate-spells build [all \| NAME \| ID ...]`, `innovate-spells secure` |
| `write --text`, `write --flame-color` | `innovate-spells apply` |
| `external-scripts`, `external-scripts --run`, `--scripts-dir PATH` | `scripts`, `scripts start`, `scripts add PATH` (kept in `creative.json`) |
| `resurrect great-enemies --activate NAME`, `--list` | `resurrect NAME`; the list is `read creative.resurrect.great_enemies` (the defeated ones only) |
| `read --query NAME` | `read NAME` |
| `read --export`, `disk-state.json` | `export`, `<TOOLS-DIR>\output\disk.json` |
| `read --param Table.ID`, `--param-check FILE`, `--probe-params` | `read params.Table.ID`, `check FILE`, `probe` |
| `read --live-buffs`, `--live-animations` | `read monitor-buffs`, `monitor-animations`, `monitor` (`--unmapped` by default) |
| `write --set NAME=VALUE`, `--reset NAME`, `--refill LIST` | `write NAME=VALUE`, `write NAME=default`, `write hp=<a big number>` |
| (none) | `reset`, `scripts start \| restart \| stop \| status`, `creative.scripts` in the document |
| `chr_state_ids.json` next to `offsets.json` | `names.json` in the reader's package (one next to the exe still wins) |
| `systems.session.mode` `"sandbox"`, `sandbox` | `"creative"`, `creative` |

Why each changed: the Remarks of [spec 1.8.0 part 2](../specs/elden-disk-spec-v1.8.0.md).

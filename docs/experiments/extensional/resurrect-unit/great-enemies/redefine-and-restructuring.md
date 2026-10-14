# Redefine & Restructure (version 1.8.0)

_(Purpose: make the tool consistent and its foundation strong, before more is built on it.)_

## Definition

**Elden-Disk is the Elden Ring Memory Disk I/O Tools.** It works as **CLI commands in a console** (Windows 10/11, 64-bit) and has no
user interface it does not need: you open a terminal, run a command, it does its work and ends. Everything the tool can do is a command,
and every command reads the same way (section "Commands").

**Philosophy: the portal.** Elden-Disk is a **portal into a parallel world** of the real game world (Elden Ring, the Lands Between).
Through the portal the world mirrors everything of the game, and you can play with it in **creative ways** (new items you design, great
enemies brought back, scripts that change the game while it runs, and more). When you leave through the portal, the real world is back
exactly as it was: **nothing you did inside comes back with you.** The vault is the portal: it keeps the real world (the save files `ER0000.sl2`, `ER0000.sl2.bak`, `ER0000.err`, `ER0000.err.bak`, `steam_autocloud.vdf`, and the
game's own files) before you go in, and puts it back, byte for byte, when you come out.

## Backbone: running the game ⟶ loading the world ⟶ playing ⟶ quitting the game

```text
vault: back up ER0000.sl2, ER0000.sl2.bak, ER0000.err, ER0000.err.bak, steam_autocloud.vdf (and swap in the regulation.bin built from creative.json)   `run`, the portal opens
 │
 ├─ read      reads the game's memory (RAM): the pointer chains of the profile (offsets.json), or a small scan when the chain is not
 │   │        known; every value is a name in ONE document, the single source of truth (below)
 │   ├─ [nothing | * | all]        all of the document
 │   └─ [NAME | ID | PATH ...]     a part of it: `hp`, `creative.resurrect.great_enemies.margit`, `params.Magic.6230.mp`
 │       └─ [--live | --tree (default) | --flat | --json]     what to do with what is read
 │
 ├─ write     writes the game's memory through the same chains, only inside the session `run` started (vault ON)
 │   ├─ [NAME | ID | PATH = VALUE ...]   a name that `read` shows: `write creative.resurrect.great_enemies.margit.defeated=false`
 │   └─ [NAME | ID | PATH = default]       the game's own value back
 │
 ├─ creative  what is built and run next to the game (it depends on the vault, like `write`)
 │   ├─ scripts                 your Python scripts, running next to the game while it runs
 │   │   ├─ defaults            the scripts the exe carries (creative/scripts/defaults)
 │   │   └─ added               the scripts added after the build (`scripts add PATH`)
 │   ├─ innovate-spells         new spells: creative.json -> a regulation.bin judged by a gate -> secured
 │   └─ resurrect               a boss you have beaten (a great enemy), alive again for the session
 │
 ├─ data      export, reset, check, probe: the document to a file, the baselines, a regulation.bin compared, the param tables found
 │
vault: restore ER0000.sl2, ER0000.sl2.bak, ER0000.err, ER0000.err.bak, steam_autocloud.vdf and the game's own files (byte for byte)   the game closes, the portal closes
```

Rules every branch follows:

1. **One document.** Whatever the tool knows of the running game is a path in the single source of truth (`systems`, `character`,
   `params`, `creative`). `read` shows it, `write` and `tools.write` change it, `export` writes it as `output\disk.json`. Nothing
   has a second name somewhere else.
2. **Read anywhere, write only through the portal.** Reading needs no session. Every write (a value, a param, a text, a colour, a flag)
   needs the session `run` started with the vault ON, for this very game process, and goes through the same gate.
3. **Memory only.** Nothing is written to the game folder or to `ER0000.sl2`, `ER0000.sl2.bak`, `ER0000.err`, `ER0000.err.bak`, `steam_autocloud.vdf`; what is built from `creative.json` (regulation.bin) is swapped in and put
   back by the vault.
4. **One command, one job, then it ends.** The things that stay open are the ones that must: `run` (the session), `read --live`, the
   scripts' host.
5. **The game's own data first.** Ids, names, flags and places come from the game's files (its params, event scripts and text); a list
   made by hand is the exception, and a test checks it against the game.

## Commands

**Beginning with `run` (or `run --vault-on -v`) to enter the Portal**

**Mechanism:**
1. Snapshot `ER0000.sl2`, `ER0000.sl2.bak`, `ER0000.err`, `ER0000.err.bak`, `steam_autocloud.vdf` from **The Real Game Save** into
   **The Vault**, each file hashed.
2. Copy the game's own `regulation.bin` into **The Vault**, build a new one with **Creative** (`innovate-spells`, ...) and swap it
   into **The Real Game Files** for the session.
3. Launch `eldenring.exe` in offline mode.
4. Once a character is in **The Game World**: the advanced designs (the spells' texts and colours, the great enemies to bring back) are
   found in **The Real Game Memory** by a quick scan or the profile's pointer chains, checked, and written.
5. The external scripts (the defaults and the added ones) start, each in a thread of its own.
6. While you play in **The Game World**, open another terminal and run the commands of the **1st**, **2nd** and **3rd** levels and the **Data** commands below.
7. Quit the game: **The Vault** puts the save files and the game's own `regulation.bin` back into **The Real Game Files**, byte for byte.
   That keeps **The Parallel Dimension World** apart from the real one and, above all, keeps your account safe: nothing edited stays.

### 1st Level: Vault Coverage

| **Commands** | **Functions** | **Mechanism**                                                                                                                                                           |
|:-------------|:--------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `vault`      | `status`      | Show the session record, the last snapshot, the vault's size                                                                                                            |
| `vault`      | `list`        | List the snapshots: time, size, verified                                                                                                                                |
| `vault`      | `verify`      | Hash a snapshot again against its manifest                                                                                                                              |
| `vault`      | `restore`     | Finish an unended session: archive `ER0000.sl2`, `ER0000.sl2.bak`, `ER0000.err`, `ER0000.err.bak`, `steam_autocloud.vdf`, put the snapshot back, verify; safe to repeat |
| `vault`      | `keep`        | Take the current `ER0000.sl2`, `ER0000.sl2.bak`, `ER0000.err`, `ER0000.err.bak`, `steam_autocloud.vdf` as the new baseline (`--yes`)                                    |
| `vault`      | `prune`       | Delete old snapshots, keep `--keep N`; refused while a session is open                                                                                                  |

### 2nd Level: Core Feature

| **Commands** | **Parameters**      | **Options**                 | **Outputs**                            | **Mechanism**                                                                                  |
|:-------------|:--------------------|:----------------------------|:---------------------------------------|:-----------------------------------------------------------------------------------------------|
| `read`       | `EMPTY`, `*`, `all` | `EMPTY (default)`, `--live` | `--tree (default)`, `--flat`, `--json` | Follow the profile's pointer chains ⟶ build the whole document; `--live` repeats at `--hz`     |
| `read`       | `[NAME\|ID\|PATH]`  | `EMPTY (default)`, `--live` | `--tree (default)`, `--flat`, `--json` | Resolve the name to its path ⟶ read only that part; `--live` repeats at `--hz`                 |

| **Commands** | **Functions**        | **Outputs**                        | **Mechanism**                                                                           |
|:-------------|:---------------------|:-----------------------------------|:----------------------------------------------------------------------------------------|
| `read`       | `monitor`            | `--mapped`, `--unmapped (default)` | Both monitors in one view                                                               |
| `read`       | `monitor-buffs`      | `--mapped`, `--unmapped (default)` | Poll the active `SpEffects` ⟶ one `+` / `-` row per id, named from `names.json` |
| `read`       | `monitor-animations` | `--mapped`, `--unmapped (default)` | Poll the active `anim` ⟶ one `+` / `-` row per id, named from `names.json`      |

| **Commands** | **Parameters**             | **Mechanism**                                                                                                                |
|:-------------|:---------------------------|:-----------------------------------------------------------------------------------------------------------------------------|
| `write`      | `EMPTY`                    | List the writable names and their ranges; write nothing                                                                      |
| `write`      | `[NAME\|ID\|PATH]=[VALUE]` | Check the portal ⟶ resolve the name ⟶ check the range ⟶ write through the gate ⟶ read back; `default` = the game's own value |

### 3rd Level: Creative Feature

_(`design` was removed)_

| **Commands** | **Parameters**      | **Outputs**                            | **Mechanism**                                         |
|:-------------|:--------------------|:---------------------------------------|:------------------------------------------------------|
| `scripts`    | `EMPTY`, `*`, `all` | `--tree (default)`, `--flat`, `--json` | List every script (defaults and added) with its state |

_(`defaults` was removed)_

| **Commands** | **Functions** | **Parameters**                         | **Options**                        | **Mechanism**                                                                                 |
|:-------------|:--------------|:---------------------------------------|:-----------------------------------|:----------------------------------------------------------------------------------------------|
| `scripts`    | `start`       | `[NAME[:ID[:PROCESS_ID]]]`, `*`, `all` | `EMPTY (default)`, `--when-loaded` | Start the host if none ⟶ run the script in a thread: `setup()`, then `loop()` every `every` s |
| `scripts`    | `restart`     | `[NAME[:ID[:PROCESS_ID]]]`, `*`, `all` |                                    | `stop` ⟶ load the file again ⟶ `start`                                                        |
| `scripts`    | `stop`        | `[NAME[:ID[:PROCESS_ID]]]`, `*`, `all` |                                    | Ask it to stop ⟶ `teardown()`; a stuck one ends only with the host                            |

| **Commands** | **Functions** | **Parameters**                         | **Outputs**                            | **Mechanism**                          |
|:-------------|:--------------|:---------------------------------------|:---------------------------------------|:---------------------------------------|
| `scripts`    | `status`      | `[NAME[:ID[:PROCESS_ID]]]`, `*`, `all` | `--tree (default)`, `--flat`, `--json` | Ask the host: state, loops, last error |

| **Commands** | **Functions** | **Parameters**             | **Mechanism**                                                       |
|:-------------|:--------------|:---------------------------|:--------------------------------------------------------------------|
| `scripts`    | `add`         | `[FILE_PATH\|FOLDER_PATH]` | Check the file loads ⟶ put it in the list of added scripts of `creative.json` |
| `scripts`    | `remove`      | `[FILE_PATH\|FOLDER_PATH]` | Take it out of the list (stop it first if it runs)                  |
| `scripts`    | `change`      | `[FILE_PATH\|FOLDER_PATH]` | Point the entry at the new file ⟶ `restart` it if it runs           |

| **Commands**      | **Functions** | **Parameters**                        | **Options**                                     | **Mechanism**                                                                    |
|:------------------|:--------------|:--------------------------------------|:------------------------------------------------|:---------------------------------------------------------------------------------|
| `innovate-spells` | `EMPTY`       |                                       |                                                 | Show the spells with their ids, built or secured                                 |
| `innovate-spells` | `build`       | `EMPTY`, `*`, `all`, `[NAME\|ID ...]` | `EMPTY (default)`, `--dry-run`, `--source FILE` | Copy the template rows ⟶ apply the design ⟶ re-encode ⟶ the gate judges the file |
| `innovate-spells` | `secure`      | `EMPTY`                               |                                                 | Gate again ⟶ keep it as `regulation.secured.bin` (game closed)                   |
| `innovate-spells` | `apply`       | `EMPTY`                               | `EMPTY (default)`, `--when-loaded`              | Put the texts and colours into the running game (memory only)                    |

| **Commands** | **Parameters**                              | **Options**                                     | **Mechanism**                                                                                        |
|:-------------|:--------------------------------------------|:------------------------------------------------|:-----------------------------------------------------------------------------------------------------|
| `resurrect`  | `[NAME\|ID\|PATH ...]`, `*`, `all`          | `EMPTY (default)`, `--dry-run`, `--when-loaded` | Check the portal ⟶ turn the boss's event flags OFF ⟶ read back; it returns when its area loads again |

### Data

| **Commands** | **Options**                 | **Mechanism**                                                                 |
|:-------------|-----------------------------|:------------------------------------------------------------------------------|
| `export`     | `EMPTY (default)`, `--live` | Export the data (the single source of truth) into `<TOOLS-DIR>\output\disk.json`; `--live`: again each time it changes |


| **Commands** | **Parameters**                          | **Mechanism**                                                                                                                 |
|:-------------|:----------------------------------------|:------------------------------------------------------------------------------------------------------------------------------|
| `reset`      | `EMPTY`, `*`, `all`, `[NAME\|ID\|PATH]` | Take the game's values now as the new baseline (`runes.delta` = 0, the monitors' history cleared); writes nothing to the game |
| `check`      | `[FILE_PATH]`                           | Decode a `regulation.bin` ⟶ compare its tables with the game's, row by row                                                    |
| `probe`      | `EMPTY`                                 | Find where the game's param tables lie in memory ⟶ check them against the profile's chains (for a new game version)           |

### Flags & Options (every command)

| **Flags & Options**         | **Definition**         | **Working on Commands**                                                         | **Mechanism**                                                                           |
|:----------------------------|:-----------------------|:--------------------------------------------------------------------------------|:----------------------------------------------------------------------------------------|
| `-v`, `--verbose`           | the log, live          | **ALL**                                                                         | shows the log lines themselves instead of the concise view                              |
| `--vault DIR`               | the vault              | **ALL**                                                                         | the vault to use (remembered once given)                                                |
| `--save-dir DIR`            | the save folder        | `run`, `vault`                                                                  | the game's save folder, for several Steam accounts (remembered)                         |
| `--game-dir DIR`            | the game folder        | `run`, `check`, `innovate-spells`                                               | where `eldenring.exe` is (found through Steam otherwise)                                |
| `--offsets FILE`            | the profile            | `read`, `write`, `scripts`, `innovate-spells apply`, `resurrect`, `export`     | the pointer chains of each game version (`offsets.json`; the one in the exe by default) |
| `--spec FILE`               | the creative file      | `run`, `scripts`, `innovate-spells`, `resurrect`                               | the creative file (`creative.json` next to the exe, else the one in the exe)                |
| `--creative-dir DIR`          | the creative files     | `run`, `scripts`, `innovate-spells`                                            | where builds, secured files and the scripts' status are kept (`<vault>\creative`)         |
| `--vault-on`, `--vault-off` | the portal             | `run`                                                                           | open the portal (default) / play without it: nothing is backed up, swapped or written   |
| `--regulation FILE`         | another world          | `run`                                                                           | swaps this `regulation.bin` instead of the one built from `creative.json`                                     |
| `--keep N`                  | snapshots kept         | `run`, `vault prune`                                                            | the newest snapshots kept                                                               |
| `--yes`                     | confirm                | `vault keep`                                                                    | what cannot be undone is done only with it                                              |
| `--hz N`                    | the pace               | `read --live`, `export --live`                                                  | reads per second (1 to 120)                                                             |
| `--version`                 | the version            | `eldendisk`                                                                     | prints the version and ends                                                             |

### Tooling

| **Commands** | **Parameters** | **Mechanism**                                                                                        |
|:-------------|:---------------|:-----------------------------------------------------------------------------------------------------|
| `hash`       | `EMPTY`        | SHA-256 of `eldenring.exe` ⟶ the key of its profile in `offsets.json` (a new game version needs one) |
| `--version`  | `EMPTY`        | The tool's version                                                                                   |

**Exit codes (every command)**

| **Code** | **Meaning**                                                                                          |
|:---------|:-----------------------------------------------------------------------------------------------------|
| `0`      | done (also when there was nothing to do: a boss already alive, a value already set)                  |
| `1`      | an error, or not applied (a wrong name, a value that did not stick, no character in the world)       |
| `2`      | not supported: no profile for this `eldenring.exe`, or the profile lacks the block the command needs |
| `3`      | the anti-cheat is running: the tool refuses to touch the game                                        |
| `4`      | a restore is pending: run `vault restore` first                                                      |
| `5`      | no portal: no session of `run` with the vault ON for this game process (every write)                 |
| `130`    | interrupted (Ctrl+C)                                                                                 |

**Naming (`NAME | ID | PATH`).** Everywhere a thing is named, the same three forms work: the **path** in the document
(`creative.resurrect.great_enemies.12050800`), the **id** (`12050800`, the game's own number) and the **name** in any letter case or a part
of it (`mohg lord`). A name that fits several is refused with the list; a wrong name changes nothing. `*` and `all` mean every one, and
stand alone.

**Addressing a script (`NAME:ID:PROCESS_ID`).** `NAME` is the script's class (`RctColoursFollowTheSpell`), `ID` its number in the host
(1, 2, ...: two scripts may share a class name in different files), `PROCESS_ID` the host's process (all the scripts of a session run in
ONE host process, each in a thread). `RctColoursFollowTheSpell` alone is enough while it is unique. **A limit to know:** Python cannot kill
a thread, so `stop` asks the script to stop (its loop ends, `teardown()` runs); a script stuck inside its own code ends only with the host
process (`scripts stop *`, or the game closing). There is no `kill` for one script.

## The creative file (`creative.json`)

What you edit to shape the parallel world. `run` reads it at every session (`--spec FILE`, else next to the exe, else the copy in the
exe); one section per creative feature, each optional:

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

| **Section**                  | **`run` does with it**                                                                            |
|:-----------------------------|:--------------------------------------------------------------------------------------------------|
| `innovate_spells`            | builds `regulation.bin` when the spells changed (or swaps the secured one), then `apply` in the world |
| `scripts.added`              | starts these scripts with the defaults, in the world (`scripts add / remove / change` edit the list) |
| `resurrect.great_enemies`    | `activate` in the world: `"all"` / `"*"`, or names and ids                                          |

A wrong name or value in `creative.json` is an error that names its place in the file; nothing is built or started from a file with an
error.

## Where things live

```text
%LOCALAPPDATA%\EldenDisk\   (<TOOLS-DIR>)        everything the tool keeps (never next to the exe: a new build cannot delete it)
 ├─ vault\ 
 │   ├─ <time>\                                 a snapshot: ER0000.sl2, ER0000.sl2.bak, ER0000.err, ER0000.err.bak, steam_autocloud.vdf,
 │   │   │                                       their manifest (hashes), bin\regulation.bin (the game's own), contaminated\ (the
 │   │   │                                       session's changed save, archived at the restore)
 │   ├─ session.json                            the session record: open while the portal is open; a record left open = a restore pending
 │   ├─ creative\                               the creative files: builds, the secured regulation.bin, the scripts' status
 │   ├─ memory-cache.json                       where this game process holds what was written (texts, colours): no second search
 │   └─ eldendisk.log                           the log of every command
 └─ output\disk.json                           what `export` writes
<exe folder>\                                   eldendisk.exe; offsets.json, names.json, creative.json when you put them next to it
                                                (they win over the copies in the exe)
```

`offsets.json` holds one **profile** per `eldenring.exe` (by its SHA-256, see `hash`): the pointer chains and the blocks each feature needs
(`text`, `equipment`, `event_flags`, ...). `names.json` names the buffs and the animations the game gives no readable name for (`311100` "Gold Scarab", `TALISMANS`;
`26030000` "Attacking (R1)", `MANNER`). It belongs to the reader and lives in its package, `code/eldendisk/reader/names.json`
(always in the exe; one next to the exe still wins, so names can be added without a new build). The buffs of the spells in
`creative.json` are named by the build, not by this file.

## Safety

- **Offline only.** The game is launched offline; with the anti-cheat running the tool refuses (exit `3`).
- **Steam Cloud** may sync the save when the game exits: `run` says so when Steam is running (use Steam's offline mode).
- **The portal checks itself.** Every write checks that the session record names this very game process (pid, start time, exe hash);
  a record left open (the game killed, a full disk) blocks the next `run` until `vault restore`.
- **The game's files are never edited.** Only `regulation.bin` is swapped, and the game's own copy is checked against the known original
  on every path; a modified one is refused.

## The single source of truth

`export` writes it as `<TOOLS-DIR>\output\disk.json`; `tools.read()` gives it to a script; every name above is a path in it.

```json
{
  "systems": {
    "profile": { "sha256": "1a3547101327f65d0c76da2f9190ac0aa66871ea42bae2aecc61e11a8b597891", "game": "eldenring.exe", "version": "1.17.1" },
    "features": { "buffs_supported": true, "animations_supported": true, "creative_supported": true },
    "status": {
      "pid": 46224, "tool_state": "IDLE", "anti_cheat_state": "DISABLED_OFFLINE", "game_connected": true,
      "ignored": { "buffs": 11, "animations": 0 }
    },
    "session": { "mode": "creative", "read_only": false, "creative": true }
  },
  "character": {
    "level": 386,
    "vitals": {
      "hit_point": { "current": 1914, "maximum": 1914, "base": 2015 },
      "focus_point": { "current": 350, "maximum": 350, "base": 350 },
      "stamina": { "current": 178, "maximum": 178, "base": 158 }
    },
    "runes": { "total": 55214603, "baseline": 55214603, "delta": 0 },
    "attributes": { "vigor": 80, "mind": 60, "endurance": 60, "strength": 90, "dexterity": 90, "intelligence": 15, "faith": 60, "arcane": 10 },
    "equipment": { "magic": { "selected": { "slot": 1, "id": 2230000 }, "slots": { "1": 2230000, "2": 6420 } } },
    "buffs": {
      "311100": { "name": "Gold Scarab", "categories": "TALISMANS", "abilities": "Permanently increases Runes gained by 20% while equipped." }
    },
    "animations": {
      "26030000": { "name": "Attacking (R1)", "categories": "MANNER" }
    }
  },
  "params": {
    "effects": {
      "1621000": { "name": "Black Flame", "effectEndurance": 2.0, "motionInterval": 0.1, "changeHpRate": 0.1, "changeHpPoint": 1, "atkOccurrenceSpEffectId": -1, "vfxId": 9010 },
      "1623000": { "name": "Scouring Black Flame", "effectEndurance": 2.0, "motionInterval": 0.1, "changeHpRate": 0.1, "changeHpPoint": 1, "atkOccurrenceSpEffectId": -1, "vfxId": 9010 },
      "1625000": { "name": "Black Flame Ritual", "effectEndurance": 2.0, "motionInterval": 0.1, "changeHpRate": 0.1, "changeHpPoint": 1, "atkOccurrenceSpEffectId": -1, "vfxId": 9010 },
      "1626001": { "name": "Black Flame Blade", "effectEndurance": 2.0, "motionInterval": 0.1, "changeHpRate": 0.1, "changeHpPoint": 1, "atkOccurrenceSpEffectId": -1, "vfxId": 9010 }
    }
  },
  "creative": {
    "scripts": {
      "host": { "process_id": 26528, "state": "running", "started": "2026-10-13 21:49:03", "scripts": 1 },
      "defaults": {
        "RctColoursFollowTheSpell": {
          "id": 1,
          "file": "rct_colours_follow_the_spell.py",
          "state": "live",
          "every": 0.2,
          "loops": 10243,
          "slow": false,
          "last_error": null
        }
      },
      "added": {}
    },
    "innovate_spells": {
      "2230000": {
        "id": "reverse_cursed_technique",
        "slot": 1,
        "rows": {
          "goods": 2230000,
          "magic": 2230000,
          "sp_effect": [21951000, 21951001],
          "bullet": [500000000, 500000001],
          "atk": [710000000, 710000001],
          "shop": 100508
        },
        "design": {
          "kind": "projectile",
          "from": 6421,
          "requires": {
            "status": { "intelligence": 0, "faith": 60, "arcane": 10 },
            "cost": { "focus_point": 120 }
          },
          "locations": {
            "kale": { "price": 34590, "stock": 1 }
          },
          "customs": {
            "basic": {
              "SpEffect.1642100.effectEndurance": 20.0,
              "SpEffect.1642100.motionInterval": 0.5,
              "SpEffect.1642100.changeHpPoint": -45,
              "SpEffect.1642100.changeMpPoint": -15,
              "SpEffect.1642100.staminaRecoverChangeSpeed": 100,
              "SpEffect.1642100.vfxId": -1,
              "Magic.6421.refType": 32,
              "Magic.6421.castSfxId": 524400,
              "Magic.6421.fireSfxId": 524401,
              "Bullet.10642100.sfxId_Bullet": -1,
              "Goods.6421.iconId": 6806
            },
            "advanced": {
              "texts": {
                "goods_name": "Reverse Cursed Technique",
                "goods_info": "An anomalous art left behind by an Unknown Sorcerer from another reality. Forces the concept of ruin to consume itself, commanding shattered flesh to remember its whole and unbroken state.",
                "goods_caption": "The nature of a curse is to erode, corrupt, and destroy. (...)"
              },
              "colors": {
                "Magic.6421.castSfxId": { "main": "#90D5FF", "accent": "#FF909E" },
                "SpEffect.1642100": "#90D5FF"
              }
            }
          }
        }
      }
    },
    "resurrect": {
      "great_enemies": {
        "12050800": {
          "name": "Mohg, Lord of Blood",
          "place": "Mohgwyn Palace",
          "grace": "Dynasty Mausoleum Midpoint",
          "runes": 420000,
          "drop": ["Remembrance of the Blood Lord", "Mohg's Great Rune"],
          "story": true,
          "dlc": false,
          "defeated": true
        },
        "10000850": {
          "name": "Margit, the Fell Omen",
          "place": "Stormhill",
          "grace": "Castleward Tunnel",
          "runes": 12000,
          "drop": ["Talisman Pouch"],
          "story": true,
          "dlc": false,
          "defeated": true
        }
      }
    }
  }
}
```

### `creative.scripts`

- `host`: the one process that runs the scripts of the session: its process id (the `PROCESS_ID` of a script's address), `running` /
  `stopped`, when it started, how many scripts it holds. `null` when no host runs (no session, or no script).
- `defaults`: the scripts the exe carries; `added`: the scripts added after the build. Each is keyed by its `NAME` (the class), with:
  - `id`: its number in the host (the `ID` of its address);
  - `file`: the file it was loaded from;
  - `state`: `loaded`, `setup`, `live`, `waiting` (no character in the world), `stopped`, `dead` (an exception), `failed` (the file
    could not be loaded), `off` (`enabled = False`), `stuck` (a loop that has not returned for 10 s);
  - `every`, `loops`, `slow` (a loop longer than its pace was seen), `last_error` (the last line of the traceback, or `null`).
- Writable: `state` = `"stopped"` (ask it to stop) or `"live"` (start it again, `setup()` first): the same as
  `scripts stop|start NAME`.

### The scripts' interface (`edstdlib`)

```python
from edstdlib import *

class BossRush(Interface):
    every = 1.0                                                   # seconds between two loop()

    def loop(self):
        x = tools.read()                                          # the single source of truth, as an object
        for boss in x.creative.resurrect.great_enemies.values():   # the defeated ones
            if boss.name.startswith("Mohg"):
                boss.defeated = False                             # bring him back
        tools.write(x)                                            # writes only what changed
```

| **Name**                 | **Does**                                                                                    |
|:-------------------------|:--------------------------------------------------------------------------------------------|
| `Interface`              | the base of a script: `setup()` once, `loop()` every `every` s, `teardown()` at the end; `enabled = False` keeps it off |
| `tools.read()`           | the single source of truth as an object (`x.character.runes.total`, `x.params.effects[1621000]`) |
| `tools.write(x)`         | writes what changed in it, through the portal, as `write` does; `True` when everything stuck |
| `tools.log(text, level)` | a line in the log and on the `run` console, under the script's name                        |
| `tools.dead()`           | ends this script now                                                                        |

### `creative.resurrect.great_enemies` (defeated only)

- **Only the great enemies that are defeated now** are in the document: they are the ones that can be brought back, and the list stays
  short (43 on the author's character, not 212). `read creative.resurrect.great_enemies` shows them; a boss that is alive is not in it.
- Each is keyed by its id, with what the table knows (`name`, `place`, the nearest `grace`, `runes`, `drop`, `story`, `dlc`) and
  `defeated: true`.
- Writable: `defeated` = `false` brings it back (the same as `--activate`); it then leaves the list until it is beaten again. `true` is
  refused: only the game marks a boss defeated.
- When the game holds no save yet (title screen), the block is `{}`.

## Open questions

1. `stop` of one script and `restart`: they need a way to reach the host from another terminal (a small file the host watches in the
   vault, or a local pipe). The file is the simpler one and needs no open port.
2. Should `creative.innovate_spells.<id>.design` also be writable as a whole (a new build from the running session), or stay the
   values only (each field written to the game's rows)?

## Remarks

What this document changes from the tool as it was (1.7.2 and the first build of 1.8.0), and why.

| **Before**                                                      | **After**                                                     | **Why**                                                                                                     |
|:----------------------------------------------------------------|:--------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------|
| `extension ...` in front of the creative commands              | no prefix: `scripts`, `innovate-spells`, `resurrect`          | one level less to type; `extension` became `design`, then `creative` (below)        |
| `design` (the overview of `design.json`)                          | removed                                                       | `read creative` shows that part of the document; `creative.json` is described once (The design file)  |
| `external-scripts`                                              | `scripts`                                                     | shorter; the scripts are the only external thing                                                            |
| `external-scripts --run`, `--scripts-dir PATH`                  | `scripts start / restart / stop / status`, `add / remove / change` | control one script while the game runs; the added scripts are kept in `creative.json`, not typed every run |
| `external-scripts defaults`                                     | removed                                                       | `scripts` lists the defaults and the added ones together                                                   |
| `innovate-items spells`                                         | `innovate-spells`                                             | one word: spells are the one kind of item so far                                                            |
| `innovate-items spells --add all\|PATH ...`                     | `innovate-spells build [all \| NAME \| ID ...]`               | a function word, like `vault status`                                                                        |
| `innovate-items spells --secure`                                | `innovate-spells secure`                                      | the same                                                                                                    |
| `write --text`, `write --flame-color`                           | `innovate-spells apply`                                       | they put the spells' design into the game: creative work, not core                                            |
| `resurrect great-enemies --activate NAME`                       | `resurrect NAME \| ID \| PATH`                                | one word: great enemies are the one kind so far                                                             |
| `resurrect great-enemies --list` (and its filters)              | removed                                                       | `creative.resurrect.great_enemies` in the document holds **only the defeated bosses**: `read creative.resurrect.great_enemies.*` shows their ids, and `resurrect 12050800` brings one back. The list a person needs is the one the document already gives |
| `creative.resurrect.great_enemies`: all 212, `defeated` true / false / null | the defeated ones only                           | the bosses that can be brought back; short (43 on the author's character); a boss leaves the set when it is brought back and comes back when it is beaten |
| a spell's node: `id`, `slot`, `rows`, `kind`, `from`, ... side by side | `id`, `slot`, `rows` apart from `design: {...}`        | the build's facts apart from what you designed                                                             |
| `read --export`, `disk-state.json` next to the tool             | `export`, `<TOOLS-DIR>\output\disk.json`                      | the document to a file is a job of its own (Data)                                                           |
| `read --param-check FILE`                                       | `check FILE`                                                  | Data, not reading the game                                                                                  |
| `read --probe-params`                                           | `probe`                                                       | the same                                                                                                    |
| `read --param Table.ID`                                         | `read params.Table.ID`                                        | a path in the document like every other name                                                               |
| `read --live-buffs`, `read --live-animations`                   | `read monitor`, `monitor-buffs`, `monitor-animations`         | function words; `monitor` shows both                                                                        |
| `write --set NAME=VALUE`                                        | `write NAME=VALUE`                                            | `--set` said nothing more than `write` does                                                                 |
| `write --reset NAME`                                            | `write NAME=default`                                          | one form for every write                                                                                    |
| `write --refill LIST`                                           | removed                                                       | `write hp=<maximum>` does the same                                                                          |
| (none)                                                          | `reset`                                                       | the read baselines (`runes.delta`, the monitors) start again from now; nothing written to the game         |
| (none)                                                          | `scripts status`, `creative.scripts` in the document   | how each script is doing, from the host itself, as data                                                    |
| `run` also took `--scripts-dir`                                 | `run` starts what `creative.json` names                         | everything the session does is in `creative.json`                                                                |
| `chr_state_ids.json` next to `offsets.json` (`code/`)            | `names.json` in the reader's package (`code/eldendisk/reader/`) | what it is in one word (the names of the buffs and the animations); it belongs to `read`, the one that uses it |
| the group `design`: package `eldendisk/design/`, `design.json`, the block `design`, `<vault>\design`, `--design-dir` | `creative`: `eldendisk/creative/`, `creative.json`, the block `creative`, `<vault>\creative`, `--creative-dir` | `design` now means one thing only, the values you designed (`creative.innovate_spells.<id>.design`); `creative`, like Minecraft's creative mode, says what the group is: the things that exist only in the parallel world, played with freely |
| `design.innovate_items.spells`                                 | `creative.innovate_spells`                                    | the same name as the command `innovate-spells`; one level less                                             |
| `design.external_scripts`                                      | `creative.scripts`                                            | the same name as the command `scripts`                                                                     |
| `systems.session.mode`: `"sandbox"`                            | `"creative"`                                                  | the same word for the same thing                                                                            |

The names of the document follow the commands: `creative.innovate_spells` is `innovate-spells`, `creative.scripts` is `scripts`,
`creative.resurrect` is `resurrect` (`great_enemies` stays under it as its first kind).

> [!NOTE]
> **Version:** `1.8.0`  
> **Status:** IMPLEMENTED (unit tests: 1,700+). Part 1 (`resurrect`) tried in the real game on 2026-10-13 (the checks of spec section 12);
> Part 2 (the commands and the names) not yet tried in the game.  
> **Last Updated:** _2026-10-14_

**Summary:** **Great enemies again, and one way to say everything.** Part 1: a boss you have beaten comes back for the session (`resurrect`):
its event flags are turned off in the game's memory, the vault puts the save back. Part 2, the big refactor: Elden-Disk is defined as the
**Elden Ring Memory Disk I/O Tools**, a **portal** into a parallel world of the game; every command reads the same way (`read NAME`,
`write NAME=VALUE`, `scripts start NAME`, `innovate-spells build NAME`, `resurrect NAME`), every value is a path in **one document**, and
the group of things that exist only in the parallel world is called `creative` (the package, `creative.json`, the block, the folder).

_(baseline: **[changes-version-1.7.2.md](changes-version-1.7.2.md)**; design: **[elden-disk-spec-v1.8.0.md](../specs/elden-disk-spec-v1.8.0.md)**; draft:
`docs/experiments/extensional/resurrect-unit/great-enemies/redefine-and-restructuring.md`)_

---

## Wahy

### Part 1: `resurrect` (2026-10-13)

| # | Change | Where |
|:-:|:---|:---|
| 1 | **The event flags of the game** (CSEventFlagMan, profile block `event_flags`): read a flag by its id through the game's tree of flag blocks; turn a flag OFF, never ON, only the flags of the table. | `game/eventflags.py`, `writer/eventflags.py`, `offsets.json` |
| 2 | **The great-enemies table**: 212 bosses (every enemy under the big health bar, the DLC included) with their flags (the defeat, the Remembrance's play-log trigger, the drops, the intro), place, nearest grace, runes, drop; made from the game's own files by a tool. | `creative/resurrect/great_enemies/`, `tools/gen_great_enemies.py` |
| 3 | **`resurrect`**: a defeated boss alive again, in memory only, inside the portal; it appears once its area loads again. | `commands/resurrect.py` |

### Part 2: Redefine and restructure (2026-10-14)

| # | Change | Where |
|:-:|:---|:---|
| 4 | **`design` is `creative`.** The package `eldendisk/creative/` (`innovate_spells`, `scripts`, `resurrect`), `creative.json`, the document's block `creative`, `<vault>\creative`, `--creative-dir`, the log tag `creative`, `systems.session.mode` `"creative"`, `features.creative_supported`. An older vault's folder is renamed once (`design` or `extension` → `creative`, `innovate-items\spells` → `innovate-spells`). | `eldendisk/creative/`, `commands/innovate.py`, `reader/export.py`, `logbook.py` |
| 5 | **The command line** (spec Part 2, "Commands"): `read [NAME ...]`, `read monitor \| monitor-buffs \| monitor-animations`, `write NAME=VALUE \| NAME=default`, `write` alone (the names and their ranges), `scripts ...`, `innovate-spells [build \| secure \| apply]`, `resurrect NAME ...`, `export`, `reset`, `check`, `probe`. Gone: `design`, `innovate-items`, `external-scripts`, `resurrect great-enemies`, `read --query / --export / --param / --param-check / --probe-params / --live-buffs / --live-animations`, `write --set / --reset / --refill / --text / --flame-color`, `run --scripts-dir`. | `__main__.py`, `commands/` |
| 6 | **The scripts controlled from another terminal.** `scripts start \| restart \| stop \| status [NAME[:ID[:PROCESS_ID]]]`: a request file in `<vault>\creative\scripts.requests\`, read by the host once a second, answered in `scripts.status.json`; no port. Each script has an id; `stop *` ends the host. `scripts add \| remove \| change PATH` keep `scripts.added` in `creative.json` (a running host loads them at once). | `creative/scripts/host.py`, `commands/scripts.py` |
| 7 | **The document.** `creative.scripts` (the host and every script: id, file, state, every, loops, slow, last_error), `creative.innovate_spells.<goods id>` (`id`, `slot`, `rows` apart from `design`), `creative.resurrect.great_enemies` (**the defeated ones only**; `defeated=false` brings one back). | `creative/scripts/backend.py`, `creative/innovate_spells/live.py`, `reader/view.py`, `disk.schema.json` |
| 8 | **`creative.json`** one level shorter (`innovate_spells`, was `innovate_items.spells`) with the sections `scripts.added` and `resurrect.great_enemies.activate`. | `code/creative.json`, `innovate_spells/spec.py`, `spells.schema.json` |
| 9 | **`innovate-spells apply`**: the texts and the colours in one step (`run` starts it); `build` takes a spell's name or its goods id. | `commands/innovate.py`, `commands/write.py` |
| 10 | **`reset`**: the read baselines (`runes.delta` = 0, the monitors' history) in `<TOOLS-DIR>\baselines.json`, taken by every reader of the same game. | `reader/baselines.py`, `commands/read.py`, `reader/ledger.py` |
| 11 | **`export`** writes `<TOOLS-DIR>\output\disk.json` (was `disk-state.json`). | `reader/export.py`, `commands/read.py` |
| 12 | **`names.json`** (was `chr_state_ids.json` next to `offsets.json`): the reader's, `code/eldendisk/reader/names.json`, always in the exe; one next to the exe wins. `--names FILE`. | `reader/names.json`, `commands/read.py`, `tools/dev_pipeline.py` |
| 13 | **`run`** starts `innovate-spells apply`, `resurrect` and `scripts start *` once a character is in the world; the scripts after the other two. | `commands/run.py` |
| 14 | **The build**: `names.json` and the great-enemies table always in the exe; the default scripts in its `scripts\`. | `tools/dev_pipeline.py` |
| 15 | **Tests**: every command test moved to the new command line; new `test_baselines.py`, the host's requests, `scripts add / remove / change`, `write` of a script's state, `read` words. | `tests/` |
| 16 | **Docs**: README, cli-commands (both), README-exe written again from spec Part 2; the handbooks' commands; spec 1.8.0 (status, implementation notes); this file. Version `1.8.0`. | `README.md`, `docs/` |

### Part 3: Optimization (2026-10-15)

| # | Change | Where |
|:-:|:---|:---|
| 17 | **The first decode of a build** 1.64 s → 1.07 s (a build 5.5 s → 4.9 s): compression.zstd gives the bytes, our decoder follows only its state; the gate keeps both decoders. | `innovate_spells/zstd.py` (`block_state`), `reblock.py`, `build.py` (`fast_body`) |
| 18 | **The CLI loads only the command that runs**: 0.27 s → 0.17 s per command (`python -m`); the exe builds collect the whole package. | `__main__.py`, `tools/dev_pipeline.py` |
| 19 | **The exe's hash remembered** (`<TOOLS-DIR>\exe-sha256.json`, by path, size and time): every attach hashed 87 MB (0.08 s, 1.7 s cold); `run` still hashes afresh. | `game/processes.py`, `game/attach.py`, `commands/run.py` |
| 20 | **`innovate-spells apply` in one attach**, the colours painted during the text's 3 s watch (the log of 2026-10-14: 3 s idle and a second attach of 1.4 s). | `commands/write.py` (`cmd_apply_both`), `commands/innovate.py` |
| 21 | **Tests** for the state-only decode, the hash cache, the lazy imports, the combined apply; spec 1.8.0 Part 3. | `tests/`, `docs/` |

### Part 4: Every param table in the disk (2026-10-15)

| # | Change | Where |
|:-:|:---|:---|
| 22 | **Every table of the game** (194 in 1.17.1, 170,966 rows) is `params.<Table>.<id>.<field>`, by the game's own name of the table in any letter case; the short names still work. The layouts from Paramdex, generated against the game's `regulation.bin`: 188 tables decode, 6 have no def that fits yet. | `game/paramlayouts.py`, `game/paramnames.py`, `tools/gen_paramdefs.py` |
| 23 | **Read when named.** The document's `params` is `{Table: {"rows": n}}`; `read params.NpcParam` (every row), `params.NpcParam.10000000[.hp]`, `params.NpcParam.*.hp` read from the game then. A script's table reads a row when it is touched. | `game/paramtables.py`, `reader/sampler.py`, `commands/read.py`, `creative/scripts/backend.py`, `disk.schema.json` |
| 24 | **`params.effects` is gone**, folded into `params.SpEffectParam.<id>`; a name under it says where its rows are. Every table is written through the same edits (type and bit width checked; an id field gets a note). | `writer/writer.py`, `writer/paramedit.py` |
| 25 | **`params.repository`**: the list the game keeps every table in, walked once; each slot named by its param type, rows, ids, the digest of its rows or the name next to it, else left out with the reason. `probe` prints every slot. | `game/profile.py`, `game/paramtables.py`, `game/probe.py`, `offsets.json` |
| 26 | **Tests** of the walk (`test_param_walk.py`); the `params.effects` tests moved to `params.SpEffectParam`; docs and spec 1.8.0 Part 4. | `tests/`, `docs/` |

## Not done (open)

- The reads and scans inside the game, measured from a session's logs (spec 1.8.0 Part 3). Decided not to do: a one-folder exe, and the
  decoded game file's state kept between builds.
- Part 2 in the real game (the new command line, the scripts' control from another terminal, `reset`).
- Part 4 in the real game: the walk of `params.repository` (`probe`).
- `creative.innovate_spells.<id>.design` written as a whole (a new build from the running session): the values only for now.

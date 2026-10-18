# Elden-Disk 1.8.5: the vault and a full disk; a lighter read for the scripts

Asked by the author (2026-10-18): (1) the vault must not be caught by a full disk; (3) the read of the game the scripts share
costs less. Two parts, each closed by a test in the game.

# Part 1: the vault and a full disk

## A1. What happened (2026-10-18, 05:00)

The log of that session:

- 04:46:27 preflight passed (the vault's drive had 3 x the save folder free, `SPACE_FACTOR`), the snapshot was taken (5 files).
- 05:00:07 the game exited; the restore began.
- 05:00:07.9 the session's save (`ER0000.err`, `.err.bak`, `.sl2`, `.sl2.bak`, `steam_autocloud.vdf`) was **copied** to
  `<snapshot>/contaminated` (about 57 MB: the two `.sl2` are about 28 MB each).
- 05:00:08.8 `regulation.bin` was put back (the game's folder, drive D:).
- 05:00:08.8 `restore ER0000.sl2: [WinError 112] There is not enough space on the disk`: RESTORE_PENDING.

The vault (`%LOCALAPPDATA%\EldenDisk\vault`) and the save folder (`%APPDATA%\EldenRing`) are both on C:. The space C: had at the
start was taken during the 14 minutes of play (by what, the log cannot say), and the copy to `contaminated` took 57 MB more, just
before the restore needed its own.

What the save folder held after it (read from the code, not seen): each file is restored to a temporary file and then put in place in
one step (`os.replace`), so no file was half written: `ER0000.err` and `.err.bak` were the snapshot's again, `ER0000.sl2` and the files
after it still the session's, whole. The failed copy left its temporary file (`ER0000.sl2.eldendisk-tmp`, partly written) in the save
folder; the next restore deletes it (a file the snapshot does not have). The restore the author ran later put everything back.

## A2. Changes

1. **The archive takes no space on the same drive.** `contaminated` is made of hard links to the session's files (NTFS, same
   drive), not copies: the restore then puts new files in their place, and the archive keeps the old ones. On another drive, or when
   a link is refused, that file is copied as before.
2. **The restore checks the space before it touches anything.** It needs, on the save folder's drive, the size of each file it will
   write (the ones that differ from the snapshot), plus the archive's copies when they cannot be links, plus `RESTORE_MARGIN`. Not
   enough: nothing is archived, nothing restored (only `regulation.bin`, on its own drive, is put back, as now), RESTORE_PENDING, and
   the log says how much to free and where: `restore needs 61 MiB free on C:\, only 12 MiB available: free 49 MiB, then run ...`.
3. **A failed copy leaves nothing behind.** Its temporary file is deleted at once.
4. **The space is watched while the game runs.** Every `SPACE_EVERY` seconds the host compares the free space of the vault's drive
   and the save folder's drive with what the restore will need (the save folder's size + `RESTORE_MARGIN`); short: one warning, while
   the game is still open: `C:\ has 12 MiB free; the restore after the game needs 120 MiB: free some space before you quit the game`;
   said again only after the space came back and ran short again.

`preflight` stays as it is (3 x the save folder on the vault's drive). `__version__` 1.8.5.

Where: `vault/vault.py` (`archive_contaminated` links, `restore_space`, `space_short`, `RESTORE_MARGIN`, the temporary file of a failed
copy deleted), `vault/recover.py` (the check before the archive and the restore), `host/host.py` (`Hooks.space_every`,
`Hooks.disk_free`, `Session._watch_space`, every poll while the game runs; the files through the vault, as every other step).

## A3. The author's choices (defaults ⭐; the author took every default, 2026-10-18)

- D1 the archive: ⭐ hard links on the same drive (no space) / copies as before.
- D2 not enough space for the restore: ⭐ stop before anything is touched and say how much to free / restore without the archive.
- D3 `SPACE_EVERY`: ⭐ 60 s.
- D4 `RESTORE_MARGIN`: ⭐ 64 MiB.

## A4. Tests

`test_vault*.py`: the archive is links on one drive (the same file: `os.path.samefile`), a copy when `os.link` fails; the space is
checked first (a disk too small: nothing archived, nothing restored, the message with the numbers); a copy that fails deletes its
temporary file; the host warns once when short, again only after the space came back.

# Part 2: a lighter read for the scripts

## B1. What is known

After 1.8.4 part 8 a script's `tools.read()` costs almost nothing; what is left is the backend's read of the game, built again at most
every `SHARE` (0.05 s) when a script reads: up to 20 a second with the three default scripts. Each build:

- `sampler.sample()`: the character (a chain of pointers, vitals, attributes, buffs, animations, equipment, lock-on); the inventory at
  most once a second.
- `creative.block()`: the scripts' status file (read again only when it changed), **every innovate spell's design with the values of
  its fields read from the game** (a row of the game for each table its `customs.basic` names), the colours from the memory cache,
  and **every great enemy's defeated flag** (`resurrect`).
- the index of the game's tables (kept for the game process) and a `LazyRows` per table.

The three default scripts read `character.lock_on`, `character.equipment` and `character.level` only: the spells' values and the great
enemies are read for nothing. How long each part takes cannot be measured here: it is the game's memory (`ReadProcessMemory`).

## B2. Step 1: measure in the game

The backend times each part of each build and writes one line a minute (debug, in the log with `-v`):

`scripts: 523 reads of the game in the last minute, 3.1 ms each (character 0.9, scripts 0.0, spells 1.4, enemies 0.7, tables 0.1),
the slowest 11.2 ms`

The author plays a few minutes as always and sends the log. Where: `creative/scripts/backend.py` (`ReadTimes`, `READ_PARTS`,
`TIMES_EVERY`; `CreativeLive.block(times)`; `LiveBackend.document()` times the character (the sample and the document), the three
creative parts and the tables).

## B3. The numbers (2026-10-18, 06:52-07:04, 11 minutes of play)

| Minute | Reads | ms each | character | scripts | spells | enemies | tables | slowest |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 613 | 15.1 | 2.1 | 0.3 | 3.7 | 3.6 | 5.4 | 1030.5 (the first: the tables found) |
| 2 | 567 | 13.7 | 0.7 | 0.2 | 3.7 | 3.6 | 5.4 | 51.7 |
| 3-10 | 552-607 | 12.0-12.7 | 0.4-0.7 | 0.2-0.3 | 3.3-3.4 | 3.2-3.4 | 4.8-5.0 | 24.0-41.0 |

About 9.5 reads a second x 12.4 ms = **118 ms a second, 12 % of one core**, of which the tables (the chain of each of the ~190 tables
followed again for its row count), the spells and the great enemies are 11.6 ms; the scripts use none of them in their loops.

## B4. Step 2: a part built when a script touches it

`LazyPart` (`backend.py`): `params` (the whole set of tables), `creative.innovate_spells` and `creative.resurrect` are in the document
as parts built at the first touch (edstdlib's Node takes the value then), once for that document: the scripts that touch it within
`SHARE` get the same; under the backend's read lock, as the document's own read. A part not touched is never built. The keys are there
as before (`params` when the game version has tables, `innovate_spells` when there is a build, `resurrect` when the game version has
event flags; a part that turns out empty is `None` / `{}`). Its time counts in the minute's line (`ReadTimes.add_part`). The command
line's `read` / `export` do not use this document (`CreativeLive.block()` stays whole).

Expected (from the numbers): about 0.8 ms a read (character + scripts), **about 8 ms a second, 15 x less**; a script that changes the
spell's values on a lock-on change or a spell selected builds the part it touches then.

## B5. Found in the same log: the teardowns wrote into a game going away

07:04:38 the game closed; the host stopped the scripts; `DismantleFollowsTheLockOn`'s `teardown()` put the build's values back and
five writes "did not stick" (warnings): the game was ending. Now the host tells the backend (`LiveBackend.game_closed`) before it stops
the scripts, and every write after it is not made and not refused (one debug line: `the game closed: the scripts' last writes are not
made (its memory is going away)`). A script stopped while the game runs (`scripts stop`, restart) still puts its values back.

## B6. Tests

`test_param_walk.py`: the minute's line (counts, each part's mean, the slowest; nothing before a minute); the tables built at the first
touch, once for two snapshots, not at all for the character only; the spells and the great enemies the same, a script sees them as
before; a game version without tables has no `params`; after the game closed a write is neither made nor refused, said once.
`test_scripts.py`: the host marks the backend when the game closes.

## B7. In the game (2026-10-18, 07:27-07:38)

| | Before (06:52) | After (07:27) |
|---|---:|---:|
| Reads a second | about 9.5 | about 9.8 |
| ms a read (minutes 2-10) | 12.0-13.7 | **1.0-1.2** |
| character / scripts / spells / enemies / tables | 0.6 / 0.2 / 3.3 / 3.3 / 4.9 | 0.7 / 0.3 / 0.0-0.1 / 0.0 / 0.0 |
| CPU a second | about 118 ms (12 % of a core) | **about 11 ms (1 %)**, 11 x less |
| the slowest read (after the first minute) | 24-52 ms | 4.4-18.5 ms |

`scripts` 0.2 -> 0.3 ms: it now also asks whether there is a build and great enemies (the parts' keys). The scripts did the same: 19
lock-on changes, the colours following the spell, no warning, no error. At the close: one debug line (`the game closed: the scripts'
last writes are not made`), no "did not stick". Part 1 in the same session: archived (links) and restored byte-identical.

# Part 3: Dismantle follows the lock-on only while it is in hand (2026-10-18)

## C1. Asked by the author

The log of 07:34: every lock-on and lock-off wrote Dismantle's 22 fields (about 7 ms each time, 07:34:39.037-.044), with another spell
in hand too. The author asked whether the script should check the spell selected first, as the colour scripts do, or whether reading
the equipment all the time costs more.

## C2. Answer and change

The equipment costs nothing more: `character.equipment` is in every read of the character already (the 0.7 ms of B7, one read of 116
bytes), and the two colour scripts read it every 0.2 s. So `DismantleFollowsTheLockOn.follow()` now returns at once while another spell
is selected (`character.equipment.magic.selected.id` is not Dismantle's Magic id): a lock-on then writes nothing. Selecting Dismantle
writes the mode of the lock-on at that moment (within `every`, 0.1 s, before a cast can start). While another spell is in hand the
game keeps the mode written last (unused: no other spell reads these rows). Without `character.equipment` (unreadable for a moment, or a
game version without it): as before, the lock-on alone.

## C3. Tests

`test_lock_on.py`: with another spell selected a lock-on / lock-off writes nothing; Dismantle selected while locked on writes the locked
mode; another spell again keeps it; Dismantle again, not locked: the fan; no equipment: follows the lock-on as before. The other tests
have Dismantle selected.

## C4. Closed (2026-10-18)

Part 3 passed in the game. **1.8.5 is closed**: parts 1-3.

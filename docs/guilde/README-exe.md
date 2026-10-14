# Elden-Disk {version} (`eldendisk.exe`)

**Elden-Disk is the Elden Ring Memory Disk I/O Tools** for **Elden Ring 1.17.1** (Windows 10/11, 64-bit): CLI commands in a console. You
open a terminal, run a command, it does its work and ends. This file sits next to `eldendisk.exe`; the full command reference follows the
quick start.

**The portal.** `run` opens a portal into a parallel world of the game: there you can play with it in creative ways (new spells you design,
great enemies brought back, your own scripts changing the game while it runs). When the game closes, the vault puts your save files and
the game's own `regulation.bin` back, byte for byte: **nothing you did inside comes back with you.**

## In this folder

| **File** | **What it is** |
|:---|:---|
| `eldendisk.exe` | the tool; run it from a terminal (`.\eldendisk.exe <command>`) |
| `README.md` | this file (written when the exe is built) |
| `offsets.json`, `names.json`, `creative.json` | only when you put them here: they win over the copies in the exe (the profile of each game version, the names of the buffs and the animations, what you create) |

Nothing is written next to the exe: everything the tool keeps lives in `%LOCALAPPDATA%\EldenDisk` (`<TOOLS-DIR>`): the vault in `vault\`
(snapshots, the session record, `eldendisk.log`, the creative files in `vault\creative\`) and what `export` writes in `output\`. So the exe
can be anywhere and replacing it loses nothing. `--save-dir` and `--vault` are remembered in the Registry (`HKCU\Software\EldenDisk`).

## Quick start

1. **Copy your save folder by hand first** (`%APPDATA%\EldenRing\<SteamID64>`). A manual copy is the one backup the tool cannot get wrong.
2. Terminal 0: `.\eldendisk.exe run`. It backs the save files up, swaps in the `regulation.bin` built from `creative.json`, starts the game
   **offline** and, when the game exits, puts everything back byte for byte. Leave it open. (Several Steam accounts: add
   `--save-dir "<folder>"` once.)
3. Terminal 1, once a character is loaded: `.\eldendisk.exe read` (the whole document once), `read runes hp attrs.*`, `read hp --live`,
   `read monitor` (the buff and animation ids that appear).
4. Terminal 2: `.\eldendisk.exe write` lists what can be written; `write vigor=99 level=150`, `write hp=99999` (full),
   `write params.effects.1621000.effectEndurance=-1` (Black Flame burns until the target dies), `write params=default` (the game's own
   values back).
5. Creative: `.\eldendisk.exe resurrect "mohg lord"` (a beaten boss alive again; rest at a Site of Grace), `read
   creative.resurrect.great_enemies` (the ones you can bring back), `scripts` (your scripts and their state), `innovate-spells` (your
   spells).
6. Quit the game. Everything is rolled back. To **keep** the save instead: let the game save (rest at a grace or quit to title), close the
   game, end `run`, then `.\eldendisk.exe vault keep --yes`.
7. Power loss, `run` killed, console closed: close the game and run `.\eldendisk.exe vault restore`.

For reading while you farm and keep what you earn: `run --vault-off` (no backup, no restore; nothing is written to the game).

## Good to know

- **Offline only.** The game is started offline; with the anti-cheat running the tool refuses (exit `3`). Changing the game's own tables
  online can get an account banned.
- **Steam Cloud** may sync the save when the game exits (not verified): use Steam's offline mode or turn Steam Cloud off for Elden Ring.
- **Every write needs the portal:** the session `run` started with the vault ON, for this very game process (exit `5` otherwise).
- `-v` on any command shows the log (`<vault>\eldendisk.log`) live instead of the short view; `run -v` also shows the other terminals.
- Exit codes: `0` done · `1` error / not applied · `2` not supported · `3` anti-cheat running · `4` restore pending · `5` no portal ·
  `130` interrupted.

---

# Command reference

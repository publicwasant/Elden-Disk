# Elden-Disk {version} (`eldendisk.exe`)

Offline save guard and live memory reader / writer for **Elden Ring 1.17.1** (Windows 10/11 x64). This file sits next to `eldendisk.exe`; the full command reference follows the quick start.

## In this folder

| File | What it is |
|:---|:---|
| `eldendisk.exe` | the tool; run it from a terminal (`.\eldendisk.exe <command>`) |
| `README.md` | this file (written when the exe is built) |
| `offsets.json`, `chr_state_ids.json` | only when the build did not embed them: the memory profile of the game and the buff / animation names; edit them here |

The other world never touches the real one: whatever you do in a `run` session, the vault puts the save and the game's own `regulation.bin` back byte-identical when the game closes.

Nothing is written next to the exe: everything the tool produces lives in `%LOCALAPPDATA%\EldenDisk` (the vault in `vault\`, the files of the extensions in `vault\extension\`, the exports of `read --export` in `output\`), so the exe can be anywhere and replacing it loses nothing. The game folder is left as it was, except for one thing you ask for: with the vault ON, `run` swaps a `regulation.bin` in for the session and puts the game's own file back, checked by hash, when the game closes. That file is the secured copy (`extension innovate-items spells --secure`, after you tried it) when the `extension.json` embedded in the exe is unchanged, otherwise a new build (a few seconds) that the gate must pass (`extension innovate-items spells --add all` builds without the game). The files live in `<vault>\extension\innovate-items\spells\`. The vault (snapshots, session record, `eldendisk.log`) lives in `%LOCALAPPDATA%\EldenDisk\vault`, and `--save-dir` / `--vault` are remembered in the Registry (`HKCU\Software\EldenDisk`).

## Quick start

1. **Copy your save folder by hand first** (`%APPDATA%\EldenRing\<SteamID64>`). A manual copy is the one backup the tool cannot get wrong.
2. Terminal 0: `.\eldendisk.exe run`. It backs the save up, starts the game **offline** and, when the game exits, puts the save back byte for byte. Leave it open. (Several Steam accounts: add `--save-dir "<folder>"` once.)
3. Terminal 1, once a character is loaded: `.\eldendisk.exe read --live` (every value, redrawn in place), or `read --query runes hp attrs.*`, `read --live-buffs`.
4. Terminal 2: `.\eldendisk.exe write --set vigor=99 level=150`, `write --refill hp,fp,stamina`. Game params: `write --set params.effects.1621000.effectEndurance=-1` makes the Black Flame burn last until the target dies (`write --reset all` puts the game's own values back; they live in the game's memory, not in the save, and are gone when the game closes). Any row of Goods, Magic, SpEffect, Bullet, AtkParam_Pc and ShopLineup can be read and written: `read --param Magic.6230` shows a row, `write --set params.Magic.6230.mp=0` makes Scouring Black Flame cost no FP, `write --reset params.Magic.6230.mp` puts the game's value back. `read --param-check` compares the `regulation.bin` in the game folder with what the game holds, row by row.
5. Quit the game. Everything `write` changed is rolled back. To **keep** it instead: let the game save (rest at a grace or quit to title), stop `run`, close the game, then `.\eldendisk.exe vault keep --yes`.
6. Power loss, host killed, console closed: close the game and run `.\eldendisk.exe vault restore`.

For read-only farming where you want to keep what you earn, start the host with `run --vault-off` (no backup, no restore; `write` is refused).

## Good to know

- **Steam Cloud** may sync the save when the game exits; this is not verified. Use Steam's offline mode or turn Steam Cloud off for Elden Ring during a session.
- **EasyAntiCheat:** `read` and `write` only work on a game started by `run` (offline, without EAC). A game started from Steam stops them with exit code `3`.
- `-v` on any command shows the log (`<vault>\eldendisk.log`) live instead of the short view; `run -v` also shows the commands other terminals run.
- **Params are for offline play only:** changing the game's own tables with anti-cheat active or online can get an account banned. `run` starts the game offline.
- **A changed row acts on what is created afterwards:** a Magic row is read at the cast, a Bullet row when the bullet is created; a flame already in the world keeps the values it had. A value written stays through Quit to Title and Continue, and is gone when the game process ends.
- Exit codes: `0` ok · `1` error / not applied · `2` unsupported `eldenring.exe` (or a read-only `params` field named in `write`) · `3` EAC loaded · `4` restore pending · `5` no valid session · `130` interrupted.

---

# Command reference

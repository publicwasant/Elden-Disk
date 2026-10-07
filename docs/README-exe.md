# Elden-Disk {version} (`eldendisk.exe`)

Offline save guard and live memory reader / writer for **Elden Ring 1.17.1** (Windows 10/11 x64). This file sits next to `eldendisk.exe`; the full command reference follows the quick start.

## In this folder

| File | What it is |
|:---|:---|
| `eldendisk.exe` | the tool; run it from a terminal (`.\eldendisk.exe <command>`) |
| `README.md` | this file (written by `eldendisk.exe build`) |
| `offsets.json`, `chr_state_ids.json` | only when the build did not embed them: the memory profile of the game and the effect / animation names; edit them here |

Nothing is written next to the exe or into the game folder. The vault (snapshots, session record, `eldendisk.log`) lives in `%LOCALAPPDATA%\EldenDisk\vault`, and `--save-dir` / `--vault` are remembered in the Registry (`HKCU\Software\EldenDisk`).

## Quick start

1. **Copy your save folder by hand first** (`%APPDATA%\EldenRing\<SteamID64>`). A manual copy is the one backup the tool cannot get wrong.
2. Terminal 0: `.\eldendisk.exe run`. It backs the save up, starts the game **offline** and, when the game exits, puts the save back byte for byte. Leave it open. (Several Steam accounts: add `--save-dir "<folder>"` once.)
3. Terminal 1, once a character is loaded: `.\eldendisk.exe read --live` (every value, redrawn in place), or `read --query runes hp attrs.*`, `read --live-effects`.
4. Terminal 2: `.\eldendisk.exe write --set vigor=99 level=150`, `write --refill hp,fp,stamina`.
5. Quit the game. Everything `write` changed is rolled back. To **keep** it instead: let the game save (rest at a grace or quit to title), stop `run`, close the game, then `.\eldendisk.exe vault keep --yes`.
6. Power loss, host killed, console closed: close the game and run `.\eldendisk.exe vault restore`.

For read-only farming where you want to keep what you earn, start the host with `run --vault-off` (no backup, no restore; `write` is refused).

## Good to know

- **Steam Cloud** may sync the save when the game exits; this is not verified. Use Steam's offline mode or turn Steam Cloud off for Elden Ring during a session.
- **EasyAntiCheat:** `read` and `write` only work on a game started by `run` (offline, without EAC). A game started from Steam stops them with exit code `3`.
- `-v` on any command shows the log (`<vault>\eldendisk.log`) live instead of the short view; `run -v` also shows the commands other terminals run.
- Exit codes: `0` ok · `1` error / not applied · `2` unsupported `eldenring.exe` · `3` EAC loaded · `4` restore pending · `5` no valid session · `130` interrupted.

---

# Command reference

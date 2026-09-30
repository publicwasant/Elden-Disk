# Elden Ring Telemetry (offline, read-only)

Launches Elden Ring **offline** (`eldenring.exe -eac-nop-loaded`) and writes live character data to
`output/telemetry-state.json`. Implements spec v1.1.0. Standard library only, Windows + 64-bit Python 3.11+.

## Guarantees
- Read-only: the only access mask requested is `PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION`.
- Nothing is written to the game folder (the logger refuses an output dir inside it).
- Never reads memory if EasyAntiCheat modules are loaded, or if the exe version has no profile.
- Any failed check (null pointer, unreadable memory, out-of-range value, cyclic/oversized effect list) discards the whole sample.
  Nothing is ever reported as `0` because a read failed.

## Quick start
1. Start the **Steam client** and log in (offline mode in Steam is fine).
2. `python -m elden_telemetry hash` → prints the SHA-256 of your `eldenring.exe`.
3. Add a profile for that hash in `offsets.json` (next section). Until you do, `run` reports `UNSUPPORTED_VERSION`.
4. `python -m elden_telemetry run -v`
   - launches the game offline, waits for the main module, then polls at 10 Hz
   - `-v` prints state changes and the reason for the last discarded sample
5. Read `output/telemetry-state.json` from any other program (schema: `elden_telemetry/telemetry.schema.json`).

Already started the game yourself with `-eac-nop-loaded`? Use `python -m elden_telemetry run --attach`
(same EAC/read-only checks apply). Ctrl+C stops the tool and leaves the game running.

Options: `--game-dir`, `--out`, `--offsets`, `--effects`, `--hz 1..30`.

## Adding a profile (once per game patch)
Use Cheat Engine **in an offline session** (or any pointer tool). Work in two stages so stats work early.

**Stage 1 – stats (fill these in `offsets.json`, leave `sp_effect.entry.*` as null)**

| Field | How |
|---|---|
| `world_chr_man_rva` | RVA of the `WorldChrMan` static pointer (module base + RVA holds the pointer) |
| `world_chr_man_to_player` | Offset from `WorldChrMan` to the local `PlayerIns` pointer |
| `player_to_game_data` | default `0x580` – verify |
| `game_data.*` | defaults `0x68` level, `0x6C` runes, `0x3C` attributes (8 × u32, vigor→arcane) – verify |

Check: level, runes and all 8 attributes must equal the in-game menu exactly; change them (level up, pick up runes) and
confirm. With a wrong offset the tool stays in `WAITING_FOR_WORLD` and `-v` prints e.g. `level=0 outside (1, 713)`.

**Stage 2 – buffs (`sp_effect` + `effects.json`)**

1. `player_to_sp_effect` (default `0x178`) → `SpecialEffect`; `sp_effect.head` (default `0x8`) → first list entry.
2. In an entry find offsets of: SpEffect **id** (u32), **next** pointer (u64), **duration** (f32), **timer** (f32).
3. `timer_mode`: use a timed buff. If the timer counts **down** to 0 → `"remaining"`; if it counts **up** to `duration` → `"elapsed"`.
4. Fill `effects.json`:
   ```json
   {
     "active":  { "<sp_effect_id>": { "name": "Golden Vow" } },
     "passive": { "<sp_effect_id>": { "name": "Gold Scarab", "category": "TALISMAN", "source_name": "Gold Scarab Talisman" } }
   }
   ```
   IDs come from `SpEffectParam` (active buffs) and from `EquipParamAccessory.refId` (talismans) of your game version,
   e.g. exported with Smithbox. Effects not listed are ignored (counted in `ignored_effects`).

If `sp_effect` is incomplete the tool still runs; `buffs_supported` is `false` and the buff arrays are empty.

## States
| `state` | Meaning |
|---|---|
| `WAITING_FOR_PROCESS` | game not running / not found |
| `EAC_ACTIVE`, `EAC_DETECTED` | EAC loaded; tool exits (code 3) without reading |
| `UNSUPPORTED_VERSION` | no complete profile for this exe hash; tool exits (code 2) |
| `WAITING_FOR_WORLD` | title screen, loading, or a check failed (see `last_error`) |
| `CONNECTED` | all checks passed; `character` filled |
| `DISCONNECTED` | game exited |

## Troubleshooting
- **Game won't start / Steam error on direct launch:** the tool passes `SteamAppId`/`SteamGameId` via environment. If that
  is not enough on your setup, create `steam_appid.txt` (containing `1245620`) in the game folder yourself; the tool never writes there.
- **`OpenProcess failed` (error 5):** the process is protected (EAC) or you need to run from the same user account.
- **Stuck in `WAITING_FOR_WORLD` in-game:** run with `-v` and read `last_error`; it names the failing pointer/field.

## Tests
`pip install -r requirements-dev.txt && python -m pytest` – covers pointer-chain logic, validation, linked-list safety,
profile loading, JSON schema and safety constraints using a fake process memory (the Windows API layer itself needs a real game to test).

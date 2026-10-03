# Detecting "resting at a Site of Grace" in Elden Ring 1.17.1

Project: Elden-Disk (offline, Python)
Game build: Elden Ring 1.17.1 (`eldenring.exe` SHA-256 `1a3547101327f65d0c76da2f9190ac0aa66871ea42bae2aecc61e11a8b597891`)
Tool used for measurement: Cheat Engine 7.7, offline play only

## 1. Goal

Make the **Elden-Disk** tool know when the player is currently resting at a Site of Grace, so the `at_grace` entry in `offsets.json` (previously `null`) can be filled in.

## 2. Result in one paragraph

The player's **current animation ID** is readable through the player's `CSChrTimeActModule`. While resting at a Grace it reads **`68011`** (`0x109AB`), which differed from every other state tested (standing, running, sprinting, rolling, attacking, pause menu) and was identical at four different Graces. The finding is well supported but not fully validated yet; see section 6.

## 3. Approaches that did not work

| **Approach**                                                         | **Outcome**                                                                                                                                                                                                                                                         |
|----------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Diff the SpEffect list (before / menu open / after)                  | No change at all                                                                                                                                                                                                                                                    |
| Continuous change-only SpEffect log through enter, menu, exit        | Nothing logged                                                                                                                                                                                                                                                      |
| Cheat Engine value scans (changed / unchanged, standing vs. sitting) | Only counters, timestamps, and values rewritten by the world reset on rest (e.g. `1472977632` / `2916801040`, values that differed on every repeat). An unknown-initial-value scan also produced about 2.77 billion results and filled the C: drive with scan files |

Lesson: resting at a Grace resets HP, flasks and enemies, which rewrites a lot of memory. A "stand to sit" filter alone mostly finds side effects of that reset.

## 4. Approach that worked

Instead of scanning, take the structure layout from open source and verify it against offsets already known to be correct.

Source: the `eldenring` crate in **https://github.com/vswarte/fromsoftware-rs** (file `chr_ins.rs`, plus the module sources for `ChrInsModuleContainer` and `CSChrTimeActModule`).

### Sanity check of the layout against existing offsets

| **Field**                     |  **Offset from the crate source** | **Existing `offsets.json` value**      |
|:------------------------------|----------------------------------:|:---------------------------------------|
| `ChrIns.special_effect`       |                           `0x178` | `player_to_sp_effect = 0x178` (match)  |
| `PlayerIns.player_game_data`  |                           `0x580` | `player_to_game_data = 0x580` (match)  |
| `ChrIns.modules`              |                           `0x190` | new                                    |

### Pointer chain

```
[eldenring.exe + 0x3B16E30]   WorldChrMan
  [+0x0]                      PlayerIns
    [+0x190]                  ChrInsModuleContainer
      [+0x18]                 CSChrTimeActModule
        read_idx : u32 at +0xC4
        anim_id  : i32 at +0x20 + read_idx * 0x10
```

`anim_queue` is a 10-entry buffer of 0x10-byte entries; `anim_id` is the first 4 bytes of an entry. The `ChrInsModuleContainer` field order puts `time_act` fourth, at `+0x18` (every field is an 8-byte pointer).

In Cheat Engine (Add Address Manually, Pointer, 4 Bytes) the offsets are entered bottom to top: `0`, `190`, `18`, then `C4` (read_idx) or `90` / `50` (queue slot).

## 5. Measurements

Base: `"eldenring.exe"+3B16E30`, offsets `[slot, 18, 190, 0]`.

| **In-game action**                       |  **Slot `+0x90`** |  **Slot `+0x50`** |
|:-----------------------------------------|------------------:|------------------:|
| _Just standing_                          |           2000000 |           2000000 |
| _Running_                                |           2020110 |           2020110 |
| _Sprinting_                              |           2020210 |           2020210 |
| _Rolling_                                |             27110 |             27110 |
| _Attacking (R1)_                         |          26030000 |          26030000 |
| _Pause menu while standing_              |           2000000 |           2000000 |
| _Resting at Palace Approach Ledge-Road_  |             68011 |             68011 |
| _Resting at Dynasty Mausoleum Entrance_  |             68011 |             68011 |
| _Resting at Dynasty Mausoleum Midpoint_  |             68011 |             68011 |
| _Resting at Church of Elleh_             |             68011 |             68011 |

Observations:

- Values were stable across repeated tries.
- The pause menu does not change the value, so this is not a generic "a menu is open" flag.
- Both queue slots show the same value in every row. The reason is not understood (a guess: the queue is filled with the current animation more than once). `read_idx` read `7` in one session and `3` in a later one, so a fixed slot offset may not be safe; reading `read_idx` first is the more robust approach.

## 6. Status and open checks

Status: **hypothesis strongly supported, not yet closed.**

Still to verify before treating `68011` as the definitive Grace signal:

1. Negative cases not yet tried: inventory and map menus, talking to an NPC, shops, chests, item pickup, ladders, doors, riding Torrent.
2. The sit-down and stand-up animations (record their IDs; decide whether they count as "at grace").
3. A Grace in another region that was not among the four tested.
4. Restart the game and confirm the same chain and the same values.
5. Confirm that reading via `read_idx` agrees with the fixed slots after the game has been restarted and after loading screens.

## 7. Final configuration

See `offsets.json`. The `anim` block holds the chain offsets and `at_grace` compares the current animation ID against `0x109AB` (68011). The loader and the memory reader in the tool still need code to support the `source: "anim"` form; that code has not been written yet.

```json
{
  "_readme": "Key = SHA-256 of eldenring.exe (python -m elden_telemetry hash). Hex strings. null = not set yet. anim: pointer chain to the player's CSChrTimeActModule (anim_id = u32 at time_act + queue + read_idx * entry_size). at_grace: source 'anim' compares the current anim_id against 'equals'. See README section 'Adding a profile'.",
  "profiles": {
    "1a3547101327f65d0c76da2f9190ac0aa66871ea42bae2aecc61e11a8b597891": {
      "label": "Elden Ring 1.17.1",
      "world_chr_man_rva": "0x3B16E30",
      "world_chr_man_to_player": "0x0",
      "player_to_game_data": "0x580",
      "player_to_sp_effect": "0x178",
      "game_data": { "level": "0x68", "runes": "0x6C", "attributes": "0x3C" },
      "sp_effect": {
        "head": "0x8",
        "entry": { "id": "0x8", "next": "0x30", "duration": "0x48", "timer": "0x40", "timer_mode": "remaining" }
      },
      "anim": {
        "player_to_modules": "0x190",
        "modules_to_time_act": "0x18",
        "time_act_read_idx": "0xC4",
        "time_act_queue": "0x20",
        "queue_entry_size": "0x10"
      },
      "at_grace": { "source": "anim", "equals": ["0x109AB"] }
    }
  }
}

```

## 8. Reproduce

1. Add the pointer address in Cheat Engine as in section 4 and watch the value while performing each action in section 5.
2. For the tool: read `read_idx` at `time_act + 0xC4`, then read the 4-byte `anim_id` at `time_act + 0x20 + read_idx * 0x10`, then test `anim_id == 68011`.

## References

- **https://github.com/vswarte/fromsoftware-rs**
- **https://docs.rs/crate/eldenring/0.14.0/source/src/cs/chr_ins/module/time_act.rs**
- **https://docs.rs/crate/eldenring/latest/source/src/cs/chr_ins/module/event.rs**

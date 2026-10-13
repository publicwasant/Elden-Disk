# 1.8.0 research: `extension resurrect-unit great-enemies`

Research notes only. Nothing in the repo was changed. 2026-10-13.

## 1. Which bosses exist: `GameAreaParam` in regulation.bin

I read it from the game's own `regulation.bin` (read-only, with the repo's own decoder): 216 rows, 96 bytes each.

- **212 rows have a defeat flag** (`defeatBossFlagId`). 40 of them are DLC bosses (m20–m28, m40–m43, m61).
- Each row has `bonusSoul_single` (the runes for the kill; the most is 500,000, the Elden Beast `19000800`), the map (`m10_00_00`), the boss's position (`bossPosX/Y/Z`), `foundBossFlagId` and `bossChallengeFlagId`.
- The row id is usually the same as the defeat flag (198 of 212 rows), for example `10000800` Godrick and `10000850` Margit. Fourteen rows differ, for example `30200800` → flag `30200810`.
- Flag endings: `…800` (175 rows), `…850` (26), `…340`, `…830`, `…860`, `…810`.
- **The rows have no names in the file.** Paramdex has a names file `ER/Names/GameAreaParam.txt`: 210 lines like `10000800 [Stormveil Castle] Godrick the Grafted`. Its license still needs checking.

Field layout (Paramdex `GameAreaParam.xml`): `bonusSoul_single`@4, `bonusSoul_multi`@8, `foundBossFlagId`@52, `foundBossTextId`@56, `bossChallengeFlagId`@64, `defeatBossFlagId`@68, `bossPos`@72, `bossMapAreaNo/Block/Map`@84–86.

## 2. How the game remembers a defeated boss: event flags

- A boss is "defeated" because its event flag is ON. The map's event script (EMEVD) checks the flag **when the map loads**. If it is ON, the boss and its fog are turned off.
- **Turn the flag OFF and load the map again, and the boss comes back.** The map loads again after a warp from a grace (even to the same grace) or after Quit → Continue. Resting may not be enough; this must be tried.
- Usually each boss has **two kinds of flag**: one says it is dead, the other says you took its reward (the Remembrance, an item lot with its own flag). If you only clear the first, the boss comes back but drops no Remembrance again (Steam guide).
- The flag reference (soulsmods eventparam) shows that each area has `…800` "boss flag (not reset)" and `…2800` "boss flag (reset)". There are also `61xxx` / `9xxx` "boss defeated" flags for the play log or achievements.
- Story side effects reported by players: reviving Radahn broke the Radahn Festival and the Great Rune fragment. Story bosses are risky. Field, catacomb, cave and tunnel bosses are fairly safe.

## 3. The flags in memory: `CSEventFlagMan` → `CSFD4VirtualMemoryFlag`

From the Rust crate `eldenring` (fromsoftware-rs, MIT/Apache, `cs/event_flag.rs`):

```text
CSFD4VirtualMemoryFlag
  +0x1C u32 event_flag_divisor        (1000)
  +0x20 u32 event_flag_holder_size    (125 bytes = 1000 flags)
  +0x24 u32 event_flag_holder_count
  +0x28 ptr flag_blocks               (the blocks laid out one after another)
  +0x30 DLMap<u32, FlagBlockDescriptor>   (a std::map tree: group -> where the block is)
FlagBlockDescriptor { u32 location_mode; union { u32 holder_offset; ptr external } }
  mode 1: flag_blocks + holder_offset * 125     mode 2: its own pointer
group = flag / 1000, byte = (flag % 1000) / 8, bit = 7 - (flag % 8)      (the highest bit first)
```

- `CSEventFlagMan` is a global of the game. The old cheat tables find it with an AOB; TGA had to fix it in 1.10, so it moves between versions.
- For us: put its RVA in the profile (offsets.json) the same way as GameDataMan, **or** find it by its shape (an object whose +0x1C is 1000 and +0x20 is 125). It must be checked in the real game read-only first, like `equipment` was.
- Writing a flag means changing one bit in memory. The tool has the writer and the session gate already. It is not synced online, and we are offline anyway.

## 4. Why it fits Elden-Disk well

- **Parallel world:** the vault restores the save when the game closes, so the bosses you bring back, the runes and the drops all disappear with the session. The real save stays as it was. A boss can be fought again safely without editing the save file (no MD5 checksum, no save format to parse).
- It uses what exists: the session gate, the writer, `--when-loaded`, the extension and the vault, `read`, and the external scripts.

## 5. Ways to build it (for the brainstorm)

| | Approach | + | − |
|:-:|:--|:--|:--|
| A | **Memory**: clear the flag in the running game, then the player warps once | the same path as `write`; session only; checked by reading back | needs the CSEventFlagMan RVA; the player must warp; must be tried |
| B | Edit the save before `run` launches the game | no warp needed | must parse and checksum the save; risky; against the rule that the save is never changed |
| C | regulation.bin | – | the boss is not in params (the event scripts are in the game's archives, which an unpatched game does not read loose) |

I recommend A.

## 6. Questions for the brainstorm

1. **"great-enemies" means which bosses?** All 212 rows with a defeat flag, or only the main bosses ("GREAT ENEMY FELLED"), or a category (field, catacombs, caves, legacy dungeons, DLC)?
2. **Rewards:** should the Remembrance drop again (clear the reward flag too), or only the fight? Runes come by themselves from `bonusSoul`.
3. **Story bosses** (Radahn, Rennala, Morgott, Malenia …): allow them with a warning, or leave them out by default?
4. **How to choose:** CLI (`--list`, `--add 10000850 "Margit"`, `--all --area m30`), or a block in extension.json (`resurrect_unit.great_enemies: [...]`) that `run` applies at every session like the text and colours, or both?
5. **When:** once when the world loads (the player then warps), or also live: `read`/`write` names (`world.great_enemies.10000850.defeated = false`) so a script can make a boss rush?
6. **Names:** use the Paramdex list (license?), or write our own list of 212?
7. **First encounter:** clear the "found" or "challenge" flag too, so the intro cutscene plays again (some tools offer "revive back to first encounter")?

## 7. Before any code (read-only, in the game)

- Find the CSEventFlagMan address for 1.17.1 and read `10000800` and `10000850` for the user's character (they should be ON if Godrick and Margit are dead).
- Clear one field boss in a session (for example a catacomb), warp, and see the boss and the reward.

Sources: [Paramdex GameAreaParam.xml](https://github.com/soulsmods/Paramdex/blob/master/ER/Defs/GameAreaParam.xml), [Paramdex names](https://github.com/soulsmods/Paramdex/blob/master/ER/Names/GameAreaParam.txt), [eldenring crate event_flag.rs](https://docs.rs/eldenring/latest/src/eldenring/cs/event_flag.rs.html), [ER event flag reference](https://soulsmods.github.io/elden-ring-eventparam/), [Save Manager event flags](https://elden-ring-save-manager.readthedocs.io/en/main/user-guide/event-flags/), [Steam: two flags per boss](https://steamcommunity.com/app/1245620/discussions/0/640179350026599023/), [Reddit: Radahn after revive](https://lr.ggtyler.dev/r/EldenRingMods/comments/1flrxmo/boss_resurrection_mod_messed_up_radahn), [Open Cheat Tables: CSFD4VirtualMemoryFlag AOB](https://opencheattables.com/viewtopic.php?t=300), [TGA CT v1.6.1 notes](https://github.com/The-Grand-Archives/Elden-Ring-CT-TGA/releases/tag/v1.6.1).

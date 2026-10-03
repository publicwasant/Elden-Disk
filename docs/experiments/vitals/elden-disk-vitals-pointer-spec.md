# Elden-Disk — Player Vitals (HP / FP / Stamina) Memory Specification

| Field | Value                                                                                                        |
|---|--------------------------------------------------------------------------------------------------------------|
| Document ID | ED-SPEC-VITALS-001                                                                                           |
| Version | 1.5.0                                                                                                        |
| Date | 2026-10-04                                                                                                   |
| Status | Offsets and chain validated on 1.17.1 by the project owner (§7.1); semantics of `max_uncapped_hp` still open |
| Target game | Elden Ring, app version 1.17.1 (exe file version 2.7.1.0), Windows x64, Steam                                |
| Subject | Pointer chain and field offsets for the local player's current and maximum HP, FP, and Stamina               |
| Out of scope | Tool architecture, implementation, code, SpEffect / buff handling, Grace detection                           |

---

## 1. Purpose and Scope

This document specifies **where** the local player's vital statistics live in the game process memory, and **how** each value is reached from the module base of `eldenring.exe`. It covers the complete ten-field vitals block of the player's data module: current, maximum, and base values for each stat, plus the extra uncapped-maximum field that exists only for HP.

### 1.1 Stat terminology

| Abbreviation | Full name | Description | Governing attribute | In-memory fields |
|---|---|---|---|---|
| HP | **Hit Points** | Health. The character dies when it reaches 0 | Vigor | `hp`, `max_hp`, `max_uncapped_hp`, `base_hp` |
| FP | **Focus Points** | Energy consumed by Sorceries, Incantations, and Skills (Ashes of War) | Mind | `fp`, `max_fp`, `base_fp` |
| Stamina | **Stamina** (no abbreviation) | Energy consumed by running, rolling, attacking, and blocking; regenerates over time | Endurance | `stamina`, `max_stamina`, `base_stamina` |

Terminology note: these names and descriptions come from community-maintained documentation [S7]. No page published by FromSoftware or Bandai Namco stating them was located while preparing this document; the in-game status screen and menu text remain the authoritative reference (see Open Item 5). "FP" (Focus Points) is distinct from the separate *Focus* resistance stat.

All access described here is **read-only** and intended for **offline** use.

## 2. Conventions

- `base` denotes the load address of the `eldenring.exe` module in the target process.
- All offsets are hexadecimal, in bytes.
- All pointers are 8 bytes (x64), little-endian. All vitals values are 4-byte signed integers (`i32`).
- Chain notation follows the project convention (as used for the stage 1 stats chain):

  `base+<static RVA> -> +<o1> -> +<o2> -> ... -> +<oN>`

  Each `->` means *read an 8-byte pointer at (current address + offset)* and continue from the pointer value. The **last** offset is added to the final pointer and is **not** dereferenced; it addresses the value itself.
- **Status tags** used in this document:

| Tag | Meaning |
|---|---|
| `PROJECT-VERIFIED` | Confirmed on 1.17.1 by the Elden-Disk project (pointer scan / in-game comparison) |
| `SOURCE-DERIVED` | Taken from published open-source reverse-engineering work; not yet confirmed on 1.17.1 by this project |
| `INFERRED` | Deduced by consistency between the two categories above; no direct source statement |

## 3. Pointer Chain

### 3.1 Canonical chain

```
base+0x3B16E30 -> +0x0 -> +0x190 -> +0x0 -> +<field offset>
```

As an offset list (Cheat Engine style): `[0x0, 0x190, 0x0, <field offset>]` applied to the static address `base+0x3B16E30`.

### 3.2 Hop-by-hop definition

| # | Operation | Resolves to | Status | Evidence |
|---|---|---|---|---|
| 0 | Read pointer at `base+0x3B16E30` | Root object `R` (type not identified by the project) | `PROJECT-VERIFIED` | Pointer-scan result recorded in the project's `offsets.json`; used by the verified stage 1 chain (`base+0x3B16E30 -> +0 -> +0x580 -> ...`) and the verified animation-ID chain |
| 1 | Read pointer at `R + 0x0` | Main player `PlayerIns` (subclass of `ChrIns`) | `INFERRED` | The next hops (`+0x190`, `+0x580`) are exactly the `ChrIns.modules` and `PlayerIns.player_game_data` offsets in [S3]; both resolve correctly on 1.17.1 in the project's verified chains |
| 2 | Read pointer at `PlayerIns + 0x190` | `ChrInsModuleContainer` | `PROJECT-VERIFIED` + `SOURCE-DERIVED` | Field `modules` in [S3]; independently listed as `ChrModules (+0x190)` in [S5]; traversed by the project's verified animation-ID chain |
| 3 | Read pointer at `ChrInsModuleContainer + 0x0` | `CSChrDataModule` | `PROJECT-VERIFIED` (owner-reported) + `SOURCE-DERIVED` | Field `data` is the first member of `ChrInsModuleContainer` in [S2]. The sibling field `time_act` (`+0x18`) is `PROJECT-VERIFIED` through the animation-ID chain |
| 4 | Add field offset (§4) — no dereference | Address of the `i32` value | `PROJECT-VERIFIED` (owner-reported) + `SOURCE-DERIVED` | Layout of `CSChrDataModule` in [S1]; values match the in-game status screen (§7.1) |

### 3.3 Related chains already verified by the project (context only)

| Purpose | Chain | Status |
|---|---|---|
| Level / runes / attributes (stage 1) | `base+0x3B16E30 -> +0x0 -> +0x580 -> +0x6C` (terminal offset as recorded in `offsets.json`) | `PROJECT-VERIFIED` |
| Player animation ID (`at_grace`) | `base+0x3B16E30 -> +0x0 -> +0x190 -> +0x18 -> +0x90` (4 bytes; value `68011` = resting at a Grace) | `PROJECT-VERIFIED` |

The vitals chain shares hops 0–2 with the animation-ID chain and diverges at the module container: `+0x0` (data module) instead of `+0x18` (time-act module).

### 3.4 Pointer validity

Any hop may resolve to `NULL` or an unreadable address when no character is loaded (main menu, loading screens, some transitions). A reader must treat a failed or null hop as "vitals unavailable", not as zero values.

## 4. `CSChrDataModule` Field Offsets

### 4.1 Vitals block

All values are `i32`. Offsets are relative to the start of the `CSChrDataModule` object (hop 3 result).

All ten fields are in scope. The "Expected description" column states the intended meaning; [S1] provides field names only, not semantics. The roles of the current, maximum, and base fields are consistent with the validation record in §7.1; the semantics of `max_uncapped_hp` remain a hypothesis.

| Offset | Field name in [S1] | Stat (full name) | Value | Expected description |
|---|---|---|---|---|
| `0x138` | `hp` | Hit Points (HP) | Current | Current HP |
| `0x13C` | `max_hp` | Hit Points (HP) | Maximum | Effective maximum HP, including equipment and buff modifiers; expected to match the status screen |
| `0x140` | `max_uncapped_hp` | Hit Points (HP) | Maximum (uncapped) | Maximum HP before the cap is applied (name-implied) |
| `0x144` | `base_hp` | Hit Points (HP) | Base | Base maximum HP from character level / Vigor, before modifiers (name-implied) |
| `0x148` | `fp` | Focus Points (FP) | Current | Current FP |
| `0x14C` | `max_fp` | Focus Points (FP) | Maximum | Effective maximum FP, including equipment and buff modifiers |
| `0x150` | `base_fp` | Focus Points (FP) | Base | Base maximum FP from character level / Mind, before modifiers (name-implied) |
| `0x154` | `stamina` | Stamina | Current | Current Stamina |
| `0x158` | `max_stamina` | Stamina | Maximum | Effective maximum Stamina, including equipment and buff modifiers |
| `0x15C` | `base_stamina` | Stamina | Base | Base maximum Stamina from character level / Endurance, before modifiers (name-implied) |

The block is contiguous: `0x138`–`0x15F` (40 bytes, ten `i32` values). **HP has four fields while FP and Stamina have three**; FP therefore starts at `0x148`, not `0x144`.

Adjacent field, documented for completeness:

| Offset | Field name in [S1] | Type | Role |
|---|---|---|---|
| `0x160` | `recoverable_hp` | `f32` | HP that can still be regained through the rally (regain) mechanic |

### 4.2 Full chain per value

| Value | Chain |
|---|---|
| HP — current | `base+0x3B16E30 -> +0x0 -> +0x190 -> +0x0 -> +0x138` |
| HP — maximum | `base+0x3B16E30 -> +0x0 -> +0x190 -> +0x0 -> +0x13C` |
| HP — maximum (uncapped) | `base+0x3B16E30 -> +0x0 -> +0x190 -> +0x0 -> +0x140` |
| HP — base | `base+0x3B16E30 -> +0x0 -> +0x190 -> +0x0 -> +0x144` |
| FP — current | `base+0x3B16E30 -> +0x0 -> +0x190 -> +0x0 -> +0x148` |
| FP — maximum | `base+0x3B16E30 -> +0x0 -> +0x190 -> +0x0 -> +0x14C` |
| FP — base | `base+0x3B16E30 -> +0x0 -> +0x190 -> +0x0 -> +0x150` |
| Stamina — current | `base+0x3B16E30 -> +0x0 -> +0x190 -> +0x0 -> +0x154` |
| Stamina — maximum | `base+0x3B16E30 -> +0x0 -> +0x190 -> +0x0 -> +0x158` |
| Stamina — base | `base+0x3B16E30 -> +0x0 -> +0x190 -> +0x0 -> +0x15C` |

### 4.3 Derivation of the `0x138` anchor

[S1] publishes the structure as an ordered field list. Several of its padding fields encode their own offset in their name (`unk68`, `unk90`, `unkc8`, `unkd4`, `unk16c`, ...), which allows the offsets above to be cross-checked rather than trusted blindly:

| Offset | Member | Size | Note |
|---|---|---|---|
| `0x00` | `vftable` | 8 | |
| `0x08` | `owner` (`ChrIns*`) | 8 | |
| `0x10` | `msb_parts` | `0x50` | Size implied by the next named offset |
| `0x60` | `msb_res_cap` | 8 | |
| `0x68` | `unk68` | 8 | Name-encoded offset matches |
| `0x70` / `0x74` / `0x78` | `unk70` / `unk74` / `unk78` | 4 each | Name-encoded offsets match |
| `0x7C` | `block_id_origin` | 4 | |
| `0x80` / `0x84` | `unk80` / `unk84` | 4 each | Name-encoded offsets match |
| `0x88` | `world_block_chr` | 8 | |
| `0x90` | `unk90` | `0x30` | Name-encoded offset matches |
| `0xC0` | `draw_params` | 4 | |
| `0xC4` | `chara_init_param_id` | 4 | |
| `0xC8` | `unkc8` | `0xC` | Name-encoded offset matches |
| `0xD4` | `unkd4` | `0x64` | Name-encoded offset matches; ends at `0x138` |
| **`0x138`** | **`hp`** | 4 | Start of vitals block |
| `0x160` | `recoverable_hp` | 4 | Ends the vitals block (`0x138` + 10 × 4 = `0x160`) |
| `0x16C` | `unk16c` | 4 | Name-encoded offset matches (after `recoverable_hp_2` at `0x164`, `recoverable_hp_time` at `0x168`) |

Every name-encoded offset agrees with the computed one, which supports the correctness of the `0x138` anchor and the ordering inside the vitals block.

### 4.4 Container layout (hop 3 anchor)

From [S2], the first members of `ChrInsModuleContainer` (all `OwnedPtr` / `usize`, 8 bytes each):

| Offset | Member |
|---|---|
| `0x00` | `data` → `CSChrDataModule` |
| `0x08` | `action_flag` → `CSChrActionFlagModule` |
| `0x10` | `behavior_script` |
| `0x18` | `time_act` → `CSChrTimeActModule` (used by the project's animation-ID chain) |

## 5. Value Semantics and Expected Invariants

The names in §4.1 come from [S1]; their precise gameplay semantics (especially `max_uncapped_hp` and the `base_*` fields) are **not defined by the source** and are therefore labelled "name-implied". For the project requirement "current and maximum", the intended pair per stat is `X` / `max_X` as listed in §4.1; the `base_*` and `max_uncapped_hp` fields are documented in full so that the entire block can be read and validated.

Expected invariants during normal gameplay (to be confirmed under §7):

- `0 <= hp <= max_hp`, `0 <= fp <= max_fp`, `0 <= stamina <= max_stamina`.
- `max_*` values are expected to reflect the character's **effective** maximum (including equipment and buff modifiers) and to match the numbers shown on the in-game status screen.
- `base_*` values are expected to depend on attributes (Vigor / Mind / Endurance) only.

The last two bullets are consistent with the validation record in §7.1 (effective maximum equals the status-screen value; base value differs from it). They are not source statements.

## 6. Version and Stability Considerations

| Layer | Stability | Notes |
|---|---|---|
| Static RVA `0x3B16E30` | **Build-specific** | Changes with every executable rebuild. Must be re-derived (pointer scan) for any game version other than 1.17.1 |
| `PlayerIns +0x190` (`modules`) | Stable across the builds seen in [S3] and [S5] | [S5] documents the same offset on a different build (ERR mod base), supporting cross-build stability |
| `ChrInsModuleContainer +0x0` (`data`) | Stable (struct layout) | Container is a plain pointer table |
| `CSChrDataModule +0x138 ...` | Stable across versions per [S1]; **confirmed on 1.17.1** (§7.1) | Re-validate after each game patch |

The structure definitions in [S1]–[S3] are from `eldenring` crate version 0.14.0 (docs.rs build dated 2026-09-30). The crate tracks the game version it targets, which is not necessarily 1.17.1; the project's verified hops (`+0x190`, `+0x18`) provide continuity evidence for the container, and §7.1 confirms the data module's vitals block on 1.17.1.

Alternative root (not used by this project): [S4] and [S6] describe `WorldChrMan → main_player` as the conventional route to the local `PlayerIns`. Its RVA is also build-specific and was not verified here. The project's current root (`base+0x3B16E30 -> +0x0`) already resolves to a `PlayerIns`-compatible object on 1.17.1 and is preferred.

## 7. Validation Plan (acceptance criteria)

All steps that **change** game state (levelling, equipment changes with persistent effects) must be performed in the project's **sandbox mode** or on a throw-away save, never on the online character.

| ID | Procedure | Expected result | Confirms |
|---|---|---|---|
| V1 | Stand idle at full health; open the in-game status screen | `hp`/`max_hp`, `fp`/`max_fp`, `stamina`/`max_stamina` equal the numbers shown on the status screen | Chain, all six offsets |
| V2 | Take damage from an enemy or fall | `hp` decreases; `max_hp` unchanged | `hp` vs. `max_hp` |
| V3 | Use a Flask of Crimson Tears | `hp` increases, never exceeding `max_hp` | `hp` |
| V4 | Use a Flask of Cerulean Tears or cast a spell | `fp` increases / decreases accordingly; `max_fp` unchanged | `fp`, `max_fp` |
| V5 | Sprint, roll, and attack repeatedly, then rest | `stamina` falls and then regenerates; `max_stamina` unchanged | `stamina`, `max_stamina` |
| V6 | Equip / unequip a talisman that raises max HP (e.g. Erdtree's Favor) | `max_hp` changes; `base_hp` expected unchanged | `max_hp` vs. `base_hp` semantics (§5) |
| V7 | Sandbox only: raise Vigor, Mind, Endurance by one level each | `base_*` and `max_*` change for the corresponding stat | `base_*` semantics |
| V8 | Quit to the main menu; load a different save; die | A hop in the chain becomes null or the values reset; no stale values are reported as valid | §3.4 pointer validity |
| V9 | Compare `max_hp` and `max_uncapped_hp` at several levels (below and above the in-game cap, if reachable in sandbox) | Documents the difference between the two fields | `max_uncapped_hp` semantics |

Acceptance (original criteria): V1–V5 and V8 must pass for the chain and the six current/maximum offsets (`0x138`, `0x13C`, `0x148`, `0x14C`, `0x154`, `0x158`) to be marked `PROJECT-VERIFIED`. V6, V7, and V9 are required to promote the "name-implied" roles of `base_hp`, `base_fp`, `base_stamina`, and `max_uncapped_hp` in §4.1.

### 7.1 Validation record

Status: the project owner reports that the full chain and all ten offsets were tested on 1.17.1 and match in-game behaviour (V1–V8). Only the V1 snapshot below was captured as evidence in this document; V2–V8 results are owner-reported and carry no recorded measurements here.

**V1 snapshot (2026-10-04)** — in-game status screen compared with the ten addresses resolved through the chain:

| Value | Status screen | Memory | Offset |
|---|---|---|---|
| HP — current | 1914 | 1914 | `0x138` |
| HP — maximum | 1914 | 1914 | `0x13C` |
| HP — maximum (uncapped) | — | 1914 | `0x140` |
| HP — base | — | 2015 | `0x144` |
| FP — current | 350 | 350 | `0x148` |
| FP — maximum | 350 | 350 | `0x14C` |
| FP — base | — | 350 | `0x150` |
| Stamina — current | 178 | 178 | `0x154` |
| Stamina — maximum | 178 | 178 | `0x158` |
| Stamina — base | — | 158 | `0x15C` |

Observations: the ten resolved addresses are contiguous at 4-byte spacing (0x24 span from first to last), consistent with §4.1. The base values for HP (2015) and Stamina (158) differ from the effective maximums shown on screen (1914 and 178), consistent with `max_*` being the effective value and `base_*` the unmodified value. Character at capture time: Level 386, Vigor 80, Mind 60, Endurance 60.

## 8. Open Items

1. Identify the type and name of root object `R` at `base+0x3B16E30` (currently only known by behaviour).
2. ~~Confirm hop 3 and the vitals block on 1.17.1~~ — closed in v1.2 (§7.1, owner-reported).
3. Determine the exact semantics of `max_uncapped_hp` (equal to `max_hp` in the V1 snapshot; V9 is needed to show when they differ). The `base_*` roles are consistent with V1 but V7 results were not recorded.
4. Decide whether `recoverable_hp` (`0x160`, `f32`) is needed by the project.
5. Confirm the full stat names against the game's own text (status screen / menu text) or an official FromSoftware / Bandai Namco publication; §1.1 currently relies on community documentation [S7].

## 9. Sources and References

| Ref | Source | Used for |
|---|---|---|
| [S1] | `eldenring` crate (vswarte/fromsoftware-rs), `CSChrDataModule` — https://docs.rs/crate/eldenring/latest/source/src/cs/chr_ins/module/data.rs | Field order and sizes of the vitals block; name-encoded offsets used in §4.3 |
| [S2] | `eldenring` crate, `ChrInsModuleContainer` — https://docs.rs/crate/eldenring/latest/source/src/cs/chr_ins/module.rs | Container layout: `data` at `+0x0`, `time_act` at `+0x18` |
| [S3] | `eldenring` crate, `ChrIns` / `PlayerIns` — https://docs.rs/crate/eldenring/latest/source/src/cs/chr_ins.rs | `ChrIns.modules` at `+0x190`; `PlayerIns.player_game_data` at `+0x580` |
| [S4] | vswarte/fromsoftware-rs repository — https://github.com/vswarte/fromsoftware-rs | Parent project of [S1]–[S3]; Rust bindings for Elden Ring, Nightreign, Dark Souls 3, Sekiro |
| [S5] | VirusAlex/ERR-MapForGoblins-DLL, `KNOWLEDGE_EN.md` — https://github.com/VirusAlex/ERR-MapForGoblins-DLL/blob/master/docs/KNOWLEDGE_EN.md | Independent confirmation of `ChrModules` at `+0x190` (different build; RVAs there are not transferable) |
| [S6] | `eldenring` crate, `WorldChrMan` — https://docs.rs/crate/eldenring/latest/source/src/cs/world_chr_man.rs | `main_player` member; alternative root (§6) |
| [S7] | Elden Ring Wiki (Fextralife), "Stats" — https://eldenring.wiki.fextralife.com/Stats | Full names (Hit Points, Focus Points), stat descriptions, and governing attributes in §1.1. Community documentation, not an official publisher source |
| [P1] | Elden-Disk project (internal): `offsets.json`, stage 1 / animation-ID verification on 1.17.1 | Static RVA `0x3B16E30`, hops 0–2, and the verified sibling chains in §3.3 (local files; project folder `D:\StudioProjects\Elden-Ring-Telemetry-Tools\code`) |

## 10. Revision History

| Version | Date | Description |
|---|---|---|
| 1.0 | 2026-10-04 | Initial draft: pointer chain and offsets for HP / FP / Stamina, derived from [S1]–[S3] and cross-checked against project-verified chains [P1] |
| 1.1 | 2026-10-04 | Made the vitals block complete: all ten fields with full descriptions and per-value chains; added stat terminology with full names (§1.1, [S7]) |
| 1.2 | 2026-10-04 | Promoted chain and offsets to project-verified on 1.17.1 per project owner; added validation record (§7.1) with the V1 snapshot; closed Open Item 2 |

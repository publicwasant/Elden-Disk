> [!NOTE]
> **Version:** `1.8.4`  
> **Status:** Part 1 IMPLEMENTED (closed). Dismantle passed in the game and its design is locked (2026-10-17). Part 2 IMPLEMENTED
> (closed): Dismantle follows the lock-on, passed in the game (2026-10-17). Part 3 IMPLEMENTED (closed): the claw marks on the ones
> hit, passed in the game (2026-10-18). Part 4 IMPLEMENTED (closed): locked on, one cut circling the
> target, passed in the game (2026-10-18). Part 5 IMPLEMENTED (closed): the fan 120°, passed in the game (2026-10-18).  
> **Last Updated:** _2026-10-18_

# Elden-Disk spec 1.8.4: Dismantle

Reads on top of [spec 1.8.3](elden-disk-spec-v1.8.3.md). Only what changes is written here. The design:
[dismantle_and_cleave.design.md](../experiments/extensional/innovate-items/dismantle_and_cleave/dismantle_and_cleave.design.md).

- **Part 1:** Dismantle, the spell of slot 2, and what the builder needed for it (a field of a copied row may name a row of the
  game): sections 1 to 8.
- **Part 2:** Dismantle follows the lock-on: one target when locked on, the fan when not (`character.lock_on` and a script): sections
  L1 to L13.
- **Part 3:** Beast Claw's claw marks next to the blood on the ones hit (the script), comments in `customs.basic`: sections C1 to C7.
- **Part 4:** locked on, cut after cut: one cut circles the target and cuts it again and again: sections S1 to S8.
- **Part 5:** the fan 120° wide, the field of binocular vision: sections B1 to B3.

# Part 1: Dismantle (2026-10-17)

## 1. Idea

The author's design, after Ryomen Sukuna's technique: an invisible slash that cuts everything in front of the caster, near to very far,
buildings and living things alike, slash damage, blood. "A very dangerous spell" (the author, 2026-10-17).

Decided on the way (2026-10-17):

- **The game's own hit, no script.** The cut is Bullet, AtkParam_Pc and SpEffect rows made by the build: the game finds the targets
  and applies the damage, the seal's scaling, the bleed and the effects. Nothing is read or written while you play.
- **One spell, one motion.** A Magic row has one cast motion (`refType`), and the motions the design named (Catch Flame's on a tap,
  Bestial Sling's on a charge) cannot be charged, so one spell cannot play both.
- **Not in it:** the design's Cleave (a close cut taking a share of the target's HP, slot 3: built and tried, then dropped by the
  author); reading the characters around the player and the one locked on (`world.units`, `lock_on`: no stable place in the game's
  memory was found, and the spell does not need it); the design's chances (50% bleed, 80% double hit: the game has no chance per hit).

## 2. The spell

`code/creative.json`, slot 2, `dismantle` (`kind projectile`, `from` 6800):

| **What** | **Value** | **The rows** |
|:--|:--|:--|
| Made from | Bestial Sling (Magic and Goods 6800); its id in the game 2230001 | the copies of slot 2 |
| Cast | Catch Flame's flick of the hand; effect 4122 on the caster | `Magic.6800.refType` 106 (Bestial Sling's own: 38), `castSfxId` 4122 |
| Cuts | 38, 5° apart, from -92° to +93°, invisible | `Bullet.10680000`: `numShoot` 38, `shootAngle` -92, `shootAngleInterval` 5, `sfxId_Bullet` -1 |
| Reach | 100 m: 120 m/s for 0.84 s, always the same | `initVellocity` / `maxVellocity` 120, `life` 0.84, `lifeRandomRange` 0, `dist` 100 |
| Width | 1.5 m at the hand, 4.5 m at the end (100 m away two cuts are 8.7 m apart: no gap) | `hitRadius` 1.5, `hitRadiusMax` 4.5, `spreadTime` 0.84 |
| Through | characters, objects, the ground and walls; a target is hit once per cast | `isPenetrateChr`, `isPenetrateObj` (the template's), `isPenetrateMap` 1; `dmgHitRecordLifeTime` 999, shared (the template's) |
| No limit | the game's group 42 (2 at once, shared with other spells) is not used | `createLimitGroupId` 0 |
| Damage | 380 physical, slash, metal, scaled by the seal; the same at 100 m | `AtkParam_Pc.68000`: `atkPhys` 380, `atkAttribute` 0, `atkMaterial` 0 |
| Bleed | 60 per hit | `spEffectId0` = a copy of SpEffect 1625 (a game bullet's bleed), `bloodAttackPower` 60 |
| Blood | a burst of blood on every one hit, and nowhere else | `spEffectId1` = a copy of SpEffect 474 emptied (section 4) |
| Hit effect | none of the spell's own | `sfxId_Hit` -1 |
| Bestial Sling's homing stones | none | `Bullet.10680001.numShoot` 0, `sfxId_Bullet` / `sfxId_Hit` -1 |
| Requires, costs | Faith 60, Arcane 10, Intelligence 15; 20 FP | `requires.status`, `requires.cost` |
| Sold | Kale, once, 8,000 runes | `locations.kale` |
| Icon | Bloodboon's | `Goods.6800.iconId` 6254 (Bloodboon is Goods 6310; the Magic rows of both share 4021) |
| Texts | "Dismantle" and a short line; the long description is the author's | `customs.advanced.texts` |

## 3. What the game showed (2026-10-17, five tests)

| **Seen** | **Why** | **Now** |
|:--|:--|:--|
| A hit only at arm's length | a cut 1.5 m wide leaves the hand about 1.2 m above the ground: it touches the ground at once, and a bullet that hits the map ends there (Bestial Sling's own cut is 0.2 m wide) | `isPenetrateMap` 1, as most of the game's wide fast bullets |
| (read from the built row) the reach 31 to 41 m | Bestial Sling's `lifeRandomRange` 0.04 s | 0 |
| Bestial Sling's look on the target, no blood | what a hit looks like is the game's own, by the attack's material: Bestial Sling's is 6 (magic); swords, maces and daggers are 0 (metal) | `atkMaterial` 0, and Beast Claw's slash on the hit removed; still no blood on the target |
| A burst of blood in the air at all 38 cuts, the game stutters | effect 4080 (the burst of a hemorrhage) as `sfxId_Hit`: the game plays a bullet's hit effect also where it ends without hitting anything | the burst as a SpEffect of the bullet (section 4), which goes only to the ones hit |
| Too many cuts (68) | | 38 |
| Strong enough to kill Kale by accident | | locked |

- **Life -1** (asked): the game's 25 bullets with `life` -1 all end when they hit the map; a cut that goes through everything would never
  end, cross the map, pull enemies from far away and stay in the world (37 more every cast, with no limit of the game's group). The reach
  is `life` x speed.
- **Gravity, speed, obstacles** (asked, read from the built row): no gravity (`gravityInRange` / `gravityOutRange` 0), no speeding up or
  slowing down (`accelTime` 0), no loss of damage with distance (`damageDamp` 0), not erased by other bullets.
- **Lock-on:** the game turns the fan towards the locked target when it is within 30° of the front (`lockShootLimitAng`, the template's).

## 4. The burst of blood on the ones hit

A copy of **SpEffect 474** (a game row a bullet gives to the one it hits; it takes 50% of the max HP + 300 from characters in the game's
state 452), emptied:

| **Field** | **474** | **The copy** |
|:--|--:|--:|
| `changeHpRate`, `changeHpPoint` | 50, 300 | 0, 0 (takes nothing) |
| `invocationConditionsStateChange1` | 452 | 0 (on every target) |
| `effectEndurance` | 0 | 0.5 s |
| `vfxId` | -1 | 6: effect 4080 at the middle of the body (the visual of all 269 bleed SpEffects of the game) |

The bleed's own SpEffect (1625) has `vfxId` 6 too, but the game shows it only when the bleed fills up.

## 5. The builder: a field may name a row of the game

Bestial Sling's chain has no SpEffect row of its own, and sections 2 and 4 need copies of 1625 and 474. In `customs.basic` (and `set`), a
field of a copied SpEffect, Bullet or AtkParam_Pc row that calls another row may name a row of the game as text:

```json
"Bullet.10680000.spEffectId0": "SpEffect.1625",
"SpEffect.1625.bloodAttackPower": 60
```

- **The fields:** the ones the builder already points at the copies (`chain.SP_PAIRS`, `BULLET_LINKS`, `ATK_PAIRS`): a Bullet's
  `spEffectId0-4`, `spEffectIDForShooter`, `atkId_Bullet`, `HitBulletID`, `intervalCreateBulletId`; an AtkParam_Pc's `spEffectId0-4`;
  a SpEffect's `cycleOccurrenceSpEffectId`, `atkOccurrenceSpEffectId`, `replaceSpEffectId`. A number there is still refused.
- **The copy:** the named row is copied into the slot's own block of its table, after the chain's own rows, in the order the design names
  them (a row the chain copies already is not copied twice); the field points at the copy; keys `<Table>.<that id>.<field>` change the
  copy, never the game's row (other spells keep using it). Every copy that called the named row now calls its copy.
- **Two spells** naming the same row get a copy each, in their own blocks.
- **Errors** (each with the key where it is written): a name that is not a row of the game; a field that calls another table
  (`spEffectId0` names a Bullet); a name in a field that calls no row; a block that is full; a key of a row that is neither in the chain
  nor named (the message says how to name it).
- `spells.schema.json` takes the name; `spells.resolved.json` lists the copies with the rest; the gate checks them as every copy.
- **Code:** `spec.py` (`LINK_TARGET`, `ROW_REF_RE`, `TABLE_LABEL`, `_set`), `recipes.py` (`_named_rows`, called by `template_rows`).

## 6. What changes

| **Where** | **Change** |
|:--|:--|
| `code/eldendisk/creative/innovate_spells/spec.py` | a field that calls another row takes a row's name (section 5) |
| `code/eldendisk/creative/innovate_spells/recipes.py` | the rows named are copied into the slot (section 5) |
| `code/eldendisk/creative/innovate_spells/spells.schema.json` | a value of `set` / `customs.basic` may be such a name |
| `code/creative.json` | slot 2 `dismantle` (section 2) |
| `code/eldendisk/__init__.py` | `1.8.4` |
| `code/tests/test_spells_named_rows.py` | new (section 7) |
| `code/tests/test_write_sparks.py` | took room for one more spell by popping `"<id-2>"`, now the first empty slot |

Nothing else: no change to the reader, the disk, the scripts or the commands.

## 7. Tests

- **The design file:** a name kept as text (spaces and leading zeros taken off); a name of the wrong table, a number, a name in a field
  that calls no row, a name in a Magic field: refused, each saying why; the design shows the name back; the schema and the validator
  agree.
- **The recipe** (small tables): the named rows copied after the chain's own, the fields pointing at the copies, the game's row untouched,
  the chain's own links still remapped; a row the chain copies not copied twice; a named Bullet in the Bullet block, every copy that
  called it calling its copy; two spells, a copy each; a name that is no row, a full block, a key outside the chain: refused.
- **With the game's regulation.bin** (`ELDENDISK_REGULATION_ORIG`, read only): `creative.json` builds and passes the gate; Dismantle's row
  as section 2 (38 cuts, 100 m, the widths, through the map, no randomness, no gravity, 380 slash metal, the bleed, the emptied 474 with
  `vfxId` 6, the cast motion and effect, the requirements, Bloodboon's icon).
- The whole suite passes (1848, 109 skipped without the game's file).

## 8. Closing check (2026-10-17)

- **Optimization:** nothing to speed up. The copies cost one pass over the design's keys at build time and no extra read of the game's
  file; the gate checks them with the rest. In the game: no script; 38 bullets a cast and one burst of blood per target hit.
- **Tidied:** one table of the three names (`TABLE_LABEL`) in `spec.py` instead of two.

# Part 2: Dismantle follows the lock-on (2026-10-17)

## L1. Idea

Asked by the author (2026-10-17):

- **Locked on:** a single attack: all 38 cuts go at the one target, cast with **Catch Flame's** motion.
- **Not locked on:** the fan of part 1, cast with **Bestial Sling's** motion.
- A script switches between the two; the tool only has to say whether the player is locked on (not who the target is).

A Magic or Bullet row can be changed in the running game and the next cast uses it (1.8.3: `write params.Bullet...` tried live, no
build). So no new build: the build keeps part 1's rows, the script writes the fields of section L3 when the lock-on changes.

## L2. `character.lock_on`

```json
"character": { "level": 150, "lock_on": true, ... }
```

- **true** while the player is locked on to something, **false** when not. Nothing about the target.
- **Where:** the player's character (`PlayerIns`, which every sample already follows) **+0x6B0** holds the game's handle of the target
  while locked on: seen by the probes of the dropped `world.units` (two games, 0x3C2A2500_17300018). The field is 64 bits; what it
  holds when nothing is locked on was not seen (the probes printed only what changed): **locked = the field holds a handle** (neither
  half 0 nor 0xFFFFFFFF), to be checked first in the game (L7).
- **Read** every sample (8 bytes, nothing more). `offsets.json`: `"player_to_lock_on": "0x6B0"` in the 1.17.1 profile; a profile without
  it leaves `lock_on` out of the disk.
- `read lock_on` (and `read character.lock_on`), `tools.read().character.lock_on` in a script. Not writable.

## L3. The two modes

The rows are slot 2's copies (Magic 2230001, Bullet 500000016 = the copy of 10680000), found by the script in
`creative.innovate_spells.dismantle` (its `rows` and `copies`), never written as numbers in the script.

| **Field** | **Not locked on (part 1's fan)** | **Locked on** | **Why** |
|:--|--:|--:|:--|
| `Magic.refType` | 38 (Bestial Sling) | 106 (Catch Flame) | the author's two motions |
| `Bullet.shootAngle`, `shootAngleInterval` | -92, 5 | 0, 0 | 38 cuts straight at the target, on one line |
| `Bullet.homingAngle` | 0 | 720 | degrees a second a cut turns towards the target (it follows it) |
| `Bullet.lockShootLimitAng` | 30 | 180 | the cuts leave aimed at the target wherever it is around you |
| `Bullet.hitRadius`, `hitRadiusMax` | 1.5, 4.5 | 0.5, 0.5 | narrow: the target, not the ones around it |
| `Bullet.isUseSharedHitList` | 1 (a target once per cast) | 0 (each cut on its own: 38 hits) | see L8.2 |

Everything else (100 m, through everything, 380 slash, the bleed, the blood) stays as part 1. **The design's part 1 has `refType` 106 in
`creative.json`**; the script writes 38 when not locked on, so the build's file stays as locked (L8.4).

## L4. The script

A default script of the exe (`code/eldendisk/creative/scripts/defaults/dismantle_follows_the_lock_on.py`), as the colours of Reverse
Cursed Technique:

- `every = 0.1` s; `loop()`: `tools.read()`, `character.lock_on`; when it differs from the mode now, the fields of L3 for the other mode,
  one `tools.write`; nothing written while it stays the same.
- `setup()`: the mode of the lock-on now (written once); `teardown()`: back to the build's values (part 1), so the spell is as built
  when the scripts stop.
- No `dismantle` in the last build (the spell taken out of `creative.json`): the script logs it once and ends (`tools.dead()`).

**Timing:** a cast within 0.1 s of locking on or off may still use the mode before (the script has not seen it yet).

## L5. What changes

| **Where** | **Change** |
|:--|:--|
| `code/offsets.json` | `player_to_lock_on` 0x6B0 (1.17.1) |
| `code/eldendisk/game/profile.py` | the field (optional) |
| `code/eldendisk/reader/sampler.py`, `export.py`, `disk.schema.json` | `character.lock_on` read each sample, in the disk |
| `code/eldendisk/commands/read.py` | `read lock_on` |
| `code/eldendisk/creative/scripts/defaults/dismantle_follows_the_lock_on.py` | new (L4) |
| `code/creative.json` | nothing |

## L6. Tests

Fake memory: `lock_on` true with a handle at +0x6B0, false with 0, with 0xFFFFFFFF_FFFFFFFF and with a half of ones; left out without
the profile field; `read lock_on`. The script on a fake backend: setup writes the mode of the lock-on now; a change writes the fields of
L3 once and nothing while it stays; teardown writes part 1's values; no `dismantle` ends the script.

## L7. In the game (the author)

1. **First:** `eldendisk read lock_on` (or the monitor) while locked on and while not: true / false. If not, the log of `read -v` shows
   the value at +0x6B0 in both, and the rule of L2 is fixed on it.
2. Locked on: Catch Flame's motion, 38 cuts on the target only (one standing next to it untouched), a target moving to the side still hit.
3. Not locked on: Bestial Sling's motion, the fan of part 1.
4. Lock on and off between casts: each cast in the mode of the moment.

## L8. For the author to decide

1. **`lock_on` in the disk:** **`character.lock_on`, true / false** (default), or another name.
2. **Locked on, how many hits:** **38: each cut hits** (default, as asked: 38 x the cut, enough to kill almost anything in one cast, and
   38 x 60 bleed: a hemorrhage at once), or **1**: the 38 cuts together hit once (the target once per cast, as the fan).
3. **Locked on, how narrow:** **0.5 m** (default: the target only), or part 1's widths (the ones around the target are cut too).
4. **`creative.json`:** **stays as locked** (default: `refType` 106; the script writes 38 when not locked on; without the scripts the
   spell is Catch Flame's motion with the fan), or `refType` 38 in it (without the scripts: Bestial Sling's motion with the fan).
5. **The script:** **a default script of the exe, every 0.1 s** (default), or a script of `scripts.added` (outside the exe).

## L9. Decided by the author (2026-10-17)

1, 3, 4, 5: the defaults. 2: "if 38 hits play 38 bursts of blood at once, then 1 hit". The blood (and the bleed) is a SpEffect the cut
gives to the one it hits; the same SpEffect given again while it lasts most likely renews it rather than adding a second burst, but the
game's own hit (the flash and the sound of metal on flesh) plays at every hit. Not known before the game shows it, so **38 hits** first;
if the game shows 38 bursts or stutters, `isUseSharedHitList` locked on goes from 0 to 1 in the script (one value, L3).

## L10. Built (2026-10-17)

- `offsets.json`: `player_to_lock_on` 0x6B0 (and in its `_readme`); `profile.py`: `Profile.player_to_lock_on` (optional).
- `sampler.py`: `is_handle()`, `_read_lock_on()` every sample, `lock_on_raw` kept for the log; `character.lock_on` when the field can be
  read. `disk.schema.json`: `character.lock_on` (boolean). `values.py`: `lock_on` is a name of the character (`read lock_on`).
  `read.py`: `read -v` of a name with `lock_on` logs the 64 bits (`lock_on: PlayerIns +0x6B0 = 0x...`) for L7.1.
- `code/eldendisk/creative/scripts/defaults/dismantle_follows_the_lock_on.py` (`DismantleFollowsTheLockOn`, every 0.1 s): the fields of
  L3; the build's values from the design's `customs.basic`, else from the game at `setup()`; ends itself without `dismantle` in the
  build or without `character.lock_on`. The exe carries it from its next build (`tools/dev_pipeline.py` embeds every default script).
- `code/tests/test_lock_on.py`: the handle rule; `lock_on` in the sample and the disk (true, false for 0 and all ones), left out without
  the field or the memory; the 1.17.1 profile has it, a profile without it loads; the name; the script on a fake backend (setup, a change
  written once, nothing while it stays, teardown to the build, locked on at the start, no spell, no `lock_on`, out of the world).
- The whole suite passes (1869, 109 skipped without the game's file).

## L11. The motions, after the tests in the game (2026-10-17)

`character.lock_on` and the script passed in the game. Bestial Sling's motion (38) brought its own brown ring and sound and did not show
4122: its look is in the animation (the game's Bestial Sling has `castSfxId` and `fireSfxId` -1), not in the spell's rows, so no field
can take it off. Of the 84 cast motions of the game's incantations, 49 take their look from the spell's rows (every game spell of
them has a `castSfxId`); the author tried them live (`write params.Magic.2230001.refType=N`) and decided:

- **Locked on: 25**, the motion of O, Flame! (it can be charged in the game: a held cast may fire nothing).
- **Not locked on: 106**, Catch Flame's, the build's (`creative.json` unchanged): the script writes `refType` only when locked on and
  puts the build's back when not.

## L12. Closed (2026-10-17)

Passed in the game: `character.lock_on` true / false, the script switching the modes, the motions of L11. Locked on, the 38 cuts all
hit: 38 x 380 before the seal ("can order anything in this world to die", the author).

## L13. Locked on costs 2.5 times the FP (2026-10-17)

Asked by the author: locked on, a cast costs the build's FP x 2.5 (`creative.json` 60 now: 150). The script writes `Magic.mp` with the
other fields of L3: `round(built x LOCKED_FP)`, LOCKED_FP 2.5; not locked on (and at `teardown()`), the build's. The build's FP is the
design's `requires.cost.focus_point` (so a script started again while locked on does not take the locked value for the build's), else
what the game holds at `setup()`. Tests: `test_lock_on.py` (60 / 150, a start while locked on, a design without a cost).

# Part 3: the claw marks on the ones hit (2026-10-18)

## C1. Idea

Asked by the author (2026-10-17): on the ones Dismantle hits, next to the burst of blood, a slash. Chosen in the game among the hit effects
of the game's purely physical spells (Bestial Sling 529523, Beast Claw 530172 / 530177, Pest Threads 526303, Aspects of the Crucible:
Thorns 540103, Pest-Thread Spears 541013 / 541018, Divine Bird Feathers 541353), tried live by borrowing the frostbite's visual (260):

- **Not locked on: 530172**, Beast Claw's claw marks.
- **Locked on: 530177**, the charged Beast Claw's, bigger.

"It comes one step closer to the real Dismantle" (the author, after the test).

## C2. Why a visual row, and which

- A bullet's own `sfxId_Hit` plays also where a cut ends without hitting anything (part 1, section 3: 38 bursts in the air, a stutter), so
  the marks must be a visual of the SpEffect the cut gives to the ones it hits (the copy of 474, part 1 section 4): one of its visual
  fields (`vfxId1`; `vfxId` is the blood) shows a SpEffectVfx row.
- No SpEffectVfx row of the game plays the hit effect of a spell (all 1,513 looked at): the marks need a row that plays 530172 / 530177.
- **SpEffectVfx 999999999**, the game's debug row: no SpEffect of the game shows it and it plays nothing (all its effects -1). The script
  makes it the claw marks in the running game; the game's file keeps it as it is.

## C3. The script

`DismantleFollowsTheLockOn` (part 2) writes, with the other fields of its two modes:

| **Row** | **Field** | **Not locked on** | **Locked on** | **Why** |
|:--|:--|--:|--:|:--|
| the copy of SpEffect 474 (21951009) | `vfxId1` | 999999999 | 999999999 | the blood's SpEffect also shows the marks |
| SpEffectVfx 999999999 | `midstSfxId` | 530172 | 530177 | Beast Claw's marks / the charged one's |
| | `midstDmyId` | 220 | 220 | at the middle of the body, as the blood |
| | `existEffectForLarge` | 1 | 1 | on big enemies and bosses too |
| | `isVisibleDeadChr` | 1 | 1 | on the cut that kills, too |

`teardown()`: `vfxId1` as built (-1) and the row as the game's file has it (all -1 / 0). Without the scripts, the blood alone (part 1).

## C4. Tried and dropped: the marks in the build (2026-10-18)

The author asked first for the marks in `creative.json` (`"SpEffect.474.vfxId1": "SpEffectVfx.6"`, `"SpEffectVfx.6.midstSfxId": 530172`,
the builder copying the game's visual 6 into slot 2's own block). Built and tested by the tests, it grew a seventh table of
regulation.bin: **28 re-encoded blocks**, one more than the gate's 27 (the most the game was seen to load, T10). The gate stopped `run`,
as it must; a test file of exactly that design (`tools/envelope_test.py --no-copies`, T11) took the game as far as the world. The author:
too much for an effect the script gives; the builder change was taken out (it knows six tables again) and the script's way kept. The
gate stays at 27; the design builds with **26** re-encoded blocks (body +124,560, frame +214,528).

## C5. Comments in `customs.basic`

Asked by the author: `"__info_<part>__": "..."` at the head of each group of keys of `customs.basic`, saying what that part is and how
it works. The validator takes a key `__info_<letters, digits, _>__` there as a comment (text, never read; one that is not text is an
error), the schema too. Dismantle's `basic` in seven parts: `__info_cast__`, `__info_fan__`, `__info_cut__`, `__info_bleed__`,
`__info_blood__`, `__info_claw_marks__` (no keys: it says the script makes them), `__info_stones__`; the general `__info__` first.

## C6. Found on the way

A session without a build of its own (`run --regulation FILE`) has no `creative.innovate_spells`: both default scripts
(`DismantleFollowsTheLockOn`, `RctColoursFollowTheSpell`) died on it, and the colours' `teardown()` failed again after a `setup()` that
had ended early. Now they log it (`... no build of its own ...`) and end; `teardown()` does nothing then.

## C7. What changes, tests, closing

| **Where** | **Change** |
|:--|:--|
| `code/eldendisk/creative/scripts/defaults/dismantle_follows_the_lock_on.py` | the claw marks (C3); the quiet end (C6) |
| `code/eldendisk/creative/scripts/defaults/rct_colours_follow_the_spell.py` | the quiet end and `teardown()` (C6) |
| `code/eldendisk/creative/innovate_spells/spec.py`, `spells.schema.json` | the comments of `customs.basic` (C5) |
| `code/creative.json` | Dismantle's `basic` in parts (the numbers unchanged) |
| `code/tests/test_lock_on.py`, `test_spells_structure.py` | the marks in both modes and at `teardown()`, the quiet end of both scripts, the comments |

The whole suite passes (1887, 109 skipped without the game's file); with the game's file, the design builds and passes the gate (26
blocks). **Passed in the game (2026-10-18):** the marks on the ones hit, 530172 in the fan, 530177 locked on.

# Part 4: locked on, cut after cut (2026-10-18)

## S1. Idea

Asked by the author: locked on, the target looks cut **once**, though all 38 cuts go at it and hit it (when it does not dodge). It
should be cut cut cut cut, one cut after the other, as many times as the cuts that hit.

## S2. Why it looks like one cut now

Locked on, the 38 cuts leave the hand together on one line (part 2, L3: `shootAngle` 0, `shootAngleInterval` 0) and each hits on its
own (`isUseSharedHitList` 0): 38 hits in the same instant. The damage is there, but the game shows one moment: one flinch, the numbers
added up, the blood and the claw marks once (the same SpEffect given again while it lasts).

## S3. The way: `shootInterval`

A Bullet row with `numShoot` > 1 can fire its shots **one after the other**: `shootInterval` = the seconds between two (f32; 1,254 rows of
the game use it, such as 20 shots every 0.1 s or 36 every 0.02 s). Dismantle's is 0 (all at once, the fan). The script adds it to the
locked-on mode, as the other fields of L3:

| **Field** | **Not locked on** | **Locked on** |
|:--|--:|--:|
| `Bullet.shootInterval` | 0 (the build's: the fan at once) | **0.05**: one cut every 0.05 s, the 38 in 1.9 s |

- Each cut then hits on its own, in its own instant: a flinch, a number, the blood and the claw marks each time (the SpEffect lasts 0.5 s,
  so at 0.05 s it is still there when the next cut comes: to be seen whether the blood shows again each time; 0.5 s may be shortened).
- A target that dies early: the cuts still to come fly on (at what is behind it on that line, 0.5 m wide).
- To be seen in the game: where the later cuts start (from where the hand was at the cast, or from the hand now), and whether a cast
  while the cuts of the one before are still coming has its own (`createLimitGroupId` 0: no limit).

## S4. What changes

`dismantle_follows_the_lock_on.py`: `("Bullet", "shootInterval"): (None, INTERVAL)` in MODES, INTERVAL at the head of the file;
`test_lock_on.py`. No build, no `creative.json`.

## S5. For the author to decide

1. **The rhythm:** **0.05 s** (default: 20 cuts a second, 38 in 1.9 s), or faster (0.03: 1.1 s), or slower (0.1: 3.8 s).
2. **The blood each cut:** **as it is** (default: the SpEffect lasts 0.5 s; see in the game), or 0.04 s locked on so it comes again with
   each cut (`SpEffectParam.<copy of 474>.effectEndurance`, written by the script).

## S6. Decided and built (2026-10-18)

Both defaults: **0.05 s** between two cuts; the blood as it is. `dismantle_follows_the_lock_on.py`: `INTERVAL = 0.05` at the head,
`("Bullet", "shootInterval"): (None, INTERVAL)` in MODES (not locked on, and at `teardown()`: the build's 0). `test_lock_on.py`: the
locked-on mode writes 0.05, the fan the build's 0. The whole suite passes (1887). The exe carries the script from its next build.

## S7. What the game showed, and the cut that circles (2026-10-18)

| **Tried (live writes, locked on)** | **Seen** | **So** |
|:--|:--|:--|
| S6: `shootInterval` 0.05 | one cut | |
| + `dmgHitRecordLifeTime` 0.04 | one cut | not the hit record alone |
| + the blood 0.04 s | the claw marks 2 or 3 times | the cuts do hit again, but few |
| `shootInterval` 0.1 | exactly 2 | **the cast lets a bullet fire its shots for about 0.1 s only**: the rest are never fired |
| one cut that stops on the target (`isPenetrateChr` 0) and leaves a still cutting zone (`HitBulletID` = the copy of 10680001, still, 1.85 s, re-hit 0.05 s; the Magic's `refId2` -1) | the first cut hits, the zone never appears (made visible: nowhere) | **a `HitBulletID` written in the running game is not used** (the game seems to prepare the bullets a bullet creates when it loads) |
| **one cut, 30 m/s, turning 1440°/s, never stopping to follow (`hormingStopRange` 0), through characters, re-hit 0.05 s, 3.5 s** | it reaches the target and circles it, cut cut cut, the HP going down step by step | **the author: "this is it"** |

**The locked-on mode now** (the script, in place of S6's `shootInterval`):

| **Field (Bullet 500000016 unless said)** | **Not locked on (the build's)** | **Locked on** |
|:--|--:|--:|
| `numShoot`, `shootAngle`, `shootAngleInterval` | 38, -92, 5 | 1, 0, 0 |
| `initVellocity`, `maxVellocity`, `life` | 120, 120, 0.84 | 30, 30, 3.5 (`SPEED`, `LIFE`) |
| `homingAngle`, `homingBeginDist`, `hormingStopRange` | 0, 0, 0 (the template's) | 1440, 0.1, 0 (`TURN`; 0.1 as Bestial Sling's homing stones; 0 as Elden Stars) |
| `lockShootLimitAng` | 30 | 180 |
| `hitRadius`, `hitRadiusMax` | 1.5, 4.5 | 1.0, 1.0 |
| `isUseSharedHitList`, `dmgHitRecordLifeTime` | 1, 999 (the template's) | 0, 0.05 (`REHIT`) |
| SpEffect copy of 474: `effectEndurance` | 0.5 | 0.04 (the blood bursts again with each cut) |

- **How many cuts:** no longer 38: one cut every 0.05 s while it circles, for what is left of its 3.5 s after the way there (30 m: 1 s,
  then about 50 cuts; point blank about 70). The number follows the distance.
- The build's values of the fields the design does not name are the template's own (`TEMPLATE` in the script), so a script started
  again while locked on does not take the locked-on values for the build's.
- Not used any more: `shootInterval`, `HitBulletID`, the Magic's `refId2` (as built).
- Tests: `test_lock_on.py` (both modes, the fan back as built after a start while locked on). The whole suite passes.

## S8. Closed (2026-10-18)

Passed in the game with the script built in (the build that came after S7 had first stopped on three tests that held the FP of
locked on at 150; the author had set `LOCKED_FP` 1.8: the tests now read the numbers at the head of the script). The author tried the
speeds live, the turn following them so that the circle stays about 1.2 m (`homingAngle` = speed x 48): 30 / 1440, 60 / 2880,
90 / 4320, 120 / 5760, and chose **120 m/s, 5760° a second**: the same speed as the fan, a target 30 m away reached in 0.25 s.

| **At the head of `dismantle_follows_the_lock_on.py`** | **Value** |
|:--|--:|
| `LOCKED_FP` (the author's) | 1.8 |
| `REHIT` | 0.05 s |
| `SPEED` | 120 m/s |
| `TURN` | 5760 °/s |
| `LIFE` | 3.5 s |

Also on the way: Dismantle's cut 280 (`AtkParam_Pc.68000.atkPhys` in `creative.json`, the author's; the test with the game's file reads
it from `creative.json`).

# Part 5: the fan 120° wide (2026-10-18)

## B1. Idea

The author: by binocular vision, the middle part where what both eyes see overlaps, about 120°, is where the brain works out depth
(stereopsis). Dismantle's fan cuts that field, not the edge of sight: from 185° (38 cuts 5° apart, -92° to +93°) to 120°.

## B2. The fan

The angle between two cuts is a whole number of degrees, so 38 cuts cannot fill 120° (3°: 111°, 4°: 148°). The ways that fill it, from
-60° to +60°, each cut grown at the end so that two cuts meet 100 m away:

| **Cuts** | **Apart** | **Apart 100 m away** | **`hitRadiusMax`** |
|--:|--:|--:|--:|
| 25 | 5° | 8.7 m | 4.5 m |
| **31 (chosen)** | **4°** | **7.0 m** | **3.5 m** |
| 41 | 3° | 5.2 m | 2.6 m |

Decided by the author: **31 cuts, 4° apart**. `creative.json`: `Bullet.10680000.numShoot` 31, `shootAngle` -60, `shootAngleInterval`
4, `hitRadiusMax` 3.5; `__info_fan__` says why 120° (binocular vision), the spell's `__info__` the new fan.

- What is at your side (more than 60° from the front) is not cut by the fan; locked on, the cut that circles (part 4) reaches it.
- 31 bullets a cast, 7 fewer than before.

## B3. Tests

The test with the game's file: the fan 31 / -60 / 4, its width 1.5 m to 3.5 m. The whole suite passes (1888).

**Passed in the game (2026-10-18).**

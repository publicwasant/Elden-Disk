> [!NOTE]
> **Version:** `1.8.4`  
> **Status:** Part 1 IMPLEMENTED (closed). Dismantle passed in the game and its design is locked (2026-10-17).  
> **Last Updated:** _2026-10-17_

# Elden-Disk spec 1.8.4: Dismantle

Reads on top of [spec 1.8.3](elden-disk-spec-v1.8.3.md). Only what changes is written here. The design:
[dismantle_and_cleave.design.md](../experiments/extensional/innovate-items/dismantle_and_cleave/dismantle_and_cleave.design.md).

- **Part 1:** Dismantle, the spell of slot 2, and what the builder needed for it (a field of a copied row may name a row of the
  game): sections 1 to 8.

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

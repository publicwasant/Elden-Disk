> [!NOTE]
> **Version:** `1.8.3`  
> **Status:** IMPLEMENTED (closed). Part 1, part 2 and the heal by share passed in the game (2026-10-17).  
> **Last Updated:** _2026-10-17_

# Elden-Disk spec 1.8.3: sparks when Reverse Cursed Technique is cast, and `colors` as the game holds them

Reads on top of [spec 1.8.2](elden-disk-spec-v1.8.2.md). Only what changes is written here.

- **Part 1:** a burst of sparks when the cast ends (effect 4271 on the second bullet): sections 1 to 7.
- **Part 2:** the `colors` block as the game holds its colours: every colour place of an effect, each writable: sections C1 to C8.

# Part 1: a burst of sparks when Reverse Cursed Technique is cast (2026-10-17)

## 1. Idea

Asked by the author (2026-10-17): when Reverse Cursed Technique finishes its cast, a burst of small sparks comes too; everything the spell
already has (the blue fire, the ring of runes, the eyes, the heal over time, the texts) stays as it is. The first wish was the blue sparkles
of Torrent; after trying the effects in the game (section 2) the author chose **4271** (a burst of ice shards with sparks), **in the
spell's main colour**.

## 2. What was tried in the game (2026-10-17)

Each effect was put live on the spell's second bullet (`write params.Bullet.500000001.sfxId_Bullet=N`, no build) and cast:

| **Effect** | **Where it was found**                                                      | **Seen in the game**                    |
|-----------:|:----------------------------------------------------------------------------|:----------------------------------------|
| 680035, 680030 | Torrent's animations (`c8000`, dummy 900)                               | a burst of smoke; a small whirlwind     |
| 525002     | Heal's own bullet                                                           | a big golden ring (shows the second bullet carries an effect) |
| 8020, 8030, 8031 | SpEffects on the horse's dummies (1100, 1110, 1111)                   | golden things                           |
| 4122       | 9 effects only the game's program names (below)                             | smoke as a fire is lit, a little slow   |
| **4271**   | the same                                                                    | **a burst of ice shards with sparks: chosen** |
| 4631       | the same                                                                    | a burst of fire sparks, golden          |
| 4091, 4282, 4712, 4732, 4161, 400003 | the same                                          | not chosen                              |

- Torrent's own sparkles were not found: no param table and no animation (the player's or Torrent's) names them, so the game's program
  plays them itself. The 9 effects tried last are the ones of the common effect archive that no table and no animation names and whose
  number the program writes in its own instructions (2,316 effects named by nothing, 23 of them in the program, 9 with textures).
- An effect on the buff's SpEffectVfx row (`initSfxId`) plays on the body, but only when the buff starts, not at a cast while it lasts
  (seen in the game). The second bullet plays at every cast: it is the place.

## 3. The spark burst in the build

One new line of `customs.basic` in `creative.json`; nothing set before is changed:

```json
"Bullet.10642101.sfxId_Bullet": 4271
```

- The spell's second bullet (10642101, copied to 500000001: Heal's ring of 6 m around the caster) has no effect of its own in the game's
  row; it gets 4271. It plays around the caster the moment the cast ends, at every cast.
- `customs.basic` already takes `Bullet.<id>.<field>` for a projectile: no new code for the build. It builds `regulation.bin` again at
  the next `run` (about 5 s).

## 4. Its colour: the spell's main colour

4271 is ice: white and light blue in the game's file. Like the fire, its colours are changed in the running game (Level 3,
`innovate-spells apply`), at the places a plan lists.

- **The plan:** `tools/fxr_places.py` on `f000004271.fxr` (common effect archive, 1.17.1): 39 colours (2 of them bloom). Added to
  `writer/fxr_plans.py` as `SPARK_PLANS` ("the effects a design puts on its spell that are painted in its main colour").
- **How a colour changes:** as for the fire (`writer/fxr.py` `recolor`), with one more colour for the white parts (`accent`); alpha is
  never touched; a bloom colour takes `main`. 4271 has many white parts (the bright core of the shards: `accent`).
- **Which colour (section 7):** a key of its own, `colors."Bullet.10642101.sfxId_Bullet"`: `{"main": "#90D5FF", "accent": "#E0F3FF"}`
  (or one colour: `main` only, the white parts stay white). `main` is the colour of the tinted parts, `accent` the colour of the white
  parts: new RGB = v × (w × accent + (1 − w) × main), v the brightness, w how white the colour is (`recolor`, `white`). Checked: the key
  must be `Bullet.<id>.sfxId_Bullet` of a copied bullet that `customs.basic` gives an effect with a plan (4271).
- **When an effect is painted:** when the design's `customs.basic` puts it on its spell (any `...sfxId...` field set to an effect that has
  a spark plan): today only 4271.
- **In the same look** as the fire, the ring and the eyes (`run`, `innovate-spells apply`): no second look through the memory. Like the
  ring, the game may not hold the file yet; it is then painted when it is found (the log says it).
- **Only while the spell is selected (section 7.3):** the script `RctColoursFollowTheSpell` gives the sparks their colours with the
  fire's when the spell is selected, and the game's own (ice) when another spell is (`tools.write` of the key repaints 4271 from the
  cache, no look through the memory). The script takes every `Bullet.<id>.sfxId_Bullet` key of the spell's colours with the fire's.
- **Shared:** 4271 is an effect of the game (its program plays it; where was not found). While the spell is selected, the game's own use
  of 4271 at that moment is in the spell's colours too (as for the fire); a separate copy of the effect under a number of its own would
  need a file added to the game's effect archive, which the tool does not touch.

## 5. What changes

| **What**                                     | **Where**                                                                 |
|:---------------------------------------------|:--------------------------------------------------------------------------|
| the line of section 3, the colours, `__info__` | `code/creative.json`                                                    |
| the key `Bullet.<id>.sfxId_Bullet` of `colors` | `creative/innovate_spells/spec.py` (`spark_color`, `SPARK_EFFECTS`), `spells.schema.json`, `live.py` |
| the plan of 4271                             | `writer/fxr_plans.py` (`SPARK_PLANS`), `writer/fxr.py` (`spark_ids`)      |
| painted in the same look                     | `commands/write.py` (`_put_flame`), `commands/run.py`, `creative/innovate_spells/service.py` (`spark_color`) |
| a script repaints it from the cache          | `creative/scripts/backend.py` (`_colour`: `spark`, `spark_accent`)         |
| the sparks follow the spell                  | `creative/scripts/defaults/rct_colours_follow_the_spell.py` (and its copy in `tests/external_scripts`) |
| the log: `spark colour: ... 4271 ...`        | `commands/write.py`                                                       |
| docs                                         | `docs/handbook/innovate-items-handbook.md` (19.8), `changes-version-1.8.3.md` |

## 6. Tests

`tests/test_write_sparks.py`:

- The plan: 39 places in the file; `recolor` gives the white parts `accent` and the tinted parts `main` (white stays white without one).
- `_put_flame`: the sparks with both colours in the same look as the fire; the sparks alone; a game that does not hold them (a log line,
  the fire still painted); an effect without a plan (a warning, nothing written).
- Back to the game's own and to the spell's colours from the cache (`repaint`), byte for byte.
- The design: the key read, written back (`design_of`), not part of the build; refused with the reason (an effect without a plan, no
  effect on the bullet, an unknown field, no `main`); `service.spark_color`.
- The script (both copies): the sparks go to the game's own and back with the fire; `live.target` names the key.
- In the game: the cast with the blue spark burst, ice again with another spell selected, and the fire, the ring and the eyes as before.

## 7. Decided by the author (2026-10-17)

1. **The colour:** a key of its own, `colors."Bullet.10642101.sfxId_Bullet"`.
2. **The white parts:** the colour #E0F3FF (`accent` of that key); the tinted parts #90D5FF (`main`).
3. **Shared with the game:** the spell's colours only while the spell is selected; the game's own ice otherwise, as the script does
   for the fire.

"Magic.6421.castSfxId": { "0x4290": [1.0, 0.5, 0.25, 0.075], "0x4334": "#90D5FF", ... },
"Magic.6421.fireSfxId": { ... 82 จุด },
"SpEffectVfx.20090050.midstSfxId": { ... 16 จุด (ดวงตา) },
"Bullet.10642101.sfxId_Bullet": { ... 39 จุด },
"Sfx.515000": { ... }, "Sfx.515001": { ... }   (วงแหวน ไม่มี param ไหนชี้ถึง)

Part 1 passed in the game (2026-10-17): the sparks at every cast, in the spell's colours.

### The heal as a share of the maximum (asked after part 2, 2026-10-17)

The heal of the buff (SpEffect 1642100, its copy) changes from fixed numbers to a share of the maximum, at every heartbeat (`motionInterval`
0.5 s, as before), in `customs.basic` (the game's own fields of the SpEffect row; negative heals, as the game's rows do: -100 is the
full restore of a Site of Grace):

| **Field**                              | **Before**  | **Now**   | **Meaning**                                   |
|:---------------------------------------|------------:|----------:|:----------------------------------------------|
| `SpEffect.1642100.changeHpRate`        | (0)         | -25.0     | 25 % of max HP every 0.5 s                    |
| `SpEffect.1642100.changeMpRate`        | (0)         | -25.0     | 25 % of max FP every 0.5 s                    |
| `SpEffect.1642100.changeStaminaRate`   | (0)         | -38.0     | 38 % of max stamina every 0.5 s               |
| `SpEffect.1642100.changeHpPoint`       | -45         | 0         | no fixed HP on top (left out, Heal's own -230 would come back) |
| `SpEffect.1642100.changeMpPoint`       | -15         | 0         | no fixed FP on top                            |

- Read as the share of each one's own maximum (the message said "of max hp" for FP and stamina too; taken as a slip, to be confirmed).
- `staminaRecoverChangeSpeed` 100 is kept (how fast stamina comes back by itself, apart from the heal).
- The sign of `changeStaminaRate` (negative gives) follows HP and FP; the game's rows hardly use it: to be seen in the game.
- A change of `customs.basic`: the next `run` builds again (about 5 s).

# Part 2: `colors` as the game holds them (2026-10-17)

Asked by the author after part 1: the `colors` block of `customs.advanced` as close to the game as it can be. A key names where the game's
own params point at an effect; under it, **every colour of that effect file**, each one writable, so the colours can be changed freely.

## C1. What it was (1.7.1 to part 1), and why it changes

`main` and `accent` were **the tool's own words**, not the game's. An effect file (`f000<id>.fxr`) holds its colours as RGBA floats at
fixed places (`writer/fxr_plans.py`: the places of each file). One colour was spread over many places by a rule (`recolor`: each place
keeps its brightness, white stays white):

| **Key (part 1)**                 | **Effect file(s)**            | **`main`**                               | **`accent`**                                   |
|:---------------------------------|:------------------------------|:-----------------------------------------|:-----------------------------------------------|
| `Magic.6421.castSfxId`           | 524400 and 524401 (the fire)  | 72 places of the two files               | 32 places `main` leaves out, and the ring of runes (515000, 515001: 79 places) |
| `SpEffect.1642100` (one colour)  | 4866 (the eyes)               | its 16 places                            | (none)                                         |
| `Bullet.10642101.sfxId_Bullet`   | 4271 (the sparks)             | its 39 places, tinted parts              | the white parts of the same places             |

- `accent` meant two different things (other places, or the white parts of the same places).
- `SpEffect.1642100` named the buff row, not the effect, and did two things: the build put the eyes on that row, and their colour. The
  eyes are 4866, which the game plays through SpEffectVfx 20090050 and 20090051 (`midstSfxId`, on the eyes' dummies 845 and 846).
- The ring of runes (515000, 515001) is played by the cast animation of fire incantations: no param of the spell names it.

## C2. The new block

A key is the param field that points at the effect (the template's row id, as in `customs.basic`); under it, one entry per colour place
of the file, named by its offset in the file, its value the colour that place has:

```json
"colors": {
  "__info__": "...",
  "Magic.6421.castSfxId": { "0x4290": [1.0, 0.5, 0.25, 0.075], "0x4334": "#90D5FF", ... },
  "Magic.6421.fireSfxId": { ... },
  "SpEffectVfx.20090050.midstSfxId": { ... },
  "Bullet.10642101.sfxId_Bullet": { ... },
  "Sfx.515000": { ... },
  "Sfx.515001": { ... }
}
```

| **Key**                            | **Effect** | **Places** | **Where the game names it**                                   |
|:-----------------------------------|-----------:|-----------:|:--------------------------------------------------------------|
| `Magic.<from>.castSfxId`           | 524400     | 22         | the spell's Magic row (`castSfxId`, set in `customs.basic`)  |
| `Magic.<from>.fireSfxId`           | 524401     | 82         | the spell's Magic row (`fireSfxId`, set in `customs.basic`)  |
| `SpEffectVfx.20090050.midstSfxId`  | 4866       | 16         | the eyes' SpEffectVfx rows (20090051 shows the same file)     |
| `Bullet.<id>.sfxId_Bullet`         | 4271       | 39         | a copied bullet (`sfxId_Bullet`, set in `customs.basic`)      |
| `Sfx.515000`, `Sfx.515001`         | 515000, 515001 | 30, 49 | no param: the cast animation of fire incantations            |

- **The effect of a key** is the one `customs.basic` sets in that field (`Magic`, `Bullet`), 4866 for the eyes, the number for `Sfx`; it
  must be an effect with a plan (524400, 524401, 4866, 4271, 515000, 515001); the same effect under two keys is refused.
- **A place** is named by its offset in the file as `"0x4290"`; it must be one of the plan's places of that effect.
- **A value:** `[red, green, blue, alpha]` as the file holds it (floats, 0 to 100; above 1 shines brighter), or `"#RRGGBB"`: that place
  keeps its own brightness and alpha (new RGB = v x the colour, v the biggest of its own R, G, B). A place not written keeps the game's
  colour. (Decided: both forms.)
- **No `main` / `accent`** (decided): a design of part 1 is refused with the reason and the way to write it now.
- **Only the colours** are in `colors`: never part of the build; changing them never builds again.

## C3. The eyes in the build

The build puts the eyes on a buff row; that was said by the key `SpEffect.<id>` of `colors`. Now by the game's own fields in
`customs.basic`, the ones the build writes:

```json
"SpEffect.1642100.vfxId1": 20090050,
"SpEffect.1642100.vfxId2": 20090051
```

- Both are needed (both eyes), on the same copied SpEffect row, in two of `vfxId1` ... `vfxId7`; the build puts them in the free fields
  of the copy as before (the same file as part 1 for the design of today: the copy of 1642100 has all seven free).
- Their colour: the key `SpEffectVfx.20090050.midstSfxId` of `colors`.

## C4. In the running game

- **`run` / `innovate-spells apply`:** every key's places written in ONE look through the memory, as before (the fire and the eyes
  required, the ring and the sparks painted when the game holds them). A copy counts only when every place of the plan holds the game's
  own colours or the colours of the design.
- **`read creative.innovate_spells.<goods>.design.customs.advanced.colors`:** every place of every key of the design, with the colour the
  game's copy has now (`[r, g, b, a]`, from the copies the tool painted), so a design can start from the game's values.
- **`write ...colors.Magic.6421.castSfxId.0x4290=[0.5, 0.8, 1, 0.075]`** (or `"#90D5FF"`), `=default` for the game's own; a whole key
  (`...colors.Magic.6421.castSfxId=default`); scripts the same (`colors["Magic.6421.castSfxId"]["0x4290"] = ...`, `colors[key] = None`).
  Written at the copies `run` painted (the cache), each place checked first and read back after.
- **The script `RctColoursFollowTheSpell`:** saves every key of the spell (but the eyes) and gives the game's own back when another spell
  is selected, the design's when the spell is selected again.
- **The eyes:** a colour written while the eyes glow may show only when the buff starts again (to be seen in the game).

## C5. `code/creative.json`

The colours of part 1 written as places, so the game looks the same: every place of 524400, 524401, 4866, 4271, 515000 and 515001 as
a hex colour (asked by the author after the first conversion to `[r, g, b, a]`): the place keeps its own brightness and alpha, so the
colour of part 1 comes back to half a step of 1/255 in each channel (238 places, none needed numbers). Any of them can then be changed
on its own; a place that needs another alpha or more brightness than its own is written as `[r, g, b, a]`.

`read` shows a place the same way: hex when a hex colour gives what the game's copy holds, `[r, g, b, a]` otherwise
(`backend.shown_place`).

## C6. What changes

| **What**                                                       | **Where**                                                              |
|:---------------------------------------------------------------|:-----------------------------------------------------------------------|
| the block read, checked, written back; the eyes from `customs.basic` | `creative/innovate_spells/spec.py`, `spells.schema.json`         |
| the colours of each effect, by place                           | `creative/innovate_spells/service.py` (`colours`)                      |
| a colour per place, the look and the writes                    | `writer/fxr.py`, `commands/write.py`, `commands/run.py`                |
| one place or a key written live, `=default`, the cache by place | `creative/innovate_spells/live.py`, `creative/scripts/backend.py`, `writer/cache.py` |
| the script                                                      | `creative/scripts/defaults/rct_colours_follow_the_spell.py`            |
| the design                                                      | `code/creative.json`                                                   |

## C7. Tests

- The block: each key and its effect; a place not in the plan, a value out of range, the same effect twice, `main` / `accent`, an effect
  without a plan: refused with the reason; written back as read; never part of the build.
- The eyes from `customs.basic` (both, one row; one alone refused).
- The writes of a design: exactly the places given, `[r, g, b, a]` and `"#RRGGBB"`; a look finds a copy painted before.
- Live: one place, a whole key, `=default`, a copy the game reloaded.
- The script with every key.
- `code/creative.json`: the places give the same bytes as the colours of part 1.

## C8. Decided by the author (2026-10-17)

1. `main` / `accent`: gone, every place on its own.
2. A value: `[r, g, b, a]` or `"#RRGGBB"`.
3. The name of a place: its offset in the file (`"0x4290"`).
4. The ring of runes: `Sfx.515000` and `Sfx.515001` (the default; not answered).
5. In 1.8.3, as its part 2.
6. The eyes in the build: `customs.basic` `SpEffect.<id>.vfxId<n>` = 20090050 and 20090051 (proposed with the work; to be confirmed).

## C9. Found while doing it

- **`spells.resolved.json` after a build used again.** The colours and the texts are not part of the build, so a design that changed only
  them builds nothing, and the record of the last build kept the design as it was then: `read` and the scripts saw the old `colors`.
  Now, when `run` uses a build again, the design in that record is written as it is now (`service.refresh_designs`; the ids and rows
  stay the build's).
- **Where the plans are checked.** The creative package may not import the writer (tests/test_architecture.py), so the reading of the
  design checks the keys and the values; whether an effect has a plan and a place is one of it is checked by `innovate-spells apply`
  before it attaches (`commands/write.py` `check_places`).
- **The script example `eyes_follow_hp.py`** (tests/external_scripts) writes every place of the eyes' key with one hex colour.

## C10. Closing check (2026-10-17)

Nothing to optimize: the colours are put in the same one look as before; a script's change of colour writes each copy in one piece
(`repaint_places`, no look); the doc reads one small block per key from the copies the cache knows. One thing made smaller: `run`
decided twice whether the last build is still good (each time a hash of the 2.5 MB regulation.bin) since part 2; now once.

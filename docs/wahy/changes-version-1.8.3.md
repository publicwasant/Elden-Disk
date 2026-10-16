> [!NOTE]
> **Version:** `1.8.3`  
> **Status:** IMPLEMENTED (closed; unit tests: 1,831). Parts 1 and 2 and the heal by share passed in the game (2026-10-17).  
> **Last Updated:** _2026-10-17_

**Summary:** Part 1: **Sparks when the cast ends.** Reverse Cursed Technique bursts into sparks around the caster at every cast (the game's
effect 4271, a burst of ice shards with sparks, on the spell's second bullet), painted in the spell's colours (#90D5FF, the white
parts #E0F3FF) while the spell is selected and the game's own ice otherwise. Everything the spell had stays as it was.
Part 2: **`colors` as the game holds them**: every colour place of every effect of the spell, each one writable.

_(baseline: **[changes-version-1.8.2.md](changes-version-1.8.2.md)**; design: **[elden-disk-spec-v1.8.3.md](../specs/elden-disk-spec-v1.8.3.md)**)_

| # | Change | Where |
|:-:|:---|:---|
| 1 | **The sparks in the build**: `customs.basic` `"Bullet.10642101.sfxId_Bullet": 4271` (the second bullet, Heal's ring around the caster, had no effect). | `code/creative.json` |
| 2 | **Their colours**: a new key of `customs.advanced.colors`, `"Bullet.<id>.sfxId_Bullet": {"main", "accent"}`: `main` on the tinted parts, `accent` on the white parts; checked against the effect `customs.basic` puts on that bullet (a plan exists for 4271 only). | `creative/innovate_spells/spec.py`, `spells.schema.json`, `service.py` |
| 3 | **The plan of 4271** (39 colours) and the white parts' own colour (`recolor`, `white`); painted in the same look as the fire, the ring and the eyes, not required. | `writer/fxr_plans.py` (`SPARK_PLANS`), `writer/fxr.py`, `commands/write.py`, `commands/run.py` |
| 4 | **Only while the spell is selected**: the script `RctColoursFollowTheSpell` gives the sparks their colours with the fire's, and the game's own when another spell is selected; a script names the key `colors.Bullet.<id>.sfxId_Bullet(.main / .accent)`. | `creative/scripts/defaults/rct_colours_follow_the_spell.py`, `creative/scripts/backend.py`, `creative/innovate_spells/live.py` |
| 5 | **The search for the effect**: the effects tried in the game and how Torrent's sparkles were looked for. | `docs/handbook/innovate-items-handbook.md` (19.8), the spec |
| 6 | **Version** 1.8.3. | `code/eldendisk/__init__.py` |
| 7 | **Part 2: `colors` as the game holds them**: a key is the param field that points at an effect (`Magic.<from>.castSfxId`, `Magic.<from>.fireSfxId`, `Bullet.<id>.sfxId_Bullet`, `SpEffectVfx.20090050.midstSfxId`, `Sfx.<effect>`), under it every colour place of that effect file by its offset, `[r, g, b, a]` or `"#RRGGBB"`; `main` / `accent` are gone. | `creative/innovate_spells/spec.py`, `spells.schema.json`, `service.py` (`colours`) |
| 8 | **The eyes in the build** from `customs.basic` (`SpEffect.<id>.vfxId1 / vfxId2` = 20090050 / 20090051), not from a key of `colors`. | `creative/innovate_spells/spec.py` |
| 9 | **A colour per place** in the same look as before (`place_states`, `value_bytes`); checked against the plans before attaching; one place or a whole key written live (`repaint_places`, the cache keeps the places); `read` shows every place as the game holds it. | `writer/fxr.py`, `writer/cache.py`, `commands/write.py`, `creative/innovate_spells/live.py`, `creative/scripts/backend.py` |
| 10 | **The scripts**: `RctColoursFollowTheSpell` gives every key but the eyes the game's own and back; the example `eyes_follow_hp.py` writes every place of the eyes. | `creative/scripts/defaults/rct_colours_follow_the_spell.py`, `tests/external_scripts/` |
| 11 | **`code/creative.json`**: the colours of part 1 written as 238 places in hex (the same colours, to half a step of 1/255); `read` shows a place in hex when a hex colour gives it. | `code/creative.json`, `creative/scripts/backend.py` |
| 12 | **A build used again** writes the design's texts and colours into `spells.resolved.json` (they are not built, so the record kept the old ones). | `creative/innovate_spells/service.py`, `commands/innovate.py` |
| 13 | **The heal as a share**: every 0.5 s 25 % of max HP, 25 % of max FP, 38 % of max stamina (`changeHpRate` / `changeMpRate` / `changeStaminaRate` -25 / -25 / -38; `changeHpPoint` / `changeMpPoint` 0). | `code/creative.json` |
| 14 | **Closing check**: nothing to optimize; `run` hashes the last build once again (it did twice since part 2). | `commands/innovate.py` |

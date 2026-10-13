> [!NOTE]
> **Version:** `1.7.1`  
> **Status:** IMPLEMENTED (unit tests); in the real game on 2026-10-11 `run` put the text and the fire colour in by itself in three sessions (written and read back every time); what is seen in the game is in manual plan 1.7.1  
> **Last Updated:** _2026-10-13_ (section 1b: the structure of a spell, the vault's real ids and the console block; accepted by the author in the game the same day)

# Elden-Disk spec 1.7.1: the text and the fire colour of a spell (Item Customization Level 3, steps 1 and 3)

Reads on top of [spec 1.7.0](elden-disk-spec-v1.7.0.md). Only what changes is written here. The research (where the text lives, why it is put into memory and not into a file, why a fixed chain from the exe was dropped, the tools) is [handbook Chapter 19](../handbook/innovate-items-handbook.md).

## 1. Idea

A new spell has a name, a short line and a long description in the game. The game reads them from FMG tables inside its archives; a loose file is not read and rewriting `Data0.bdt` is out of scope. So the text is given to the **running** game: after a character is in the world, the tool finds the game's three item-text tables in memory, rebuilds them with the spells' entries added and points the game at the new tables. The fire of *Flame, Grant Me Strength* is made of effect files the game keeps in memory as they are in the file; the tool finds them and writes new colours into the colour fields. Nothing is written to the game folder. Both last until the game closes, and both are done **once**: nothing watches the game afterwards.

Both steps find what they change by **looking through the game's memory** (section 5). No fixed address from the exe is used: the pointer chain that was measured for the text held the right object in 3 of 5 runs of the same game.

## 1a. Positive Curse Energy Eyes (`positive_curse_energy_eyes`)

While the buff of a spell lasts, both of the caster's eyes glow, in the design's colour.

```json
"positive_curse_energy_eyes": { "on": "SpEffect.1642100", "color": [0.2, 0.65, 1] }
```

| Key | Meaning |
|:--|:--|
| `on` | The copied SpEffect row that is the buff, `SpEffect.<id>` with the template's id as in `set`. Required for a spell made from a game spell (kinds `buff` with `from`, `enchant`, `projectile`, `attack`); refused on a heal-over-time buff made from scratch, which has one buff row (it gets the eyes). A `clone` copies no SpEffect row and cannot have `positive_curse_energy_eyes` |
| `color` | Optional, three numbers as `flame_color` (0 to 2). Without it the eyes are the game's own red |

Which eyes (read in the game's own files 1.17.1, not assumed). The glowing eyes of an enemy are put on the eyes of the enemy's model: the gold eyes of the enemies that give five times the runes (SpEffect `5250`, `haveSoulRate` 5) are effect `71` on DummyPoly `199`, which the enemy model `c5250` has twice, once on each eye. The player's model `c0000` has no `199`; its eyes are DummyPoly `845` (left) and `846` (right), on the bone `Head` (`220`, where the first version put the eyes of Gold-Pickled Fowl Foot, is on `Spine2`, the chest). Of all SpEffectVfx rows of the game, only two put a lasting effect on `845` and `846`: `20090050` and `20090051`, the effect `f000004866` (glowing red eyes with a light), which the game shows on a human NPC of the DLC (NpcParam `150000002`, SpEffects `20018100` and `20018101`, which never end). That is what `positive_curse_energy_eyes` uses. (`f000004225` on `845` is a flash of 1-1.5 s that some NPC attacks show.)

**Build.** The buff's SpEffect row gets `20090050` and `20090051` in the first two of `vfxId1`-`vfxId7` that are `-1` (nothing is overwritten; `vfxId` is left to the design, the author's spell sets it to `-1`), unless a visual field already holds them. The build refuses `on` when it is not one of the copied rows, and a file whose SpEffects `20018100` / `20018101` do not show those rows. The gate sees it: a template spell's copied row must equal the template's with the design's fields **and** the eyes (`G11 ... differs in: vfxId1, vfxId2`), and a buff made from scratch must hold both (`G5 ... has no positive curse energy eyes`). `on` is part of the build (adding, moving or removing the eyes builds again); `color` is not. `bases.RECIPE_VERSION` is 2 since this change: a build or a secured file made by version 1 (the first version of the eyes put SpEffectVfx 5364 on DummyPoly 220, the chest) is built again.

**Colour.** `write --flame-color` (section 4, started by `run`) recolours the glow in the same look as the fire, with its own colour: `Spells.eyes_color(selection)` gives the colour of the first spell (by slot) that names one, with a note when others differ. The places of the colours are in `writer/fxr_plans.py: EYES_PLANS`, made by `tools/fxr_places.py` from the file itself; that reading of FXR version 5 finds 71 of the 72 places of the fire's plans that were tried in the game (the one left is a black curve tangent, which a recolouring leaves black). The effect file is shared with that NPC, so its eyes have the colour too while the game runs. The game holds the file of the eyes more than once (two and three copies were seen, only one of them with the file's header) and draws from a copy that a look stopping at the first one did not reach, so when the eyes or the ring have a colour every copy is painted (`find_all(..., everything=True)`): the look reads first the 320 MB around where every log saw the effect files (160 MB each way; 64 MB each way, the first version of this look, missed the copy of the eyes the game drew from on 2026-10-13: it lay 1400 MB in, the copy that was painted 1327 MB in, and the eyes stayed red) (1312 MB into the game's biggest private block, 2560 MB: the fire 1312 MB in, the eyes 1327 MB, the ring 1300 MB), then the surroundings of every copy it found, and stops (`fxr.EFFECTS_AT`); all the memory is read only when the fire or the eyes are not there. The first version read all the memory (7 GB): two minutes after the character appeared, while the world was still loading; this one reads about 350 MB (3.4 s in the game of 2026-10-13, both copies of the eyes found). Made quicker the same day, the same copies found (measured on the running game, read only: 3.7 s → 1.1 s for the step `run` starts, 1.7 s by hand): (a) each effect is searched for by the colour of its plan that is quickest to find (`fxr.FIND_AT`: a colour whose last byte is rare in the game's memory, `...3d`, not `...3f` or `...00`; 22-45 ms per 64 MB instead of 25-79 ms), every other colour is checked at each hit as before; (b) the step `run` starts (`--when-loaded`) searches only for the game's own colours, since nothing can be painted yet in a game just started (by hand, a copy painted before is still recognised); (c) the rest is owed for the reading only, as section 5 says, not for the time our process spends looking through its own copy of the bytes (it slept 1.2 s, now 0.1 s); this applies to the text step's look too. Output: `✓ write  eyes colour: the glowing eyes are now (0.2, 0.65, 1.0) (N places written); it lasts until the game closes`.

**Seen in the game on 2026-10-12** (manual plan 1.7.1, EY): both eyes glow while the buff lasts, on the eyes, and they turned blue once every copy was painted (32 places in two copies, a third already done). Not tried yet: a whole `run` where the step started by `run` (which now looks through all the memory) is the only one; if the eyes are red, cast once and run `write --flame-color` by hand.

## 1b. The structure of a spell (`requires.status/cost`, `locations`, `customs.basic/advanced`)

A spell made from a game spell (`from`) can be written in one structure that says, in this order, what the spell is, what it needs, where it is sold and what is changed, with a comment (`__info__`) on every part. The fields of 1.7.0 and of sections 1a-2b stay valid: both are read into the same canonical form (`spec.upgrade_spell`), so **the same spell written either way builds the same file** and a secured build stays secured after the design is rewritten. `code/extension.json` is written this way since this section; `reverse_cursed_technique` is the same spell as before (blue fire with a purple ring, blue eyes; proven by a test that compares the canonical forms).

```json
"reverse_cursed_technique": {
  "__info__": "what the spell is and how each part works (any text; the tool does not read it)",
  "kind": "projectile",
  "from": 6421,
  "requires": {
    "status": { "intelligence": 0, "faith": 60, "arcane": 10 },
    "cost":   { "focus_point": 120 }
  },
  "locations": { "kale": { "price": 34590, "stock": 1 } },
  "customs": {
    "basic": {
      "__info__": "...",
      "SpEffect.1642100.effectEndurance": 20,
      "Magic.6421.castSfxId": 524400,
      "Goods.6421.iconId": 6806
    },
    "advanced": {
      "__info__": "...",
      "texts":  { "goods_name": "...", "goods_info": "...", "goods_caption": "..." },
      "colors": {
        "Magic.6421.castSfxId": { "main": [0.2, 0.65, 1], "accent": [1.0, 1.0, 1.0] },
        "SpEffect.1642100": [0.2, 0.65, 1]
      }
    }
  }
}
```

| Key | Level | Same as (canonical form) | Rules |
|:--|:-:|:--|:--|
| `__info__` | - | (dropped) | Any text, allowed on the spell and on every object below it. A comment for people: what the spell is, what each field does |
| `kind`, `from` | 2 | `kind`, `from` | As in 1.7.0; `from` is required for this structure (a heal-over-time buff made from scratch keeps its own fields) |
| `requires.status` | 2 | `requires` | `intelligence`, `faith`, `arcane`, each 0-99; the ones left out keep the template's |
| `requires.cost` | 2 | `fp_cost`, `stamina_cost` | `focus_point` and `stamina`, each 0-999 |
| `locations` | 2 | `shop` | One place. This version sells at **Kalé** only, written `kale` (`Kalé`, `Kale` and the template's `<shop-id-1>` are read as Kalé too); `price` 1-99,999,999, `stock` -1 (unlimited) or 1-99. Shelves 1-7 only (Chapter 8 of the handbook) |
| `customs.basic` | 2 | `set` | `<Table>.<row id>.<field>: number` over the copies of the game's rows (Magic, Goods, SpEffect, Bullet, AtkParam_Pc), exactly as `set` (spells handbook 7.5). Built into regulation.bin |
| `customs.advanced.texts` | 3 | `text` | `goods_name` (80), `goods_info` (300), `goods_caption` (3000; `goods_captions` is accepted too). Put into the running game (section 3) |
| `customs.advanced.colors` `"Magic.<from>.castSfxId"` | 3 | `flame_color`, `flame_accent_color` | `[r, g, b]` (the fire only) or `{"main": [r, g, b], "accent": [r, g, b]}` (accent: the ring of runes at the hand and the parts of the fire the main colour leaves out, section 2a). Each number 0-2. The id must be the spell's `from`; the spell must cast `524400` (the only effect with a colour plan): a `customs.basic` that sets `Magic.<from>.castSfxId` to another effect is an error |
| `customs.advanced.colors` `"SpEffect.<id>"` | 3 | `positive_curse_energy_eyes` `{on, color}` | The buff row whose eyes glow (section 1a). A colour, or `null` for the game's own red |

**A colour** (every colour of the design, here and in `flame_color`, `flame_accent_color`, `positive_curse_energy_eyes.color`; since 2026-10-13) is a hex string `"#90D5FF"` (`#` optional, `"#9DF"` = `"#99DDFF"`, any letter case), each channel n/255, or as before three numbers `[r, g, b]` from 0 to 2 (above 1 shines brighter, which hex cannot say). The tool writes a colour back (the diff, `spells.resolved.json`, the console, the log) as hex when it is one: `fire ■ #90D5FF   accent ■ #FF909E`, `eyes colour: the glowing eyes are now #90D5FF`. The author's design: `main` `#90D5FF` (positive curse energy), `accent` `#FF909E` (negative), eyes `#90D5FF`.

The levels: **1** is `write --set` on a running game (1.6), **2** is regulation.bin built from the game's own rows (copied and changed: `customs.basic`, `requires`, `locations`), **3** is what the game has no row for and is written into its memory after the world loads (`customs.advanced`, sections 3-5). A change in `customs.advanced` never builds again and never un-secures.

**Checked by the tool** (exit 1, nothing built; every message names the place the user wrote, e.g. `$.innovate_items.spells.slots[x].customs.basic.Magic.6422.mp: ...`): a field that does not exist at any level; a number out of its range; `stock` 0; a place other than Kalé or more than one place; a `customs.basic` key that is not `<Table>.<row id>.<field>` or names a row the template does not copy; a text too long; a colour that is not three numbers 0-2; a `castSfxId` colour whose id is not `from`, or a spell that casts an effect without a colour plan; this structure without `from`. `spells.schema.json` (`$defs.design`) says the same for an editor; a test checks that the schema and the tool agree on the same designs.

**The key of a spell** (`reverse_cursed_technique`, written `<id-1>` in the template) is a label the user chooses: unique, 1-40 characters, lower-case letters, digits, `_` and `-` (a literal `<id-1>` is refused with that message; an empty slot may keep it, as `null`). The game knows the spell by the ids of its slot. **After every build** the vault keeps `spells.resolved.json` next to `spells.build.json`: each spell under its **real Goods id** (`2230000` + slot - 1) with the label, the slot, the rows it owns in the game (`goods`, `magic`, the copied `sp_effect`, `bullet`, `atk` rows, the `shop` line) and its design in this structure with the values that were built. A dry run writes nothing.

**The diff** that says why `run` builds (and `extension --list`) names the places of this structure: `reverse_cursed_technique.locations.kale.price  34590 -> 40000`, `....customs.basic.SpEffect.1642100.effectEndurance  20.0 -> 30.0`.

**The console** (no `-v`): the whole of `extension innovate-items spells` (and its part of `run`) is **one block**:

```
 ╭─ design · innovate-items spells
 │  ·  building because the design changed since the last build (1 field)
 │     └─ reverse_cursed_technique.locations.kale.price  34590 -> 40000
 │  ✓  reverse_cursed_technique built, gate passed (26 blocks re-encoded)  (5.8 s)
 │  ·  reverse_cursed_technique  slot 1 · projectile of 6421
 │       name    Reverse Cursed Technique
 │       status  faith 60 · arcane 10
 │       cost    focus point 120
 │       sold    Kalé · 40000 runes, stock 1
 │       fire    ■ 0.2 0.65 1   accent ■ 0.54 0.4 0.8
 │       eyes    ■ 0.2 0.65 1
 │       game    goods 2230000 · magic 2230000 · SpEffect ... · shop line 100508
 ╰─ ✓  wrote C:\...\regulation.bin  (6.1 s)
```

The squares are drawn in the design's colours on a colour console. Everywhere on the console (every tag, with and without `-v`), an id of four digits or more (`114880`) and an address (`0x7ff3cbbb0000`) have colours of their own; a date, a time, a version and a number inside a path are left alone. A mistake in the design is in the block once, with its place in cyan, and the block ends `╰─ ✖ stopped`. With `-v` there is no block: the log lines, as before. The log file stays plain text.

**Accepted by the author on 2026-10-13** (a new build of the shipped design in this structure through `run`, cast, the eyes blue). Not checked one by one: a `run` with the design in this structure (it must build nothing new when a secured build of the same spell exists, and look the same in the game: blue fire, purple ring, blue eyes, the text, Kalé's price); `spells.resolved.json` next to a real build; the block in Windows Terminal and in the IDE run window.

## 2. The design: `text` and `flame_color`

`name` and `description` (1.7.0, stored only) are **removed**; a spell has one optional object, placed before `set` in the canonical form and the schema:

```json
"text": { "goods_name": "", "goods_info": "", "goods_captions": "" }
```

| Field | Game table | Shown | Limit |
|:--|:--|:--|:-:|
| `goods_name` | GoodsName | the name | 80 |
| `goods_info` | GoodsInfo | the short line | 120 |
| `goods_captions` | GoodsCaption | the long description (Inventory, controller square); `\n` = new line | 1000 |

All three are optional; the canonical form always holds all three (empty = nothing is written for it). Any other key in `text` is an error. The old keys give `renamed in 1.7.1: use text.goods_name` (and `text.goods_info`).

A spell of any kind may also have

```json
"flame_color": [0.2, 0.65, 1.0]
```

three numbers, red, green, blue, each from 0 to 2 (1 = the full colour, above 1 shines brighter; anything else is an error with its path). The fire effects are the game's own and shared by every spell that uses them, so there is **one** colour for the whole design: `Spells.flame_color(selection)` gives the colour of the first spell (by slot) that names one, and a note when other spells name a different colour. The `LEVEL3_KEYS` refused by the design are now `icon`, `icon_file`, `colour`, `color` and `model`.

`build_view` leaves `text` and `flame_color` (and the 1.7.0 `name`/`description` of old records) out: an edit of either never changes the build, the gate, `decide` or `decide_last`, and never un-secures a secured build. `Spells.texts(selection)` gives `{goods id: text}` for **every** slot (the Goods id is `2230000 + slot - 1`), empty for a slot with no spell or a spell outside the selection.

### 2a. A second colour for the fire: `flame_accent_color`

```json
"flame_color": [0.2, 0.65, 1], "flame_accent_color": [0.54, 0.4, 0.8]
```

With `flame_color` only (it is an error without it), the same three numbers. It colours what `flame_color` does not reach, so the cast has two colours:

- the places of the two fire files that the plan of section 4 leaves out (`writer/fxr_plans.py`, `accent` of each plan: the smallest and biggest values and some first keys of the linear colours, pink and red in the game's file; 4 in `524400`, 28 in `524401`, of which those that are not white or black change), found with `tools/fxr_places.py`;
- the **ring of runes** at the hand (the circle seen while Flame, Grant Me Strength is cast): `f000515000` (the game has the same file as 515010, 515020, 515030 and 515060) and `f000515001` (the ring with a burst; also 515011), the effects that use the ring texture `s60110`, red in the game's file (`ACCENT_PLANS`). The game may not hold them yet: they are painted when they are there, never required.

`Spells.flame_accent_color(selection)` gives the second colour of the spell that gives the fire its colour. Not part of the build. The author's design: blue fire with a purple ring, `[0.54, 0.4, 0.8]` (the hue of the gravity sorceries' effects, Magic 4700 and 4720: `(0.67, 0.5, 1.0)`, at 80 % brightness). Seen in the game on 2026-10-12: the ring of runes purple, the fire blue.

### 2b. Icons: an icon the game already has

A new picture is not possible (it lives in the game's menu texture archives), but a spell made from a game spell can show the icon of **any item the game has**, with the `set` it already has: `"Goods.<from>.iconId": N` (`<from>` is the template's Magic id, as in 1.7.0 section 4b; `N` is the `iconId` of the Goods row of the item whose picture is wanted). The Goods row of the copy gets `N`; the Magic row keeps the template's `iconId` (`Magic.<from>.iconId` can be set the same way if the memory screen needs it). The picture must be in an icon sheet the game loads: the sheet of `MENU_ItemIcon_06806` is `SB_Icon_07_dlc`, so a DLC icon needs the DLC installed. Example of the author's design: `reverse_cursed_technique` (a copy of Heal, 6421) with `"Goods.6421.iconId": 6806`, the icon of Gravitational Missile (Goods 2004710); built on the original `regulation.bin` the gate passes and the new Goods row (2230000) holds 6806. Seen in the game on 2026-10-12 (the author's check: the icon fits the spell); the screens one by one are in manual plan 1.7.1, IC.

## 3. `write --text [--wait [SEC] | --when-loaded] [--spec FILE] [--extension-dir DIR]`

Stands alone (an error with `--set`, `--refill`, `--reset` or `--flame-color`; `--wait`, `--when-loaded`, `--spec` and `--extension-dir` need `--text` or `--flame-color`; `--when-loaded` does not go with `--wait`). Same authorisation as every write (record readable, `RUNNING`, snapshot verified, the recorded game process, same exe hash, host alive; exit `5`); EAC loaded exit `3`; a profile without a `text` block exit `2`.

1. The design and the selection give the texts (as `extension` does).
2. The game is found. With `--when-loaded` the tool waits, without a time limit, until the game's modules can be read and a character is in the world (the player exists and has a level that makes sense) and has stayed there for 5 s (the loading screens flicker); if the game closes first nothing is written and the exit is `0`. With `--wait` a game that cannot be attached yet is tried again every second until SEC (default 300). Otherwise one try.
3. **Look.** `writer/text.py: find_tables` finds the tables: a place whose bytes start like a table (version-2 header, the `1` at `0x08`, the address at `0x18` equal to the place's own address + `0x28` + 16 × the group count, the size field in range) and whose size is the one `text.sizes` says for GoodsName, GoodsInfo or GoodsCaption. `find_arrays` then looks for the pointer to GoodsName and, where one is seen, reads the other two slots at the distances of `text.files` (GoodsName at `A + 10 * 8`, GoodsInfo at `A + 20 * 8`, GoodsCaption at `A + 24 * 8`): an array. It looks around the tables first (`near`: 64 MB each way), then the head of the big blocks, then the rest, and ends at the first whole array, which is the one written (the full looks of 2026-10-11 saw exactly one). This lighter look was written after those measurements; in the run of 2026-10-12 it found the tables in 1.6 s (156 MB) and the array in 0.3 s (38 MB, `near`), and the text was written about 6 s after the character was in the world (3 s of that is the settle time). If no array is found and the look for the tables had stopped early, the tables are looked for again through all the memory (a second copy may exist). With `--when-loaded` or `--wait` a failed look is made again after 10, 20, 40 and 60 s of rest.
4. For each array found and each table: read the table the pointer leads to (the address at `0x18` turned back into an offset, the size checked), `Fmg.read`, put each non-empty text at its Goods id and take the entry away when the text is empty. If the entries are the same as now, nothing is done for this table.
5. `swap`: allocate memory in the game (`VirtualAllocEx`, read/write), write the whole new table in its live form (address at `0x18` = new base + offsets position), check that the slot still holds the old table, change the slot with one aligned 8-byte write, read it back. The old table is untouched. A failure leaves the table concerned on the game's own and exits `1` (a table already switched stays switched).
6. With `--when-loaded` or `--wait`: after 3 s the slots are read again; if the game replaced them, steps 4-5 run once more; a second miss is an error.

Not idempotent across calls in the same game: after the first `write --text` the array points at the new tables, which have not the sizes of the game's own, so a second call finds no array and says `the text was set already in this session`. The text stays as written. Emptying a text in the design and starting the game again removes the entry. The tables are the game's own plus the slot entries; every other text is kept.

`writer/writer.py` gains `WritableProcessMemory.alloc` and `regions` (`VirtualQueryEx`: the readable private blocks the look walks) and is still the only module that names `WriteProcessMemory` or `VirtualAllocEx` (`test_write_capability_is_confined_to_the_writer_package`). `writer/text.py` knows bytes only (the writer package may not import the extension); the tables are built in `commands/write.py` with `extension/innovate_items/fmg.py`.

## 4. `write --flame-color [--wait [SEC] | --when-loaded] [--spec FILE] [--extension-dir DIR]`

The same rules as section 3 for the options, the authorisation and the wait. The design gives the colour (`Spells.flame_color`) and, since section 1a, the colour of the positive curse energy eyes (`Spells.eyes_color`), which is recoloured in the same look with its own colour; either may be absent. With neither: `no spell of the design names a flame_color or a positive_curse_energy_eyes color: nothing to do`, exit `0`.

1. Two effect files make the fire that is recoloured: `524400` (the fire while casting; 18 colours) and `524401` (the burst when the cast ends; 54 colours). The third (`524402`, the fire on the body) is left alone. `writer/fxr_plans.py` lists, for each file, where every colour (four little-endian floats, RGBA) sits and whether it is a bloom colour.
2. **New colour.** With v = the biggest of R, G, B and w = 1 − (v − the smallest) / v: new RGB = v × (w + (1 − w) × target). White stays white, black stays black, alpha is never touched. A bloom colour becomes v × target.
3. **Look.** `writer/fxr.py: find_all` goes through the memory (section 5) and keeps a place where **every** colour of a plan matches the game's bytes, the original or the painted ones (so a second run finds its own work). The look stops when each effect has a copy. A copy that does not match entirely is not touched.
4. Each copy is written at its listed places and read back. A place that would not change (black) is not written. `already` counts the copies that were painted before.
5. If an effect is not found the look is made again after 10, 20, 40 and 60 s of rest (with `--when-loaded` or `--wait`); at the end: `the game does not hold the effect file(s) … : the game is still starting (use --wait), or it is not the version this was made for`, exit `1`.

Output: `✓ write  flame colour: the fire of Flame, Grant Me Strength is now (0.2, 0.65, 1.0) in 2 effects (68 places written); it lasts until the game closes`; with `flame_accent_color` the line names both colours and `✓ write  ring colour: the ring of runes at the hand is now (…)` follows when the game holds the ring (section 2a). The effect files are shared by every spell that uses them, so the game's own Flame, Grant Me Strength has the colour too while the game runs.

## 5. The look: `writer/scan.py`

One way of looking, shared by both steps; it never writes. The caller gives `visit(address, data, n)` for each piece and returns True when it has what it wants.

| Rule | Why (measured on 1.17.1) |
|:--|:--|
| The game's private, readable memory is read in pieces of 1 MB (16 MB in the measured runs of section 9); the tool owes a rest of half the time the reading took and sleeps it in lumps of at least 2 ms | the first versions rested a fixed 5 ms per MB, which Windows made ~15 ms: the time went into resting, not reading. A share of the piece's time keeps the game's share of the memory bus whatever the speed |
| First the first 128 MB of each private block of 256 MB or more (biggest first), then all the rest (biggest first) | the text tables lie ~43 MB into a block of 1530 MB (found in 0.6 s); the fire lies ~1312 MB into a block of 2560 MB (found in the rest, 6.5 s) |
| A piece also holds the first `overlap` bytes of the next one | something that begins in a piece and ends after it is seen whole |
| A piece that cannot be read whole is read again in parts of 256 KB | one page that is gone does not hide the rest |
| A look ends at 120 s | a bound; the logs of 2026-10-11 never came near it |

## 6. The profile: `text`

```json
"text": { "files": { "GoodsName": 10, "GoodsInfo": 20, "GoodsCaption": 24 }, "sizes": { "GoodsName": 114880, "GoodsInfo": 164208, "GoodsCaption": 975296 } }
```

Optional per exe hash (absent = `write --text` unsupported, exit `2`); a block that is there must be complete and `sizes` must name the same tables as `files` (each size from `0x28` bytes to 64 MB). `files` are the numbers of the text files (checked in the game); `sizes` are the sizes of the game's own tables in the language the game is played in (here the English tables of 1.17.1). No address is kept (the `rva` and `array` of the first version are gone).

## 7. `run` starts them

`Hooks.on_running(pid)` (new, default does nothing) is called once, right after the record says `RUNNING` and only with the vault ON; an exception in it is logged and never ends the session. `commands/run.py` sets it when all hold: vault ON, the regulation.bin swapped is the extension's (`secured`, `last` or `built`, not `--regulation FILE`). It then starts, each as a **separate process** (`python -m eldendisk` in the source tree, the exe itself when frozen) in its own console process group, stdout and stderr inherited (silenced under `-v`, where the log shows their lines):

- `eldendisk write --text --when-loaded --vault V --offsets O [--spec S] [--extension-dir D]` when the design has any text for the built spells;
- `eldendisk write --flame-color --when-loaded …` when a spell of the design names a `flame_color`.

`run` therefore still never opens the game's memory (the host and vault rules of spec 1.6.2 hold). A child still running when the session ends is stopped.

## 8. Failures

| Case | Result |
|:--|:--|
| tables not found (the game is still loading, another version or language) | `write --text` exits `1` with what was seen (the sizes of the tables it saw), the game goes on without the text |
| the tables were seen but no array points at all three | `the text was set already in this session …` or `the game keeps them differently than offsets.json describes`, exit `1` |
| the game replaces the tables again | one more try, then exit `1` |
| a fire effect is not in the game | exit `1` after the looks |
| a step fails inside `run` | the session is not affected; run it by hand |
| closing the game | everything vanishes (the memory was the game's) |

## 9. Measured (real game, 2026-10-11, three `run` sessions)

| | Text | Fire |
|:--|:--|:--|
| Found | all three tables in 0.6-0.7 s (176 MB read, the head); one array, about 6 MB before them, in a look through all the memory (7.3 GB, 70-73 s, 3 pointers) | one copy of each effect in 6.4-6.6 s (1712 MB read, the rest of the blocks) |
| Written | GoodsName 114880 → 114952 bytes, GoodsInfo 164208 → 164610, GoodsCaption 975296 → 977510; the pointers read back | 68 places (18 + 50), read back |
| After the character is in the world | ~75 s | ~7 s |

The earlier chain from the exe gave the right object in 3 of 5 runs and memory given back in 2 (an FMG groups table, UTF-16 text, whole numbers): the reason for section 1.

## 10. Not done (open)

Thai and other scripts (glyphs in the game's font untested); a game language other than English (the profile holds the English sizes); the colour of the fire on the body (`524402`); the positive curse energy eyes in the game (section 1a); a new icon picture (Level 3 step 2; reusing an existing icon is 2b); a faster look for the array (it is found by a look through all the memory, ~72 s; it lies near the tables); a second `write --text` in the same game.

## 11. Tests

`tests/test_write_text.py` (writer/text.py against a fake game memory: the shape of a table, `find_tables` and `find_arrays` with decoys, a second copy of the array, the look around the tables and the fall back to all the memory, swap and every failure of it; the command: three tables, idempotent, emptying, no session, other process, no profile block, waits and gives up with the sizes it saw, the game putting its tables back, command-line rules), `tests/test_write_flame.py` (the positive curse energy eyes: their plan, their own colour in the same look, the step with only the eyes or both; `scan.walk`: borders, rest in proportion to the time and the budget, rests slept in lumps, the near tier read once, the head tier, unreadable parts; `find_all`; `paint_many`; the command step), `test_fxr_places.py` (tools/fxr_places.py on a small FXR file), `test_ext_design.py` (section 1b: the structure and the earlier fields give the same spell, `design_of` and back, every mistake named where it is written, the diff in its words, the schema and the tool agree, the real ids, `spells.resolved.json`, the block through the CLI), additions to `test_ui.py` (ids and addresses, the block), `test_ext_golden.py` (positive curse energy eyes built on the real file and seen by the gate), additions to `test_ext_spec.py` (the object, limits, renamed keys, `flame_color`, `positive_curse_energy_eyes`), `test_ext_service.py` (`texts`, `flame_color`, an edit of either decides nothing), `test_host.py` (`on_running`), `test_run_command.py` (the command lines, when the steps start, stopping them), `test_profile_policy.py` (the `text` block: files and sizes), `test_disk.py` (the one allocation), `test_gamearchive.py` and `test_ext_fmg.py` (tools/gamearchive.py, the FMG), `test_probe_text.py` (the research tool).

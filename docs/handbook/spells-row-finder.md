# Spells Row Finder
### id → the rows a spell uses (the companion of the [Spells Innovation Handbook](spells-innovation-handbook.md))

> **What this is:** for every spell that a workshop above the Photocopier accepts, the list of rows you may write in `set`: their **ids**, **names**, **durations** and **base damage**. Read Chapter 3 of the handbook first if the words "row" and "id" are new to you.
> **Data:** read from the original Elden Ring 1.17.1 `regulation.bin` with the tool's own chain reader. Names come from the community's Paramdex lists and can be blank or imperfect; the **numbers** are the game's.
> **Also in this file:** the **Motion Finder** (numbers for `cast_motion`) and the **Visual Finder** (numbers for `effect.visual`), right below, before the spells.
> **Find a spell** with your editor's search (`Ctrl+F`, type the name or the id). The ids are the same as in the Spell Finder (Appendix A of the handbook).

### How to read an entry

```
### 6210 · Black Flame                              ← the spell's Magic id (this is your `from`) and name
*18 FP · 1 memory slot · workshops: Fireball*       ← its original cost and size, and who accepts it

- SpEffect  `1621000` … (lasts 2 s)                 ← an effect row. In `set`: SpEffect.1621000.effectEndurance
- Bullet    `10621000` …                            ← a projectile row. In `set`: Bullet.10621000.dist
- Hit       `62101` … — fire 244                    ← a hit row with its BASE damage. In `set`: AtkParam_Pc.62101.atkFire
```

- A row shown here is **copied** into your shelf by that workshop, so `set` works on it. Rows that many other spells share are **not listed**: they stay the game's and cannot be changed.
- **Damage numbers are base values** of the hit. What you see in the game is also scaled by your build.
- *"lasts 2 s"* is the effect's `effectEndurance`; *endless* means it never runs out; *instant / no timer* means it acts once.
- The **Photocopier** (`clone`) changes only the spell's own `Magic.<id>` and `Goods.<id>` rows and needs none of this, so photocopy-only spells are not listed here.
- Different spells can list the same row id; each shelf gets its own private copy, so changing it on your shelf does not affect any other spell.

---

## Motion Finder — numbers for `cast_motion`

`cast_motion` is the **cast animation**: the way your character raises the hands and plays the spell. In the game it is one number on a spell's own Magic row (`Magic.<id>.refType`). Spells that cast alike share the number: all the fireballs (Flame Sling, Black Flame…) use `17`, the four "Flame, … Me" buffs use `31`. To borrow a cast animation, **find a spell whose cast you like and write its number**.

```json
"cast_motion": 32,                         ← the number of Black Flame Blade
"cast_motion": "black-flame-blade"         ← the same thing, by name
```

- The two **names** are shortcuts: `flame-grant-me-strength` = `31`, `black-flame-blade` = `32`. Only these two have been tried in the game (✓).
- **Any other number is accepted but untried.** The tool checks that some spell of the game really uses it (it refuses `3`, for instance, which no spell uses), but it cannot know how the animation looks on your spell. Try it, and tell us what you see.
- The animation of a *sorcery* on an *incantation* shelf (or the other way round) may look odd or play with a different timing: that is exactly the kind of experiment this table is for.
- Only the home-made spell (kind `buff` without `from`) has a `cast_motion`. A spell made from a game spell keeps the cast of the original, unless you write `"set": {"Magic.<its id>.refType": <number>}` (the build and its checks pass; not tried in the game yet ◦).
- Spells that only boss and NPC characters cast are not listed.

| Motion | Incantations that use it | Sorceries that use it | Name |
|:-:|:--|:--|:--|
| **0** | Inescapable Frenzy (7300) | — |  |
| **1** | — | Glintstone Icecrag (4400), Glintstone Pebble (4000), Great Glintstone Shard (4001) |  |
| **2** | — | Comet (4021), Glintstone Cometshard (4020), Night Comet (4620), Shard Spiral (4030) |  |
| **4** | — | Crystal Barrage (4060) |  |
| **5** | — | Loretta's Greatbow (4380), Loretta's Mastery (4381) |  |
| **6** | — | Ranni's Dark Moon (4361), Rennala's Full Moon (4360) |  |
| **7** | — | Comet Azur (4200), Crystal Torrent (4520) |  |
| **8** | — | Carian Phalanx (4301), Eternal Darkness (4650), Glintblade Phalanx (4300) |  |
| **9** | — | Adula's Moonblade (4431), Carian Greatsword (4430) |  |
| **10** | — | Carian Piercer (4450) |  |
| **11** | — | Frozen Armament (4490), Scholar's Armament (4460), Unseen Blade (4660) |  |
| **12** | — | Scholar's Shield (4470) |  |
| **13** | — | Lucidity (4480), Starlight (4140), Terra Magicus (4130) |  |
| **14** | — | Zamor Ice Storm (4410) |  |
| **15** | — | Meteorite (4700), Meteorite of Astel (4701) |  |
| **16** | — | Glintstone Arc (4070) |  |
| **17** | Black Flame (6210), Flame Fall Upon Them (6020), Flame Sling (6010), Giantsflame Take Thee (6100) | — |  |
| **19** | Flame of The Fell God (6110) | Watchful Spirit (2007600) |  |
| **20** | Whirl, O Flame (6030) | — |  |
| **22** | Scouring Black Flame (6230) | — |  |
| **23** | Surge, O Flame (6220) | — |  |
| **24** | Burn, O Flame! (6120), Fire's Deadly Sin (7900) | — |  |
| **25** | O, Flame! (6001) | — |  |
| **26** | Darkness (6530), Poison Mist (7220), Shadow Bait (6520), Swarm of Flies (7210) | — |  |
| **27** | Discus of Light (6700), Triple Rings of Light (6701) | — |  |
| **28** | Rejection (6400) | — |  |
| **29** | Wrath of Gold (6410) | — |  |
| **31** | Bestial Constitution (6850), Bestial Vitality (6840), Black Flame's Protection (6260), Flame Cleanse Me (6040), Flame Grant Me Strength (6050), Flame Protect Me (6060) | — | `flame-grant-me-strength` |
| **32** | Black Flame Blade (6250) | — | `black-flame-blade` |
| **33** | Cure Poison (6440), Divine Fortification (6480), Flame Fortification (6450), Lightning Fortification (6470), Magic Fortification (6460), Urgent Heal (6420) | — |  |
| **34** | Barrier of Gold (6330), Blessing of The Erdtree (6431), Blessing's Boon (6430), Erdtree Heal (6424), Golden Light Fortification (7903), Great Heal (6422), Heal (6421), Lord's Aid (6441), Lord's Divine Fortification (6490), Lord's Heal (6423), Protection of The Erdtree (6340) | — |  |
| **35** | Golden Vow (6600) | — |  |
| **36** | Lightning Spear (6900) | — |  |
| **37** | Stone of Gurranq (6810) | — |  |
| **38** | Bestial Sling (6800) | — |  |
| **40** | Beast Claw (6820) | — |  |
| **41** | Gurranq's Beast Claw (6830) | — |  |
| **42** | Ancient Dragons' Light Strike (6910), Electrocharge (2006920) | Death Lightning (5040) |  |
| **44** | Ancient Dragons' Light Spear (6940) | — |  |
| **45** | Lansseax's Glaive (6950) | — |  |
| **48** | Radagon's Rings of Light (6710) | — |  |
| **49** | Immutable Shield (6740) | — |  |
| **50** | Agheel's Flame (7001), Borealis's Mist (7021), Ekzykes's Decay (7031), Ghostflame Breath (2007020), Smarag's Glint Breath (7041) | — |  |
| **51** | Placidusax's Ruin (7050) | — |  |
| **52** | Dragonclaw (7060) | — |  |
| **54** | Dragonmaw (7080) | — |  |
| **55** | Greyoll's Roar (7090) | — |  |
| **56** | — | Shatter Earth (4100) |  |
| **57** | — | Rock Blaster (4110) |  |
| **58** | — | Crystal Release (4510) |  |
| **59** | Electrify Armament (6960), Vyke's Dragonbolt (6970) | — |  |
| **60** | Dragonbolt Blessing (6971) | — |  |
| **66** | The Flame of Frenzy (7310) | — |  |
| **67** | Dragonfire (7000), Dragonice (7020), Glintstone Breath (7040), Rotten Breath (7030) | — |  |
| **70** | Aspects of the Crucible: Tail (7500) | — |  |
| **71** | Aspects of the Crucible: Horns (7510) | — |  |
| **74** | Pest Threads (7200) | — |  |
| **75** | — | Oracle Bubbles (5100) |  |
| **76** | — | Great Oracular Bubble (5110) |  |
| **78** | — | Gavel of Haima (4120) |  |
| **79** | — | Night Shard (4610), Swift Glintstone Shard (4010) |  |
| **80** | — | Carian Slicer (4440) |  |
| **81** | Briars of Sin (8000) | Briars of Sin (4900) |  |
| **82** | Briars of Punishment (8001) | Briars of Punishment (4910) |  |
| **83** | — | Ambush Shard (4600) |  |
| **84** | — | Carian Retaliation (4640), Carian Retaliation (Unused 1) (4641), Carian Retaliation (Unused 2) (4642) |  |
| **86** | Law of Causality (6760), Law of Regression (6730), Order Healing (6780) | — |  |
| **87** | Litany of Proper Death (6750) | — |  |
| **88** | Unendurable Frenzy (7311) | — |  |
| **89** | Frenzied Burst (7320) | — |  |
| **90** | Howl of Shabriri (7330) | — |  |
| **91** | Elden Stars (6720), Land of Shadow (2006680) | — |  |
| **92** | — | Cannon of Haima (4080) |  |
| **93** | Bloodboon (6310) | — |  |
| **94** | Bloodflame Talons (6300) | — |  |
| **95** | — | Greatblade Phalanx (4302), Rykard's Rancor (4830) |  |
| **98** | Fortissax's Light Spear (6941) | — |  |
| **99** | Black Flame Ritual (6240) | — |  |
| **100** | Aspects of the Crucible: Breath (7520) | — |  |
| **102** | — | Gelmir's Fury (4810) |  |
| **103** | — | Ancient Death Rancor (5001), Rancorcall (5000) |  |
| **104** | Order's Blade (6770) | — |  |
| **105** | Noble Presence (6270) | — |  |
| **106** | Catch Flame (6000) | — |  |
| **107** | — | Glintstone Nail (2004500), Glintstone Nails (2004510), Glintstone Stars (4040), Magic Downpour (4370), Star Shower (4050), Stars of Ruin (4220) |  |
| **108** | — | Rock Sling (4710) |  |
| **109** | — | Unseen Form (4670) |  |
| **110** | — | Thops's Barrier (4630) |  |
| **111** | Honed Bolt (6930), Lightning Strike (6920) | — |  |
| **112** | Bloodflame Blade (6320), Poison Armament (7230) | — |  |
| **113** | Night Maiden's Mist (6500) | Crystal Burst (4090), Fia's Mist (5020), Freezing Mist (4420), Shattering Crystal (4500) |  |
| **114** | Assassin's Approach (6510) | — |  |
| **115** | — | Explosive Ghostflame (5010) |  |
| **116** | Black Blade (7530) | — |  |
| **117** | — | Magma Shot (4800), Roiling Magma (4820) |  |
| **118** | — | Magic Glintblade (4390) |  |
| **119** | Frozen Lightning Spear (6921) | — |  |
| **120** | — | Blades of Stone (2004700), Collapsing Stars (4721), Fleeting Microcosm (2007410), Gravitational Missile (2004710), Gravity Well (4720) |  |
| **121** | — | Tibia's Summons (5030) |  |
| **122** | Scarlet Aeonia (7240) | — |  |
| **123** | Magma Breath (7010), Theodorix's Magma (7011) | — |  |
| **124** | — | Founding Rain of Stars (4210) |  |
| **125** | Aspects of the Crucible: Thorns (2006650) | — |  |
| **126** | — | Vortex of Putrescence (2006200) |  |
| **127** | — | Miriam's Vanishing (2004300) |  |
| **128** | Minor Erdtree (2006670) | — |  |
| **129** | Aspects of the Crucible: Bloom (2006660) | — |  |
| **130** | Heal from Afar (2006400) | — |  |
| **131** | Roar of Rugalea (2006800) | — |  |
| **133** | Bayle's Tyranny (2007000) | — |  |
| **134** | Bayle's Flame Lightning (2007010) | — |  |
| **135** | Rotten Butterflies (2007200) | — |  |
| **136** | Pest-Thread Spears (2007210) | — |  |
| **137** | Midra's Flame of Frenzy (2007300) | — |  |
| **138** | — | Glintblade Trio (2004310) |  |
| **139** | Knight's Lightning Spear (2006900) | — |  |
| **140** | Furious Blade of Ansbach (2006300) | — |  |
| **141** | Messmer's Orb (2007820) | — |  |
| **143** | — | Rings of Spectral Light (2005000) |  |
| **144** | Dragonbolt of Florissax (2006910) | — |  |
| **145** | Light of Miquella (2006700) | — |  |
| **146** | — | Spira (2007720) |  |
| **147** | Divine Beast Tornado (2007730) | — |  |
| **148** | — | Golden Arcs (2007700) |  |
| **149** | Multilayered Ring of Light (2006710) | — |  |
| **150** | — | Mantle of Thorns (2004900) |  |
| **151** | Wrath from Afar (2006690) | — |  |
| **152** | Divine Bird Feathers (2007740) | — |  |
| **153** | Fire Serpent (2007800) | — |  |
| **154** | — | Giant Golden Arc (2007710) |  |
| **156** | — | Impenetrable Thorns (2004910) |  |
| **157** | — | Cherishing Fingers (2007420) |  |
| **158** | — | Mass of Putrescence (2006210) |  |
| **159** | Rain of Fire (2007810) | — |  |
| **161** | — | Rellana's Twin Moons (2004320) |  |

## Visual Finder — numbers for `effect.visual`

`effect.visual` is **what you see on the character while the effect lasts**: the burning body, the healing glow. In the game it is one number on the effect's row (`SpEffect.<id>.vfxId`), the id of a *visual effect* (a particle show). Many effects share one visual.

```json
"visual": 1605000,                         ← the burning body of Flame, Grant Me Strength
"visual": "flame"                          ← the same thing, by name
"visual": -1                               ← no visual (same as "none" or null)
```

- Three **names** are shortcuts: `flame` = `1605000`, `flask` = `5030` (the glow of a Flask of Crimson Tears), `none` = `-1`.
- **Any other number is accepted but untried.** The tool checks that some effect of the game uses it (the game has about 1,000 such numbers; the table below lists the **72 used by the effects of spells**). A visual may be made for something else (the weapon, the hit, a boss) and show nothing on a body, or show it somewhere odd. Try it and see.
- A spell can have several effects with several visuals; the table lists each visual with the spells whose effects use it and a few of the effect rows (`SpEffect` ids; read them with `eldendisk read --param SpEffect.<id>`).
- Only the home-made spell (kind `buff` without `from`) has `effect.visual`. To change the look of a copied spell, use `set` on its `SpEffect` rows (`vfxId` is one of the fields in section 7.8 of the handbook).

| Visual | Spells whose effects use it | Effect rows | Name |
|:-:|:--|:--|:--|
| **2** | Poison Armament (7230), Poison Mist (7220) | 1722000, 1723001 |  |
| **5** | Ekzykes's Decay (7031), Rotten Breath (7030), Rotten Butterflies (2007200), Scarlet Aeonia (7240) | 1703000, 1703100, 1724000 +2 |  |
| **6** | Bloodboon (6310), Bloodflame Blade (6320), Bloodflame Talons (6300), Briars of Punishment (4910), Briars of Punishment (8001), Briars of Sin (4900), +4 more | 1490001, 1490010, 1491001 +11 |  |
| **260** | Adula's Moonblade (4431), Borealis's Mist (7021), Dragonice (7020), Explosive Ghostflame (5010), Freezing Mist (4420), Frozen Armament (4490), +8 more | 1436100, 1440000, 1441000 +17 |  |
| **5304** | Minor Erdtree (2006670) | 21667000 |  |
| **9010** | Black Flame (6210), Black Flame Blade (6250), Black Flame Ritual (6240), Noble Presence (6270), Scouring Black Flame (6230) | 1621000, 1623000, 1624010 +2 |  |
| **9012** | Black Blade (7530) | 6850 |  |
| **9013** | Black Blade (7530) | 6860 |  |
| **1413000** | Terra Magicus (4130) | 1413000 |  |
| **1414000** | Starlight (4140) | 1414000 |  |
| **1436000** | Rennala's Full Moon (4360) | 1436000 |  |
| **1436100** | Ranni's Dark Moon (4361) | 1436101 |  |
| **1446000** | Scholar's Armament (4460) | 1446000 |  |
| **1447000** | Scholar's Shield (4470) | 1447000 |  |
| **1448000** | Lucidity (4480) | 1448000 |  |
| **1449000** | Frozen Armament (4490) | 1449000 |  |
| **1466000** | Unseen Blade (4660) | 1466000 |  |
| **1467000** | Unseen Form (4670) | 1467000 |  |
| **1467001** | Unseen Form (4670) | 1467001 |  |
| **1467002** | Unseen Form (4670) | 1467002 |  |
| **1467005** | Unseen Form (4670) | 1467005 |  |
| **1467006** | Unseen Form (4670) | 1467006 |  |
| **1604000** | Flame Cleanse Me (6040) | 1604000 |  |
| **1605000** | Flame Grant Me Strength (6050) | 1605000 | `flame` |
| **1606000** | Flame Protect Me (6060) | 1606000 |  |
| **1626000** | Black Flame Blade (6250) | 1626000 |  |
| **1627000** | Black Flame's Protection (6260) | 1627000 |  |
| **1632000** | Bloodflame Blade (6320) | 1632000 |  |
| **1633000** | Barrier of Gold (6330) | 1633000 |  |
| **1634000** | Protection of The Erdtree (6340) | 1634000 |  |
| **1642000** | Urgent Heal (6420) | 1642000 |  |
| **1642100** | Heal (6421) | 1642100, 1642101 |  |
| **1642200** | Great Heal (6422), Heal from Afar (2006400) | 1642200, 1642201, 21640000 +1 |  |
| **1642300** | Lord's Heal (6423) | 1642300, 1642301 |  |
| **1642400** | Erdtree Heal (6424) | 1642400, 1642401 |  |
| **1643000** | Blessing's Boon (6430) | 1643000, 1643001 |  |
| **1643100** | Blessing of The Erdtree (6431) | 1643100, 1643101 |  |
| **1644000** | Cure Poison (6440) | 1644000 |  |
| **1644100** | Lord's Aid (6441) | 1644100, 1644110 |  |
| **1645000** | Flame Fortification (6450) | 1645000 |  |
| **1646000** | Magic Fortification (6460) | 1646000 |  |
| **1647000** | Lightning Fortification (6470) | 1647000 |  |
| **1648000** | Divine Fortification (6480) | 1648000 |  |
| **1649000** | Lord's Divine Fortification (6490) | 1649000 |  |
| **1651000** | Assassin's Approach (6510) | 1651000 |  |
| **1651001** | Assassin's Approach (6510) | 1651002 |  |
| **1653000** | Darkness (6530) | 1653001 |  |
| **1673000** | Law of Regression (6730) | 1673000, 1673020 |  |
| **1674000** | Immutable Shield (6740) | 1674000 |  |
| **1676000** | Law of Causality (6760) | 1676000 |  |
| **1676001** | Law of Causality (6760) | 1676007 |  |
| **1676002** | Law of Causality (6760) | 1676010 |  |
| **1677000** | Order's Blade (6770) | 1677000 |  |
| **1678000** | Order Healing (6780) | 1678000 |  |
| **1685000** | Bestial Vitality (6840) | 1685000 |  |
| **1686000** | Bestial Constitution (6850) | 1686000 |  |
| **1696000** | Electrify Armament (6960) | 1696000 |  |
| **1697000** | Vyke's Dragonbolt (6970) | 1697000 |  |
| **1697001** | Vyke's Dragonbolt (6970) | 1697001 |  |
| **1697100** | Dragonbolt Blessing (6971) | 1697100 |  |
| **1709000** | Greyoll's Roar (7090) | 1709000 |  |
| **1723000** | Poison Armament (7230) | 1723000 |  |
| **1733000** | Howl of Shabriri (7330) | 1733000 |  |
| **1790000** | Fire's Deadly Sin (7900) | 1790000, 1790010 |  |
| **1790300** | Golden Light Fortification (7903) | 1790300 |  |
| **21430000** | Miriam's Vanishing (2004300) | 21430000 |  |
| **21490000** | Mantle of Thorns (2004900) | 21490000 |  |
| **21490001** | Mantle of Thorns (2004900) | 21490001 |  |
| **21691000** | Dragonbolt of Florissax (2006910) | 21691001 |  |
| **21691002** | Dragonbolt of Florissax (2006910) | 21691000 |  |
| **21692000** | Electrocharge (2006920) | 21692000, 21692010 |  |
| **92082000** | Adula's Moonblade (4431), Aspects of the Crucible: Horns (7510), Aspects of the Crucible: Tail (7500), Black Blade (7530), Carian Greatsword (4430), Carian Piercer (4450), +4 more | 6900, 6901, 6903 +3 |  |

## Incantations (129)

### 5040 · Death Lightning
*28 FP · 2 memory slots · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `70` Blight Effect (endless); `1504000` Death Lightning (instant / no timer); `1504001` Death Lightning (instant / no timer)
- **Bullet** (`Bullet.<id>.…`): `10504000` Death Lightning; `10504001` Death Lightning; `10504002` Death Lightning; `10504003` Death Lightning; `10504004` Death Lightning; `10504050` Death Lightning [Charged]; `10504051` Death Lightning; `10504052` Death Lightning; `10504053` Death Lightning; `10504054` Death Lightning
- **Hit** (`AtkParam_Pc.<id>.…`): `50400` Death Lightning — lightning 513; `50401` Death Lightning — no damage; `50405` Death Lightning [Charged] — lightning 564; `50406` Death Lightning — no damage

### 6000 · Catch Flame
*10 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10600000` Catch Flame; `10600001` Catch Flame; `10600002` Catch Flame; `10600005` Catch Flame; `10600006` Catch Flame
- **Hit** (`AtkParam_Pc.<id>.…`): `60000` Catch Flame — no damage; `60001` Catch Flame — fire 225

### 6001 · O, Flame!
*16 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10600100` O Flame!; `10600101` O Flame!; `10600105` O Flame!; `10600106` O Flame!; `10600150` O Flame! [Charged]; `10600151` O Flame!; `10600155` O Flame!; `10600156` O Flame!
- **Hit** (`AtkParam_Pc.<id>.…`): `60010` Catch Flame — no damage; `60011` O Flame! — fire 280; `60015` Catch Flame — no damage; `60016` O Flame! [Charged] — fire 385

### 6010 · Flame Sling
*11 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10601000` Flame Sling; `10601001` Flame Sling; `10601050` Flame Sling [Charged]; `10601051` Flame Sling
- **Hit** (`AtkParam_Pc.<id>.…`): `60100` Flame Sling — fire 202; `60101` Flame Sling — fire 202; `60102` Flame Sling — fire 255; `60103` Flame Sling — fire 255

### 6020 · Flame Fall Upon Them
*16 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10602000` Flame Fall Upon Them; `10602001` Flame Fall Upon Them; `10602002` Flame Fall Upon Them; `10602050` Flame Fall Upon Them [Charged]; `10602051` Flame Fall Upon Them; `10602052` Flame Fall Upon Them
- **Hit** (`AtkParam_Pc.<id>.…`): `60200` Flame Fall Upon Them Bullet — fire 115; `60201` Flame Fall Upon Them Bullet — fire 115; `60202` Flame Fall Upon Them Bullet — fire 115; `60205` Flame Fall Upon Them [Charged] Bullet — fire 140; `60206` Flame Fall Upon Them Bullet — fire 140; `60207` Flame Fall Upon Them Bullet — fire 140

### 6030 · Whirl, O Flame
*19 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10603000` Whirl O Flame!; `10603050` Whirl O Flame! [Charged]
- **Hit** (`AtkParam_Pc.<id>.…`): `60300` Whirl O Flame! Bullet — fire 96; `60305` Whirl O Flame! [Charged] Bullet — fire 121

### 6040 · Flame Cleanse Me
*14 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1604000` Flame Cleanse Me (instant / no timer); `1604001` Flame Cleanse Me (instant / no timer); `1604002` Flame Cleanse Me (instant / no timer); `1604003` Flame Cleanse Me (instant / no timer); `1604004` Flame Cleanse Me (lasts 0.2 s); `1604005` Flame Cleanse Me (instant / no timer)
- **Bullet** (`Bullet.<id>.…`): `10604000` Flame Cleanse Me; `10604001` Flame Cleanse Me; `10604002` Flame Cleanse Me
- **Hit** (`AtkParam_Pc.<id>.…`): `60400` Flame Cleanse Me Bullet — no damage

### 6050 · Flame Grant Me Strength
*28 FP · 1 memory slot · workshops: Buff tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1605000` Flame Grant Me Strength (lasts 30 s); `1605001` Flame Grant Me Strength (lasts 0.1 s); `1605002` Flame Grant Me Strength (lasts 0.1 s)

### 6060 · Flame Protect Me
*30 FP · 1 memory slot · workshops: Buff tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1606000` Flame Protect Me (lasts 70 s)

### 6100 · Giantsflame Take Thee
*30 FP · 2 memory slots · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10610000` Giantsflame Take Thee; `10610001` Giantsflame Take Thee; `10610050` Giantsflame Take Thee [Charged]; `10610051` Giantsflame Take Thee
- **Hit** (`AtkParam_Pc.<id>.…`): `61000` Giantsflame Take Thee — fire 325; `61005` Giantsflame Take Thee — fire 389

### 6110 · Flame of The Fell God
*34 FP · 2 memory slots · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10611000` Flame of the Fell God; `10611001` Flame of the Fell God; `10611002` Flame of the Fell God; `10611003` Flame of the Fell God; `10611004` Flame of the Fell God; `10611005` Flame of the Fell God; `10611006` Flame of the Fell God; `10611007` Flame of the Fell God; `10611008` Flame of the Fell God; `10611009` Flame of the Fell God
- **Hit** (`AtkParam_Pc.<id>.…`): `61100` Flame of the Fell God — fire 415; `61101` Flame of the Fell God — fire 35

### 6120 · Burn, O Flame!
*26 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10612000` Burn O Flame!; `10612001` Burn O Flame!; `10612002` Burn O Flame!; `10612003` Burn O Flame!; `10612004` Burn O Flame!; `10612005` Burn O Flame!; `10612050` Burn O Flame! [Charged]; `10612051` Burn O Flame!; `10612052` Burn O Flame!; `10612053` Burn O Flame!; `10612054` Burn O Flame!; `10612055` Burn O Flame!
- **Hit** (`AtkParam_Pc.<id>.…`): `61203` Burn O Flame! Bullet — fire 288

### 6210 · Black Flame
*18 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1621000` Black Flame (DoT Black) (lasts 2 s)
- **Bullet** (`Bullet.<id>.…`): `10621000` Black Flame; `10621001` Black Flame; `10621050` Black Flame [Charged]; `10621051` Black Flame
- **Hit** (`AtkParam_Pc.<id>.…`): `62101` Black Flame — fire 244; `62106` Black Flame [Charged] — fire 300

### 6220 · Surge, O Flame
*1 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10622000` Surge O Flame!
- **Hit** (`AtkParam_Pc.<id>.…`): `62200` Surge O Flame! Bullet — fire 51

### 6230 · Scouring Black Flame
*21 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1623000` Scouring Black Flame (DoT Black) (lasts 2 s)
- **Bullet** (`Bullet.<id>.…`): `10623000` Scouring Black Flame; `10623001` Scouring Black Flame; `10623050` Scouring Black Flame [Charged]; `10623051` Scouring Black Flame
- **Hit** (`AtkParam_Pc.<id>.…`): `62300` Scouring Black Flame — fire 255; `62305` Scouring Black Flame — fire 299

### 6240 · Black Flame Ritual
*30 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1625000` Black Flame Ritual (DoT Black) (lasts 2 s)
- **Bullet** (`Bullet.<id>.…`): `10625000` Black Flame Ritual; `10625001` Black Flame Ritual; `10625002` Black Flame Ritual; `10625003` Black Flame Ritual; `10625050` Black Flame Ritual [Charged]; `10625051` Black Flame Ritual; `10625052` Black Flame Ritual; `10625053` Black Flame Ritual
- **Hit** (`AtkParam_Pc.<id>.…`): `62502` Black Flame Ritual — fire 106; `62503` Black Flame Ritual — fire 106; `62507` Black Flame Ritual — fire 109; `62508` Black Flame Ritual — fire 109

### 6250 · Black Flame Blade
*15 FP · 1 memory slot · workshops: Enchant tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1626000` Black Flame Blade (lasts 7 s); `1626001` Black Flame Blade (DoT Black) (lasts 2 s)

### 6260 · Black Flame's Protection
*30 FP · 1 memory slot · workshops: Buff tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1627000` Black Flame's Protection (lasts 70 s); `1627001` Black Flame's Protection (lasts 0.1 s)

### 6270 · Noble Presence
*20 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1624000` Noble Presence (lasts 0.6 s); `1624010` Noble Presence (DoT Black) (lasts 2 s)
- **Bullet** (`Bullet.<id>.…`): `10624000` Noble Presence; `10624001` Noble Presence; `10624050` Noble Presence; `10624051` Noble Presence
- **Hit** (`AtkParam_Pc.<id>.…`): `62401` Noble Presence — fire 239; `62406` Noble Presence — fire 279

### 6300 · Bloodflame Talons
*12 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1630000` Bloodflame Talons (Self) (lasts 2 s); `1630001` Bloodflame Talons (Cycled) (lasts 0.1 s)
- **Bullet** (`Bullet.<id>.…`): `10630000` Bloodflame Talons; `10630001` Bloodflame Talons
- **Hit** (`AtkParam_Pc.<id>.…`): `63000` Bloodflame Talons — fire 236

### 6310 · Bloodboon
*13 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1631000` Bloodboon (Self) (lasts 2 s); `1631001` Bloodboon (Cycled) (lasts 0.1 s)
- **Bullet** (`Bullet.<id>.…`): `10631000` Bloodboon; `10631001` Bloodboon; `10631002` Bloodboon; `10631005` Bloodboon
- **Hit** (`AtkParam_Pc.<id>.…`): `63100` Bloodboon — fire 159; `63101` Bloodboon — fire 44

### 6320 · Bloodflame Blade
*20 FP · 1 memory slot · workshops: Enchant tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1632000` Bloodflame Blade (Self) (lasts 60 s); `1632001` Bloodflame Blade (Cycled) (lasts 2 s); `1632002` Bloodflame Blade (Cycled) (lasts 0.1 s)

### 6330 · Barrier of Gold
*30 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1633000` Barrier of Gold (lasts 70 s)
- **Bullet** (`Bullet.<id>.…`): `10633000` Barrier of Gold; `10633001` Barrier of Gold
- **Hit** (`AtkParam_Pc.<id>.…`): `63300` Barrier of Gold — no damage; `63301` Barrier of Gold — no damage

### 6340 · Protection of The Erdtree
*30 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1634000` Protection of the Erdtree (lasts 70 s)
- **Bullet** (`Bullet.<id>.…`): `10634000` Protection of the Erdtree; `10634001` Protection of the Erdtree
- **Hit** (`AtkParam_Pc.<id>.…`): `63400` Protection of the Erdtree — no damage; `63401` Protection of the Erdtree — no damage

### 6400 · Rejection
*9 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1640000` Rejection (lasts 0.6 s)
- **Bullet** (`Bullet.<id>.…`): `10640000` Rejection; `10640050` Rejection
- **Hit** (`AtkParam_Pc.<id>.…`): `64000` Rejection — no damage; `64005` Rejection — no damage

### 6410 · Wrath of Gold
*40 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1641000` Wrath of Gold (lasts 0.6 s)
- **Bullet** (`Bullet.<id>.…`): `10641000` Wrath of Gold; `10641050` Wrath of Gold [Charged]
- **Hit** (`AtkParam_Pc.<id>.…`): `64100` Wrath of Gold — no damage; `64105` Wrath of Gold — no damage

### 6420 · Urgent Heal
*16 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1642000` Urgent Heal (instant / no timer)
- **Bullet** (`Bullet.<id>.…`): `10642000` Urgent Heal
- **Hit** (`AtkParam_Pc.<id>.…`): `64200` Urgent Heal — no damage

### 6421 · Heal
*32 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1642100` Heal (instant / no timer); `1642101` Heal - Allies (instant / no timer)
- **Bullet** (`Bullet.<id>.…`): `10642100` Heal; `10642101` Heal
- **Hit** (`AtkParam_Pc.<id>.…`): `64210` Heal — no damage; `64211` Heal — no damage

### 6422 · Great Heal
*45 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1642200` Great Heal (instant / no timer); `1642201` Great Heal - Allies (instant / no timer)
- **Bullet** (`Bullet.<id>.…`): `10642200` Great Heal; `10642201` Great Heal
- **Hit** (`AtkParam_Pc.<id>.…`): `64220` Great Heal — no damage; `64221` Great Heal — no damage

### 6423 · Lord's Heal
*55 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1642300` Lord's Heal (instant / no timer); `1642301` Lord's Heal - Allies (instant / no timer)
- **Bullet** (`Bullet.<id>.…`): `10642300` Lord's Heal; `10642301` Lord's Heal
- **Hit** (`AtkParam_Pc.<id>.…`): `64230` Lord's Heal — no damage; `64231` Lord's Heal — no damage

### 6424 · Erdtree Heal
*65 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1642400` Erdtree Heal (instant / no timer); `1642401` Erdtree Heal - Allies (instant / no timer)
- **Bullet** (`Bullet.<id>.…`): `10642400` Erdtree Heal; `10642401` Erdtree Heal
- **Hit** (`AtkParam_Pc.<id>.…`): `64240` Erdtree Heal — no damage; `64241` Erdtree Heal — no damage

### 6430 · Blessing's Boon
*30 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `475` Blessing of the Erdtree - HP Regen (lasts 30 s); `1643000` Blessing's Boon (lasts 90 s); `1643001` Blessing's Boon - Allies (lasts 90 s)
- **Bullet** (`Bullet.<id>.…`): `10643000` Blessing's Boon; `10643001` Blessing's Boon
- **Hit** (`AtkParam_Pc.<id>.…`): `64300` Blessing's Boon — no damage; `64301` Blessing's Boon — no damage

### 6431 · Blessing of The Erdtree
*60 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `475` Blessing of the Erdtree - HP Regen (lasts 30 s); `1643100` Blessing of the Erdtree (lasts 90 s); `1643101` Blessing of the Erdtree - Allies (lasts 90 s)
- **Bullet** (`Bullet.<id>.…`): `10643100` Blessing of the Erdtree; `10643101` Blessing of the Erdtree
- **Hit** (`AtkParam_Pc.<id>.…`): `64310` Blessing of the Erdtree — no damage; `64311` Blessing of the Erdtree — no damage

### 6440 · Cure Poison
*7 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1644000` Cure Poison (instant / no timer); `1644001` Cure Poison (instant / no timer)
- **Bullet** (`Bullet.<id>.…`): `10644000` Cure Poison
- **Hit** (`AtkParam_Pc.<id>.…`): `64400` Cure Poison — no damage

### 6441 · Lord's Aid
*12 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **SpEffect** (`SpEffect.<id>.…`): `1644100` Lord's Aid (instant / no timer); `1644101` Lord's Aid (instant / no timer); `1644102` Lord's Aid (instant / no timer); `1644103` Lord's Aid (instant / no timer); `1644104` Lord's Aid (instant / no timer); `1644105` Lord's Aid (instant / no timer); `1644110` Lord's Aid (instant / no timer); `1644111` Lord's Aid (instant / no timer); `1644112` Lord's Aid (instant / no timer); `1644113` Lord's Aid (instant / no timer); `1644114` Lord's Aid (instant / no timer); `1644115` Lord's Aid (instant / no timer)
- **Bullet** (`Bullet.<id>.…`): `10644100` Lord's Aid; `10644101` Lord's Aid; `10644110` Lord's Aid - Allies; `10644111` Lord's Aid - Allies
- **Hit** (`AtkParam_Pc.<id>.…`): `64410` Lord's Aid — no damage; `64411` Lord's Aid — no damage

### 6450 · Flame Fortification
*20 FP · 1 memory slot · workshops: Buff tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1645000` Flame Fortification (lasts 90 s)

### 6460 · Magic Fortification
*20 FP · 1 memory slot · workshops: Buff tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1646000` Magic Fortification (lasts 90 s)

### 6470 · Lightning Fortification
*20 FP · 1 memory slot · workshops: Buff tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1647000` Lightning Fortification (lasts 90 s)

### 6480 · Divine Fortification
*20 FP · 1 memory slot · workshops: Buff tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1648000` Divine Fortification (lasts 90 s)

### 6490 · Lord's Divine Fortification
*30 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1649000` Lord's Divine Fortification (lasts 70 s)
- **Bullet** (`Bullet.<id>.…`): `10649000` Lord's Divine Fortification; `10649001` Lord's Divine Fortification - Allies
- **Hit** (`AtkParam_Pc.<id>.…`): `64900` Lord's Divine Fortification — no damage; `64901` Lord's Divine Fortification — no damage

### 6510 · Assassin's Approach
*15 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1651000` Assassin's Approach (lasts 30 s); `1651001` Assassin's Approach (Cycled) (lasts 0.1 s); `1651002` Assassin's Approach (lasts 20 s)
- **Bullet** (`Bullet.<id>.…`): `10651001` Assassin's Approach
- **Hit** (`AtkParam_Pc.<id>.…`): `65101` Assassin's Approach — no damage

### 6520 · Shadow Bait
*15 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `481` Shadow Bait (lasts 1 s)
- **Bullet** (`Bullet.<id>.…`): `10652000` Shadow Bait; `10652001` Shadow Bait
- **Hit** (`AtkParam_Pc.<id>.…`): `65200` Shadow Bait — no damage; `65201` Shadow Bait — no damage

### 6530 · Darkness
*24 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1653000` Darkness (instant / no timer); `1653001` Darkness (Chained) (lasts 7 s)
- **Bullet** (`Bullet.<id>.…`): `10653000` Darkness; `10653001` Darkness
- **Hit** (`AtkParam_Pc.<id>.…`): `65300` Darkness — no damage; `65301` Darkness — no damage

### 6600 · Golden Vow
*47 FP · 1 memory slot · workshops: Fireball*


### 6700 · Discus of Light
*3 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10670000` Discus of Light; `10670001` Discus of Light; `10670002` Discus of Light; `10670003` Discus of Light
- **Hit** (`AtkParam_Pc.<id>.…`): `67000` Discus of Light — no damage; `67001` Discus of Light — no damage; `67002` Discus of Light — no damage; `67003` Discus of Light — no damage

### 6701 · Triple Rings of Light
*23 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10670100` Triple Rings of Light; `10670101` Triple Rings of Light; `10670102` Triple Rings of Light; `10670103` Triple Rings of Light; `10670105` Triple Rings of Light
- **Hit** (`AtkParam_Pc.<id>.…`): `67010` Triple Rings of Light — no damage; `67011` Triple Rings of Light — no damage; `67012` Triple Rings of Light — no damage; `67013` Triple Rings of Light — no damage; `67014` Triple Rings of Light — no damage

### 6710 · Radagon's Rings of Light
*21 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10671000` Radagon's Rings of Light; `10671001` Radagon's Rings of Light; `10671050` Radagon's Rings of Light [Charged]; `10671051` Radagon's Rings of Light
- **Hit** (`AtkParam_Pc.<id>.…`): `67100` Radagon's Rings of Light — no damage; `67105` Radagon's Rings of Light — no damage

### 6720 · Elden Stars
*41 FP · 2 memory slots · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10672000` Elden Stars; `10672001` Elden Stars; `10672002` Elden Stars; `10672003` Elden Stars; `10672004` Elden Stars; `10672005` Elden Stars; `10672006` Elden Stars
- **Hit** (`AtkParam_Pc.<id>.…`): `67200` Elden Stars — no damage; `67201` Elden Stars — no damage; `67202` Elden Stars — no damage

### 6730 · Law of Regression
*55 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **SpEffect** (`SpEffect.<id>.…`): `503041` [Item] Mimic's Veil (lasts 0.1 s); `1673000` Law of Regression (instant / no timer); `1673001` Law of Regression (instant / no timer); `1673002` Law of Regression (instant / no timer); `1673003` Law of Regression (instant / no timer); `1673004` Law of Regression (instant / no timer); `1673005` Law of Regression (instant / no timer); `1673006` Law of Regression (instant / no timer); `1673007` Law of Regression (instant / no timer); `1673008` Law of Regression (instant / no timer); `1673009` Law of Regression (instant / no timer); `1673010` Law of Regression (instant / no timer); `1673011` Law of Regression (instant / no timer); `1673012` Law of Regression (instant / no timer); `1673013` Law of Regression (instant / no timer); `1673014` Law of Regression (lasts 1 s); `1673020` Law of Regression (instant / no timer); `1673021` Law of Regression (instant / no timer); `1673022` Law of Regression (instant / no timer); `1673023` Law of Regression (instant / no timer); `1673024` Law of Regression (instant / no timer); `1673025` Law of Regression (instant / no timer); `1673026` Law of Regression (instant / no timer); `1673027` Law of Regression (instant / no timer); `1673028` Law of Regression (instant / no timer); `1673029` Law of Regression (instant / no timer); `1673030` Law of Regression (instant / no timer); `1673031` Law of Regression (instant / no timer); `1673032` Law of Regression (instant / no timer); `1673033` Law of Regression (instant / no timer); `1673034` Law of Regression (lasts 1 s)
- **Bullet** (`Bullet.<id>.…`): `10673000` Law of Regression; `10673001` Law of Regression; `10673002` Law of Regression; `10673010` Law of Regression; `10673011` Law of Regression; `10673012` Law of Regression; `10673013` Law of Regression
- **Hit** (`AtkParam_Pc.<id>.…`): `67300` Law of Regression — no damage; `67301` Law of Regression — no damage

### 6740 · Immutable Shield
*15 FP · 1 memory slot · workshops: Enchant tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1674000` Immutable Shield (lasts 30 s); `1674001` Immutable Shield (Cycled) (lasts 0.1 s); `1674002` Immutable Shield (lasts 0.1 s)

### 6750 · Litany of Proper Death
*17 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1675000` Litany of Proper Death (lasts 0.1 s)
- **Bullet** (`Bullet.<id>.…`): `10675000` Litany of Proper Death; `10675001` Litany of Proper Death; `10675002` Litany of Proper Death; `10675003` Litany of Proper Death; `10675004` Litany of Proper Death; `10675005` Litany of Proper Death; `10675006` Litany of Proper Death; `10675007` Litany of Proper Death; `10675008` Litany of Proper Death; `10675009` Litany of Proper Death; `10675010` Litany of Proper Death; `10675011` Litany of Proper Death; `10675012` Litany of Proper Death; `10675013` Litany of Proper Death; `10675014` Litany of Proper Death; `10675015` Litany of Proper Death
- **Hit** (`AtkParam_Pc.<id>.…`): `67500` Litany of Proper Death — no damage

### 6760 · Law of Causality
*22 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1676000` Law of Causality (lasts 120 s); `1676005` Law of Causality (Chained) (lasts 121 s); `1676006` Law of Causality (Chained) (lasts 0.05 s); `1676007` Law of Causality (Chained) (lasts 0.05 s); `1676008` Law of Causality (Chained) (lasts 0.1 s); `1676009` Law of Causality (Chained) (lasts 0.1 s); `1676010` Law of Causality (lasts 1 s); `1676011` Law of Causality (Chained) (instant / no timer)
- **Bullet** (`Bullet.<id>.…`): `10676000` Law of Causality
- **Hit** (`AtkParam_Pc.<id>.…`): `67601` Law of Causality — no damage

### 6770 · Order's Blade
*22 FP · 1 memory slot · workshops: Enchant tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1677000` Order's Blade (lasts 90 s)

### 6780 · Order Healing
*15 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1678000` Order Healing (instant / no timer); `1678001` Order Healing (instant / no timer)
- **Bullet** (`Bullet.<id>.…`): `10678000` Order Healing
- **Hit** (`AtkParam_Pc.<id>.…`): `67800` Order Healing — no damage

### 6800 · Bestial Sling
*7 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10680000` Bestial Sling; `10680001` Bestial Sling
- **Hit** (`AtkParam_Pc.<id>.…`): `68000` Bestial Sling — phys 87

### 6810 · Stone of Gurranq
*15 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10681000` Stone of Gurranq; `10681001` Stone of Gurranq
- **Hit** (`AtkParam_Pc.<id>.…`): `68100` Stone of Gurranq — phys 245

### 6820 · Beast Claw
*10 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **Bullet** (`Bullet.<id>.…`): `10682000` Beast Claw; `10682001` Beast Claw; `10682002` Beast Claw; `10682003` Beast Claw; `10682004` Beast Claw; `10682005` Beast Claw; `10682006` Beast Claw; `10682050` Beast Claw [Charged]; `10682051` Beast Claw; `10682052` Beast Claw; `10682053` Beast Claw; `10682054` Beast Claw; `10682055` Beast Claw; `10682056` Beast Claw; `10682057` Beast Claw; `10682058` Beast Claw; `10682059` Beast Claw; `10682060` Beast Claw; `10682061` Beast Claw; `10682062` Beast Claw
- **Hit** (`AtkParam_Pc.<id>.…`): `68200` Beast Claw — phys 193; `68205` Beast Claw — phys 222

### 6830 · Gurranq's Beast Claw
*21 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10683000` Gurranq's Beast Claw; `10683001` Gurranq's Beast Claw; `10683002` Gurranq's Beast Claw; `10683003` Gurranq's Beast Claw; `10683004` Gurranq's Beast Claw; `10683005` Gurranq's Beast Claw; `10683006` Gurranq's Beast Claw; `10683007` Gurranq's Beast Claw; `10683008` –
- **Hit** (`AtkParam_Pc.<id>.…`): `68300` Gurranq's Beast Claw — phys 225; `68301` – — phys 85

### 6840 · Bestial Vitality
*18 FP · 1 memory slot · workshops: Buff tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1685000` Bestial Vitality (lasts 120 s)

### 6850 · Bestial Constitution
*10 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1686000` Bestial Constitution (instant / no timer); `1686001` Bestial Constitution (instant / no timer); `1686002` Bestial Constitution (instant / no timer); `1686003` Bestial Constitution (instant / no timer)
- **Bullet** (`Bullet.<id>.…`): `10686000` Bestial Constitution; `10686001` Bestial Constitution
- **Hit** (`AtkParam_Pc.<id>.…`): `68600` Bestial Constitution — no damage

### 6900 · Lightning Spear
*18 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10690000` Lightning Spear; `10690001` Lightning Spear; `10690002` Lightning Spear; `10690003` Lightning Spear; `10690004` Lightning Spear; `10690050` Lightning Spear [Charged]; `10690051` Lightning Spear; `10690052` Lightning Spear; `10690053` Lightning Spear; `10690054` Lightning Spear; `10690055` Lightning Spear; `10690056` Lightning Spear; `10690057` Lightning Spear; `10690058` Lightning Spear; `10690059` Lightning Spear
- **Hit** (`AtkParam_Pc.<id>.…`): `69000` Lightning Spear — lightning 234; `69001` Lightning Spear — lightning 50; `69005` Lightning Spear — lightning 293; `69006` Lightning Spear [Charged] — lightning 50

### 6910 · Ancient Dragons' Light Strike
*36 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **Bullet** (`Bullet.<id>.…`): `10691000` Ancient Dragons' Lightning Strike; `10691001` Ancient Dragons' Lightning Strike; `10691002` Ancient Dragons' Lightning Strike; `10691003` Ancient Dragons' Lightning Strike; `10691004` Ancient Dragons' Lightning Strike; `10691005` Ancient Dragons' Lightning Strike; `10691010` Ancient Dragons' Lightning Strike; `10691011` Ancient Dragons' Lightning Strike; `10691012` Ancient Dragons' Lightning Strike; `10691013` Ancient Dragons' Lightning Strike; `10691014` Ancient Dragons' Lightning Strike; `10691015` Ancient Dragons' Lightning Strike; `10691016` Ancient Dragons' Lightning Strike; `10691020` Ancient Dragons' Lightning Strike; `10691021` Ancient Dragons' Lightning Strike; `10691022` Ancient Dragons' Lightning Strike; `10691023` Ancient Dragons' Lightning Strike; `10691024` Ancient Dragons' Lightning Strike; `10691025` Ancient Dragons' Lightning Strike; `10691050` Ancient Dragons' Lightning Strike [Charged]; `10691051` Ancient Dragons' Lightning Strike; `10691052` Ancient Dragons' Lightning Strike; `10691053` Ancient Dragons' Lightning Strike; `10691054` Ancient Dragons' Lightning Strike; `10691055` Ancient Dragons' Lightning Strike; `10691060` Ancient Dragons' Lightning Strike; `10691061` Ancient Dragons' Lightning Strike; `10691062` Ancient Dragons' Lightning Strike; `10691063` Ancient Dragons' Lightning Strike; `10691064` Ancient Dragons' Lightning Strike; `10691065` Ancient Dragons' Lightning Strike; `10691066` Ancient Dragons' Lightning Strike; `10691070` Ancient Dragons' Lightning Strike; `10691071` Ancient Dragons' Lightning Strike; `10691072` Ancient Dragons' Lightning Strike; `10691073` Ancient Dragons' Lightning Strike; `10691074` Ancient Dragons' Lightning Strike; `10691075` Ancient Dragons' Lightning Strike
- **Hit** (`AtkParam_Pc.<id>.…`): `69100` Ancient Dragons' Lightning Strike — lightning 317; `69101` Ancient Dragons' Lightning Strike — lightning 50; `69105` Ancient Dragons' Lightning Strike [Charged] — lightning 379; `69106` Ancient Dragons' Lightning Strike — lightning 50

### 6920 · Lightning Strike
*19 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10692000` Lightning Strike; `10692002` Lightning Strike; `10692003` Lightning Strike; `10692004` Lightning Strike; `10692005` Lightning Strike; `10692006` Lightning Strike; `10692009` Lightning Strike; `10692010` Lightning Strike; `10692011` Lightning Strike; `10692012` Lightning Strike; `10692013` Lightning Strike; `10692014` Lightning Strike; `10692015` Lightning Strike; `10692016` Lightning Strike
- **Hit** (`AtkParam_Pc.<id>.…`): `69200` Lightning Strike — lightning 246; `69201` Lightning Strike — lightning 50

### 6921 · Frozen Lightning Spear
*29 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1692100` Frozen Lightning Spear (Self) (lasts 30 s)
- **Bullet** (`Bullet.<id>.…`): `10692100` Frozen Lightning Spear; `10692101` Frozen Lightning Spear; `10692102` Frozen Lightning Spear; `10692103` Frozen Lightning Spear; `10692104` Frozen Lightning Spear; `10692105` Frozen Lightning Spear; `10692106` Frozen Lightning Spear; `10692107` Frozen Lightning Spear; `10692109` Frozen Lightning Spear; `10692110` Frozen Lightning Spear; `10692111` Frozen Lightning Spear; `10692112` Frozen Lightning Spear
- **Hit** (`AtkParam_Pc.<id>.…`): `69210` Frozen Lightning Spear — lightning 240; `69211` Frozen Lightning Spear — lightning 307

### 6930 · Honed Bolt
*12 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10693000` Honed Bolt; `10693001` Honed Bolt; `10693002` Honed Bolt; `10693003` Honed Bolt; `10693004` Honed Bolt; `10693005` Honed Bolt; `10693006` Honed Bolt; `10693007` Honed Bolt; `10693008` Honed Bolt
- **Hit** (`AtkParam_Pc.<id>.…`): `69300` Honed Bolt — lightning 205; `69301` Honed Bolt — lightning 50

### 6940 · Ancient Dragons' Light Spear
*25 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10694000` Ancient Dragons' Lightning Spear; `10694001` Ancient Dragons' Lightning Spear; `10694002` Ancient Dragons' Lightning Spear; `10694003` Ancient Dragons' Lightning Spear; `10694004` Ancient Dragons' Lightning Spear; `10694005` Ancient Dragons' Lightning Spear; `10694006` Ancient Dragons' Lightning Spear; `10694007` Ancient Dragons' Lightning Spear; `10694008` Ancient Dragons' Lightning Spear; `10694009` Ancient Dragons' Lightning Spear; `10694010` Ancient Dragons' Lightning Spear; `10694011` Ancient Dragons' Lightning Spear; `10694012` Ancient Dragons' Lightning Spear; `10694013` Ancient Dragons' Lightning Spear; `10694014` Ancient Dragons' Lightning Spear; `10694015` Ancient Dragons' Lightning Spear
- **Hit** (`AtkParam_Pc.<id>.…`): `69400` Ancient Dragons' Lightning Spear — lightning 360; `69401` Ancient Dragons' Lightning Spear — lightning 122; `69402` Ancient Dragons' Lightning Spear — lightning 285

### 6941 · Fortissax's Light Spear
*35 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **Bullet** (`Bullet.<id>.…`): `10694100` Fortissax's Lightning Spear; `10694101` Fortissax's Lightning Spear; `10694102` Fortissax's Lightning Spear; `10694103` Fortissax's Lightning Spear; `10694104` Fortissax's Lightning Spear; `10694105` Fortissax's Lightning Spear; `10694106` Fortissax's Lightning Spear; `10694107` Fortissax's Lightning Spear; `10694108` Fortissax's Lightning Spear; `10694109` Fortissax's Lightning Spear; `10694110` Fortissax's Lightning Spear; `10694111` Fortissax's Lightning Spear; `10694112` Fortissax's Lightning Spear; `10694113` Fortissax's Lightning Spear; `10694114` Fortissax's Lightning Spear; `10694115` Fortissax's Lightning Spear; `10694150` Fortissax's Lightning Spear; `10694151` Fortissax's Lightning Spear; `10694152` Fortissax's Lightning Spear; `10694153` Fortissax's Lightning Spear; `10694154` Fortissax's Lightning Spear; `10694155` Fortissax's Lightning Spear; `10694156` Fortissax's Lightning Spear; `10694157` Fortissax's Lightning Spear; `10694158` Fortissax's Lightning Spear; `10694159` Fortissax's Lightning Spear; `10694160` Fortissax's Lightning Spear; `10694161` Fortissax's Lightning Spear; `10694162` Fortissax's Lightning Spear; `10694163` Fortissax's Lightning Spear; `10694164` Fortissax's Lightning Spear; `10694165` Fortissax's Lightning Spear
- **Hit** (`AtkParam_Pc.<id>.…`): `69410` Fortissax's Lightning Spear — lightning 367; `69411` Fortissax's Lightning Spear — lightning 122; `69412` Fortissax's Lightning Spear — lightning 288; `69415` Fortissax's Lightning Spear — lightning 374; `69416` Fortissax's Lightning Spear — lightning 123; `69417` Fortissax's Lightning Spear — lightning 292

### 6950 · Lansseax's Glaive
*22 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10695000` Lansseax's Glaive; `10695001` Lansseax's Glaive; `10695002` Lansseax's Glaive; `10695003` Lansseax's Glaive; `10695004` Lansseax's Glaive; `10695005` Lansseax's Glaive; `10695006` Lansseax's Glaive; `10695007` Lansseax's Glaive; `10695008` Lansseax's Glaive; `10695009` Lansseax's Glaive; `10695010` Lansseax's Glaive; `10695011` Lansseax's Glaive; `10695012` Lansseax's Glaive; `10695013` Lansseax's Glaive
- **Hit** (`AtkParam_Pc.<id>.…`): `69500` Lansseax's Glaive — lightning 325; `69501` Lansseax's Glaive — lightning 325; `69502` Lansseax's Glaive — lightning 167

### 6960 · Electrify Armament
*27 FP · 1 memory slot · workshops: Enchant tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1696000` Electrify Armament (lasts 90 s)

### 6970 · Vyke's Dragonbolt
*35 FP · 1 memory slot · workshops: Enchant tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1697000` Vyke's Dragonbolt (lasts 70 s); `1697001` Vyke's Dragonbolt (lasts 70 s); `1697002` Vyke's Dragonbolt (Cycled) (lasts 0.1 s)

### 6971 · Dragonbolt Blessing
*20 FP · 1 memory slot · workshops: Buff tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1697100` Dragonbolt Blessing (lasts 70 s); `1697101` Dragonbolt Blessing (Cycled) (lasts 0.1 s)

### 7000 · Dragonfire
*28 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10700000` Dragonfire; `10700001` Dragonfire; `10700002` Dragonfire
- **Hit** (`AtkParam_Pc.<id>.…`): `70000` Dragonfire — fire 144

### 7001 · Agheel's Flame
*36 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10700100` Agheel's Flame; `10700101` Agheel's Flame; `10700102` Agheel's Flame; `10700110` Agheel's Flame
- **Hit** (`AtkParam_Pc.<id>.…`): `70010` Agheel's Flame — fire 169

### 7010 · Magma Breath
*30 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10701000` Magma Breath; `10701001` Magma Breath; `10701002` Magma Breath; `10701003` Magma Breath; `10701004` Magma Breath; `10701005` Magma Breath; `10701009` Magma Breath; `10701010` Magma Breath
- **Hit** (`AtkParam_Pc.<id>.…`): `70100` Magma Breath — fire 223; `70101` Magma Breath — fire 34; `70102` Magma Breath — fire 223; `70109` Magma Breath — no damage

### 7011 · Theodorix's Magma
*45 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10701100` Theodorix's Magma; `10701101` Theodorix's Magma; `10701102` Theodorix's Magma; `10701103` Theodorix's Magma; `10701104` Theodorix's Magma; `10701105` Theodorix's Magma; `10701109` Theodorix's Magma; `10701110` Theodorix's Magma
- **Hit** (`AtkParam_Pc.<id>.…`): `70110` Theodorix's Magma — fire 315; `70111` Theodorix's Magma — fire 40; `70112` Theodorix's Magma — fire 315; `70119` Theodorix's Magma — no damage

### 7020 · Dragonice
*36 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1702000` Dragonice (Self) (lasts 30 s)
- **Bullet** (`Bullet.<id>.…`): `10702000` Dragonice; `10702001` Dragonice; `10702002` Dragonice
- **Hit** (`AtkParam_Pc.<id>.…`): `70200` Dragonice — magic 135

### 7021 · Borealis's Mist
*48 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1702100` Borealis's Mist (Self) (lasts 30 s)
- **Bullet** (`Bullet.<id>.…`): `10702100` Borealis's Mist; `10702101` Borealis's Mist; `10702102` Borealis's Mist; `10702110` Borealis's Mist
- **Hit** (`AtkParam_Pc.<id>.…`): `70210` Borealis's Mist — magic 158

### 7030 · Rotten Breath
*36 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1703000` Rotten Breath (Self) (lasts 90 s)
- **Bullet** (`Bullet.<id>.…`): `10703000` Rotten Breath; `10703001` Rotten Breath; `10703002` Rotten Breath
- **Hit** (`AtkParam_Pc.<id>.…`): `70300` Rotten Breath — phys 131

### 7031 · Ekzykes's Decay
*48 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1703100` Ekzyke's Decay (Self) (lasts 90 s)
- **Bullet** (`Bullet.<id>.…`): `10703100` Ekzykes's Decay; `10703101` Ekzykes's Decay; `10703102` Ekzykes's Decay; `10703110` Ekzykes's Decay
- **Hit** (`AtkParam_Pc.<id>.…`): `70310` Ekzykes's Decay — phys 155

### 7040 · Glintstone Breath
*28 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10704000` Glintstone Breath; `10704001` Glintstone Breath; `10704002` Glintstone Breath
- **Hit** (`AtkParam_Pc.<id>.…`): `70400` Glintstone Breath — magic 159

### 7041 · Smarag's Glint Breath
*36 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10704100` Smarag's Glintstone Breath; `10704101` Smarag's Glintstone Breath; `10704102` Smarag's Glintstone Breath; `10704110` Smarag's Glintstone Breath
- **Hit** (`AtkParam_Pc.<id>.…`): `70410` Smarag's Glintstone Breath — magic 188

### 7050 · Placidusax's Ruin
*62 FP · 3 memory slots · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10705000` Placidusax's Ruin; `10705001` Placidusax's Ruin; `10705002` Placidusax's Ruin; `10705003` Placidusax's Ruin; `10705004` Placidusax's Ruin; `10705010` Placidusax's Ruin
- **Hit** (`AtkParam_Pc.<id>.…`): `70500` Placidusax's Ruin — fire 356; `70501` Placidusax's Ruin — fire 356; `70502` Placidusax's Ruin — lightning 241

### 7060 · Dragonclaw
*24 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10706000` Dragonclaw; `10706001` Dragonclaw; `10706002` Dragonclaw; `10706003` Dragonclaw
- **Hit** (`AtkParam_Pc.<id>.…`): `70600` Dragonclaw — phys 395; `70601` Dragonclaw — phys 410; `70602` Dragonclaw — phys 395; `70603` Dragonclaw — phys 410; `70605` Dragonclaw — phys 253; `70606` Dragonclaw — phys 263

### 7080 · Dragonmaw
*34 FP · 1 memory slot · workshops: Strike*

- **Hit** (`AtkParam_Pc.<id>.…`): `70800` Dragonmaw — phys 628

### 7090 · Greyoll's Roar
*50 FP · 2 memory slots · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1709000` Greyoll's Roar (lasts 60 s); `1709001` – (lasts 0.1 s)
- **Bullet** (`Bullet.<id>.…`): `10709000` Greyoll's Roar; `10709001` Greyoll's Roar
- **Hit** (`AtkParam_Pc.<id>.…`): `70900` Greyoll's Roar — phys 320

### 7200 · Pest Threads
*19 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10720000` Pest Threads (Midleft); `10720001` Pest Threads (Midright); `10720002` Pest Threads (Rightmost); `10720003` Pest Threads (Leftmost); `10720004` Pest Threads; `10720005` Pest Threads
- **Hit** (`AtkParam_Pc.<id>.…`): `72000` Pest Threads — phys 60

### 7210 · Swarm of Flies
*14 FP · 1 memory slot · workshops: Fireball*


### 7220 · Poison Mist
*18 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1722000` Poison Mist (Self) (lasts 90 s)
- **Bullet** (`Bullet.<id>.…`): `10722000` Poison Mist; `10722001` Poison Mist
- **Hit** (`AtkParam_Pc.<id>.…`): `72200` Poison Mist — no damage

### 7230 · Poison Armament
*15 FP · 1 memory slot · workshops: Enchant tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1723000` Poison Armament (Self) (lasts 60 s); `1723001` Poison Armament (lasts 90 s)

### 7240 · Scarlet Aeonia
*48 FP · 3 memory slots · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `6900` Accumulator Increase +2 (instant / no timer); `1724000` Scarlet Aeonia (Self) (lasts 90 s)
- **Bullet** (`Bullet.<id>.…`): `10724000` Scarlet Aeonia; `10724001` Scarlet Aeonia
- **Hit** (`AtkParam_Pc.<id>.…`): `72400` Scarlet Aeonia — phys 40; `72401` Scarlet Aeonia — phys 362; `72402` Scarlet Aeonia — phys 60

### 7300 · Inescapable Frenzy
*22 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1730001` – (lasts 1 s); `1730002` – (lasts 1 s)
- **Bullet** (`Bullet.<id>.…`): `10730000` Inescapable Frenzy; `10730001` Inescapable Frenzy
- **Hit** (`AtkParam_Pc.<id>.…`): `73000` Inescapable Frenzy 1 -Compare- — phys 70; `73002` Inescapable Frenzy 2 -Compare- — phys 70; `73010` Inescapable Frenzy -Compare- — no damage

### 7310 · The Flame of Frenzy
*16 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1731000` The Flame of Frenzy (lasts 1 s); `1731001` The Flame of Frenzy (lasts 1 s); `1731002` – (lasts 1 s); `1731003` – (lasts 1 s)
- **Bullet** (`Bullet.<id>.…`): `10731000` The Flame of Frenzy; `10731001` The Flame of Frenzy; `10731002` The Flame of Frenzy; `10731005` The Flame of Frenzy; `10731006` The Flame of Frenzy; `10731010` The Flame of Frenzy; `10731050` The Flame of Frenzy; `10731051` The Flame of Frenzy; `10731052` The Flame of Frenzy; `10731055` The Flame of Frenzy; `10731056` The Flame of Frenzy; `10731060` The Flame of Frenzy
- **Hit** (`AtkParam_Pc.<id>.…`): `73100` The Flame of Frenzy — fire 107; `73101` The Flame of Frenzy — fire 107; `73105` The Flame of Frenzy [Charged] — fire 124; `73106` The Flame of Frenzy — fire 124; `73109` The Flame of Frenzy — no damage

### 7311 · Unendurable Frenzy
*22 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1731100` Unendurable Frenzy (lasts 1 s); `1731101` Unendurable Frenzy (Self) (lasts 1 s)
- **Bullet** (`Bullet.<id>.…`): `10731100` Unendurable Frenzy; `10731103` Unendurable Frenzy; `10731104` Unendurable Frenzy; `10731105` Unendurable Frenzy; `10731106` Unendurable Frenzy; `10731107` Unendurable Frenzy; `10731108` Unendurable Frenzy; `10731110` Unendurable Frenzy; `10731115` Unendurable Frenzy; `10731116` Unendurable Frenzy; `10731117` Unendurable Frenzy
- **Hit** (`AtkParam_Pc.<id>.…`): `73110` Unendurable Frenzy — fire 125; `73111` Unendurable Frenzy — fire 125; `73112` Unendurable Frenzy — no damage

### 7320 · Frenzied Burst
*24 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1732000` Frenzied Burst (lasts 1 s); `1732001` Frenzied Burst (lasts 1 s); `1732002` – (lasts 1 s); `1732003` – (lasts 1 s)
- **Bullet** (`Bullet.<id>.…`): `10732000` Frenzied Burst; `10732050` Frenzied Burst [Charged]
- **Hit** (`AtkParam_Pc.<id>.…`): `73200` Frenzied Burst — fire 250; `73205` Frenzied Burst — fire 309

### 7330 · Howl of Shabriri
*21 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1733000` Howl of Shabriri (lasts 40 s); `1733001` Howl of Shabriri (lasts 1 s); `1733002` Howl of Shabriri (Self) (lasts 1 s); `1733005` Howl of Shabriri (lasts 0.1 s); `1733006` Howl of Shabriri (lasts 0.1 s); `1733007` Howl of Shabriri (lasts 0.1 s)
- **Bullet** (`Bullet.<id>.…`): `10733000` Howl of Shabriri; `10733001` Howl of Shabriri
- **Hit** (`AtkParam_Pc.<id>.…`): `73300` Howl of Shabriri — phys 22; `73301` Howl of Shabriri — no damage

### 7500 · Aspects of the Crucible: Tail
*20 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `6908` Accumulator Increase +18 (instant / no timer)
- **Hit** (`AtkParam_Pc.<id>.…`): `75000` Aspects of the Crucible: Tail — phys 202; `75005` Aspects of the Crucible: Tail [Charged] — phys 274

### 7510 · Aspects of the Crucible: Horns
*18 FP · 1 memory slot · workshops: Strike*

- **SpEffect** (`SpEffect.<id>.…`): `6908` Accumulator Increase +18 (instant / no timer)
- **Hit** (`AtkParam_Pc.<id>.…`): `75100` Aspects of the Crucible: Horns — phys 277; `75101` Aspects of the Crucible: Horns — phys 277; `75105` Aspects of the Crucible: Horns [Charged] — phys 327; `75106` Aspects of the Crucible: Horns — phys 327

### 7520 · Aspects of the Crucible: Breath
*28 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10752000` Aspects of the Crucible: Breath; `10752001` Aspects of the Crucible: Breath
- **Hit** (`AtkParam_Pc.<id>.…`): `75200` Aspects of the Crucible: Breath — fire 98

### 7530 · Black Blade
*26 FP · 2 memory slots · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `6850` Destined Death - (DoT Main) (lasts 2 s); `6860` Destined Death - (Max HP Debuff) (lasts 15 s); `6908` Accumulator Increase +18 (instant / no timer)
- **Bullet** (`Bullet.<id>.…`): `10753000` Black Blade; `10753001` Black Blade; `10753010` Black Blade; `10753011` Black Blade; `10753020` Black Blade; `10753021` Black Blade; `10753030` Black Blade; `10753031` Black Blade
- **Hit** (`AtkParam_Pc.<id>.…`): `75300` Black Blade — no damage; `75301` Black Blade — no damage; `75302` Black Blade — no damage; `75303` Black Blade — no damage; `75304` Black Blade — no damage; `75305` Black Blade — no damage; `75306` Black Blade — no damage; `75307` Black Blade — no damage

### 7900 · Fire's Deadly Sin
*26 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1790000` Fire's Deadly Sin (lasts 40 s); `1790001` Fire's Deadly Sin (lasts 0.3 s); `1790002` Fire's Deadly Sin (lasts 0.55 s); `1790003` Fire's Deadly Sin (lasts 0.1 s); `1790010` Fire's Deadly Sin (lasts 40 s); `1790011` Fire's Deadly Sin (lasts 0.3 s); `1790012` Fire's Deadly Sin (lasts 0.55 s)
- **Bullet** (`Bullet.<id>.…`): `10790001` Fire's Deadly Sin; `10790051` Fire's Deadly Sin; `10790099` Fire's Deadly Sin
- **Hit** (`AtkParam_Pc.<id>.…`): `79001` Fire's Deadly Sin — fire 183; `79006` Fire's Deadly Sin [Charged] — fire 212; `79009` Fire's Deadly Sin — no damage

### 7903 · Golden Light Fortification
*30 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1790300` Golden Lightning Fortification (lasts 70 s)
- **Bullet** (`Bullet.<id>.…`): `10790300` Golden Lightning Fortification; `10790301` Golden Lightning Fortification
- **Hit** (`AtkParam_Pc.<id>.…`): `79030` Golden Lightning Fortification — no damage; `79031` Golden Lightning Fortification — no damage

### 2006300 · Furious Blade of Ansbach
*18 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **SpEffect** (`SpEffect.<id>.…`): `6903` Accumulator Increase +8 (instant / no timer); `21630000` Furious Blade of Ansbach: Attack 1 (lasts 2 s); `21630001` Furious Blade of Ansbach: Attack 1 - Apply Hemorrhage (lasts 0.1 s); `21630002` Furious Blade of Ansbach: Attack 2 (lasts 2 s); `21630003` Furious Blade of Ansbach: Attack 2 - Apply Hemorrhage (lasts 0.1 s); `21630010` Furious Blade of Ansbach: Attack 3 (lasts 2 s); `21630011` Furious Blade of Ansbach: Attack 3 - Apply Hemorrhage (lasts 0.1 s); `21630012` Furious Blade of Ansbach: Attack 4 (lasts 2 s); `21630013` Furious Blade of Ansbach: Attack 4 - Apply Hemorrhage (lasts 0.1 s)
- **Bullet** (`Bullet.<id>.…`): `210630000` Furious Blade of Ansbach; `210630001` Furious Blade of Ansbach; `210630002` Furious Blade of Ansbach; `210630003` Furious Blade of Ansbach; `210630004` Furious Blade of Ansbach; `210630005` Furious Blade of Ansbach; `210630006` Furious Blade of Ansbach; `210630010` Furious Blade of Ansbach; `210630011` Furious Blade of Ansbach; `210630012` Furious Blade of Ansbach; `210630013` Furious Blade of Ansbach; `210630014` Furious Blade of Ansbach; `210630015` Furious Blade of Ansbach; `210630016` Furious Blade of Ansbach; `210630050` Furious Blade of Ansbach; `210630051` Furious Blade of Ansbach; `210630052` Furious Blade of Ansbach; `210630053` Furious Blade of Ansbach; `210630054` Furious Blade of Ansbach; `210630055` Furious Blade of Ansbach; `210630056` Furious Blade of Ansbach; `210630060` Furious Blade of Ansbach; `210630061` Furious Blade of Ansbach; `210630062` Furious Blade of Ansbach; `210630063` Furious Blade of Ansbach; `210630064` Furious Blade of Ansbach; `210630065` Furious Blade of Ansbach; `210630066` Furious Blade of Ansbach
- **Hit** (`AtkParam_Pc.<id>.…`): `210630000` Furious Blade of Ansbach — fire 97; `210630001` Furious Blade of Ansbach — fire 97; `210630010` Furious Blade of Ansbach — fire 154; `210630050` Furious Blade of Ansbach — fire 98; `210630051` Furious Blade of Ansbach — fire 98; `210630060` Furious Blade of Ansbach — fire 163

### 2006400 · Heal from Afar
*45 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `21640000` Heal from Afar: HP Gain (instant / no timer); `21640001` Heal from Afar: HP Gain for Allies (instant / no timer)
- **Bullet** (`Bullet.<id>.…`): `210640000` Heal from Afar; `210640001` Heal from Afar
- **Hit** (`AtkParam_Pc.<id>.…`): `210640000` Heal from Afar — no damage; `210640001` Heal from Afar — no damage

### 2006650 · Aspects of the Crucible: Thorns
*14 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210665000` Aspects of the Crucible: Thorns; `210665001` Aspects of the Crucible: Thorns; `210665002` Aspects of the Crucible: Thorns; `210665003` Aspects of the Crucible: Thorns; `210665004` Aspects of the Crucible: Thorns; `210665005` Aspects of the Crucible: Thorns; `210665006` Aspects of the Crucible: Thorns
- **Hit** (`AtkParam_Pc.<id>.…`): `210665000` Aspects of the Crucible: Thorns — phys 45; `210665001` Aspects of the Crucible: Thorns — phys 120

### 2006660 · Aspects of the Crucible: Bloom
*23 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210666000` Aspects of the Crucible: Bloom; `210666001` Aspects of the Crucible: Bloom; `210666002` Aspects of the Crucible: Bloom; `210666003` Aspects of the Crucible: Bloom; `210666004` Aspects of the Crucible: Bloom; `210666005` Aspects of the Crucible: Bloom; `210666050` Aspects of the Crucible: Bloom; `210666051` Aspects of the Crucible: Bloom; `210666052` Aspects of the Crucible: Bloom; `210666053` Aspects of the Crucible: Bloom; `210666054` Aspects of the Crucible: Bloom; `210666055` Aspects of the Crucible: Bloom
- **Hit** (`AtkParam_Pc.<id>.…`): `210666000` Aspects of the Crucible: Bloom — no damage; `210666050` Aspects of the Crucible: Bloom — no damage

### 2006670 · Minor Erdtree
*30 FP · 2 memory slots · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `475` Blessing of the Erdtree - HP Regen (lasts 30 s); `21667000` Minor Erdtree: HP Gain (lasts 0.5 s)
- **Bullet** (`Bullet.<id>.…`): `210667000` Minor Erdtree; `210667001` Minor Erdtree
- **Hit** (`AtkParam_Pc.<id>.…`): `210667000` Minor Erdtree — no damage

### 2006680 · Land of Shadow
*40 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210668000` Land of Shadow; `210668001` Land of Shadow; `210668002` Land of Shadow; `210668003` Land of Shadow; `210668004` Land of Shadow; `210668005` Land of Shadow; `210668006` Land of Shadow; `210668007` Land of Shadow; `210668008` Land of Shadow; `210668009` Land of Shadow
- **Hit** (`AtkParam_Pc.<id>.…`): `210668000` Land of Shadow — no damage; `210668001` Land of Shadow — no damage

### 2006690 · Wrath from Afar
*18 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210669000` Wrath from Afar; `210669001` Wrath from Afar; `210669050` Wrath from Afar; `210669051` Wrath from Afar
- **Hit** (`AtkParam_Pc.<id>.…`): `210669000` Wrath from Afar — no damage; `210669050` Wrath from Afar — no damage

### 2006700 · Light of Miquella
*48 FP · 2 memory slots · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210670000` Light of Miquella; `210670001` Light of Miquella; `210670002` Light of Miquella; `210670003` Light of Miquella; `210670004` Light of Miquella; `210670005` Light of Miquella; `210670006` Light of Miquella; `210670007` Light of Miquella; `210670008` Light of Miquella
- **Hit** (`AtkParam_Pc.<id>.…`): `210670000` Light of Miquella — no damage; `210670001` Light of Miquella — no damage

### 2006710 · Multilayered Ring of Light
*23 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210671000` Multilayered Ring of Light; `210671001` Multilayered Ring of Light; `210671002` Multilayered Ring of Light; `210671050` Multilayered Ring of Light; `210671051` Multilayered Ring of Light; `210671052` Multilayered Ring of Light
- **Hit** (`AtkParam_Pc.<id>.…`): `210671000` Multilayered Ring of Light — no damage; `210671001` Multilayered Ring of Light — no damage; `210671050` Multilayered Ring of Light — no damage; `210671051` Multilayered Ring of Light — no damage

### 2006800 · Roar of Rugalea
*17 FP · 1 memory slot · workshops: Fireball*

- **Hit** (`AtkParam_Pc.<id>.…`): `210680000` Roar of Rugalea — phys 355; `210680050` Roar of Rugalea — phys 250; `210680051` Roar of Rugalea — phys 30; `210680052` Roar of Rugalea — phys 200; `210680053` – — phys 100

### 2006900 · Knight's Lightning Spear
*29 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **Bullet** (`Bullet.<id>.…`): `210690000` Knight's Lightning Spear; `210690001` Knight's Lightning Spear; `210690002` Knight's Lightning Spear; `210690003` Knight's Lightning Spear; `210690004` Knight's Lightning Spear; `210690005` Knight's Lightning Spear; `210690006` Knight's Lightning Spear; `210690007` Knight's Lightning Spear; `210690008` Knight's Lightning Spear; `210690009` Knight's Lightning Spear; `210690010` Knight's Lightning Spear; `210690050` Knight's Lightning Spear; `210690051` Knight's Lightning Spear; `210690052` Knight's Lightning Spear; `210690053` Knight's Lightning Spear; `210690054` Knight's Lightning Spear; `210690055` Knight's Lightning Spear; `210690056` Knight's Lightning Spear; `210690057` Knight's Lightning Spear; `210690058` Knight's Lightning Spear; `210690059` Knight's Lightning Spear; `210690060` Knight's Lightning Spear; `210690061` Knight's Lightning Spear; `210690062` Knight's Lightning Spear; `210690063` Knight's Lightning Spear; `210690064` Knight's Lightning Spear; `210690065` Knight's Lightning Spear
- **Hit** (`AtkParam_Pc.<id>.…`): `210690000` Knight's Lightning Spear — lightning 138; `210690001` Knight's Lightning Spear — lightning 50; `210690002` Knight's Lightning Spear Bullet — lightning 138; `210690050` Knight's Lightning Spear — lightning 164; `210690051` Knight's Lightning Spear — lightning 50; `210690052` Knight's Lightning Spear Bullet — lightning 164

### 2006910 · Dragonbolt of Florissax
*35 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `21691000` Dragonbolt of Florissax: Setup (lasts 70 s); `21691001` Dragonbolt of Florissax: Body Effect - Absorption Boost (lasts 0.1 s); `21691002` Dragonbolt of Florissax: Left-hand Effect - Absorption Boost (lasts 0.1 s)
- **Bullet** (`Bullet.<id>.…`): `210691000` Dragonbolt of Florissax; `210691001` Dragonbolt of Florissax
- **Hit** (`AtkParam_Pc.<id>.…`): `210691000` Dragonbolt of Florissax — no damage; `210691001` Dragonbolt of Florissax — no damage

### 2006920 · Electrocharge
*26 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `21692000` Electrocharge: Setup (lasts 45 s); `21692001` Electrocharge: Behavior (Bullet) (lasts 0.3 s); `21692002` Electrocharge: (lasts 0.55 s); `21692010` Electrocharge: Setup (lasts 45 s); `21692011` Electrocharge: Behavior (Bullet) (lasts 0.3 s); `21692012` Electrocharge (lasts 0.55 s)
- **Bullet** (`Bullet.<id>.…`): `210692000` Electrocharge; `210692050` Electrocharge
- **Hit** (`AtkParam_Pc.<id>.…`): `210692001` Electrocharge — lightning 213; `210692051` Electrocharge — lightning 262

### 2007000 · Bayle's Tyranny
*46 FP · 2 memory slots · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210700000` Bayle's Tyranny; `210700001` Bayle's Tyranny; `210700002` Bayle's Tyranny; `210700003` Bayle's Tyranny; `210700004` Bayle's Tyranny; `210700005` Bayle's Tyranny
- **Hit** (`AtkParam_Pc.<id>.…`): `210700000` Bayle's Tyranny — fire 325 · lightning 210; `210700001` Bayle's Tyranny — fire 50 · lightning 20

### 2007010 · Bayle's Flame Lightning
*43 FP · 2 memory slots · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210701000` Bayle's Flame Lightning; `210701001` Bayle's Flame Lightning; `210701002` Bayle's Flame Lightning; `210701003` Bayle's Flame Lightning
- **Hit** (`AtkParam_Pc.<id>.…`): `210701000` Bayle's Flame Lightning — phys 280 · fire 220 · lightning 280; `210701001` Bayle's Flame Lightning — fire 30 · lightning 15; `210701002` Bayle's Flame Lightning — fire 150 · lightning 200

### 2007020 · Ghostflame Breath
*36 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `21702000` Ghostflame Breath: Apply Frostbite (lasts 30 s)
- **Bullet** (`Bullet.<id>.…`): `210702000` Ghostflame Breath; `210702001` Ghostflame Breath; `210702002` Ghostflame Breath; `210702010` Ghostflame Breath
- **Hit** (`AtkParam_Pc.<id>.…`): `210702000` Ghostflame Breath — magic 168

### 2007200 · Rotten Butterflies
*48 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `21720000` Rotten Butterflies: Apply Scarlet Rot (lasts 90 s); `21720001` Rotten Butterflies: Apply Scarlet Rot (lasts 90 s)
- **Bullet** (`Bullet.<id>.…`): `210720000` Rotten Butterflies; `210720001` Rotten Butterflies; `210720002` Rotten Butterflies; `210720003` Rotten Butterflies; `210720004` Rotten Butterflies; `210720005` Rotten Butterflies; `210720006` Rotten Butterflies; `210720007` Rotten Butterflies; `210720008` Rotten Butterflies
- **Hit** (`AtkParam_Pc.<id>.…`): `210720000` Rotten Butterflies — phys 100; `210720001` Rotten Butterflies — phys 100

### 2007210 · Pest-Thread Spears
*28 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210721000` Pest-Thread Spears; `210721001` Pest-Thread Spears; `210721050` Pest-Thread Spears; `210721051` Pest-Thread Spears
- **Hit** (`AtkParam_Pc.<id>.…`): `210721000` Pest-Thread Spears — phys 180; `210721050` Pest-Thread Spears — phys 230

### 2007300 · Midra's Flame of Frenzy
*22 FP · 2 memory slots · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `21730000` Midra's Flame of Frenzy: Apply Madness (lasts 1 s); `21730001` Midra's Flame of Frenzy: Apply Madness (lasts 1 s); `21730002` Midra's Flame of Frenzy: Apply Madness (lasts 1 s)
- **Bullet** (`Bullet.<id>.…`): `210730000` Midra's Flame of Frenzy; `210730001` Midra's Flame of Frenzy; `210730002` Midra's Flame of Frenzy; `210730003` Midra's Flame of Frenzy; `210730004` Midra's Flame of Frenzy; `210730005` Midra's Flame of Frenzy; `210730006` Midra's Flame of Frenzy; `210730007` Midra's Flame of Frenzy; `210730008` Midra's Flame of Frenzy; `210730009` Midra's Flame of Frenzy; `210730010` Midra's Flame of Frenzy; `210730011` Midra's Flame of Frenzy
- **Hit** (`AtkParam_Pc.<id>.…`): `210730000` Midra's Flame of Frenzy — fire 75; `210730010` Midra's Flame of Frenzy — no damage

### 2007600 · Watchful Spirit
*12 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210760000` Watchful Spirit; `210760001` Watchful Spirit
- **Hit** (`AtkParam_Pc.<id>.…`): `210760000` Watchful Spirit — no damage

### 2007700 · Golden Arcs
*12 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210770000` Golden Arcs; `210770050` Golden Arcs
- **Hit** (`AtkParam_Pc.<id>.…`): `210770000` Golden Arcs — no damage; `210770050` Golden Arcs — no damage

### 2007710 · Giant Golden Arc
*24 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210771000` Giant Golden Arc; `210771001` Giant Golden Arc; `210771050` Giant Golden Arc; `210771051` Giant Golden Arc
- **Hit** (`AtkParam_Pc.<id>.…`): `210771000` Giant Golden Arc — no damage; `210771050` Giant Golden Arc — no damage

### 2007720 · Spira
*10 FP · 2 memory slots · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210772000` Spira; `210772001` Spira; `210772002` Spira; `210772003` Spira; `210772004` Spira
- **Hit** (`AtkParam_Pc.<id>.…`): `210772000` Spira — no damage

### 2007730 · Divine Beast Tornado
*24 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210773000` Divine Beast Tornado; `210773001` Divine Beast Tornado; `210773010` Divine Beast Tornado; `210773050` Divine Beast Tornado; `210773051` Divine Beast Tornado
- **Hit** (`AtkParam_Pc.<id>.…`): `210773000` Divine Beast Tornado — phys 220; `210773010` Divine Beast Tornado — no damage; `210773050` Divine Beast Tornado — phys 275

### 2007740 · Divine Bird Feathers
*3 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210774000` Divine Bird Feathers
- **Hit** (`AtkParam_Pc.<id>.…`): `210774000` Divine Bird Feathers — phys 53

### 2007800 · Fire Serpent
*11 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210780000` Fire Serpent; `210780001` Fire Serpent; `210780002` Fire Serpent; `210780003` Fire Serpent; `210780050` Fire Serpent; `210780051` Fire Serpent; `210780052` Fire Serpent; `210780053` Fire Serpent
- **Hit** (`AtkParam_Pc.<id>.…`): `210780000` Fire Serpent — fire 168; `210780050` Fire Serpent — fire 210

### 2007810 · Rain of Fire
*27 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **Bullet** (`Bullet.<id>.…`): `210781000` Rain of Fire; `210781001` Rain of Fire; `210781002` Rain of Fire; `210781003` Rain of Fire; `210781004` Rain of Fire; `210781005` Rain of Fire; `210781006` Rain of Fire; `210781007` Rain of Fire; `210781008` Rain of Fire; `210781050` Rain of Fire; `210781051` Rain of Fire; `210781052` Rain of Fire; `210781053` Rain of Fire; `210781054` Rain of Fire; `210781055` Rain of Fire; `210781056` Rain of Fire; `210781057` Rain of Fire; `210781058` Rain of Fire
- **Hit** (`AtkParam_Pc.<id>.…`): `210781000` Rain of Fire — fire 62; `210781001` Rain of Fire — fire 62; `210781050` Rain of Fire — fire 75; `210781051` Rain of Fire — fire 75

### 2007820 · Messmer's Orb
*31 FP · 2 memory slots · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210782000` Messmer's Orb; `210782001` Messmer's Orb; `210782050` Messmer's Orb; `210782051` Messmer's Orb
- **Hit** (`AtkParam_Pc.<id>.…`): `210782000` Messmer's Orb — fire 50; `210782001` Messmer's Orb — fire 50; `210782002` Messmer's Orb — fire 50; `210782003` Messmer's Orb — fire 308; `210782050` Messmer's Orb — fire 70; `210782051` Messmer's Orb — fire 70; `210782052` Messmer's Orb — fire 70; `210782053` Messmer's Orb — fire 411

## Sorceries (84)

### 4000 · Glintstone Pebble
*7 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10400000` Glintstone Pebble; `10400099` Glintstone Pebble
- **Hit** (`AtkParam_Pc.<id>.…`): `40000` Glintstone Pebble — magic 152

### 4001 · Great Glintstone Shard
*12 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10400100` Great Glintstone Shard; `10400199` Great Glintstone Shard
- **Hit** (`AtkParam_Pc.<id>.…`): `40010` Great Glintstone Shard — magic 211

### 4010 · Swift Glintstone Shard
*5 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10401000` Swift Glintstone Shard
- **Hit** (`AtkParam_Pc.<id>.…`): `40100` Swift Glintstone Shard — magic 114

### 4020 · Glintstone Cometshard
*17 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10402000` –; `10402050` –
- **Hit** (`AtkParam_Pc.<id>.…`): `40200` Comet — magic 259; `40201` Glintstone Cometshard — magic 324

### 4021 · Comet
*24 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10402100` Comet; `10402150` Comet [Charged]; `10402151` Comet [Hit]
- **Hit** (`AtkParam_Pc.<id>.…`): `40210` Comet — magic 292; `40211` Comet — magic 365; `40212` Comet [Hit] — magic 365

### 4030 · Shard Spiral
*14 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10403000` Shard Spiral; `10403001` Shard Spiral - Emitted; `10403050` Shard Spiral [Charged]; `10403051` Shard Spiral - Emitted
- **Hit** (`AtkParam_Pc.<id>.…`): `40300` Shard Spiral - Emitted — magic 92; `40301` Shard Spiral — magic 110

### 4040 · Glintstone Stars
*12 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **Bullet** (`Bullet.<id>.…`): `10404000` Glintstone Stars - Emitter 1; `10404001` Glintstone Stars; `10404002` Glintstone Stars; `10404003` Glintstone Stars; `10404004` Glintstone Stars; `10404005` Glintstone Stars; `10404006` Glintstone Stars; `10404007` Glintstone Stars; `10404008` Glintstone Stars; `10404009` Glintstone Stars; `10404010` Glintstone Stars; `10404011` Glintstone Stars; `10404050` Glintstone Stars - Emitter [Charged]; `10404051` Glintstone Stars; `10404052` Glintstone Stars; `10404053` Glintstone Stars; `10404054` Glintstone Stars; `10404055` Glintstone Stars; `10404056` Glintstone Stars; `10404057` Glintstone Stars; `10404058` Glintstone Stars; `10404059` Glintstone Stars; `10404060` Glintstone Stars; `10404061` Glintstone Stars; `10404099` Glintstone Stars
- **Hit** (`AtkParam_Pc.<id>.…`): `40400` Glintstone Stars — magic 87; `40401` Glintstone Stars — magic 78; `40402` Glintstone Stars — magic 68; `40405` Glintstone Stars — magic 99; `40406` Glintstone Stars [Charged] — magic 90; `40407` Glintstone Stars — magic 80

### 4050 · Star Shower
*23 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **Bullet** (`Bullet.<id>.…`): `10404099` Glintstone Stars; `10405000` Star Shower - Emitter 1; `10405001` Star Shower; `10405002` Star Shower; `10405003` Star Shower; `10405004` Star Shower; `10405005` Star Shower; `10405006` Star Shower; `10405007` Star Shower; `10405008` Star Shower; `10405009` Star Shower; `10405010` Star Shower; `10405011` Star Shower; `10405012` Star Shower; `10405013` Star Shower; `10405014` Star Shower; `10405015` Star Shower; `10405016` Star Shower; `10405017` Star Shower; `10405018` Star Shower; `10405019` Star Shower; `10405020` Star Shower; `10405021` Star Shower; `10405022` Star Shower; `10405023` Star Shower; `10405050` Star Shower - Emitter [Charged]; `10405051` Star Shower; `10405052` Star Shower; `10405053` Star Shower; `10405054` Star Shower; `10405055` Star Shower; `10405056` Star Shower; `10405057` Star Shower; `10405058` Star Shower; `10405059` Star Shower; `10405060` Star Shower; `10405061` Star Shower; `10405062` Star Shower; `10405063` Star Shower; `10405064` Star Shower; `10405065` Star Shower; `10405066` Star Shower; `10405067` Star Shower; `10405068` Star Shower; `10405069` Star Shower; `10405070` Star Shower; `10405071` Star Shower; `10405072` Star Shower; `10405073` Star Shower
- **Hit** (`AtkParam_Pc.<id>.…`): `40500` Star Shower — magic 79; `40501` Star Shower — magic 69; `40502` Star Shower — magic 69; `40503` Star Shower — magic 59; `40504` Star Shower — magic 49; `40505` Star Shower — magic 44; `40510` Star Shower — magic 88; `40511` Star Shower [Charged] — magic 78; `40512` Star Shower — magic 68; `40513` Star Shower — magic 63; `40514` Star Shower — magic 58; `40515` Star Shower — magic 53

### 4060 · Crystal Barrage
*14 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10406000` Crystal Barrage; `10406001` Crystal Barrage; `10406099` Crystal Barrage
- **Hit** (`AtkParam_Pc.<id>.…`): `40600` Crystal Barrage — magic 36; `40601` Crystal Barrage — magic 36

### 4070 · Glintstone Arc
*9 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10407000` Glintstone Arc; `10407001` Glintstone Arc; `10407002` Glintstone Arc; `10407003` Glintstone Arc; `10407004` Glintstone Arc; `10407005` Glintstone Arc; `10407006` Glintstone Arc; `10407007` Glintstone Arc; `10407099` Glintstone Arc
- **Hit** (`AtkParam_Pc.<id>.…`): `40070` Glintstone Arc — magic 148

### 4080 · Cannon of Haima
*38 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10408000` Cannon of Haima; `10408001` Cannon of Haima; `10408050` Cannon of Haima [Charged]; `10408051` Cannon of Haima
- **Hit** (`AtkParam_Pc.<id>.…`): `40800` Cannon of Haima — no damage; `40801` Cannon of Haima — magic 285; `40805` Cannon of Haima — no damage; `40806` Cannon of Haima [Charged] — magic 332

### 4090 · Crystal Burst
*14 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10409000` Crystal Burst; `10409001` Crystal Burst; `10409002` Crystal Burst; `10409050` Crystal Burst [Charged]; `10409051` Crystal Burst; `10409052` Crystal Burst
- **Hit** (`AtkParam_Pc.<id>.…`): `40900` Crystal Burst — magic 40; `40905` Crystal Burst — magic 45

### 4100 · Shatter Earth
*10 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10410000` Shatter Earth; `10410001` Shatter Earth; `10410002` Shatter Earth
- **Hit** (`AtkParam_Pc.<id>.…`): `41000` Shatter Earth — magic 182; `41001` Shatter Earth — magic 205; `41002` Shatter Earth — magic 52; `41003` Shatter Earth — magic 68; `41004` Shatter Earth — magic 68; `41005` – — magic 68; `41006` – — magic 68

### 4110 · Rock Blaster
*22 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `6900` Accumulator Increase +2 (instant / no timer)
- **Bullet** (`Bullet.<id>.…`): `10411000` Rock Blaster; `10411010` Rock Blaster; `10411011` Rock Blaster; `10411012` Rock Blaster; `10411013` Rock Blaster; `10411014` Rock Blaster; `10411015` Rock Blaster
- **Hit** (`AtkParam_Pc.<id>.…`): `41100` Rock Blaster — magic 64; `41101` Rock Blaster — magic 260; `41102` Rock Blaster — magic 64; `41103` Rock Blaster — magic 64

### 4120 · Gavel of Haima
*22 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10412000` Gavel of Haima; `10412001` Gavel of Haima
- **Hit** (`AtkParam_Pc.<id>.…`): `41200` Gavel of Haima — magic 297; `41201` Gavel of Haima — magic 297; `41205` Gavel of Haima — magic 242; `41206` Gavel of Haima — magic 242

### 4130 · Terra Magicus
*20 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1413000` Terra Magicus (lasts 1.5 s)
- **Bullet** (`Bullet.<id>.…`): `10413000` Terra Magicus; `10413001` Terra Magicus; `10413002` Terra Magicus; `10413003` Terra Magicus
- **Hit** (`AtkParam_Pc.<id>.…`): `41300` Terra Magicus — no damage

### 4140 · Starlight
*9 FP · 1 memory slot · workshops: Buff tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1414000` Starlight (lasts 180 s)

### 4200 · Comet Azur
*40 FP · 3 memory slots · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10420000` Comet Azur - Constant Close Attack; `10420001` Comet Azur - Infrequent Stagger Bullet; `10420002` Comet Azur - Constant Projectile; `10420003` Comet Azur - Release Final Bullet; `10420004` Comet Azur - Intial Cast Close Knockback
- **Hit** (`AtkParam_Pc.<id>.…`): `42000` Comet Azur — magic 55; `42001` Comet Azur - Constant Close Attack — magic 90; `42002` Comet Azur - Infrequent Stagger Bullet — magic 75; `42003` Comet Azur - Constant Projectile — magic 100; `42004` Comet Azur - Release Final Bullet — magic 55

### 4210 · Founding Rain of Stars
*27 FP · 2 memory slots · workshops: none (too big for one shelf: Photocopier only)*

- **Bullet** (`Bullet.<id>.…`): `10421000` Founding Rain of Stars; `10421001` Founding Rain of Stars; `10421002` Founding Rain of Stars; `10421003` Founding Rain of Stars; `10421004` Founding Rain of Stars; `10421005` Founding Rain of Stars; `10421006` Founding Rain of Stars; `10421007` Founding Rain of Stars; `10421008` Founding Rain of Stars; `10421050` Founding Rain of Stars [Charged]; `10421051` Founding Rain of Stars; `10421052` Founding Rain of Stars; `10421053` Founding Rain of Stars; `10421054` Founding Rain of Stars; `10421055` Founding Rain of Stars; `10421056` Founding Rain of Stars; `10421057` Founding Rain of Stars; `10421058` Founding Rain of Stars
- **Hit** (`AtkParam_Pc.<id>.…`): `42100` Founding Rain of Stars — magic 54; `42105` Founding Rain of Stars — magic 60

### 4220 · Stars of Ruin
*32 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **Bullet** (`Bullet.<id>.…`): `10422000` Stars of Ruin; `10422001` Stars of Ruin; `10422002` Stars of Ruin; `10422003` Stars of Ruin; `10422004` Stars of Ruin; `10422005` Stars of Ruin; `10422006` Stars of Ruin; `10422007` Stars of Ruin; `10422008` Stars of Ruin; `10422009` Stars of Ruin; `10422010` Stars of Ruin; `10422011` Stars of Ruin; `10422015` Stars of Ruin; `10422016` Stars of Ruin; `10422017` Stars of Ruin; `10422018` Stars of Ruin; `10422019` Stars of Ruin; `10422020` Stars of Ruin; `10422021` Stars of Ruin; `10422022` Stars of Ruin; `10422023` Stars of Ruin; `10422024` Stars of Ruin; `10422025` Stars of Ruin; `10422026` Stars of Ruin; `10422030` Stars of Ruin; `10422031` Stars of Ruin; `10422032` Stars of Ruin; `10422033` Stars of Ruin; `10422034` Stars of Ruin; `10422035` Stars of Ruin; `10422036` Stars of Ruin; `10422037` Stars of Ruin; `10422050` Stars of Ruin [Charged]; `10422051` Stars of Ruin; `10422052` Stars of Ruin; `10422053` Stars of Ruin; `10422054` Stars of Ruin; `10422055` Stars of Ruin; `10422056` Stars of Ruin; `10422057` Stars of Ruin; `10422058` Stars of Ruin; `10422059` Stars of Ruin; `10422060` Stars of Ruin; `10422061` Stars of Ruin; `10422065` Stars of Ruin; `10422066` Stars of Ruin; `10422067` Stars of Ruin; `10422068` Stars of Ruin; `10422069` Stars of Ruin; `10422070` Stars of Ruin; `10422071` Stars of Ruin; `10422072` Stars of Ruin; `10422073` Stars of Ruin; `10422074` Stars of Ruin; `10422075` Stars of Ruin; `10422076` Stars of Ruin; `10422080` Stars of Ruin; `10422081` Stars of Ruin; `10422082` Stars of Ruin; `10422083` Stars of Ruin; `10422084` Stars of Ruin; `10422085` Stars of Ruin; `10422086` Stars of Ruin; `10422087` Stars of Ruin; `10422098` Stars of Ruin; `10422099` Stars of Ruin
- **Hit** (`AtkParam_Pc.<id>.…`): `42200` Stars of Ruin — magic 52; `42201` Stars of Ruin — magic 52; `42202` Stars of Ruin — magic 49; `42203` Stars of Ruin — magic 49; `42204` Stars of Ruin — magic 45; `42205` Stars of Ruin — magic 45; `42206` Stars of Ruin — magic 43; `42207` Stars of Ruin — magic 43; `42210` Stars of Ruin — magic 65; `42211` Stars of Ruin [Charged] — magic 65; `42212` Stars of Ruin — magic 60; `42213` Stars of Ruin — magic 60; `42214` Stars of Ruin — magic 57; `42215` Stars of Ruin — magic 57; `42216` Stars of Ruin — magic 54; `42217` Stars of Ruin — magic 54

### 4300 · Glintblade Phalanx
*18 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10430000` Glintblade Phalanx; `10430001` Glintblade Phalanx
- **Hit** (`AtkParam_Pc.<id>.…`): `43000` Glintblade Phalanx — magic 60; `43001` Glintblade Phalanx — magic 60

### 4301 · Carian Phalanx
*24 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10430100` Carian Phalanx; `10430101` Carian Phalanx
- **Hit** (`AtkParam_Pc.<id>.…`): `43010` Carian Phalanx — magic 48; `43011` Carian Phalanx — magic 48

### 4302 · Greatblade Phalanx
*30 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10430200` Greatblade Phalanx; `10430201` Greatblade Phalanx
- **Hit** (`AtkParam_Pc.<id>.…`): `43020` Greatblade Phalanx — magic 100; `43021` Greatblade Phalanx — magic 100

### 4360 · Rennala's Full Moon
*47 FP · 2 memory slots · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1436000` Rennala's Full Moon (lasts 60 s)
- **Bullet** (`Bullet.<id>.…`): `10436000` Rennala's Full Moon; `10436001` Rennala's Full Moon; `10436002` Rennala's Full Moon
- **Hit** (`AtkParam_Pc.<id>.…`): `43600` Rennala's Full Moon — magic 360

### 4361 · Ranni's Dark Moon
*57 FP · 2 memory slots · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1436100` Ranni's Dark Moon (lasts 30 s); `1436101` – (lasts 60 s)
- **Bullet** (`Bullet.<id>.…`): `10436100` Ranni's Dark Moon; `10436101` Ranni's Dark Moon; `10436102` Ranni's Dark Moon
- **Hit** (`AtkParam_Pc.<id>.…`): `43610` Ranni's Dark Moon — magic 330

### 4370 · Magic Downpour
*18 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **Bullet** (`Bullet.<id>.…`): `10437000` Magic Downpour; `10437001` Magic Downpour; `10437002` Magic Downpour; `10437003` Magic Downpour; `10437004` Magic Downpour; `10437005` Magic Downpour; `10437050` Magic Downpour [Charged]; `10437051` Magic Downpour; `10437052` Magic Downpour; `10437053` Magic Downpour; `10437054` Magic Downpour; `10437055` Magic Downpour
- **Hit** (`AtkParam_Pc.<id>.…`): `43700` Magic Downpour — no damage; `43701` Magic Downpour — no damage; `43702` Magic Downpour — magic 58; `43703` Magic Downpour — no damage; `43704` Magic Downpour — no damage; `43705` Magic Downpour — magic 58; `43706` Magic Downpour — no damage; `43707` Magic Downpour — no damage; `43708` Magic Downpour — magic 58; `43709` Magic Downpour — no damage; `43710` Magic Downpour — no damage; `43711` Magic Downpour [Charged] — magic 58

### 4380 · Loretta's Greatbow
*24 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10438000` Loretta's Greatbow; `10438001` Loretta's Greatbow; `10438050` Loretta's Greatbow [Charged]; `10438051` Loretta's Greatbow
- **Hit** (`AtkParam_Pc.<id>.…`): `43801` Loretta's Greatbow — magic 270; `43806` Loretta's Greatbow [Charged] — magic 330

### 4381 · Loretta's Mastery
*39 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10438100` Loretta's Mastery; `10438101` Loretta's Mastery; `10438102` Loretta's Mastery; `10438110` Loretta's Mastery; `10438111` Loretta's Mastery; `10438112` Loretta's Mastery; `10438150` Loretta's Mastery [Charged]; `10438151` Loretta's Mastery; `10438152` Loretta's Mastery; `10438160` Loretta's Mastery; `10438161` Loretta's Mastery; `10438162` Loretta's Mastery
- **Hit** (`AtkParam_Pc.<id>.…`): `43811` Loretta's Mastery — magic 108; `43816` Loretta's Mastery [Charged] — magic 127

### 4390 · Magic Glintblade
*12 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10439000` Magic Glintblade; `10439001` Magic Glintblade; `10439002` Magic Glintblade; `10439003` Magic Glintblade; `10439050` Magic Glintblade [Charged]; `10439051` Magic Glintblade; `10439052` Magic Glintblade; `10439053` Magic Glintblade
- **Hit** (`AtkParam_Pc.<id>.…`): `43900` Magic Glintblade — magic 182; `43905` Magic Glintblade — magic 230

### 4400 · Glintstone Icecrag
*12 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1440000` Glintstone Icecrag (lasts 30 s)
- **Bullet** (`Bullet.<id>.…`): `10440000` Glintstone Icecrag
- **Hit** (`AtkParam_Pc.<id>.…`): `44000` Glintstone Icecrag — magic 199

### 4410 · Zamor Ice Storm
*17 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1441000` Zamor Ice Storm (lasts 30 s)
- **Bullet** (`Bullet.<id>.…`): `10441000` Zamor Ice Storm; `10441001` Zamor Ice Storm; `10441002` Zamor Ice Storm; `10441009` Zamor Ice Storm; `10441050` Zamor Ice Storm [Charged]; `10441051` Zamor Ice Storm; `10441052` Zamor Ice Storm; `10441059` Zamor Ice Storm
- **Hit** (`AtkParam_Pc.<id>.…`): `44100` Zamor Ice Storm — magic 99; `44101` Zamor Ice Storm — magic 74; `44105` Zamor Ice Storm — magic 104; `44106` Zamor Ice Storm [Charged] — magic 79

### 4420 · Freezing Mist
*20 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1442000` Freezing Mist (lasts 30 s)
- **Bullet** (`Bullet.<id>.…`): `10442000` Freezing Mist; `10442001` Freezing Mist; `10442050` Freezing Mist [Charged]; `10442051` Freezing Mist
- **Hit** (`AtkParam_Pc.<id>.…`): `44200` Freezing Mist — no damage; `44205` Freezing Mist [Charged] — no damage

### 4430 · Carian Greatsword
*12 FP · 1 memory slot · workshops: Strike*

- **SpEffect** (`SpEffect.<id>.…`): `6904` Accumulator Increase +10 (instant / no timer)
- **Hit** (`AtkParam_Pc.<id>.…`): `44300` Carian Greatsword — magic 268; `44301` Carian Greatsword — magic 268; `44305` Carian Greatsword — magic 268; `44306` Carian Greatsword — magic 268; `44307` Carian Greatsword — magic 272; `44308` Carian Greatsword — magic 272

### 4431 · Adula's Moonblade
*22 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `6904` Accumulator Increase +10 (instant / no timer); `1443100` – (lasts 30 s); `1443101` Adula's Moonblade (lasts 30 s)
- **Bullet** (`Bullet.<id>.…`): `10443100` Adula's Moonblade; `10443101` Adula's Moonblade; `10443110` Adula's Moonblade; `10443111` Adula's Moonblade; `10443120` Adula's Moonblade; `10443121` Adula's Moonblade; `10443130` Adula's Moonblade; `10443131` Adula's Moonblade
- **Hit** (`AtkParam_Pc.<id>.…`): `44310` Adula's Moonblade — magic 133; `44311` Adula's Moonblade — magic 133; `44315` Adula's Moonblade — magic 133; `44316` Adula's Moonblade — magic 133; `44317` Adula's Moonblade — magic 137; `44318` Adula's Moonblade — magic 137; `44319` Adula's Moonblade — magic 189

### 4440 · Carian Slicer
*4 FP · 1 memory slot · workshops: Strike*

- **SpEffect** (`SpEffect.<id>.…`): `6901` Accumulator Increase +4 (instant / no timer)
- **Hit** (`AtkParam_Pc.<id>.…`): `44400` Carian Slicer — magic 180; `44401` Carian Slicer — magic 180; `44405` Carian Slicer — magic 180; `44406` Carian Slicer — magic 180; `44407` Carian Slicer — magic 184; `44408` Carian Slicer — magic 184

### 4450 · Carian Piercer
*17 FP · 1 memory slot · workshops: Strike*

- **SpEffect** (`SpEffect.<id>.…`): `6906` Accumulator Increase +14 (instant / no timer)
- **Hit** (`AtkParam_Pc.<id>.…`): `44500` Carian Piercer — magic 287; `44501` Carian Piercer — magic 287; `44505` Carian Piercer [Charged] — magic 355; `44506` Carian Piercer — magic 355

### 4460 · Scholar's Armament
*25 FP · 1 memory slot · workshops: Enchant tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1446000` Scholar's Armament (lasts 90 s)

### 4470 · Scholar's Shield
*30 FP · 1 memory slot · workshops: Enchant tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1447000` Scholar's Shield (lasts 60 s); `1447001` Scholar's Shield (Cycled) (lasts 0.1 s)

### 4480 · Lucidity
*10 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1448000` Lucidity (instant / no timer); `1448001` Lucidity (instant / no timer); `1448002` Lucidity (instant / no timer); `1448003` Lucidity (instant / no timer)
- **Bullet** (`Bullet.<id>.…`): `10448000` Lucidity; `10448001` Lucidity
- **Hit** (`AtkParam_Pc.<id>.…`): `44800` Lucidity — no damage

### 4490 · Frozen Armament
*20 FP · 1 memory slot · workshops: Enchant tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1449000` Frozen Armament (lasts 60 s); `1449001` Frozen Armament (lasts 30 s)

### 4500 · Shattering Crystal
*21 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10450000` Shattering Crystal; `10450001` Shattering Crystal; `10450002` Shattering Crystal; `10450003` Shattering Crystal; `10450004` Shattering Crystal; `10450050` Shattering Crystal [Charged]; `10450051` Shattering Crystal; `10450052` Shattering Crystal; `10450053` Shattering Crystal; `10450054` Shattering Crystal
- **Hit** (`AtkParam_Pc.<id>.…`): `45000` Shattering Crystal — magic 127; `45001` Shattering Crystal — magic 60; `45002` Shattering Crystal — magic 51; `45005` Shattering Crystal [Charged] — magic 160; `45006` Shattering Crystal — magic 75; `45007` Shattering Crystal — magic 67

### 4510 · Crystal Release
*34 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10451000` Crystal Release; `10451001` Crystal Release; `10451002` Crystal Release; `10451010` Crystal Release; `10451011` Crystal Release; `10451012` Crystal Release; `10451020` Crystal Release; `10451021` Crystal Release; `10451022` Crystal Release
- **Hit** (`AtkParam_Pc.<id>.…`): `45100` Crystal Release — magic 100; `45101` Crystal Release — magic 125

### 4520 · Crystal Torrent
*20 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10452000` Crystal Torrent; `10452001` Crystal Torrent; `10452002` Crystal Torrent
- **Hit** (`AtkParam_Pc.<id>.…`): `45200` Crystal Torrent — magic 57; `45201` Crystal Torrent — magic 57

### 4600 · Ambush Shard
*13 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10460000` Ambush Shard; `10460001` Ambush Shard; `10460002` Ambush Shard; `10460003` Ambush Shard
- **Hit** (`AtkParam_Pc.<id>.…`): `46000` Ambush Shard — magic 146

### 4610 · Night Shard
*7 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10461000` Night Shard; `10461001` Night Shard
- **Hit** (`AtkParam_Pc.<id>.…`): `46100` Night Shard — magic 111

### 4620 · Night Comet
*21 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10462000` Night Comet; `10462001` Night Comet; `10462050` Night Comet [Charged]; `10462051` Night Comet
- **Hit** (`AtkParam_Pc.<id>.…`): `46200` Night Comet — magic 230; `46201` Night Comet — magic 276; `46202` Night Comet — no damage

### 4630 · Thops's Barrier
*7 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10463000` Thops's Barrier
- **Hit** (`AtkParam_Pc.<id>.…`): `79984` Thops's Barrier — no damage

### 4640 · Carian Retaliation
*8 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1464000` – (instant / no timer)
- **Bullet** (`Bullet.<id>.…`): `10464000` Carian Retaliation; `10464001` Carian Retaliation
- **Hit** (`AtkParam_Pc.<id>.…`): `7` Phantom Great Rune Bullet — no damage

### 4650 · Eternal Darkness
*25 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10465000` Eternal Darkness; `10465001` Eternal Darkness

### 4660 · Unseen Blade
*13 FP · 1 memory slot · workshops: Enchant tuner*

- **SpEffect** (`SpEffect.<id>.…`): `1466000` Unseen Blade (lasts 45 s)

### 4670 · Unseen Form
*20 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1467000` Unseen Form (lasts 30 s); `1467001` Unseen Form (lasts 1 s); `1467002` Unseen Form (lasts 30 s); `1467005` Unseen Form (lasts 30 s); `1467006` Unseen Form (lasts 1 s)
- **Bullet** (`Bullet.<id>.…`): `10467001` Unseen Form
- **Hit** (`AtkParam_Pc.<id>.…`): `46701` Unseen Form — no damage

### 4700 · Meteorite
*30 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **Bullet** (`Bullet.<id>.…`): `10470000` Meteorite; `10470001` Meteorite; `10470002` Meteorite - Projectile; `10470003` Meteorite; `10470005` Meteorite; `10470006` Meteorite; `10470007` Meteorite - Projectile; `10470008` Meteorite; `10470010` Meteorite; `10470011` Meteorite; `10470012` Meteorite - Projectile; `10470013` Meteorite; `10470020` Meteorite; `10470021` Meteorite; `10470022` Meteorite - Projectile; `10470023` Meteorite; `10470030` Meteorite; `10470031` Meteorite; `10470032` Meteorite - Projectile; `10470033` Meteorite; `10470040` Meteorite; `10470041` Meteorite; `10470042` Meteorite - Projectile; `10470043` Meteorite
- **Hit** (`AtkParam_Pc.<id>.…`): `47000` Meteorite — phys 180 · magic 100; `47001` Meteorite — phys 180 · magic 100

### 4701 · Meteorite of Astel
*60 FP · 2 memory slots · workshops: none (too big for one shelf: Photocopier only)*

- **Bullet** (`Bullet.<id>.…`): `10470100` Meteorite of Astel; `10470101` Meteorite of Astel; `10470102` Meteorite of Astel; `10470103` Meteorite of Astel; `10470104` Meteorite of Astel; `10470105` Meteorite of Astel - Projectile; `10470106` Meteorite of Astel; `10470110` Meteorite of Astel; `10470111` Meteorite of Astel; `10470112` Meteorite of Astel; `10470113` Meteorite of Astel; `10470114` Meteorite of Astel; `10470115` Meteorite of Astel - Projectile; `10470120` Meteorite of Astel; `10470121` Meteorite of Astel; `10470122` Meteorite of Astel; `10470125` Meteorite of Astel - Projectile; `10470150` Meteorite of Astel; `10470151` Meteorite of Astel; `10470152` Meteorite of Astel
- **Hit** (`AtkParam_Pc.<id>.…`): `47010` Meteorite of Astel — phys 185 · magic 105; `47011` Meteorite of Astel — phys 185 · magic 105

### 4710 · Rock Sling
*18 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **Bullet** (`Bullet.<id>.…`): `10471000` Rock Sling; `10471001` Rock Sling; `10471002` Rock Sling; `10471003` Rock Sling; `10471004` Rock Sling; `10471005` Rock Sling; `10471006` Rock Sling; `10471007` Rock Sling; `10471008` Rock Sling; `10471009` Rock Sling; `10471010` Rock Sling; `10471011` Rock Sling; `10471012` Rock Sling; `10471050` Rock Sling [Hand]; `10471051` Rock Sling; `10471052` Rock Sling; `10471053` Rock Sling; `10471054` Rock Sling; `10471055` Rock Sling; `10471056` Rock Sling; `10471057` Rock Sling; `10471058` Rock Sling; `10471059` Rock Sling; `10471060` Rock Sling; `10471061` Rock Sling; `10471062` Rock Sling
- **Hit** (`AtkParam_Pc.<id>.…`): `47100` Rock Sling — phys 102

### 4720 · Gravity Well
*12 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10472000` Gravity Well; `10472050` Gravity Well [Charged]
- **Hit** (`AtkParam_Pc.<id>.…`): `47200` Gravity Well — magic 148; `47205` Gravity Well — magic 180

### 4721 · Collapsing Stars
*18 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10472100` Collapsing Stars; `10472101` Collapsing Stars; `10472105` Collapsing Stars; `10472150` Collapsing Stars [Charged]; `10472151` Collapsing Stars; `10472155` Collapsing Stars
- **Hit** (`AtkParam_Pc.<id>.…`): `47210` Collapsing Stars — magic 44; `47211` Collapsing Stars — magic 44; `47215` Collapsing Stars — magic 49; `47216` Collapsing Stars [Charged] — magic 49

### 4800 · Magma Shot
*16 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10480000` Magma Shot; `10480001` Magma Shot; `10480002` Magma Shot; `10480003` Magma Shot; `10480004` Magma Shot; `10480050` Magma Shot [Charged]; `10480051` Magma Shot; `10480052` Magma Shot; `10480053` Magma Shot; `10480054` Magma Shot
- **Hit** (`AtkParam_Pc.<id>.…`): `48000` Magma Shot — fire 210; `48001` Magma Shot — no damage; `48003` Magma Shot — fire 48; `48005` Magma Shot — fire 250; `48006` Magma Shot [Charged] — no damage; `48007` Magma Shot — fire 53

### 4810 · Gelmir's Fury
*16 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10481000` Gelmir's Fury; `10481001` Gelmir's Fury; `10481002` Gelmir's Fury; `10481003` Gelmir's Fury; `10481004` Gelmir's Fury; `10481005` Gelmir's Fury; `10481010` Gelmir's Fury; `10481011` Gelmir's Fury; `10481015` Gelmir's Fury
- **Hit** (`AtkParam_Pc.<id>.…`): `48100` Gelmir's Fury — fire 125; `48107` Gelmir's Fury — fire 125; `48108` Gelmir's Fury Bullet — fire 160

### 4820 · Roiling Magma
*28 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **Bullet** (`Bullet.<id>.…`): `10482000` Roiling Magma; `10482001` Roiling Magma; `10482002` Roiling Magma; `10482003` Roiling Magma; `10482004` Roiling Magma; `10482005` Roiling Magma; `10482006` Roiling Magma; `10482007` Roiling Magma; `10482050` Roiling Magma [Charged]; `10482051` Roiling Magma; `10482052` Roiling Magma; `10482053` Roiling Magma; `10482054` Roiling Magma; `10482055` Roiling Magma; `10482056` Roiling Magma; `10482057` Roiling Magma
- **Hit** (`AtkParam_Pc.<id>.…`): `48200` Roiling Magma — fire 234; `48201` Roiling Magma — no damage; `48202` Roiling Magma — no damage; `48203` Roiling Magma — no damage; `48204` Roiling Magma — fire 318; `48205` Roiling Magma — no damage; `48206` Roiling Magma — fire 43; `48210` Roiling Magma [Charged] — fire 325; `48211` Roiling Magma — no damage; `48212` Roiling Magma — no damage; `48213` Roiling Magma — no damage; `48214` Roiling Magma — fire 390; `48215` Roiling Magma — no damage; `48216` Roiling Magma — fire 48

### 4830 · Rykard's Rancor
*23 FP · 2 memory slots · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10483000` Rykard's Rancor; `10483001` Rykard's Rancor; `10483002` Rykard's Rancor; `10483003` Rykard's Rancor; `10483004` Rykard's Rancor; `10483005` Rykard's Rancor
- **Hit** (`AtkParam_Pc.<id>.…`): `48300` Rykard's Rancor — fire 150

### 4900 · Briars of Sin
*6 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1490000` – (instant / no timer); `1490001` – (instant / no timer); `1490010` Briars of Sin (lasts 0.1 s)
- **Bullet** (`Bullet.<id>.…`): `10490000` Briars of Sin; `10490001` Briars of Sin; `10490002` Briars of Sin
- **Hit** (`AtkParam_Pc.<id>.…`): `49000` Briars of Sin — magic 200; `49001` Briars of Sin — magic 232; `49002` Briars of Sin — magic 233

### 4910 · Briars of Punishment
*9 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1491000` – (instant / no timer); `1491001` – (instant / no timer); `1491010` Briars of Punishment (lasts 0.1 s)
- **Bullet** (`Bullet.<id>.…`): `10491000` Briars of Punishment; `10491001` Briars of Punishment; `10491002` Briars of Punishment; `10491003` Briars of Punishment; `10491004` Briars of Punishment; `10491005` Briars of Punishment; `10491006` Briars of Punishment
- **Hit** (`AtkParam_Pc.<id>.…`): `49100` Briars of Punishment — magic 212

### 5000 · Rancorcall
*12 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10500000` Rancorcall; `10500001` Rancorcall; `10500002` Rancorcall; `10500005` Rancorcall; `10500050` Rancorcall [Charged]; `10500051` Rancorcall; `10500052` Rancorcall; `10500055` Rancorcall; `10500099` Rancorcall
- **Hit** (`AtkParam_Pc.<id>.…`): `50000` Rancorcall — magic 54; `50005` Rancorcall — magic 57

### 5001 · Ancient Death Rancor
*21 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10500099` Rancorcall; `10500100` Ancient Death Rancor; `10500101` Ancient Death Rancor; `10500102` Ancient Death Rancor; `10500105` Ancient Death Rancor; `10500150` Ancient Death Rancor [Charged]; `10500151` Ancient Death Rancor; `10500152` Ancient Death Rancor; `10500155` Ancient Death Rancor
- **Hit** (`AtkParam_Pc.<id>.…`): `50011` Ancient Death Rancor — magic 49; `50016` Ancient Death Rancor [Charged] — magic 52

### 5010 · Explosive Ghostflame
*29 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1501000` Explosive Ghostflame (lasts 30 s); `1501001` Explosive Ghostflame (lasts 30 s)
- **Bullet** (`Bullet.<id>.…`): `10501000` Explosive Ghostflame; `10501001` Explosive Ghostflame; `10501002` Explosive Ghostflame; `10501003` Explosive Ghostflame; `10501004` Explosive Ghostflame; `10501005` Explosive Ghostflame; `10501006` Explosive Ghostflame; `10501007` Explosive Ghostflame; `10501008` Explosive Ghostflame; `10501009` Explosive Ghostflame; `10501010` Explosive Ghostflame; `10501020` Explosive Ghostflame
- **Hit** (`AtkParam_Pc.<id>.…`): `50100` Explosive Ghostflame — magic 312; `50101` Explosive Ghostflame — magic 60

### 5020 · Fia's Mist
*25 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `70` Blight Effect (endless); `1502000` Fia's Mist (instant / no timer)
- **Bullet** (`Bullet.<id>.…`): `10502000` Fia's Mist; `10502001` Fia's Mist; `10502050` Fia's Mist [Charged]; `10502051` Fia's Mist
- **Hit** (`AtkParam_Pc.<id>.…`): `50200` Fia's Mist — no damage; `50205` Fia's Mist[Charged] — no damage

### 5030 · Tibia's Summons
*17 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10503000` Tibia's Summons; `10503001` Tibia's Summons; `10503002` Tibia's Summons; `10503003` Tibia's Summons; `10503004` Tibia's Summons; `10503010` Tibia's Summons; `10503011` Tibia's Summons
- **Hit** (`AtkParam_Pc.<id>.…`): `50300` Tibia's Summons — magic 125

### 5100 · Oracle Bubbles
*12 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10510000` Oracle Bubbles; `10510001` Oracle Bubbles; `10510002` Oracle Bubbles; `10510050` Oracle Bubbles [Charged]; `10510051` Oracle Bubbles; `10510052` Oracle Bubbles; `10510099` Oracle Bubbles
- **Hit** (`AtkParam_Pc.<id>.…`): `51000` Oracle Bubbles — magic 54; `51005` Oracle Bubbles — magic 65

### 5110 · Great Oracular Bubble
*16 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `10511000` Great Oracular Bubble; `10511001` Great Oracular Bubble; `10511050` Great Oracular Bubble [Charged]; `10511051` Great Oracular Bubble
- **Hit** (`AtkParam_Pc.<id>.…`): `51010` Great Oracular Bubble — magic 298; `51015` Great Oracular Bubble — magic 355

### 6500 · Night Maiden's Mist
*20 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `1650000` Night Maiden's Mist (lasts 1.7 s)
- **Bullet** (`Bullet.<id>.…`): `10650000` Night Maiden's Mist; `10650001` Night Maiden's Mist; `10650002` Night Maiden's Mist; `10650050` Night Maiden's Mist [Charged]; `10650051` Night Maiden's Mist; `10650052` Night Maiden's Mist
- **Hit** (`AtkParam_Pc.<id>.…`): `65001` Night Maiden's Mist — phys 20; `65006` Night Maiden's Mist — phys 20

### 2004300 · Miriam's Vanishing
*9 FP · 1 memory slot · workshops: Buff tuner*

- **SpEffect** (`SpEffect.<id>.…`): `19975` Miriam's Vanishing (lasts 2 s); `21430000` Miriam's Vanishing: Enemy Sight Reduction (lasts 1 s)

### 2004310 · Glintblade Trio
*19 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210431000` Glintblade Trio; `210431001` Glintblade Trio; `210431002` Glintblade Trio; `210431003` Glintblade Trio; `210431004` Glintblade Trio; `210431005` Glintblade Trio; `210431006` Glintblade Trio; `210431050` Glintblade Trio; `210431051` Glintblade Trio; `210431052` Glintblade Trio; `210431053` Glintblade Trio; `210431054` Glintblade Trio; `210431055` Glintblade Trio; `210431056` Glintblade Trio
- **Hit** (`AtkParam_Pc.<id>.…`): `210431000` Glintblade Trio — magic 109; `210431050` Glintblade Trio — magic 127

### 2004320 · Rellana's Twin Moons
*47 FP · 2 memory slots · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210432000` Rellana's Twin Moons; `210432001` Rellana's Twin Moons; `210432002` Rellana's Twin Moons; `210432003` Rellana's Twin Moons; `210432004` Rellana's Twin Moons; `210432005` Rellana's Twin Moons; `210432006` Rellana's Twin Moons
- **Hit** (`AtkParam_Pc.<id>.…`): `210432000` Rellana's Twin Moons — magic 300; `210432002` Rellana's Twin Moons — magic 400

### 2004500 · Glintstone Nail
*10 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **Bullet** (`Bullet.<id>.…`): `210450000` Glintstone Nail; `210450001` Glintstone Nail; `210450002` Glintstone Nail; `210450003` Glintstone Nail; `210450004` Glintstone Nail; `210450005` Glintstone Nail; `210450006` Glintstone Nail; `210450007` Glintstone Nail; `210450008` Glintstone Nail; `210450009` Glintstone Nail; `210450010` Glintstone Nail; `210450050` Glintstone Nail; `210450051` Glintstone Nail; `210450052` Glintstone Nail; `210450053` Glintstone Nail; `210450054` Glintstone Nail; `210450055` Glintstone Nail; `210450056` Glintstone Nail; `210450057` Glintstone Nail; `210450058` Glintstone Nail; `210450059` Glintstone Nail; `210450060` Glintstone Nail
- **Hit** (`AtkParam_Pc.<id>.…`): `210450000` Glintstone Nail — magic 216; `210450050` Glintstone Nail — magic 269

### 2004510 · Glintstone Nails
*23 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **Bullet** (`Bullet.<id>.…`): `210451000` Glintstone Nails; `210451001` Glintstone Nails; `210451002` Glintstone Nails; `210451003` Glintstone Nails; `210451004` Glintstone Nails; `210451005` Glintstone Nails; `210451006` Glintstone Nails; `210451007` Glintstone Nails; `210451008` Glintstone Nails; `210451009` Glintstone Nails; `210451010` Glintstone Nails; `210451050` Glintstone Nails; `210451051` Glintstone Nails; `210451052` Glintstone Nails; `210451053` Glintstone Nails; `210451054` Glintstone Nails; `210451055` Glintstone Nails; `210451056` Glintstone Nails; `210451057` Glintstone Nails; `210451058` Glintstone Nails; `210451059` Glintstone Nails; `210451060` Glintstone Nails
- **Hit** (`AtkParam_Pc.<id>.…`): `210451000` Glintstone Nails — magic 66; `210451050` Glintstone Nails — magic 75

### 2004700 · Blades of Stone
*18 FP · 2 memory slots · workshops: none (too big for one shelf: Photocopier only)*

- **Bullet** (`Bullet.<id>.…`): `210470000` Blades of Stone; `210470001` Blades of Stone; `210470002` Blades of Stone; `210470003` Blades of Stone; `210470004` Blades of Stone; `210470005` Blades of Stone; `210470006` Blades of Stone; `210470007` Blades of Stone; `210470008` Blades of Stone; `210470050` Blades of Stone; `210470051` Blades of Stone; `210470052` Blades of Stone; `210470053` Blades of Stone; `210470054` Blades of Stone; `210470055` Blades of Stone; `210470056` Blades of Stone; `210470057` Blades of Stone; `210470058` Blades of Stone; `210470060` Blades of Stone; `210470061` Blades of Stone; `210470062` Blades of Stone; `210470063` Blades of Stone; `210470064` Blades of Stone; `210470065` Blades of Stone; `210470066` Blades of Stone; `210470067` Blades of Stone; `210470068` Blades of Stone; `210470070` Blades of Stone; `210470071` Blades of Stone; `210470072` Blades of Stone; `210470073` Blades of Stone; `210470074` Blades of Stone; `210470075` Blades of Stone; `210470076` Blades of Stone; `210470077` Blades of Stone; `210470078` Blades of Stone
- **Hit** (`AtkParam_Pc.<id>.…`): `210470000` Blades of Stone — phys 261; `210470050` Blades of Stone — phys 302; `210470051` Blades of Stone Bullet — phys 185

### 2004710 · Gravitational Missile
*18 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **Bullet** (`Bullet.<id>.…`): `210471000` Gravitational Missile; `210471001` Gravitational Missile; `210471002` Gravitational Missile; `210471003` Gravitational Missile; `210471004` Gravitational Missile; `210471005` Gravitational Missile; `210471006` Gravitational Missile; `210471007` Gravitational Missile; `210471050` Gravitational Missile; `210471051` Gravitational Missile; `210471052` Gravitational Missile; `210471053` Gravitational Missile; `210471054` Gravitational Missile; `210471055` Gravitational Missile; `210471056` Gravitational Missile; `210471057` Gravitational Missile; `210471058` Gravitational Missile; `210471059` Gravitational Missile; `210471060` Gravitational Missile
- **Hit** (`AtkParam_Pc.<id>.…`): `210471001` Gravitational Missile — magic 30; `210471002` Gravitational Missile — magic 279; `210471051` Gravitational Missile — magic 40; `210471052` Gravitational Missile — magic 338

### 2004900 · Mantle of Thorns
*9 FP · 1 memory slot · workshops: Buff tuner*

- **SpEffect** (`SpEffect.<id>.…`): `21490000` Mantle of Thorns: Damage on Roll (lasts 30 s); `21490001` Mantle of Thorns: VFX (lasts 30 s); `21490002` Mantle of Thorns: HP Loss (instant / no timer); `21490003` Mantle of Thorns: Apply Hemorrhage (instant / no timer)

### 2004910 · Impenetrable Thorns
*15 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `21491000` Impenetrable Thorns: HP Loss (instant / no timer); `21491001` Impenetrable Thorns: Apply Hemorrhage (instant / no timer); `21491010` Impenetrable Thorns: Apply Hemorrhage (lasts 0.1 s)
- **Bullet** (`Bullet.<id>.…`): `210491000` Impenetrable Thorns; `210491001` Impenetrable Thorns; `210491002` Impenetrable Thorns; `210491003` Impenetrable Thorns; `210491004` Impenetrable Thorns; `210491005` Impenetrable Thorns; `210491006` Impenetrable Thorns; `210491007` Impenetrable Thorns; `210491008` Impenetrable Thorns
- **Hit** (`AtkParam_Pc.<id>.…`): `210491000` Impenetrable Thorns — magic 63

### 2005000 · Rings of Spectral Light
*14 FP · 1 memory slot · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `21500000` Rings of Spectral Light: Apply Frostbite (lasts 10 s); `21500001` Rings of Spectral Light: Apply Frostbite (lasts 10 s)
- **Bullet** (`Bullet.<id>.…`): `210500000` Rings of Spectral Light; `210500001` Rings of Spectral Light; `210500002` Rings of Spectral Light; `210500003` Rings of Spectral Light; `210500004` Rings of Spectral Light; `210500005` Rings of Spectral Light; `210500050` Rings of Spectral Light; `210500051` Rings of Spectral Light; `210500052` Rings of Spectral Light; `210500053` Rings of Spectral Light; `210500054` Rings of Spectral Light; `210500055` Rings of Spectral Light
- **Hit** (`AtkParam_Pc.<id>.…`): `210500000` Rings of Spectral Light — magic 53; `210500050` Rings of Spectral Light — magic 63

### 2006200 · Vortex of Putrescence
*29 FP · 2 memory slots · workshops: Fireball*

- **SpEffect** (`SpEffect.<id>.…`): `21620000` Vortex of Putrescence: Apply Frostbite (lasts 10 s)
- **Bullet** (`Bullet.<id>.…`): `210620000` Vortex of Putrescence; `210620001` Vortex of Putrescence; `210620002` Vortex of Putrescence; `210620003` Vortex of Putrescence; `210620004` Vortex of Putrescence; `210620005` Vortex of Putrescence; `210620006` Vortex of Putrescence; `210620007` Vortex of Putrescence; `210620010` Vortex of Putrescence; `210620011` Vortex of Putrescence; `210620012` Vortex of Putrescence; `210620013` Vortex of Putrescence
- **Hit** (`AtkParam_Pc.<id>.…`): `210620000` Vortex of Putrescence — magic 328

### 2006210 · Mass of Putrescence
*41 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **SpEffect** (`SpEffect.<id>.…`): `21621000` Mass of Putrescence: Apply Frostbite (lasts 10 s); `21621001` Mass of Putrescence: Apply Frostbite (lasts 10 s); `21621002` Mass of Putrescence: Apply Frostbite (lasts 10 s); `21621003` Mass of Putrescence: Apply Frostbite (lasts 10 s)
- **Bullet** (`Bullet.<id>.…`): `210621000` Mass of Putrescence; `210621001` Mass of Putrescence; `210621002` Mass of Putrescence; `210621005` Mass of Putrescence; `210621006` Mass of Putrescence; `210621007` Mass of Putrescence; `210621050` Mass of Putrescence; `210621051` Mass of Putrescence; `210621052` Mass of Putrescence; `210621053` Mass of Putrescence; `210621054` Mass of Putrescence; `210621055` Mass of Putrescence; `210621056` Mass of Putrescence; `210621057` Mass of Putrescence; `210621058` Mass of Putrescence; `210621059` Mass of Putrescence; `210621060` Mass of Putrescence
- **Hit** (`AtkParam_Pc.<id>.…`): `210621000` Mass of Putrescence — magic 80; `210621001` Mass of Putrescence — magic 200; `210621050` Mass of Putrescence — magic 100; `210621051` Mass of Putrescence — magic 300

### 2007410 · Fleeting Microcosm
*26 FP · 1 memory slot · workshops: Fireball*

- **Bullet** (`Bullet.<id>.…`): `210741000` Fleeting Microcosm; `210741001` Fleeting Microcosm; `210741002` Fleeting Microcosm; `210741003` Fleeting Microcosm; `210741004` Fleeting Microcosm; `210741005` Fleeting Microcosm; `210741006` Fleeting Microcosm; `210741050` Fleeting Microcosm; `210741051` Fleeting Microcosm; `210741052` Fleeting Microcosm; `210741053` Fleeting Microcosm; `210741054` Fleeting Microcosm; `210741055` Fleeting Microcosm; `210741056` Fleeting Microcosm
- **Hit** (`AtkParam_Pc.<id>.…`): `210741000` Fleeting Microcosm — magic 120; `210741001` Fleeting Microcosm — magic 214; `210741050` Fleeting Microcosm — magic 160; `210741051` Fleeting Microcosm — magic 271

### 2007420 · Cherishing Fingers
*20 FP · 1 memory slot · workshops: none (too big for one shelf: Photocopier only)*

- **Bullet** (`Bullet.<id>.…`): `210742000` Cherishing Fingers; `210742001` Cherishing Fingers; `210742002` Cherishing Fingers; `210742003` Cherishing Fingers; `210742004` Cherishing Fingers; `210742005` Cherishing Fingers; `210742006` Cherishing Fingers; `210742007` Cherishing Fingers; `210742008` Cherishing Fingers; `210742050` Cherishing Fingers; `210742051` Cherishing Fingers; `210742052` Cherishing Fingers; `210742053` Cherishing Fingers; `210742054` Cherishing Fingers; `210742055` Cherishing Fingers; `210742056` Cherishing Fingers; `210742057` Cherishing Fingers; `210742058` Cherishing Fingers
- **Hit** (`AtkParam_Pc.<id>.…`): `210742000` Cherishing Fingers — phys 253; `210742050` Cherishing Fingers — phys 347

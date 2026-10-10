# Spells Innovation Handbook
### Remix the spells Elden Ring already has into new ones — a hands-on guide for players, with a cheat-sheet inside

> **For:** anyone who wants to design a spell and play it. You do **not** need to be a programmer.
> **Version:** Elden-Disk 1.7.0 · Elden Ring 1.17.1 · offline play only · 2026-10-11
> **How sure are we?** Every claim carries a mark. **✓** = tried in the real game and it worked · **◦** = the tool accepts it and builds the right data, but nobody has cast it yet · **✗** = not possible.
> **📌 Cheat-sheet boxes** (like this one) give the short version. The last chapter, *Quick Reference Card*, puts everything on one page.
> **Looking for how the file is built inside?** That is the [Item Customization Handbook](innovate-items-handbook.md). **All commands?** See [cli-commands](../guilde/cli-commands.md).

---

## Chapter 1 — The idea: innovation, not creation

### 1.1 What this is (and what it is not)

Elden-Disk does **not** let you invent a spell from nothing. It lets you **innovate**: take something the game already has, and use it as an ingredient.

Think of the game as a **huge kitchen with a full pantry**. Everything the game can do — heal, burn, throw a fireball, enchant a sword, play a cast animation, show a flame on the body — is an ingredient already on the shelf. You cannot grow a new vegetable. But you can:

- **cook a new dish** from the ingredients you find (a home-made healing spell),
- **copy a famous recipe and change one thing** (the same Black Flame, but it burns twice as long, costs 5 FP, and needs no stats),
- **mix the dials** of a recipe (how strong, how long, how often, how much it costs).

The result is a **brand-new spell item**: it has its own place in your inventory, its own price at the merchant, its own cost and requirements — and it does not change the original spell at all. The game's own spells are never touched; yours are added next to them.

> 📌 **One sentence:** *Innovation = take what the game already has, then remix it with your own numbers into a new item.*

### 1.2 You are free… inside a frame

You really do have a lot of freedom. And there is a frame around it. Knowing both saves you hours.

| 🟢 You are free to… | 🔒 The frame (what is fixed) |
|:--|:--|
| Choose **how much** a spell heals or restores, **how fast**, and **for how long** | You cannot make a **new kind of effect** the game does not have. You choose among the game's effects and set their numbers. |
| Pick **any player spell** as a starting point and copy it | The copy plays the **same animation** as the spell you copied. The tool cannot create new animations. (A home-made spell can pick between **two** cast animations.) |
| Change **FP cost, stamina cost, stat requirements**, and the **price** | A copy cannot change between **incantation and sorcery**. It stays what it was. |
| Make a fireball burn longer, fly farther, hit harder (by editing its numbers) | You cannot change a **game spell**. You only add **new** spells next to them. |
| Make a weapon enchant last for minutes instead of seconds | Only **7** of your spells can be **sold** at the merchant today (the merchant has 7 free lines). |
| Build up to about **20** spells in one file | A **size limit** protects the game file. Heavier spells (fireballs) use more of it. |
| Decide the **balance**. The tool will not stop you from making a spell that heals 9,999 HP | **Names, descriptions and pictures** of your items cannot be changed yet. (The game shows `?GoodsName?` and the original's icon.) |
| Play with it freely on your own machine | **Offline only.** This is for single-player play. |

> 📌 **The frame in three words:** same animations, only spells, limited size.

### 1.3 Why a frame at all?

The game keeps its data in tables (think: spreadsheets with thousands of rows). We **add new rows** to those tables, and every new row has to fit the shape the game expects. The game reads these tables in a very strict way, so we only add what we know the game will accept, and we check the finished file before the game ever sees it (Chapter 9). That is also why the tool is strict about typos: it would rather stop and tell you than hand the game something broken.

### 1.4 Five ways to innovate (five workshops)

Every spell you make belongs to one of five **workshops**. In the file this is the `kind` of the spell.

| Workshop | `kind` | Everyday picture | You start from… | You can change… | Proven |
|:--|:--|:--|:--|:--|:-:|
| 🍳 **Home kitchen** | `buff` (no `from`) | Cooking your own dish | an empty plate (a ready-made heal-over-time) | HP/FP/stamina per beat, beat speed, duration, glow, cost, stats, cast animation (2 choices) | ✓ |
| 🖨️ **Photocopier** | `clone` | A photocopy with a few pen marks | any player spell | cost, stat requirements, memory slots, other small settings of the spell itself | ✓ |
| ⚔️ **Enchant tuner** | `enchant` | Re-tuning a weapon blessing | a weapon or shield enchant | everything a clone can + the numbers of the blessing (how long, how strong) | ✓ weapon · ◦ shield |
| 🔥 **Fireball workshop** | `projectile` | Re-tuning a thrown spell | a spell that throws something | + the fireball's flight, size, burn, and hit damage | ✓ |
| 👊 **Strike workshop** | `attack` | Re-tuning a direct hit | a spell that hits directly, no projectile | + the hit's damage and size | ✓ |
| 🧪 **Buff tuner** | `buff` **with** `from` | Re-tuning a self-buff | a spell that only buffs you | + the buff's numbers | ◦ |

Which one to use? Look at the spell you want to start from:

- It **only buffs you** (a glow, a boost) → *Buff tuner*.
- It **blesses your weapon** → *Enchant tuner*.
- It **throws something** (a fireball, a stone) → *Fireball workshop*.
- It **hits right in front of you** → *Strike workshop*.
- You only want to change **cost, stats, size in the memory list** → *Photocopier* (works with any spell).
- You want something **of your own** that none of those cover → *Home kitchen*.

If you pick the wrong workshop, the tool tells you which one fits (Chapter 10).

### 1.5 A few ideas to spark you

*(◦ unless marked — the tool accepts them; try one change at a time.)*

| Idea | Workshop | Knob |
|:--|:--|:--|
| A heal that comes as a **big burst** instead of a slow trickle | Home kitchen | `heal_hp_per_tick` up, `duration_seconds` down |
| An **FP fountain** that gives mana back | Home kitchen | `restore_fp_per_tick` up, `heal_hp_per_tick` 0 |
| A famous spell that **costs almost nothing** and needs no stats | Photocopier ✓ | `fp_cost`, `requires` |
| A spell that takes **1 memory slot** instead of 3 | Photocopier ✓ | `Magic.<id>.slotLength` |
| A weapon blessing that lasts **10 minutes** | Enchant tuner ✓ | `effectEndurance` of the blessing |
| A flame that **burns for 30 seconds** | Fireball workshop ✓ | `effectEndurance` of the burn |
| A direct hit that hits **ten times harder** | Strike workshop ✓ | `atkMag` of each hit |
| A fireball that **flies farther or faster** | Fireball workshop | Bullet `dist`, `initVellocity` |
| A fireball that **homes in** better | Fireball workshop | Bullet `homingAngle` |
| A self-buff that lasts **much longer** | Buff tuner | `effectEndurance` of the buff |

---

## Chapter 2 — Words you will meet

You only need these.

| Word | Plain meaning |
|:--|:--|
| **`regulation.bin`** | The game's **recipe book**: one file holding the numbers for every item, spell, enemy, shop. Elden-Disk reads it, builds a new copy with your spells added, and puts it in place while you play. Your original is kept safe and restored afterwards. |
| **Row / table (param)** | A table is a spreadsheet; a row is one line (one spell, one effect…). A spell is not one row: it is a **chain** of a few rows that point at each other (the item, the spell, its effect…). |
| **Slot** | A numbered **shelf**. Your spells live on shelves 1, 2, 3… The shelf number decides the game ids your spell uses. |
| **`extension.json`** | The **order form** where you write your spells. |
| **JSON** | The way the order form is written. Section below. |
| **`from`** | "Start from this game spell." It is the spell's id number. |
| **`set`** | "On my copy, change this one number." |
| **Tick** | A **heartbeat** of an effect. A heal "every 0.5 seconds" is a tick every half second. |
| **Gate** | A **security check** on the finished file: if it is too big or wrong, the file is not used and the game does not start. |
| **Dry run** | A **rehearsal**: build and check, but write nothing. |
| **Secure** | "This build worked in the game; keep it as the known-good one." |
| **FP / HP / stamina** | Mana / health / the green bar. |

### JSON in one minute

An order form in JSON is just **labels and values** in curly braces:

```json
{
  "fp_cost": 90,
  "type": "incantation",
  "requires": { "intelligence": 45, "faith": 15 }
}
```

Five rules are enough:

1. **Labels are in quotes**, followed by a colon: `"fp_cost": 90`.
2. **Words are in quotes**, numbers are not: `"incantation"` but `90`.
3. **A comma between items**, **no comma after the last one**. (The most common mistake.)
4. Curly braces `{ }` hold a group of items. Every `{` needs its `}`.
5. `null` means "nothing here" — an **empty shelf**.

Edit it with a plain text editor that colours JSON (Notepad++, VS Code). **Not** Word. If you break a rule the tool points at the exact problem and builds nothing, so you cannot hurt your game by a typo.

---

## Chapter 3 — Your first spell in ten minutes

You will start from the spell that is already there: **Reverse Cursed Technique**, a regenerating incantation that gives back HP, FP and stamina over 15 seconds. We will make it last twice as long.

**Step 1. Open `extension.json`** (the one next to `eldendisk.exe`; if there is none the exe uses the copy built into it).

**Step 2. Find the spell.** Search for `reverse_curse_technique`. It sits on shelf 1. Find the line:

```json
"duration_seconds": 15,
```

**Step 3. Change one number.** Make it `30`. Save.

**Step 4. Rehearse.** In a terminal. (With the exe type `eldendisk.exe`; from the source code type `python -m eldendisk`. The examples below write just `eldendisk`.)

```commandline
eldendisk extension innovate-items spells --add all --dry-run
```

It builds in memory (about 20 seconds) and prints whether the **gate passed**. Nothing is written.

**Step 5. Play.**

```commandline
eldendisk run
```

The tool builds, checks, puts the new file in place and starts the game.

**Step 6. In the game.** Visit the merchant **Kalé**, buy the spell, memorize it (you need the stats it lists, 45 Intelligence, 15 Faith, 10 Arcane in its shipped design), and cast it. The glow lasts twice as long.

**Step 7 (when it works).** Close the game and run:

```commandline
eldendisk extension innovate-items spells --secure
```

This saves your build as the known-good one.

**Your second spell — a photocopy.** Find the next empty shelf. In a fresh file it looks like this:

```json
"<id-2>": null,
```

Replace that whole line (keep it in the **same position**) with:

```json
"cheap_black_flame": {
  "kind": "clone",
  "from": 6210,
  "fp_cost": 5,
  "requires": { "intelligence": 0, "faith": 0 },
  "shop": { "price": 1000, "stock": -1 }
},
```

Rehearse, run, buy at Kalé. You now own a **copy of Black Flame** that costs 5 FP and needs no Intelligence or Faith. The original Black Flame is untouched.

> 📌 **Remember:** (1) change **one thing at a time**, (2) always **rehearse** first, (3) **keep every shelf where it is** and put new spells in empty shelves, (4) if it has no `shop`, you cannot buy it.

---

## Chapter 4 — The file and its shelves

```json
{
  "innovate_items": {
    "spells": {
      "maximum": 20,
      "slots": {
        "reverse_curse_technique": { ...your spell... },
        "<id-2>": null,
        "<id-3>": null
      }
    }
  }
}
```

(The `...your spell...` is a placeholder for this page only.)

| Rule | Detail |
|:--|:--|
| `maximum` | How many shelves. A whole number from **1 to 64**. The shipped file has **20**. |
| `slots` | **Exactly** `maximum` entries, in order. Too few or too many is an error. |
| **Shelf number** | The **position** of the entry: first = shelf 1, second = shelf 2… It decides which game ids the spell gets. |
| Filled shelf | The label is the **spell id** you choose: 1–40 characters of `a-z`, `0-9`, `_`, `-`. The value is the spell. |
| Empty shelf | `null`. The label can be anything unique; `<id-N>` is the convention. |
| Two entries with the same label | Refused. |
| A field the tool does not know | Refused (so typos are caught, never silently ignored). |

**Never reorder or delete shelves.** If you move a spell to another shelf it gets different game ids; an item you bought from the old shelf would then not be the same item. Put new spells on empty shelves and leave the others where they are.

**Addresses (for the curious).** Shelf *n* uses these rows:

| Table | Id for shelf *n* | Rows reserved |
|:--|:--|:--|
| Item (Goods) and Spell (Magic) | `2230000 + n − 1` | 1 each |
| Effects (SpEffect) | `21951000 + (n − 1) × 8` | up to 8 |
| Projectiles (Bullet) | `500000000 + (n − 1) × 16` | up to 16 |
| Direct attacks (AtkParam_Pc) | `710000000 + (n − 1) × 8` | up to 8 |

---

## Chapter 5 — 🍳 The home kitchen: your own spell

This is the workshop for a spell that is truly yours. It is a **regenerating incantation**: when cast, a glow starts that gives HP, FP and stamina back, beat by beat, for a while.

### 5.1 The dials

| Dial | What it does | Range | If you leave it out |
|:--|:--|:--|:--|
| `type` | Always `"incantation"` | — | **required** |
| `requires` | Stats needed: `intelligence`, `faith`, `arcane` | 0–99 each | **required** (missing stats are 0) |
| `fp_cost` | FP to cast | 0–999 | **required** |
| `stamina_cost` | Stamina to cast | 0–999 | 0 |
| `cast_motion` | The animation: `"flame-grant-me-strength"` or `"black-flame-blade"` | those two | the first |
| `effect.heal_hp_per_tick` | HP gained each heartbeat | 0–9999 | 60 |
| `effect.restore_fp_per_tick` | FP gained each heartbeat | 0–999 | 4 |
| `effect.stamina_regen_speed` | How much faster stamina recovers while it lasts | 0–9999 | 100 |
| `effect.tick_seconds` | Seconds between heartbeats | 0.1–60 | 0.5 |
| `effect.duration_seconds` | How long the effect lasts | 0.5–600 | 15 |
| `effect.visual` | What you see on the body: `"flame"` (burning body), `"flask"` (a healing glow), `"none"` or `null` (nothing) | — | `"flame"` |
| `poise_while_casting_seconds` | Super-armor while casting (you can't be staggered) | 0.1–10 | none |
| `shop` | `price` 1–99,999,999 and `stock` (−1 = unlimited, or 1–99) | — | not for sale |
| `name`, `description` | Kept in the file only (Chapter 8) | 80 / 400 characters | empty |

### 5.2 How to think about the numbers

The three effect numbers are **per heartbeat**. The total you get is:

> **total = amount per tick × (duration ÷ tick length)**

With the defaults: 60 HP × (15 ÷ 0.5) = 60 × 30 = **1,800 HP**, and 4 FP × 30 = **120 FP**, over 15 seconds.

Because everything is a rate, a long duration with a big amount is very strong. **The game does not cap it. You are the balance designer.**

| I want… | Turn this dial |
|:--|:--|
| a bigger heal | `heal_hp_per_tick` up |
| the heal to be quick and sharp | `duration_seconds` down, `heal_hp_per_tick` up |
| the heal to be slow and steady | `duration_seconds` up, `heal_hp_per_tick` down |
| mana back | `restore_fp_per_tick` up |
| it harder to cast | `fp_cost` up, `requires` up |
| a different look | `visual`, `cast_motion` |
| to not be interrupted while casting | `poise_while_casting_seconds` |

### 5.3 Worked design: Reverse Cursed Technique ✓

*The idea.* A technique that turns negative energy into positive: a short, strong regeneration of HP, FP and stamina, cast with the Black Flame Blade motion, for a high price and high stats, sold **once**.

```json
"reverse_curse_technique": {
  "type": "incantation",
  "name": "Reverse Cursed Technique",
  "description": "Converts negative cursed energy into positive energy.",
  "requires": { "intelligence": 45, "faith": 15, "arcane": 10 },
  "fp_cost": 90,
  "cast_motion": "black-flame-blade",
  "effect": {
    "heal_hp_per_tick": 60,
    "restore_fp_per_tick": 15,
    "stamina_regen_speed": 100,
    "tick_seconds": 0.5,
    "duration_seconds": 15,
    "visual": null
  },
  "poise_while_casting_seconds": 2.0,
  "shop": { "price": 34590, "stock": 1 }
}
```

Reading it line by line:

| Line | What it means |
|:--|:--|
| the label `reverse_curse_technique` | The spell's id. It is the **first** entry, so it lives on shelf 1. |
| `type: incantation` | A spell cast with a sacred seal. |
| `name`, `description` | Your words. They are saved in the file, but the game cannot show them yet (Chapter 8). |
| `requires` 45 / 15 / 10 | To memorize it you need 45 Intelligence, 15 Faith and 10 Arcane. |
| `fp_cost: 90` | Each cast costs 90 FP. |
| `cast_motion: black-flame-blade` | The character plays the Black Flame Blade animation. |
| `heal_hp_per_tick: 60` + `tick_seconds: 0.5` + `duration_seconds: 15` | 60 HP twice a second for 15 seconds → about **1,800 HP**. |
| `restore_fp_per_tick: 15` | 15 FP each beat → about **450 FP** back. You paid 90, so you gain about **360**. |
| `stamina_regen_speed: 100` | Faster stamina recovery during the effect. |
| `visual: null` | No flame on the body afterwards. |
| `poise_while_casting_seconds: 2.0` | For 2 seconds of the cast you are hard to stagger. |
| `shop` 34,590 / 1 | Kalé sells it once for 34,590 runes. |

**Make it your own** (try one change at a time):

- *Emergency heal:* `heal_hp_per_tick: 300`, `restore_fp_per_tick: 0`, `duration_seconds: 3`, `fp_cost: 60`.
- *FP fountain:* `heal_hp_per_tick: 0`, `restore_fp_per_tick: 40`, `duration_seconds: 10`.
- *Plain cast:* remove `poise_while_casting_seconds`; set `visual` to `"none"`.
- *Flask glow:* `visual: "flask"`.

### 5.4 Limits of the home kitchen

It makes **incantations that give HP, FP and stamina**, and nothing else. It cannot throw a fireball or hit anything, and it cannot be a sorcery. For those, remix a game spell (Chapter 6).

---

## Chapter 6 — Remixing a game spell

### 6.1 The two words that matter: `from` and `set`

Think of a **photocopier with a pen**:

- **`from`** = the page you put on the glass. The tool makes a copy of that spell.
- **`set`** = the pen. "On the copy, change **this** number to **that**."

Everything you do not touch stays exactly like the original: the animation, the icon, the flame, the sound, the damage. The original is never changed. Only the **copy** is.

```json
"my_spell": {
  "kind": "enchant",
  "from": 6250,
  "fp_cost": 5,
  "shop": { "price": 1000, "stock": -1 },
  "set": { "SpEffect.1626000.effectEndurance": 600 }
}
```

### 6.2 Finding `from`

`from` is the **Magic id** of a spell a player can cast (not a boss spell). Some you may know: `6210` Black Flame, `6250` Black Flame Blade, `6050` Flame, Grant Me Strength, `4000` Glintstone Pebble. **Appendix A lists every id that works** for each workshop.

How many spells each workshop accepts today:

| Workshop | Incantations | Sorceries |
|:--|:-:|:-:|
| Photocopier (`clone`) | 129 | 84 |
| Buff tuner (`buff` + `from`) | 9 | 3 |
| Enchant tuner (`enchant`) | 7 | 4 |
| Fireball workshop (`projectile`) | 103 | 59 |
| Strike workshop (`attack`) | 2 | 3 |

(23 more thrown spells are too big for one shelf and are refused by the fireball workshop; a photocopy of most of them works.)

### 6.3 The common fields

| Field | Range | If you leave it out |
|:--|:--|:--|
| `kind` | `clone` / `enchant` / `projectile` / `attack` / `buff` | **required** |
| `from` | a Magic id | **required** |
| `fp_cost`, `stamina_cost` | 0–999 | the original's |
| `requires` | `intelligence`, `faith`, `arcane`, 0–99. Only the stats you list change. | the original's |
| `type` | only as a check: a copy cannot change between incantation and sorcery | the original's |
| `shop` | `price`, `stock` | not for sale |
| `set` | see 6.5 | nothing changed |
| `name`, `description` | stored only | empty |

The smallest valid copy is `{"kind": "clone", "from": 6210}`. It is an exact copy with no shop line, so you cannot buy it, which is why you almost always add a `shop`.

### 6.4 What each workshop copies

Think of a spell as a **chain of rows**. A workshop decides how long a piece of the chain it copies. What it copies, you can edit with `set`. What it does not copy still points to the **game's own** rows — and the game's rows are never changed, so you cannot `set` them.

| Workshop | Copies | `set` can touch |
|:--|:--|:--|
| Photocopier | the item and the spell | `Magic`, `Goods` |
| Enchant tuner | + the blessing's effect rows | + `SpEffect` |
| Buff tuner | + the buff's effect rows | + `SpEffect` |
| Fireball workshop | + effects, projectiles and hit rows | + `Bullet`, `AtkParam_Pc` |
| Strike workshop | + effects and hit rows | + `AtkParam_Pc` |

Which spells fit which workshop (the tool checks this for you):

- **Enchant tuner:** a spell that enchants a weapon or shield. *Weapon ✓, shield ◦.*
- **Buff tuner:** a spell that only applies an effect to you (and is not an enchant).
- **Fireball workshop:** a spell that throws or creates a projectile.
- **Strike workshop:** a spell that hits directly and throws nothing. (Black Flame throws a fireball, so it is a fireball spell.)

A shelf has room for **8 effect rows, 16 projectile rows, 8 hit rows**. A spell that needs more is refused.

### 6.5 `set` — the pen

```json
"set": {
  "Magic.6210.slotLength": 1,
  "SpEffect.1621000.effectEndurance": 30,
  "AtkParam_Pc.44400.atkMag": 1800
}
```

A key has **three parts** joined by dots: `Table . row id . field`. The value is the new number.

| Table | The row id to write | Which workshops |
|:--|:--|:--|
| `Magic` (the spell) | the spell's own `from` | all |
| `Goods` (the item) | the spell's own `from` | all |
| `SpEffect` (effects: burns, buffs, durations) | the **game's** id of an effect the spell uses | Enchant tuner, Buff tuner, Fireball, Strike |
| `Bullet` (projectiles) | the game's id of a projectile the spell makes | Fireball |
| `AtkParam_Pc` (hits and their damage) | the game's id of a hit the spell makes | Fireball, Strike |

**Write the game's ids, not yours.** `SpEffect.1621000` means "the burn of Black Flame"; the tool applies your change to the **copy** on your shelf. The original `1621000` stays as it was.

**Rules for the value:** a whole number for whole-number fields; a decimal is fine for decimal fields; a number that does not fit the field is an error (the tool never "rounds it to fit").

**Not allowed in `set`** (the tool tells you why):

| What | Why |
|:--|:--|
| Link fields (anything that points to another row: `refId…`, `replaceMagicId`, `spEffectId0…4`, `HitBulletID`, `goodsType` …) | The tool links the copies to each other. A changed link would send your copy back to the game's rows. |
| `mp`, `stamina`, `requirementIntellect`, `requirementFaith`, `requirementLuck` | They have friendly names: use `fp_cost`, `stamina_cost` and `requires`. |
| A row that is not one of the copied rows | The error lists the rows you may use. |
| `SpEffect`, `Bullet` or `AtkParam_Pc` in a photocopy | A photocopy does not copy those. Choose a richer workshop. |

### 6.6 Recipe cards — proven in the real game ✓

*(These are illustrations. Put any of them on an empty shelf and give it a price.)*

**Recipe 1 — A cheaper, lighter Black Flame** *(Photocopier)*

```json
"cheap_black_flame": {
  "kind": "clone",
  "from": 6210,
  "fp_cost": 5,
  "requires": { "intelligence": 0, "faith": 0 },
  "shop": { "price": 2000, "stock": 2 },
  "set": { "Magic.6210.slotLength": 1 }
}
```

Costs **5 FP**, needs **no Intelligence or Faith** (Arcane stays the original's because it is not listed), and takes **1 memory slot**. Same fireball, same burn: a photocopy shares the original's chain.

**Recipe 2 — A ten-minute weapon blessing** *(Enchant tuner)*

```json
"long_blade_blessing": {
  "kind": "enchant",
  "from": 6250,
  "fp_cost": 5,
  "shop": { "price": 3000, "stock": 3 },
  "set": { "SpEffect.1626000.effectEndurance": 600 }
}
```

`1626000` is the effect that carries the blessing's duration. 600 seconds = ten minutes.

**Recipe 3 — A flame that burns for 30 seconds** *(Fireball workshop)*

```json
"long_burn_flame": {
  "kind": "projectile",
  "from": 6210,
  "fp_cost": 5,
  "shop": { "price": 4000, "stock": 4 },
  "set": { "SpEffect.1621000.effectEndurance": 30 }
}
```

The fireball flies and hits like the original; the **burn** it leaves lasts 30 seconds.

**Recipe 4 — A strike that hits ten times harder** *(Strike workshop)*

```json
"mighty_strike": {
  "kind": "attack",
  "from": 4440,
  "fp_cost": 4,
  "shop": { "price": 5000, "stock": 5 },
  "set": {
    "AtkParam_Pc.44400.atkMag": 1800,
    "AtkParam_Pc.44401.atkMag": 1800,
    "AtkParam_Pc.44405.atkMag": 1800,
    "AtkParam_Pc.44406.atkMag": 1800,
    "AtkParam_Pc.44407.atkMag": 1840,
    "AtkParam_Pc.44408.atkMag": 1840
  }
}
```

This spell makes its damage with **six hit rows**. To make it stronger you change `atkMag` (magic damage) on **each** row; change only some and only those hits change. The original keeps its damage (180 in this case); the copy reads 1800.

### 6.7 What else could you change? ◦

The tool accepts about **220 settings** on a spell and its item, **360** on effects, **110** on projectiles and **200** on hits. These are the ones people are likely to want. *None of these were tried in the game: change one at a time, cast, look.*

| Table | Fields | Use |
|:--|:--|:--|
| Spell (Magic) | `slotLength`, `iconId`, `sortId`, `toughnessCorrectRate`, `castSfxId`, `fireSfxId`, `effectSfxId`, `enable_multi`, `enable_live`, `enable_gray`, `enable_white`, `enable_black`, `disableOffline`, `isUseNoAttackRegion`, `enableRiding`, `disableRiding`, `mp_charge`, `stamina_charge` | memory slots, where it works, charge costs, effects shown |
| Item (Goods) | `iconId`, `sortId`, `weight`, `basicPrice`, `sellValue`, `maxNum`, `maxRepositoryNum`, `rarity`, `isDrop`, `isOnlyOne`, `consumeMP`, `consumeHP`, `useLevel`, `shopLv` | inventory behavior (stack size, sell value, icon) |
| Effect (SpEffect) | `effectEndurance`, `motionInterval`, `changeHpPoint`, `changeHpRate`, `changeMpPoint`, `changeMpRate`, `changeStaminaPoint`, `staminaRecoverChangeSpeed`, `mpRecoverChangeSpeed`, `maxHpRate`, `maxMpRate`, `maxStaminaRate`, `physicsAttackRate`, `magicAttackRate`, `fireAttackRate`, `thunderAttackRate`, the `…DamageCutRate` family, the `…DiffenceRate` family, `poizonAttackPower`, `bloodAttackPower`, `curseAttackPower`, `toughnessDamageCutRate`, `soulRate`, `equipWeightChangeRate`, `vfxId` | duration, heartbeat, heal/damage, strength multipliers, defences, status buildup |
| Projectile (Bullet) | `life`, `dist`, `initVellocity`, `maxVellocity`, `accelInRange`, `hitRadius`, `hitRadiusMax`, `numShoot`, `shootAngle`, `shootAngleInterval`, `homingAngle`, `shootInterval`, `gravityInRange`, `damageDamp`, `spelDamageDamp`, `fireDamageDamp`, `isPenetrateChr`, `isPenetrateObj`, `isEndlessHit` | how long and far it flies, speed, size, how many, spread, homing, passing through enemies |
| Hit (AtkParam_Pc) | `atkPhys`, `atkMag`, `atkFire`, `atkThun`, `atkStam`, `hit0_Radius` … `hit12_Radius`, `blowingCorrection`, `dmgLevel`, `atkAttribute`, `atkType`, `atkSuperArmor`, `hitStopTime` | damage per element, hit size, stagger |

⚠ **Signs differ between fields.** In the home kitchen's own buff a heal is stored as a *negative* number. Before changing a number, **read what the original has** and move from there.

**How to read a value or a field name:**

```commandline
eldendisk read --param SpEffect.1621000                      # every field of that row (game running)
eldendisk read --param SpEffect.1621000.effectEndurance      # one field
eldendisk read --param-check                                 # after a build: every original row equal, new rows counted
```

`read --param` looks into the **running game**.

---

## Chapter 7 — Selling it: the shop and the shelves

You need to **buy** a spell to own it, so a spell needs a `shop` entry (a price and a stock).

- Only shelves **1 to 7** have a merchant line, at **Kalé**. A spell on shelf 8 or higher **is built but cannot be bought yet**; writing a `shop` for it is an error. This is a known limit, put aside on purpose; the format, the checks and the ids already support the shelves above.
- `price`: 1 to 99,999,999 runes. `stock`: `-1` = unlimited, or 1–99 for that many copies. `0` is refused.
- Tip: use a price that tells you where an item came from (for example 1001 for shelf 1, 1002 for shelf 2…). It is only a habit; the tool does not require it.

> 📌 **Seven shelves can sell. Put the spells you want to play on shelves 1–7.**

---

## Chapter 8 — What the tool cannot do (yet)

Being honest about the frame saves you disappointment.

| You might wish for… | Answer |
|:--|:--|
| A **name** and **description** that show up in the game | ✗ Not yet. The game shows `?GoodsName?`. What you write in `name` / `description` is **saved in your file** for when that is built. |
| A **new picture / icon** | ✗ Not yet. The copy keeps the original's icon. |
| A **new animation** | ✗ The tool cannot make animations. A home-made spell can pick one of two; a copy keeps the original's. |
| A copy that is a **sorcery instead of an incantation** (or the reverse) | ✗ It keeps its type. |
| A home-made spell that **deals damage** or **throws something** | ✗ Home-made spells only heal. For damage, remix a game spell. |
| A home-made **sorcery** | ✗ Home-made spells are incantations. |
| To **change a game spell** | ✗ Never. Your spells are always new. |
| New **weapons, armor, talismans** | ✗ Spells only for now. |
| More than 7 spells **for sale** | ✗ Not yet (shelves 8+). |
| More than about 20 spells in one file | ✗ The size check (Chapter 9). |
| Online play | ✗ Offline only. |

---

## Chapter 9 — How many spells can I make? (the suitcase)

Imagine the game file as a **suitcase with a weight limit**. Each spell you add puts something in. The **gate** weighs the suitcase *before* the game ever sees it; if it is over, nothing is used and the game does not start. A warning counts as a stop.

| Kind of spell | Weight | Why |
|:--|:--|:--|
| Photocopier | 🪶 very light | it adds only a few rows |
| Home kitchen / Enchant tuner / Buff tuner | 🎒 light | a few rows of effects |
| Strike workshop | 🧳 heavy | it adds hit rows |
| Fireball workshop | 🧳🧳 heaviest | it adds projectile rows and hit rows |

What fits (measured offline, and checked in the game for the last row):

| Design | Fits? |
|:--|:--|
| Photocopies only | ✓ even all 64 shelves |
| Home-made / enchant only | ✓ up to 32, ✗ at 64 |
| **Any mix up to 20 shelves without fireballs** | ✓ |
| 2 fireball + 2 strike + 16 home-made, 20 shelves | ✓ **tested in the game** |
| 16 or more fireball (or strike) spells of the same kind | ✗ |
| 64 shelves mixed | ✗ |

**Rules of thumb:** plan for **about 20 mixed spells**, with **a few** fireballs and strikes, not a dozen. The weight depends on **how many things you add**, not on the numbers you choose: changing 15 to 30 never makes it heavier. The weight does not grow smoothly (one more spell can jump it), so **always rehearse** with `--add all --dry-run`.

*For developers:* the gate allows 27 changed 4-KiB blocks, 292,000 bytes of compressed-frame growth and 219,000 bytes of body growth (limits raised only after a bigger file passed in the game; the tested file had 27 blocks and 291,040 bytes). The developer tool `tools/capacity.py --source <original regulation.bin> --mix buff=16,projectile=2,attack=2` prints the numbers of any mix offline.

---

## Chapter 10 — Running it, and what the messages mean

### 10.1 The loop

```commandline
eldendisk extension innovate-items spells --add all --dry-run    # 1. rehearse (about 20 s, writes nothing)
eldendisk run                                                    # 2. build, check, play
eldendisk extension innovate-items spells --secure               # 3. after it worked, game closed: keep this build
```

- `--add <id>` builds just one spell instead of `all`.
- `run` uses the **secured** build while your design equals the secured one. If you changed something it says what changed (`reverse_curse_technique.shop.price  34590 -> 40000`) and rebuilds.
- The files live in `<vault>\extension\innovate-items\spells\`: `regulation.bin` (latest build), `regulation.secured.bin`, `spells.commit.json`.
- With `--vault-off` the spells are not used.
- After a build, `read --param-check` (game running) compares every original row with the game: they must all be equal, and your new rows are counted.

### 10.2 Messages and what to do

The tool lists **every** problem it finds at once.

| What it says (shortened) | What it means | Do this |
|:--|:--|:--|
| `has N slots but maximum is M` | The number of shelves does not match `maximum`. | Keep every shelf; use `null` for empty ones. |
| `a filled slot's key is the spell's id …` | Bad characters or too long. | Use `a-z`, `0-9`, `_`, `-`, up to 40. |
| `` `from` N is not a Magic row of this game `` | There is no such spell. | Pick from Appendix A. |
| `… has no Goods row (the spells of NPCs and bosses have none)` | It is not a player spell. | Pick a player spell. |
| `a copy cannot change type` | You wrote incantation/sorcery the other way. | Remove `type`, or use the original's. |
| `… is not a weapon or shield enchant (use kind …)` | Wrong workshop. | Use the kind it names. |
| `… not only SpEffect rows: kind buff needs a spell that only applies an effect` | The spell also throws or hits. | Use the Fireball or Strike workshop (it names the kind). |
| `… is an enchant: use kind enchant` | A buff tuner on an enchant. | Use `enchant`. |
| `… calls AtkParam_Pc and no Bullet row: kind projectile needs …` | It hits directly, nothing is thrown. | Use `attack`. |
| `… kind attack needs a spell that makes a direct attack … and throws nothing` | It throws something. | Use `projectile`. |
| `the chain of X has N … rows of its own; a slot has room for …` | The spell is too big for one shelf. | Pick another spell, or use a photocopy. |
| `a clone shares the template's … rows … does not copy them` | You used `set` on effects/projectiles/hits in a photocopy. | Use a richer workshop. |
| `… is an id or type that links rows …` | You tried to change a link. | Not possible; the tool links the copies. |
| `… already has a friendly field (…)` | You used `set` on `mp`, `requirementFaith`, … | Use `fp_cost`, `requires.…`. |
| `slot N has no shop line` | A `shop` on shelf 8 or higher. | Remove `shop`, or use shelves 1–7. |
| `GATE FAILED … nothing was swapped` | The suitcase is too heavy. | Fewer or lighter spells (Chapter 9). |

---

## Chapter 11 — Quick Reference Card (the cheat-sheet)

### 11.1 Before you play

- [ ] Every shelf is where it was; `maximum` equals the number of shelves.
- [ ] New spells are on **empty** shelves; spells you want to **buy** are on shelves **1–7**.
- [ ] Every spell has either `kind` + `from` (a remix) or `type` + `requires` + `fp_cost` (home-made).
- [ ] `from` is in Appendix A for that workshop and type.
- [ ] `set` uses **the game's ids**, no link fields.
- [ ] `shop`: price ≥ 1; stock −1 or 1–99.
- [ ] `--add all --dry-run` says the gate passed.
- [ ] **One new idea** since the last build that worked.

### 11.2 Home-made spell (all fields; the values shown are the defaults)

```json
"my_spell_id": {
  "type": "incantation",
  "requires": { "intelligence": 0, "faith": 0, "arcane": 0 },
  "fp_cost": 0,
  "stamina_cost": 0,
  "cast_motion": "flame-grant-me-strength",
  "effect": {
    "heal_hp_per_tick": 60,
    "restore_fp_per_tick": 4,
    "stamina_regen_speed": 100,
    "tick_seconds": 0.5,
    "duration_seconds": 15,
    "visual": "flame"
  },
  "poise_while_casting_seconds": 2.0,
  "shop": { "price": 1000, "stock": -1 },
  "name": "My Spell",
  "description": "What it does."
}
```

Required: `type`, `requires`, `fp_cost`. Everything else can be left out.

### 11.3 Remixed spell (all fields)

```json
"my_remix_id": {
  "kind": "clone",
  "from": 6210,
  "fp_cost": 5,
  "stamina_cost": 0,
  "requires": { "intelligence": 0, "faith": 0 },
  "shop": { "price": 1000, "stock": -1 },
  "set": { "Magic.6210.slotLength": 1 },
  "name": "My Remix",
  "description": "What it does."
}
```

Required: `kind`, `from`. `kind` is `clone`, `enchant`, `projectile`, `attack` or `buff`. Delete the lines you do not need.

### 11.4 All the limits on one page

| Thing | Limit |
|:--|:--|
| Shelves (`maximum`) | 1–64 (about 20 mixed fit the game) |
| Shelves with a shop line | 1–7 |
| Spell id | 1–40 characters of `a-z 0-9 _ -` |
| `requires.*` | 0–99 |
| `fp_cost`, `stamina_cost` | 0–999 |
| `shop.price` | 1–99,999,999 |
| `shop.stock` | −1 or 1–99 |
| `name` / `description` | 80 / 400 characters (saved only) |
| `heal_hp_per_tick` | 0–9999 |
| `restore_fp_per_tick` | 0–999 |
| `stamina_regen_speed` | 0–9999 |
| `tick_seconds` | 0.1–60 |
| `duration_seconds` | 0.5–600 |
| `poise_while_casting_seconds` | 0.1–10 |
| Effect rows per shelf | 8 · projectile rows 16 · hit rows 8 |
| Cast animations (home-made) | `flame-grant-me-strength`, `black-flame-blade` |
| Glow (`visual`) | `flame`, `flask`, `none` (or `null`) |

### 11.5 Is it proven?

| Workshop | State |
|:--|:--|
| Home kitchen | ✓ cast in the game |
| Photocopier (incantation) | ✓ |
| Photocopier (sorcery) | ◦ |
| Enchant tuner (weapon) | ✓ |
| Enchant tuner (shield) | ◦ |
| Buff tuner | ◦ |
| Fireball workshop | ✓ |
| Strike workshop | ✓ |
| Names, descriptions, icons | ✗ not yet |
| Items other than spells | ✗ not yet |
| Shelves 8 and up for sale | ✗ not yet |

---

## Appendix A — Which `from` ids work

Each list holds the spells the tool accepts for that workshop, checked against the 1.17.1 game file. Ids from 2,000,000 up come from the DLC.

**Photocopier (`clone`) · incantation (129):** 5040, 6000, 6001, 6010, 6020, 6030, 6040, 6050, 6060, 6100, 6110, 6120, 6210, 6220, 6230, 6240, 6250, 6260, 6270, 6300, 6310, 6320, 6330, 6340, 6400, 6410, 6420, 6421, 6422, 6423, 6424, 6430, 6431, 6440, 6441, 6450, 6460, 6470, 6480, 6490, 6510, 6520, 6530, 6600, 6700, 6701, 6710, 6720, 6730, 6740, 6750, 6760, 6770, 6780, 6800, 6810, 6820, 6830, 6840, 6850, 6900, 6910, 6920, 6921, 6930, 6940, 6941, 6950, 6960, 6970, 6971, 7000, 7001, 7010, 7011, 7020, 7021, 7030, 7031, 7040, 7041, 7050, 7060, 7080, 7090, 7200, 7210, 7220, 7230, 7240, 7300, 7310, 7311, 7320, 7330, 7500, 7510, 7520, 7530, 7900, 7903, 2006300, 2006400, 2006650, 2006660, 2006670, 2006680, 2006690, 2006700, 2006710, 2006800, 2006900, 2006910, 2006920, 2007000, 2007010, 2007020, 2007200, 2007210, 2007300, 2007600, 2007700, 2007710, 2007720, 2007730, 2007740, 2007800, 2007810, 2007820

**Photocopier (`clone`) · sorcery (84):** 4000, 4001, 4010, 4020, 4021, 4030, 4040, 4050, 4060, 4070, 4080, 4090, 4100, 4110, 4120, 4130, 4140, 4200, 4210, 4220, 4300, 4301, 4302, 4360, 4361, 4370, 4380, 4381, 4390, 4400, 4410, 4420, 4430, 4431, 4440, 4450, 4460, 4470, 4480, 4490, 4500, 4510, 4520, 4600, 4610, 4620, 4630, 4640, 4650, 4660, 4670, 4700, 4701, 4710, 4720, 4721, 4800, 4810, 4820, 4830, 4900, 4910, 5000, 5001, 5010, 5020, 5030, 5100, 5110, 6500, 2004300, 2004310, 2004320, 2004500, 2004510, 2004700, 2004710, 2004900, 2004910, 2005000, 2006200, 2006210, 2007410, 2007420

**Buff tuner (`buff` + `from`) · incantation (9):** 6050, 6060, 6260, 6450, 6460, 6470, 6480, 6840, 6971

**Buff tuner (`buff` + `from`) · sorcery (3):** 4140, 2004300, 2004900

**Enchant tuner (`enchant`) · incantation (7):** 6250, 6320, 6740, 6770, 6960, 6970, 7230

**Enchant tuner (`enchant`) · sorcery (4):** 4460, 4470, 4490, 4660

**Fireball workshop (`projectile`) · incantation (103):** 5040, 6000, 6001, 6010, 6020, 6030, 6040, 6100, 6110, 6120, 6210, 6220, 6230, 6240, 6270, 6300, 6310, 6330, 6340, 6400, 6410, 6420, 6421, 6422, 6423, 6424, 6430, 6431, 6440, 6490, 6510, 6520, 6530, 6600, 6700, 6701, 6710, 6720, 6750, 6760, 6780, 6800, 6810, 6830, 6850, 6900, 6920, 6921, 6930, 6940, 6950, 7000, 7001, 7010, 7011, 7020, 7021, 7030, 7031, 7040, 7041, 7050, 7060, 7090, 7200, 7210, 7220, 7240, 7300, 7310, 7311, 7320, 7330, 7500, 7520, 7530, 7900, 7903, 2006400, 2006650, 2006660, 2006670, 2006680, 2006690, 2006700, 2006710, 2006800, 2006910, 2006920, 2007000, 2007010, 2007020, 2007200, 2007210, 2007300, 2007600, 2007700, 2007710, 2007720, 2007730, 2007740, 2007800, 2007820

**Fireball workshop (`projectile`) · sorcery (59):** 4000, 4001, 4010, 4020, 4021, 4030, 4060, 4070, 4080, 4090, 4100, 4110, 4120, 4130, 4200, 4300, 4301, 4302, 4360, 4361, 4380, 4381, 4390, 4400, 4410, 4420, 4431, 4480, 4500, 4510, 4520, 4600, 4610, 4620, 4630, 4640, 4650, 4670, 4720, 4721, 4800, 4810, 4830, 4900, 4910, 5000, 5001, 5010, 5020, 5030, 5100, 5110, 6500, 2004310, 2004320, 2004910, 2005000, 2006200, 2007410

**Strike workshop (`attack`) · incantation (2):** 7080, 7510

**Strike workshop (`attack`) · sorcery (3):** 4430, 4440, 4450

**Too big for one shelf, refused by the Fireball workshop (23, incantations and sorceries together):** 4040, 4050, 4210, 4220, 4370, 4700, 4701, 4710, 4820, 6441, 6730, 6820, 6910, 6941, 2004500, 2004510, 2004700, 2004710, 2006210, 2006300, 2006900, 2007420, 2007810


## Appendix B — For developers: where each fact comes from

| Topic | Source |
|:--|:--|
| Field ranges, `set` rules, messages | `code/eldendisk/extension/innovate_items/spells/spec.py`, `recipes.py` |
| Rows per shelf, ids | `recipes.py`, `build.py`, `chain.py` |
| Gate numbers | `code/eldendisk/extension/innovate_items/preflight.py` |
| Field names per table | `paramdefs.py` (generated from Paramdex) |
| Tests in the game | [manual-test-plan-1.7.0](../experiments/extensional/innovate-items/spell/docs/manual-test-plan-1.7.0.md) |
| Roadmap, what is deferred | [roadmap-innovate-spells](../experiments/extensional/innovate-items/spell/docs/roadmap-innovate-spells.md) |
| The full spec | [elden-disk-spec-v1.7.0](../specs/elden-disk-spec-v1.7.0.md) |
| The story of how the first spell was built | [Item Customization Handbook](innovate-items-handbook.md) |

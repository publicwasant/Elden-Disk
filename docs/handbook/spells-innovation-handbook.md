# Spells Innovation Handbook
### Remix the spells Elden Ring already has into new ones — a hands-on guide for players, with a cheat-sheet inside

> **For:** anyone who wants to design a spell and play it. You do **not** need to be a programmer.
> **Version:** Elden-Disk 1.7.1 · Elden Ring 1.17.1 · offline play only · 2026-10-11
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
| Decide the **balance**. The tool will not stop you from making a spell that heals 9,999 HP | **Pictures (icons)** of your items cannot be changed yet. (The game shows the original's icon; the name and description are yours since 1.7.1, 6.1b.) |
| Play with it freely on your own machine | **Offline only.** This is for single-player play. |

> 📌 **The frame in three words:** same animations, only spells, limited size.

### 1.3 Why a frame at all?

The game keeps its data in tables (think: spreadsheets with thousands of rows). We **add new rows** to those tables, and every new row has to fit the shape the game expects. The game reads these tables in a very strict way, so we only add what we know the game will accept, and we check the finished file before the game ever sees it (Chapter 10). That is also why the tool is strict about typos: it would rather stop and tell you than hand the game something broken.

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

If you pick the wrong workshop, the tool tells you which one fits (Chapter 11).

### 1.5 A few ideas to spark you

*(◦ unless marked — the tool accepts them; try one change at a time.)*

| Idea | Workshop | Knob |
|:--|:--|:--|
| A heal that comes as a **big burst** instead of a slow trickle | Home kitchen | `heal_hp_per_tick` up, `duration_seconds` down |
| An **FP fountain** that gives mana back | Home kitchen | `restore_fp_per_tick` up, `heal_hp_per_tick` 0 |
| A famous spell that **costs almost nothing** and needs no stats | Photocopier ✓ | `fp_cost`, `requires` |
| A big spell that takes **1 memory slot** instead of 3 (for example Comet Azur, `4200`) | Photocopier ◦ | `Magic.4200.slotLength` |
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
| **`creative.json`** | The **order form** where you write your spells. |
| **JSON** | The way the order form is written. Section below. |
| **Row / id** | Every line of a game table has a number, its **id**: its address. `6210` is the address of Black Flame. Chapter 3 is the map of these numbers. |
| **`from`** | "Start from this game spell." It is the spell's id number (its Magic id). |
| **Spell Finder / Row Finder** | Lookup tables in this handbook: *name → id* (Appendix A) and *id → the rows it uses* ([spells-row-finder.md](spells-row-finder.md)). |
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

## Chapter 3 — The number map: where do all these numbers come from?

Open the file and you meet numbers like `6210`, `1621000`, `44400`. Nothing in the game's menus shows them, so it is fair to ask: *what are they, where do they come from, and how do I know which one to write?* This chapter answers that. Keep it open while you design.

### 3.1 Every number is an address

Behind the game there is a handful of giant **tables** (think of phone books with thousands of lines). Every line is a **row**, and every row has an **id**: its phone number. In `creative.json`, whenever you point at "that spell" or "that burn" or "that hit", you write its id.

| Table (the name written in the file) | One row is… | What the id looks like | Example | Where you write it |
|:--|:--|:--|:--|:--|
| **Magic** | the **spell**: FP cost, stat requirements, memory slots, cast animation, and *which other rows it calls* | 4–7 digits | `6210` = Black Flame | `"from": 6210` · `Magic.6210.…` |
| **Goods** | the **item** in your inventory and the shop for that spell. It has the **same id as its Magic row** | same as Magic | `6210` | `Goods.6210.…` |
| **SpEffect** | an **effect**: a burn, a buff, a heal-over-time, a weapon blessing, with its duration | 4–7 digits | `1621000` = Black Flame's burn | `SpEffect.1621000.…` |
| **Bullet** | a **projectile**: a fireball or stone in flight | 8 digits | `10621000` | `Bullet.10621000.…` |
| **AtkParam_Pc** | a **hit**: one blow, with its damage | 4–6 digits | `62101` | `AtkParam_Pc.62101.…` |

The ids are the game's own and never change between your builds. The names next to them in this handbook come from the community's **Paramdex** name lists; they are good but not perfect, so a blank or odd name is possible. The **numbers** in the Finders below were read straight from the game file (1.17.1).

> 📌 **`from` is always a Magic id. Everything else in `set` is the id of a row the spell reaches.**

### 3.2 A spell is a chain of rows

A spell is not one row. The **Magic** row says "when cast, call these rows", and those rows call more rows. Here are three real spells, drawn as the chain the tool follows.

**Black Flame** (`6210`) throws a fireball that burns:

```
Magic 6210  Black Flame                       18 FP · 1 memory slot
 ├─ Bullet 10621000  Black Flame              the fireball
 │   ├─ Bullet 10621001  Black Flame          (part of the fireball)
 │   │   ├─ AtkParam_Pc 62101  Black Flame    the hit:  fire 244
 │   │   └─ SpEffect 1621000  (DoT Black)     the BURN: lasts 2 s
 │   └─ AtkParam_Pc 79980                     used by other spells too: shared, never copied
 └─ Bullet 10621050  Black Flame [Charged]    the charged fireball
     ├─ Bullet 10621051  Black Flame
     │   ├─ AtkParam_Pc 62106  [Charged]      the hit:  fire 300
     │   └─ SpEffect 1621000  (DoT Black)     the same burn
     └─ AtkParam_Pc 79990                     shared, never copied
```

**Carian Slicer** (`4440`) hits straight away, no projectile:

```
Magic 4440  Carian Slicer                     4 FP · 1 memory slot
 ├─ AtkParam_Pc 44400   hit: magic 180
 ├─ AtkParam_Pc 44401   hit: magic 180
 ├─ AtkParam_Pc 44405   hit: magic 180
 ├─ AtkParam_Pc 44406   hit: magic 180
 ├─ AtkParam_Pc 44407   hit: magic 184
 ├─ AtkParam_Pc 44408   hit: magic 184
 └─ (every hit also calls SpEffect 6901 "Accumulator Increase +4": the tool copies it; you never need to touch it)
```

**Black Flame Blade** (`6250`) blesses your weapon:

```
Magic 6250  Black Flame Blade                 15 FP · 1 memory slot
 └─ SpEffect 1626000  the blessing            lasts 7 s
     └─ SpEffect 1626001  (DoT Black)         the burn it applies: lasts 2 s
```

How a workshop uses the chain: a **Photocopier** copies only the first line (Magic + Goods). An **Enchant tuner** also copies the SpEffect lines. A **Fireball workshop** copies everything it reaches, except rows that many other spells use (they stay shared). Whatever is **copied** you can change with `set`; whatever is **shared** still belongs to the game and cannot be touched.

### 3.3 How to read a key like `SpEffect.1621000.effectEndurance`

```
   SpEffect . 1621000 . effectEndurance : 30
   ────┬───   ───┬───   ───────┬───────   ─┬
       │         │             │           └─ the NEW value (here: seconds)
       │         │             └─ the FIELD: a column of that table. Here "how long the effect lasts"
       │         └─ the ROW id: which line of the table. Here Black Flame's burn
       └─ the TABLE: which phone book. Here the effects
```

So the line means: *"On my copy, make Black Flame's burn last 30 seconds."* Every key in every `set` reads the same way.

### 3.4 Finding the number you need (four steps)

1. **Which spell?** Look up its name in the **Spell Finder** (Appendix A). The number in the first column is its **id**. That is your `from`, and also the number in `Magic.<id>.…` / `Goods.<id>.…`. The table also tells you its FP cost, its memory slots and **which workshops accept it**.
2. **Which part do I want to change?** Look the id up in the **Row Finder** ([spells-row-finder.md](spells-row-finder.md), one entry per spell). It lists every effect, projectile and hit row of that spell, with their ids, names, durations and base damage. Those are the rows you may write in `set`.
3. **Which field?** Use the dictionary in section 7.8 (what `effectEndurance`, `atkMag`, `dist` … mean).
4. **Check the original value first** (section 7.9) so you know what you are changing from.

Which row do I need? Use this:

| I want to change… | Table | Field | Which row |
|:--|:--|:--|:--|
| how long a **burn, buff or blessing** lasts | SpEffect | `effectEndurance` | the effect row in the Row Finder (a burn is the row named "(DoT …)"; a blessing or buff carries the spell's own name) |
| **damage** | AtkParam_Pc | `atkPhys` / `atkMag` / `atkFire` / `atkThun` | **every** hit row of the spell that shows damage |
| how far or fast a **projectile** flies | Bullet | `dist`, `initVellocity`, `maxVellocity` | the projectile rows |
| how many **memory slots** it takes | Magic | `slotLength` | the spell's own id |
| **FP, stamina, stat requirements** | — | `fp_cost`, `stamina_cost`, `requires` | none (friendly fields) |
| **price, stock** | — | `shop` | none |

**Worked example: where do `1800` and `1840` come from?** In the Row Finder, Carian Slicer (`4440`) has six hit rows: `44400`, `44401`, `44405`, `44406` show *magic 180*, and `44407`, `44408` show *magic 184*. To hit **ten times harder** you write ten times each value: `1800` for the first four, `1840` for the last two. The ids are the rows this spell actually reaches; `44402`–`44404` are not in its chain, so they are not on the list. (Those are the spell's *base* damage numbers; the damage you see in the game is also scaled by your build.)

### 3.5 When an id is not in the Finder

The Finders cover every spell the tool accepts, for the game version this handbook was made for. If the game is patched, or you are curious about a row, you can read it yourself (the game must be running):

```commandline
eldendisk read params.Magic.6210
```

You will see fields `refCategory1…10` and `refId1…10`: each pair says "I call the row with this id in that table". The category tells you which table: **0 = AtkParam_Pc (a hit), 1 = Bullet, 2 = SpEffect**. Then `read params.Bullet.<id>` shows what *that* row calls, and so on down the chain, exactly like the drawings above.

Community tools such as Paramdex and Smithbox show the same tables with the same ids; they are a good second opinion.

### 3.6 Numbers inside a row: the cast and the look

Some dials are not row ids at all. They are **settings stored inside a row**, and the game reuses each of them for many spells. Five of them decide how a spell *feels*: how the hands move, what flashes when you cast, and what you see on the body.

| What you want to change | Home-made spell (Chapter 6) | Remixed spell (`set`, Chapter 7) | Stored in | Look it up in |
|:--|:--|:--|:--|:--|
| the **cast animation** (how the hands move) | `"cast_motion": 32` or a name | `"Magic.<from>.refType": 32` | the spell's Magic row | **Motion Finder** |
| the **flash and sound when the cast starts** | always Flame, Grant Me Strength's | `"Magic.<from>.castSfxId": 524090` | the spell's Magic row | **Cast Finder** |
| the **flash and sound when it fires** | always Flame, Grant Me Strength's | `"Magic.<from>.fireSfxId": 524091` | the spell's Magic row | **Cast Finder** |
| an **extra effect the spell keeps showing** | none | `"Magic.<from>.effectSfxId": -1` | the spell's Magic row | **Cast Finder** |
| the **look on the body** while the effect lasts | `"visual": 1605000` or a name | `"SpEffect.<effect id>.vfxId": 1605000` | an effect (SpEffect) row | **Visual Finder** |

All three Finders are in [spells-row-finder.md](spells-row-finder.md). The easiest way to choose: **find a spell whose cast or look you like** (you know them from playing), and copy its numbers. The Cast Finder lists all four Magic numbers of every spell in one row, so *"I want the cast of Black Flame Blade"* means: find "Black Flame Blade (6250)" and take `32`, `524090`, `524091`.

> ⚠️ **In `Magic.<from>.…` the middle number is always your own `from`**, never the spell you copy from. The numbers you copy go in the *value*, after the colon. `"Magic.6050.refType": 31` on a spell made from `6430` is an error (*"the row id must be this spell's `from`"*); the right line is `"Magic.6430.refType": 31`.

The names are only shortcuts for the best-known numbers:

| Name | Number | It is |
|:--|:-:|:--|
| `flame-grant-me-strength` | `cast_motion` 31 | the cast of Flame, Grant Me Strength (also Flame Protect Me and others) |
| `black-flame-blade` | `cast_motion` 32 | the cast of Black Flame Blade |
| `flame` | `visual` 1605000 | the burning body of Flame, Grant Me Strength |
| `flask` | `visual` 5030 | the healing glow of a Flask of Crimson Tears |
| `none` (or `null`) | `visual` −1 | nothing on the body |

**Worked example — a mend with the cast of Black Flame Blade** ◦ *(Fireball workshop; builds and passes the checks, not yet tried in the game)*

```json
"reverse_curse_boon": {
  "kind": "projectile",
  "from": 6430,
  "text": {
    "goods_name": "Reverse Curse Boon",
    "goods_info": "A short, strong mend instead of a long, faint one",
    "goods_captions": "Blessing's Boon with the curse turned around: a short, strong mend instead of a long, faint one."
  },
  "fp_cost": 70,
  "requires": { "intelligence": 0, "faith": 25, "arcane": 25 },
  "shop": { "price": 30000, "stock": 1 },
  "set": {
    "SpEffect.1643000.effectEndurance": 20,
    "SpEffect.1643000.motionInterval": 0.5,
    "SpEffect.1643000.changeHpPoint": -45,
    "SpEffect.1643000.changeMpPoint": -15,
    "SpEffect.1643000.staminaRecoverChangeSpeed": 100,
    "SpEffect.1643000.vfxId": -1,
    "Magic.6430.refType": 32,
    "Magic.6430.castSfxId": 524090,
    "Magic.6430.fireSfxId": 524091
  }
}
```

| Number | What it is | Where it comes from |
|:--|:--|:--|
| `6430` | the Magic id of **Blessing's Boon**: the spell this one is made from | Spell Finder (Appendix A), row "6430 · Blessing's Boon" |
| `1643000` | the effect row of Boon: its slow HP regeneration | Row Finder, entry 6430, the `SpEffect 1643000` line (lasts 90 s) |
| `effectEndurance: 20` | how long the effect lasts, in seconds | yours; the original is 90 (the Row Finder's "lasts" figure) |
| `motionInterval: 0.5` | seconds between heartbeats | yours; the original is 1 (read it with section 7.9) |
| `changeHpPoint: -45` | HP per heartbeat. **Negative heals** | yours; the original is −8 |
| `changeMpPoint: -15` | FP per heartbeat. Negative restores | yours; the original is 0 |
| `staminaRecoverChangeSpeed: 100` | faster stamina recovery while it lasts | yours; the original is 0 |
| `vfxId: -1` | no glow on the body | −1 = none (Visual Finder); the original glows with 1643000 |
| `refType: 32`, `castSfxId: 524090`, `fireSfxId: 524091` | the cast of **Black Flame Blade** | Cast Finder, row "Black Flame Blade (6250)"; the middle number of the key is *your* `from`, 6430 |
| `price: 30000`, `stock: 1` | your merchant line | your choice |

Total healed: 45 HP × (20 s ÷ 0.5 s) = **1,800 HP**. Blessing's Boon also applies a second, smaller regeneration (the effect `475`, 30 s); it is left as it is.

> ◦ **Only five of these settings have been tried in the game:** the names in the table above. Any other number is checked (the tool refuses a motion or visual number that no spell or effect of the game uses) but not tested: it may look wrong, or show nothing. That is a fair experiment for an innovator: try it, and note what you see.

---

## Chapter 4 — Your first spell in ten minutes

You will start from the spell that is already there: **Reverse Cursed Technique**, a regenerating incantation that gives back HP, FP and stamina over 15 seconds. We will make it last twice as long.

**Step 1. Open `creative.json`** (the one next to `eldendisk.exe`; if there is none the exe uses the copy built into it).

**Step 2. Find the spell.** Search for `reverse_curse_technique`. It sits on shelf 1. Find the line:

```json
"duration_seconds": 15,
```

**Step 3. Change one number.** Make it `30`. Save.

**Step 4. Rehearse.** In a terminal. (With the exe type `eldendisk.exe`; from the source code type `python -m eldendisk`. The examples below write just `eldendisk`.)

```commandline
eldendisk innovate-spells build --dry-run
```

It builds in memory (a few seconds) and prints whether the **gate passed**. Nothing is written.

**Step 5. Play.**

```commandline
eldendisk run
```

The tool builds, checks, puts the new file in place and starts the game.

**Step 6. In the game.** Visit the merchant **Kalé**, buy the spell, memorize it (you need the stats it lists, 45 Intelligence, 15 Faith, 10 Arcane in its shipped design), and cast it. The glow lasts twice as long.

**Step 7 (when it works).** Close the game and run:

```commandline
eldendisk innovate-spells secure
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

What the numbers are: `"from": 6210` is the **id of Black Flame**, looked up by name in the Spell Finder (Appendix A); `fp_cost: 5` replaces its normal 18 FP; the `price` is yours to choose. (More about every number in Chapter 3.)

Rehearse, run, buy at Kalé. You now own a **copy of Black Flame** that costs 5 FP and needs no Intelligence or Faith. The original Black Flame is untouched.

> 📌 **Remember:** (1) change **one thing at a time**, (2) always **rehearse** first, (3) **keep every shelf where it is** and put new spells in empty shelves, (4) if it has no `shop`, you cannot buy it.

---

## Chapter 5 — The file and its shelves

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

## Chapter 6 — 🍳 The home kitchen: your own spell

This is the workshop for a spell that is truly yours. It is a **regenerating incantation**: when cast, a glow starts that gives HP, FP and stamina back, beat by beat, for a while.

### 6.1 The dials

| Dial | What it does | Range | If you leave it out |
|:--|:--|:--|:--|
| `type` | Always `"incantation"` | — | **required** |
| `requires` | Stats needed: `intelligence`, `faith`, `arcane` | 0–99 each | **required** (missing stats are 0) |
| `fp_cost` | FP to cast | 0–999 | **required** |
| `stamina_cost` | Stamina to cast | 0–999 | 0 |
| `cast_motion` | The cast animation: a **name** (`"flame-grant-me-strength"`, `"black-flame-blade"`) or the game's own **number** from the Motion Finder (section 3.6) | 2 names, or a number 0–999 that some spell of the game uses | `"flame-grant-me-strength"` |
| `effect.heal_hp_per_tick` | HP gained each heartbeat | 0–9999 | 60 |
| `effect.restore_fp_per_tick` | FP gained each heartbeat | 0–999 | 4 |
| `effect.stamina_regen_speed` | How much faster stamina recovers while it lasts | 0–9999 | 100 |
| `effect.tick_seconds` | Seconds between heartbeats | 0.1–60 | 0.5 |
| `effect.duration_seconds` | How long the effect lasts | 0.5–600 | 15 |
| `effect.visual` | What you see on the body: a **name** (`"flame"` burning body, `"flask"` healing glow, `"none"` or `null` nothing) or the game's own **number** from the Visual Finder (section 3.6) | 3 names, or −1 to 99,999,999 that some effect of the game uses | `"flame"` |
| `poise_while_casting_seconds` | Super-armor while casting (you can't be staggered) | 0.1–10 | none |
| `shop` | `price` 1–99,999,999 and `stock` (−1 = unlimited, or 1–99) | — | not for sale |
| `text` | An object: `goods_name` (the name), `goods_info` (the short line under it), `goods_captions` (the long description). Shown in the game (6.1b) | 80 / 120 / 1000 characters | empty |
| `flame_color` | `[red, green, blue]`: the colour of the fire of Flame, Grant Me Strength while casting and in the burst. One colour for the whole design (6.1c) | each 0–2 (1 = full colour, above 1 shines brighter) | the game's own orange |
| `flame_accent_color` | `[red, green, blue]`, with `flame_color`: the second colour of the fire, for what flame_color does not reach, and the ring of runes at the hand (6.1c) | each 0–2 | the game's own red |
| `positive_curse_energy_eyes` | `{}` or `{"color": [red, green, blue]}`: both of the caster's eyes glow while the effect lasts (6.1d) | each 0–2 | no glow |

### 6.1b The text of your spell (since 1.7.1)

A spell has three pieces of text, all in the object `text` (all optional; an empty one shows nothing):

| Field | Where you see it |
|:--|:--|
| `goods_name` | The name: in the merchant's list and wherever the game shows the item's name |
| `goods_info` | The short line shown with the item |
| `goods_captions` | The long description: Inventory → select the spell → the controller's square button (the item's description page). `\n` starts a new line |

```json
"text": {
  "goods_name": "Reverse Cursed Technique",
  "goods_info": "Converts negative cursed energy into positive energy",
  "goods_captions": "Converts negative cursed energy into positive energy.\nHeals over time and restores FP."
}
```

What to know:

- ✓ You do nothing extra. `eldendisk run` waits until a character is in the world, then puts the text in by itself, once (you will see `goods text: 1 spell named in the game …`; it takes about a minute and a half after the character appears, because the tool looks through the game's memory for the game's text without freezing the game). Tried in the real game 2026-10-11: the name and short line in the merchant's list, the long description in the inventory.
- It lasts until the game closes and is not saved anywhere. Every `run` does it again.
- Changing only the text **does not rebuild** anything and does not un-secure a secured build. The text is put in once per game: to see a new text, close the game and `run` again. (A second `eldendisk innovate-spells apply` in the same game is refused with `the text was set already in this session`: the tool finds the game's own tables by their shape, and the game no longer points at them.)
- Words in `text` are only for the spells that are built (the `innovate-spells build` choice, Chapter 11); a spell that is not built shows nothing.
- ◦ Only English letters were tried. Thai or other scripts might not exist in the game's font (boxes or blanks); try a short word first.
- The old fields `name` and `description` of 1.7.0 are errors now; the message tells you where they went (`name` → `text.goods_name`, `description` → `text.goods_info`).

### 6.1c The colour of your fire (since 1.7.1)

Flame, Grant Me Strength throws a fire when you cast and a burst when the cast ends. Both are effects of the game's own (they are not rows of a table), so a spell cannot have its own: you give **the whole design** a colour with `flame_color`, in any spell:

```json
"flame_color": [0.2, 0.65, 1.0]
```

Three numbers, red, green, blue, each from 0 to 2 (1 = the full colour; above 1 shines brighter). The fire of the cast and the burst turn blue here; the burning on the body keeps its colour.

- ✓ You do nothing extra. `eldendisk run` waits until a character is in the world and recolours the fire by itself, once (`flame colour: the fire of Flame, Grant Me Strength is now (…)`; about 7 seconds after the character appears). Tried in the real game 2026-10-11, three sessions.
- The fire effects are shared by every spell that uses them, so there is **one** colour for the design: the first spell (lowest slot) that names one. If two spells name different colours a warning says which was used.
- It colours **Flame, Grant Me Strength itself**, not only your spell: the game's own spell has the new colour while the game runs. It lasts until the game closes and is not saved anywhere.
- Editing `flame_color` does not rebuild anything and does not un-secure a secured build.
- White stays white and black stays black: the colour is applied the way a tint is, so the shape and brightness of the fire are kept.
- A second colour: `"flame_accent_color": [0.54, 0.4, 0.8]` next to `flame_color` colours the parts of the fire the first colour does not reach and the **ring of runes** at the hand (purple with these numbers; the author's design uses `[1.0, 1.0, 1.0]` since 2026-10-13, a deep red-purple for the negative curse energy, against the blue of the positive). Seen in the game on 2026-10-12. If the ring stays red, cast once and run `eldendisk innovate-spells apply` (the game had not loaded it yet).

### 6.1d Positive Curse Energy Eyes (since 1.7.1, seen in the game 2026-10-12)

While the buff of your spell lasts, both of your character's eyes glow, in any colour (the game's own glowing eyes of a human NPC of the DLC; the gold eyes of the enemies that give five times the runes need points on the model that the player does not have):

```json
"positive_curse_energy_eyes": { "on": "SpEffect.1642100", "color": [0.2, 0.65, 1] }
```

- `on` is the buff: for a spell made from a game spell, the SpEffect row (the template's number, as in `set`) that you have while the spell lasts. A heal-over-time buff made from scratch has only one, so it has no `on`: `"positive_curse_energy_eyes": {}`.
- `color` is optional: without it the eyes are the game's red. It is put into the running game by the same step as `flame_color`, so that NPC's eyes have the colour too while the game runs.
- Adding or removing the eyes (or changing `on`) builds again; changing only `color` does not.

### 6.2 How to think about the numbers

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
| a different look | `visual`, `cast_motion` (a name, or a number from the Visual / Motion Finder) |
| to not be interrupted while casting | `poise_while_casting_seconds` |

### 6.3 Worked design: Reverse Cursed Technique ✓

*The idea.* A technique that turns negative energy into positive: a short, strong regeneration of HP, FP and stamina, cast with the Black Flame Blade motion, for a high price and high stats, sold **once**.

```json
"reverse_curse_technique": {
  "type": "incantation",
  "text": {
    "goods_name": "Reverse Cursed Technique",
    "goods_info": "Converts negative cursed energy into positive energy",
    "goods_captions": "Converts negative cursed energy into positive energy.\nHeals over time and restores FP."
  },
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
| `text` | Your words: the name, the short line and the long description. The game shows them (6.1b). |
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

### 6.4 Limits of the home kitchen

It makes **incantations that give HP, FP and stamina**, and nothing else. It cannot throw a fireball or hit anything, and it cannot be a sorcery. For those, remix a game spell (Chapter 7).

---

## Chapter 7 — Remixing a game spell

### 7.0 The structure since 1.7.1 (section 1b): one place for each thing

Since 1.7.1 a remixed spell can be written so that each part answers one question. The older fields (7.3, 7.5, 6.1b-6.1d) still work, and the same spell written either way builds **the same file**.

```json
"reverse_cursed_technique": {
  "__info__": "Your notes: what the spell is, why the numbers are what they are.",
  "kind": "projectile",
  "from": 6421,
  "requires": {
    "status": { "intelligence": 0, "faith": 60, "arcane": 10 },
    "cost":   { "focus_point": 120 }
  },
  "locations": { "kale": { "price": 34590, "stock": 1 } },
  "customs": {
    "basic":    { "SpEffect.1642100.effectEndurance": 20, "Magic.6421.refType": 32, "Magic.6421.castSfxId": 524400,
                  "SpEffect.1642100.vfxId1": 20090050, "SpEffect.1642100.vfxId2": 20090051 },
    "advanced": {
      "texts":  { "goods_name": "Reverse Cursed Technique", "goods_info": "One short line", "goods_caption": "The long story." },
      "colors": { "Magic.6421.castSfxId": { "0x4290": [0.56, 0.84, 1.0, 0.075], "0x4334": "#90D5FF" },
                  "SpEffectVfx.20090050.midstSfxId": { "0x2a0": "#90D5FF" } }
    }
  }
}
```

| Question | Where | Same as |
|:--|:--|:--|
| What is it? | `__info__`, `kind`, `from` | (`__info__` is a note for you; the tool skips it, and you can put one in every `{ }`) |
| What does it need? | `requires.status` (to learn it), `requires.cost` (to cast it) | `requires`, `fp_cost`, `stamina_cost` |
| Where is it sold? | `locations.kale` | `shop` (Kalé only for now; shelves 1-7) |
| What numbers change? | `customs.basic` | `set` (7.5): built into regulation.bin |
| What does the game not have a row for? | `customs.advanced.texts`, `customs.advanced.colors` | `text`, `colors` (`flame_color` + `flame_accent_color` before 1.8.3): written into the running game, never a rebuild |

`colors` (1.8.3) is the colours as the game holds them. A key is the param field that points at an effect: `"Magic.<from>.castSfxId"` (the fire while casting, 524400), `"Magic.<from>.fireSfxId"` (the burst when the cast ends, 524401), `"Bullet.<id>.sfxId_Bullet"` (what a copied bullet shows, such as the sparks 4271), `"SpEffectVfx.20090050.midstSfxId"` (the glowing eyes, 4866) and `"Sfx.<effect>"` for an effect no param names (the ring of runes at the hand: `Sfx.515000`, `Sfx.515001`). Under a key, every colour place of that effect file by its offset in the file (`"0x4290"`), its value `[red, green, blue, alpha]` as the file holds it (above 1 shines brighter) or `"#RRGGBB"` (the place keeps its own brightness and alpha); a place you leave out keeps the game's colour. `read ...design.customs.advanced.colors` shows every place with what the game holds now; `write ...colors.<key>.<place>=...` changes one in the running game. The effect of a `Magic` or `Bullet` key is the one `customs.basic` puts there, and only the effects with a colour plan can be painted (524400, 524401, 4866, 4271, 515000, 515001). The eyes are put on the buff in `customs.basic` (`"SpEffect.<id>.vfxId1": 20090050, "SpEffect.<id>.vfxId2": 20090051`), as the build writes them.

**Your spell's real id.** The name you give it (`reverse_cursed_technique`) is a label. The game knows it by the ids of its shelf: after a build, `<vault>\design\innovate-items\spells\spells.resolved.json` lists every spell under its Goods id (`2230000` for shelf 1, `2230001` for shelf 2, ...) with all the rows it owns. The console shows the same under the spell (`game  goods 2230000 · magic 2230000 · ...`).

**Editing later: a checklist.**

1. Change one thing at a time, and keep the old value in `__info__` if you might want it back.
2. Numbers of the game's rows go in `customs.basic` with the key you would use in `set` (3.3, 7.5); look the row up in the Row Finder first (Appendix B) and read the original value (7.9).
3. A change in `customs.basic`, `requires` or `locations` builds regulation.bin again (a few seconds); a change in `customs.advanced` does not, it is written into the game after the world loads.
4. The message of a mistake names the exact place (`...customs.basic.Magic.6422.mp: ...`): fix that line only.
5. After `run` builds, read the block on the console: the changes (`└─ ...  34590 -> 40000`), then each spell with what the design says. When it works in the game, close it and run `innovate-spells secure`.

### 7.1 The two words that matter: `from` and `set`

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

### 7.2 Finding `from`

`from` is the **Magic id** of a spell a player can cast (not a boss spell). You do not have to guess it: **look the spell up by name in the Spell Finder (Appendix A)**. The id is in the first column, and the ✓ columns tell you which workshops accept that spell. Some you may know: `6210` Black Flame, `6250` Black Flame Blade, `6050` Flame, Grant Me Strength, `4000` Glintstone Pebble, `4440` Carian Slicer.

How many spells each workshop accepts today:

| Workshop | Incantations | Sorceries |
|:--|:-:|:-:|
| Photocopier (`clone`) | 129 | 84 |
| Buff tuner (`buff` + `from`) | 9 | 3 |
| Enchant tuner (`enchant`) | 7 | 4 |
| Fireball workshop (`projectile`) | 103 | 59 |
| Strike workshop (`attack`) | 2 | 3 |

(23 more thrown spells are too big for one shelf; they show "too big" in the Finder and are refused by the fireball workshop. A photocopy of most of them works.)

### 7.3 The common fields

| Field | Range | If you leave it out |
|:--|:--|:--|
| `kind` | `clone` / `enchant` / `projectile` / `attack` / `buff` | **required** |
| `from` | a Magic id | **required** |
| `fp_cost`, `stamina_cost` | 0–999 | the original's |
| `requires` | `intelligence`, `faith`, `arcane`, 0–99. Only the stats you list change. | the original's |
| `type` | only as a check: a copy cannot change between incantation and sorcery | the original's |
| `shop` | `price`, `stock` | not for sale |
| `set` | see 7.5 | nothing changed |
| `text` | `goods_name`, `goods_info`, `goods_captions` (6.1b) | empty |

The smallest valid copy is `{"kind": "clone", "from": 6210}`. It is an exact copy with no shop line, so you cannot buy it, which is why you almost always add a `shop`.

### 7.4 What each workshop copies

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

### 7.5 `set` — the pen

```json
"set": {
  "SpEffect.1621000.effectEndurance": 30,
  "AtkParam_Pc.62101.atkFire": 488
}
```

(An illustration for the spell `6210`, Black Flame: the first line makes its burn last 30 s, the second doubles the base fire damage of its main hit from 244 to 488. Both ids are rows of Black Flame's chain, see Chapter 3.)

A key has **three parts** joined by dots: `Table . row id . field`. The value is the new number.

| Table | The row id to write | Which workshops |
|:--|:--|:--|
| `Magic` (the spell) | the spell's own `from`, **never another spell's id** (the numbers you copy from another spell go in the *value*) | all |
| `Goods` (the item) | the spell's own `from` | all |
| `SpEffect` (effects: burns, buffs, durations) | the **game's** id of an effect the spell uses | Enchant tuner, Buff tuner, Fireball, Strike |
| `Bullet` (projectiles) | the game's id of a projectile the spell makes | Fireball |
| `AtkParam_Pc` (hits and their damage) | the game's id of a hit the spell makes | Fireball, Strike |

**Write the game's ids, not yours.** `SpEffect.1621000` means "the burn of Black Flame"; the tool applies your change to the **copy** on your shelf. The original `1621000` stays as it was. Where to find the ids: Chapter 3 and the Row Finder.

**Rules for the value:** a whole number for whole-number fields; a decimal is fine for decimal fields; a number that does not fit the field is an error (the tool never "rounds it to fit").

**Not allowed in `set`** (the tool tells you why):

| What | Why |
|:--|:--|
| Link fields (anything that points to another row: `refId…`, `replaceMagicId`, `spEffectId0…4`, `HitBulletID`, `goodsType` …) | The tool links the copies to each other. A changed link would send your copy back to the game's rows. |
| `mp`, `stamina`, `requirementIntellect`, `requirementFaith`, `requirementLuck` | They have friendly names: use `fp_cost`, `stamina_cost` and `requires`. |
| A row that is not one of the copied rows | The error lists the rows you may use. |
| `SpEffect`, `Bullet` or `AtkParam_Pc` in a photocopy | A photocopy does not copy those. Choose a richer workshop. |

### 7.6 Recipe cards — proven in the real game ✓

*(These are illustrations. Put any of them on an empty shelf and give it a price.) Under each card, a small map says where every number comes from.*

**Recipe 1 — A cheap Black Flame that needs no stats** *(Photocopier)*

```json
"cheap_black_flame": {
  "kind": "clone",
  "from": 6210,
  "fp_cost": 5,
  "requires": { "intelligence": 0, "faith": 0 },
  "shop": { "price": 2000, "stock": 2 }
}
```

| Number | What it is | Where it comes from |
|:--|:--|:--|
| `6210` | the Magic id of **Black Flame** | Spell Finder, row "6210 · Black Flame" |
| `fp_cost: 5` | your new cost | the original costs **18 FP** (the Finder's FP column) |
| `requires` 0 / 0 | no Intelligence, no Faith needed | your choice; Arcane is not listed, so it stays the original's |
| `price: 2000`, `stock: 2` | your merchant line | your choice |

Same fireball, same burn: a photocopy shares the original's chain, so only the item itself differs.

*Want it to take fewer memory slots too?* Add `"set": { "Magic.<id>.slotLength": 1 }` with the spell's own id. It only helps a spell that takes more than one slot (the Finder has a **Memory slots** column; Black Flame already takes 1). The `set` itself is proven, using it on a multi-slot spell is ◦.

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

| Number | What it is | Where it comes from |
|:--|:--|:--|
| `6250` | the Magic id of **Black Flame Blade** | Spell Finder, "6250 · Black Flame Blade" (✓ in the Enchant column) |
| `SpEffect.1626000` | the **blessing itself** | the chain in section 3.2: the spell calls `1626000`, which lasts **7 s** |
| `effectEndurance` | how long that effect lasts | field dictionary (section 7.8) |
| `600` | 10 minutes in seconds | your choice (the original is 7) |

`1626001` is the burn the blessing applies (2 s); we leave it alone.

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

| Number | What it is | Where it comes from |
|:--|:--|:--|
| `6210` | Black Flame | Spell Finder (✓ in the Fireball column) |
| `SpEffect.1621000` | **the burn** ("DoT Black" = damage over time) | the chain in section 3.2, and the Row Finder entry of 6210; it lasts **2 s** in the original |
| `30` | seconds | your choice |

The fireball flies and hits like the original; the **burn** it leaves lasts 30 seconds. Both fireballs (normal and charged) call the same burn row, so one `set` changes both.

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

| Number | What it is | Where it comes from |
|:--|:--|:--|
| `4440` | the Magic id of **Carian Slicer** (a sorcery) | Spell Finder (✓ in the Strike column) |
| `44400`, `44401`, `44405`, `44406`, `44407`, `44408` | the **six hit rows** this spell makes | the chain in section 3.2, Row Finder entry of 4440. Rows 44402–44404 exist in the game but this spell does not reach them |
| `atkMag` | the hit's **magic damage** (base value) | field dictionary (section 7.8) |
| `1800`, `1840` | **ten times** the original values | the Row Finder shows `180` for the first four hits and `184` for the last two; ×10 |

Change only some of the rows and only those hits get stronger. The original keeps its damage; the copy reads 1800.

### 7.7 What else could you change? ◦

The tool accepts about **220 settings** on a spell and its item, **360** on effects, **110** on projectiles and **200** on hits. These are the ones people are likely to want. *None of these were tried in the game: change one at a time, cast, look.*

| Table | Fields | Use |
|:--|:--|:--|
| Spell (Magic) | `slotLength`, `iconId`, `sortId`, `toughnessCorrectRate`, `castSfxId`, `fireSfxId`, `effectSfxId`, `enable_multi`, `enable_live`, `enable_gray`, `enable_white`, `enable_black`, `disableOffline`, `isUseNoAttackRegion`, `enableRiding`, `disableRiding`, `mp_charge`, `stamina_charge` | memory slots, where it works, charge costs, effects shown |
| Item (Goods) | `iconId`, `sortId`, `weight`, `basicPrice`, `sellValue`, `maxNum`, `maxRepositoryNum`, `rarity`, `isDrop`, `isOnlyOne`, `consumeMP`, `consumeHP`, `useLevel`, `shopLv` | inventory behavior (stack size, sell value, icon) |
| Effect (SpEffect) | `effectEndurance`, `motionInterval`, `changeHpPoint`, `changeHpRate`, `changeMpPoint`, `changeMpRate`, `changeStaminaPoint`, `staminaRecoverChangeSpeed`, `mpRecoverChangeSpeed`, `maxHpRate`, `maxMpRate`, `maxStaminaRate`, `physicsAttackRate`, `magicAttackRate`, `fireAttackRate`, `thunderAttackRate`, the `…DamageCutRate` family, the `…DiffenceRate` family, `poizonAttackPower`, `bloodAttackPower`, `curseAttackPower`, `toughnessDamageCutRate`, `soulRate`, `equipWeightChangeRate`, `vfxId` | duration, heartbeat, heal/damage, strength multipliers, defences, status buildup |
| Projectile (Bullet) | `life`, `dist`, `initVellocity`, `maxVellocity`, `accelInRange`, `hitRadius`, `hitRadiusMax`, `numShoot`, `shootAngle`, `shootAngleInterval`, `homingAngle`, `shootInterval`, `gravityInRange`, `damageDamp`, `spelDamageDamp`, `fireDamageDamp`, `isPenetrateChr`, `isPenetrateObj`, `isEndlessHit` | how long and far it flies, speed, size, how many, spread, homing, passing through enemies |
| Hit (AtkParam_Pc) | `atkPhys`, `atkMag`, `atkFire`, `atkThun`, `atkStam`, `hit0_Radius` … `hit12_Radius`, `blowingCorrection`, `dmgLevel`, `atkAttribute`, `atkType`, `atkSuperArmor`, `hitStopTime` | damage per element, hit size, stagger |

⚠ **Signs differ between fields.** In the home kitchen's own buff a heal is stored as a *negative* number. Before changing a number, **read what the original has** and move from there.

### 7.8 What the field names mean

Field names are the column names of the game's tables. These are the ones used in this handbook. *Meanings follow the field names and community documentation; confirm by changing one and watching.*

| Field | Table | Meaning |
|:--|:--|:--|
| `slotLength` | Magic | memory slots the spell takes |
| `refType` | Magic | the cast animation (Motion Finder, section 3.6) |
| `castSfxId`, `fireSfxId` | Magic | the flash and sound when the cast starts / when the spell fires (Cast Finder, section 3.6) |
| `effectSfxId` | Magic | an extra effect the spell keeps showing; `-1` = none (Cast Finder) |
| `iconId` | Magic, Goods | which icon (a number from the game's icon sheet) |
| `effectEndurance` | SpEffect | how long the effect lasts, in seconds (`-1` = endless, `0` = instant) |
| `motionInterval` | SpEffect | seconds between beats of a repeating effect |
| `vfxId` | SpEffect | the visual effect shown while it lasts (Visual Finder, section 3.6); `-1` = none |
| `changeHpPoint`, `changeMpPoint` | SpEffect | HP / FP changed on each beat (negative = restores, as the home kitchen uses it) |
| `staminaRecoverChangeSpeed` | SpEffect | how much faster stamina recovers |
| `atkPhys`, `atkMag`, `atkFire`, `atkThun` | AtkParam_Pc | base damage of the hit: physical, magic, fire, lightning |
| `atkStam` | AtkParam_Pc | stamina damage the hit deals |
| `life` | Bullet | how long the projectile lives, in seconds |
| `dist` | Bullet | how far it flies |
| `initVellocity`, `maxVellocity` | Bullet | starting speed, top speed |
| `hitRadius` | Bullet | size of its hit area |
| `numShoot` | Bullet | how many are shot at once |
| `homingAngle` | Bullet | how sharply it steers toward a target |
| `shootAngle` | Bullet | spread of the shots |

### 7.9 Reading the original's value first

**How to read a value or a field name:**

```commandline
eldendisk read params.SpEffect.1621000                      # every field of that row (game running)
eldendisk read params.SpEffect.1621000.effectEndurance      # one field
eldendisk check                                 # after a build: every original row equal, new rows counted
```

`read params.<Table>.<id>` looks into the **running game**.

---

## Chapter 8 — Selling it: the shop and the shelves

You need to **buy** a spell to own it, so a spell needs a `shop` entry (a price and a stock).

- Only shelves **1 to 7** have a merchant line, at **Kalé**. A spell on shelf 8 or higher **is built but cannot be bought yet**; writing a `shop` for it is an error. This is a known limit, put aside on purpose; the format, the checks and the ids already support the shelves above.
- `price`: 1 to 99,999,999 runes. `stock`: `-1` = unlimited, or 1–99 for that many copies. `0` is refused.
- Tip: use a price that tells you where an item came from (for example 1001 for shelf 1, 1002 for shelf 2…). It is only a habit; the tool does not require it.

> 📌 **Seven shelves can sell. Put the spells you want to play on shelves 1–7.**

---

## Chapter 9 — What the tool cannot do (yet)

Being honest about the frame saves you disappointment.

| You might wish for… | Answer |
|:--|:--|
| A **name** and **description** that show up in the game | ✓ Since 1.7.1: write them in `text` (6.1b). They are put into the running game each time you start it with `run`; nothing is saved in the game's files. Only English letters are tried; Thai and other scripts may show as boxes ◦. |
| A different **colour of the fire** of Flame, Grant Me Strength | ✓ Since 1.7.1: `flame_color` (6.1c). The fire of the cast and the burst, put into the running game; the burning on the body keeps its colour. |
| The **icon of another item** (reuse a picture the game already has) | ◦ Since 1.7.1, for spells made from a game spell (`clone`, `projectile`, `attack`, ...): `"set": {"Goods.<from>.iconId": 6806}` gives the copy the icon whose number you give (6806 = Gravitational Missile). The number is the item's `iconId` in the Goods table (`read params.Goods.<id>.iconId` shows it). The icon must be one the game loads: the DLC icons are in the DLC sheet and need the DLC installed. Tried in the game 2026-10-12 with 6806 on `reverse_cursed_technique`: the icon of Gravitational Missile shows (the author's check; the screens one by one are in manual plan 1.7.1, IC). |
| A **new picture** that the game does not have | ✗ Not yet (it needs the game's menu texture archive). |
| A **new animation** | ✗ The tool cannot make animations. A home-made spell can pick one of two; a copy keeps the original's. |
| A copy that is a **sorcery instead of an incantation** (or the reverse) | ✗ It keeps its type. |
| A home-made spell that **deals damage** or **throws something** | ✗ Home-made spells only heal. For damage, remix a game spell. |
| A home-made **sorcery** | ✗ Home-made spells are incantations. |
| To **change a game spell** | ✗ Never. Your spells are always new. |
| New **weapons, armor, talismans** | ✗ Spells only for now. |
| More than 7 spells **for sale** | ✗ Not yet (shelves 8+). |
| More than about 20 spells in one file | ✗ The size check (Chapter 10). |
| Online play | ✗ Offline only. |

---

## Chapter 10 — How many spells can I make? (the suitcase)

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

**Rules of thumb:** plan for **about 20 mixed spells**, with **a few** fireballs and strikes, not a dozen. The weight depends on **how many things you add**, not on the numbers you choose: changing 15 to 30 never makes it heavier. The weight does not grow smoothly (one more spell can jump it), so **always rehearse** with `innovate-spells build --dry-run`.

*For developers:* the gate allows 27 changed 4-KiB blocks, 292,000 bytes of compressed-frame growth and 219,000 bytes of body growth (limits raised only after a bigger file passed in the game; the tested file had 27 blocks and 291,040 bytes). The developer tool `tools/capacity.py --source <original regulation.bin> --mix buff=16,projectile=2,attack=2` prints the numbers of any mix offline.

---

## Chapter 11 — Running it, and what the messages mean

### 11.1 The loop

```commandline
eldendisk innovate-spells build --dry-run    # 1. rehearse (a few seconds, writes nothing)
eldendisk run                                                    # 2. build, check, play
eldendisk innovate-spells secure               # 3. after it worked, game closed: keep this build
```

- **Build only some spells:** `innovate-spells build <id>` (the key of the spell's slot in `creative.json`) builds just that spell; give several paths to build several, e.g. `innovate-spells build my_heal my_flame`. `eldendisk run` then goes on building **the same spells** until you type `innovate-spells build` (or build another selection). If you never choose, `run` builds every spell. A rehearsal (`--dry-run`) does not change the choice. The tool always tells you which spells it is building and which it left out.
- `run` uses the **secured** build while your design equals the secured one. If you changed something it says what changed (`reverse_curse_technique.shop.price  34590 -> 40000`) and rebuilds.
- The files live in `<vault>\design\innovate-items\spells\`: `regulation.bin` (latest build), `regulation.secured.bin`, `spells.commit.json`.
- With `--vault-off` the spells are not used (and so no text is put in).
- The text of the spells (6.1b) is put in by `run` once the game is up; `eldendisk innovate-spells apply` (game running) does it again after you edit it.
- After a build, `check` (game running) compares every original row with the game: they must all be equal, and your new rows are counted.

### 11.2 Messages and what to do

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
| `GATE FAILED … nothing was swapped` | The suitcase is too heavy. | Fewer or lighter spells (Chapter 10). |
| `.name: renamed in 1.7.1: use text.goods_name` (also `description`) | A 1.7.0 field. | Move the words into the `text` object (6.1b). |
| `goods text: N spell(s) named in the game …` | The text was put into the running game. | Nothing; open the merchant or the inventory. |
| `the game's text tables were not found (…)` | The tool looked through the game's memory and did not find them: the game is not fully loaded, or it is another version or language of the game (the profile holds the sizes of the English tables). | Run `eldendisk innovate-spells apply` once a character is in the world. |
| `the game replaced its text tables again after they were set` | The game reloaded its text while the tool was done. | Run `eldendisk innovate-spells apply` again. |

---

## Chapter 12 — Quick Reference Card (the cheat-sheet)

### 12.0 The number map on one page

| You see | It is | Look it up in |
|:--|:--|:--|
| `"from": 6210` | the **Magic id** of a spell | Spell Finder (Appendix A): name → id |
| `Magic.6210.…` / `Goods.6210.…` | the same spell's own rows (item and spell) | same id as `from` |
| `SpEffect.1621000.…` | an **effect** the spell calls (burn, buff, blessing) | Row Finder: the spell's *SpEffect* line |
| `Bullet.10621000.…` | a **projectile** the spell makes | Row Finder: the spell's *Bullet* line |
| `AtkParam_Pc.62101.…` | a **hit** the spell makes | Row Finder: the spell's *Hit* line (with its base damage) |
| `….effectEndurance` / `….atkMag` | a **field** (column) | section 7.8 |
| `"cast_motion": 32` / `Magic.6430.refType` | a **cast animation** number (a Magic `refType`) | Motion Finder (in the Row Finder file) |
| `Magic.6430.castSfxId` / `fireSfxId` / `effectSfxId` | the **flash and sound** of the cast, and an extra effect (Magic fields) | Cast Finder (in the Row Finder file) |
| `"visual": 1605000` | a **visual effect** number (a SpEffect `vfxId`) | Visual Finder (in the Row Finder file) |
| the number after `:` | the new value | yours |

Key = `Table . row id . field : new value`.

### 12.1 Before you play

- [ ] Every shelf is where it was; `maximum` equals the number of shelves.
- [ ] New spells are on **empty** shelves; spells you want to **buy** are on shelves **1–7**.
- [ ] Every spell has either `kind` + `from` (a remix) or `type` + `requires` + `fp_cost` (home-made).
- [ ] `from` is in Appendix A for that workshop and type.
- [ ] `set` uses **the game's ids**, no link fields.
- [ ] `shop`: price ≥ 1; stock −1 or 1–99.
- [ ] `innovate-spells build --dry-run` says the gate passed.
- [ ] **One new idea** since the last build that worked.

### 12.2 Home-made spell (all fields; the values shown are the defaults)

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
  "text": { "goods_name": "My Spell", "goods_info": "One short line", "goods_captions": "What it does." }
}
```

Required: `type`, `requires`, `fp_cost`. Everything else can be left out.

### 12.3 Remixed spell (all fields)

```json
"my_remix_id": {
  "kind": "clone",
  "from": 6100,
  "fp_cost": 5,
  "stamina_cost": 0,
  "requires": { "intelligence": 0, "faith": 0 },
  "shop": { "price": 1000, "stock": -1 },
  "text": { "goods_name": "My Remix", "goods_info": "One short line", "goods_captions": "What it does." },
  "set": { "Magic.6100.slotLength": 1 }
}
```

Required: `kind`, `from`. `kind` is `clone`, `enchant`, `projectile`, `attack` or `buff`. Delete the lines you do not need.

The same spell in the structure of 1.7.1 (7.0; both build the same file):

```json
"my_remix_id": {
  "__info__": "my notes",
  "kind": "clone",
  "from": 6100,
  "requires":  { "status": { "intelligence": 0, "faith": 0 }, "cost": { "focus_point": 5, "stamina": 0 } },
  "locations": { "kale": { "price": 1000, "stock": -1 } },
  "customs": {
    "basic":    { "Magic.6100.slotLength": 1 },
    "advanced": { "texts": { "goods_name": "My Remix", "goods_info": "One short line", "goods_caption": "What it does." } }
  }
}
``` (`6100` is the id of Giantsflame Take Thee, a 2-slot spell; look yours up in the Spell Finder.)

### 12.4 All the limits on one page

| Thing | Limit |
|:--|:--|
| Shelves (`maximum`) | 1–64 (about 20 mixed fit the game) |
| Shelves with a shop line | 1–7 |
| Spell id | 1–40 characters of `a-z 0-9 _ -` |
| `requires.*` | 0–99 |
| `fp_cost`, `stamina_cost` | 0–999 |
| `shop.price` | 1–99,999,999 |
| `shop.stock` | −1 or 1–99 |
| `text.goods_name` / `goods_info` / `goods_captions` | 80 / 120 / 1000 characters |
| `heal_hp_per_tick` | 0–9999 |
| `restore_fp_per_tick` | 0–999 |
| `stamina_regen_speed` | 0–9999 |
| `tick_seconds` | 0.1–60 |
| `duration_seconds` | 0.5–600 |
| `poise_while_casting_seconds` | 0.1–10 |
| Effect rows per shelf | 8 · projectile rows 16 · hit rows 8 |
| Cast animations (home-made) | `flame-grant-me-strength`, `black-flame-blade`, or a number 0–999 used by a spell of the game |
| Glow (`visual`) | `flame`, `flask`, `none` (or `null`), or a number −1 to 99,999,999 used by an effect of the game |

### 12.5 Is it proven?

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
| `cast_motion` / `visual` by **name** | ✓ |
| `cast_motion` / `visual` by **another number** | ◦ accepted, not tried |
| Cast flash / sound (`castSfxId`, `fireSfxId`, `effectSfxId`) through `set` | ◦ builds and passes the checks, not tried |
| Names, descriptions, icons | ✗ not yet |
| Items other than spells | ✗ not yet |
| Shelves 8 and up for sale | ✗ not yet |

---

## Appendix A — Spell Finder: name → id (and who accepts it)

Look a spell up by name. The **Id** is what you write in `from`. **FP** and **Memory slots** are the original's values. A ✓ means that workshop accepts the spell; "too big" means its chain does not fit one shelf (a photocopy still works). Ids from 2,000,000 up are the DLC. Checked against the 1.17.1 game file; names from Paramdex.

*(Tip: use your editor's search to jump to a name.)*

### Incantations (129)

| Id (`from`) | Name | FP | Memory slots | Photocopier | Buff tuner | Enchant tuner | Fireball | Strike |
|--:|:--|--:|--:|:-:|:-:|:-:|:-:|:-:|
| 5040 | Death Lightning | 28 | 2 | ✓ |  |  | ✓ |  |
| 6000 | Catch Flame | 10 | 1 | ✓ |  |  | ✓ |  |
| 6001 | O, Flame! | 16 | 1 | ✓ |  |  | ✓ |  |
| 6010 | Flame Sling | 11 | 1 | ✓ |  |  | ✓ |  |
| 6020 | Flame Fall Upon Them | 16 | 1 | ✓ |  |  | ✓ |  |
| 6030 | Whirl, O Flame | 19 | 1 | ✓ |  |  | ✓ |  |
| 6040 | Flame Cleanse Me | 14 | 1 | ✓ |  |  | ✓ |  |
| 6050 | Flame Grant Me Strength | 28 | 1 | ✓ | ✓ |  |  |  |
| 6060 | Flame Protect Me | 30 | 1 | ✓ | ✓ |  |  |  |
| 6100 | Giantsflame Take Thee | 30 | 2 | ✓ |  |  | ✓ |  |
| 6110 | Flame of The Fell God | 34 | 2 | ✓ |  |  | ✓ |  |
| 6120 | Burn, O Flame! | 26 | 1 | ✓ |  |  | ✓ |  |
| 6210 | Black Flame | 18 | 1 | ✓ |  |  | ✓ |  |
| 6220 | Surge, O Flame | 1 | 1 | ✓ |  |  | ✓ |  |
| 6230 | Scouring Black Flame | 21 | 1 | ✓ |  |  | ✓ |  |
| 6240 | Black Flame Ritual | 30 | 1 | ✓ |  |  | ✓ |  |
| 6250 | Black Flame Blade | 15 | 1 | ✓ |  | ✓ |  |  |
| 6260 | Black Flame's Protection | 30 | 1 | ✓ | ✓ |  |  |  |
| 6270 | Noble Presence | 20 | 1 | ✓ |  |  | ✓ |  |
| 6300 | Bloodflame Talons | 12 | 1 | ✓ |  |  | ✓ |  |
| 6310 | Bloodboon | 13 | 1 | ✓ |  |  | ✓ |  |
| 6320 | Bloodflame Blade | 20 | 1 | ✓ |  | ✓ |  |  |
| 6330 | Barrier of Gold | 30 | 1 | ✓ |  |  | ✓ |  |
| 6340 | Protection of The Erdtree | 30 | 1 | ✓ |  |  | ✓ |  |
| 6400 | Rejection | 9 | 1 | ✓ |  |  | ✓ |  |
| 6410 | Wrath of Gold | 40 | 1 | ✓ |  |  | ✓ |  |
| 6420 | Urgent Heal | 16 | 1 | ✓ |  |  | ✓ |  |
| 6421 | Heal | 32 | 1 | ✓ |  |  | ✓ |  |
| 6422 | Great Heal | 45 | 1 | ✓ |  |  | ✓ |  |
| 6423 | Lord's Heal | 55 | 1 | ✓ |  |  | ✓ |  |
| 6424 | Erdtree Heal | 65 | 1 | ✓ |  |  | ✓ |  |
| 6430 | Blessing's Boon | 30 | 1 | ✓ |  |  | ✓ |  |
| 6431 | Blessing of The Erdtree | 60 | 1 | ✓ |  |  | ✓ |  |
| 6440 | Cure Poison | 7 | 1 | ✓ |  |  | ✓ |  |
| 6441 | Lord's Aid | 12 | 1 | ✓ |  |  | too big |  |
| 6450 | Flame Fortification | 20 | 1 | ✓ | ✓ |  |  |  |
| 6460 | Magic Fortification | 20 | 1 | ✓ | ✓ |  |  |  |
| 6470 | Lightning Fortification | 20 | 1 | ✓ | ✓ |  |  |  |
| 6480 | Divine Fortification | 20 | 1 | ✓ | ✓ |  |  |  |
| 6490 | Lord's Divine Fortification | 30 | 1 | ✓ |  |  | ✓ |  |
| 6510 | Assassin's Approach | 15 | 1 | ✓ |  |  | ✓ |  |
| 6520 | Shadow Bait | 15 | 1 | ✓ |  |  | ✓ |  |
| 6530 | Darkness | 24 | 1 | ✓ |  |  | ✓ |  |
| 6600 | Golden Vow | 47 | 1 | ✓ |  |  | ✓ |  |
| 6700 | Discus of Light | 3 | 1 | ✓ |  |  | ✓ |  |
| 6701 | Triple Rings of Light | 23 | 1 | ✓ |  |  | ✓ |  |
| 6710 | Radagon's Rings of Light | 21 | 1 | ✓ |  |  | ✓ |  |
| 6720 | Elden Stars | 41 | 2 | ✓ |  |  | ✓ |  |
| 6730 | Law of Regression | 55 | 1 | ✓ |  |  | too big |  |
| 6740 | Immutable Shield | 15 | 1 | ✓ |  | ✓ |  |  |
| 6750 | Litany of Proper Death | 17 | 1 | ✓ |  |  | ✓ |  |
| 6760 | Law of Causality | 22 | 1 | ✓ |  |  | ✓ |  |
| 6770 | Order's Blade | 22 | 1 | ✓ |  | ✓ |  |  |
| 6780 | Order Healing | 15 | 1 | ✓ |  |  | ✓ |  |
| 6800 | Bestial Sling | 7 | 1 | ✓ |  |  | ✓ |  |
| 6810 | Stone of Gurranq | 15 | 1 | ✓ |  |  | ✓ |  |
| 6820 | Beast Claw | 10 | 1 | ✓ |  |  | too big |  |
| 6830 | Gurranq's Beast Claw | 21 | 1 | ✓ |  |  | ✓ |  |
| 6840 | Bestial Vitality | 18 | 1 | ✓ | ✓ |  |  |  |
| 6850 | Bestial Constitution | 10 | 1 | ✓ |  |  | ✓ |  |
| 6900 | Lightning Spear | 18 | 1 | ✓ |  |  | ✓ |  |
| 6910 | Ancient Dragons' Light Strike | 36 | 1 | ✓ |  |  | too big |  |
| 6920 | Lightning Strike | 19 | 1 | ✓ |  |  | ✓ |  |
| 6921 | Frozen Lightning Spear | 29 | 1 | ✓ |  |  | ✓ |  |
| 6930 | Honed Bolt | 12 | 1 | ✓ |  |  | ✓ |  |
| 6940 | Ancient Dragons' Light Spear | 25 | 1 | ✓ |  |  | ✓ |  |
| 6941 | Fortissax's Light Spear | 35 | 1 | ✓ |  |  | too big |  |
| 6950 | Lansseax's Glaive | 22 | 1 | ✓ |  |  | ✓ |  |
| 6960 | Electrify Armament | 27 | 1 | ✓ |  | ✓ |  |  |
| 6970 | Vyke's Dragonbolt | 35 | 1 | ✓ |  | ✓ |  |  |
| 6971 | Dragonbolt Blessing | 20 | 1 | ✓ | ✓ |  |  |  |
| 7000 | Dragonfire | 28 | 1 | ✓ |  |  | ✓ |  |
| 7001 | Agheel's Flame | 36 | 1 | ✓ |  |  | ✓ |  |
| 7010 | Magma Breath | 30 | 1 | ✓ |  |  | ✓ |  |
| 7011 | Theodorix's Magma | 45 | 1 | ✓ |  |  | ✓ |  |
| 7020 | Dragonice | 36 | 1 | ✓ |  |  | ✓ |  |
| 7021 | Borealis's Mist | 48 | 1 | ✓ |  |  | ✓ |  |
| 7030 | Rotten Breath | 36 | 1 | ✓ |  |  | ✓ |  |
| 7031 | Ekzykes's Decay | 48 | 1 | ✓ |  |  | ✓ |  |
| 7040 | Glintstone Breath | 28 | 1 | ✓ |  |  | ✓ |  |
| 7041 | Smarag's Glint Breath | 36 | 1 | ✓ |  |  | ✓ |  |
| 7050 | Placidusax's Ruin | 62 | 3 | ✓ |  |  | ✓ |  |
| 7060 | Dragonclaw | 24 | 1 | ✓ |  |  | ✓ |  |
| 7080 | Dragonmaw | 34 | 1 | ✓ |  |  |  | ✓ |
| 7090 | Greyoll's Roar | 50 | 2 | ✓ |  |  | ✓ |  |
| 7200 | Pest Threads | 19 | 1 | ✓ |  |  | ✓ |  |
| 7210 | Swarm of Flies | 14 | 1 | ✓ |  |  | ✓ |  |
| 7220 | Poison Mist | 18 | 1 | ✓ |  |  | ✓ |  |
| 7230 | Poison Armament | 15 | 1 | ✓ |  | ✓ |  |  |
| 7240 | Scarlet Aeonia | 48 | 3 | ✓ |  |  | ✓ |  |
| 7300 | Inescapable Frenzy | 22 | 1 | ✓ |  |  | ✓ |  |
| 7310 | The Flame of Frenzy | 16 | 1 | ✓ |  |  | ✓ |  |
| 7311 | Unendurable Frenzy | 22 | 1 | ✓ |  |  | ✓ |  |
| 7320 | Frenzied Burst | 24 | 1 | ✓ |  |  | ✓ |  |
| 7330 | Howl of Shabriri | 21 | 1 | ✓ |  |  | ✓ |  |
| 7500 | Aspects of the Crucible: Tail | 20 | 1 | ✓ |  |  | ✓ |  |
| 7510 | Aspects of the Crucible: Horns | 18 | 1 | ✓ |  |  |  | ✓ |
| 7520 | Aspects of the Crucible: Breath | 28 | 1 | ✓ |  |  | ✓ |  |
| 7530 | Black Blade | 26 | 2 | ✓ |  |  | ✓ |  |
| 7900 | Fire's Deadly Sin | 26 | 1 | ✓ |  |  | ✓ |  |
| 7903 | Golden Light Fortification | 30 | 1 | ✓ |  |  | ✓ |  |
| 2006300 | Furious Blade of Ansbach *(DLC)* | 18 | 1 | ✓ |  |  | too big |  |
| 2006400 | Heal from Afar *(DLC)* | 45 | 1 | ✓ |  |  | ✓ |  |
| 2006650 | Aspects of the Crucible: Thorns *(DLC)* | 14 | 1 | ✓ |  |  | ✓ |  |
| 2006660 | Aspects of the Crucible: Bloom *(DLC)* | 23 | 1 | ✓ |  |  | ✓ |  |
| 2006670 | Minor Erdtree *(DLC)* | 30 | 2 | ✓ |  |  | ✓ |  |
| 2006680 | Land of Shadow *(DLC)* | 40 | 1 | ✓ |  |  | ✓ |  |
| 2006690 | Wrath from Afar *(DLC)* | 18 | 1 | ✓ |  |  | ✓ |  |
| 2006700 | Light of Miquella *(DLC)* | 48 | 2 | ✓ |  |  | ✓ |  |
| 2006710 | Multilayered Ring of Light *(DLC)* | 23 | 1 | ✓ |  |  | ✓ |  |
| 2006800 | Roar of Rugalea *(DLC)* | 17 | 1 | ✓ |  |  | ✓ |  |
| 2006900 | Knight's Lightning Spear *(DLC)* | 29 | 1 | ✓ |  |  | too big |  |
| 2006910 | Dragonbolt of Florissax *(DLC)* | 35 | 1 | ✓ |  |  | ✓ |  |
| 2006920 | Electrocharge *(DLC)* | 26 | 1 | ✓ |  |  | ✓ |  |
| 2007000 | Bayle's Tyranny *(DLC)* | 46 | 2 | ✓ |  |  | ✓ |  |
| 2007010 | Bayle's Flame Lightning *(DLC)* | 43 | 2 | ✓ |  |  | ✓ |  |
| 2007020 | Ghostflame Breath *(DLC)* | 36 | 1 | ✓ |  |  | ✓ |  |
| 2007200 | Rotten Butterflies *(DLC)* | 48 | 1 | ✓ |  |  | ✓ |  |
| 2007210 | Pest-Thread Spears *(DLC)* | 28 | 1 | ✓ |  |  | ✓ |  |
| 2007300 | Midra's Flame of Frenzy *(DLC)* | 22 | 2 | ✓ |  |  | ✓ |  |
| 2007600 | Watchful Spirit *(DLC)* | 12 | 1 | ✓ |  |  | ✓ |  |
| 2007700 | Golden Arcs *(DLC)* | 12 | 1 | ✓ |  |  | ✓ |  |
| 2007710 | Giant Golden Arc *(DLC)* | 24 | 1 | ✓ |  |  | ✓ |  |
| 2007720 | Spira *(DLC)* | 10 | 2 | ✓ |  |  | ✓ |  |
| 2007730 | Divine Beast Tornado *(DLC)* | 24 | 1 | ✓ |  |  | ✓ |  |
| 2007740 | Divine Bird Feathers *(DLC)* | 3 | 1 | ✓ |  |  | ✓ |  |
| 2007800 | Fire Serpent *(DLC)* | 11 | 1 | ✓ |  |  | ✓ |  |
| 2007810 | Rain of Fire *(DLC)* | 27 | 1 | ✓ |  |  | too big |  |
| 2007820 | Messmer's Orb *(DLC)* | 31 | 2 | ✓ |  |  | ✓ |  |

### Sorceries (84)

| Id (`from`) | Name | FP | Memory slots | Photocopier | Buff tuner | Enchant tuner | Fireball | Strike |
|--:|:--|--:|--:|:-:|:-:|:-:|:-:|:-:|
| 4000 | Glintstone Pebble | 7 | 1 | ✓ |  |  | ✓ |  |
| 4001 | Great Glintstone Shard | 12 | 1 | ✓ |  |  | ✓ |  |
| 4010 | Swift Glintstone Shard | 5 | 1 | ✓ |  |  | ✓ |  |
| 4020 | Glintstone Cometshard | 17 | 1 | ✓ |  |  | ✓ |  |
| 4021 | Comet | 24 | 1 | ✓ |  |  | ✓ |  |
| 4030 | Shard Spiral | 14 | 1 | ✓ |  |  | ✓ |  |
| 4040 | Glintstone Stars | 12 | 1 | ✓ |  |  | too big |  |
| 4050 | Star Shower | 23 | 1 | ✓ |  |  | too big |  |
| 4060 | Crystal Barrage | 14 | 1 | ✓ |  |  | ✓ |  |
| 4070 | Glintstone Arc | 9 | 1 | ✓ |  |  | ✓ |  |
| 4080 | Cannon of Haima | 38 | 1 | ✓ |  |  | ✓ |  |
| 4090 | Crystal Burst | 14 | 1 | ✓ |  |  | ✓ |  |
| 4100 | Shatter Earth | 10 | 1 | ✓ |  |  | ✓ |  |
| 4110 | Rock Blaster | 22 | 1 | ✓ |  |  | ✓ |  |
| 4120 | Gavel of Haima | 22 | 1 | ✓ |  |  | ✓ |  |
| 4130 | Terra Magicus | 20 | 1 | ✓ |  |  | ✓ |  |
| 4140 | Starlight | 9 | 1 | ✓ | ✓ |  |  |  |
| 4200 | Comet Azur | 40 | 3 | ✓ |  |  | ✓ |  |
| 4210 | Founding Rain of Stars | 27 | 2 | ✓ |  |  | too big |  |
| 4220 | Stars of Ruin | 32 | 1 | ✓ |  |  | too big |  |
| 4300 | Glintblade Phalanx | 18 | 1 | ✓ |  |  | ✓ |  |
| 4301 | Carian Phalanx | 24 | 1 | ✓ |  |  | ✓ |  |
| 4302 | Greatblade Phalanx | 30 | 1 | ✓ |  |  | ✓ |  |
| 4360 | Rennala's Full Moon | 47 | 2 | ✓ |  |  | ✓ |  |
| 4361 | Ranni's Dark Moon | 57 | 2 | ✓ |  |  | ✓ |  |
| 4370 | Magic Downpour | 18 | 1 | ✓ |  |  | too big |  |
| 4380 | Loretta's Greatbow | 24 | 1 | ✓ |  |  | ✓ |  |
| 4381 | Loretta's Mastery | 39 | 1 | ✓ |  |  | ✓ |  |
| 4390 | Magic Glintblade | 12 | 1 | ✓ |  |  | ✓ |  |
| 4400 | Glintstone Icecrag | 12 | 1 | ✓ |  |  | ✓ |  |
| 4410 | Zamor Ice Storm | 17 | 1 | ✓ |  |  | ✓ |  |
| 4420 | Freezing Mist | 20 | 1 | ✓ |  |  | ✓ |  |
| 4430 | Carian Greatsword | 12 | 1 | ✓ |  |  |  | ✓ |
| 4431 | Adula's Moonblade | 22 | 1 | ✓ |  |  | ✓ |  |
| 4440 | Carian Slicer | 4 | 1 | ✓ |  |  |  | ✓ |
| 4450 | Carian Piercer | 17 | 1 | ✓ |  |  |  | ✓ |
| 4460 | Scholar's Armament | 25 | 1 | ✓ |  | ✓ |  |  |
| 4470 | Scholar's Shield | 30 | 1 | ✓ |  | ✓ |  |  |
| 4480 | Lucidity | 10 | 1 | ✓ |  |  | ✓ |  |
| 4490 | Frozen Armament | 20 | 1 | ✓ |  | ✓ |  |  |
| 4500 | Shattering Crystal | 21 | 1 | ✓ |  |  | ✓ |  |
| 4510 | Crystal Release | 34 | 1 | ✓ |  |  | ✓ |  |
| 4520 | Crystal Torrent | 20 | 1 | ✓ |  |  | ✓ |  |
| 4600 | Ambush Shard | 13 | 1 | ✓ |  |  | ✓ |  |
| 4610 | Night Shard | 7 | 1 | ✓ |  |  | ✓ |  |
| 4620 | Night Comet | 21 | 1 | ✓ |  |  | ✓ |  |
| 4630 | Thops's Barrier | 7 | 1 | ✓ |  |  | ✓ |  |
| 4640 | Carian Retaliation | 8 | 1 | ✓ |  |  | ✓ |  |
| 4650 | Eternal Darkness | 25 | 1 | ✓ |  |  | ✓ |  |
| 4660 | Unseen Blade | 13 | 1 | ✓ |  | ✓ |  |  |
| 4670 | Unseen Form | 20 | 1 | ✓ |  |  | ✓ |  |
| 4700 | Meteorite | 30 | 1 | ✓ |  |  | too big |  |
| 4701 | Meteorite of Astel | 60 | 2 | ✓ |  |  | too big |  |
| 4710 | Rock Sling | 18 | 1 | ✓ |  |  | too big |  |
| 4720 | Gravity Well | 12 | 1 | ✓ |  |  | ✓ |  |
| 4721 | Collapsing Stars | 18 | 1 | ✓ |  |  | ✓ |  |
| 4800 | Magma Shot | 16 | 1 | ✓ |  |  | ✓ |  |
| 4810 | Gelmir's Fury | 16 | 1 | ✓ |  |  | ✓ |  |
| 4820 | Roiling Magma | 28 | 1 | ✓ |  |  | too big |  |
| 4830 | Rykard's Rancor | 23 | 2 | ✓ |  |  | ✓ |  |
| 4900 | Briars of Sin | 6 | 1 | ✓ |  |  | ✓ |  |
| 4910 | Briars of Punishment | 9 | 1 | ✓ |  |  | ✓ |  |
| 5000 | Rancorcall | 12 | 1 | ✓ |  |  | ✓ |  |
| 5001 | Ancient Death Rancor | 21 | 1 | ✓ |  |  | ✓ |  |
| 5010 | Explosive Ghostflame | 29 | 1 | ✓ |  |  | ✓ |  |
| 5020 | Fia's Mist | 25 | 1 | ✓ |  |  | ✓ |  |
| 5030 | Tibia's Summons | 17 | 1 | ✓ |  |  | ✓ |  |
| 5100 | Oracle Bubbles | 12 | 1 | ✓ |  |  | ✓ |  |
| 5110 | Great Oracular Bubble | 16 | 1 | ✓ |  |  | ✓ |  |
| 6500 | Night Maiden's Mist | 20 | 1 | ✓ |  |  | ✓ |  |
| 2004300 | Miriam's Vanishing *(DLC)* | 9 | 1 | ✓ | ✓ |  |  |  |
| 2004310 | Glintblade Trio *(DLC)* | 19 | 1 | ✓ |  |  | ✓ |  |
| 2004320 | Rellana's Twin Moons *(DLC)* | 47 | 2 | ✓ |  |  | ✓ |  |
| 2004500 | Glintstone Nail *(DLC)* | 10 | 1 | ✓ |  |  | too big |  |
| 2004510 | Glintstone Nails *(DLC)* | 23 | 1 | ✓ |  |  | too big |  |
| 2004700 | Blades of Stone *(DLC)* | 18 | 2 | ✓ |  |  | too big |  |
| 2004710 | Gravitational Missile *(DLC)* | 18 | 1 | ✓ |  |  | too big |  |
| 2004900 | Mantle of Thorns *(DLC)* | 9 | 1 | ✓ | ✓ |  |  |  |
| 2004910 | Impenetrable Thorns *(DLC)* | 15 | 1 | ✓ |  |  | ✓ |  |
| 2005000 | Rings of Spectral Light *(DLC)* | 14 | 1 | ✓ |  |  | ✓ |  |
| 2006200 | Vortex of Putrescence *(DLC)* | 29 | 2 | ✓ |  |  | ✓ |  |
| 2006210 | Mass of Putrescence *(DLC)* | 41 | 1 | ✓ |  |  | too big |  |
| 2007410 | Fleeting Microcosm *(DLC)* | 26 | 1 | ✓ |  |  | ✓ |  |
| 2007420 | Cherishing Fingers *(DLC)* | 20 | 1 | ✓ |  |  | too big |  |

## Appendix B — Row Finder: id → the rows a spell uses

One entry per spell for every workshop above the Photocopier, with the ids you may write in `set`, their names, durations and base damage. The same file also holds the **Motion Finder** (numbers for `cast_motion`), the **Visual Finder** (numbers for `effect.visual`) and the **Cast Finder** (the four cast numbers of every spell): **[spells-row-finder.md](spells-row-finder.md)** (a companion file next to this one).

## Appendix C — For developers: where each fact comes from

| Topic | Source |
|:--|:--|
| Field ranges, `set` rules, messages | `code/eldendisk/design/innovate_items/spells/spec.py`, `recipes.py` |
| Rows per shelf, ids | `recipes.py`, `build.py`, `chain.py` |
| Gate numbers | `code/eldendisk/design/innovate_items/preflight.py` |
| Field names per table | `paramdefs.py` (generated from Paramdex) |
| Spell and row names, Finders | Paramdex `ER/Names/*.txt` (community), ids and numbers read from the original 1.17.1 `regulation.bin` with the tool's own chain reader (`chain.py`) |
| Tests in the game | [manual-test-plan-1.7.0](../experiments/extensional/innovate-items/spell/level2/docs/manual-test-plan-1.7.0.md) |
| Roadmap, what is deferred | [roadmap-innovate-spells](../experiments/extensional/innovate-items/spell/level2/docs/roadmap-innovate-spells.md) |
| The full spec | [elden-disk-spec-v1.7.0](../specs/elden-disk-spec-v1.7.0.md) |
| The story of how the first spell was built | [Item Customization Handbook](innovate-items-handbook.md) |

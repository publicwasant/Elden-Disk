# Item Customization Handbook
### Creating a brand-new incantation in Elden Ring 1.17.1 by editing `regulation.bin` — lab notes, experiments, and a method you can repeat

> **Status:** checkpoint 1 of 2 — the *data layer* of a new item works in the real game; the *UI layer* (name, description text, custom image) is still open.
> **Case study:** the incantation **Reverse Curse Technique** (custom; regenerates HP, FP and stamina)
> **Game:** Elden Ring app version 1.17.1, `regulation.bin` SHA-256 `766521f9508de3a3532df61c45a1c2d93340f1ff7ed8306ab20df761712ca2ab` (2,045,728 bytes), offline play only
> **Written:** 2026-10-08 (update 2026-10-09 below)
> **Language:** English (technical terms are explained where they first appear; Appendix D is a glossary)
> **Companion material:** `tools/` (every script needed to reproduce the build, next to this file) and `../../memory-read-101.md` (how Elden-Disk reads the live game, which is how we *observed* the result)

> **Update 2026-10-09.** The final item (Z4: Flame-style cast, 34,590 runes, stock 1, Int 45 / Fai 15 / Arc 10, FP 80, 2.0 s poise buff) worked in the real game, and **Elden-Disk now builds this file itself** (`innovate-items spells`, spec 1.7.0): same bytes as `tools/make_item.py --name Z4` (decrypted SHA-256 `1aa16ee0dbcbc5902cef2b6eb29bd542f42b2158fcdb44c221c187280db5277b`), swapped in by `run`, put back byte-identical by the vault. The Y1/Y2 "pending" lines below are superseded by Z4. The poise part is not yet confirmed in the game. For more than one item see 17.1 (measurements added) and spec 1.7.0 section 10b.
>
> **Update 2026-10-09 (later).** Slot 1 of the back-growth build (appended rows in Goods, Magic, SpEffect and ShopLineup) passed in the game, and Elden-Disk can now *look at and change the tables of the running game*: `read --param Magic.6230` shows any row of Goods, Magic, SpEffect, Bullet, AtkParam_Pc and ShopLineup by field name, `write --set params.Magic.6230.mp=0` changes a field live (and `--reset` puts the game's own value back), `read --param-check` compares a built `regulation.bin` with the game row by row (the slot-1 build was equal on every row of all six tables). This is the "observe" half of the method in this book without Cheat Engine, and the test bench for the next kinds of spell (clone, buff, enchant, projectile, attack): Magic is read at the cast, Bullet when the bullet is created, and a changed row acts only on what is created afterwards. See [phase1-params-workbench.md](../experiments/extensional/innovate-items/spell/level2/docs/phase1-params-workbench.md) and [roadmap-innovate-spells.md](../experiments/extensional/innovate-items/spell/level2/docs/roadmap-innovate-spells.md).

>
> **Update 2026-10-11 (1.7.1) — the text layer works.** Name, short line and long description of the new item now show in the real game. Not by editing a file (a loose replacement of the text archive is not read by the unpatched game, tried), but by giving the *running* game a rebuilt text table: Elden-Disk copies the game's own table, adds the entries for the new Goods ids, puts it in memory it allocates in the game and changes the single pointer that leads to it. Chapter 19 has the method, how the tool finds the tables (by scanning, not by a fixed chain), the colour of the fire, the research tools and the limits. The icon is still open.
---

## Preface — what this book is, and what it is not

Elden Ring keeps almost all of its gameplay data in tables called **params**, packed together in one encrypted, compressed file: `regulation.bin`. Every item, spell, buff, shop line and projectile is a row in one of those tables. If you can write that file, you can add things to the game.

Doing that *safely and repeatably* turned out to be the hard part. This book records what we actually did: roughly **70 test files**, each one loaded by hand into the real game by the project owner, with a pass/fail result written down. It is organised so that you can:

1. **Read the verdict first** (Chapter 1: what works, what does not).
2. **Understand the machinery** (Part I: the file format; Part II: how an incantation is wired together).
3. **See the evidence** (Part III: every experiment, including the ones that failed and why that was useful).
4. **Rebuild it yourself** (Part IV: a step-by-step recipe with commands, plus a configuration reference).
5. **Know what is still unknown** (Part V).

### Conventions used in this book

> 📌 **Case File** = a real observation from our sessions (a test id, a number, a screenshot, a log line).
> ⚠️ **Warning** = a mistake that cost us time, or a risk you should know about.
> 🔬 **Confidence** = how sure we are, stated bluntly.

Evidence levels (used in tables):

| Level | Meaning |
|---|---|
| **E0** | Computed or inferred only; nothing was run in the game |
| **E1** | Verified offline: our decoder **and** libzstd both decode the file back to exactly the intended bytes |
| **E2** | The game **loaded** it (title screen → character → world, playable) |
| **E3** | The game **showed the effect** (a price, a menu entry, a buff timer, an animation) |

A result is only called a **PASS** at E2 or better. A result is a **FAIL** if the game showed *Failed to save game. Save data is corrupted*, hung, or terminated.

### Scope and safety (read this before you copy any file into your game)

- Everything here was done on a **single-player, offline** installation: Steam in offline mode, cloud saves off, auto-update off, anti-cheat bypassed with the project's offline launcher. **Do not play online with a modified `regulation.bin`.** Modified params are exactly what anti-cheat and server-side checks look for; the realistic outcome is a ban.
- **Back up** the original `regulation.bin` and your saves before the first test. Keep an untouched copy named `regulation.orig.bin`; every script in this book reads it as the starting point.
- The game folder and the Elden-Disk vault were treated as **read-only unless explicitly allowed per file**. Test files were written only to the vault's `regulation\` folder and then swapped in by the user.
- A new game patch changes `regulation.bin`. Files built for 1.17.1 must not be reused on another version; rebuild from that version's pristine file.

---

## Chapter 1 — Executive summary

### 1.1 The goal, as stated

Create a **brand-new incantation** (not a re-skin of an existing one), by any technical means, with a method that can be repeated for more items later:

| # | Requirement | Status today | Evidence |
|---|---|---|---|
| 1 | A truly new item, repeatable method | ✅ done for **one** item; a second item needs free rows (see 17.1) | E3 |
| 2a | Has an icon | ✅ (re-uses an existing icon id) | E3 |
| 2b | Has a name and a description | ✅ (1.7.1, real game 2026-10-11) name, short line and long description are put into the running game's text tables, no file changes (Chapter 19) | E3, 19.6 |
| 2c | Has a custom *image* | ⏳ not started (needs the menu-texture archive) | — |
| 3 | Is an incantation with a configurable Faith requirement | ✅ shows *Incantation*, *Fai 20*, FP cost 30 | E3 |
| 4 | On use: restore HP, FP and stamina | ✅ buff lasts 15.0 s, all three rise | E3 |
| 4b | …"until full, then end" | ⏳ currently a fixed 15 s | — |
| 5 | Appears in the inventory immediately (no purchase) | ⏳ not done; it is bought from a merchant today | — |
| 6 | Visual effect copied from a vanilla animation | ✅ flask glow and kneel animation seen (X1); Flame-style cast being tested (Y1/Y2) | E3 / Z4 |
| 7 | Sold by a merchant at a fixed price, stock 1 | ✅ (X1 verified buy / memorize / cast); price 8,990 + stock 1 in Y1/Y2; final Z4 price 34,590 | E3 / Z4 |

### 1.2 The five discoveries that mattered

1. **The game's loader is picky about the *compressed* layout, not about the content.** A `regulation.bin` is a single zstd frame cut into 64 KiB blocks. A file whose bytes decode to *exactly the same params* is accepted or rejected depending only on how the frame is built (Chapter 9–11).
2. **Whole-frame re-compression with a standard zstd library always failed.** Four independent variants hung or terminated the game (tests A, C2, C3, C5).
3. **Splicing "stored" (uncompressed) blocks into the original frame often worked… and often did not**, in a pattern we could not explain (tests E7, F1, J, K, L, Q, R, S, T). *Every* failure in the whole campaign involved stored blocks.
4. **A frame made only of compressed blocks never failed.** We wrote our own block encoder (our own FSE sequence encoder plus a repeat-offset solver) so that only the blocks that really changed are rewritten as compressed blocks, and every other byte of the original frame is kept. After that, **every build made this way loaded — 8 out of 8** (U6, U32, V1a–V1d, W1, X1) — including the first complete item (Chapter 11).
5. **An incantation can be built from just three rows** (Goods + Magic + SpEffect), because a Magic row may point *straight at a SpEffect* (`refCategory1 = 2`). No projectile (Bullet) row is needed for a self-buff (Chapter 5).

### 1.3 What a user sees today

> 📌 **Case File — test X1 (screenshot, in game)**
> The merchant's *Purchase Item* screen shows a new entry in the incantation tab: icon of a golden scroll, name **`?GoodsName?`**, type **Incantation**, *FP Cost 30*, *Slots Used 1*, *Attributes Required: Fai 20*, price **4,444**. The purchase dialog asks *Purchase how many? 1 / 699*. After buying: runes drop by the price, the item is in the inventory, it can be memorised, and casting it kneels the character, plays the flask glow and shows a buff icon.
>
> `eldendisk read --live-buffs` during the cast printed the buff row: `+ 999999999  Unknown  5.1 / 15.0 s` — a **15.0 s** timer counting down, on the SpEffect id we had put in the file. (Later builds use id `21950111`, now named in `chr_state_ids.json`.)

### 1.4 The one-paragraph method

Take the pristine `regulation.bin`; decrypt it (AES-256-CBC); unwrap the DCX/zstd container; parse the BND4 archive; edit the **unused "dummy" rows at the end of the Goods, Magic, SpEffect and Shop tables** (they are already last in id order, so relabelling them keeps every table sorted and the same size); rebuild the BND4 (same length); then write the result back as the **original zstd frame in which only the touched 64 KiB blocks are re-encoded as ordinary compressed blocks**. Encrypt with a fresh IV. Verify offline. Copy to the game folder, play offline.

---

# Part I — Anatomy of `regulation.bin`

## Chapter 2 — The container stack

`regulation.bin` is five layers deep. Each layer was verified byte-for-byte before anything was edited (see `tools/selftest.py`).

```
regulation.bin  (2,045,728 bytes)
└─ AES-256-CBC     IV = first 16 bytes, no padding scheme: zero bytes fill to a multiple of 16
   └─ DCX header   0x4C bytes ("DCX\0" … "DCS" … "DCP" "ZSTD" … "DCA")
      └─ zstd frame        2,045,634 bytes   827 blocks, window 64 MiB
         └─ BND4 archive   54,111,776 bytes  194 entries (…param files)
            └─ PARAM       one table per entry (rows of fixed size)
```

### 2.1 Layer 1 — AES

| Item | Value |
|---|---|
| Cipher | AES-256, CBC mode |
| Key | `99 BF FC 36 6A 6B C8 C6 F5 82 7D 09 36 02 D6 76 C4 28 92 A0 1C 20 7F B0 24 D3 AF 4E 49 3F EF 99` (the key the modding community has published for Elden Ring; we *verified* it by checking that the decrypted text begins with `DCX\0`) |
| IV | the first 16 bytes of the file; we always write a fresh random IV |
| Padding | the plaintext is zero-filled to a multiple of 16 |

📌 **Case File** — file length arithmetic: `16 (IV) + 0x4C (DCX header) + 2,045,634 (frame) + 2 (zero padding) = 2,045,728`. That *"2 trailing zero bytes"* shape turned out to matter for how we tuned file sizes (Section 10.4).

### 2.2 Layer 2 — the DCX header (0x4C bytes)

Only three fields matter to us; everything else is copied untouched from the original:

| Offset | Size | Meaning | Endianness |
|---|---|---|---|
| `0x00` | 4 | magic `DCX\0` | — |
| `0x1C` | 4 | **uncompressed size** (here 54,111,776) | big-endian |
| `0x20` | 4 | **compressed size** (the frame length) | big-endian |
| `0x28` | 4 | codec name `ZSTD` | — |
| `0x2C` | 1 | compression level byte (0x15 in the original) | — |

Whenever the body length or the frame length changes you must rewrite the two big-endian sizes. Our builds never change the body length (all edits are same-size), only the frame length.

### 2.3 Layer 3 — the zstd frame (the part that caused 90% of the trouble)

The original frame was produced by the game's toolchain, not by a standard library call. Its shape is unusual, and **the game's loader proved to care**:

| Property | Original value |
|---|---|
| Frame header | `28 b5 2f fd 00 80` — magic, then descriptor `00` (no content size, no checksum, no dictionary) and window descriptor `0x80` = **64 MiB window** |
| Blocks | **827**: 826 compressed blocks of 65,536 output bytes (the last compressed one is partial: 44,576 bytes) + **one empty stored block** carrying the "last block" flag |
| Block types used | compressed (type 2) ×826, stored (type 0) ×1 (the empty last block); **no RLE blocks** |
| Literals sections | raw ×194, Huffman-compressed with a new tree ×590, treeless (re-use previous tree) ×45 |
| Sequence tables | FSE-compressed (mode 2) in 806 blocks, *predefined* (mode 0) in 20; **never RLE, never "repeat"** |
| Trailing bytes | 2 zero bytes after the frame |

> 📌 **Case File — frame census** (`tools/inspect_frame.py`)
> ```
> blocks 827 frame bytes 2045634 body bytes 54111776 frame header 28b52ffd0080
> ('block type', 0) 1        ('block type', 2) 826
> ('literals type/size-format', (0, *)) 194     (2, *) 590     (3, *) 45
> ('seq mode ll', 0) 20      ('seq mode ll', 2) 806     (same for 'of' and 'ml')
> ```

Each block's output is independent *in size* (every block decodes to 64 KiB) but **not independent in state**. A block can depend on two things left behind by earlier blocks:

- the **repeat-offset registers** (three numbers `rep0, rep1, rep2` that "repeat offset" codes refer to), and
- the **Huffman tree** (a *treeless* literals section re-uses the tree of the previous block that had one).

Matches may also copy bytes from any earlier block (the window is 64 MiB), so changed bytes can in principle be "referenced" by later blocks; in our edits this never happened, but the builder checks it.

### 2.4 Layer 4 — BND4

A standard FromSoftware archive: 194 entries, 36-byte entry headers starting at `0x40`, entry data stored uncompressed and 16-byte aligned. We only ever need to **replace the data of an existing entry by data of the same length**, which keeps every offset and size field valid. (`tools/erlib.py: Bnd4`)

The tables used in this book:

| Entry | Rows | Row size | Bytes | Position in body | 64 KiB blocks touched |
|---|---|---|---|---|---|
| `EquipParamGoods.param` | 2,329 | 176 | 465,889 | 27,925,504 | 426–433 |
| `Magic.param` | 317 | 168 | 60,947 | 33,773,392 | 515–516 |
| `SpEffectParam.param` | 11,354 | 912 | 10,627,431 | 41,305,456 | 630–792 (row *index* in 630–634, row *data* up to 792) |
| `ShopLineupParam.param` | 1,296 | 52 | 98,582 | 41,146,416 | 627–629 |
| `BulletParam` (`Bullet.param`) | 15,475 | 272 | 4,580,684 | 21,811,904 | 332–402 |
| `SpEffectVfxParam.param` | 1,513 | 164 | 284,535 | 51,949,072 | 792–797 |

## Chapter 3 — PARAM files

### 3.1 Layout (Elden Ring, verified against our own rebuilds)

```
0x00  u32  strings_off            where row names / type string begin (end of the row data)
0x0A  u16  row_count
0x10  u64  type_name_offset       (points into the strings area)
0x30  u64  data_start             always 0x40 + 24 * row_count
0x40  row descriptors, 24 bytes each:  i32 id | u32 0 | u64 data_offset | u64 name_offset
...   row data, row_size bytes each, back to back (same order as the descriptors)
...   strings area (UTF-16 names + type string), copied as is
```

Rules we rely on (all asserted by `erlib.Param`):

- descriptors are **sorted by id**; the game looks rows up by binary search, so a relabelled row must be moved to its sorted position;
- every row of one table has the same size; row *i* of the data corresponds to descriptor *i*;
- `Param.build()` of an unmodified table reproduces the original bytes exactly (self-test step 3).

### 3.2 Field definitions come from Paramdex

The meaning and offset of each field is defined by the community's **Paramdex** (`ER/Defs/*.xml`). `tools/erdefs.py` turns one XML file into `(name, type, byte offset, bit position, bit width)` and offers `get(row, name)` / `set(row, name, value)`. We used commit `ff7245e5…` (2026-03-06). Table → definition file:

| Table | Paramdex file |
|---|---|
| Goods | `EquipParamGoods.xml` |
| Magic | `MagicParam.xml` |
| SpEffect | `SpEffect.xml` |
| Bullet | `BulletParam.xml` |
| Shop | `ShopLineupParam.xml` |
| SpEffect VFX | `SpEffectVfx.xml` |

⚠️ Paramdex field *names* are community-chosen and sometimes wrong or vague. Everything in Appendix A that is marked "(inferred)" is a best reading, not documentation.

### 3.3 The "dummy" rows (the trick that makes everything small)

At the end of several tables sit rows that the game never uses. We found them by looking at the last few ids of each table:

| Table | Last real id | Dummy row(s) at the end |
|---|---|---|
| Goods | 2,220,010 | `999999999` |
| Magic | 2,050,090 | `999999999` |
| SpEffect | 21,950,011 | `999999999` |
| Bullet | 400,000,002 | `999999998`, `999999999` |
| Shop | 9,001,004 | `9999001`, `9999002` |

All of them have `disableParam_NT = 1` (or, in tables without that field, are all-default rows). Because they are **already last in sorted order**, giving one of them a new id that is *greater than every real id* leaves the table sorted and the same length. No row is inserted, nothing shifts, no other table moves. This is the foundation of the whole method; it is also its main limitation (Section 17.1): each table only has one or two dummies.

For the Shop table the new id is *smaller* than the dummy ids (a gap line such as `100508`), so the row is relabelled and then **re-sorted into place**; descriptors and row data between the old and new position shift by one slot, but the table's total size is unchanged (Section 11.6).

---

# Part II — How an incantation is wired together

## Chapter 4 — The tables and the chain between them

A spell the player can buy, memorise and cast is not one row; it is a **chain** of rows in five tables. Ids are the glue.

```
 Shop line ──equipId──▶ Goods row ══same id══ Magic row ──refCategory1/refId1──▶ SpEffect row
 (ShopLineupParam)      (EquipParamGoods)     (MagicParam)        │                (the buff / effect)
                        goodsType 18 =                            └─▶ Bullet row ──spEffectId0──▶ SpEffect
                        "incantation"                                 (projectile, optional)
```

| Table | Role | Link out |
|---|---|---|
| **ShopLineupParam** (Shop) | One line of a merchant's stock: which item, what price, how many, which event flag remembers "sold out" | `equipId` = Goods id (with `equipType = 3` meaning "goods") |
| **EquipParamGoods** (Goods) | The *inventory item*: type, icon, stack size, sort order, "can be stored" flags. `goodsType = 18` makes it an incantation | **same id** as the Magic row (its `refId_default` stays `-1`) |
| **MagicParam** (Magic) | The *spell*: FP and stamina cost, attribute requirements (`requirementFaith`), cast animation type, cast sound/visual ids | `refCategory1` + `refId1`: 0 = attack row, **1 = Bullet row**, **2 = SpEffect row** |
| **BulletParam** (Bullet) | A projectile / area object spawned by the spell | `spEffectId0…` = SpEffect applied on hit/spawn |
| **SpEffect** | The actual *effect on a character*: damage multipliers, HP/FP/stamina changes per tick, duration, buff icon, visual effect id | `vfxId` → **SpEffectVfx** row (particles/effects), `cycleOccurrenceSpEffectId` → another SpEffect run every tick |

The rule "**Goods id = Magic id**" is the single most important wiring fact. Goods row 6421 (*Heal*) and Magic row 6421 are the same spell seen from two sides (the inventory side and the casting side).

### 4.1 Rows we studied as templates

| Template | Goods/Magic id | What it is | Why we used it |
|---|---|---|---|
| *Heal* (vanilla incantation) | 6421 | Cast → projectile → heals | Gave us the working healing numbers and the **flask-like glow** (SpEffect `1642100`, `vfxId` 5030) |
| *Flame! Grant Me Strength* | Magic 6050 → SpEffect `1605000` | Self-buff incantation | A **direct Magic→SpEffect** spell (no Bullet), plus the cast animation and effects we want to copy |

⚠️ Magic row 6050 has `disableParam_NT = 1`, yet the spell works in game (we saw SpEffect `1605000` live in `eldendisk read`). **`disableParam_NT` does not mean "dead row".** It only means "disabled in the network-test build". We therefore never use that flag to decide whether a row is safe to repurpose; we rely on the **end-of-table dummy** rows (which have it set *and* are unreferenced).

## Chapter 5 — The three-row self-buff incantation

Heal needs a Bullet row because it *spawns* something. A self-buff does not. A Magic row whose `refCategory1 = 2` applies a SpEffect directly to the caster. That reduces the item to:

| # | Table | Row | Cloned from | What we change |
|---|---|---|---|---|
| 1 | SpEffect | new id `21950111` (relabelled dummy `999999999`) | Heal's SpEffect `1642100` | HP/FP/stamina per tick, duration, tick interval, buff icon, visual |
| 2 | Magic | new id `2230000` (relabelled dummy) | Magic `6050` (Flame! Grant Me Strength) | `mp` (FP cost), `requirementFaith`, `refCategory1 = 2`, `refId1 = 21950111`, `iconId`, `sortId`, `disableParam_NT = 0` |
| 3 | Goods | new id `2230000` (relabelled dummy) | Goods `6421` (Heal) | `sortId`, `iconId` (taken from Goods `6424`, a neighbouring incantation icon) |
| 4 | Shop | new line `100508` (relabelled dummy `9999002`) | Shop line `100507` | `equipId = 2230000`, `value` (price), `sellQuantity`, `eventFlag_forStock`, `equipType = 3` |

### 5.1 The healing numbers

Heal's SpEffect (`1642100`) heals by **`changeHpPoint = −230`**. The sign is the opposite of what the field name suggests.

⚠️ **Negative `changeHpPoint` restores HP; positive hurts.** We first assumed the opposite (the name says "change HP point") and the first design was therefore wrong. The evidence is Heal's own row: it is the vanilla healing spell and it carries `−230`. The same convention holds for `changeMpPoint` (FP) — negative restores.

A **tick effect** is built from three fields:

| Field | Meaning | Our value |
|---|---|---|
| `effectEndurance` | total lifetime, seconds | `15.0` |
| `motionInterval` | seconds between ticks | `0.5` |
| `changeHpPoint`, `changeMpPoint` | applied **per tick** | `−60`, `−4` |
| `staminaRecoverChangeSpeed` | stamina regeneration speed modifier while the effect lasts | `100` |

15 s ÷ 0.5 s = 30 ticks → up to **1,800 HP** and **120 FP** restored over the buff's life; stamina regenerates at the boosted rate. 🔬 *Confidence:* the *direction* and the 15.0 s timer are E3 (seen in game and in `eldendisk read --live-buffs`); the *exact* per-second numbers were not measured, only seen to rise. `staminaRecoverChangeSpeed = 100`'s real unit is inferred.

### 5.2 What differs between a vanilla heal and a vanilla buff (the diff that taught us the cast-style fields)

Direct comparison, `tools/inspect_rows.py`:

**Magic 6421 (Heal) vs Magic 6050 (Flame! Grant Me Strength)** — only 14 of ~130 fields differ:

| Field | Heal | Flame GMS | Reading |
|---|---|---|---|
| `refCategory1` | 1 (Bullet) | 2 (SpEffect) | what the spell triggers |
| `refId1` | 10642100 | 1605000 | the target row |
| `refType` | 34 | 31 | cast style / behaviour class (inferred) |
| `castSfxId` / `fireSfxId` / `effectSfxId` | 525000 / 525001 / 525004 | 524400 / 524401 / −1 | cast and fire visual/sound effects |
| `subCategory1` | 0 | 21 | spell sub-class (inferred) |
| `mp` / `stamina` / `requirementFaith` | 32 / 35 / 12 | 28 / 16 / 15 | costs and requirement |
| `iconId`, `sortId`, `aiUseJudgeId`, `disableParam_NT` | … | … | cosmetic/AI/flag |

**Goods 6421 vs Goods 6050** differ only in `sortId`, `iconId`, `sortGroupId` and the NT flag. So *all* spell behaviour lives in the **Magic** row; the Goods row is just the inventory shell.

**SpEffect 1642100 (Heal) vs 1605000 (Flame GMS)** — the differences that matter for "how a buff behaves":

| Field | Heal | Flame GMS |
|---|---|---|
| `effectEndurance` | 0 (instant) | 30.0 s |
| `motionInterval` | 0 | 0.06 |
| `changeHpPoint` | −230 | 0 |
| `spCategory` | 10 | 151 |
| `isExtendSpEffectLife` / `isContractSpEffectLife` | 0 / 0 | **1 / 1** |
| `effectTargetFriendlyTarget` | 0 | 1 |
| `vfxId` | 1642100 | 1605000 |
| `iconId` | −1 | 20406 (buff icon) |
| damage multipliers (`atk…CorrectRate_*`), `magParamChange`, `miracleParamChange`, `shamanParamChange` | 1.0 / 0 | 1.15–1.20 / 1 |

We copy only the *behaviour/visual* fields (`vfxId`, `isExtendSpEffectLife`, `isContractSpEffectLife`) from Flame GMS and **none of its damage bonuses**.

### 5.3 What the buff row's id is called in telemetry

Elden-Disk's `read --live-buffs` lists active SpEffects by id, using `code/chr_state_ids.json` to give names. The mapping key **is the SpEffect id**, not the goods id:

```json
"21950111": {
  "name": "Reverse Curse Technique",
  "categories": "INCANTATIONS",
  "abilities": "Regenerates HP, FP and stamina over time for 15 s (custom spell, goods/magic id 2230000)."
}
```

If you change `--sp-id` when building, update this key too. (In the X1 test the id was still `999999999`, which the tool printed as `Unknown` — a good reminder.)

## Chapter 6 — The case study: Reverse Curse Technique

### 6.1 The requested design

*"A new incantation with a configurable Faith requirement. On use it regenerates HP, FP and stamina until full, then ends. It sits in the inventory directly. Using it plays the visual effect of drinking a flask once."* Later refinements: sold by a merchant; price 8,990 runes, stock 1; cast animation and effects copied from *Flame! Grant Me Strength*; re-casting should behave like that spell.

### 6.2 The configuration actually built (defaults of `tools/make_item.py`)

| Setting | Value | Table.field |
|---|---|---|
| Goods/Magic id | `2230000` | key of both rows |
| SpEffect id | `21950111` | key of the buff row |
| Faith requirement | 20 | Magic `requirementFaith` |
| FP cost | 30 | Magic `mp` |
| Stamina cost | 0 | Magic `stamina` |
| HP / FP per tick | −60 / −4 | SpEffect `changeHpPoint` / `changeMpPoint` |
| Stamina regen modifier | 100 | SpEffect `staminaRecoverChangeSpeed` |
| Tick / duration | 0.5 s / 15.0 s | SpEffect `motionInterval` / `effectEndurance` |
| Buff icon | 20411 | SpEffect `iconId` |
| Spell icon | 4036 | Magic `iconId` |
| Cast style | cloned from Magic 6050 | whole row |
| Visual on the body | Flame's `vfxId 1605000` (`--flask-vfx` keeps Heal's 5030) | SpEffect `vfxId` |
| Shop line | `100508`, price 8,990, stock 1, flag `150080` | Shop |

### 6.3 What we observed in game (first full build, X1)

> 📌 **Case File — user's report after test X1**
> 1. *Buy:* works; runes decrease by the price.
> 2. *Memorise:* it can be placed in a memory slot.
> 3. *Cast:* a **kneeling animation** plays, the **flask-style glow** appears, a **buff icon** shows in the status bar and **HP, FP and stamina rise for 15.0 s**. The spell can be cast again; on a re-cast the **animation plays but the glow does not play a second time**.

That last line is why Y1/Y2 clone the Flame row: its `isExtendSpEffectLife`/`isContractSpEffectLife` flags and cast-effect ids decide how a re-cast is shown. 🔬 *Confidence:* that those two flags are what refreshes the effect is a **hypothesis (E0)** until Y1/Y2 are tested.

## Chapter 7 — Shops: finding the right line (a detour worth reading)

Shop lines are not named. A merchant sells every line whose id falls inside the range its dialogue script passes to the "open shop" call. Two facts cost us several test files:

1. **Lines `100000–100026` are not the merchant we were looking at.** We had assumed they were *Kalé* (Church of Elleh); we never confirmed which NPC owns which range. The merchant in the user's screenshot sold items with prices 40, 500, 1000, 300, 20 …; we searched `ShopLineupParam` for that price signature and it matched **lines `100500–100524`** (arrows 20/40, chain-armour set 1000/1500/1000/1000, a club for 200, a shield for 600). Tests V1b, V1c, V1d and W1 all edited the *wrong group*, so they could not show up — and W1 (set every price of the wrong group to 7) correctly showed **no change**.
2. After editing the right group (test X1, line `100502`), the item appeared immediately, together with the prices set to 7, proving the game uses our file.

> 📌 **Case File — how to identify a merchant's lines from a screenshot**
> A short script over `ShopLineupParam` grouped the table into blocks of 25 ids and counted how many of the on-screen prices occurred in each block. The signature is *not unique* (two groups contained all eight distinct prices), so the decision rested on structure: group `100500` contains Throwing Dagger (goods `1700`) at **40**, arrows at **20** and **40**, a four-piece armour set priced **1000 / 1500 / 1000 / 1000** (armour ids `11000xx`) and a club at **200**, which is exactly the screenshot. Test X1 then confirmed it.

Useful field facts for a shop line:

| Field | Meaning | Notes |
|---|---|---|
| `equipId` | Goods/weapon/armour id | |
| `equipType` | 0 weapon, 1 armour, 3 goods | our item: 3 |
| `value` | price in runes; `-1` = use the item's own sell value | |
| `sellQuantity` | stock; `-1` = unlimited | with a finite stock the line **must have its own `eventFlag_forStock`** or the game cannot remember the sale |
| `eventFlag_forStock` | save-file flag set when stock is exhausted | vanilla pattern for most lines of this group: `150000 + (line − 100500) × 10`; we use `150080` for line `100508` |
| `eventFlag_forRelease` | flag that must be set before the line appears | `0` = always |
| `mtrlId` | crafting-material cost | `-1` = none |

**Which line to use?** Test X1 *replaced* a real merchandise line (`100502`, goods id `9300`, 500 runes, stock 1). The final design relocates the item to the unused id `100508` (a gap in the merchant's range, so an existing player-visible item is not removed) by relabelling the **Shop dummy** `9999002` and re-sorting. 🔬 *Confidence:* that `100508` is inside the merchant's scripted range is an inference from the neighbours `100507` and `100510` (both sold); **it is a Y-test pending result.**

---

# Part III — The experiments (lab notebook)

## Chapter 8 — How we tested

### 8.1 The loop

```
 build file (offline, in the sandbox)
   → verify offline (E1): decrypt → unzstd with libzstd == intended body, and our own decoder agrees
   → copy into the Elden-Disk vault folder  vault\regulation\regulation.<TAG>.bin
   → the project owner swaps it in as the game's regulation.bin, starts the game (offline), and loads a character
   → reports: PASS (world loads, playable) / FAIL (symptom) — failures repeated up to 3 times
```

Every file is **named with a short tag** (`J6`, `K5`, `U32`, …). Tags are used in all tables below. The tag letter is the *question* being asked; the digit is the variant.

### 8.2 Symptoms and what they mean

| Symptom | Where it appears | What we concluded |
|---|---|---|
| *Hang / "not responding" / process exits* | on launch, before the title screen | the game's regulation loader choked (early failures: A, C2, C3, C5, G3, J7) |
| ***"Failed to save game. Save data is corrupted. Select OK to try again."*** (OK / CANCEL) | on the **title screen**, game does **not** crash | the file was *read* but rejected at a later check; deterministic — retrying 3× never changed the outcome |
| Title → character → world loads, playable | — | PASS (E2) |

⚠️ The corrupted-save dialog is misleading. Forum posts attribute it to "a mod's `regulation.bin` not matching the game version". In our case the offending files contained **byte-identical decoded params to the original game** (the no-op tests K4, S6, S8, S10). So the dialog does not prove a content or version problem.

### 8.3 Offline checks before sending any file (all in `tools/`)

1. libzstd decodes the new frame to **exactly** the intended 54,111,776-byte body.
2. Our own pure-Python decoder (`zdec.py`, validated against libzstd on the whole original frame) decodes it to the same bytes — and it can be told to simulate other decoder semantics.
3. Only the intended param tables differ from the original; inside them, only the intended rows/bytes differ.
4. The padding shape (Section 10.4) matches the original.

## Chapter 9 — Phase 1: what does the loader accept? (container-level tests)

**Question:** can we change the file *at all*? Start with content that is identical to the original and vary only the packaging.

| Tag | Packaging | Decoded content | Result | Takeaway |
|---|---|---|---|---|
| **A** | whole body re-compressed with libzstd | unchanged | ❌ hang | "the same params, recompressed" is not accepted |
| **C1** | the **original frame, byte for byte**, only a new random IV | unchanged | ✅ | AES layer fine; a fresh IV is fine |
| **C2** | new libzstd frame *shaped like the original* (no content size, no checksum, 64 MiB window), level 6 | unchanged | ❌ | matching the frame *header* shape is not enough |
| **C3** | libzstd frame cut into 64 KiB blocks | unchanged | ❌ | |
| **C5** | C3 + exactly 2 bytes of zero padding like the original | unchanged | ❌ | |
| **E3** | original frame; **one byte of the frame header changed** (window descriptor `0x80 → 0x81`) | unchanged | ✅ | the loader does not hash the frame; a different window size is tolerated |
| **E7** | original frame; **one block (#16) re-stored raw** (uncompressed) | unchanged | ✅ | stored blocks *can* be accepted |
| **F1** | original frame; Magic-table blocks stored raw (+ block 3, a dependent) — "all spells cost 1 FP" | edited | ✅ (loaded) | an edit via splicing works at least once |
| **G2** | first full item (v0): new rows added to five tables, which were **moved to the end of the archive** with the BND4 entries repointed; a shop line added | edited | ❌ | table moves + stored blocks |
| **G3** | the same item **in place** (no growth) | edited | ❌ hang | |
| **H0** | 16 zero bytes appended after the last BND4 entry (nothing points there) | unchanged | ✅ | growing the body by itself is not rejected |
| **H1** | the five tables re-appended unchanged at the end, entries repointed to the copies | unchanged | ❌ | |

(Tests B and B2 — "Heal costs 1 FP", "every spell costs 1 FP" — were built with the same libzstd packaging as A; they were superseded by F1.)

### 9.1 What Phase 1 told us

- **The original frame is sacred.** Anything that keeps the original frame (C1, E3, E7, H0, F1) can pass; every wholesale libzstd re-encoding failed, whatever its parameters.
- The AES key and the DCX header handling are right.
- **Stored (raw) blocks are tolerated at least sometimes** (E7, F1). That suggested the *splice method* (Chapter 10), which looked like the answer for almost 50 tests.
- 🔬 We later learned (Chapter 10–11) that G2/G3/H1 probably failed for the *same reason as everything else with stored blocks*, not because of table growth; **table growth has not been re-tested with the final method** (open problem 17.1).

## Chapter 10 — Phase 2: the splice method and the stored-block problem

### 10.1 The splice method

If the game only trusts its own compressed blocks, then keep them: copy the original frame, and for each 64 KiB output block whose bytes changed, **store that block raw** (zstd block type 0: header + the plain bytes). Everything else is untouched.

*Complication — the cascade.* A raw block does not leave behind the **repeat-offset registers** (and, if it carried the tree, the **Huffman tree**) that the original compressed block left. The next original block was compressed assuming those, so it now decodes to garbage at its first repeat-offset code. The fix: also store the *next* block raw, then check again, until a standard decoder reproduces the target. 729 of the 826 blocks can be stored on their own (closure of size 1); blocks 0–2 and some runs (e.g. 318–323, 332–338) drag neighbours along. This was verified: the cascade is caused by lost *state*, not by matches into changed data.

The final frame must also hit the original's **2-byte tail** (10.4), which needed a trick: cut one stored block into up to 16 stored pieces to adjust the length instead of adding more stored blocks (`SplitSplicer`).

### 10.2 Table-level bisection (J, L, M, Q, R)

We took the complete item and tried to find which table broke the load.

| Tag | What was edited | Stored blocks | Result |
|---|---|---|---|
| **J1** | Goods: a plain clone row inserted at a sorted position (rows shift) | {3, 426, 428–433} | ❌ corrupted save |
| **J3** | Magic: plain clone inserted | {3, 515–516} | ✅ |
| **J6** | Goods: end-dummy relabelled (no shift) | {3, 426} | ✅ |
| **J7** | J6 + six "identity" Goods fields set (`goodsType`, `maxNum`, …) | {3–15, 426, 433} | ❌ (game terminated) |
| **J8 / J9** | J6 + the other fields / all of Heal's fields | {3–15, 426, 433} | ❌ |
| **J10** | the complete item *except* Goods content | {3–5, 338, 402–405, 426, 515–516, 634, 792–793} | ❌ |
| **L1** | complete item (Goods, Magic, Bullet, SpEffect), in place, no shop | large | ❌ |
| **L2** | L1 + shop line | large | ❌ |
| **Q1** | Goods with all of Heal's values, tail tuned by `SplitSplicer` | {426, 433} | ✅ |
| **Q2** | Goods `weight` only | {426, 433} | ✅ |
| **Q3 / Q4** | L2 / L1 repacked with the better padding | {338, 402–405, 426, 433, 515–516, 634, 792–793} (+ {628–629} for Q3) | ❌ |
| **R1–R6** | one table each, real values, tuned: Magic, SpEffect {634, 792–793}, Bullet {338, 402–405}, Goods {426, 433}, Shop {628–629}, Goods+Magic {426, 433, 515–516} | as listed | ✅ for R2, R3, R5, R6 (R1, R4 were not reported separately; R6 is their union) |

*Reading:* **every table, edited alone, loads**; the **union of the same edits does not** (Q4 = R3 ∪ R6 ∪ R2 fails although R3, R6 and R2 each pass). That cannot be a content problem. The next step was to test stored blocks **with no content change at all**.

### 10.3 No-op stored-block tests (K, S, T)

Decoded body identical to the original; only *which blocks are stored raw* varies.

| Tag | Stored blocks (original numbering) | Total size | Result |
|---|---|---|---|
| **E7** | {16} | — | ✅ |
| **K5** | {332–338} (7 consecutive) | 2.44 MB | ✅ (repeated twice, same) |
| **K4** | {318–323} (6 consecutive) | — | ❌ (repeated twice, same) |
| **K2** | {2–33} | — | ❌ |
| **S6** | {15, 75, 135, 195, 255, 315} (six *isolated* blocks) | 2.42 MB | ❌ ×3 |
| **S8** | {49, 109, …, 469} (eight isolated) | — | ❌ ×3 |
| **S10** | {59, 119, …, 599} (ten isolated) | — | ❌ ×3 |
| **T1a** | {426, 433, 515, 516, 792, 793} — the *real item*, three tables, no Bullet | — | ❌ |
| **T1b** | T1a + {628, 629} (Shop) | — | ❌ |

**The key surprise:** S6 (2.42 MB, six isolated stored blocks) **fails**, while K5 (2.44 MB, seven stored blocks) **passes**. Neither size nor number of stored blocks separates them.

### 10.4 The "2 trailing bytes" shape

The original file is `IV + header + frame + 2 zero bytes`: the AES layer pads to 16, so the **frame length is ≡ 14 (mod 16) minus the header**. Our early builds ignored this (tests P1–P3, "nopad", were built but never sent). From Q onward every file reproduces the exact `2 trailing zero bytes` shape. We have **never shown that this is required**; every U/V/W/X/Y file keeps it as a precaution. When an edit changes the frame length, we nudge the length back with a free, harmless knob (Section 11.4).

### 10.5 Hypotheses we eliminated

| Hypothesis | Why it is dead |
|---|---|
| "Inserting/relabelling a Goods row corrupts the table" (from J1) | K4, S6, S8, S10 are **pure no-ops** and fail |
| "The game caps the number or total size of stored blocks" | S6 (6 blocks, 2.42 MB) fails; K5 (7 blocks, 2.44 MB) passes |
| "The game's decoder resets rep-offsets / FSE / Huffman state after a stored block" (a non-standard decoder) | We simulated eight state-reset variants in our decoder; none reproduces the observed passes **and** fails (F1, J3, J6 pass; K4 fails) |
| "Regulation version mismatch" (forum explanation of the dialog) | the no-op files decode to the original's exact bytes |
| "The file was corrupted in transit" | SHA-256 matched on both sides |
| "The content (values) is invalid" | no-op files have no new content |
| "Hash/integrity check over the whole compressed frame" | E3 (one changed header byte) and many stored-block files pass |

🔬 **Where that leaves us:** *the game rejects some frames that contain stored blocks, accepts others, and the rule is not size, count, content or standard decoder state.* We never found the rule. We found something better: a method that avoids stored blocks completely.

## Chapter 11 — Phase 3: compressed blocks only (the method that works)

### 11.1 The turning experiment

If *stored* blocks are the poison, rewrite the same blocks as **compressed** blocks. The simplest compressed block we can write without a full encoder is: *raw literals + the original sequence section, byte for byte* (the sequence section is where the matches live; raw literals only change the literal bytes' representation).

| Tag | Blocks rewritten | As | Result |
|---|---|---|---|
| **U6** | the **same six blocks as S6** | compressed (raw literals + original sequences) | ✅ |
| **U32** | the **same 32 blocks as K2** | compressed | ✅ |

K2 and S6 failed as stored blocks; as compressed blocks they pass. **That was the first reliable win in about fifty tests.** (`tools/make_u_noop.py` builds these; `tools/legacy_raw_noop.py` builds the failing twins S6/K2-style so you can verify the contrast yourself.)

### 11.2 What the block rewriter must preserve

A rewritten block is *a different compressed block that decodes to the new bytes and leaves the decoder in the same state as the original block did*. Three pieces of cross-block state exist; we handle each:

| State | Who depends on it | How we keep it identical |
|---|---|---|
| **Repeat offsets** (`rep0, rep1, rep2`) | the next original block's first repeat-offset codes | the new block must **end in the same `(rep0, rep1, rep2)`** as the original block — solved by a small dynamic programme (11.3) |
| **Huffman tree** | following blocks with *treeless* literals (type 3) | we write **raw literals** (type 0), which do not touch the tree; and, if the replaced block had *created* the tree (type 2), the treeless blocks that follow it are also rewritten with raw literals |
| **FSE sequence tables** | nothing across blocks (the original uses fresh or predefined tables per block) | nothing to preserve |

### 11.3 Re-segmenting a block (`tools/reencode.py`)

For a block whose output bytes changed:

1. **Parse** the original block into its sequences `(literal_length, match_length, offset)` and note, for every sequence, whether its offset was coded explicitly or as a repeat code (`tools/seqparse.py`).
2. **Walk the old matches.** For each old match with offset `off` covering `[ms, me)`, keep the **maximal runs of at least 3 bytes** where `new[j] == new[j − off]` — i.e., where copying with that offset still gives the *new* bytes. Everything else (including the changed bytes) becomes literals. A match fully intact is kept as is; a damaged one is shortened, split, or dropped.
3. **Choose offset codes with a DP.** The state after each sequence is `(rep0, rep1, rep2)`. For a sequence that needs offset `X` with literal length `ll`, the options are: an **explicit** offset (always valid; pushes `X` onto the registers) or any repeat code 1–3 whose resolved offset equals `X` (with the zero-literal-length shift of the format). We run a forward pass over reachable states with back-pointers and **require the final state to equal the original block's final state**; pick any path that reaches it. In all our builds a path existed.
4. **Encode the sequences** with our own FSE encoder (`tools/fse.py`): for each of the three symbol streams — literal-length code, offset code, match-length code — normalise counts to a power-of-two table (≤ 2⁹ for literal/match lengths, ≤ 2⁸ for offsets), write the normalised-count header, compute the state chain **backwards** (every symbol has a unique predecessor state whose range contains the next state), and emit the bit stream in reverse read order with a final `1` sentinel bit. We use the same modes the original uses for 806 of 826 blocks: **FSE-compressed tables, no RLE, no "repeat" mode**.
5. **Literals** are written raw (type 0); the block header is `size << 3 | (2 << 1) | last`.
6. **Verify:** libzstd must decode the whole frame to exactly the new body. If a *later* block now mis-decodes (it copied bytes from a changed region), that block is added to the edit set and the loop repeats. (It never triggered on our edits.)

> 📌 **Case File — encoder round trip**
> `tools/selftest.py` encodes the real sequences of blocks 3, 100, 426, 433 and 515 with our encoder and decodes them with the independent decoder: identical. Our sequence sections come out within about 1% of the original's size (e.g. block 3: 1,458 vs 1,455 bytes; block 433: 2,654 vs 2,648).

### 11.4 Hitting the original file shape

Replacing a block with *raw literals* makes it larger (a few KB each), so the frame grows (our first complete item V1a: 2,057,826 bytes of frame vs 2,045,634 originally). The DCX header's compressed size is updated, and the 2-byte tail shape is restored using a **free knob**: the *literal size header* of a raw-literals section may legally be written in a longer form (1, 2 or 3 bytes); we re-emit some *unchanged raw-literal blocks* in a longer form, which adds a handful of bytes. U6 and U32 already used this knob and passed, so the game tolerates it.

### 11.5 First complete items

| Tag | What | Result |
|---|---|---|
| **V1a** | Goods + Magic + SpEffect (SpEffect still on id `999999999`), no Bullet, no shop — compressed blocks {426, 433, 515, 516, 792} + treeless follower 793 | ✅ |
| **V1b** | V1a + shop line `100026` at 4,444 runes | ✅ loads; **item not visible in any tab** |
| **V1c** | shop line `100002` (a live line of the wrong group) | ✅ loads; not visible |
| **V1d** | line `100026`, original stock flag kept | ✅ loads; not visible |
| **W1** | every price of lines `100000–100026` set to 7 | ✅ loads; **prices unchanged in the shop he opened** |
| **X1** | the item in line `100502` of the **`100500–100524` group**, other prices of that group set to 7 | ✅ item **visible**, buy / memorise / cast all work (E3) |
| **Y1 / Y2** | cast style cloned from Flame! Grant Me Strength; price 8,990, stock 1, line `100508`; Y1 = Flame vfx, Y2 = flask glow vfx | built and verified (E1); **results pending** |

V1b–d and W1 are the "wrong merchant" mistake of Chapter 7, not a loading problem: in every case the file loaded.

### 11.6 Why relabelling a Shop row needs a re-sort (and why it is cheap)

The new shop line `100508` is relabelled from the dummy `9999002`, but the table is **sorted by id**, so the row has to move from the end to the middle. All descriptors and data rows between the new position and the end shift by one slot (24 and 52 bytes). The table's total length is unchanged, nothing outside the Shop table moves, and only blocks 627–629 change. That is why we can add a line anywhere without growing the file.

---

# Part IV — Reproduce it yourself

Everything below was executed from a clean directory with the files in `tools/` (we did exactly that before writing this chapter: the output of `make_item.py` was byte-identical, after decryption, to the file that was tested in game as Y1).

## Chapter 12 — Setup

### 12.1 What you need

| Need | Notes |
|---|---|
| Elden Ring **1.17.1**, a **copy** of its `regulation.bin` | `<Steam>\steamapps\common\ELDEN RING\Game\regulation.bin`. Must be pristine; check the hash below |
| Python **3.10+** | the scripts use `X \| None` annotations |
| `pip install cryptography zstandard` | AES and libzstd (used only to *verify*; the new frame is built by our own code) |
| Paramdex | field definitions: `git clone https://github.com/soulsmods/Paramdex.git` inside `tools/`, then `git -C Paramdex checkout ff7245e5` (the commit we used) |

### 12.2 Folder and files

```
item-customization/
├─ item-customization-handbook.md      ← this file
└─ tools/
   ├─ regulation.orig.bin              ← YOU provide: pristine copy of the game's regulation.bin
   ├─ Paramdex/ER/Defs/*.xml           ← YOU provide: git clone (12.1)
   └─ *.py                             ← provided (Appendix E)
```

Optional environment variables (defaults in brackets): `ER_REGULATION` [`regulation.orig.bin`], `ER_OUT` [`out`], `PARAMDEX_ER_DEFS` [`Paramdex/ER/Defs`].

### 12.3 Check the input

```
python -c "import hashlib;d=open('regulation.orig.bin','rb').read();print(len(d),hashlib.sha256(d).hexdigest())"
```

Expected for 1.17.1: `2045728 766521f9508de3a3532df61c45a1c2d93340f1ff7ed8306ab20df761712ca2ab`. If your numbers differ, **stop**: the offsets in this book (block numbers, table positions) belong to that exact file; other versions need re-derivation (all scripts compute positions at run time, but results are only proven for this build).

### 12.4 Self-test (no game needed)

```
python selftest.py
```

Expected tail:

```
4. pure-Python zstd decoder reproduces the whole body
5. FSE sequence encoder round-trips on 5 real blocks
ALL OK
```

(Steps 1–3 print the container checks: decrypt + unzstd, BND4 rebuild byte-identical, every parsable `.param` table rebuilds byte-identical.) If step 1 fails with *"AES key / file is wrong"*, the input is not a plain `regulation.bin`.

`python inspect_frame.py` prints the frame census of Section 2.3 and is a good second check.

## Chapter 13 — Build the item

### 13.1 One command

```
python make_item.py --name Z1
```

Expected output (the item with its shipped defaults):

```
blocks whose decoded bytes change: [426, 433, 515, 516, 627, 628, 629, 634, 792]
verified Z1: 2071248 bytes, trailing 2
edited blocks: [426, 433, 515, 516, 627, 628, 629, 634, 792] | converted: [793]
```

Result: `out/regulation.Z1.bin`. Because the IV is random the *file* hash differs each time, but the **decrypted** content is deterministic: the SHA-256 of the decrypted bytes (DCX header + frame + 2 zero bytes) is

```
3dee9f745861bd0b771f225fcc3691022143439a7ec12fe7bff0b01904de8674     (2,071,248 bytes)
```

```
python - <<'EOF'
import hashlib, erreg
d = erreg.decrypt(open("out/regulation.Z1.bin","rb").read())
print(len(d), hashlib.sha256(d).hexdigest())
EOF
```

If you get that hash, your build is bit-for-bit what we built as **Y1** (cast style of Flame! Grant Me Strength, Flame visual, 8,990 runes, stock 1, shop line 100508).

### 13.2 What the script does, step by step

1. `erlib.load_regulation` — decrypt → unwrap DCX/zstd → parse BND4.
2. **SpEffect** — take the dummy row `999999999`; fill it with a copy of Heal's SpEffect `1642100`; overwrite `changeHpPoint`, `changeMpPoint`, `staminaRecoverChangeSpeed`, `effectEndurance`, `motionInterval`, `iconId`, `spCategory = 161`, `stateInfo = 50`, `vfxId`; copy `isExtendSpEffectLife` and `isContractSpEffectLife` from `1605000`; relabel to the new SpEffect id.
3. **Magic** — dummy row filled with a copy of the `--cast-from` row (default `6050`), then `disableParam_NT = 0`, `mp`, `stamina`, `requirementFaith`, `iconId`, `sortId`, `refCategory1 = 2`, `refId1 = <SpEffect id>`; relabel to the item id.
4. **Goods** — dummy row filled with a copy of Heal's `6421`; `sortId`, `iconId` (from Goods `6424`); relabel to the item id.
5. **Shop** — the dummy `9999002` filled with a copy of line `100507`; `equipId`, `value`, `sellQuantity`, `eventFlag_forStock`, `eventFlag_forRelease = 0`, `equipType = 3`; relabel to `--shop-line`; **re-sort** the table by id.
6. Sanity: each new id must be **greater than the last real id** of its table, or the script refuses (the table would become unsorted).
7. `Bnd4.build()` — the new body has the **same length** as the old one.
8. `reencode.build` — find the 64 KiB output blocks whose bytes differ; re-encode exactly those (Section 11.3); convert treeless followers; tune the length (11.4); verify with libzstd; encrypt with a fresh IV; write `out/regulation.<name>.bin`.

### 13.3 Things you can vary (all flags have defaults)

| Flag | Default | What it changes |
|---|---|---|
| `--faith` | 20 | Magic `requirementFaith` |
| `--fp-cost` / `--stamina-cost` | 30 / 0 | Magic `mp` / `stamina` |
| `--hp-tick`, `--fp-tick` | −60, −4 | **negative restores**; per tick |
| `--stamina-regen` | 100 | `staminaRecoverChangeSpeed` |
| `--tick`, `--duration` | 0.5 s, 15.0 s | `motionInterval`, `effectEndurance` |
| `--price`, `--qty` | 8990, 1 | Shop `value`, `sellQuantity` (`-1` = unlimited) |
| `--shop-line`, `--shop-flag` | 100508, 150080 | where it is sold; the flag must be unique (never reuse the flag of another line) |
| `--shop-line 0` | — | do not sell it at all |
| `--cast-from` | 6050 | clone the cast animation / cast effects from another Magic row (`6421` = Heal's kneel) |
| `--flask-vfx` | off | keep Heal's flask glow (`vfxId 5030`) instead of Flame's `1605000` |
| `--item-id`, `--sp-id` | 2230000, 21950111 | new ids; must exceed the last real ids (2,220,010 and 21,950,011) |
| `--buff-icon`, `--magic-icon`, `--sort-magic`, `--sort-goods` | see `--help` | cosmetic |

Examples:

```
python make_item.py --name HardMode --faith 40 --fp-cost 60 --duration 8 --hp-tick -120
python make_item.py --name Heal-like --cast-from 6421 --flask-vfx
python make_item.py --name Free --price 1 --qty -1
```

## Chapter 14 — Install and verify in the game

### 14.1 Install (offline only!)

1. Steam **offline mode**, cloud saves **off**, auto-update **off**, anti-cheat bypassed with the project's offline launcher. Never connect to the online servers with a modified `regulation.bin`.
2. Back up the game's `regulation.bin` and your saves.
3. Put `out/regulation.<TAG>.bin` in place of the game's `regulation.bin` (the project's vault does the swap and restore; a manual copy works too).
4. Start the game offline; load your character.

### 14.2 What to check, in order

| # | Check | If it fails |
|---|---|---|
| 1 | Title screen appears without the corrupted-save dialog | build a different file (Section 16.1); **do not** retry endlessly: the outcome is deterministic |
| 2 | Character loads, world playable | as above |
| 3 | The merchant of the chosen shop group lists the item under *incantations* | wrong shop group/line (Chapter 7); see below |
| 4 | Price and stock as configured; attribute requirement shows `Fai 20` | check the Shop/Magic values with `inspect_rows.py` |
| 5 | Buy → runes decrease; item in inventory; can be memorised | |
| 6 | Cast: animation, effect, buff icon; HP/FP/stamina rise for the configured time | read the buff with Elden-Disk: `eldendisk.exe read --live-buffs` should list the SpEffect id with a timer `x / 15.0 s` |
| 7 | Re-cast: refreshes the timer | note what plays on the re-cast |

**To find which lines a merchant sells** (when step 3 fails): stand at the merchant, screenshot the item/price list, and match prices and item types against groups of 25 ids in `ShopLineupParam` (Chapter 7). Set every price of a candidate group to a silly value (like W1/X1 did) for an unmistakable test.

### 14.3 Read the result from outside

The `read` command of Elden-Disk is the observation tool: it attaches to the running game and prints active SpEffects (`--live-buffs`) or a filtered view (`--query character.buffs.* --live`). That is how we proved the buff existed and ran for 15.0 s without trusting only what the screen showed.

## Chapter 15 — Doing your own edits (the building-block API)

All you need to edit any param table in place and write a loadable file is this (it is `example_all_spells_1fp.py`: every spell costs 1 FP; **E1 verified only — the in-game equivalent F1 was tested with the old splice method**):

```python
import erlib, erdefs
from blockedit import SRC
from reencode import O, build, BS

raw, dcx, body, hdr, bnd = erlib.load_regulation(SRC)
P = erlib.Param(bnd.get("Magic").data)           # find the entry by short name
d = erdefs.Def("MagicParam")                       # Paramdex definition
for row in P.rows:                                 # row = [id, name_offset, bytearray(data)]
    if row[0] < 999999990 and d.get(row[2], "mp") > 1:
        d.set(row[2], "mp", 1)
bnd.get("Magic").data = P.build()                  # same length -> offsets stay valid
nb = bnd.build()                                   # new 54,111,776-byte body

changed = sorted({i for i in range(len(O.body) // BS + 1)
                  if nb[i*BS:(i+1)*BS] != O.body[i*BS:(i+1)*BS]})
build("AllSpells1FP", nb, changed)                 # compressed blocks only; verifies with libzstd
```

Output: `216 spells changed; blocks [515, 516]` and `verified AllSpells1FP: … trailing 2`.

Rules for safe edits:

1. **Keep every table the same length.** Change values, or relabel a dummy. Growing a table moves everything behind it (open problem 17.1).
2. **Keep ids sorted.** A relabelled row must be re-sorted (`P.rows.sort(key=lambda r: r[0])`).
3. **Never store blocks raw.** Always go through `reencode.build`.
4. Use **`d.get` / `d.set` with Paramdex names**; do not poke offsets by hand.
5. Set only the fields you understand; clone a real, working row first (cloning is how the cast animation, the sounds and the icon come for free).
6. After building, always rely on the printed `verified …` line (libzstd decode equals the intended body) before touching the game.

## Chapter 16 — Pitfalls and a triage table

### 16.1 Triage

| You see | Most likely | Do |
|---|---|---|
| *Failed to save game. Save data is corrupted* | the file contains **stored (raw) blocks**, or its frame shape is different from the original's | rebuild through `reencode.build`; never `Splicer` |
| Hang / not responding at launch | a frame re-compressed wholesale by a library | same |
| Loads, but the new item is not in the shop | wrong merchant group or a line outside its range | Chapter 7 |
| Loads, item present but name shows `?GoodsName?` | the text (msgbnd FMG) is not edited | open problem 17.3 |
| Buff icon shows, HP drops | sign error: **negative** `changeHpPoint` heals | Section 5.1 |
| Item "sold out" at once or never sold out | stock flag reused or `0` with a finite `sellQuantity` | give the line its own `eventFlag_forStock` |
| Telemetry prints `Unknown` for the buff | `chr_state_ids.json` key ≠ your SpEffect id | Section 5.3 |

### 16.2 Mistakes we made (so you do not have to)

- **Assumed the sign of `changeHpPoint`** (it is inverted vs. the name).
- **Assumed a merchant's line range** from guesswork (Chapter 7) and lost four test cycles.
- **Chased a size/count theory** for stored blocks (S6/S8/S10) that the next result killed.
- **Designed experiments that changed several things at once** (L1/L2 changed four tables and a shop line, so a failure said nothing). The R-series (one table at a time) and the no-op series (no content change) were the productive designs.
- **Trusted a plausible forum explanation** ("version mismatch") for the corrupted-save dialog; our own no-op files disproved it.

---

# Part V — What is still open, and what comes next

## Chapter 17 — Open problems

### 17.1 More than one item (a supply problem)

The relabel trick uses the **unused dummy rows**, and each table has only one (Goods, Magic, SpEffect) or two (Shop and Bullet) of them. One incantation therefore exhausts Goods, Magic and SpEffect. Options for a second item:

| Option | Status |
|---|---|
| **Grow the tables** (append rows, shift everything behind them, update BND4 offsets and DCX sizes) | **Not re-tested with the final method.** The only attempts (G2, H1) used stored blocks, which we now know fail for unrelated reasons. This is the first thing to retry. 🔬 E0 |
| **Repurpose an unused real row** (a row no shop, drop or script references) | Needs a trustworthy "unused" detector; `disableParam_NT` is *not* one (6050 has it set and is live) |
| **Overwrite one item with several variants** | Works today but costs an existing item |

**Measurements (2026-10-09, 1.17.1 original, decoded body 54,111,776 bytes = 826 blocks of 64 KiB).** Goods starts in block 426 (465,889 bytes, 2,329 rows of 176), Magic in 515 (60,947; 317 x 168), Shop in 627 (98,582; 1,296 x 52), SpEffect in 630 (10,627,431; 11,354 x 912). Inserting a row in place re-encodes every block behind it, about 400 from Goods on (tested so far: at most 11). Moving only the three small tables to the end of the body (copies appended, entries repointed, old copies left) changes the header block and about 11 new blocks. SpEffect is too big to move (about 162 blocks). Row names are not stored in the file (the strings area of each table holds only the table's type name), so "unused" rows cannot be found from the file. The merchant's range 100500-100524 has 7 free lines: 100508 (used), 100509, 100512, 100521-100524. Plan and first test: spec 1.7.0 section 10b.

### 17.2 What exactly does the game dislike about stored blocks?

Known: every failing file had stored blocks; every compressed-only frame passed (8/8 built with our method). Unknown: the rule that makes {332–338} pass but {318–323} fail. Not size, not count, not content, not standard decoder state (10.5). A plausible class of explanation — *the game decodes with its own bespoke zstd decoder that mishandles stored blocks in some alignments* — fits the data but is untested. **We do not need the answer to build items,** only to avoid the trigger.

### 17.3 Name and description text (the UI layer, part 1)

**Solved in 1.7.1, for the session — see Chapter 19.** The game showed `?GoodsName?`/`?GoodsInfo?` because there is no text for the new Goods id. The text lives in FMG string tables inside `msgbnd.dcx` archives inside `Data0.bdt`; a loose copy of the archive is not read by the unpatched game, so the text is put into the running game's memory instead. What stays open: a permanent file change (not needed), other scripts such as Thai (the font is untested) and other game languages.

### 17.4 A custom image (the UI layer, part 2)

Today the item re-uses existing icon ids (`4036` for the spell, goods icon from `6424`). A truly new picture means editing the menu-icon texture archive and the icon-atlas layout that maps an `iconId` to a rectangle. Not started.

### 17.5 "Directly in the inventory"

Params alone do not grant items; they describe items. Candidate ways (E0, none tried): (a) put the item into a **starting-gift / item-lot** row so it is delivered by an event the player will hit anyway; (b) make a merchant line that is **free and stocked 1** (already supported: `--price 1 --qty 1`); (c) use an event script. Option (b) is the only one inside the "params only" boundary of this book.

### 17.6 "Restore until full, then stop"

Today the effect lasts a fixed 15 s. SpEffect rows carry HP-ratio fields (`conditionHp`, `conditionHpRate`, `maxHpRate`, `changeHpRate`) and a per-tick follow-up effect (`cycleOccurrenceSpEffectId`), which suggest a design where the tick effect only acts while HP is below its maximum. Untested (E0).

### 17.7 Visual effects and colour

Current state: cast style and effects are cloned from *Flame! Grant Me Strength* (Y1/Y2 pending). A *different colour* means borrowing the effect ids (`castSfxId`, `fireSfxId`, SpEffect `vfxId`) of a spell that already has that colour (for example a black-flame or golden-effect spell) rather than recolouring particles. Test after Y1/Y2 tell us which of the three ids produces which visible part.

### 17.8 Re-cast behaviour

Hypothesis: `isExtendSpEffectLife` / `isContractSpEffectLife` (both 1 on Flame GMS, both 0 on Heal) make a re-cast refresh the effect and replay its visual. Tested by Y1/Y2.

## Chapter 18 — Roadmap

| Step | Goal | Method | Risk |
|---|---|---|---|
| 1 | Close the loop on Y1/Y2 (cast style, re-cast, price, stock) | in-game test | low |
| 2 | Add text (name, description) | ✅ 1.7.1: not by the archive but by a rebuilt table in the game's memory (Chapter 19) | done |
| 3 | Retry table growth with compressed blocks only → more items (first test: move the Goods table to the end, see 17.1) | `reencode` + a table-growing `Bnd4` | medium |
| 4 | "Until full" logic | SpEffect conditions | medium (unknown fields) |
| 5 | Visual variants and colour | borrow ids; compare | low |
| 6 | Custom image | texture archive | high |
| 7 | Generalise `make_item.py` into a recipe/config format for many items | done for one item: Elden-Disk `spells.design.json` (spec 1.7.0); several items wait for step 3 | low |
| 8 | Spells of every kind (clone, buff, enchant, projectile, attack) in up to 64 slots | Phase 1 (live read/write of six tables, check against the build) is done; Phase 2 is planned in [roadmap-innovate-spells.md](../experiments/extensional/innovate-items/spell/level2/docs/roadmap-innovate-spells.md) | medium |

---

# Part VI — Level 3: text in the game

## Chapter 19 — Name, short line and description of a new item (1.7.1)

### 19.1 Where the text lives

| What | Where |
|---|---|
| The tables | **FMG** version 2 (little endian, 64-bit offsets): ids → UTF-16 strings. `GoodsName` (the name), `GoodsInfo` (the short line, "Item Effect"), `GoodsCaption` (the long description). A spell's text is keyed by its Goods id, which for our slots is `2230000 + slot - 1` (nothing in the game has text for those ids, so they showed `?GoodsName?`) |
| The files | `/msg/engUS/item.msgbnd.dcx` (and `menu`, and the `_dlc01`/`_dlc02` ones): a BND4 inside a DCX (KRAK, the Oodle codec; `oo2core_6_win64.dll` is in the game folder) |
| The archive | `Data0.bdt`, indexed by `Data0.bhd`: a BHD5 index encrypted with RSA (the public keys are embedded in `eldenring.exe`, five PEM blocks, in the order Data0..Data3, DLC); each file is found by a 64-bit hash of its lower-case path (multiplier `0x85`), and encrypted with an AES-128 key (ECB) stored in its index entry |

### 19.2 What did not work, and what was not tried

- **A loose file.** The archive was extracted and rebuilt with the new text (`tools/dump_msgbnd.py` + an edited copy) and placed in `Game\msg\engUS\`: the game showed no change. The unpatched game does not read loose message files (2026-10-11: the first attempt had the files in the wrong folder, the second had them in `Game\msg\engUS` and still showed the old name).
- **Rewriting `Data0.bdt`.** Not tried: it is a very large file the vault would have to guard, and the in-memory method below needs none of that.

### 19.3 What works: a rebuilt table in the game's memory

1. `tools/probe_text.py` (read-only) looked for the dumped `GoodsName.fmg` in the running game's memory. No byte-exact copy existed, but a laid-over comparison (`analyse`) showed that the game keeps **each table as it is in the file, except the 8 bytes at `0x18`** (the position of the string offsets): there the game holds an absolute address (`table base + offsets position`). String offsets inside the table stay relative. **One** 8-byte pointer in the game's memory leads to each table.
2. `tools/patch_text.py` built the table again with new entries (`Fmg.read(original)`, add, `write()`), allocated memory in the game (`VirtualAllocEx`), wrote the new table there (with its own address at `0x18`) and changed the one pointer (one aligned 8-byte write). The old table is untouched; putting the old pointer back undoes it; closing the game removes everything. Tried in the real game: Flame, Grant Me Strength showed "(text test)" and slot 1 in Kalé's shop showed its new name, short line and (Inventory → controller square) long description.
3. **Finding the pointer.** A first scan of all of the game's memory took minutes and made the PC stutter; a fixed chain from the exe (`eldenring.exe + 0x3D61FB8` → an object → `object + 0x1F20 + N * 8`) was found by walking backwards from the pointer and took about a second. But in five runs of the same game the pointer held the right object in three and memory that had been given back and used for something else in two (an FMG groups table, UTF-16 text, whole numbers), so **the chain was dropped**: nothing here follows a fixed address. The pointer to the table of text file number N sits at `array + N * 8` (GoodsName N = 10, GoodsInfo N = 20, GoodsCaption N = 24, checked in the game), and the tool *finds* that array and the tables each time (19.4). Only the numbers N and the sizes of the tables are in the `text` block of the profile in `offsets.json`.

### 19.4 In the tool

| Piece | What |
|---|---|
| `design.json` | each spell's `"text": {"goods_name", "goods_info", "goods_captions"}`, before `set`; 80 / 120 / 1000 characters. It is **not** part of the build (`build_view` leaves it out), so editing a text never rebuilds or un-secures anything |
| `eldendisk/writer/scan.py` | the one way the tool looks through the game's memory (text and fire share it): 1 MB pieces (no single read is long enough to be a frame the game misses), a rest owed as half the time the reading took and slept in lumps of at least 2 ms (so the game keeps its share of the memory bus whatever the speed), an optional `near` (the surroundings of given addresses, 64 MB each way, are read first and not read again), the first 128 MB of each private block of 256 MB or more first and then the rest (biggest first), a stop as soon as the caller has what it wants, a budget of 120 s, an unreadable piece read again in parts of 256 KB. It never writes |
| `eldendisk/writer/text.py` | the memory side, bytes only. **Step A:** find the game's tables by shape (version-2 header, the `1` at `0x08`, the address at `0x18` equal to the table's own base + `0x28` + 16 × the number of groups) and by size (`text.sizes` of the profile). **Step B:** find the pointer to GoodsName, and where one is seen read the other two slots at the distances the file numbers give (`A + 10 * 8`, `A + 20 * 8`, `A + 24 * 8`): three pointers at exactly these distances do not happen by chance. The look starts around the tables (in the logs the array lay within 20 MB of them) and ends at the first whole array; only if there is none does it go through the rest of the memory (written for 1.7.1 after the first measurements; in the run of 2026-10-12 the tables took 1.6 s and the array 0.3 s, 38 MB read in the near tier). Then read the table the game holds, allocate, write the new table, change the pointer, read it back |
| `eldendisk/design/innovate_items/fmg.py` | the FMG reader/writer (stdlib only); `write()` is canonical (4 of 6 real files come back byte-identical; the other two differ in 2 trailing bytes and the size field) |
| `write --text [--wait [SEC] \| --when-loaded]` (`commands/write.py`) | builds the three tables from the design and the game's own tables, skips a table that would not change, switches the pointers (every array found, so a copy the game no longer uses is changed too), checks 3 s later that the game kept them. `--when-loaded` waits until a character has been in the world for 5 s (the loading screens flicker), looks, writes **once** and ends: nothing watches the game afterwards |
| `run` | with the vault ON and a design build swapped in, starts `write --text --when-loaded` (and `write --flame-color --when-loaded`, 19.7) once the record says RUNNING (hook `Hooks.on_running`). Separate processes, so the host still never touches the game's memory; if one fails the game goes on |

Rules that keep it safe: the same session check as every `write`; `VirtualAllocEx` exists only in `writer/writer.py` (the one new allocation; `test_write_capability_is_confined_to_the_writer_package` enforces it); the game's own table is never changed; an empty text removes the entry; an unchanged result allocates nothing.

### 19.5 The research tools (`code/tools/`, a record; not needed to use the feature)

| Tool | Does |
|---|---|
| `dump_msgbnd.py --game <Game folder> --out msgdump` | reads `item`/`menu` (+ DLC) `msgbnd.dcx` out of `Data0-3.bdt` (with `gamearchive.py`), opens the DCX (Oodle through the game's DLL) and the BND4, writes the `.fmg` files and `report.txt`. Writes only to `--out` |
| `gamearchive.py` | the archive reader: RSA index, BHD5, path hash, AES-128 ECB. A library for the tool |
| `probe_text.py` | read-only: finds the dumped table, or its laid-over copy, in the running game and the pointers to it (`--out textprobe.json`) |

(`patch_text.py`, the experiment that first wrote a table into the game, and `probe_chain.py`, which found the fixed chain, are gone: `write --text` does the first and the chain was dropped, 19.3.)

For another game version or language: run `dump_msgbnd.py` (the keys are in that exe); the size of each `GoodsName.fmg`, `GoodsInfo.fmg` and `GoodsCaption.fmg` it writes is the size to put in `text.sizes`; the file numbers N come from the distances between the pointers that `probe_text.py` reports for the three tables.

### 19.6 Results and limits

| Test (real game, 2026-10-11) | Result |
|---|---|
| Rename of an existing item (Flame, Grant Me Strength + " (text test)") in the inventory | ✅ |
| New item in Kalé's shop: name, short line | ✅ |
| New item: long description (Inventory → controller square) | ✅ |
| Fixed chain, a fresh `run` session, patch run by hand | ◦ worked in 3 of 5 runs (19.3): dropped |
| `run` starting `write --text --when-loaded` by itself (3 runs, `run -v` logs of 2026-10-11) | ✅ all three tables found, written and read back in every run. The tables were found in 0.6-0.7 s (176 MB read: the head of the private blocks; they lie about 43 MB into a block of 1530 MB); the one array was about 6 MB before them and was found by a look through all the memory (7.3 GB, 70-73 s, 3 pointers seen, 1 array). The text is in the game about 75 s after the character is in the world |
| Thai or other scripts | ◦ not tried; the game's font may lack the glyphs |
| A language other than English | ◦ not tried (the tool patches whichever tables the game has loaded) |

The text exists only while the game runs. The old tables stay in memory (a few hundred KB per switch) until the game closes.

Known limit: a second `write --text` by hand in the same game ends with `set already in this session`, because the array no longer points at the game's own tables (the tool looks for those). The text stays as written.

### 19.7 The colour of the fire (`flame_color`)

The same idea, for the fire of *Flame, Grant Me Strength*, which is made of effect files (SFX, `f000<id>.fxr`), not of params or text. Level 3 step 3, done for the fire of the cast.

| What | How |
|---|---|
| Where the fire lives | the game keeps each effect file in memory **as it is in the file**; a colour is four little-endian floats (RGBA). Two files make the fire that is recoloured: `524400` (the fire while casting; 18 colours) and `524401` (the burst when the cast ends; 54 colours). The third, `524402` (the fire on the body), is left alone. `eldendisk/writer/fxr_plans.py` lists where each colour sits in each file |
| The new colour | with v = the biggest of R, G, B and w = 1 − (v − the smallest) / v: new RGB = v × (w + (1 − w) × target). White stays white, black stays black, alpha is never touched; a bloom colour becomes v × target |
| Finding the copies | by the colours, with the same scan as the text (`writer/scan.py`): a copy counts only if **every** colour of the plan matches the game's bytes, the original or the painted one (so a second run finds its own work). The look stops as soon as each effect has a copy; the writes are read back |
| In the design | `"flame_color": [red, green, blue]` in a spell, each 0 to 2 (1 = full colour, above 1 shines brighter). The fire effects are shared by every spell that uses them, so there is **one** colour for the design: the first spell (by slot) that names one; if the spells name different colours a warning says which was used. It is not part of the build: editing it never rebuilds or un-secures anything |
| `write --flame-color [--wait [SEC] \| --when-loaded]` | same session rules, same `--when-loaded` as `--text`; started by `run` when a spell of the design names a colour |

Real game, 2026-10-11, three `run` sessions with the colour `[0.2, 0.65, 1.0]`: one copy of each effect found (about 1312 MB into the largest private block, of 2560 MB, in all three runs), 68 colour places written (18 + 50; a place that would not change, such as black, is not written), read back, in 6.4-6.6 s (1712 MB read); the fire is written about 7 s after the character is in the world. The head of the blocks did not hold the fire (the look ended in the rest of the memory), which is why the look goes on to the rest. The colour lasts until the game closes.

---

# Appendices

## Appendix A — Field reference (the fields we touched)

*(inferred)* = a reading from names and diffs, not documentation.

### A.1 EquipParamGoods (`EquipParamGoods.xml`) — row size 176

| Field | Heal 6421 | Our item | Meaning |
|---|---|---|---|
| `goodsType` | 18 | 18 | 18 = incantation |
| `maxNum` / `maxRepositoryNum` | 99 / 600 | same | stack limits |
| `isDiscard`, `isDeposit` | 1, 1 | same | can be discarded / stored |
| `refId_default` | −1 | same | unused for spells (the Magic row has the same id instead) |
| `sortId` | 300010 | 300011 | sort order |
| `iconId` | 6301 | 6302 (from Goods 6424) | inventory icon |
| `sortGroupId` | 10 | 10 | |
| `disableParam_NT` | 0 | 0 | 1 on the dummy; we clone Heal's 0 |

### A.2 MagicParam (`MagicParam.xml`) — row size 168

| Field | Meaning | Our value |
|---|---|---|
| `mp`, `stamina` | FP and stamina cost | 30, 0 |
| `requirementFaith` / `requirementIntellect` | attribute requirements | 20 / 0 |
| `refCategory1` + `refId1` | what the spell triggers: 0 attack, 1 Bullet, 2 SpEffect | 2, `21950111` |
| `ezStateBehaviorType` | cast state-machine class (same, 1, for Heal and Flame) | 1 |
| `refType`, `subCategory1` | cast/behaviour class *(inferred)* | 31, 21 (cloned) |
| `castSfxId`, `fireSfxId`, `effectSfxId` | cast / fire / effect visuals + sounds | 524400, 524401, −1 (cloned) |
| `iconId`, `sortId` | spell menu icon / order | 4036, 5511 |
| `slotLength` | memory slots used | 1 |
| `aiUseJudgeId` | enemy-AI use heuristic | cloned |
| `disableParam_NT` | | 0 |

### A.3 SpEffect (`SpEffect.xml`) — row size 912

| Field | Meaning | Heal `1642100` | Flame `1605000` | Ours |
|---|---|---|---|---|
| `changeHpPoint` | HP per tick; **negative restores** | −230 | 0 | −60 |
| `changeMpPoint` | FP per tick; negative restores | 0 | 0 | −4 |
| `staminaRecoverChangeSpeed` | stamina regen modifier | 0 | 5 | 100 |
| `effectEndurance` | lifetime (s) | 0 | 30 | 15 |
| `motionInterval` | tick period (s) | 0 | 0.06 | 0.5 |
| `vfxId` | row of SpEffectVfx | 1642100 | 1605000 | 1605000 (or 5030) |
| `iconId` | buff icon | −1 | 20406 | 20411 |
| `spCategory` | exclusivity group *(inferred)* | 10 | 151 | 161 |
| `stateInfo` | buff-bar style *(inferred)* | 284 | 200 | 50 |
| `isExtendSpEffectLife`, `isContractSpEffectLife` | refresh behaviour *(inferred)* | 0, 0 | 1, 1 | 1, 1 |
| `cycleOccurrenceSpEffectId` | effect applied each tick | −1 | 1605001 | −1 (unchanged from Heal) |

### A.4 ShopLineupParam (`ShopLineupParam.xml`) — row size 52

`equipId`, `value`, `mtrlId`, `eventFlag_forStock`, `eventFlag_forRelease`, `sellQuantity`, `equipType`, `costType`, `setNum`, `value_Add`, `value_Magnification`, `iconId`, `nameMsgId`, `menuTitleMsgId`, `menuIconId` — see Chapter 7 for the ones that matter.

## Appendix B — Format cheat sheet

**zstd block header** (3 bytes, little-endian): `bit 0` = last block; `bits 1–2` = type (0 stored, 1 RLE, 2 compressed); `bits 3–23` = size. A stored block's size is its length; an RLE block's is the repeat count (content is 1 byte).

**Literals section** (first thing in a compressed block): type in bits 0–1 (0 raw, 1 RLE, 2 Huffman-compressed with a tree, 3 treeless); size format in bits 2–3; the header is 1–5 bytes depending on type/size format. A raw section of `n` bytes: `n < 32` → 1 byte `n << 3`; `n < 4096` → 2 bytes (`((n & 15) << 4) | 4`, `n >> 4`); otherwise 3 bytes (`((n & 15) << 4) | 12`, `(n >> 4) & 255`, `n >> 12`). **Longer forms than necessary are legal** — this is the padding knob.

**Sequence section**: count (1–3 bytes), mode byte (`LL<<6 | OF<<4 | ML<<2`; 0 predefined, 1 RLE, 2 FSE-compressed, 3 repeat), tables, then a bit stream read **backwards** from a final sentinel `1` bit: initial states (LL, OF, ML), then per sequence: offset extra bits, match-length extra bits, literal-length extra bits, then (except after the last) the three state updates in the order LL, ML, OF.

**Offset codes:** value `ofv`: `ofv > 3` → explicit offset `ofv − 3` (pushes onto the registers); `ofv ∈ {1,2,3}` → repeat code; when the literal length is 0 the meaning shifts by one (`1 → rep1`, `2 → rep2`, `3 → rep0 − 1`).

**DCX**: sizes at `0x1C` (uncompressed) and `0x20` (compressed), big-endian. **BND4**: header 0x40, entry headers 36 bytes, entry data 16-byte aligned. **PARAM**: Section 3.1.

## Appendix C — Master results table

*(✅ loaded / played; ❌ rejected; ⚪ built but not run or result not recorded.)*

| Tag | Description | Result |
|---|---|---|
| A | whole body re-compressed (libzstd) | ❌ hang |
| B, B2 | "Heal costs 1 FP" / "every spell costs 1 FP" (libzstd packaging) | ⚪ |
| C1 | original frame, new IV | ✅ |
| C2, C3, C5 | libzstd frames (header-shaped / 64 KiB blocks / + 2-byte tail) | ❌ |
| E3 | original frame, window-descriptor byte changed | ✅ |
| E6 | whole body stored raw | ⚪ |
| E7 | one block stored raw (#16) | ✅ |
| F1 | all spells 1 FP via stored blocks | ✅ |
| G2 / G3 | first full item: tables moved / in place | ❌ / ❌ hang |
| H0 / H1 | 16 zero bytes appended / tables re-appended and repointed | ✅ / ❌ |
| J1 | Goods clone row inserted | ❌ |
| J3 | Magic clone row inserted | ✅ |
| J6 | Goods end-dummy relabelled | ✅ |
| J7 / J8 / J9 / J10 | Goods field sets / all Heal fields / item without Goods content | ❌ (J7 terminated) |
| J2, J4, J5 | Shop / SpEffect / Bullet clone rows | ⚪ |
| K1, K3 | no-op, 125 / 6 stored blocks | ⚪ |
| K2 / K4 / K5 | no-op stored {2–33} / {318–323} / {332–338} | ❌ / ❌ / ✅ |
| L1 / L2 | full item in place, without / with shop | ❌ / ❌ |
| N1–N4, P1–P3 | Goods single-field probes / no-padding twins | ⚪ (never sent) |
| Q1 / Q2 | Goods all Heal fields / `weight`, tail tuned | ✅ / ✅ |
| Q3 / Q4 | L2 / L1 repacked | ❌ / ❌ |
| R2 / R3 / R5 / R6 | SpEffect / Bullet / Shop / Goods+Magic single edits | ✅ ✅ ✅ ✅ |
| R1, R4 | Magic / Goods single edits | ⚪ (covered by R6) |
| S6 / S8 / S10 | no-op, 6 / 8 / 10 isolated stored blocks | ❌ ❌ ❌ |
| T1a / T1b | the real item (no Bullet) via stored blocks, without / with shop | ❌ / ❌ |
| U6 / U32 | no-op, the S6 / K2 blocks as **compressed** blocks | ✅ / ✅ |
| U10 | no-op, the S10 blocks as compressed | ⚪ (built, not sent) |
| V1a / V1b / V1c / V1d | item, compressed; shop 100026 / 100002 / 100026+flag | ✅ ✅(not visible) ✅(not visible) ✅(not visible) |
| W1 | prices of lines 100000–100026 set to 7 | ✅ (no visible change; wrong group) |
| X1 | item in line 100502 + prices of the 100500–100524 group set to 7 | ✅ + visible, buy / memorise / cast E3 |
| Y1 / Y2 | Flame cast style, 8,990 runes, stock 1, line 100508 | built, E1; ⏳ in-game |

## Appendix D — Glossary

| Term | Meaning |
|---|---|
| **regulation.bin** | the game's encrypted, compressed archive of all param tables |
| **param / PARAM** | one table of fixed-size rows keyed by an integer id |
| **row / id** | one record / its key; ids must be sorted in the file |
| **dummy row** | an unreferenced row at the end of a table, safe to relabel |
| **Paramdex** | community field definitions (names, types, offsets) for every param |
| **SpEffect** | a status effect applied to a character (buff, debuff, tick damage/heal) |
| **Goods** | the "usable item" param (also holds incantations as inventory items) |
| **Magic** | the spell param (cost, requirements, what it triggers) |
| **Bullet** | the projectile/area param |
| **DCX** | FromSoftware's compression wrapper (here with a zstd payload) |
| **BND4** | FromSoftware's file archive format |
| **zstd frame / block** | the compressed stream / one ≤ 128 KiB (here 64 KiB output) unit of it |
| **stored (raw) block** | a block holding uncompressed bytes (type 0) |
| **literals / sequences** | the two halves of a compressed block: unmatched bytes and (literal-length, match-length, offset) copy instructions |
| **FSE / Huffman** | the two entropy coders zstd uses (sequences / literals) |
| **repeat offsets (rep0–2)** | three remembered match offsets that short codes refer to |
| **treeless literals** | a literals section that re-uses the previous Huffman tree |
| **cascade** | the need to rewrite further blocks because one block's decoder state was lost |
| **E0–E3** | our evidence levels (Preface) |
| **FMG / msgbnd** | the string-table format / its archive; holds item names and descriptions |
| **vault** | Elden-Disk's backup/swap folder for game files |

## Appendix E — Tool index (`tools/`)

| File | Purpose |
|---|---|
| `erreg.py` | AES layer: `decrypt`, `encrypt` (fresh IV) |
| `erlib.py` | DCX unpack, `Bnd4`, `Param`, `load_regulation`; also the *legacy* splicers (`Splicer`, `SplitSplicer`) kept only to reproduce the failing experiments |
| `erdefs.py` | Paramdex definitions → typed `get` / `set` |
| `zdec.py` | pure-Python zstd decoder (validated on the full original frame) |
| `fse.py` | FSE normalisation, normalised-count writer, sequence encoder + decoder for round-trip |
| `seqparse.py` | splits a compressed block into literals and sequences, tracking repeat-offset state |
| `blockedit.py` | `Orig` (frame/blocks/census), frame assembly, padding tuner (`pack_file`), file writer and verifier |
| `reencode.py` | **the core**: re-segmentation, rep-offset DP, `build()` loop |
| `make_item.py` | **the item**: Chapter 13 |
| `make_u_noop.py` | the passing no-op (U6/U32): compressed blocks, same bytes |
| `legacy_raw_noop.py` | the failing no-op (S6/K-style): stored blocks, same bytes |
| `inspect_rows.py`, `inspect_frame.py`, `selftest.py` | diff two rows / frame census / offline checks |
| `example_all_spells_1fp.py` | the minimal "edit any table" example (Chapter 15) |
| `dump_msgbnd.py`, `gamearchive.py`, `probe_text.py` | the text research of 1.7.1 (`code/tools/`, Chapter 19.5) |

---

*End of checkpoint 1. Part VI (text, 1.7.1) is written; when the image and the inventory placement are done, this book gets Part VII.*

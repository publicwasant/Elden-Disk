# Phase 2.0: draft spec for spells of every kind (for the author to approve; no code yet)

Status: **APPROVED by the author 2026-10-09** (the six decisions of section 8). Built so far: 2.1 `clone` (section 9); the rest is not built. It extends spec 1.7.0 section 4 (the design) and section 10b (rows appended to the tables). Decisions already taken by the author: `from` is a numeric Magic id; slots 8-64 are decided later; names and descriptions stay "stored only".

## 1. What the game's data says (measured on the 1.17.1 original, 317 Magic rows)

A spell is a **chain of rows**: Magic → (Bullet | AtkParam_Pc | SpEffect, by `refCategory1..10` and `refId1..10`) → more Bullets (`HitBulletID`, `intervalCreateBulletId`), AtkParam_Pc (`atkId_Bullet`) and SpEffects (`spEffectId0-4`, `spEffectIDForShooter`; a SpEffect can point to others through `cycleOccurrenceSpEffectId`, `atkOccurrenceSpEffectId`, `replaceSpEffectId`).

Rows reached from one Magic row (all 317 rows counted):

| Table | median | 90th percentile | max |
|:--|:-:|:-:|:-:|
| Bullet | 4 | 14 | 66 |
| AtkParam_Pc | 2 | 6 | 18 |
| SpEffect | 1 | 4 | 31 |

Examples: Black Flame (6210) reaches Bullets 10621000, 10621001, 10621050, 10621051, AtkParam_Pc 62101, 62106 (and the shared 79980, 79990), SpEffect 1621000. Black Flame Ritual (6240) reaches 8 Bullets, 4 own AtkParam_Pc and SpEffect 1625000.

**Private and shared rows.** A row of a chain is either the spell's own (reached by that Magic row and, at most, its siblings: Ritual and its variant 53243 share all their rows) or a generic row that many spells use (AtkParam_Pc 1 is reached by 73 Magic rows, 79990 by 20, Bullet 10999999 by 38). A copy of a spell must copy the own rows (so the new spell can be tuned without touching the original) and keep pointing at the generic ones.

Largest real ids below the game's `999999999` dummy rows: Bullet 400000002, AtkParam_Pc 701320361, SpEffect 21950011, Goods 2220010, Magic 2050090.

## 2. The idea: one engine, five kinds

Every kind is the same operation: **copy the template's own rows under new ids owned by the slot, point the copies at each other, then write the fields the design names**. The kinds differ in which rows the chain contains, which friendly fields exist, and what is checked.

| kind | `from` (template Magic row) must call | rows added (besides Goods + Magic) |
|:--|:--|:--|
| `clone` | anything | none: the Magic copy keeps pointing at the template's rows, so it behaves exactly like the template, with its own cost, requirements and shop line |
| `buff` | a SpEffect (`refCategory1` = 2), not an enchant | SpEffect copies. Default `from` is 6050 and the existing friendly `effect` block (heal over time) stays: spells without `kind` are `buff`, so the Z4 spell and the golden hash do not change |
| `enchant` | a SpEffect with `isEnchant` (weapon) or `isShieldEnchant` (shield) | SpEffect copies (to be checked in the game: whether an enchant needs another table) |
| `projectile` | a Bullet (`refCategory1` = 1) | Bullet copies + the AtkParam_Pc and SpEffect rows the bullets own |
| `attack` | an AtkParam_Pc (`refCategory1` = 0) | AtkParam_Pc copies + their SpEffects |

A `from` that does not match its `kind` is an error that names what the template really is.

## 3. The design file

Slot key = the spell's id, a slot is still `null` when empty, the slot number still fixes the ids. New and changed fields of a spell:

```json
"cursed_black_flame": {
  "kind": "projectile",
  "from": 6210,
  "name": "Cursed Black Flame",
  "description": "stored only",
  "requires": {"intelligence": 45, "faith": 15, "arcane": 10},
  "fp_cost": 30,
  "stamina_cost": 0,
  "shop": {"price": 34590, "stock": 1},
  "set": {"Bullet.10621000.life": 3.0, "SpEffect.1621000.changeHpRate": -0.5}
}
```

- `kind` is optional and defaults to `buff`. `from` is required for every kind but `buff`.
- `requires`, `fp_cost`, `stamina_cost` default to the template's values. `type` (incantation or sorcery) is the template's and cannot be changed (the cast motion and the catalyst follow it); a different `type` is an error.
- `shop` is as in 1.7.0 (slots 1-7 only until the slots above 7 are decided).
- `set` writes any single number of a **copied** row. The key is `<Table>.<template row id>.<field>`, the same name the workbench uses (`write --set params.Bullet.10621000.life=3`), so what was tried in the game is pasted into the design. The value is checked like `write` checks it (field exists, type and bit width, no clamp). A field that holds another row's id is refused unless the value is an id that exists in the base file; the builder sets the ids between the copies itself. A key that names a row that is not copied (a shared row) is an error that says so.
- Legacy fields of `buff` (`cast_motion`, `effect`, `poise_while_casting_seconds`) keep their meaning and cannot be combined with `set` on the rows they build.
- A **plan** is printed before a build (`extension innovate-items spells --add all --dry-run` already builds in memory; it will list, per spell, every row of the chain marked *copied* or *shared (reached by N spells)*, the new ids and the bytes added). A row reached by more than 3 Magic rows is shared by default; `"copy": ["AtkParam_Pc.79990"]` or `"share": ["Bullet.10625003"]` overrides one row.

## 4. Ids owned by a slot (slot *n*, 1..64)

Existing, unchanged: Goods and Magic `2230000 + n - 1`; SpEffect (heal over time) `21950111 + n - 1`; SpEffect (poise) `21950211 + n - 1`; shop lines as in 1.7.0.

New pools, each slot owns a fixed block so a spell keeps its ids while it stays in its slot:

| Table | Block per slot | Base | Why this base |
|:--|:-:|:--|:--|
| SpEffect (copies) | 8 | `21951000 + (n - 1) * 8` | above the last real id 21950011 and above the two existing blocks |
| Bullet | 16 | `410000000 + (n - 1) * 16` | above the last real id 400000002, below 999999999 |
| AtkParam_Pc | 8 | `710000000 + (n - 1) * 8` | above the last real id 701320361 |

A chain with more own rows than its block (Bullet 16, AtkParam_Pc 8, SpEffect 8) is refused with the numbers; 90% of the game's chains fit (Bullet p90 14, AtkParam_Pc p90 6, SpEffect p90 4).

## 5. Validation and gate

- Spec: `kind`/`from` consistency, `set` keys against the field layouts (`paramdefs.py`, same data as the workbench), block sizes, uniqueness of ids.
- Build: the copy of each row is the base row with only the named fields and the remapped ids changed; shared rows are never changed; **every copied row's id fields point only to base rows or to copies of the same spell** (no copy points at the template's own rows by accident).
- Footprint: lists rows added per table; the preflight accepts six tables differing, still nothing existing removed or modified (R5).
- Gate additions (to be named in the spec when built): ids inside the block of the slot; no id used twice; the Magic copy's `ref` slots resolve; `set` values in range; capacity numbers of 2.5.
- After a build in the game: `read --param-check` must find every row equal (done for slot 1).

## 6. Capacity (an estimate; the game decides in 2.5)

Bytes per added row (record 24 B + row): Goods 200, Magic 192, ShopLineup 76, SpEffect 936, Bullet 296, AtkParam_Pc 480. A median chain (4 Bullets, 2 AtkParam_Pc, 1 SpEffect) is about 3.5 KB with its Goods, Magic and shop rows: 64 of them are about 227 KB, close to the 219 KB the game accepted (466 KB failed). A heavy chain (p90) is about 11 KB: 64 of them would be about 720 KB. So the number of slots depends on the kind **and** on the template; the table "slots per kind" comes from 2.5, and the gate numbers are raised only after a bigger file has passed in the game.

## 7. Steps after approval

2.1 `clone` (no new table, smallest test in the game) → 2.2 `buff` under the new spec and `enchant` → 2.3 `projectile` (Bullet table; re-apply the T7 work from the backup) → 2.4 `attack` → 2.5 capacity → 2.6 slots 8-64. Each ends with unit tests, a golden anchor, `read --param-check` in the game, and the docs (spec, cli-commands, changes, manual plan).

## 8. Decisions asked of the author

1. One engine (copy the own rows of the chain, then `set`) instead of one hand-written recipe per kind: **recommended**, because a recipe per kind would repeat the same copying five times and `set` lets what the workbench found go straight into the design.
2. `kind` defaults to `buff` so existing designs and the Z4 hash stay valid.
3. `set` keys use the template's row ids (`Bullet.10621000.life`).
4. Shared-row rule: a row reached by more than 3 Magic rows is shared, with `copy`/`share` overrides.
5. Block sizes per slot: Bullet 16, AtkParam_Pc 8, SpEffect 8.
6. `type` follows the template and cannot be changed.

## 9. What 2.1 built (2026-10-09)

`kind: clone` as in section 3, with the approved decisions 1-6, in the smallest form: the Goods and Magic rows of the template are copied under the slot's ids and the Magic copy keeps pointing at the template's own chain, so no Bullet, AtkParam_Pc or SpEffect row is added and the ids of section 4 for those tables are not used yet. Spec: [specs/elden-disk-spec-v1.7.0.md](../../../../../specs/elden-disk-spec-v1.7.0.md) section 4b.

Where it differs from this draft:

- **`set` refuses every id-like field** (the draft allowed one whose value is an id that exists in the base file). A pointer is only safe when the whole chain is checked; that comes with the kinds that copy a chain (2.3, 2.4). Also refused: `goodsType` (it follows the template) and the fields that have a friendly name in the same design.
- `set` can only name the two copied rows (`Magic.<from>.<field>`, `Goods.<from>.<field>`); a key for a chain row says it is shared and not copied. The `copy` / `share` overrides and the printed plan of section 3 come with the first kind that copies a chain (2.3).
- `requires`, `fp_cost` and `stamina_cost` that are left out stay the template's (nothing is written), so the canonical form of a clone holds only what the design says.

## 10. What 2.2 built (2026-10-10)

`enchant` and `buff` with `from`, decisions 1-6 as approved. The engine copies the template's own SpEffect rows (reached by no more than 3 Magic rows of the game; the others are generic and shared), ids `21951000 + (n-1)*8 + k`, remaps the three SpEffect link fields among the copies and the Magic `refId` that point to them, and `set` takes `SpEffect.<template row id>.<field>`. Where it differs from this draft:

- The reach count is computed from the game's file (`chain.py` reads Bullet and AtkParam_Pc too), not from a hard-coded list.
- The three link fields followed are `replaceSpEffectId`, `cycleOccurrenceSpEffectId` and `atkOccurrenceSpEffectId`; `applyIdOnGetSoul`, `accumuOverFireId` and `accumuUnderFireId` are refused in `set` but not followed (none of the 23 templates of the game has a value in them).
- (2.3 adds Bullet rows to the footprint, see section 11.) The footprint only adds SpEffect rows; the `copy` / `share` overrides and the printed plan are left to 2.3.

## 11. What 2.3 built (2026-10-10)

`projectile` as approved: the engine now also copies the template's own Bullet rows (block of 16 ids per slot). Where it differs from this draft:

- Bullet ids start at `500000000` (the range T7 loaded in the game), not `410000000` as planned in section 4.
- The attack rows (AtkParam_Pc) are **not** copied (that is 2.4): the copies keep calling the game's, so the damage of a projectile does not change yet; its range, life, speed and what it applies on hit do.
- The walk that decides which rows are copied (`chain.copy_set`) goes only through *own* Bullet and SpEffect rows and stops at generic rows and attack rows, so a row that only a shared row calls is not copied.
- T7 passed in the game first, so the gate allows 20 re-encoded blocks.

## 12. What 2.4 built (2026-10-10)

`attack`, and the Atk copies for `projectile`. AtkParam_Pc is the sixth table the engine copies: a block of 8 ids per slot (`710000000 + (n-1)*8`), the copies are remapped (`atkId_Bullet` in the Bullet copies, `refId` in the Magic copy, `spEffectId0-4` in the Atk copies) and `set` takes `AtkParam_Pc.<template row id>.<field>` for the kinds `projectile` and `attack`. Where it differs from this draft:

- **The table grows at its end.** The first way (the same as for the other tables: the new records and rows are written in front of the table) evicts `AtkParam_Npc`, 6.17 MB, in front of AtkParam_Pc; the body grew by 6.27 MB and the game refused the save (T8, failed). The second way (`mode: "end"`, T9, passed): the records grow into the front of the row data, the first few rows are moved behind the strings, the new rows take the hole, and the table behind it (28 KB) is moved to the end of the body. Four new rows relocate 5 old rows; the body grew by 124,560 bytes and 26 blocks changed.
- The gate is now 26 blocks, 219,000 bytes of body and 243,000 of frame (T9). A design with one projectile and its Atk copies is at the limit of the 26 blocks.
- `attack` needs a Magic row that makes a direct attack (an AtkParam_Pc ref and no Bullet ref): 4430, 4440, 4450, 7080, 7510 in the game. Generic rows (e.g. 79980, 79990) stay shared.
- `PLANNED_KINDS` is empty: all five kinds exist.
- In the game: A0-A6 of the manual plan are open.

# Subject: Reverse Curse Technique (final build "Z4")

A custom incantation added to Elden Ring 1.17.1 by editing `regulation.bin`. Case study of the *Item Customization Handbook* (`../item-customization-handbook.md`, Part VI).

**Offline play only.** Back up your original `regulation.bin` and saves first. The file only fits the pristine 1.17.1 `regulation.bin` (SHA-256 `766521f9508de3a3532df61c45a1c2d93340f1ff7ed8306ab20df761712ca2ab`).

## The file

`regulation.customized.z4-reverse-curse-technique-i45-f15-a10-fp80-bfb-hyperarmor.bin`

| | |
|---|---|
| size | 2,071,488 bytes |
| SHA-256 (file) | `a8f0a1716e188c54b9de206b6b42031c2d4b91e54730de48996973cd3479b1a9` |
| SHA-256 (decrypted) | `1aa16ee0dbcbc5902cef2b6eb29bd542f42b2158fcdb44c221c187280db5277b` |
| in-game status | loaded and played; cast speed confirmed; accepted as final by the owner |

Install: copy over the game's `regulation.bin` (offline, original backed up). Elden-Disk's vault copy lives in `…\EldenDisk\vault\regulation\`.

## Item sheet

| Property | Value |
|---|---|
| Ids | Goods = Magic = `2230000`; buff SpEffect `21950111`; poise SpEffect `102006` (reused unused row) |
| Type | Incantation |
| Requirements | Int 45, Faith 15, Arcane 10 |
| Cost | 80 FP, 0 stamina |
| Cast | Black Flame Blade motion (`refType 32`), Flame visuals (`castSfxId 524400`, `fireSfxId 524401`, buff `vfxId 1605000`) |
| Effect | for 15.0 s, every 0.5 s: HP −60 (heals), FP −4 (restores), stamina regen speed 100 |
| While casting | Endure-style poise buff for 2.0 s, no damage reduction (still flinches in practice) |
| Shop | merchant group `100500–100524`, line `100508`, 34,590 runes, stock 1, stock flag `150080` |
| Text | `?GoodsName?` / `?GoodsInfo?` (not yet localized) |

## Rebuild

```
cd tools
python make_item.py --name Z4 --faith 15 --intellect 45 --arcane 10 --fp-cost 80 --price 34590 --motion 32 --poise-sp 102006
```

The decrypted output must hash to the value above (the encrypted file differs on each build because of a random IV).

## Known limits

* No name/description text, custom image or direct inventory placement yet (handbook Part V).
* True I-frames are impossible from params; the poise buff does not fully prevent flinching (handbook 19.3–19.4).
* Row `102006` is overwritten; it is labelled *unused* in Paramdex but that was not proven.
* The earlier variants Y1 (Flame cast, 8,990 runes) and Z1–Z5 are in the vault; only Y1 and Z4 were played.

# Section (1b) - Innovate Items - Spell Restructuring Design Json

__(Still in 1.7.1)__

**Schema Template:**

```json
{
    "<id-1>": {                                                     <- The unique ID of the spell, user can add whatever ids in `extentions.json` but after buit `regulation.bin` the `<id-n>` should be replace with actual id in the **Vault**.
        "__info__": "<explain-everthing-about-this-spell-and-how-every-fields-means-and-works>",
        "kind": "projectile",
        "from": 6421,
        "requires": {
            "status": {
                "intelligence": 0,
                "faith": 60,
                "arcane": 10
            },
            "cost": {
                "focus_point": 120
            }
        },
        "locations": {
            "<shop-id-1>": {
                "price": 34590,
                "stock": 1
            },
            .
            .
            . _<shop-id-n>_                                             <- For this time specific only on NPC Merchant Kalé
        },
        "customs": {
            "basic": {                                                  <- Basic params setting (Level-2), use settled pointer-chain in offsets.json
                "__info__": "<explain-specificly-about-what-are-these-fields-and-how-they-works>",
                "SpEffect.1642100.effectEndurance": 20,
                "SpEffect.1642100.motionInterval": 0.5,
                "SpEffect.1642100.changeHpPoint": -45,
                "SpEffect.1642100.changeMpPoint": -15,
                "SpEffect.1642100.staminaRecoverChangeSpeed": 100,
                "SpEffect.1642100.vfxId": -1,
                "Magic.6421.refType": 32,
                "Magic.6421.castSfxId": 524400,
                "Magic.6421.fireSfxId": 524401,
                "Bullet.10642100.sfxId_Bullet": -1,
                "Goods.6421.iconId": 6806
            },
            "advanced": {                                               <- Advanced params setting (Level-3), use write scanner (optimized) to find the pointer-chain in memories
                "__info__": "<explain-specificly-about-what-are-these-fields-and-how-they-works>",
                "texts": {
                    "goods_name": "...",                                <- The name of the spell, shown in the shop list and inventory
                    "goods_info": "...",                                <- The short description of the spell, shown in the shop list and inventory
                    "goods_caption": "..."                              <- The long description of the spell, shown in the inventory and memory slot
                },
                "colors": {
                    "Magic.6421.castSfxId": [0.2, 0.65, 1],                    <- The RGB color of the spell's fire, shown when casting and burning on the body
                    "SpEffect.1642100": [0.2, 0.65, 1],                 <- The RGB color of the spell's eyes, shown when casting and buffed
                    .
                    .
                    . <params-id-n>
                }
            }
        }
    }
}
```

### Tasks
1. Restructure the spell design JSON according to the schema template provided above. (json)
2. Ensure that all required fields are filled in with appropriate values, including the spell's ID, kind, requirements, locations, and custom parameters. (coding)
3. Test the restructured JSON in the game to verify that the spell behaves as expected, including its effects, costs, and visual elements. (testing)
4. Update core-documentation to reflect the new structure and provide clear instructions for future modifications. (documentation)


### Important Notes:
- The `id` field should be unique for each spell and should follow the format `<id-1>`, `<id-2>`, ETC. And In `extentions.json` user can add whatever ids but after buit `regulation.bin` the `<id-n>` should be replace with actual id in the **Vault**.
- THe Logging Console, redesign and replace, log representation should be more clear and readable, with a focus on the changes made to the spell design and any errors encountered during the restructuring process. (Modern CLI Console UX Design รวมระบวนการ extension innovate-items spells ให้อยู่ใน block ลักษณะ pacing เดียวกัน, ตัว ids และ addresses เช่น 114880, 0x7ff3cbbb0000 มีสีเฉพาะของมันเอง)


### Additional Considerations:
- The IDs that appear in the template: __6421__, __1642100__, __524400__, __524401__, __6806__ are specific to the game and should be used as-is, and the user can find out what the meaning of it in `spells-innovation-handbook.md` and `spells-row-finder.md`.
- Meaning of **Level N** (มาจากแนวคิดที่ผมเขียนไว้เองของเรื่อง Items Customization): Level-1: Basic design can run `eldendisk.exe write --set [NAME]=[VALUES]` to set parameters, Level-2: คือการหยิบเขาของที่มีอยู่แล้วในเกมมา "เล่นแร่แปรธาตุ" (Restructure) จับมา ดัดแปลง คัดลอก และ ประกอบกันเป็นของชิ้นใหม่, Level-3: เหมือนกับ Level-2 แต่มีการหยิบเข้าสิ่งที่ไม่เคยมีอยู่ในเกมมาก่อน "สร้างใหม่" แล้วยัดเข้าไปด้วยการ scan memory (write scanner) ตัวอย่างก็เช่น Item's text หรือ Item's effect color; (Level-3) นั้นยากที่สุด เพราะเราเคยลอง scan หา pointer-chain แล้วตั้งเป็น settled pointer-chain in offsets.json ได้ผลแบบสุม หมายความ pointer-chain กลุ่มนีไม่สามารถ settle ได้ จึงต้องทำการ scan memory และ write สดตอนเกมเข้าโลก (ซึ่งเราทำสำเร็จไปแล้ว และหาวิธี opimize ให้เร็วขึ้นอยู่ตลอด)
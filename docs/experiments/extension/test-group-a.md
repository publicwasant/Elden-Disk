# การทดสอบ Extension Innovate-Items Spells (Phase 2)

## Group A. kind: attack and the attack rows of a projectile (Phase 2.4; coded and tested, not run in the game yet)

_(Manual Test Reference: [manual-test-plan-1.7.0](docs/manual-test-plan-1.7.0.md#a-kind-attack-and-the-attack-rows-of-a-projectile-phase-24-coded-and-tested-not-run-in-the-game-yet))_

**Before start: completing rebuild .exe tools first**:

```commandLine
python -m .\code\tools\dev-pipline.py --vault-on
```

### A0

**Do:** slot 4 เดิม รัน --add all --dry-run ต้องขึ้น gate passed (26 blocks re-encoded) แล้ว run ยิง Black Flame ที่ copy ต้องเหมือนเดิม

**Result:**

```commandLine
```

### A1

**Do:** ใส่ slot 5 ใน extension.json แทนบรรทัด `<id-5>: null` ด้วย `"strike_copy": {"kind":"attack","from":4440,"fp_cost":4,"shop":{"price":1000,"stock":-1}}` แล้ว `dry-run`, `run`, ซื้อ, จด, ร่าย

**Change Subject `extension.json` Slot 5:** 

```json
{
  "strike_copy": {
    "kind": "attack",
    "from": 4440,
    "fp_cost": 4,
    "shop": {
      "price": 1000,
      "stock": -1
      }
    }
}
```


**Result:**

```commandLine
```

### A2, A3

**DO:** `read --param-check` ต้องเท่ากันทุกแถว และ `read --param AtkParam_Pc.710000032.atkMag` ต้องได้ `180`


**Result:**

```commandLine
```

### A4

**Do:** พิ่ม `set` ตั้ง `atkMag 6` แถวเป็น `1800/1840` ตัว copy ต้องแรงขึ้นราว `10` เท่า ส่วน `4440` ตัวจริงต้องยัง `180`

**Change Subject `extension.json` Slot 5:** 

```json
{
  "strike_copy": {
    "kind": "attack",
    "from": 4440,
    "fp_cost": 4,
    "shop": {
      "price": 1000,
      "stock": -1
      }
    },
    "set": {
      "Bullet.10621000.life": 0.3,
      "SpEffect.1621000.changeHpRate": -0.05
    }
}
```


**Result:**

```commandLine
```

### A5, A6

**Do:** เคส error สองอัน (attack จาก 6210 และ projectile จาก 4440) ต้องขึ้นข้อความ error และไม่ build อะไร

**1. Change Subject `extension.json` Slot 5: `--add all --dry-run`** 

```json
{
  "strike_copy": {
    "kind": "attack",
    "from": 6210,
    "fp_cost": 4,
    "shop": {
      "price": 1000,
      "stock": -1
      }
    },
    "set": {
      "Bullet.10621000.life": 0.3,
      "SpEffect.1621000.changeHpRate": -0.05
    }
}
```


**Result:**

```commandLine
```

**2. Change Subject `extension.json` Slot 5: `--add all --dry-run`** 

```json
{
  "strike_copy": {
    "kind": "projectile",
    "from": 4440,
    "fp_cost": 4,
    "shop": {
      "price": 1000,
      "stock": -1
      }
    },
    "set": {
      "Bullet.10621000.life": 0.3,
      "SpEffect.1621000.changeHpRate": -0.05
    }
}
```


**Result:**

```commandLine
```
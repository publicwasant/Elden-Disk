# Adding a profile — step by step

A **profile** tells the tool where things live inside one specific build of `eldenring.exe`. You need one the first time you
use the tool and again after every game patch (a patch changes the exe, so the tool refuses to read until it has a profile
for the new exe — this is intentional, it never guesses).

> **Short on time?**    
> If your exe hash is `1a3547101327f65d0c76da2f9190ac0aa66871ea42bae2aecc61e11a8b597891` (Elden Ring 1.17.1)    
> You do **not** need Cheat Engine at all: use the ready-made profile in the [**Appendix**](adding-a-profile.md#appendix--reference-profile-for-elden-ring-1171) and jump to [**Part D**](adding-a-profile.md#part-d--fill-in-the-profile-and-verify-the-stats).

## What you will do

| Part | Goal                                                                        | Rough time (first time)     | You can stop here and already have…  |
|:----:|:----------------------------------------------------------------------------|:----------------------------|:-------------------------------------|
|  A   | Prepare: hash, profile skeleton, game open in-world, Cheat Engine attached  | 10 min                      | —                                    |
|  B   | Find the memory address of your **runes**                                   | 10 min                      | —                                    |
|  C   | Turn that address into a permanent **pointer path** (Pointer Scan)          | 10–30 min (mostly waiting)  | the numbers for the profile          |
|  D   | Put the numbers in `offsets.json` and verify level, runes and attributes    | 10 min                      | **working stats telemetry**          |
|  E   | Buffs & Animations: verify layout and fill `names.json`             | 30+ min                     | buffs and animations telemetry       |
|  F   | Wrap-up: back up, record, patch-day shortcut                                | 5 min                       | —                                    |

Times are rough guesses for a first attempt. Later patches are much faster because you already know the routine.
Each part ends with a **🟢 Checkpoint** — if you do not see it, do not continue; use the troubleshooting table of that part.

## The idea in one minute

- Every time the game starts, the objects that hold your character (level, runes, …) are created at **new addresses**.
  An address you find today is useless tomorrow.
- What stays the same (for one game build) is a **static pointer inside the exe** (`eldenring.exe + some number`) that
  leads to your character in a few hops. Finding that hop-by-hop path is what Pointer Scan does.
- The path looks like: `[exe + RVA]  →  + offset 0  →  + offset 1  →  + offset 2 = runes`. Those four numbers
  go into the profile. (Background: *Memory Read 101*, chapters 2 and 8.)

```
Cheat Engine result row                       offsets.json field
──────────────────────────────────────        ───────────────────────────────
Base Address  "eldenring.exe"+03B16E30   ──►  world_chr_man_rva          = "0x3B16E30"
Offset 0      0                          ──►  world_chr_man_to_player    = "0x0"
Offset 1      580                        ──►  player_to_game_data        = "0x580"
Offset 2      6C                         ──►  game_data.runes            = "0x6C"
```

## What you need

- Windows 10/11, **64-bit** Python 3.11+, this project, the Steam client installed and logged in
- **Cheat Engine** installed, **[download](https://www.cheatengine.org/)** any recent version, run **as Administrator**
- A character you can load into the world, and a way to change your runes (defeat an enemy or spend at a merchant)
- **Offline only.** The tool starts the game without EasyAntiCheat; never do this while playing online

---

## Part A — Prepare

**A1. Get the hash of your `eldenring.exe`**

```powershell
python -m eldendisk hash
```

It prints one 64-character line. Copy it. (If it says the game was not found, add `--game-dir "<folder with eldenring.exe>"`.)

**A2. Add a profile skeleton to `offsets.json`**

Open `offsets.json` and add a block under `"profiles"`, with **your hash as the key**. Keep any profile you already have.
Paste this and replace the two `<…>` values:

```json
"<YOUR_HASH_HERE>": {
  "label": "Elden Ring <game version>",
  "world_chr_man_rva": null,
  "world_chr_man_to_player": null,
  "player_to_game_data": "0x580",
  "player_to_sp_effect": "0x178",
  "game_data": { "level": "0x68", "runes": "0x6C", "attributes": "0x3C" },
  "sp_effect": {
    "head": "0x8",
    "entry": { "id": "0x8", "next": "0x30", "duration": "0x48", "timer": "0x40", "timer_mode": "remaining" }
  }
}
```

The two `null` values are what Parts B–D find. The other numbers are community/starting values that worked on 1.17.1; you
verify them (they may differ on another build), you do not have to discover them from scratch.
The file must stay valid JSON: a comma between profiles, none after the last one.

**A3. Launch the game through the tool**

```powershell
python -m eldendisk run -v
```

Expected: the game starts, and the tool prints

```
[UNSUPPORTED_VERSION] profile incomplete: world_chr_man_rva is not set
```

and exits. **That is the success message for this step** — it proves the hash in your profile matches your exe.
The game stays open. If it says `no profile for exe sha256 …` instead, the hash key has a typo.

**A4. Get in-world**

Load your character and stand somewhere safe. Alt-Tab is fine (the game does not pause). Stay in the world until Part C is finished.

**A5. Attach Cheat Engine**

1. Start Cheat Engine as Administrator (right-click → Run as administrator).
2. Click the first toolbar icon (*Select a process to open*), choose `eldenring.exe`, click **Open**.
3. The title bar now shows `…-eldenring.exe`.

> 🟢 **Checkpoint A:** the game is open in-world, Cheat Engine shows `eldenring.exe` in its title bar.

| Problem                              | Fix                                                                                          |
|--------------------------------------|----------------------------------------------------------------------------------------------|
| `no profile for exe sha256`          | Hash key in `offsets.json` differs from `hash` output                                        |
| `EAC_ACTIVE`                         | You started the game from Steam's normal Play button. Close it and use `run -v`              |
| Cheat Engine cannot open the process | Run Cheat Engine as Administrator; make sure the game was started by `run -v` (no EAC)       |
| `No module named eldendisk`    | You are in the wrong folder. `cd` to the folder that *contains* the `eldendisk` folder |

---

## Part B — Find the address of your runes

Goal: an address that currently holds your runes. It only needs to be right *right now*.

**B1.** Look at your runes on screen. If the number is still counting, wait until it stops. Write it down.
(The larger and more unusual the number, the fewer false matches you get.)

**B2.** In Cheat Engine set:

| Setting                      | Value                                          |
|------------------------------|------------------------------------------------|
| Scan Type                    | `Exact Value`                                  |
| Value Type                   | `4 Bytes`                                      |
| Hex (checkbox next to Value) | **unticked**                                   |
| Value                        | your runes, digits only (no commas, no spaces) |

**B3.** Click **First Scan**. Top-left shows `Found: N`.

**B4.** In the game change your runes (defeat an enemy or spend some). Wait until the counter stops, then in Cheat Engine type the
**new** number in *Value* and click **Next Scan** (not *New Scan*).

**B5.** Repeat B4 until `Found` is small (1 to 3) or stops shrinking. Several addresses left is normal: the game keeps copies
of the number (UI, buffers).

**B6.** Choose which address to try first. If more than one remains, start with one whose last hex digit is **C**
(the runes field is at `+0x6C` inside an object that starts on a multiple of 16). This is only a hint; if Part C finds nothing, try the next address.

**B7.** Put it in the lower table: **double-click** the address (or select it and click the red arrow at the bottom middle).

> 🟢 **Checkpoint B:** the lower table contains a row whose Value equals your current runes, and changes when your runes change.

| Problem                                                      | Fix                                                                                                 |
|--------------------------------------------------------------|-----------------------------------------------------------------------------------------------------|
| Error `Scan error: thread 0: please fill something in (100)` | The *Value* box is empty or not a plain number                                                      |
| `Found: 0`                                                   | *Value Type* is not `4 Bytes`, *Hex* is ticked, the number is wrong, or the process is not attached |
| Huge `Found` count                                           | Keep changing your runes and use Next Scan; each round removes most false matches                   |
| `Found` stays at 2–3                                         | Normal. Go to Part C with the first candidate                                                       |

---

## Part C — Turn the address into a pointer path

**C1.** Right-click the row **in the lower table** → **Pointer scan for this address**.
(The menu does not exist on the upper results list — that is the most common "where is it?" moment.)

**C2.** Set the dialog exactly like this:

| Option                                      | Value                                                 |
|---------------------------------------------|-------------------------------------------------------|
| Scan for address                            | selected (default)                                    |
| Max different offsets per node              | `3`                                                   |
| **Pointers must end with specific offsets** | **ticked**                                            |
| — offset list                               | type `6C` → click **Add**; type `580` → click **Add** |
| Max deviation                               | `0`                                                   |
| Nr of threads scanning                      | default                                               |
| **Maximum offset value**                    | `200000` (default 4095 is too small)                  |
| **Max level**                               | `4`                                                   |

The offset list must show two entries: `6C` (labelled *Last offset*) and then `580`. Two classic mistakes:

- typing `6C` into **Max deviation** (that box must say `0`)
- typing a number in the box under the list and **not clicking Add** (or clicking Add for a stray `0`)

Click **OK**, choose any file name for the result file.

**C3.** Wait. First you see *Generating pointermap* (a green bar), then the numbers start moving. This can take minutes and
uses a lot of RAM.

- do **not** click Stop, do **not** change your runes, do **not** leave the world (no loading screens, no quitting to the menu)
- close heavy programs; fans spinning is normal

**C4.** A result window opens. `Pointer paths: N` tells you how many paths were found.

**C5.** Read a row. Numbers are hex. Starting at *Base Address*, one step per offset:

```
p0 = value stored at  [ eldenring.exe + RVA ]
p1 = value stored at  [ p0 + Offset 0 ]
p2 = value stored at  [ p1 + Offset 1 ]
runes address = p2 + Offset 2          ← the last step is only added, never read
```

**C6.** Choose a row: base starts with `eldenring.exe`, **exactly three offsets**, ending `580`, `6C`. If there are several, use the one
with the fewest offsets; if two look equal, try each in Part D.

Example from the reference build (1.17.1) — two rows were found:

| Base Address               | Offset 0 | Offset 1 | Offset 2 | Offset 3 |
|----------------------------|----------|----------|----------|----------|
| `"eldenring.exe"+03B16E30` | 0        | 580      | 6C       |          |
| `"eldenring.exe"+03D66170` | 8        | 0        | 580      | 6C       |

The first row has three offsets → use it. The second has four (one extra hop) and does not fit the profile format.

**C7.** Copy the numbers into the profile fields (add `0x` in front; leading zeros do not matter):

| Cheat Engine         | offsets.json field        | Reference build value          |
|----------------------|---------------------------|--------------------------------|
| Base Address `+ RVA` | `world_chr_man_rva`       | `"0x3B16E30"`                  |
| Offset 0             | `world_chr_man_to_player` | `"0x0"` (yes, zero is correct) |
| Offset 1             | `player_to_game_data`     | `"0x580"`                      |
| Offset 2             | `game_data.runes`         | `"0x6C"`                       |

> 🟢 **Checkpoint C:** you have one row with three offsets ending `580, 6C`, and you have written its numbers down.

| Problem                           | Fix                                                                                                                                                                                                                                                                                                                                                                                                                                |
|-----------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Menu item not found               | You right-clicked the upper list. Add the address to the lower table first (B7)                                                                                                                                                                                                                                                                                                                                                    |
| Zero paths found                  | (1) did you stay in the world and keep the runes unchanged during the scan? (2) try the next candidate address from B5 (3) redo the scan **without** ticking *must end with specific offsets* and with Max level `5`, then look at the last two offsets of the paths: they are `player_to_game_data` and `game_data.runes` for your build (level and attributes are then unknown; Part D will show whether the defaults still fit) |
| Only paths with 4 or more offsets | The profile has room for exactly three hops. Save the result window as a screenshot and ask for help (see Part F)                                                                                                                                                                                                                                                                                                                  |
| Scan seems frozen                 | Wait; the pointermap step is long. Check RAM in Task Manager before giving up                                                                                                                                                                                                                                                                                                                                                      |
| Windows runs out of memory        | Close other programs, or lower *Max level* to `3` and retry                                                                                                                                                                                                                                                                                                                                                                        |

---

## Part D — Fill in the profile and verify the stats

**D1.** Edit your profile block in `offsets.json`: replace the two `null` values (and, if your row differed, the others):

```json
"world_chr_man_rva": "0x3B16E30",
"world_chr_man_to_player": "0x0",
```

Save the file. It must still be valid JSON.

**D2.** With the game still open and in-world, run:

```powershell
python -m eldendisk run --attach -v
```

> ⚠️ **Use `--attach` here.** Without it the tool starts a second copy of the game. And `--attach` only works while the game is
> open; if you closed the game it waits forever at `WAITING_FOR_PROCESS`.

Expected: `[CONNECTED]`. A line like `note: buffs disabled: …` is fine at this point.

**D3.** `[CONNECTED]` only means the numbers were *plausible*. Now check they are *true*. Open `output\disk.json`
and compare with the in-game Status screen — **every row must match exactly**:

| Field                                  | In game | JSON                     |
|----------------------------------------|---------|--------------------------|
| level                                  |         | `character.level`        |
| runes (after the counter stops)        |         | `character.runes`        |
| vigor, mind, endurance, strength       |         | `character.attributes.*` |
| dexterity, intelligence, faith, arcane |         | `character.attributes.*` |

**D4.** Change your runes (gain some, spend some). `character.runes.delta` must go up when you gain and down when you spend.

**D5. Restart test (recommended).** Close the game, run `python -m eldendisk run -v` (this time *without* `--attach`),
load your character and check again. A pointer path that only works for one launch would fail here.

**D6. Order test (only if some attributes have the same value).** If e.g. mind and endurance are both 60, swapped fields look
identical. On a throwaway character raise **one** attribute by one point and confirm that exactly that JSON field (and `level`) goes up by 1.

> 🟢 **Checkpoint D:** level, runes and all eight attributes match the game, `runes.delta` follows your runes, and it still works after a restart. **Stats telemetry is done.** Back up `offsets.json` now.

| What you see                                                         | Meaning                                             | Fix                                                                    |
|----------------------------------------------------------------------|-----------------------------------------------------|------------------------------------------------------------------------|
| `[UNSUPPORTED_VERSION] profile incomplete: <field> is not set`       | a `null` is left in the profile                     | fill the named field                                                   |
| `no profile for exe sha256 …`                                        | hash key does not match                             | copy the hash again from `hash`                                        |
| `[EAC_ACTIVE]`                                                       | the game was started with EAC (Steam Play button)   | close it; start with `run -v`                                          |
| stays `[WAITING_FOR_WORLD]` and nothing is printed                   | you are on the title screen / loading               | load your character                                                    |
| `[WAITING_FOR_WORLD] invalid pointer …` or `read failed: …`          | RVA or first offsets wrong                          | recheck C7 numbers against the result row                              |
| `[WAITING_FOR_WORLD] level=0 outside (1, 713) (PlayerGameData+0x68)` | chain reaches an object but `level` offset is wrong | offsets inside `PlayerGameData` differ on this build                   |
| `[WAITING_FOR_WORLD] runes=… outside 0..999999999`                   | `game_data.runes` wrong                             | recheck Offset 2 from C7                                               |
| `[CONNECTED]` but numbers differ from the game                       | plausible but wrong offset                          | the field offsets are shifted; compare in Cheat Engine or ask for help |

---

## Part E — Buffs (optional, after Part D)

Buffs need the **layout** of the buff list (already filled with starting values in A2 — you *verify* it) and, to be named, the
profile's `inventory` and `params` blocks: since 1.8.2 a buff is named by the held item that gives it (the game's own tables say which
SpEffect each item gives), not by `names.json`.

**E1. Verify the layout.** In-world, run (with the game started by `eldendisk run`):

```powershell
python -m eldendisk read monitor-buffs -q
```

You should see a table with one row per id (`id`, `name`, `timer`, `time`), and it should stay stable.
Equip and unequip one talisman at a Site of Grace: exactly one `permanent` row must go away and come back.

| Message                                                                            | Suspect field                        |
|------------------------------------------------------------------------------------|--------------------------------------|
| `[waiting] read failed: SpecialEffect pointer` / `invalid pointer SpecialEffect=…` | `player_to_sp_effect`                |
| `read failed: SpEffect list head`                                                  | `sp_effect.head`                     |
| `invalid SpEffect entry pointer` / `cycle in SpEffect list`                        | `sp_effect.entry.next`               |
| IDs look random                                                                    | `sp_effect.entry.id`                 |
| permanent buffs do not show `permanent`                                            | `sp_effect.entry.duration` / `timer` |

**E2. Timer direction.** Use a buff that lasts at least 30 s (for example Golden Vow) and watch its row in `read monitor-buffs`:

- timer goes **down** from `duration` towards 0 → `"timer_mode": "remaining"`
- timer goes **up** from 0 towards `duration` → `"timer_mode": "elapsed"`

Set it in the profile. A wrong value does not crash — it reports wrong times with confidence (a fresh 80 s buff would show about 4 s left).

**E3. Collect IDs.** Keep `read monitor-buffs` running and do one thing at a time. Note the `+` rows:

| You do                      | You see (reference build)                                          |
|-----------------------------|--------------------------------------------------------------------|
| unequip / equip Gold Scarab | `311100` goes `-`, then `+` again with `permanent`                 |
| use Gold-Pickled Fowl Foot  | `+ 3971` with a timer of about `180 s`                             |
| cast Golden Vow             | `+ 1660000` with about `80 s` (plus tiny `…001`, `…002` helpers: ignore) |

Ignore anything that flickers with a duration under 1 s (internal engine buffs; `-q` hides them) and anything whose timer stays equal to its duration forever (refreshed every frame, not a real countdown).

**E4. Write `names.json`.** One object, `animations`, keys are the IDs as strings (`read monitor-animations`). Each entry has a `name`, and optionally `categories` and `abilities`. The buffs need no entry (1.8.2): `read monitor-buffs` shows each one with the name of the held item that gives it, and `Unknown` for the rest; a `buffs` object left in an older file is not read.

```json
{
  "animations": {
    "2020110": { "name": "Running", "categories": "MANNER" }
  }
}
```

A 1.6.2 file (one flat list with a `sources` field) is converted by `python code/tools/convert_state_ids.py names.json`. The monitors re-read the file while they run, so names you add show at once.

**E5. End-to-end test.** While a buff is running: `python -m eldendisk read buffs` twice, about five seconds apart.
`buff_duration` must have dropped by about five, `max_duration` must equal the duration you saw, and the buff must vanish when it ends.

> 🟢 **Checkpoint E:** the buffs you configured show correct names and counting-down times in `character.buffs`.

Mapping every ID to an item name can wait. A param editor such as Smithbox lists the `SpEffectParam`, `EquipParamAccessory`
(talismans, link via `refId`), `Goods` (items) and `Magic` (spells) tables; ids you do not list simply count towards `systems.status.ignored.buffs`.

---

## Part F — Wrap-up

1. **Back up** `offsets.json` and `names.json` (or commit them). They are the product of this whole exercise.
2. Fill the sign-off row for your build in the spec (§7.8). Stats verified and restart-tested is "PROVISIONAL"; add a 30-minute session
   with `python tools\soak_check.py` (spec V-06) to call it "VERIFIED".
3. **After the next game patch** run `hash` again. The tool will say `UNSUPPORTED_VERSION` (safe). Add a **new** profile under the
   new hash (keep the old one), set the two `null` values again via Parts B–C, and repeat Part D, E1 and one timed buff of E2.
   Usually only `world_chr_man_rva` and `world_chr_man_to_player` change; verify the rest instead of assuming it.

**Asking for help — please include:**

- the output of `python -m eldendisk hash`, and the game version shown on the title screen
- your profile block from `offsets.json`
- the last lines of `python -m eldendisk run -v` (state and `last_error`)
- a screenshot of the Cheat Engine pointer-scan options dialog and of the result window

---

## Appendix — Reference profile for Elden Ring 1.17.1

Build: app version 1.17.1, `eldenring.exe` file version 2.7.1.0, SHA-256
`1a3547101327f65d0c76da2f9190ac0aa66871ea42bae2aecc61e11a8b597891`.
If your `hash` output is identical, add this block under `"profiles"` in `offsets.json`, then go to Part D3 (or E for buffs).
It reproduces the profile that was verified on this build: stats matched the in-game menu exactly, restart-tested, and the buff timers behave as described in Part E.
(One open item: mind/endurance/faith and strength/dexterity had equal values on the test character, so their order is community-standard but not independently proven — see D6.)

```json
"1a3547101327f65d0c76da2f9190ac0aa66871ea42bae2aecc61e11a8b597891": {
  "label": "Elden Ring 1.17.1",
  "world_chr_man_rva": "0x3B16E30",
  "world_chr_man_to_player": "0x0",
  "player_to_game_data": "0x580",
  "player_to_sp_effect": "0x178",
  "game_data": { "level": "0x68", "runes": "0x6C", "attributes": "0x3C" },
  "sp_effect": {
    "head": "0x8",
    "entry": { "id": "0x8", "next": "0x30", "duration": "0x48", "timer": "0x40", "timer_mode": "remaining" }
  }
}
```

Starter `names.json` for the same build (1.8.2: animations only; the buffs are named by their items):

```json
{
  "animations": {}
}
```

## Quick glossary

| Term             | Meaning                                                                                                   |
|------------------|-----------------------------------------------------------------------------------------------------------|
| **Profile**      | the block in `offsets.json` for one exe hash                                                              |
| **RVA**          | distance from the start of `eldenring.exe` in memory; the `+03B16E30` part of a Cheat Engine base address |
| **Offset**       | a distance added to an address to reach a field inside an object                                          |
| **Pointer path** | base + a few offsets that leads from a fixed spot in the exe to your character                            |
| **Pointer Scan** | the Cheat Engine feature that searches for such paths                                                     |


---

## Required blocks (since 1.5.2)

A profile is pinned to one `eldenring.exe` hash, so nothing is borrowed from another version:

- `vitals` is **required** (`player_to_modules`, `modules_to_data`, `data_to_vitals`). Without it the profile is rejected with `UNSUPPORTED_VERSION: profile incomplete`.
- `at_grace` is `null` (Grace detection off) or `{ "source": "anim", "equals": ["0x109AB"] }`. `equals` is required; there is no default ID.

---

## Optional block: `params` (since 1.6.3)

`params` lets `read` / `write` reach the game's own tables (`SpEffectParam`: the game's table of effects: buffs, burns, ...). It is **optional**: a profile without it still works, and `params` is then `null` in `disk.json` and `write params...` says the game version has no params. A block that is there must be complete, or the profile is rejected (`UNSUPPORTED_VERSION: profile incomplete: params...`). The values of the 1.17.1 profile are in `code/offsets.json`; the way they were found is in `docs/experiments/params/sp-effect-params/sp-effect-params-hypothesis-report.md`.

```json
"params": {
  "file_layout": { "row_count": "0xA", "data_start": "0x30", "descriptors": "0x40",
                   "descriptor_size": "0x18", "descriptor_id": "0x0", "descriptor_data_offset": "0x8" },
  "tables": {
    "effects": {
      "table": "SpEffectParam", "row_size": "0x390",
      "head_chains": [ { "rva": "0x4861FB0", "offsets": ["0x98", "0xE8", "0x130"] } ],
      "fields": { "effectEndurance": { "offset": "0x8", "type": "f32", "writable": true, "min": -1, "max": 9999 },
                  "vfxId":           { "offset": "0x170", "type": "s32", "writable": false } },
      "rows": { "1621000": { "name": "Black Flame", "defaults": { "effectEndurance": 2 } } }
    }
  }
}
```

- **`tables.<name>`:** since 1.8.0 no longer a name you type (`params.effects` is gone): its chains are where `probe` starts looking.
- **`catalog` (1.8.0):** a measured chain per table, by the game's name of the table: `"SpEffectParam": { "rva": "0x3D85F58", "offsets":
  ["0x4C0", "0x80", "0x80"] }`. Six are measured (EquipParamGoods, Magic, SpEffectParam, Bullet, AtkParam_Pc, ShopLineupParam); they win
  for their tables. A name that is not a table of the game is refused.
- **`repository` (1.8.0):** the list the game keeps every table in, for every other table: `{ "rva": "0x3D85F58", "first": "0x88",
  "stride": "0x48", "slots": 256, "tail": ["0x80", "0x80"] }`. Slot n is `[[base + rva] + first + n * stride]`, then the `tail` to the
  file. The tool walks every slot and names each file by its param type, rows, ids, the digest of its rows or the name next to its slot
  (spec 1.8.0 Part 4); `probe` prints every slot with its table, so a new game version can be checked at once. The catalog's chains are
  slots of this list: their offsets give `first` and `stride`.
- **`file_layout`:** a param file in memory starts with a header (row count as `u16`, data start as `u64`), then a table of row descriptors (`descriptor_size` bytes each: row id `u32`, offset of the row data from the file start `u64`), then the rows (`row_size` bytes each). The tool requires `data_start == descriptors + row_count * descriptor_size`; this is how it knows a chain really leads to a param file. Other param files of the game have the same layout, a different `row_size` and different chains.
- **`head_chains`:** `[...[[base + rva] + o1] + o2 ...]` is the **start of the file**: read an 8-byte pointer at `base + rva`, add `o1`, read a pointer there, and so on; the last pointer read is the file head. Cheat Engine lists these offsets the other way round (last applied first) and its final entry is the row field offset, not part of the chain. Give several chains: the first that leads to a valid file is used.
- **`fields`:** offset inside a row, type (`f32` or `s32`), `writable`. A writable field needs `min` and `max` (the range `write` clamps to). Offsets come from the Paramdex definition of the param (`Defs/<Param>.xml`) and are reliable for the fields the definition lists; check one in the game before trusting it.
- **`rows`:** the key is the row **id** (digits, no leading zero), `name` is a text for people (shown as `name` in `disk.json`, never written, and not a field name you can use); every writable field needs its game value in `defaults` (what `write NAME=default` puts back; take it from the CSV export of the param). The tool finds a row by id in the descriptor table. A field called `name` is rejected in `fields`.

To find the chains and the file on a new build: export the rows with Smithbox (view/export only), scan Cheat Engine for the first bytes of one row as an array of byte, find the file head (row count and data start next to it), then run a pointer scan on the head address (static addresses only, 8-byte aligned, level 4, max offset 16383) and keep the paths that are still right after restarting the game twice.

---

## Optional block: `text` (since 1.7.1)

`text` tells `innovate-spells apply` which item-text tables to look for in the game, so it can give the running game a spell's name and description. Optional: without it `innovate-spells apply` says the game version has no `text` block (exit `2`). A block that is there must be complete.

```json
"text": { "files": { "GoodsName": 10, "GoodsInfo": 20, "GoodsCaption": 24 }, "sizes": { "GoodsName": 114880, "GoodsInfo": 164208, "GoodsCaption": 975296 } }
```

No address is kept: the tool **finds** what it changes, by looking through the game's memory (handbook Chapter 19.4). `sizes` is the size in bytes of the game's own table (its `.fmg` file) in the language the game is played in: a table of the right shape and exactly that size is the one wanted. `files` names the three tables and their text file numbers N: the pointer to the table of file N sits at `array + N * 8` in an array that the tool also finds (three pointers to the three tables at exactly these distances). Both keys are required and must name the same three tables.

To fill them in for a new build or language: `tools/dump_msgbnd.py` writes the original tables (their sizes are the file sizes); the numbers N come from the distances between the pointers `tools/probe_text.py` reports for the three tables (Chapter 19.5). Check the result in the game (a rename must show). The sizes in the example are those of the English (engUS) tables of 1.17.1.

## Optional block: `equipment` (since 1.7.2)

```json
"equipment": { "game_data_to_magic": "0x530", "magic_slots": "0x10", "magic_slot_size": "0x8", "magic_slot_count": 14, "magic_selected": "0x80" }
```

Where PlayerGameData keeps the spells memorised in the magic slots: the pointer at `PlayerGameData + game_data_to_magic` leads to a block
whose `magic_slot_count` slots start at `magic_slots`, `magic_slot_size` bytes each, the Magic id first as a 32-bit number (`-1` for an empty
slot); the slot that is selected (0 = the first) is a 32-bit number at `magic_selected`. `read` shows it as `character.equipment.magic`
(`selected.slot` and `selected.id`, `slots` numbered from 1 as the game shows them). Without the block there is no
`character.equipment`; a block that is there must be complete.

How the 1.17.1 values were found (2026-10-13, read-only, the game running): with a spell of the design (Magic 2230000) memorised in the
first slot, a look for that number in PlayerGameData and one pointer away from it found it at `[PlayerGameData+0x530]+0x10`, followed by the
other memorised spells 8 bytes apart; selecting the next slot changed one number only, at `+0x80`, from 0 to 1.

## Optional block: `event_flags` (since 1.8.0)

```json
"event_flags": { "man_rva": "0x3D6C4B8", "divisor": 1000, "holder_size": 125 }
```

Where the game keeps its event flags, for `resurrect great-enemies`: the static at `base + man_rva` points at `CSEventFlagMan`,
whose first member is `CSFD4VirtualMemoryFlag`; the manager must hold `divisor` at `+0x1C` and `holder_size` at `+0x20` (else the
command says the game version moved it). The rest of the layout (the tree of groups at `+0x38`, the blocks at `+0x28`) is in
`game/eventflags.py`. Without the block the great enemies are listed but cannot be read or brought back (exit `2`).

How the 1.17.1 value was found (2026-10-13, read-only, a character in the world): every 8 bytes of the exe's `.data` (13.3 MB) were read
as a pointer, and the one object they point at whose vftable lies in the exe and whose `+0x1C` / `+0x20` are 1000 / 125 was the
manager; one candidate, in 1.9 s. Its tree then gave Godrick's and Margit's defeat flags as the game shows them.

## Optional block: `inventory` (since 1.8.1)

`inventory` tells the reader where PlayerGameData keeps what the character carries (`character.inventory`). Without it there is no
`character.inventory`; a block that is there must be complete.

```json
"inventory": {
  "entry_size": "0x18", "entry_handle": "0x0", "entry_id": "0x4", "entry_quantity": "0x8",
  "items": { "pointer": "0x418", "start": "0x0", "capacity": 2688 },
  "key_items": { "start": "0xB10", "capacity": 384 }
}
```

- **`items`, `key_items`:** a list of `capacity` entries at `[PlayerGameData + pointer] + start`, or at `PlayerGameData + start` when
  there is no `pointer`.
- **`entry_*`:** the size of an entry and where the handle, the item id and the quantity are in it.
- To measure them on a new game version: load a character and run `probe inventory --find <goods id> ...` with the ids of a few items
  whose counts the Inventory menu shows; the lists of 24-byte entries it prints, and the words around each id, give every number above
  (spec 1.8.1 section 4).

The names of the items come from `text.names` (param table -> the numbers of its name text files in `item.msgbnd`, the DLC's last;
`tools/dump_msgbnd.py` lists them): for example `"EquipParamGoods": [10, 319, 419]`.

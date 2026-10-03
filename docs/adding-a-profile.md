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
|  E   | Buffs & Animations: verify layout and fill `chr_state_ids.json`             | 30+ min                     | buffs and animations telemetry       |
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

**D3.** `[CONNECTED]` only means the numbers were *plausible*. Now check they are *true*. Open `output\disk-state.json`
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

Buffs need two things: the **layout** of the effect list (already filled with starting values in A2 — you *verify* it) and a
table of **effect IDs** with names (`effects.json`).

**E1. Verify the layout.** In-world, run:

```powershell
python -m eldendisk effects -q
```

You should see a list, e.g. `--- 8 effects now active ---` with lines `id | duration | timer`, and it should stay stable.
Equip and unequip one talisman at a Site of Grace: exactly one permanent line (`-1.00 | -1.00`) must disappear and come back.

| Message                                                                            | Suspect field                        |
|------------------------------------------------------------------------------------|--------------------------------------|
| `[waiting] read failed: SpecialEffect pointer` / `invalid pointer SpecialEffect=…` | `player_to_sp_effect`                |
| `read failed: SpEffect list head`                                                  | `sp_effect.head`                     |
| `invalid SpEffect entry pointer` / `cycle in SpEffect list`                        | `sp_effect.entry.next`               |
| IDs look random                                                                    | `sp_effect.entry.id`                 |
| permanent effects do not show `-1.00`                                              | `sp_effect.entry.duration` / `timer` |

**E2. Timer direction.** Use a buff that lasts at least 30 s (for example Golden Vow) and watch its line in `effects`:

- timer goes **down** from `duration` towards 0 → `"timer_mode": "remaining"`
- timer goes **up** from 0 towards `duration` → `"timer_mode": "elapsed"`

Set it in the profile. A wrong value does not crash — it reports wrong times with confidence (a fresh 80 s buff would show about 4 s left).

**E3. Collect IDs.** Keep `effects` running and do one thing at a time. Note the `+` lines:

| You do                      | You see (reference build)                                          |
|-----------------------------|--------------------------------------------------------------------|
| unequip / equip Gold Scarab | `- 311100` then `+ 311100 │ -1.00 │ -1.00` → permanent (passive)   |
| use Gold-Pickled Fowl Foot  | `+ 3971 │ 180.00 │ …` → timed (active)                             |
| cast Golden Vow             | `+ 1660000 │ 80.00 │ …` (plus tiny `…001`, `…002` helpers: ignore) |

Ignore anything that flickers with duration under 1 s (internal engine effects) and anything whose timer stays equal to its duration forever (refreshed every frame, not a real countdown).

**E4. Write `effects.json`.** Timed buffs go under `active`, permanent talisman effects under `passive`:

```json
{
  "active": {
    "3971":    { "name": "Gold-Pickled Fowl Foot" },
    "1605000": { "name": "Flame, Grant Me Strength" },
    "1660000": { "name": "Golden Vow" }
  },
  "passive": {
    "311100": { "name": "Gold Scarab", "category": "TALISMAN", "source_name": "Gold Scarab" }
  }
}
```

Allowed `category` values: `TALISMAN`, `ARMOR`, `WEAPON`, `GREAT_RUNE`. Keys are the IDs as strings.

**E5. End-to-end test.** While a buff is running: `python -m eldendisk run --attach -v`, open the JSON twice about five seconds apart.
`remaining_seconds` must have dropped by about five, `max_duration_seconds` must equal the duration you saw, and the buff must vanish when it ends.

> 🟢 **Checkpoint E:** the buffs you configured show correct names and counting-down times in `active_buffs`, talismans appear in `passive_buffs`.

Mapping every ID to an item name can wait. A param editor such as Smithbox lists the `SpEffectParam`, `EquipParamAccessory`
(talismans, link via `refId`), `Goods` (items) and `Magic` (spells) tables; entries you do not list simply count towards `ignored_effects`.

---

## Part F — Wrap-up

1. **Back up** `offsets.json` and `effects.json` (or commit them). They are the product of this whole exercise.
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

Starter `effects.json` for the same build (IDs observed in-game):

```json
{
  "active": {
    "3971":    { "name": "Gold-Pickled Fowl Foot" },
    "1605000": { "name": "Flame, Grant Me Strength" },
    "1660000": { "name": "Golden Vow" }
  },
  "passive": {
    "311100": { "name": "Gold Scarab", "category": "TALISMAN", "source_name": "Gold Scarab" }
  }
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

# Implementation Plan v1.6.3 (IMPLEMENTED, unit tests only)

Feature: **params**, starting with `SpEffectParam`. Read and edit the game's own parameter table in memory, for example make the Black Flame burn permanent. Status: implemented on 2026-10-08, 624 tests pass; `effectEndurance = -1` on all four rows confirmed on the real game by the author (2026-10-08), the rest not yet run. Data and pointer chains were found and validated on the real game (1.17.1) with Cheat Engine. Where the build differs from this plan, section 7 says so.

## 1. What we found (evidence)

| Fact | How it was checked |
|:--|:--|
| The game keeps `SpEffectParam` in memory: 11,354 rows of 912 bytes | Row count and data start read in Cheat Engine match the CSV (11,354 rows, data start 272,560 = 0x40 + 11,354 × 24) |
| `effectEndurance` (f32 @ 0x8): `-1` = permanent, `0` = instant | Smithbox + CSV + game |
| Black Flame rows are used by the player's spells only (NPC rows start at 29000) | CSV |
| Write `-1` into row 1621000 → Black Flame burns the target until it dies | Real game (frog in Mogwyn Palace) |
| Three pointer chains reach the file head; stable across two game restarts | Cheat Engine, all three chains |
| Row address = file head + row data offset (from the row descriptor table) | Verified for 1621000 (head + 0x799188) |

Update 2026-10-08: the author reports that `effectEndurance = -1` works for all four rows. Not yet tried in the game: any field except `effectEndurance`, `--reset`, the title screen. Offsets come from the file layout and Paramdex; the code finds rows by ID and refuses to write when a check fails.

Rows (all `effectEndurance` = 2 by default):

| Name in the tool | Row | Spell |
|:--|:--|:--|
| `black_flame` | 1621000 | Black Flame |
| `scouring_black_flame` | 1623000 | Scouring Black Flame |
| `black_flame_ritual` | 1625000 | Black Flame Ritual |
| `black_flame_blade` | 1626001 | Black Flame Blade (the burn put on the enemy) |

Not included for now: Noble Presence (1624010), Black Flame Tornado (835), Black Flame's Protection (1627000/1627001), weapon burns (855/860). Adding one later = one entry in `offsets.json`.

## 2. What the user sees

### `disk-state.json` (third block, next to `systems` and `character`)

```json
{
  "systems": { "...": "unchanged" },
  "character": { "...": "unchanged" },
  "params": {
    "effects": {
      "black_flame": {
        "effectEndurance": -1.0,
        "motionInterval": 0.1,
        "changeHpRate": 0.1,
        "changeHpPoint": 1,
        "atkOccurrenceSpEffectId": -1,
        "vfxId": 9010
      },
      "scouring_black_flame": { "...": "same six fields" },
      "black_flame_ritual": { "...": "same six fields" },
      "black_flame_blade": { "...": "same six fields" }
    }
  }
}
```

- `params` is `null` while the game is closed or not attached (params edits vanish with the game, so an old value would lie).
- Types: `f32` fields are JSON numbers with a decimal part, `s32` fields are integers.
- `atkOccurrenceSpEffectId` and `vfxId` are shown but **locked** (cannot be written).

### Commands

```text
read  --query params                                          all spells, all fields
read  --query params.effects.1621000.effectEndurance      one value  ->  2.0
write --set   params.effects.1621000.effectEndurance=-1   one field
write --set   "params.effects.*black_flame*.effectEndurance=-1"   lists the 4 names it matched, writes all four
write --reset params.effects.1621000.effectEndurance      one field back to the game default
write --reset params.effects.1621000                      one spell back (all writable fields)
write --reset all                                             every params value back
```

Example output:

```text
$ eldendisk write --set params.effects.1621000.effectEndurance=-1
✓ write params.effects.1621000.effectEndurance = -1.0

$ eldendisk write --set params.effects.1621000.vfxId=0
✗ write params.effects.1621000.vfxId is locked (read-only)        exit 2, nothing written

$ eldendisk write --set "params.effects.1621000.*=1"
· matched: effectEndurance motionInterval changeHpRate changeHpPoint
· skipped (locked): atkOccurrenceSpEffectId vfxId
```

Rules:
- `params.` must be typed in full. No short form, so `effects.…` still means `character.buffs`.
- `--reset` takes a name without `=value`.
- Same gate as every other `write`: a valid `run` session is required, exit 5 otherwise (this includes `--vault-off`).

## 3. Design

### Data: `offsets.json`, new `params` block under the 1.17.1 profile

```json
"params": {
  "file_layout": {
    "row_count": "0xA", "row_count_type": "u16", "data_start": "0x30",
    "descriptors": "0x40", "descriptor_size": "0x18",
    "descriptor_id": "0x0", "descriptor_data_offset": "0x8"
  },
  "SpEffectParam": {
    "head_chains": [
      { "rva": "0x4861FB0", "offsets": ["0x98",  "0xE8", "0x130"] },
      { "rva": "0x3D7D568", "offsets": ["0x148", "0xE8", "0x130"] },
      { "rva": "0x3D85F58", "offsets": ["0x4C0", "0x80", "0x80"]  }
    ],
    "fields": {
      "effectEndurance":         { "offset": "0x8",   "type": "f32", "writable": true,  "min": -1 },
      "motionInterval":          { "offset": "0xC",   "type": "f32", "writable": true  },
      "changeHpRate":            { "offset": "0x9C",  "type": "f32", "writable": true  },
      "changeHpPoint":           { "offset": "0xA0",  "type": "s32", "writable": true  },
      "atkOccurrenceSpEffectId": { "offset": "0x12C", "type": "s32", "writable": false },
      "vfxId":                   { "offset": "0x170", "type": "s32", "writable": false }
    },
    "rows": {
      "black_flame":          { "id": 1621000, "defaults": { "effectEndurance": 2.0, "motionInterval": 0.1, "changeHpRate": 0.1, "changeHpPoint": 1 } },
      "scouring_black_flame": { "id": 1623000, "defaults": { "...": "..." } },
      "black_flame_ritual":   { "id": 1625000, "defaults": { "...": "..." } },
      "black_flame_blade":    { "id": 1626001, "defaults": { "...": "..." } }
    }
  }
}
```

(The `...` default entries are filled in with the CSV values when the file is written.)

- **Defaults live in `offsets.json`** (taken from the game CSV, checked against the game on first read). `--reset` writes the default back and `state` can be computed by comparison. This replaces the earlier idea of saving the original value at the first write: no state file, and `--reset` also works for values changed with Cheat Engine.
- Ranges for writable fields: the minimum and maximum seen in the CSV column across all 11,354 rows, except `effectEndurance` whose minimum is `-1`. Values outside are clamped, with a message (same behaviour as `level`, `vigor`, …).

### Finding a row (no cached addresses, like MW-2)

1. Try the three chains in order (module base + `rva`, follow `offsets`). Take the first head that passes the self-check below.
2. Self-check of the head: `data_start == 0x40 + row_count × 0x18` (11,354 → 0x428B0 ✓). The row count is **not** hard-coded.
3. Read the descriptor table once (about 272 KB), find the row **by ID**, check the data offset lies inside the file.
4. Field address = head + data offset + field offset. Read with the type of the field.
5. Any failed check → skip with a clear message (exit 1), never write blind.

### Code

| Where | Change |
|:--|:--|
| `code/offsets.json` | `params` block above |
| `game/profile.py` | parse and validate the `params` block (unknown field type, duplicate row id, bad hex → profile error) |
| **NEW** `game/params.py` | resolve head, self-check, find row, read field, convert types, compute `state`. Pure over a memory object, no Windows calls |
| `game/values.py` | `params` root; names `params.effects.<name>.<field>`; writable/locked set from the profile; wildcard expansion for `write`; "did you mean" suggestions |
| `reader/sampler.py` + `reader/export.py` | `params` block in the document, read at connect, after a `write`, and about once a second (not every frame); `null` when not attached; `params` changes do not by themselves force an export write more than once per interval |
| `reader/disk.schema.json` | `params` (object or null) |
| `reader/view.py` | `params` in the tree / `--flat` / `--live`; `character.*` does not include it |
| `writer/writer.py` | write one param field (value converted to the field type, clamped, then read back to confirm); `--reset` |
| `commands/write.py`, `__main__.py` | `--reset NAME … | all`; wildcard in `--set`; locked field → exit 2 |
| `__init__.py`, `README.md`, build files | version `1.6.3`; test count |

Architecture rules stay as they are (`game` only imports `game`; `writer` imports `game` and `vault.session`; the host never imports the writer or the reader).

### Not in this version

`character.inventory.*` (no data yet), creating items, other param tables, unlocking `vfxId` / `atkOccurrenceSpEffectId`, any address / scan feature.

## 4. Tests

### Unit (fake memory with a real-looking param file: head, 24-byte descriptors, 912-byte rows)

- `test_params.py`: first chain broken → second used; all chains broken → clear error; head self-check fails (wrong `data_start`) → skipped; row id missing → error; data offset out of range → error; read f32 / s32; write then read back; `-1` round trip; field and row addressing equals the values measured in Cheat Engine (0x799188 for 1621000 on a 11,354-row file).
- `test_values.py`: `params.…` names, wildcard, no short form (`effects.black_flame` stays `character.buffs`), suggestions for typos, locked fields not in the writable set.
- `test_write_command.py`: `--set` param; locked field → exit 2 and no write handle opened; wildcard skips locked and lists matches; `--reset` at three levels; clamp message; no session → exit 5; vault OFF → exit 5; `--reset` without a name / with `=value` → usage error.
- `test_export.py` / `test_read_command.py`: `params` block present and valid against the schema; `null` when disconnected; `state` default / modified / mixed; `read --query params…`; `--flat`; `--live` change highlight; `character.*` excludes `params`.
- `test_profile_policy.py`: `params` block parsing and errors.
- `test_architecture.py`: still passes.
- Target: all of the 494 existing tests still pass, plus the new ones; pyflakes clean.

### Manual on the real game (appended to `manual-test-plan-1.6.3.md`, section 7 "params")

Setup: `T0 = eldendisk run`, a loaded character with Black Flame equipped, a target that does not die at once (the frog in Mogwyn Palace works). Copy the save folder first.

| ID | Do | Expect | |
|:--|:--|:--|:-:|
| PA1 | `read --query params` | 4 spells × 6 fields; `effectEndurance` = 2.0, `vfxId` = 9010, `atkOccurrenceSpEffectId` = -1 for each; exit 0 | [ ] |
| PA2 | `read --query params.effects.1621000.effectEndurance` and `--json` | `2.0`; valid JSON | [ ] |
| PA3 | `read --export` | `params` block present; file valid against the schema; `character.*` and `systems` unchanged | [ ] |
| PA4 | T1: `write --set params.effects.1621000.effectEndurance=-1`, then cast Black Flame on the frog | `✓ write …`; the burn stays until the target dies | [ ] |
| PA5 | `read --query params.effects.1621000` | `effectEndurance` -1.0; the other fields unchanged | [ ] |
| PA6 | Same as PA4 for `scouring_black_flame`, `black_flame_ritual`, `black_flame_blade` (one at a time, reset in between) | each burns permanently with its own spell and **only** with it; write down which ones fail (not yet tried in the game) | [ ] |
| PA7 | `write --set "params.effects.*black_flame*.effectEndurance=-1"` | lists exactly the 4 names, writes 4 values | [ ] |
| PA8 | `write --reset params.effects.1621000.effectEndurance`; then `--reset params.effects.1621000`; then `--reset all` | values return to the defaults (2.0); a new cast burns about 2 s again | [ ] |
| PA9 | Burn already applied before the write | a burn started before the edit still ends by its old duration; a new cast uses the new value | [ ] |
| PA10 | `write --set params.effects.1621000.vfxId=0` and `…atkOccurrenceSpEffectId=0` | exit 2, "locked", nothing changed (`read` shows 9010 / -1); also with no `run` session | [ ] |
| PA11 | `write --set "params.effects.1621000.*=1"` | writable fields written, locked ones listed as skipped | [ ] |
| PA12 | `write --set params.effects.1621000.effectEndurance=-5` | clamped to -1 with a message; `=abc` → error, exit 1 | [ ] |
| PA13 | `write --set params.effects.black_flam.effectEndurance=-1` | exit 1, "did you mean … black_flame"; `effects.black_flame…` (no `params.`) is rejected for `write` | [ ] |
| PA14 | `read --query effects` | still the character's active effects, not params | [ ] |
| PA15 | Same edit with no session: T0 stopped / game started from Steam | exit 5 (no valid session) or exit 3 (EAC); nothing written | [ ] |
| PA16 | `run --vault-off`, then `write --set params…` | exit 5 (same gate) | [ ] |
| PA17 | `read --live --query params.effects.1621000` in T1, `write` in T2 | the value changes within about a second, highlighted | [ ] |
| PA18 | Quit the game with `-1` still set, start it again (`run`), `read --query params…` | back to the defaults, `state` default; `read --export` while the game is closed gives `"params": null` | [ ] |
| PA19 | At the title screen (no character loaded): `read --query params` | note what happens (values, or a clear "not ready" message); no crash | [ ] |
| PA20 | `read --live --export` for about 10 minutes with `params` | CPU stays low; the file is not rewritten when only params are unchanged; no errors in the log | [ ] |
| PA21 | Regression: quickly repeat Q1–Q3, X1, L1, and `write --set level=…` | unchanged behaviour; `character.*` does not contain `params` | [ ] |
| PA22 | README / `write -h` | `--reset` documented; warnings present: offline `run` only (online play risks a ban), edits vanish when the game closes, a burn that is already on keeps its old duration | [ ] |

## 5. Docs and release

- New: `docs/specs/elden-disk-spec-v1.6.3.md`, `docs/wahy/changes-version-1.6.3.md`, `docs/manual-test-plan-1.6.3.md` (1.6.2 plan + section 7), this plan.
- Update: `README.md` (version, commands, export example, warnings), `docs/cli-commands.md`, `docs/cli-commands-exe.md`, `docs/adding-a-profile.md` (how to find the `params` chains and rows).
- Build the zip after the tests pass; do not run the build pipeline while a session record exists.

## 6. Decisions (settled by the project owner, 2026-10-08)

1. Params edits use the **same gate** as every `write`: allowed only inside a valid `run --vault-on` session; `--vault-off` refuses them (exit 5).
2. `--reset` writes the **defaults stored in `offsets.json`** (from the CSV), not a saved original.

## 7. As built (differences from the plan above)

| Plan | Built | Why |
|:--|:--|:--|
| `offsets.json` key `SpEffectParam` | `params.tables.effects` with `"table": "SpEffectParam"`, `row_size` and `head_chains` inside the table | the interface name (`params.effects…`) and the table key are the same; more tables later without renaming |
| `motionInterval` min = CSV minimum | min `0.01` | a zero or negative tick interval was never given to the game |
| locked field refused before anything | refused after `locate` (profile known), before the session check | the lock lives in the profile |
| document had `state` (default/modified) | dropped | needs a comparison on every sample, adds nothing the values do not show |
| `test_values.py`, `test_export.py`, `test_profile_policy.py` | cases are in `test_params.py`, `test_write_command.py`, `test_read_command.py`, `test_memory_writer.py` | tests sit next to what they test |
| PA1-PA22 | PA1-PA23 in `manual-test-plan-1.6.3.md`, section 7A (reset split into its own cases; clamp, refused values, `--reset` misuse and the title screen separated) | finer steps for the real game |

**Revised the same day (project owner):** (1) rows are addressed by id, `params.effects.<id>.{name, ...six fields}`, `name` locked, no snake_case names; `offsets.json` rows are `"1621000": {"name": "Black Flame", "defaults": {...}}`. (2) `chr_state_ids.json` is `{"buffs": {...}, "animations": {...}}` without `sources`, and "effects" became "buffs" everywhere the tool speaks (`--live-buffs`, `--state-ids`, `character.buffs`, `buffs_supported`, `ignored.buffs`); `params.effects` and `sp_effect` keep the game's word. Everything above that still shows spell names (`black_flame`...) or `character.effects` is the first draft: spec 1.6.3 is the reference.

Files changed: `offsets.json`, `game/profile.py`, `game/params.py` (new), `game/values.py`, `reader/{sampler,export,view,disk.schema}`, `writer/writer.py`, `commands/{read,write}.py`, `__main__.py`, `__init__.py`; tests `paramfile.py`, `test_params.py` (new) and four existing test files; docs listed in section 5.
Result: 624 passed, 1 skipped; `pyflakes` clean.

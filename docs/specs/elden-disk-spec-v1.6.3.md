# EldenDisk Memory I/O Tools
> **Document Version:** 1.6.3 (revised from 1.6.2) · **Status:** IMPLEMENTED (tests only; real-game verification open, section 9)
> **Date of Issue:** 2026-10-08
> **Target Platform:** Windows 10 / 11 (x64), Python 3.11+ (64-bit) · **Game:** Elden Ring 1.17.1

1.6.3 adds **params**, the game's own parameter tables read and edited in memory (first table: `SpEffectParam`, the four Black Flame rows; for example, make the burn permanent), and renames the character's *effects* to **buffs** together with a new shape of `chr_state_ids.json` (section 2.1). **Everything not mentioned here behaves as in [1.6.2](elden-disk-spec-v1.6.2.md)** (host, vault, session record, exit codes, monitors, export policy). Evidence and the reasoning: `docs/experiments/params/sp-effect-params/`.

## 1. Roles and commands

The writer gains `--reset` and the `params` names; the monitor flags are renamed (section 2.1).

| Command | Change |
|:---|:---|
| `read` | the document has a third block, `params` (section 3). `read --query params…` works like any other name. `--live-effects` is now `--live-buffs`, `--effects FILE` is `--state-ids FILE` (section 2.1) |
| `write --set NAME=VALUE ...` | `NAME` may be a `params.…` name (section 5) |
| `write --reset NAME [NAME ...]` | **new.** Puts `params` values back to the game's own values. Takes `params.…` names or `all` |

Other roles are unchanged (the host and the vault know nothing of buffs or params): `run` never opens the game for memory access, `vault` and the session record are untouched.

## 2. Modules and dependency rules

| Module | Change |
|:---|:---|
| `game/profile.py` (params) | optional `params` block of a profile: `ParamsProfile` (`layout`, `tables`), `ParamTable`, `ParamField`, `ParamRow`, `ParamChain`. Absent block = no params for that exe (`Profile.params is None`). A present block must be complete and consistent, else the profile is `Incomplete` (section 4) |
| **`game/params.py`** (new) | **read-only.** Finds the param file, checks it, finds rows by id, decodes fields, matches names. Resolves addresses but never writes |
| `game/values.py` | `params` is a root of the names; `params.…` paths skip the aliases and the implicit `character.`; `is_param_name()`; `buff` is an alias of `buffs` |
| `game/profile.py` (`load_state_ids`) | `chr_state_ids.json` is read into `StateIds(buffs, animations)`, two tables of `StateConfig(name, categories, abilities)` (section 2.1) |
| `reader/buffs.py` (was `effects.py`) | `BuffsMonitor` for `--live-buffs`; `BuffsMonitor.table` / `AnimationsMonitor.table` are the two name tables |
| `reader/sampler.py`, `reader/export.py`, `reader/disk.schema.json`, `reader/view.py` | `params` in the sample, in the document, in the schema, in the tree/`--flat`/`--live` views (section 3) |
| `writer/writer.py` | `ParamEdit`, `plan_params`, `MemoryWriter._tick_params`; the only place that writes (MW-1) |
| `commands/write.py`, `__main__.py` | `--reset`, params planning between `locate` and `authorise` |

Dependency rules are unchanged and still enforced by `test_architecture.py`: `game` imports only `game`; `writer` imports `game` and `vault.session`; the write capability exists only in `writer/writer.py` (so `game/params.py` has `mem.read` only); `commands/write.py` is the only user of the writer.

### 2.1 Buffs, and the shape of `chr_state_ids.json`

"Effects" of the character are called **buffs** everywhere the tool speaks (the game's own word, *SpEffect*, stays where it names the game's structures: `sp_effect` in a profile, `SpEffectParam`, `params.effects`).

| 1.6.2 | 1.6.3 |
|:---|:---|
| `read --live-effects` | `read --live-buffs` |
| `read --effects FILE` | `read --state-ids FILE` |
| `character.effects` | `character.buffs` |
| `systems.features.effects_supported` | `systems.features.buffs_supported` |
| `systems.status.ignored.effects` | `systems.status.ignored.buffs` |
| name `effects` (alias of `character.effects`) | name `buffs` (alias `buff`); a bare `effects` is no longer a name |
| `chr_state_ids.json`: one flat `{id: {name, sources, categories, abilities}}` | `{"buffs": {id: {name, categories?, abilities?}}, "animations": {id: {...}}}` |

- **`sources` is gone.** It only told buffs from animations; the two objects do that now. An id may be in both objects (two tables). The legacy fallbacks (`effects.json`, singular `category`/`ability`) are gone too.
- Unchanged: the entries of `character.buffs` / `character.animations` (`name`, `categories`, `abilities`, `times`), the monitors, `--mapped` / `--unmapped`, `-q`, the reload every 2 s.
- A file in the old flat shape (or any object without `buffs` or `animations`) is refused **before the game is looked for**: `read` exits `1` with `malformed …: expected an object with "buffs" and "animations" (an old flat file? python tools/convert_state_ids.py FILE converts it)`. A file that changes to a bad one while a monitor runs keeps the old names and warns, as before. A missing file means empty tables.
- `tools/convert_state_ids.py FILE [--out NEW]` converts the old shape (entries with `sources: "ANIMATIONS"` go to `animations`, all others to `buffs`; keeps `FILE.bak` unless `--out` is given).

## 3. The `params` block of `disk-state.json`

Third block after `systems` and `character`:

```json
"params": {
  "effects": {
    "1621000": {
      "name": "Black Flame",
      "effectEndurance": 2.0, "motionInterval": 0.1, "changeHpRate": 0.1, "changeHpPoint": 1,
      "atkOccurrenceSpEffectId": -1, "vfxId": 9010
    },
    "1623000": { "name": "Scouring Black Flame", "...": "same six fields" },
    "1625000": { "name": "Black Flame Ritual",    "...": "same six fields" },
    "1626001": { "name": "Black Flame Blade",     "...": "same six fields" }
  }
}
```

- Shape: `params.<table key>.<row id>.<field>`; the row is its game id (a string key), in the order of the profile; each row starts with `name` (a string from the profile, never read from the game) followed by the six fields. 4 rows × (name + 6 fields) in 1.6.3.
- `null` when no game is attached, the exe is unsupported or EAC is loaded, and when the profile has no `params` block. A table that cannot be read right now (file not found, a check failed) makes the whole block `null` for that sample (correct-or-silent); the sampler asks again every 0.25 s until it works, then every 1.0 s.
- Types: `f32` fields are JSON numbers always written with a decimal part (`-1.0`), shown to 7 significant digits (`0.1`, not `0.10000000149011612`); `s32` fields are integers. The console prints ids without thousands separators.
- Schema (`disk.schema.json`): `params` is optional, object or null; `effects` maps ids (digits) to objects that require `name` (a string) and the six fields (three numbers, three integers). A 1.6.2 document stays valid.
- `read` without a name ends with the `params` tree. `character.*` does not include it. A name that does not start with `params.` never means a params value (`effects` alone is not a name any more).

## 4. The `params` block of `offsets.json` (profile)

```text
params
├─ file_layout   row_count 0xA (u16) · data_start 0x30 (u64) · descriptors 0x40 · descriptor_size 0x18
│                descriptor_id 0x0 · descriptor_data_offset 0x8
└─ tables
   └─ effects    table "SpEffectParam" · row_size 0x390
      ├─ head_chains   3 × { rva, offsets }   (tried in order)
      ├─ fields        name → { offset, type f32|s32, writable, min, max }   (not called `name`)
      └─ rows          "<id>" → { name (text), defaults {writable field → value} }
```

Validation (any failure = `Incomplete`, the exe is treated as unsupported): hex/number parse, `type` known, `offset + 4 <= row_size`, a writable field has `min` and `max`, no duplicate field names (case-insensitive) and none called `name`, every row key an id (digits, no leading zero) with a non-empty `name`, every writable field has a default inside its range, locked fields have none, no empty chains, fields, rows or tables.

The table key is `effects` (the name in the interface); the game's own name is the `table` value.

Fields (1.17.1, offsets from the row start, as in Paramdex and checked in Cheat Engine for row 1621000):

| Field | Offset | Type | Writable | Range | Meaning |
|:---|:-:|:-:|:-:|:-:|:---|
| `effectEndurance` | 0x8 | f32 | yes | -1 … 9999 | seconds; `-1` permanent, `0` instant; game value 2 |
| `motionInterval` | 0xC | f32 | yes | 0.01 … 999 | seconds between ticks; game value 0.1 |
| `changeHpRate` | 0x9C | f32 | yes | -100 … 100 | % of max HP per tick; game value 0.1 |
| `changeHpPoint` | 0xA0 | s32 | yes | -9999 … 999 | HP per tick; game value 1 |
| `atkOccurrenceSpEffectId` | 0x12C | s32 | **no** | | another SpEffect put on whoever is hit; `-1` none |
| `vfxId` | 0x170 | s32 | **no** | | visual effect; 9010 |

Ranges are the observed minimum and maximum of the CSV column, except `effectEndurance` (minimum `-1`) and `motionInterval` (minimum raised from the CSV's `-1` to `0.01`: a zero or negative interval is a risk the game was never given). The two id fields are locked on purpose: a wrong id may crash the game.

Rows: `1621000` Black Flame, `1623000` Scouring Black Flame, `1625000` Black Flame Ritual, `1626001` Black Flame Blade. Not included: Noble Presence (1624010), Black Flame Tornado, Black Flame's Protection, weapon burns. Adding a row is one `rows` entry.

## 5. Names and the writer

### 5.1 Names

`params.effects.<id>.<field>`, typed **in full** (no short form) and in any letter case (`params.effects.1621000.effectendurance` works; `read` shows the canonical spelling). Patterns use `fnmatch` on the lower-cased path: `params.effects.*.effectEndurance` (every row), `params.effects.1621000.*` (every field of one row). `name` is the first value of every row: it can be read, and it is **locked**: named exactly it is refused like a read-only field (exit 2); in a pattern it is skipped without being listed (it is not a game value). Unknown names fail with the closest candidates (`did you mean …`).

### 5.2 `--set`

- One field per name, a number after `=`: a decimal for `f32`, a whole number for `s32`; `_` is ignored. Anything else (`abc`, `1.5` for an s32, nothing after `=`) is an error, exit 1, nothing written.
- A group (`params.effects.1621000`) is refused; a pattern may stand for many values. A pattern that matches several values prints `X matches N values: …`.
- A **locked** field named exactly is refused: exit 2, `is locked (read-only)`, nothing written. In a pattern, locked fields are skipped and listed (`skipped (locked): …`); a pattern that matches only locked fields is refused like the exact name.
- Out-of-range values are clamped and the result line says so: `(clamped from -5 to the allowed -1..9999)`.
- A name given twice, or in `--set` and `--reset`, is a usage error.

### 5.3 `--reset`

`--reset NAME [NAME ...]` (repeatable). `NAME` is a field, a row (its writable fields), a table (`params.effects`), or `all` (every writable params value). A pattern is allowed. It writes the **defaults stored in `offsets.json`**, not a saved original: no state file, and it also fixes values changed by other means. `--reset` with `=value`, or with a name that is not `params…`, is rejected (exit 1): the 13 character values have no stored default.

### 5.4 Gate and flow

Same gate as every write (1.6.2, section 3): a valid session record whose host is alive and whose snapshot is verified, the attached game being the recorded process. `run --vault-off` therefore refuses params edits (exit 5).

`write`: parse → load the session record → `locate` (EAC refused, profile for this exe) → **plan params** → `authorise` (exit 5) → open `WritableProcessMemory` → apply → read back → close.

- Planning needs the profile, so a locked field is refused only once the game was found (exit 2, as before for other refused names), but **before** the session check.
- Each write: follow the chains again (nothing is cached, MW-2), check the file, find the row by id, re-check that the field is writable, clamp, write 4 bytes, read them back. A failed check skips that edit with its reason and the command exits 1; it never writes blind.
- Reading the file (`game/params.py`): try each chain in order and take the first head that passes: `data_start == 0x40 + row_count × 0x18` (the row count is read, not hard-coded; 0 < count ≤ 100,000). Read the descriptor table once, find the wanted ids, require each data offset to lie inside the data and on the row grid. One failed check stops the whole read.
- A burn already on a target keeps the duration it was applied with; a new cast uses the new value. Edits are in game memory only: they vanish when the game closes and are never written to the save.

## 6. Exit codes

Unchanged: `0` ok · `1` error / not applied · `2` unsupported exe **or a read-only params field named in `write`** · `3` EAC loaded · `4` restore pending · `5` no valid session · `130` interrupted.

## 7. Tests

624 pass, 1 skipped (Linux, fake memory). New: `tests/test_convert_state_ids.py`, state-ids loader and read-command tests, `tests/paramfile.py` (a fake param file of the real layout, also at the real size of 11,354 rows with the Black Flame rows at their measured indexes) and `tests/test_params.py` (62 tests); params cases added to `test_write_command`, `test_memory_writer`, `test_read_command`. The real-size test asserts the same offsets as Cheat Engine: `effectEndurance` of 1621000 at head + `0x799188`, and 1623000 / 1625000 / 1626001 at `0x799518` / `0x799FC8` / `0x79A6E8`.

## 8. Implementation order (tests green after each step)

1. Profile block and parser (`game/profile.py`), then `game/params.py` with the fake param file.
2. Names (`game/values.py`), then reader: sampler, document, schema, view.
3. Writer: edits, planning, `_tick_params`, `--reset`; `commands/write.py`, `__main__.py`.
4. README, CLI docs, adding-a-profile, manual plan section 7A, this spec, changes; version 1.6.3.

## 9. Real-game evidence and open items

**Seen on the real game (1.17.1, Cheat Engine, reported by the author, 2026-10)**
- The table is in memory as one file of 11,354 rows of 912 bytes; row count (u16 at +0xA) and data start (u64 at +0x30, 272,560) match the CSV.
- Row 1621000 `effectEndurance` is at head + `0x799188`; writing `-1` made the Black Flame burn until the target died.
- The three pointer chains reach the same head and survived two restarts of the game. Level 3 / offset 4095 found no path; level 4 / offset 16383 found 32.
- Three copies of the table exist in memory; the live one is at the highest address. What the other copy (lower address) does was not recorded.

**Still open** (code from this release was **not run on real Windows**)
- Rows 1623000, 1625000, 1626001: positions derived from the file layout (same arithmetic as the measured row); the author expects them to work. Test PA6.
- Fields other than `effectEndurance`: offsets from Paramdex, not measured. Tests PA8, PA10.
- The title screen (no character loaded): reading and writing there. Test PA20.
- The buffs rename and the new `chr_state_ids.json` are covered by unit tests only; real-game checks are M14-M16 in the manual plan (the monitors themselves were seen working in 1.6.2).
- Earlier open items of 1.6.2 (T10 Steam Cloud, console close, Registry vault path …) are unchanged.
- **Out of scope:** `character.inventory.*` (no data yet), creating items, other param tables, unlocking `vfxId` / `atkOccurrenceSpEffectId`, any address, scan or raw read/write feature in the interface.

**Warnings** (also in the README): use offline through `eldendisk run` only, because changed params online risk a ban; edits vanish when the game closes; keep a manual backup of the save folder.

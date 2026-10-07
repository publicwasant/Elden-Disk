> [!NOTE]
> **Version:** `1.6.3`  
> **Status:** IMPLEMENTED (unit tests only; real-game verification still open, see spec 1.6.3 section 9)  
> **Last Updated:** _2026-10-08_

**Summary:** **Params**: the tool reads and edits the game's own `SpEffectParam` table in memory, starting with the four Black Flame rows (for example, make the burn permanent with `effectEndurance = -1`). Also, the character's *effects* are now called **buffs** and `chr_state_ids.json` has a new shape (`buffs` / `animations` objects, no `sources`). Host, vault, session record and the rest of 1.6.2 are unchanged.

_(baseline: **[changes-version-1.6.2.md](changes-version-1.6.2.md)**; design: **[elden-disk-spec-v1.6.3.md](../specs/elden-disk-spec-v1.6.3.md)**; evidence: `docs/experiments/params/sp-effect-params/`)_

---

## Wahy

| # | Change | Where |
|:-:|:---|:---|
| 1 | **`params` block in `disk-state.json`.** Third block after `systems` and `character`: `params.effects.<id>.{name, effectEndurance, motionInterval, changeHpRate, changeHpPoint, atkOccurrenceSpEffectId, vfxId}`: the row is its game id, `name` its text from the profile (shown, never written). `null` when no game is attached or the table cannot be read. Optional in the schema, so a 1.6.2 document stays valid. | `reader/export.py`, `reader/disk.schema.json` |
| 2 | **Four rows.** `1621000` Black Flame, `1623000` Scouring Black Flame, `1625000` Black Flame Ritual, `1626001` Black Flame Blade. Adding another is one entry in `offsets.json` (`"<id>": {"name": ..., "defaults": ...}`). | `offsets.json` |
| 3 | **`offsets.json` `params` block** per exe profile: file layout, pointer chains, fields (offset, type, writable, range), rows with their default values. Optional; a present block that is incomplete or inconsistent makes the profile `Incomplete`. | `game/profile.py`, `docs/adding-a-profile.md` |
| 4 | **Read-only param access.** New `game/params.py`: follows three pointer chains, self-checks the file (`data_start == 0x40 + rows × 0x18`), finds rows **by id**, never by position, caches nothing, and stops the whole read on one failed check. | `game/params.py` |
| 5 | **Names.** `params.effects.<id>.<field>`, typed in full and in any letter case; `fnmatch` patterns (`params.effects.*.effectEndurance` = every row); "did you mean" for typos. | `game/values.py`, `reader/view.py` |
| 6 | **`write --set params.…=VALUE`**, one value or a pattern (`params.effects.*.effectEndurance=-1` writes all four rows). The value is converted to the field type, clamped to its range (with a visible note) and read back. | `writer/writer.py`, `commands/write.py` |
| 7 | **`write --reset NAME [NAME …]`.** A field, a row, `params.effects` or `all`; writes the defaults stored in `offsets.json` (from the CSV), so it needs no saved original and also fixes values changed by other tools. | `writer/writer.py`, `__main__.py` |
| 8 | **Locked values.** `atkOccurrenceSpEffectId` and `vfxId` are shown but cannot be written (a wrong id may crash the game); `name` is shown and never written. Named exactly: exit `2`. In a pattern: skipped (the two ids are listed, `name` is not). | `offsets.json`, `game/params.py` |
| 9 | **Same gate as every write.** Params edits need a valid `run --vault-on` session; `--vault-off` and a game started from Steam get exit `5` / `3`. | `commands/write.py` |
| 10 | **Reader cadence.** Params are sampled at most once a second (`0.25 s` retry while unreadable), so `read --live --export` does not pay for them every frame and does not rewrite the file when only unchanged params are read. | `reader/sampler.py` |
| 11 | **Tests.** 624 pass, 1 skipped. New `tests/paramfile.py` (a fake param file; also at the real size, 11,354 rows, asserting the offsets measured in Cheat Engine) and `tests/test_params.py` (62 tests); params cases in the write, writer and read tests. | tests |
| 12 | **Buffs, not effects.** `read --live-effects` → `--live-buffs`; `--effects FILE` → `--state-ids FILE`; `character.effects` → `character.buffs`; `features.effects_supported` → `buffs_supported`; `status.ignored.effects` → `.buffs`; the name `effects` → `buffs` (alias `buff`). `params.effects` and the profile's `sp_effect` keep the game's word. | `reader/`, `commands/read.py`, `__main__.py`, `game/values.py`, schema |
| 13 | **New `chr_state_ids.json`.** `{"buffs": {id: {...}}, "animations": {id: {...}}}`. The `sources` field is gone (the two objects say it), an id may be in both objects, the old `effects.json` / singular `category` fallbacks are gone. The old flat file is refused up front with a hint; `tools/convert_state_ids.py` converts it. | `game/profile.py` (`load_state_ids`), `chr_state_ids.json`, `tools/convert_state_ids.py` |
| 14 | **Docs.** Hypothesis report H1-H8 with the Cheat Engine evidence; spec, plan and manual test plan 1.6.3 (section 7A, PA1-PA23); README, CLI docs. | `docs/` |

## Behaviour changes

- `disk-state.json` changed: `character.effects` is `character.buffs` (and the two names under `systems`); anything that reads the file (for example the soak check, already updated) must follow. The schema is updated.
- Your own `chr_state_ids.json` must be converted once: `python code/tools/convert_state_ids.py chr_state_ids.json` (a `.bak` is kept). Until then `read` exits `1` with that hint.
- `read` without a name now ends with the `params` tree; `read --export` writes it. `character.*` does not include it.
- `write` has `--reset`. Without params names nothing else changes: the 13 character values keep their names, ranges and exit codes.
- Exit `2` now also means "a read-only params field was named in `write`".
- Params edits live in game memory only: they vanish when the game closes and are never written to the save. Use offline (`eldendisk run`); changed params online risk a ban.

## Decisions taken while implementing

- **Rows by id.** After the first draft (rows named `black_flame`...), the project owner asked for `params.effects.<id>` with a `name` value, so a row is the id the game uses and nothing is invented. There are no snake_case aliases.
- **`--effects` became `--state-ids`**, not `--buffs`: the file holds buffs and animations, and the option is its path.
- **Names in the profile:** the table is `params.tables.effects` in `offsets.json` (the plan said `SpEffectParam`); `SpEffectParam` is its `table` value. The interface name `effects` matches `params.effects…`.
- **`motionInterval` minimum is `0.01`**, not the CSV's `-1`: a zero or negative tick interval was never given to the game, and the cost of testing it is a freeze.
- **Locked fields** are refused as soon as the game is found (profile known) and before the session check, so the answer is the same with or without `run`. This needs the game process to exist.
- **No `state` field** (default/modified) in the document: it would need a comparison with the defaults on every sample and says nothing the values do not. `--reset` is enough.
- **Defaults from `offsets.json`**, not a copy saved at the first write: no state file to lose.
- **One table copy only.** The game keeps three copies of the table in memory; the chains lead to the live one. Whether the other copy matters is unknown (see open items).

## Not done / open

- Real game, reported by the author (2026-10-08): `effectEndurance = -1` makes **all four** Black Flame rows burn without end (PA4 and PA6 as far as `effectEndurance` goes). Not reported yet: the other fields (PA8, PA10), `--reset` (PA9), the title screen (PA20), the buffs rename and the new `chr_state_ids.json` (M14-M16).
- `character.inventory.*`: postponed (no data yet).
- The earlier open items of 1.6.2 (T10 Steam Cloud and the others in spec 1.6.2 section 9) are unchanged.

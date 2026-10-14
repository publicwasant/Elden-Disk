"""Developer tool (not shipped): the great-enemies table of `resurrect` (spec 1.8.0 section 4) from the game's own
files, read-only. Writes eldendisk/creative/resurrect/great_enemies/great_enemies.json.

    python tools/gen_great_enemies.py [--game DIR] [--out FILE]

What comes from where (all from the game folder; nothing is written there):
  regulation.bin  GameAreaParam (every row with a defeat flag: the runes, the map, the boss's position),
                  BonfireWarpParam + BonfireWarpSubCategoryParam (the graces: position, name, the place they are listed under),
                  ItemLotParam_map / _enemy (what a lot gives and its flag)
  /event/*.emevd  the boss's events: the defeat event (it sets the defeat flag and the play-log flag `9xxx`; `2003[12]` names the
                  boss's entity), the health bar (`2003[11]`: the NpcName text the game shows), the intro (a cutscene, then the
                  flags it sets ON), the lots its events give (`2003[36]`, `2003[4]`), the graces it lights (common event 9005810)
  common.emevd    event 0 starts event 1100 once per Remembrance: (play-log flag, lot, 0, lot flag)
  /msg/engUS      NpcName (the boss), PlaceName (graces), GR_MenuText (the place a grace is listed under), GoodsName/... (drops)

Rows the scripts do not explain are kept with what is known (`drop: []`, `grace: null`); `OVERRIDES` holds what a person checked.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import gamearchive as ga  # noqa: E402
from dump_msgbnd import bnd4_files, undcx  # noqa: E402
from eldendisk.creative.innovate_spells import container, zstd  # noqa: E402
from eldendisk.creative.innovate_spells.container import Bnd4  # noqa: E402
from eldendisk.creative.innovate_spells.fmg import Fmg  # noqa: E402

DEFAULT_GAME = Path(r"C:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game")
OUT = HERE.parent / "eldendisk" / "creative" / "resurrect" / "great_enemies" / "great_enemies.json"
DLC_AREAS = {20, 21, 22, 25, 28, 40, 41, 42, 43, 61}
# the bosses whose death the story waits on (spec 1.8.0 section 4, accepted 2026-10-13), by the name the game shows
STORY = ("Margit, the Fell Omen", "Godrick the Grafted", "Rennala", "Starscourge Radahn", "Morgott", "Rykard", "Malenia", "Mohg, Lord of Blood",
         "Fire Giant", "Godskin Duo", "Maliketh", "Sir Gideon Ofnir", "Godfrey", "Hoarah Loux", "Radagon", "Elden Beast", "Messmer",
         "Romina", "Midra", "Bayle", "Promised Consort Radahn", "Rellana", "Commander Gaius", "Putrescent Knight", "Metyr")
CATEGORY = {1: "Goods", 2: "Weapon", 3: "Protector", 4: "Accessory", 5: "Gem"}
OVERRIDES: dict[int, dict] = {}       # row id -> fields a person checked in the game (merged last)


# ---------------------------------------------------------------------------------------------------------------- the game's files
class Game:
    def __init__(self, folder: Path):
        self.folder = folder
        exe = (folder / "eldenring.exe").read_bytes()
        keys = ga.keys_from_exe(exe)
        names = [n for n in ("Data0", "Data1", "Data2", "Data3", "DLC") if (folder / f"{n}.bhd").is_file()]
        self.indexes = [(n, ga.parse_index(ga.decrypt_index((folder / f"{n}.bhd").read_bytes(), keys[i])))
                        for i, n in enumerate(names) if i < len(keys)]
        dcx = container.decrypt((folder / "regulation.bin").read_bytes())
        csize = struct.unpack(">I", dcx[0x20:0x24])[0]
        self.bnd = Bnd4(zstd.decode_frame(dcx[0x4C:0x4C + csize]))
        self._texts: dict[str, dict[int, str]] = {}

    def read(self, path: str) -> bytes | None:
        h = ga.path_hash(path)
        for n, ix in self.indexes:
            e = ix.get(h)
            if e is not None:
                with open(self.folder / f"{n}.bdt", "rb") as f:
                    return undcx(self.folder, ga.read_entry(f, e))[1]
        return None

    def table(self, name: str) -> dict[int, bytes]:
        blob = self.bnd.get(name).data
        n = struct.unpack_from("<H", blob, 0xA)[0]
        strings = struct.unpack_from("<I", blob, 0)[0]
        start = struct.unpack_from("<Q", blob, 0x30)[0]
        size = (strings - start) // n
        out = {}
        for i in range(n):
            rid, _p, off, _nm = struct.unpack_from("<iIQQ", blob, 0x40 + 24 * i)
            out[rid] = blob[off:off + size]
        return out

    def text(self, kind: str, tid: int) -> str | None:
        if not self._texts:
            for n in ("item", "menu", "item_dlc01", "menu_dlc01", "item_dlc02", "menu_dlc02"):
                blob = self.read(f"/msg/engUS/{n}.msgbnd.dcx")
                for _fid, name, data in bnd4_files(blob) if blob else ():
                    short = name.replace("\\", "/").rsplit("/", 1)[-1].split(".")[0].split("_dlc")[0]
                    try:
                        for k, v in Fmg.read(data).entries.items():
                            if v and not v.startswith("[ERROR]"):
                                self._texts.setdefault(short, {}).setdefault(k, v)
                    except Exception:
                        pass
        return self._texts.get(kind, {}).get(tid)


# ---------------------------------------------------------------------------------------------------------------- EMEVD (64-bit)
def emevd(blob: bytes) -> dict[int, tuple[list, list]]:
    """{event id: ([(bank, id, args bytes)], [(instruction index, target byte, source byte, count)])}."""
    ev_n, ev_o, _in_n, in_o = struct.unpack_from("<qqqq", blob, 0x10)
    _pa_n, pa_o = struct.unpack_from("<qq", blob, 0x50)
    _ar_n, ar_o = struct.unpack_from("<qq", blob, 0x70)
    events = {}
    for i in range(ev_n):
        eid, n, ioff, pn, poff, _rest = struct.unpack_from("<qqqqqI", blob, ev_o + 0x30 * i)
        ins = []
        for k in range(n):
            bank, iid, alen, aoff, _layer = struct.unpack_from("<iiqqq", blob, in_o + ioff + 0x20 * k)
            ins.append((bank, iid, blob[ar_o + aoff:ar_o + aoff + alen]))
        params = [struct.unpack_from("<qqqq", blob, pa_o + poff + 0x20 * k) for k in range(pn)]
        events[eid] = (ins, params)
    return events


def words(b: bytes) -> list[int]:
    return [struct.unpack_from("<i", b, i)[0] for i in range(0, len(b) - 3, 4)]


def filled(event: tuple[list, list], args: bytes) -> list[tuple[int, int, bytes]]:
    """The instructions of an event with its parameters taken from `args` (the bytes an Initialize* passed after the event id)."""
    ins, params = event
    put = defaultdict(list)
    for idx, tgt, src, cnt in params:
        put[idx].append((tgt, args[src:src + cnt]))
    out = []
    for k, (bank, iid, a) in enumerate(ins):
        a = bytearray(a)
        for tgt, val in put.get(k, ()):
            a[tgt:tgt + len(val)] = val
        out.append((bank, iid, bytes(a)))
    return out


SETS = ((2003, 66), (2003, 69))      # SetEventFlag (type, flag, state)
AWARDS = ((2003, 36), (2003, 4))     # AwardItemsIncludingClients / AwardItemLot (lot)
INIT, INIT_COMMON = (2000, 0), (2000, 6)


def flags_on(instrs) -> list[int]:
    out = []
    for bank, iid, a in instrs:
        w = words(a)
        if (bank, iid) in SETS and len(w) >= 3 and w[2] & 0xFF == 1:
            out.append(w[1] & 0xFFFFFFFF)
    return out


# ---------------------------------------------------------------------------------------------------------------- the table
def build(game: Game) -> dict:
    area = game.table("GameAreaParam")
    graces_t, subcat = game.table("BonfireWarpParam"), game.table("BonfireWarpSubCategoryParam")
    lots_map, lots_enemy = game.table("ItemLotParam_map"), game.table("ItemLotParam_enemy")

    common = emevd(game.read("/event/common_func.emevd.dcx"))
    remembrance = {}
    for bank, iid, a in emevd(game.read("/event/common.emevd.dcx"))[0][0]:
        w = words(a)
        if (bank, iid) == INIT and len(w) >= 6 and w[1] == 1100:
            remembrance[w[2]] = (w[3], w[5] & 0xFFFFFFFF)       # play-log flag -> (lot, lot flag)

    graces = []
    for gid, r in graces_t.items():
        _lit, ent = struct.unpack_from("<II", r, 4)
        sub, = struct.unpack_from("<i", r, 20)
        x, y, z = struct.unpack_from("<fff", r, 36)
        tid, = struct.unpack_from("<i", r, 48)
        place = None
        if sub in subcat:
            place = game.text("GR_MenuText", struct.unpack_from("<i", subcat[sub], 4)[0])     # the place the map menu lists it under
        if ent and gid and game.text("PlaceName", tid):
            graces.append(dict(id=gid, entity=ent, area=r[32], gx=r[33], gz=r[34], pos=(x, y, z), name=game.text("PlaceName", tid), place=place))

    def world(a, gx, gz, pos):
        x, y, z = pos
        return (gx * 256 + x, y, gz * 256 + z) if a in (60, 61) else (x, y, z)

    def lot_rows(lot: int) -> list[tuple[int, bytes]]:
        rows, table = [], lots_map if lot in lots_map else lots_enemy
        i = lot
        while i in table and len(rows) < 10:
            rows.append((i, table[i]))
            i += 1
        return rows

    def lot_items(lot: int) -> tuple[list[str], list[int]]:
        names, flags = [], []
        for _i, r in lot_rows(lot):
            items, cats = struct.unpack_from("<8i", r, 0), struct.unpack_from("<8i", r, 32)
            flag, = struct.unpack_from("<I", r, 128)
            if flag:
                flags.append(flag)
            for item, cat in zip(items, cats):
                if item and cat in CATEGORY:
                    n = game.text(f"{CATEGORY[cat]}Name", item)
                    if n and n not in names:
                        names.append(n)
        return names, flags

    out, events_of_map = {}, {}
    for rid, r in sorted(area.items()):
        defeat, = struct.unpack_from("<I", r, 68)
        if not defeat:
            continue
        runes, = struct.unpack_from("<I", r, 4)
        found, = struct.unpack_from("<I", r, 52)
        bx, by, bz = struct.unpack_from("<fff", r, 72)
        a, bl, mp = r[84], r[85], r[86]
        m = f"m{a:02d}_{bl:02d}_{mp:02d}_00"
        if m not in events_of_map:
            blob = game.read(f"/event/{m}.emevd.dcx")
            events_of_map[m] = emevd(blob) if blob else {}
        evs = events_of_map[m]

        # every event body that concerns the boss: the map's events, and the common events the map starts with the flag
        bodies = []
        for eid, ev in evs.items():
            body = ev[0]
            if any(defeat in words(x[2]) for x in body if (x[0], x[1]) not in (INIT, INIT_COMMON)):
                bodies.append((eid, body))
            for bank, iid, a2 in body:
                if (bank, iid) in (INIT, INIT_COMMON) and defeat in words(a2):
                    target = struct.unpack_from("<I", a2, 4)[0]
                    table = common if (bank, iid) == INIT_COMMON else evs
                    if target in table:
                        bodies.append((target, filled(table[target], a2[8:])))
        playlog, entity, name_id, intro, lots, lit = [], None, None, [], [], []
        for eid, body in bodies:
            on = flags_on(body)
            kinds = {(b, i) for b, i, _x in body}
            if defeat in on:
                playlog += [f for f in on if 9000 <= f < 10000]
                for b, i, x in body:
                    if (b, i) == (2003, 12):
                        entity = words(x)[0]
            if any(b == 2002 for b, _i in kinds) and defeat not in on:
                intro += [f for f in on if f // 1000 == defeat // 1000 and f != defeat]
            for b, i, x in body:
                w = words(x)
                if (b, i) in AWARDS and w and w[0] > 0:
                    lots.append(w[0])
                if (b, i) == (2003, 11) and len(w) >= 4 and (entity is None or w[1] == entity):
                    name_id = name_id or w[3]
            if eid in (9005810, 9005811):
                lit += [v for v in words(b"".join(x[2] for x in body))]
        for bank, iid, a2 in (x for ev in evs.values() for x in ev[0]):   # the health bar may be in an event that names the entity only
            w = words(a2)
            if name_id is None and entity is not None and (bank, iid) == (2003, 11) and len(w) >= 4 and w[1] == entity:
                name_id = w[3]
        name = game.text("NpcName", name_id) if name_id else None

        drop_names, drop_flags = [], []
        for f in dict.fromkeys(playlog):
            if f in remembrance:
                lot, lflag = remembrance[f]
                n, fl = lot_items(lot)
                drop_names += n
                drop_flags += fl or [lflag]
        for lot in dict.fromkeys(lots):
            n, fl = lot_items(lot)
            drop_names += n
            drop_flags += fl

        # the nearest grace that is not the one the fight lights (its entity is an argument of the boss's grace events, or its name
        # is the boss's), in the boss's map (legacy dungeons, caves) or its region of the open world
        here = world(a, bl, mp, (bx, by, bz))
        cands = [g for g in graces if g["area"] == a and (a in (60, 61) or g["gx"] == bl)]
        cands = [g for g in cands if g["entity"] not in lit and g["name"] != name]
        best = min(cands, key=lambda g: math.dist(world(g["area"], g["gx"], g["gz"], g["pos"]), here)) if cands else None

        row = {
            "name": name or f"great enemy {rid}",          # no health-bar name in the scripts: the id (OVERRIDES may name it)
            "place": (best or {}).get("place"),
            "map": m[:-3],
            "flags": {"defeated": defeat, "playlog": sorted(set(playlog)), "drop": sorted(set(drop_flags)),
                      "cutscene": sorted(set(intro))},
            "runes": runes,
            "drop": drop_names,
            "grace": {"id": best["id"], "name": best["name"], "meters": round(math.dist(world(best["area"], best["gx"], best["gz"], best["pos"]), here))} if best else None,
            "story": bool(name) and any(s in name for s in STORY),
            "dlc": a in DLC_AREAS,
        }
        if found and found // 1000 == defeat // 1000 and found not in row["flags"]["cutscene"] and not intro:
            row["flags"]["cutscene"] = [found]
        row.update(OVERRIDES.get(rid, {}))
        out[str(rid)] = row
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--game", type=Path, default=DEFAULT_GAME)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    table = build(Game(a.game))
    doc = {"_readme": "spec 1.8.0 section 4: made by tools/gen_great_enemies.py from the game's own files (1.17.1); do not edit by hand, "
                      "add to OVERRIDES in the tool instead", "game": "1.17.1", "great_enemies": table}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    rows = list(table.values())
    print(f"{len(rows)} great enemies -> {a.out}")
    print(f"  named from the game: {sum(1 for r in rows if not r['name'].startswith('great enemy'))}; with a grace: "
          f"{sum(1 for r in rows if r['grace'])}; with a drop: {sum(1 for r in rows if r['flags']['drop'])}; with an intro: "
          f"{sum(1 for r in rows if r['flags']['cutscene'])}; story: {sum(1 for r in rows if r['story'])}; DLC: {sum(1 for r in rows if r['dlc'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

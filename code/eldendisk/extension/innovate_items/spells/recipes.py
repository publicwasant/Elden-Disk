"""Recipes: how a spec spell becomes rows of regulation.bin 1.17.1.

Every spell, whatever its slot, becomes NEW rows appended to the four tables (grow.py): a Goods row (the inventory item), a Magic
row (the spell), a SpEffect row (the heal over time), a second SpEffect row when the spell gives poise while casting, and a
ShopLineup row when it is sold. Each row is a copy of a real row of the game with the fields of the spec written over it.
A spell made from a game spell is a Goods row and a Magic row (copies of the template's rows) and, when sold, a ShopLineup row; a
`clone` keeps pointing at the template's own chain, an `enchant` or a `buff` with `from` also copies the template's own SpEffect rows. Nothing existing is changed or removed. The ids of the rows are fixed by the slot (`slot_rows`), so a spell keeps its ids as long
as it stays in its slot. Everything a recipe adds is declared in a Footprint, which the preflight checks against the result."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple

from ..container import ContainerError, Param
from ..defs import TABLE_FILES, Def
from .spec import GOODS_TYPES, MAX_SLOTS, VISUAL_VFX, motion_number, visual_number
from . import chain as chainmod


class RecipeError(Exception):
    pass


# --- rows of the 1.17.1 base that are copied or used (see handbook Part VI) ---
DUMMY = 999999999            # never-used debug row at the end of Goods / Magic / SpEffect: only its name pointer is borrowed
SHOP_DUMMY = 9999002         # the same in ShopLineup
CAST_FROM = 6050             # Magic row cloned: Flame, Grant Me Strength (cast animation, sfx)
SHOP_CLONE = 100507
# effect.visual -> SpEffect.vfxId (spec.VISUAL_VFX): flame = the burning body of Flame! Grant Me Strength, flask = Heal's glow, none = no lingering visual
HEAL_GOODS, HEAL_SP, FLAME_SP, ENDURE_SP, ICON_GOODS = 6421, 1642100, 1605000, 1650, 6424
# golden_eyes: glowing eyes, the effect f000004866 the game puts on both eyes of a human NPC of the DLC (NpcParam 150000002): SpEffectVfx
# 20090050 on DummyPoly 845 (the left eye of the human model, which the player has too) and 20090051 on 846 (the right eye), shown by
# that NPC's SpEffects 20018100 and 20018101
EYES_VFX = (20090050, 20090051)
EYES_FROM_SP = (20018100, 20018101)
EYES_SLOTS = tuple("vfxId%d" % k for k in range(1, 8))      # the extra visual fields of a SpEffect row; vfxId itself is the design's

KEYS = ("goods", "magic", "sp", "shop", "bullet", "atk")      # the tables a recipe may add rows to
NAME_FROM = {"goods": DUMMY, "magic": DUMMY, "sp": DUMMY, "shop": SHOP_DUMMY, "bullet": DUMMY, "atk": DUMMY}   # the row whose name pointer new rows share

# --- the rows a slot owns (fixed: slot 1 has the ids of the Z4 spell that was tested in the game) ---
ITEM_BASE = 2230000          # Goods id == Magic id; above the last real goods id (2220010)
SP_BASE = 21950111           # the heal-over-time SpEffect; above the last real id (21950011)
POISE_BASE = 21950211        # the poise SpEffect of a spell that has `poise_while_casting_seconds`
COPY_SP_BASE = 21951000      # the SpEffect rows a spell made from a template copies: a block of 8 per slot, above the two blocks above
COPY_SP_BLOCK = 8
COPY_BULLET_BASE = 500000000   # the Bullet rows a projectile copies: a block of 16 per slot (the range T7 loaded in the game; the game's own ids end at 400,000,002)
COPY_BULLET_BLOCK = 16
COPY_ATK_BASE = 710000000      # the AtkParam_Pc rows a projectile or attack copies: a block of 8 per slot (the game's own ids end at 701,320,361)
COPY_ATK_BLOCK = 8
SHARED_ABOVE = 3             # a row that more than this many Magic rows of the game reach is generic: shared, never copied
# The merchant's group 100500-100524 has 7 lines that are free in the game's own file; a slot above 7 has no shop line.
SHOP_LINES = (100508, 100509, 100512, 100521, 100522, 100523, 100524)
SHOP_RANGE = (100500, 100524)      # the merchant's group of 25 lines that the handbook (Chapter 7) found in the game


def slot_rows(slot: int) -> dict:
    """The ids of the rows slot `slot` (1..MAX_SLOTS) owns in the game. shop_line/shop_flag are None above the 7th slot."""
    if not isinstance(slot, int) or not 1 <= slot <= MAX_SLOTS:
        raise RecipeError("slot %r is outside 1..%d" % (slot, MAX_SLOTS))
    line = SHOP_LINES[slot - 1] if slot <= len(SHOP_LINES) else None
    return {"goods": ITEM_BASE + slot - 1, "magic": ITEM_BASE + slot - 1, "sp_effect": SP_BASE + slot - 1,
            "poise_sp_effect": POISE_BASE + slot - 1, "sp_copy_base": COPY_SP_BASE + (slot - 1) * COPY_SP_BLOCK,
            "bullet_copy_base": COPY_BULLET_BASE + (slot - 1) * COPY_BULLET_BLOCK,
            "atk_copy_base": COPY_ATK_BASE + (slot - 1) * COPY_ATK_BLOCK, "shop_line": line,
            "shop_flag": None if line is None else 150000 + (line - 100500) * 10}      # the game's own pattern for this group


@dataclass
class Footprint:
    removed: dict = field(default_factory=lambda: {k: set() for k in KEYS})
    added: dict = field(default_factory=lambda: {k: set() for k in KEYS})
    modified: dict = field(default_factory=lambda: {k: set() for k in KEYS})


def _row(P: Param, rid: int, what: str):
    r = P.find(rid)
    if r is None:
        raise RecipeError("%s: row %d is missing, so this is not the 1.17.1 regulation.bin" % (what, rid))
    return r


def _motion(P: dict, D: dict, spell: dict) -> int:
    """Magic.refType of a spell made from scratch: the number of its `cast_motion`, which some Magic row of the game must use."""
    n = motion_number(spell["cast_motion"])
    if not any(D["magic"].get(r[2], "refType") == n for r in P["magic"].rows):
        raise RecipeError("%s: cast_motion %d is not a motion number any spell of the game uses (the handbook lists them)" % (spell["id"], n))
    return n


def _visual(P: dict, D: dict, spell: dict) -> int:
    """SpEffect.vfxId of the body effect of a spell made from scratch: the number of its `effect.visual`, which some SpEffect row of the game must use."""
    n = visual_number(spell["effect"]["visual"])
    if n not in VISUAL_VFX.values() and not any(D["sp"].get(r[2], "vfxId") == n for r in P["sp"].rows):
        raise RecipeError("%s: effect.visual %d is not a visual number any effect of the game uses (the handbook lists them)" % (spell["id"], n))
    return n


def _shop_row(P: dict, D: dict, spell: dict, ids: dict):
    """The ShopLineup row of a spell that is sold (a line of the merchant's group), or None when it has no `shop`."""
    shop = spell.get("shop")
    if shop is None:
        return None
    if ids["shop_line"] is None:
        raise RecipeError("slot %d has no shop line (the merchant's group has %d free lines, for slots 1-%d): "
                          "remove its `shop`" % (spell["slot"], len(SHOP_LINES), len(SHOP_LINES)))
    data = bytearray(_row(P["shop"], SHOP_CLONE, "shop")[2])
    for n, v in dict(equipId=ids["goods"], value=shop["price"], sellQuantity=shop["stock"],
                     eventFlag_forStock=ids["shop_flag"], eventFlag_forRelease=0, equipType=3).items():
        D["shop"].set(data, n, v)
    return bytes(data)


def _eyes_vfx(P: dict, D: dict, who: str) -> tuple:
    """The SpEffectVfx rows of the eyes, checked against the file: the NPC's own SpEffect rows must still show them."""
    for sp, vfx in zip(EYES_FROM_SP, EYES_VFX):
        r = P["sp"].find(sp)
        if r is None or D["sp"].get(r[2], "vfxId") != vfx:
            raise RecipeError("%s: golden_eyes: SpEffect %d does not show SpEffectVfx %d in this file, so this is not the 1.17.1 "
                              "regulation.bin" % (who, sp, vfx))
    return EYES_VFX


def _visuals(d: Def, data) -> list:
    return [d.get(data, n) for n in ("vfxId",) + EYES_SLOTS]


def add_eyes(d: Def, data: bytearray, who: str, vfx: tuple = EYES_VFX) -> None:
    """Give a SpEffect row the eyes: each of `vfx` (left eye, right eye) in the first of vfxId1-vfxId7 that is free (-1), unless a
    visual field already holds it."""
    for v in vfx:
        if v in _visuals(d, data):
            continue
        free = [n for n in EYES_SLOTS if d.get(data, n) == -1]
        if not free:
            raise RecipeError("%s: golden_eyes: the buff's SpEffect row has no free visual field for both eyes (vfxId1-vfxId7)" % who)
        d.set(data, free[0], v)


def has_eyes(d: Def, data: bytes, vfx: tuple = EYES_VFX) -> bool:
    return all(v in _visuals(d, data) for v in vfx)


class Built(NamedTuple):
    goods: bytes
    magic: bytes
    sp: list           # [(new id, bytes)] the SpEffect rows copied (none for a clone), sorted by id
    bullet: list       # [(new id, bytes)] the Bullet rows copied (only kind projectile), sorted by id
    atk: list          # [(new id, bytes)] the AtkParam_Pc rows copied (kinds projectile and attack), sorted by id
    own: dict          # {"sp": {template id: new id}, "bullet": {...}, "atk": {...}} of those rows


def is_template(spell: dict) -> bool:
    """A spell made from a game spell (clone, enchant, projectile, buff with `from`), not the heal-over-time buff of the first recipe."""
    return "from" in spell


def needs_chain(spell: dict) -> bool:
    return is_template(spell) and spell.get("kind", "buff") != "clone"


_TABLE_NAME = {"sp": "SpEffect", "bullet": "Bullet", "atk": "AtkParam_Pc"}


def template_rows(P: dict, D: dict, spell: dict, chain=None) -> Built:
    """The rows of a spell made from a game spell: the template's Goods and Magic rows (the Goods row has the Magic row's id) with
    only the fields the design names written over them; for `enchant`, `buff`, `projectile` and `attack` also copies of the template's
    own SpEffect rows, for `projectile` Bullet rows, for `projectile` and `attack` AtkParam_Pc rows (the rows no more than
    SHARED_ABOVE Magic rows of the game reach, found by chain.copy_set), pointing at each other, called by the Magic copy, with `set`
    written over them. P: the ORIGINAL tables (the template is a row of the game). `chain`: chain.Chain of the original (needed for
    every kind but clone)."""
    src, who, kind = spell["from"], "%s (slot %d)" % (spell["id"], spell["slot"]), spell.get("kind", "buff")
    magic, goods = P["magic"].find(src), P["goods"].find(src)
    if magic is None:
        raise RecipeError("%s: `from` %d is not a Magic row of this game" % (who, src))
    if goods is None:
        raise RecipeError("%s: `from` %d has no Goods row (the spells of NPCs and bosses have none): pick a spell a player can cast"
                          % (who, src))
    gtype = D["goods"].get(goods[2], "goodsType")
    if gtype not in GOODS_TYPES:
        raise RecipeError("%s: Goods %d is not a spell (goodsType %d)" % (who, src, gtype))
    if spell.get("type", GOODS_TYPES[gtype]) != GOODS_TYPES[gtype]:
        raise RecipeError("%s: `from` %d is %s %s: a copy cannot change `type` (the cast motion and the catalyst follow it)"
                          % (who, src, "an" if GOODS_TYPES[gtype] == "incantation" else "a", GOODS_TYPES[gtype]))
    g, m = bytearray(goods[2]), bytearray(magic[2])
    own, sp_rows, bullet_rows, atk_rows = {"sp": {}, "bullet": {}, "atk": {}}, [], [], []
    if kind != "clone":
        if chain is None:
            raise RecipeError("%s: internal error: no chain reader for kind %s" % (who, kind))
        enchant = D["magic"].get(m, "isEnchant") or D["magic"].get(m, "isShieldEnchant")
        refs = chain.refs(src)
        tables = {t for _n, t, _i in refs}
        called = ", ".join(sorted(_TABLE_NAME[t] for t in tables)) or "nothing"
        if kind == "enchant" and not enchant:
            raise RecipeError("%s: `from` %d is not a weapon or shield enchant (use kind %s)"
                              % (who, src, "buff" if refs and tables == {"sp"} else "projectile" if "bullet" in tables
                                 else "attack" if "atk" in tables else "clone"))
        if kind in ("buff", "enchant") and (not refs or tables != {"sp"}):
            raise RecipeError("%s: `from` %d calls %s, not only SpEffect rows: kind %s needs a spell that only applies an effect "
                              "(for a spell that throws something use kind projectile, for a direct attack kind attack)" % (who, src, called, kind))
        if kind == "buff" and enchant:
            raise RecipeError("%s: `from` %d is an enchant: use kind enchant" % (who, src))
        if kind == "projectile" and "bullet" not in tables:
            raise RecipeError("%s: `from` %d calls %s and no Bullet row: kind projectile needs a spell that throws or creates a Bullet "
                              "(a spell that only applies an effect is kind buff or enchant, a direct attack is kind attack)" % (who, src, called))
        if kind == "attack" and ("atk" not in tables or "bullet" in tables):
            raise RecipeError("%s: `from` %d calls %s: kind attack needs a spell that makes a direct attack (an AtkParam_Pc row) and "
                              "throws nothing (a spell that throws or creates a Bullet is kind projectile, one that only applies an "
                              "effect is kind buff or enchant)" % (who, src, called))
        take = chain.copy_set(src, SHARED_ABOVE)
        for t, block, base, name in (("sp", COPY_SP_BLOCK, slot_rows(spell["slot"])["sp_copy_base"], "SpEffect"),
                                     ("bullet", COPY_BULLET_BLOCK, slot_rows(spell["slot"])["bullet_copy_base"], "Bullet"),
                                     ("atk", COPY_ATK_BLOCK, slot_rows(spell["slot"])["atk_copy_base"], "AtkParam_Pc")):
            ids = sorted(take[t])
            if len(ids) > block:
                raise RecipeError("%s: the chain of %d has %d %s rows of its own; a slot has room for %d" % (who, src, len(ids), name, block))
            own[t] = {old: base + k for k, old in enumerate(ids)}
        for n, t, rid in refs:
            if t in own and rid in own[t]:
                D["magic"].set(m, "refId%d" % n, own[t][rid])
        sets = {"sp": {}, "bullet": {}, "atk": {}}
        for key, v in spell.get("set", {}).items():
            table, rid, name = key.split(".", 2)
            t = {"SpEffect": "sp", "Bullet": "bullet", "AtkParam_Pc": "atk"}.get(table)
            if t is None:
                continue
            if int(rid) not in own[t]:
                reach = chain.reach(t, int(rid))
                why = ("is shared with %d spells of the game and is not copied" % reach) if int(rid) in chain.closure(src)[t] and reach > SHARED_ABOVE \
                    else "is not part of the chain of %d that is copied" % src
                raise RecipeError("%s: set %s: %s %s %s (copied %s rows: %s)" % (who, key, table, rid, why, table, ", ".join(map(str, own[t])) or "none"))
            sets[t].setdefault(int(rid), []).append((name, v))
        eyes_on = None
        if "golden_eyes" in spell:
            eyes_on = int(spell["golden_eyes"]["on"].split(".", 1)[1])
            if eyes_on not in own["sp"]:
                raise RecipeError("%s: golden_eyes.on: SpEffect %d is not one of the copied SpEffect rows (copied: %s)"
                                  % (who, eyes_on, ", ".join(map(str, own["sp"])) or "none"))
            eyes_vfx = _eyes_vfx(P, D, who)
        for t, rows, links in (("sp", sp_rows, chainmod.SP_PAIRS), ("bullet", bullet_rows, chainmod.BULLET_LINKS),
                               ("atk", atk_rows, chainmod.ATK_PAIRS)):
            for old, new in own[t].items():
                data = bytearray(chain.rows[t][old])
                for table, link in links:
                    target = D[t].get(data, link)
                    if target in own[table]:
                        D[t].set(data, link, own[table][target])
                for name, v in sets[t].get(old, []):
                    D[t].set(data, name, v)
                if t == "sp" and old == eyes_on:
                    add_eyes(D["sp"], data, who, eyes_vfx)
                rows.append((new, bytes(data)))
    r = spell.get("requires", {})
    friendly = {"mp": spell.get("fp_cost"), "stamina": spell.get("stamina_cost"), "requirementIntellect": r.get("intelligence"),
                "requirementFaith": r.get("faith"), "requirementLuck": r.get("arcane")}      # Arcane is stored in requirementLuck
    for name, v in friendly.items():
        if v is not None:
            D["magic"].set(m, name, v)
    for key, v in spell.get("set", {}).items():
        table, _rid, name = key.split(".", 2)
        if table in ("Magic", "Goods"):
            D["magic" if table == "Magic" else "goods"].set(m if table == "Magic" else g, name, v)
    return Built(bytes(g), bytes(m), sp_rows, bullet_rows, atk_rows, own)


def make_rows(P: dict, D: dict, spells: list, chain=None):
    """P: key -> Param of the ORIGINAL tables, D: key -> Def (keys goods/magic/sp/shop), chain: chain.Chain of the original (only
    for spells that copy SpEffect rows). -> (jobs for grow.grow, Footprint). Nothing in P is changed."""
    fp = Footprint()
    rows = {k: [] for k in KEYS}
    seen = set()
    for spell in spells:
        if spell["slot"] in seen:
            raise RecipeError("slot %d is used by two spells" % spell["slot"])
        seen.add(spell["slot"])
        ids = slot_rows(spell["slot"])
        if is_template(spell):
            built = template_rows(P, D, spell, chain)
            rows["goods"].append((ids["goods"], built.goods))
            rows["magic"].append((ids["magic"], built.magic))
            rows["sp"].extend(built.sp)
            rows["bullet"].extend(built.bullet)
            rows["atk"].extend(built.atk)
            sh = _shop_row(P, D, spell, ids)
            if sh is not None:
                rows["shop"].append((ids["shop_line"], sh))
            continue
        e, r = spell["effect"], spell["requires"]
        poise = spell.get("poise_while_casting_seconds")
        # SpEffect: heal-over-time buff, start from Heal's own SpEffect, then override. NEGATIVE changeHpPoint heals.
        data = bytearray(_row(P["sp"], HEAL_SP, "sp")[2])
        flame = _row(P["sp"], FLAME_SP, "sp")[2]
        f = dict(changeHpPoint=-e["heal_hp_per_tick"], changeMpPoint=-e["restore_fp_per_tick"],
                 staminaRecoverChangeSpeed=e["stamina_regen_speed"], effectEndurance=e["duration_seconds"],
                 motionInterval=e["tick_seconds"], iconId=20411, spCategory=161, stateInfo=50,
                 vfxId=_visual(P, D, spell))
        for n in ("isExtendSpEffectLife", "isContractSpEffectLife"):
            f[n] = D["sp"].get(flame, n)
        for n, v in f.items():
            D["sp"].set(data, n, v)
        if "golden_eyes" in spell:
            add_eyes(D["sp"], data, "%s (slot %d)" % (spell["id"], spell["slot"]), _eyes_vfx(P, D, spell["id"]))
        rows["sp"].append((ids["sp_effect"], bytes(data)))
        # Poise: Endure's poise buff cloned into a row of its own, damage reduction stripped, no vfx/icon, short life.
        if poise:
            data = bytearray(_row(P["sp"], ENDURE_SP, "sp")[2])
            f = {k: 1.0 for k in D["sp"].order if k.startswith(("defPlayerDmgCorrectRate_", "defEnemyDmgCorrectRate_"))}
            f.update(vfxId=-1, iconId=-1, effectEndurance=poise)
            for n, v in f.items():
                D["sp"].set(data, n, v)
            rows["sp"].append((ids["poise_sp_effect"], bytes(data)))
        # Magic: the whole row cloned from a real spell, then ours; refCategory1 = 2 points straight at the SpEffect.
        data = bytearray(_row(P["magic"], CAST_FROM, "magic")[2])
        f = dict(disableParam_NT=0, sortId=5511 + spell["slot"] - 1, mp=spell["fp_cost"], stamina=spell["stamina_cost"],
                 requirementFaith=r["faith"], iconId=4036, refCategory1=2, refId1=ids["sp_effect"],
                 requirementIntellect=r["intelligence"], requirementLuck=r["arcane"],      # Arcane is stored in requirementLuck
                 refType=_motion(P, D, spell))
        if poise:
            f.update(refCategory2=2, refId2=ids["poise_sp_effect"])
        for n, v in f.items():
            D["magic"].set(data, n, v)
        rows["magic"].append((ids["magic"], bytes(data)))
        # Goods: the inventory item (goodsType 18 = incantation); Heal's goods row.
        data = bytearray(_row(P["goods"], HEAL_GOODS, "goods")[2])
        for n, v in dict(sortId=300011 + spell["slot"] - 1,
                         iconId=D["goods"].get(_row(P["goods"], ICON_GOODS, "goods")[2], "iconId")).items():
            D["goods"].set(data, n, v)
        rows["goods"].append((ids["goods"], bytes(data)))
        # Shop: a line of the merchant's group (only the slots that have one).
        sh = _shop_row(P, D, spell, ids)
        if sh is not None:
            rows["shop"].append((ids["shop_line"], sh))
    for key in KEYS:
        fp.added[key] = {rid for rid, _ in rows[key]}
    jobs = {TABLE_FILES[key]: {"rows": rows[key], "name_from": NAME_FROM[key]} for key in KEYS if rows[key]}
    if "AtkParam_Pc" in jobs:
        jobs["AtkParam_Pc"]["mode"] = "end"       # the entry in front of it is 6 MB: it grows at its end (grow.py _grow_end, test T9)
    return jobs, fp


# ---------------- checking a finished file against the spec ----------------
def _same(a, b) -> bool:
    """Whole numbers (ids, costs) must match exactly; only a fractional spec value (seconds, stored as float32) gets a tolerance.
    (A tolerance relative to the size of an id such as 21950111 would let a wrong id through.)"""
    if isinstance(b, int) and not isinstance(b, bool):
        return float(a) == float(b)
    return abs(float(a) - float(b)) <= 1e-6 * max(1.0, abs(float(b)))


def _check_shop(P, D, spell, ids, who, row, need, bad):
    """The shop line of a spell (both kinds): its fields, its own stock flag, the merchant's range; no line when there is no `shop`."""
    shop = spell.get("shop")
    line = ids["shop_line"]
    if shop is not None:
        if line is None:
            bad.append("G12: %s has a shop but its slot has no shop line" % who)
        else:
            srow = row("shop", line, "shop line")
            if srow is not None:
                lname = "shop line %d" % line
                need("shop", srow, "equipId", ids["goods"], lname, "G12")
                need("shop", srow, "value", shop["price"], lname, "G12")
                need("shop", srow, "sellQuantity", shop["stock"], lname, "G12")
                need("shop", srow, "eventFlag_forStock", ids["shop_flag"], lname, "G12")
                users = [x[0] for x in P["shop"].rows if D["shop"].get(x[2], "eventFlag_forStock") == ids["shop_flag"]]
                if users != [line]:
                    bad.append("G12: %s: stock flag %d is used by shop lines %s; it must belong to line %d only" % (who, ids["shop_flag"], users, line))
            if not SHOP_RANGE[0] <= line <= SHOP_RANGE[1]:
                bad.append("G12: %s: shop line %d is outside the merchant's range %d-%d" % (who, line, *SHOP_RANGE))
    elif line is not None and P["shop"].find(line) is not None:
        bad.append("G12: %s has no shop but its shop line %d exists in the file" % (who, line))


def check_incantation(P: dict, D: dict, spell: dict) -> list:
    """Read the rows of a FINISHED file (not what the recipe meant to write) and compare them with the spec and with what the
    handbook says breaks a spell: a broken id chain (Chapter 4), a shop line outside the merchant's range or a reused stock flag
    (Chapter 7, 16.1), a heal with the wrong sign (5.1). P: key -> ParamView/Param of the file. -> list of problems."""
    bad = []
    ids = slot_rows(spell["slot"])
    who = "%s (slot %d)" % (spell["id"], spell["slot"])

    def row(key, rid, what):
        r = P[key].find(rid)
        if r is None:
            bad.append("G11: %s: %s row %d is missing" % (who, what, rid))
            return None
        return r[2]

    def need(key, data, name, want, what, code="G11"):
        got = D[key].get(data, name)
        if not _same(got, want):
            bad.append("%s: %s: %s.%s is %s, the spec says %s" % (code, who, what, name, got, want))

    goods, magic = row("goods", ids["goods"], "goods"), row("magic", ids["magic"], "magic")
    sp = row("sp", ids["sp_effect"], "SpEffect")
    e, r = spell["effect"], spell["requires"]
    mname = "Magic %d" % ids["magic"]
    if magic is not None:
        need("magic", magic, "refCategory1", 2, mname)
        need("magic", magic, "refId1", ids["sp_effect"], mname)
        need("magic", magic, "disableParam_NT", 0, mname)
        for name, want in (("mp", spell["fp_cost"]), ("stamina", spell["stamina_cost"]), ("requirementIntellect", r["intelligence"]),
                           ("requirementFaith", r["faith"]), ("requirementLuck", r["arcane"]), ("refType", motion_number(spell["cast_motion"]))):
            need("magic", magic, name, want, mname, "G5")
        if spell.get("poise_while_casting_seconds"):
            need("magic", magic, "refCategory2", 2, mname)
            need("magic", magic, "refId2", ids["poise_sp_effect"], mname)
            prow = row("sp", ids["poise_sp_effect"], "poise SpEffect")
            if prow is not None:
                need("sp", prow, "effectEndurance", spell["poise_while_casting_seconds"], "SpEffect %d" % ids["poise_sp_effect"], "G5")
        else:
            need("magic", magic, "refCategory2", D["magic"].get(P["magic"].find(CAST_FROM)[2], "refCategory2"), mname)
    if sp is not None:
        # NEGATIVE changeHpPoint heals; a positive value would drain the player (handbook 5.1)
        sname = "SpEffect %d" % ids["sp_effect"]
        for name, amount in (("changeHpPoint", e["heal_hp_per_tick"]), ("changeMpPoint", e["restore_fp_per_tick"])):
            got = D["sp"].get(sp, name)
            if amount > 0 and not got < 0:
                bad.append("G13: %s: %s.%s is %s: a heal must be negative or it drains the player" % (who, sname, name, got))
            need("sp", sp, name, -amount, sname, "G13")
        for name, want in (("staminaRecoverChangeSpeed", e["stamina_regen_speed"]), ("effectEndurance", e["duration_seconds"]),
                           ("motionInterval", e["tick_seconds"]), ("vfxId", visual_number(e["visual"]))):
            need("sp", sp, name, want, sname, "G5")
        if "golden_eyes" in spell and not has_eyes(D["sp"], sp):
            bad.append("G5: %s: %s has no golden eyes (SpEffectVfx %s in vfxId1-vfxId7), the spec has golden_eyes"
                       % (who, sname, " and ".join(map(str, EYES_VFX))))
    _check_shop(P, D, spell, ids, who, row, need, bad)
    if goods is None and magic is not None:
        bad.append("G11: %s: Magic %d exists but its Goods row does not" % (who, ids["magic"]))
    return bad


def _differing_fields(d: Def, a: bytes, b: bytes) -> list:
    names = [n for n in d.order if d.fields[n][5] == 1 and d.fields[n][0] in ("s8", "u8", "s16", "u16", "s32", "u32", "f32")
             and d.get(a, n) != d.get(b, n)]
    return names or ["(bytes outside any named field)"]


def check_template(P: dict, D: dict, spell: dict, B: dict, chain=None) -> list:
    """The same kind of reading as check_incantation, for a spell made from a game spell (clone, enchant, projectile, buff with `from`):
    the Goods, Magic and copied SpEffect and Bullet rows of the FINISHED file must equal what the template in the ORIGINAL (B) gives with only
    the design's fields changed (a difference names the fields), the design's costs and requirements must be in the Magic row,
    every SpEffect the copies call must exist and none may still call a SpEffect that was copied (a pointer back to the
    template's own row), the copies must sit in the slot's block of ids, and the shop line must be right. -> list of problems."""
    bad = []
    ids = slot_rows(spell["slot"])
    who = "%s (slot %d)" % (spell["id"], spell["slot"])

    def row(key, rid, what):
        r = P[key].find(rid)
        if r is None:
            bad.append("G11: %s: %s row %d is missing" % (who, what, rid))
            return None
        return r[2]

    def need(key, data, name, want, what, code="G11"):
        got = D[key].get(data, name)
        if not _same(got, want):
            bad.append("%s: %s: %s.%s is %s, the spec says %s" % (code, who, what, name, got, want))

    goods, magic = row("goods", ids["goods"], "goods"), row("magic", ids["magic"], "magic")
    try:
        want = template_rows(B, D, spell, chain)
    except RecipeError as e:
        bad.append("G11: %s" % e)
        return bad
    for key, name, got, expected in (("goods", "Goods %d" % ids["goods"], goods, want.goods), ("magic", "Magic %d" % ids["magic"], magic, want.magic)):
        if got is not None and bytes(got) != expected:
            bad.append("G11: %s: %s is not the template's row %d with only the design's fields changed (differs in: %s)"
                       % (who, name, spell["from"], ", ".join(_differing_fields(D[key], bytes(got), expected))))
    for t, rows, base, block, name, links in (("sp", want.sp, ids["sp_copy_base"], COPY_SP_BLOCK, "SpEffect", chainmod.SP_PAIRS),
                                              ("bullet", want.bullet, ids["bullet_copy_base"], COPY_BULLET_BLOCK, "Bullet", chainmod.BULLET_LINKS),
                                              ("atk", want.atk, ids["atk_copy_base"], COPY_ATK_BLOCK, "AtkParam_Pc", chainmod.ATK_PAIRS)):
        for new, expected in rows:
            if not base <= new < base + block:
                bad.append("G11: %s: %s %d is outside the slot's block %d-%d" % (who, name, new, base, base + block - 1))
            got = row(t, new, name)
            if got is None:
                continue
            if bytes(got) != expected:
                bad.append("G11: %s: %s %d is not the template's row with only the design's fields changed (differs in: %s)"
                           % (who, name, new, ", ".join(_differing_fields(D[t], bytes(got), expected))))
            for table, link in links:
                target = D[t].get(got, link)
                if target in want.own[table]:
                    bad.append("G11: %s: %s %d.%s still points at the template's row %d, not at its copy" % (who, name, new, link, target))
                elif target > 0 and table in P and P[table].find(target) is None and target != DUMMY:
                    bad.append("G11: %s: %s %d.%s points at %s %d, which is not in the file" % (who, name, new, link, table, target))
    if magic is not None:
        mname, r = "Magic %d" % ids["magic"], spell.get("requires", {})
        for name, wanted in (("mp", spell.get("fp_cost")), ("stamina", spell.get("stamina_cost")),
                             ("requirementIntellect", r.get("intelligence")), ("requirementFaith", r.get("faith")),
                             ("requirementLuck", r.get("arcane"))):
            if wanted is not None:
                need("magic", magic, name, wanted, mname, "G5")
        for i in range(1, 11):       # an AtkParam_Pc, SpEffect or Bullet row the copy calls must exist
            table = {0: "atk", 1: "bullet", 2: "sp"}.get(D["magic"].get(magic, "refCategory%d" % i))
            if table:
                rid = D["magic"].get(magic, "refId%d" % i)
                label = {"sp": "SpEffect", "bullet": "Bullet", "atk": "AtkParam_Pc"}[table]
                if rid in want.own[table]:
                    bad.append("G11: %s: %s.refId%d still calls the template's %s %d, not its copy" % (who, mname, i, label, rid))
                elif rid > 0 and P[table].find(rid) is None:
                    bad.append("G11: %s: %s.refId%d points at %s %d, which is not in the file" % (who, mname, i, label, rid))
    _check_shop(P, D, spell, ids, who, row, need, bad)
    return bad

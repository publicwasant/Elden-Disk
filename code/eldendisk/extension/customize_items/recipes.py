"""Recipes: how a spec item becomes rows of regulation.bin 1.17.1.

The "dummy row" trick: the game ships one never-used debug row at the end of the Goods, Magic and SpEffect tables
(id 999999999) and two in ShopLineup (9999001/9999002). A recipe turns such a row into the new row by changing its id (the new
id is larger than every real id, so the table stays sorted and keeps its size) and overwriting its fields. No row moves, no
table grows. Everything a recipe touches is declared in a Footprint, which the preflight checks against the result."""
from __future__ import annotations

from dataclasses import dataclass, field

from .container import ContainerError, Param
from .defs import Def
from .spec import CAST_MOTIONS


class RecipeError(Exception):
    pass


# --- fixed rows of the 1.17.1 base (see handbook Part VI) ---
DUMMY = 999999999            # last row of Goods / Magic / SpEffect (disableParam_NT = 1)
SHOP_DUMMY = 9999002         # last-but-one row of ShopLineup
ITEM_ID = 2230000            # Goods id == Magic id; above the last real goods id (2220010)
SP_ID = 21950111             # the heal-over-time SpEffect; above the last real id (21950011)
POISE_ID = 102006            # "[Tear] Deflecting Hardtear - Unused": overwritten with an Endure-style poise buff
SHOP_LINE = 100508           # free line inside the merchant's 100500-100524 range
SHOP_FLAG = 150080           # eventFlag_forStock; unique per line
SHOP_CLONE = 100507
CAST_FROM = 6050             # Magic row cloned: Flame, Grant Me Strength (cast animation, sfx)
HEAL_GOODS, HEAL_SP, FLAME_SP, ENDURE_SP, ICON_GOODS = 6421, 1642100, 1605000, 1650, 6424


@dataclass
class Footprint:
    removed: dict = field(default_factory=lambda: {k: set() for k in ("goods", "magic", "sp", "shop")})
    added: dict = field(default_factory=lambda: {k: set() for k in ("goods", "magic", "sp", "shop")})
    modified: dict = field(default_factory=lambda: {k: set() for k in ("goods", "magic", "sp", "shop")})


def _row(P: Param, rid: int, what: str):
    r = P.find(rid)
    if r is None:
        raise RecipeError("%s: row %d is missing, so this is not the 1.17.1 regulation.bin" % (what, rid))
    return r


def _free(P: Param, rid: int, what: str):
    if P.find(rid) is not None:
        raise RecipeError("%s: id %d is already in use" % (what, rid))


def _take_dummy(P: Param, dummy_id: int, new_id: int, what: str):
    row = _row(P, dummy_id, what)
    _free(P, new_id, what)
    real = max(r[0] for r in P.rows if r[0] not in (DUMMY, SHOP_DUMMY, 9999001))
    if what != "shop" and new_id <= real:
        raise RecipeError("%s: new id %d must be above the last real id %d" % (what, new_id, real))
    return row


def apply_incantation(P: dict, D: dict, item: dict, fp: Footprint) -> None:
    """P: key -> Param, D: key -> Def (keys goods/magic/sp/shop). Edits P in place."""
    sp, magic, goods, shop = P["sp"], P["magic"], P["goods"], P["shop"]
    e = item["effect"]
    # SpEffect: heal-over-time buff, start from Heal's own SpEffect, then override. NEGATIVE changeHpPoint heals.
    row = _take_dummy(sp, DUMMY, SP_ID, "sp")
    data = bytearray(_row(sp, HEAL_SP, "sp")[2])
    flame = _row(sp, FLAME_SP, "sp")[2]
    f = dict(changeHpPoint=-e["heal_hp_per_tick"], changeMpPoint=-e["restore_fp_per_tick"],
             staminaRecoverChangeSpeed=e["stamina_regen_speed"], effectEndurance=e["duration_seconds"],
             motionInterval=e["tick_seconds"], iconId=20411, spCategory=161, stateInfo=50,
             vfxId=FLAME_SP if e["visual"] == "flame" else 5030)
    for n in ("isExtendSpEffectLife", "isContractSpEffectLife"):
        f[n] = D["sp"].get(flame, n)
    for n, v in f.items():
        D["sp"].set(data, n, v)
    row[2], row[0] = data, SP_ID
    fp.removed["sp"].add(DUMMY), fp.added["sp"].add(SP_ID)
    # Magic: the whole row cloned from a real spell, then ours; refCategory1 = 2 points straight at the SpEffect.
    row = _take_dummy(magic, DUMMY, ITEM_ID, "magic")
    data = bytearray(_row(magic, CAST_FROM, "magic")[2])
    r = item["requires"]
    f = dict(disableParam_NT=0, sortId=5511, mp=item["fp_cost"], stamina=item["stamina_cost"],
             requirementFaith=r["faith"], iconId=4036, refCategory1=2, refId1=SP_ID,
             requirementIntellect=r["intelligence"], requirementLuck=r["arcane"],      # Arcane is stored in requirementLuck
             refType=CAST_MOTIONS[item["cast_motion"]])
    poise = item.get("poise_while_casting_seconds")
    if poise:
        f.update(refCategory2=2, refId2=POISE_ID)
    for n, v in f.items():
        D["magic"].set(data, n, v)
    row[2], row[0] = data, ITEM_ID
    fp.removed["magic"].add(DUMMY), fp.added["magic"].add(ITEM_ID)
    if poise:   # clone Endure's poise buff into a reused row, strip its damage reduction, no vfx/icon, short life
        prow = _row(sp, POISE_ID, "sp")
        data = bytearray(_row(sp, ENDURE_SP, "sp")[2])
        f = {k: 1.0 for k in D["sp"].order if k.startswith(("defPlayerDmgCorrectRate_", "defEnemyDmgCorrectRate_"))}
        f.update(vfxId=-1, iconId=-1, effectEndurance=poise)
        for n, v in f.items():
            D["sp"].set(data, n, v)
        prow[2] = data
        fp.modified["sp"].add(POISE_ID)
    # Goods: the inventory item (goodsType 18 = incantation); Heal's goods row.
    row = _take_dummy(goods, DUMMY, ITEM_ID, "goods")
    data = bytearray(_row(goods, HEAL_GOODS, "goods")[2])
    for n, v in dict(sortId=300011, iconId=D["goods"].get(_row(goods, ICON_GOODS, "goods")[2], "iconId")).items():
        D["goods"].set(data, n, v)
    row[2], row[0] = data, ITEM_ID
    fp.removed["goods"].add(DUMMY), fp.added["goods"].add(ITEM_ID)
    # Shop: the spare dummy line becomes a free line inside the merchant's range.
    row = _take_dummy(shop, SHOP_DUMMY, SHOP_LINE, "shop")
    data = bytearray(_row(shop, SHOP_CLONE, "shop")[2])
    for n, v in dict(equipId=ITEM_ID, value=item["shop"]["price"], sellQuantity=item["shop"]["stock"],
                     eventFlag_forStock=SHOP_FLAG, eventFlag_forRelease=0, equipType=3).items():
        D["shop"].set(data, n, v)
    row[2], row[0] = data, SHOP_LINE
    fp.removed["shop"].add(SHOP_DUMMY), fp.added["shop"].add(SHOP_LINE)


# ---------------- checking a finished file against the spec ----------------
SHOP_RANGE = (100500, 100524)      # the merchant's group of 25 lines that the handbook (Chapter 7) found in the game


def _same(a, b) -> bool:
    """Whole numbers (ids, costs) must match exactly; only a fractional spec value (seconds, stored as float32) gets a tolerance.
    (A tolerance relative to the size of an id such as 21950111 would let a wrong id through.)"""
    if isinstance(b, int) and not isinstance(b, bool):
        return float(a) == float(b)
    return abs(float(a) - float(b)) <= 1e-6 * max(1.0, abs(float(b)))


def check_incantation(P: dict, D: dict, item: dict) -> list:
    """Read the rows of a FINISHED file (not what the recipe meant to write) and compare them with the spec and with what the
    handbook says breaks an item: a broken id chain (Chapter 4), a shop line outside the merchant's range or a reused stock flag
    (Chapter 7, 16.1), a heal with the wrong sign (5.1). -> list of problems."""
    bad = []

    def row(key, rid, what):
        r = P[key].find(rid)
        if r is None:
            bad.append("G11: %s row %d is missing" % (what, rid))
            return None
        return r[2]

    def need(key, data, name, want, what, code="G11"):
        got = D[key].get(data, name)
        if not _same(got, want):
            bad.append("%s: %s.%s is %s, the spec says %s" % (code, what, name, got, want))

    goods, magic = row("goods", ITEM_ID, "goods"), row("magic", ITEM_ID, "magic")
    sp, shop = row("sp", SP_ID, "SpEffect"), row("shop", SHOP_LINE, "shop line")
    e, r = item["effect"], item["requires"]
    if magic is not None:
        need("magic", magic, "refCategory1", 2, "Magic %d" % ITEM_ID)
        need("magic", magic, "refId1", SP_ID, "Magic %d" % ITEM_ID)
        need("magic", magic, "disableParam_NT", 0, "Magic %d" % ITEM_ID)
        for name, want in (("mp", item["fp_cost"]), ("stamina", item["stamina_cost"]), ("requirementIntellect", r["intelligence"]),
                           ("requirementFaith", r["faith"]), ("requirementLuck", r["arcane"]), ("refType", CAST_MOTIONS[item["cast_motion"]])):
            need("magic", magic, name, want, "Magic %d" % ITEM_ID, "G5")
        if item.get("poise_while_casting_seconds"):
            need("magic", magic, "refCategory2", 2, "Magic %d" % ITEM_ID)
            need("magic", magic, "refId2", POISE_ID, "Magic %d" % ITEM_ID)
            prow = row("sp", POISE_ID, "poise SpEffect")
            if prow is not None:
                need("sp", prow, "effectEndurance", item["poise_while_casting_seconds"], "SpEffect %d" % POISE_ID, "G5")
    if sp is not None:
        # NEGATIVE changeHpPoint heals; a positive value would drain the player (handbook 5.1)
        for name, amount in (("changeHpPoint", e["heal_hp_per_tick"]), ("changeMpPoint", e["restore_fp_per_tick"])):
            got = D["sp"].get(sp, name)
            if amount > 0 and not got < 0:
                bad.append("G13: SpEffect %d.%s is %s: a heal must be negative or it drains the player" % (SP_ID, name, got))
            need("sp", sp, name, -amount, "SpEffect %d" % SP_ID, "G13")
        for name, want in (("staminaRecoverChangeSpeed", e["stamina_regen_speed"]), ("effectEndurance", e["duration_seconds"]),
                           ("motionInterval", e["tick_seconds"])):
            need("sp", sp, name, want, "SpEffect %d" % SP_ID, "G5")
    if shop is not None:
        need("shop", shop, "equipId", ITEM_ID, "shop line %d" % SHOP_LINE, "G12")
        need("shop", shop, "value", item["shop"]["price"], "shop line %d" % SHOP_LINE, "G12")
        need("shop", shop, "sellQuantity", item["shop"]["stock"], "shop line %d" % SHOP_LINE, "G12")
        need("shop", shop, "eventFlag_forStock", SHOP_FLAG, "shop line %d" % SHOP_LINE, "G12")
        users = [x[0] for x in P["shop"].rows if D["shop"].get(x[2], "eventFlag_forStock") == SHOP_FLAG]
        if users != [SHOP_LINE]:
            bad.append("G12: stock flag %d is used by shop lines %s; it must belong to line %d only" % (SHOP_FLAG, users, SHOP_LINE))
    if not SHOP_RANGE[0] <= SHOP_LINE <= SHOP_RANGE[1]:
        bad.append("G12: shop line %d is outside the merchant's range %d-%d" % (SHOP_LINE, *SHOP_RANGE))
    if goods is None and magic is not None:
        bad.append("G11: Magic %d exists but its Goods row does not" % ITEM_ID)
    return bad

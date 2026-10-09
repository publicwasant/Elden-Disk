"""Recipes: how a spec spell becomes rows of regulation.bin 1.17.1.

Every spell, whatever its slot, becomes NEW rows appended to the four tables (grow.py): a Goods row (the inventory item), a Magic
row (the spell), a SpEffect row (the heal over time), a second SpEffect row when the spell gives poise while casting, and a
ShopLineup row when it is sold. Each row is a copy of a real row of the game with the fields of the spec written over it.
Nothing existing is changed or removed. The ids of the rows are fixed by the slot (`slot_rows`), so a spell keeps its ids as long
as it stays in its slot. Everything a recipe adds is declared in a Footprint, which the preflight checks against the result."""
from __future__ import annotations

from dataclasses import dataclass, field

from .container import ContainerError, Param
from .defs import Def
from .spec import CAST_MOTIONS, MAX_SLOTS


class RecipeError(Exception):
    pass


# --- rows of the 1.17.1 base that are copied or used (see handbook Part VI) ---
DUMMY = 999999999            # never-used debug row at the end of Goods / Magic / SpEffect: only its name pointer is borrowed
SHOP_DUMMY = 9999002         # the same in ShopLineup
CAST_FROM = 6050             # Magic row cloned: Flame, Grant Me Strength (cast animation, sfx)
SHOP_CLONE = 100507
# effect.visual -> SpEffect.vfxId: flame = the burning body of Flame! Grant Me Strength, flask = Heal's glow, none = no lingering visual
VISUAL_VFX = {"flame": 1605000, "flask": 5030, "none": -1}
HEAL_GOODS, HEAL_SP, FLAME_SP, ENDURE_SP, ICON_GOODS = 6421, 1642100, 1605000, 1650, 6424

# --- the rows a slot owns (fixed: slot 1 has the ids of the Z4 spell that was tested in the game) ---
ITEM_BASE = 2230000          # Goods id == Magic id; above the last real goods id (2220010)
SP_BASE = 21950111           # the heal-over-time SpEffect; above the last real id (21950011)
POISE_BASE = 21950211        # the poise SpEffect of a spell that has `poise_while_casting_seconds`
# The merchant's group 100500-100524 has 7 lines that are free in the game's own file; a slot above 7 has no shop line.
SHOP_LINES = (100508, 100509, 100512, 100521, 100522, 100523, 100524)
SHOP_RANGE = (100500, 100524)      # the merchant's group of 25 lines that the handbook (Chapter 7) found in the game


def slot_rows(slot: int) -> dict:
    """The ids of the rows slot `slot` (1..MAX_SLOTS) owns in the game. shop_line/shop_flag are None above the 7th slot."""
    if not isinstance(slot, int) or not 1 <= slot <= MAX_SLOTS:
        raise RecipeError("slot %r is outside 1..%d" % (slot, MAX_SLOTS))
    line = SHOP_LINES[slot - 1] if slot <= len(SHOP_LINES) else None
    return {"goods": ITEM_BASE + slot - 1, "magic": ITEM_BASE + slot - 1, "sp_effect": SP_BASE + slot - 1,
            "poise_sp_effect": POISE_BASE + slot - 1, "shop_line": line,
            "shop_flag": None if line is None else 150000 + (line - 100500) * 10}      # the game's own pattern for this group


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


def make_rows(P: dict, D: dict, spells: list):
    """P: key -> Param of the ORIGINAL tables, D: key -> Def (keys goods/magic/sp/shop).
    -> (jobs for grow.grow, Footprint). Nothing in P is changed."""
    fp = Footprint()
    rows = {k: [] for k in ("goods", "magic", "sp", "shop")}
    seen = set()
    for spell in spells:
        if spell["slot"] in seen:
            raise RecipeError("slot %d is used by two spells" % spell["slot"])
        seen.add(spell["slot"])
        ids = slot_rows(spell["slot"])
        e, r = spell["effect"], spell["requires"]
        poise = spell.get("poise_while_casting_seconds")
        # SpEffect: heal-over-time buff, start from Heal's own SpEffect, then override. NEGATIVE changeHpPoint heals.
        data = bytearray(_row(P["sp"], HEAL_SP, "sp")[2])
        flame = _row(P["sp"], FLAME_SP, "sp")[2]
        f = dict(changeHpPoint=-e["heal_hp_per_tick"], changeMpPoint=-e["restore_fp_per_tick"],
                 staminaRecoverChangeSpeed=e["stamina_regen_speed"], effectEndurance=e["duration_seconds"],
                 motionInterval=e["tick_seconds"], iconId=20411, spCategory=161, stateInfo=50,
                 vfxId=VISUAL_VFX[e["visual"]])
        for n in ("isExtendSpEffectLife", "isContractSpEffectLife"):
            f[n] = D["sp"].get(flame, n)
        for n, v in f.items():
            D["sp"].set(data, n, v)
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
                 refType=CAST_MOTIONS[spell["cast_motion"]])
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
        shop = spell.get("shop")
        if shop is not None:
            if ids["shop_line"] is None:
                raise RecipeError("slot %d has no shop line (the merchant's group has %d free lines, for slots 1-%d): "
                                  "remove its `shop`" % (spell["slot"], len(SHOP_LINES), len(SHOP_LINES)))
            data = bytearray(_row(P["shop"], SHOP_CLONE, "shop")[2])
            for n, v in dict(equipId=ids["goods"], value=shop["price"], sellQuantity=shop["stock"],
                             eventFlag_forStock=ids["shop_flag"], eventFlag_forRelease=0, equipType=3).items():
                D["shop"].set(data, n, v)
            rows["shop"].append((ids["shop_line"], bytes(data)))
    for key, short, dummy in (("goods", "EquipParamGoods", DUMMY), ("magic", "Magic", DUMMY), ("sp", "SpEffectParam", DUMMY),
                              ("shop", "ShopLineupParam", SHOP_DUMMY)):
        fp.added[key] = {rid for rid, _ in rows[key]}
    jobs = {short: {"rows": rows[key], "name_from": dummy} for key, short, dummy in (
        ("goods", "EquipParamGoods", DUMMY), ("magic", "Magic", DUMMY), ("sp", "SpEffectParam", DUMMY),
        ("shop", "ShopLineupParam", SHOP_DUMMY)) if rows[key]}
    return jobs, fp


# ---------------- checking a finished file against the spec ----------------
def _same(a, b) -> bool:
    """Whole numbers (ids, costs) must match exactly; only a fractional spec value (seconds, stored as float32) gets a tolerance.
    (A tolerance relative to the size of an id such as 21950111 would let a wrong id through.)"""
    if isinstance(b, int) and not isinstance(b, bool):
        return float(a) == float(b)
    return abs(float(a) - float(b)) <= 1e-6 * max(1.0, abs(float(b)))


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
                           ("requirementFaith", r["faith"]), ("requirementLuck", r["arcane"]), ("refType", CAST_MOTIONS[spell["cast_motion"]])):
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
                           ("motionInterval", e["tick_seconds"]), ("vfxId", VISUAL_VFX[e["visual"]])):
            need("sp", sp, name, want, sname, "G5")
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
    if goods is None and magic is not None:
        bad.append("G11: %s: Magic %d exists but its Goods row does not" % (who, ids["magic"]))
    return bad

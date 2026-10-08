#!/usr/bin/env python3
"""Build a regulation.bin that contains the custom incantation "Reverse Curse Technique".

    python make_item.py --name Z1                      # defaults = the shipped design
    python make_item.py --name Z2 --faith 30 --price 5000 --flask-vfx
    # the final "Z4" item (Int45/Fai15/Arc10, FP80, 34,590 runes, Black-Flame-Blade cast, hyper armor while casting):
    python make_item.py --name Z4 --faith 15 --intellect 45 --arcane 10 --fp-cost 80 --price 34590 --motion 32 --poise-sp 102006

Everything that is NOT edited stays byte-identical to the original compressed frame (see reencode.py).
Input : $ER_REGULATION (default ./regulation.orig.bin)  -- a pristine copy of the game's regulation.bin
Output: $ER_OUT/regulation.<name>.bin (default ./out/)
"""
import argparse, sys
import erlib, erdefs
from blockedit import SRC
from reencode import O, build, BS

TABLES = dict(goods=("EquipParamGoods", "EquipParamGoods"), magic=("Magic", "MagicParam"),
              sp=("SpEffectParam", "SpEffect"), shop=("ShopLineupParam", "ShopLineupParam"))
DUMMY = 999999999          # last row of Goods / Magic / SpEffect (disableParam_NT = 1, never used by the game)
SHOP_DUMMY = 9999002       # last-but-one row of ShopLineupParam (also unused)

def variant(a):
    raw, dcx_, body_, hdr_, bnd = erlib.load_regulation(SRC)
    defs = {k: erdefs.Def(v[1]) for k, v in TABLES.items()}
    P = {k: erlib.Param(bnd.get(v[0]).data) for k, v in TABLES.items()}
    def put(k): bnd.get(TABLES[k][0]).data = P[k].build()
    # new ids must sort AFTER every real row so the dummy keeps its slot at the end of the (sorted) table
    for k, nid in (("goods", a.item_id), ("magic", a.item_id), ("sp", a.sp_id)):
        real = max(r[0] for r in P[k].rows if r[0] != DUMMY)
        assert nid > real, "%s id %d must be > last real id %d" % (k, nid, real)
    # --- SpEffect: the heal-over-time buff. Start from Heal's own SpEffect (1642100: changeHpPoint -230, flask glow),
    #     then override the numbers. NEGATIVE changeHpPoint = heal. Flame-style bits come from 1605000.
    row = P["sp"].find(DUMMY); data = bytearray(P["sp"].find(1642100)[2])
    flame = P["sp"].find(1605000)[2]
    f = dict(changeHpPoint=a.hp_tick, changeMpPoint=a.fp_tick, staminaRecoverChangeSpeed=a.stamina_regen,
             effectEndurance=a.duration, motionInterval=a.tick, iconId=a.buff_icon, spCategory=161, stateInfo=50,
             vfxId=5030 if a.flask_vfx else 1605000)
    for n in ("isExtendSpEffectLife", "isContractSpEffectLife"): f[n] = defs["sp"].get(flame, n)
    for n, v in f.items(): defs["sp"].set(data, n, v)
    row[2] = data; row[0] = a.sp_id; put("sp")
    # --- Magic: whole row cloned from a real spell (default 6050 = Flame! Grant Me Strength: cast animation + cast sfx),
    #     then our costs/requirements and a direct SpEffect reference (refCategory1 = 2, no Bullet needed).
    row = P["magic"].find(DUMMY); data = bytearray(P["magic"].find(a.cast_from)[2])
    f = dict(disableParam_NT=0, sortId=a.sort_magic, mp=a.fp_cost, stamina=a.stamina_cost, requirementFaith=a.faith,
             iconId=a.magic_icon, refCategory1=2, refId1=a.sp_id)
    if a.intellect is not None: f["requirementIntellect"] = a.intellect
    if a.arcane is not None: f["requirementLuck"] = a.arcane          # Arcane is stored in requirementLuck
    if a.motion is not None: f["refType"] = a.motion                  # cast motion category (32 = Black Flame Blade)
    if a.poise_sp:                                                    # extra SpEffect applied at cast time (slot 2 or 3)
        assert P["sp"].find(a.poise_sp) is not None, "poise row must be an existing (unused) SpEffect row"
        f["refCategory%d" % a.poise_slot] = 2; f["refId%d" % a.poise_slot] = a.poise_sp
    for n, v in f.items(): defs["magic"].set(data, n, v)
    row[2] = data; row[0] = a.item_id; put("magic")
    # --- optional: 'hyper armor while casting'. Clone Endure's poise buff (1650) into a REUSED unused row, strip its damage
    #     reduction (all *DmgCorrectRate = 1.0), no vfx/icon, short life.
    if a.poise_sp:
        d = defs["sp"]; row = P["sp"].find(a.poise_sp); data = bytearray(P["sp"].find(1650)[2])
        f = {k: 1.0 for k in d.order if k.startswith(("defPlayerDmgCorrectRate_", "defEnemyDmgCorrectRate_"))}
        f.update(vfxId=-1, iconId=-1, effectEndurance=a.poise_dur)
        for n, v in f.items(): d.set(data, n, v)
        row[2] = data; put("sp")
    # --- Goods: the inventory item (goodsType 18 = incantation). Clone Heal's goods row.
    row = P["goods"].find(DUMMY); data = bytearray(P["goods"].find(6421)[2])
    for n, v in dict(sortId=a.sort_goods, iconId=defs["goods"].get(P["goods"].find(6424)[2], "iconId")).items(): defs["goods"].set(data, n, v)
    row[2] = data; row[0] = a.item_id; put("goods")
    # --- Shop: relabel the spare dummy line into a free line inside the merchant's range; the table keeps its size.
    if a.shop_line:
        assert P["shop"].find(a.shop_line) is None, "shop line already exists"
        row = P["shop"].find(SHOP_DUMMY); data = bytearray(P["shop"].find(a.shop_clone)[2])
        for n, v in dict(equipId=a.item_id, value=a.price, sellQuantity=a.qty, eventFlag_forStock=a.shop_flag,
                         eventFlag_forRelease=0, equipType=3).items(): defs["shop"].set(data, n, v)
        row[2] = data; row[0] = a.shop_line
        P["shop"].rows.sort(key=lambda r: r[0]); put("shop")
    nb = bnd.build(); assert len(nb) == len(O.body)
    return nb

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", required=True, help="output tag: out/regulation.<name>.bin")
    p.add_argument("--item-id", type=int, default=2230000, help="Goods id == Magic id (> 2220010, the last real goods id)")
    p.add_argument("--sp-id", type=int, default=21950111, help="SpEffect id of the buff (> 21950011)")
    p.add_argument("--faith", type=int, default=20)
    p.add_argument("--fp-cost", type=int, default=30)
    p.add_argument("--stamina-cost", type=int, default=0)
    p.add_argument("--hp-tick", type=int, default=-60, help="per tick; NEGATIVE heals")
    p.add_argument("--fp-tick", type=int, default=-4, help="per tick; NEGATIVE restores")
    p.add_argument("--stamina-regen", type=int, default=100, help="staminaRecoverChangeSpeed")
    p.add_argument("--tick", type=float, default=0.5, help="seconds between ticks (motionInterval)")
    p.add_argument("--duration", type=float, default=15.0, help="seconds (effectEndurance)")
    p.add_argument("--price", type=int, default=8990)
    p.add_argument("--qty", type=int, default=1, help="sellQuantity (-1 = unlimited)")
    p.add_argument("--shop-line", type=int, default=100508, help="0 = do not sell (100508 is a free line of the 100500-100524 merchant)")
    p.add_argument("--shop-flag", type=int, default=150080, help="eventFlag_forStock; must be unique per line")
    p.add_argument("--shop-clone", type=int, default=100507)
    p.add_argument("--cast-from", type=int, default=6050, help="Magic row to clone cast animation / sfx from (6050 = Flame! Grant Me Strength, 6421 = Heal)")
    p.add_argument("--intellect", type=int, default=None, help="requirementIntellect")
    p.add_argument("--arcane", type=int, default=None, help="requirementLuck (= Arcane)")
    p.add_argument("--motion", type=int, default=None, help="Magic.refType = cast motion category (31 Flame GMS, 32 Black Flame Blade)")
    p.add_argument("--poise-sp", type=int, default=0, help="id of an UNUSED SpEffect row to overwrite with an Endure-style poise buff (e.g. 102006); 0 = off")
    p.add_argument("--poise-slot", type=int, default=2, choices=(2, 3), help="Magic ref slot (refCategory/refId 2 or 3) that carries the poise effect")
    p.add_argument("--poise-dur", type=float, default=2.0, help="seconds the poise lasts")
    p.add_argument("--flask-vfx", action="store_true", help="keep Heal's flask glow (vfx 5030) instead of Flame's vfx 1605000")
    p.add_argument("--buff-icon", type=int, default=20411)
    p.add_argument("--magic-icon", type=int, default=4036)
    p.add_argument("--sort-magic", type=int, default=5511)
    p.add_argument("--sort-goods", type=int, default=300011)
    a = p.parse_args(argv)
    nb = variant(a)
    direct = sorted({i for i in range(len(O.body) // BS + 1) if nb[i*BS:(i+1)*BS] != O.body[i*BS:(i+1)*BS]})
    print("blocks whose decoded bytes change:", direct)
    build(a.name, nb, direct)

if __name__ == "__main__":
    main()

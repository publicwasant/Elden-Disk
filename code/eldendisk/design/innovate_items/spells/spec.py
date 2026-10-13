"""The `innovate_items.spells` section of design.json: a strict stdlib validator.

    {"innovate_items": {"spells": {"maximum": 64, "slots": {"<spell-id>": {...the spell...}, "<id-2>": null, ...}}}}

A slot is a place in the list, counted from 1 in file order; its number fixes the rows the spell gets in the game (so a spell
that moves to another slot gets other rows). A slot holding null is empty and is not built. The other sections of design.json
(other kinds of items under `innovate_items`, other designs) and are left alone.

Text (since 1.7.1): `text` = {"goods_name", "goods_info", "goods_captions"} is the spell's name, its short line and its long
description in the game. It is not part of the build (a new text never builds again; `write --text` puts it into the running game).
Anything that needs files inside the game's archives (colour, icon) is still Level 3 and refused."""
from __future__ import annotations

import json
import re

from ..defs import Def

FORMAT = 1                    # the canonical form (what `normalise` returns and the commit record stores)
PATH = ("innovate_items", "spells")   # where this design sits in design.json: {"innovate_items": {"spells": {...}}}
SECTION = ".".join(PATH)             # the same, as it is written in error messages
MAX_SLOTS = 64                # proven in the game (T6): 64 new rows in each of Goods, Magic, ShopLineup and SpEffect
ID_RE = r"[a-z0-9][a-z0-9_-]{0,39}"
CAST_MOTIONS = {"flame-grant-me-strength": 31, "black-flame-blade": 32}   # names for two of the game's motion numbers (Magic.refType)
MAX_MOTION = 999              # a motion may also be written as the game's own number; the build checks that a Magic row uses it


def motion_number(cm) -> int:
    """The Magic.refType a `cast_motion` stands for: a name from CAST_MOTIONS or the number itself."""
    return CAST_MOTIONS[cm] if isinstance(cm, str) else cm
VISUAL_VFX = {"flame": 1605000, "flask": 5030, "none": -1}   # names for three of the game's visual numbers (SpEffect.vfxId)
MAX_VFX = 99999999            # a visual may also be written as the game's own number; the build checks that a SpEffect row uses it


def visual_number(v) -> int:
    """The SpEffect.vfxId an `effect.visual` stands for: a name from VISUAL_VFX or the number itself."""
    return VISUAL_VFX[v] if isinstance(v, str) else v
VISUALS = ("flame", "flask", "none")   # none: only the cast flash (from Flame! Grant Me Strength), nothing burning on the body afterwards
KINDS = ("attack", "buff", "clone", "enchant", "projectile")               # built today; "buff" is the default so designs from before `kind` stay as they were
PLANNED_KINDS = ()                                 # kinds named in the design but not built yet (none since Phase 2.4)
TYPES = ("incantation", "sorcery")
GOODS_TYPES = {5: "sorcery", 16: "incantation", 17: "sorcery", 18: "incantation"}   # goodsType of a player spell's Goods row
# `set` (kinds clone, buff with `from`, enchant) writes single numbers of the copied rows: Goods and Magic always, SpEffect rows
# for the kinds that copy their SpEffect chain. Fields that name another row are refused (Phase
# 2.1 clones keep the template's chain; a copy that points elsewhere comes with 2.3/2.4), and so are the fields the spell
# already has friendly names for, which would silently fight the friendly value.
SET_TABLES = {"Magic": "magic", "Goods": "goods", "SpEffect": "sp", "Bullet": "bullet", "AtkParam_Pc": "atk"}
SET_KEY_RE = re.compile(r"(Magic|Goods|SpEffect|Bullet|AtkParam_Pc)\.(\d+)\.([A-Za-z_][A-Za-z0-9_]*)")
FRIENDLY_FIELDS = {"sp": {}, "magic": {"fp_cost": "mp", "stamina_cost": "stamina", "intelligence": "requirementIntellect",
                              "faith": "requirementFaith", "arcane": "requirementLuck"}, "goods": {}, "bullet": {}, "atk": {}}
ID_FIELDS = {
    "sp": {"replaceSpEffectId", "cycleOccurrenceSpEffectId", "atkOccurrenceSpEffectId", "applyIdOnGetSoul", "accumuOverFireId",
           "accumuUnderFireId"},      # the builder points these at the copies itself
    "magic": {"refCategory1", "refCategory2", "refCategory3", "refCategory4", "refCategory5", "refCategory6", "refCategory7",
              "refCategory8", "refCategory9", "refCategory10", "refId1", "refId2", "refId3", "refId4", "refId5", "refId6",
              "refId7", "refId8", "refId9", "refId10", "replaceMagicId", "mtrlItemId", "limitCancelSpEffectId",
              "createLimitGroupId"},
    "bullet": {"atkId_Bullet", "HitBulletID", "intervalCreateBulletId", "spEffectIDForShooter", "spEffectId0", "spEffectId1",
               "spEffectId2", "spEffectId3", "spEffectId4"},
    "atk": {"spEffectId0", "spEffectId1", "spEffectId2", "spEffectId3", "spEffectId4"},
    "goods": {"refId_default", "refId_1", "replaceItemId", "appearanceReplaceItemId", "refVirtualWepId", "vagrantItemLotId",
              "vagrantBonusEneDropItemLotId", "vagrantItemEneDropItemLotId", "reinforceGoodsId", "reinforceMaterialId",
              "goodsType"},      # goodsType decides attack/support and sorcery/incantation: it follows the template
}
LEVEL3_KEYS = {"icon", "icon_file", "colour", "color", "model"}
FLAME_COLOR_MAX = 2.0     # a colour channel: 0..1 is the colour, up to 2 shines brighter
EYES_ON_RE = re.compile(r"SpEffect\.(\d+)")    # positive_curse_energy_eyes.on: the copied SpEffect row the caster has while the buff lasts
TEXT_FIELDS = {"goods_name": 80, "goods_info": 300, "goods_captions": 3000}   # field -> most characters (name; the short line under it; the long description). A loose guard, not a game limit: the game's own longest are 43 / 86 / 462
RENAMED = {"name": "text.goods_name", "description": "text.goods_info (the long description is text.goods_captions)",   # 1.7.0 -> 1.7.1
           "golden_eyes": "positive_curse_energy_eyes"}                                                              # in 1.7.1


class SpecError(Exception):
    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


class _Check:
    def __init__(self):
        self.problems = []

    def bad(self, path, msg):
        self.problems.append("%s: %s" % (path, msg))

    def keys(self, obj, path, required, optional):
        for k in obj:
            if k in RENAMED:
                self.bad("%s.%s" % (path, k), "renamed in 1.7.1: use %s" % RENAMED[k])
            elif k in LEVEL3_KEYS:
                self.bad("%s.%s" % (path, k), "this needs files inside the game's archives (Level 3) and is not supported yet")
            elif k not in required and k not in optional:
                self.bad("%s.%s" % (path, k), "unknown field")
        for k in required:
            if k not in obj:
                self.bad("%s.%s" % (path, k), "missing")

    def integer(self, obj, key, path, lo, hi, default=None):
        if key not in obj:
            return default
        v = obj[key]
        if not _int(v) or not lo <= v <= hi:
            self.bad("%s.%s" % (path, key), "must be a whole number from %d to %d" % (lo, hi))
            return default
        return v

    def real(self, obj, key, path, lo, hi, default=None):
        if key not in obj:
            return default
        v = obj[key]
        if not _num(v) or not lo <= v <= hi:
            self.bad("%s.%s" % (path, key), "must be a number from %g to %g" % (lo, hi))
            return default
        return float(v)

    def text(self, obj, key, path, maxlen, default=""):
        if key not in obj:
            return default
        v = obj[key]
        if not isinstance(v, str) or len(v) > maxlen:
            self.bad("%s.%s" % (path, key), "must be text of at most %d characters" % maxlen)
            return default
        return v


def _text_obj(c, raw, path, fields=TEXT_FIELDS):
    """`raw` = {"goods_name", "goods_info", "goods_captions"} (each optional, text; empty = the game shows nothing) -> the canonical
    form, which always holds all three. `path` is where the user wrote it (for the messages)."""
    out = {k: "" for k in TEXT_FIELDS}
    if not isinstance(raw, dict):
        c.bad(path, "must be an object: " + ", ".join('"%s"' % k for k in fields))
        return out
    c.keys(raw, path, [], list(fields))
    for k, hi in TEXT_FIELDS.items():
        out[k] = c.text(raw, k, path, hi)
    return out


def _text_object(c, it, p):
    return _text_obj(c, it.get("text", {}), p + ".text")


def empty_text(maximum: int = MAX_SLOTS) -> str:
    """An design.json with `maximum` empty slots: nothing to build yet."""
    slots = ",\n".join('        "<id-%d>": null' % n for n in range(1, maximum + 1))
    return ('{\n  "innovate_items": {\n    "spells": {\n      "maximum": %d,\n      "slots": {\n%s\n      }\n    }\n  }\n}\n'
            % (maximum, slots))


def _requires(c, it, p, full):
    """`requires`: all three keys with 0 as default (buff), or only the keys given (clone: the rest stays the template's)."""
    req = it.get("requires", {} if not full else None)
    r = {"intelligence": 0, "faith": 0, "arcane": 0}
    if not isinstance(req, dict):
        c.bad(p + ".requires", "must be an object")
        return r if full else {}
    c.keys(req, p + ".requires", [], list(r))
    got = {k: c.integer(req, k, p + ".requires", 0, 99, 0) for k in r if k in req}
    return {**r, **got} if full else got


def _shop_obj(c, shop, path):
    """A shop line {"price", "stock"} -> the canonical form. `path` is where the user wrote it (for the messages)."""
    s = {"price": 0, "stock": 1}
    if not isinstance(shop, dict):
        c.bad(path, "must be an object")
    else:
        c.keys(shop, path, ["price"], ["stock"])
        s["price"] = c.integer(shop, "price", path, 1, 99999999, 1)
        s["stock"] = c.integer(shop, "stock", path, -1, 99, 1)
        if s["stock"] == 0:
            c.bad(path + ".stock", "must be -1 (unlimited) or 1 to 99")
    return s


def _shop(c, it, p):
    """`shop`: optional; a spell without a shop line is built but cannot be bought (slots above 7 have no line)."""
    return _shop_obj(c, it["shop"], p + ".shop")


def _flame_color(c, it, p, o):
    """`flame_color`: [red, green, blue], each 0..2 (1 = full colour, above 1 shines brighter). The fire of Flame, Grant Me Strength
    (the fire while casting and the burst; the fire on the body is left alone) is recoloured in the running game by `write --flame-color`; the effects are the game's own and
    shared by every spell that uses them, so the colour belongs to the whole design (see service.flame_color). Not part of the build.
    `flame_accent_color` (with flame_color): the colour of the parts of those files that flame_color leaves out (writer/fxr_plans.py
    `accent`: pink and red in the game's file), so the fire has two colours."""
    if "flame_color" not in it:
        if "flame_accent_color" in it:
            c.bad(p + ".flame_accent_color", "goes with flame_color (it colours the parts of the fire flame_color leaves out)")
        return
    v = it["flame_color"]
    if not _colour(v):
        c.bad(p + ".flame_color", "must be " + COLOUR_HELP)
        return
    o["flame_color"] = colour_of(v)
    if "flame_accent_color" in it:
        a = it["flame_accent_color"]
        if not _colour(a):
            c.bad(p + ".flame_accent_color", "must be " + COLOUR_HELP)
        else:
            o["flame_accent_color"] = colour_of(a)


_HEX_RE = re.compile(r"#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})")
COLOUR_HELP = ('a hex colour "#RRGGBB" (or "#RGB"), or three numbers [red, green, blue], each from 0 to %g (1 = full colour, above 1 '
               "shines brighter)" % FLAME_COLOR_MAX)


def colour_of(v) -> list | None:
    """A colour of the design -> [red, green, blue] (floats, 1 = full colour), or None when it is not one. A hex string "#90D5FF" (the
    `#` is optional, "#9DF" is "#99DDFF") gives each channel as n/255; three numbers [r, g, b] (0 to FLAME_COLOR_MAX) stay as they are
    (above 1 shines brighter, which hex cannot say)."""
    if isinstance(v, str):
        m = _HEX_RE.fullmatch(v.strip())
        if not m:
            return None
        h = m.group(1)
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    if isinstance(v, list) and len(v) == 3 and all(_num(x) and 0 <= x <= FLAME_COLOR_MAX for x in v):
        return [float(x) for x in v]
    return None


def colour_text(rgb) -> str | list:
    """[r, g, b] -> "#RRGGBB" when every channel is a whole 255th within 0..1 (what a hex colour of the design gives), else the
    numbers themselves (a channel above 1)."""
    if all(0 <= x <= 1 and abs(x * 255 - round(x * 255)) < 1e-6 for x in rgb):
        return "#" + "".join("%02X" % round(x * 255) for x in rgb)
    return [float(x) for x in rgb]


def _colour(v) -> bool:
    return colour_of(v) is not None


def _positive_curse_energy_eyes(c, it, p, o, template):
    """`positive_curse_energy_eyes`: {"on": "SpEffect.<id>", "color": [red, green, blue]}. While the buff lasts both of the caster's eyes glow (the
    game's own effect 4866 of a human NPC of the DLC, SpEffectVfx 20090050 and 20090051 on the eyes, added to the buff's SpEffect row by
    the build). `on` names the copied SpEffect row that is the buff (a spell made from a game spell; the template's id, as in `set`); a
    heal-over-time buff made from scratch has one buff row and no `on`. `color` (optional, as flame_color) recolours the glow in the
    running game (`write --flame-color` does both); without it the eyes are the game's red. The effect file is shared with that NPC, so
    the colour belongs to the whole design (service.eyes_color). `on` is part of the build, `color` is not."""
    if "positive_curse_energy_eyes" not in it:
        return
    v, q = it["positive_curse_energy_eyes"], p + ".positive_curse_energy_eyes"
    if o.get("kind") == "clone":
        c.bad(q, "a clone shares the template's SpEffect rows with the game's own spell: use kind buff (with `from`), enchant, "
                 "projectile or attack, which copy them")
        return
    if not isinstance(v, dict):
        c.bad(q, 'must be an object: {"on": "SpEffect.<id>", "color": [red, green, blue]}' if template else
                 'must be an object: {} or {"color": [red, green, blue]}')
        return
    allowed = ("on", "color") if template else ("color",)
    for k in v:
        if k not in allowed:
            c.bad("%s.%s" % (q, k), "unknown field" if k != "on" else
                  "a heal-over-time buff made from scratch has one buff row: leave `on` out")
    e = {}
    if template:
        m = EYES_ON_RE.fullmatch(v["on"]) if isinstance(v.get("on"), str) else None
        if "on" not in v:
            c.bad(q + ".on", "missing: the copied SpEffect row that is the buff, as SpEffect.<id> (the template's id, as in `set`)")
        elif not m:
            c.bad(q + ".on", "must be SpEffect.<id> (the template's id of the copied SpEffect row, as in `set`)")
        else:
            e["on"] = "SpEffect.%d" % int(m.group(1))
    if "color" in v:
        if _colour(v["color"]):
            e["color"] = colour_of(v["color"])
        else:
            c.bad(q + ".color", "must be " + COLOUR_HELP)
    o["positive_curse_energy_eyes"] = e


def _buff(c, it, p, n, iid):
    """A heal-over-time buff built from Flame, Grant Me Strength (the canonical form has no `kind`: it is the default)."""
    c.keys(it, p, ["type", "requires", "fp_cost"],
           ["kind", "text", "stamina_cost", "cast_motion", "effect", "poise_while_casting_seconds", "shop", "flame_color", "flame_accent_color", "positive_curse_energy_eyes"])
    if it.get("type") != "incantation":
        c.bad(p + ".type", 'only "incantation" is supported')
    o = {"slot": n, "id": iid, "type": "incantation", "text": _text_object(c, it, p)}
    o["requires"] = _requires(c, it, p, True)
    o["fp_cost"] = c.integer(it, "fp_cost", p, 0, 999, 0)
    o["stamina_cost"] = c.integer(it, "stamina_cost", p, 0, 999, 0)
    cm = it.get("cast_motion", "flame-grant-me-strength")
    if not (cm in CAST_MOTIONS if isinstance(cm, str) else _int(cm) and 0 <= cm <= MAX_MOTION):
        c.bad(p + ".cast_motion", "must be one of the names %s or a motion number from 0 to %d (Magic.refType; the handbook lists them)"
              % (", ".join(sorted(CAST_MOTIONS)), MAX_MOTION))
        cm = "flame-grant-me-strength"
    o["cast_motion"] = cm
    eff = it.get("effect", {})
    e = {"heal_hp_per_tick": 60, "restore_fp_per_tick": 4, "stamina_regen_speed": 100, "tick_seconds": 0.5,
         "duration_seconds": 15.0, "visual": "flame"}
    if not isinstance(eff, dict):
        c.bad(p + ".effect", "must be an object")
    else:
        c.keys(eff, p + ".effect", [], list(e))
        e["heal_hp_per_tick"] = c.integer(eff, "heal_hp_per_tick", p + ".effect", 0, 9999, 60)
        e["restore_fp_per_tick"] = c.integer(eff, "restore_fp_per_tick", p + ".effect", 0, 999, 4)
        e["stamina_regen_speed"] = c.integer(eff, "stamina_regen_speed", p + ".effect", 0, 9999, 100)
        e["tick_seconds"] = c.real(eff, "tick_seconds", p + ".effect", 0.1, 60, 0.5)
        e["duration_seconds"] = c.real(eff, "duration_seconds", p + ".effect", 0.5, 600, 15.0)
        v = eff.get("visual", "flame")      # left out: flame. An explicit null means "nothing on the body", same as "none"
        if "visual" in eff and v is None:
            v = "none"
        if not (v in VISUALS if isinstance(v, str) else _int(v) and -1 <= v <= MAX_VFX):
            c.bad(p + ".effect.visual", "must be one of the names %s or a visual number from -1 to %d (SpEffect.vfxId; the handbook lists them)"
                  % (", ".join(VISUALS), MAX_VFX))
            v = "flame"
        e["visual"] = v
    o["effect"] = e
    if "poise_while_casting_seconds" in it:
        o["poise_while_casting_seconds"] = c.real(it, "poise_while_casting_seconds", p, 0.1, 10, 2.0)
    if "shop" in it:
        o["shop"] = _shop(c, it, p)
    _flame_color(c, it, p, o)
    _positive_curse_energy_eyes(c, it, p, o, False)
    return o


def _template(c, it, p, n, iid, kind):
    """A spell made from a game spell: `clone` (copy of the Goods and Magic rows, it keeps calling the template's own chain),
    `buff` with `from` and `enchant` (the same, and the template's own SpEffect rows are copied too, so they can be tuned with
    `set`). What is not named stays the template's, so the canonical form holds only what the design says."""
    c.keys(it, p, ["kind", "from"], ["type", "text", "requires", "fp_cost", "stamina_cost", "shop", "set", "flame_color", "flame_accent_color", "positive_curse_energy_eyes"])
    o = {"slot": n, "id": iid, "kind": kind, "text": _text_object(c, it, p)}
    src = c.integer(it, "from", p, 1, 2**31 - 1)
    if src is not None:
        o["from"] = src
    if "type" in it:
        t = it["type"]
        if t not in TYPES:
            c.bad(p + ".type", "must be one of: " + ", ".join(TYPES))
        else:
            o["type"] = t           # checked against the template when the rows are built: a copy cannot change it
    o["requires"] = _requires(c, it, p, False)
    for k, hi in (("fp_cost", 999), ("stamina_cost", 999)):
        v = c.integer(it, k, p, 0, hi)
        if v is not None:
            o[k] = v
    if "shop" in it:
        o["shop"] = _shop(c, it, p)
    if "set" in it:
        o["set"] = _set(c, it["set"], p + ".set", o)
    _flame_color(c, it, p, o)
    _positive_curse_energy_eyes(c, it, p, o, True)
    return o


def _set(c, raw, path, o):
    """`set`: {"Magic.<from>.<field>": number, "Goods.<from>.<field>": number, "SpEffect.<id>.<field>": number} -> the same, values
    checked against the field. Whether a SpEffect id is one of the copied rows is checked when the rows are built."""
    if not isinstance(raw, dict):
        c.bad(path, "must be an object: \"Magic.<from>.<field>\": number")
        return {}
    out = {}
    for key, val in raw.items():
        kp = "%s[%s]" % (path, key)
        m = SET_KEY_RE.fullmatch(key) if isinstance(key, str) else None
        if not m:
            c.bad(kp, "a key looks like Magic.<from>.<field>, Goods.<from>.<field> (the row id is the spell's `from`), SpEffect.<id>.<field>, Bullet.<id>.<field> or AtkParam_Pc.<id>.<field>")
            continue
        table, rid, name = SET_TABLES[m.group(1)], int(m.group(2)), m.group(3)
        if table in ("sp", "bullet", "atk"):
            name_ = {"sp": "SpEffect", "bullet": "Bullet", "atk": "AtkParam_Pc"}[table]
            if o["kind"] == "clone":
                c.bad(kp, "a clone shares the template's %s rows with the game's own spell and does not copy them: use "
                          "kind buff (with `from`), enchant, projectile or attack to tune a SpEffect, kind projectile for a Bullet, "
                          "kind projectile or attack for an AtkParam_Pc row" % name_)
                continue
            if table == "bullet" and o["kind"] != "projectile":
                c.bad(kp, "only kind projectile copies Bullet rows (a buff or an enchant calls SpEffect rows only)")
                continue
            if table == "atk" and o["kind"] not in ("projectile", "attack"):
                c.bad(kp, "only the kinds projectile and attack copy AtkParam_Pc rows (a buff or an enchant calls SpEffect rows only)")
                continue
        elif "from" in o and rid != o["from"]:
            c.bad(kp, "Magic and Goods can only be set on the copied rows: the row id must be this spell's `from` (%d). The "
                      "other rows of the chain are shared with the game's own spell (SpEffect rows are copied by the kinds buff with "
                      "`from` and enchant: SpEffect.<id>.<field>)" % o["from"])
            continue
        d = Def(table)
        why = d.problem(name, val)
        if why:
            c.bad(kp, why)
            continue
        if name in ID_FIELDS[table]:
            c.bad(kp, "%s is an id or type that links rows; it follows the template (the builder points the copies at each other) "
                      "and is not set here" % name)
            continue
        friendly = [k for k, f in FRIENDLY_FIELDS[table].items() if f == name]
        if friendly:
            c.bad(kp, "%s already has a friendly field (%s): use that" % (name, "requires." + friendly[0] if friendly[0] in ("intelligence", "faith", "arcane") else friendly[0]))
            continue
        if d.fields[name][0] == "f32":
            val = float(val)
        elif isinstance(val, float):
            val = int(val)
        out[key] = val
    return out


# ---------------------------------------------------------------- the structure of section 1b
# A spell may be written as
#   {"__info__": "...", "kind": "projectile", "from": 6421,
#    "requires":  {"status": {"intelligence", "faith", "arcane"}, "cost": {"focus_point", "stamina"}},
#    "locations": {"kale": {"price", "stock"}},
#    "customs":   {"basic":    {"__info__": "...", "SpEffect.<id>.<field>": n, "Magic.<from>.<field>": n, ...},
#                  "advanced": {"__info__": "...", "texts": {"goods_name", "goods_info", "goods_caption"},
#                               "colors": {"Magic.<from>.castSfxId": [r, g, b] | {"main": [r, g, b], "accent": [r, g, b]},
#                                          "SpEffect.<id>": [r, g, b] | null}}}}
# (a spell made from a game spell: `from`). `upgrade_spell` turns it into the fields the rest of the tool has always read; the
# earlier fields stay valid, so a design written either way builds the same file. `design_of` goes the other way.
SHOP_PLACES = {"kale": "Kale, the merchant of the Church of Elleh (the lines 100508, 100509, ... of ShopLineupParam)"}
_SHOP_KEY_RE = re.compile("kal[eé]|<shop-id-[0-9]+>", re.IGNORECASE)
_CAST_COLOR_RE = re.compile(r"Magic\.([0-9]+)\.castSfxId")
_EYES_COLOR_RE = re.compile(r"SpEffect\.([0-9]+)")
FIRE_EFFECT = 524400          # the cast effect of Flame, Grant Me Strength: the one `colors` has a colour plan for (writer/fxr_plans.py)
STATUS_KEYS = ("intelligence", "faith", "arcane")
COST_KEYS = {"focus_point": ("fp_cost", 999), "stamina": ("stamina_cost", 999)}


def _is_v2(it: dict) -> bool:
    req = it.get("requires")
    return "locations" in it or "customs" in it or (isinstance(req, dict) and bool({"status", "cost"} & set(req)))


def _object(c, v, path, allowed, what=None):
    """`v` must be an object whose keys are in `allowed` (plus `__info__`); -> the object (empty when it is not one)."""
    if not isinstance(v, dict):
        c.bad(path, "must be an object" + (": " + what if what else ""))
        return {}
    for k in v:
        if k != "__info__" and k not in allowed:
            c.bad("%s.%s" % (path, k), "unknown field (use %s)" % ", ".join(allowed))
    return v


def upgrade_spell(c, it: dict, p: str) -> dict:
    """A spell in the structure of section 1b -> the same spell in the fields the rest of the tool reads (`requires`, `fp_cost`,
    `stamina_cost`, `shop`, `set`, `text`, `flame_color`, `flame_accent_color`, `positive_curse_energy_eyes`). Every message names the place the
    user wrote. A spell that is not written that way comes back as it is (only `__info__`, a comment, is taken out)."""
    it = {k: v for k, v in it.items() if k != "__info__"}
    if not _is_v2(it):
        return it
    out = {k: v for k, v in it.items() if k not in ("locations", "customs", "requires")}
    if "from" not in it:
        c.bad(p, "the structure with `requires.status`, `requires.cost`, `locations` and `customs` is for a spell made from a game "
                 "spell (`from`); a heal-over-time buff made from scratch is written with its own fields")
        return out
    src = it["from"] if _int(it["from"]) else None
    # ---- requires: status (the attributes the spell needs) and cost (what casting it takes)
    if "requires" in it:
        req = _object(c, it["requires"], p + ".requires", ("status", "cost"), "status and cost")
        status = req.get("status")
        if status is not None:
            status = _object(c, status, p + ".requires.status", STATUS_KEYS)
            out["requires"] = {k: c.integer(status, k, p + ".requires.status", 0, 99, 0) for k in STATUS_KEYS if k in status}
        cost = req.get("cost")
        if cost is not None:
            cost = _object(c, cost, p + ".requires.cost", tuple(COST_KEYS))
            for k, (legacy, hi) in COST_KEYS.items():
                if k in cost:
                    v = c.integer(cost, k, p + ".requires.cost", 0, hi)
                    if v is not None:
                        out[legacy] = v
    # ---- locations: where the spell is sold (this time Kale only)
    if "locations" in it:
        loc = it["locations"]
        if not isinstance(loc, dict):
            c.bad(p + ".locations", 'must be an object: {"kale": {"price": ..., "stock": ...}}')
        else:
            places = [k for k in loc if k != "__info__"]
            for k in places:
                if not _SHOP_KEY_RE.fullmatch(k):
                    c.bad("%s.locations.%s" % (p, k), 'unknown place: this version sells only at Kale, written "kale"')
            if len(places) > 1:
                c.bad(p + ".locations", "one place only: a spell has one shop line")
            for k in places[:1]:
                if _SHOP_KEY_RE.fullmatch(k):
                    out["shop"] = _shop_obj(c, loc[k], "%s.locations.%s" % (p, k))
    # ---- customs: basic (the game's own rows, Level 2) and advanced (what is put into the running game, Level 3)
    if "customs" in it:
        cus = _object(c, it["customs"], p + ".customs", ("basic", "advanced"), "basic and advanced")
        if "basic" in cus:
            basic = cus["basic"]
            if not isinstance(basic, dict):
                c.bad(p + ".customs.basic", 'must be an object: "Magic.<from>.<field>": number, "SpEffect.<id>.<field>": number, ...')
            else:
                raw = {k: v for k, v in basic.items() if k != "__info__"}
                pseudo = {"kind": it.get("kind", "buff")}
                if src is not None:
                    pseudo["from"] = src
                out["set"] = _set(c, raw, p + ".customs.basic", pseudo)
        if "advanced" in cus:
            _advanced(c, cus["advanced"], p + ".customs.advanced", src, out)
    return out


def _advanced(c, adv, path, src, out):
    adv = _object(c, adv, path, ("texts", "colors"), "texts and colors")
    if "texts" in adv:
        raw = adv["texts"]
        if isinstance(raw, dict):             # the long description: `goods_caption` (the template) or `goods_captions`
            raw = {("goods_captions" if k == "goods_caption" else k): v for k, v in raw.items()}
        out["text"] = _text_obj(c, raw, path + ".texts", ("goods_name", "goods_info", "goods_caption", "goods_captions"))
    if "colors" not in adv:
        return
    colors = adv["colors"]
    if not isinstance(colors, dict):
        c.bad(path + ".colors", 'must be an object: "Magic.<from>.castSfxId": [r, g, b], "SpEffect.<id>": [r, g, b]')
        return
    bad_colour = "must be " + COLOUR_HELP
    for key, val in colors.items():
        if key == "__info__":
            continue
        kp = "%s.colors.%s" % (path, key)
        m, e = _CAST_COLOR_RE.fullmatch(key), _EYES_COLOR_RE.fullmatch(key)
        if m:
            if src is not None and int(m.group(1)) != src:
                c.bad(kp, "the row id must be this spell's `from` (%d)" % src)
                continue
            if isinstance(val, dict):
                for k in val:
                    if k not in ("main", "accent"):
                        c.bad("%s.%s" % (kp, k), "unknown field (use main and accent)")
                main, accent = val.get("main"), val.get("accent")
            else:
                main, accent = val, None
            if not _colour(main):
                c.bad(kp + (".main" if isinstance(val, dict) else ""), bad_colour)
                continue
            out["flame_color"] = colour_of(main)
            if accent is not None:
                if _colour(accent):
                    out["flame_accent_color"] = colour_of(accent)
                else:
                    c.bad(kp + ".accent", bad_colour)
            fx = out.get("set", {}).get("Magic.%d.castSfxId" % src) if src is not None else None
            if fx is not None and fx != FIRE_EFFECT:
                c.bad(kp, "the spell casts the effect %d, which has no colour plan (only %d, the fire of Flame, Grant Me Strength, "
                          "has one): set Magic.%d.castSfxId to %d in `customs.basic`" % (fx, FIRE_EFFECT, src, FIRE_EFFECT))
        elif e:
            eyes = {"on": "SpEffect.%d" % int(e.group(1))}
            if val is not None:
                if not _colour(val):
                    c.bad(kp, "must be null (the game's own colour) or " + COLOUR_HELP)
                    continue
                eyes["color"] = colour_of(val)
            out["positive_curse_energy_eyes"] = eyes
        else:
            c.bad(kp, 'a key is "Magic.<from>.castSfxId" (the fire and the ring of the cast) or "SpEffect.<id>" (the eyes while '
                      "that buff row lasts)")


def design_of(spell: dict) -> dict:
    """A spell of the canonical form -> the structure of section 1b (without `__info__`; `slot` and `id` are left out). A spell that
    is not made from a game spell keeps its own fields."""
    s = {k: v for k, v in spell.items() if k not in ("slot", "id")}
    if "from" not in s:
        return s
    out = {k: s[k] for k in ("kind", "from", "type") if k in s}
    req = {}
    if s.get("requires"):
        req["status"] = dict(s["requires"])
    cost = {name: s[legacy] for name, (legacy, _hi) in COST_KEYS.items() if legacy in s}
    if cost:
        req["cost"] = cost
    if req:
        out["requires"] = req
    if "shop" in s:
        out["locations"] = {"kale": dict(s["shop"])}
    customs, adv = {}, {}
    if s.get("set"):
        customs["basic"] = dict(s["set"])
    if "text" in s:
        t = s["text"]
        adv["texts"] = {"goods_name": t.get("goods_name", ""), "goods_info": t.get("goods_info", ""),
                        "goods_caption": t.get("goods_captions", "")}
    colors = {}
    if "flame_color" in s:
        main = colour_text(s["flame_color"])
        colors["Magic.%d.castSfxId" % s["from"]] = ({"main": main, "accent": colour_text(s["flame_accent_color"])}
                                                    if "flame_accent_color" in s else main)
    if "positive_curse_energy_eyes" in s:
        g = s["positive_curse_energy_eyes"]
        colors[g["on"]] = colour_text(g["color"]) if "color" in g else None
    if colors:
        adv["colors"] = colors
    if adv:
        customs["advanced"] = adv
    if customs:
        out["customs"] = customs
    return out


def normalise(data) -> dict:
    """Validate and fill in defaults -> the canonical form {"format", "maximum", "spells": [{"slot", "id", ...}]}, filled slots
    only, in slot order. Raises SpecError listing every problem found."""
    c = _Check()
    if not isinstance(data, dict):
        raise SpecError(["the file must contain a JSON object"])
    sec = data
    for key in PATH:
        sec = sec.get(key) if isinstance(sec, dict) else None
    if not isinstance(sec, dict):
        raise SpecError(['$.%s: missing (an object with "maximum" and "slots")' % SECTION])
    top = "$." + SECTION
    c.keys(sec, top, ["maximum", "slots"], [])
    maximum = sec.get("maximum")
    if not _int(maximum) or not 1 <= maximum <= MAX_SLOTS:
        c.bad(top + ".maximum", "must be a whole number from 1 to %d" % MAX_SLOTS)
        maximum = 0
    slots = sec.get("slots")
    out = []
    if not isinstance(slots, dict):
        c.bad(top + ".slots", "must be an object: one key per slot, null for an empty slot")
        slots = {}
    elif maximum and len(slots) != maximum:
        c.bad(top + ".slots", "has %d slots but maximum is %d (a slot's place in the list fixes its rows: keep every slot, "
                              "use null for an empty one)" % (len(slots), maximum))
    for n, (iid, it) in enumerate(slots.items(), 1):
        if it is None:
            continue
        p = "%s.slots[%s]" % (top, iid)
        if not re.fullmatch(ID_RE, iid):
            c.bad(p, "a filled slot's key is the spell's id: 1-40 characters, lower-case letters, digits, '_' and '-'")
        if iid in RESERVED_IDS:
            c.bad(p, "`%s` is reserved (`--add %s` means every spell): choose another id" % (iid, iid))
        if not isinstance(it, dict):
            c.bad(p, "must be an object (or null for an empty slot)")
            continue
        it = upgrade_spell(c, it, p)
        kind = it.get("kind", "buff")
        if kind in PLANNED_KINDS:
            c.bad(p + ".kind", "%r is planned but not built yet (Phase 2.4); built kinds: %s" % (kind, ", ".join(KINDS)))
            continue
        if kind not in KINDS:
            c.bad(p + ".kind", "must be one of: " + ", ".join(KINDS))
            continue
        if kind == "buff" and "from" not in it:
            o = _buff(c, it, p, n, iid)
        else:
            o = _template(c, it, p, n, iid, kind)
        out.append(o)
    if c.problems:
        raise SpecError(c.problems)
    return {"format": FORMAT, "maximum": maximum, "spells": out}


def _no_duplicate_keys(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError("the key %r appears twice in one object (the second would silently replace the first)" % k)
        d[k] = v
    return d


def parse(text: str) -> dict:
    try:
        data = json.loads(text, object_pairs_hook=_no_duplicate_keys)
    except ValueError as e:
        raise SpecError(["not valid JSON: %s" % e])
    return normalise(data)


def as_file(spec: dict) -> dict:
    """The canonical form back into the shape of design.json (filled slots keep their numbers, the others are null)."""
    by_slot = {s["slot"]: s for s in spec["spells"]}
    slots = {}
    for n in range(1, spec["maximum"] + 1):
        s = by_slot.get(n)
        slots[s["id"] if s else "<id-%d>" % n] = {k: v for k, v in s.items() if k not in ("slot", "id")} if s else None
    return {"innovate_items": {"spells": {"maximum": spec["maximum"], "slots": slots}}}


def build_view(spec: dict) -> dict:
    """What decides the bytes of the build (the text fields and the colours do not: they are put into the running game; the Positive
    Curse Energy Eyes themselves are built, their colour is not). A record written before the eyes were renamed (`golden_eyes`) reads
    the same, so it does not build again."""
    def view(it):
        it = {("positive_curse_energy_eyes" if k == "golden_eyes" else k): v for k, v in it.items()}
        out = {k: v for k, v in it.items() if k not in ("text", "name", "description", "flame_color", "flame_accent_color")}
        if "positive_curse_energy_eyes" in out:
            out["positive_curse_energy_eyes"] = {k: v for k, v in out["positive_curse_energy_eyes"].items() if k != "color"}
        return out
    return {"format": spec["format"], "spells": [view(it) for it in spec["spells"]]}


def design_view(spec: dict) -> dict:
    """What decides the bytes of the build (`build_view`), written the way the design is (section 1b): the lines of a diff then name
    the places the user edits (`locations.kale.price`, `customs.basic.SpEffect.1642100.effectEndurance`)."""
    spells = []
    for it in build_view(spec)["spells"]:
        spells.append({"id": it["id"], "slot": it["slot"], **design_of(it)})
    return {"format": spec["format"], "spells": spells}


def dumps(spec: dict) -> str:
    return json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


SELECT_PREFIXES = ("innovate_items.spells.slots", "spells.slots")      # where a spell sits in design.json, as `--add` writes it
RESERVED_IDS = ("all",)                                                 # `--add all` means every spell: no spell may be called that


def selection_of(which) -> "str | list":
    """What `--add` was given -> "all", or the ids of the spells (syntax only, nothing is looked up).

    A value is `all`, `spells.slots` (the same), `spells.slots.<id>` (the path of a spell in design.json; the leading
    `innovate_items.` is optional) or a bare `<id>`. Several can be given. `all` stands alone. Raises SpecError."""
    values = [which] if isinstance(which, str) else list(which)
    if not values:
        raise SpecError(["give `all` or the path of a spell: spells.slots.<id>"])
    ids, every = [], False
    for raw in values:
        v = raw.strip() if isinstance(raw, str) else raw
        if v == "all" or v in SELECT_PREFIXES:
            every = True
            continue
        sid = v
        if isinstance(v, str):
            for pre in SELECT_PREFIXES:
                if v.startswith(pre + "."):
                    sid = v[len(pre) + 1:]
                    break
        if not isinstance(sid, str) or not re.fullmatch(ID_RE, sid) or sid in RESERVED_IDS:
            raise SpecError(["%r is not a spell: write spells.slots.<id> (the id is the key of the slot in design.json), or all" % (raw,)])
        if sid not in ids:
            ids.append(sid)
    if every and ids:
        raise SpecError(["`all` stands alone: it already builds every spell"])
    return "all" if every else ids


def select(spec: dict, which) -> list:
    """`all`, a spell id / path, or a list of them -> the spells to build, in slot order. An id the design does not have is
    an error that lists the spells it has, as the paths `--add` takes."""
    sel = selection_of(which)
    if sel == "all":
        return list(spec["spells"])
    have = [i["id"] for i in spec["spells"]]
    missing = [i for i in sel if i not in have]
    if missing:
        raise SpecError(["no spell %s in the design%s" % (", ".join("spells.slots." + m for m in missing),
                         " (spells: %s)" % ", ".join("spells.slots." + h for h in have) if have else ": its slots are all empty")])
    return [i for i in spec["spells"] if i["id"] in sel]

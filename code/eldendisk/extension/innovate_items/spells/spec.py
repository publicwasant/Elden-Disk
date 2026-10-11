"""The `innovate_items.spells` section of extension.json: a strict stdlib validator.

    {"innovate_items": {"spells": {"maximum": 64, "slots": {"<spell-id>": {...the spell...}, "<id-2>": null, ...}}}}

A slot is a place in the list, counted from 1 in file order; its number fixes the rows the spell gets in the game (so a spell
that moves to another slot gets other rows). A slot holding null is empty and is not built. The other sections of extension.json
(other kinds of items under `innovate_items`, other extensions) and are left alone.

Text (since 1.7.1): `text` = {"goods_name", "goods_info", "goods_captions"} is the spell's name, its short line and its long
description in the game. It is not part of the build (a new text never builds again; `write --text` puts it into the running game).
Anything that needs files inside the game's archives (colour, icon) is still Level 3 and refused."""
from __future__ import annotations

import json
import re

from ..defs import Def

FORMAT = 1                    # the canonical form (what `normalise` returns and the commit record stores)
PATH = ("innovate_items", "spells")   # where this extension sits in extension.json: {"innovate_items": {"spells": {...}}}
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
TEXT_FIELDS = {"goods_name": 80, "goods_info": 300, "goods_captions": 3000}   # field -> most characters (name; the short line under it; the long description). A loose guard, not a game limit: the game's own longest are 43 / 86 / 462
RENAMED = {"name": "text.goods_name", "description": "text.goods_info (the long description is text.goods_captions)"}   # 1.7.0 -> 1.7.1


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


def _text_object(c, it, p):
    """`text`: {"goods_name", "goods_info", "goods_captions"} (each optional, text; empty = the game shows nothing). The canonical form
    always holds all three."""
    raw = it.get("text", {})
    out = {k: "" for k in TEXT_FIELDS}
    if not isinstance(raw, dict):
        c.bad(p + ".text", "must be an object: " + ", ".join('"%s"' % k for k in TEXT_FIELDS))
        return out
    c.keys(raw, p + ".text", [], list(TEXT_FIELDS))
    for k, hi in TEXT_FIELDS.items():
        out[k] = c.text(raw, k, p + ".text", hi)
    return out


def empty_text(maximum: int = MAX_SLOTS) -> str:
    """An extension.json with `maximum` empty slots: nothing to build yet."""
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


def _shop(c, it, p):
    """`shop`: optional; a spell without a shop line is built but cannot be bought (slots above 7 have no line)."""
    shop = it["shop"]
    s = {"price": 0, "stock": 1}
    if not isinstance(shop, dict):
        c.bad(p + ".shop", "must be an object")
    else:
        c.keys(shop, p + ".shop", ["price"], ["stock"])
        s["price"] = c.integer(shop, "price", p + ".shop", 1, 99999999, 1)
        s["stock"] = c.integer(shop, "stock", p + ".shop", -1, 99, 1)
        if s["stock"] == 0:
            c.bad(p + ".shop.stock", "must be -1 (unlimited) or 1 to 99")
    return s


def _flame_color(c, it, p, o):
    """`flame_color`: [red, green, blue], each 0..2 (1 = full colour, above 1 shines brighter). The fire of Flame, Grant Me Strength
    (the fire while casting and the burst; the fire on the body is left alone) is recoloured in the running game by `write --flame-color`; the effects are the game's own and
    shared by every spell that uses them, so the colour belongs to the whole design (see service.flame_color). Not part of the build."""
    if "flame_color" not in it:
        return
    v = it["flame_color"]
    if not (isinstance(v, list) and len(v) == 3 and all(_num(x) and 0 <= x <= FLAME_COLOR_MAX for x in v)):
        c.bad(p + ".flame_color", "must be three numbers [red, green, blue], each from 0 to %g (1 = full colour)" % FLAME_COLOR_MAX)
        return
    o["flame_color"] = [float(x) for x in v]


def _buff(c, it, p, n, iid):
    """A heal-over-time buff built from Flame, Grant Me Strength (the canonical form has no `kind`: it is the default)."""
    c.keys(it, p, ["type", "requires", "fp_cost"],
           ["kind", "text", "stamina_cost", "cast_motion", "effect", "poise_while_casting_seconds", "shop", "flame_color"])
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
    return o


def _template(c, it, p, n, iid, kind):
    """A spell made from a game spell: `clone` (copy of the Goods and Magic rows, it keeps calling the template's own chain),
    `buff` with `from` and `enchant` (the same, and the template's own SpEffect rows are copied too, so they can be tuned with
    `set`). What is not named stays the template's, so the canonical form holds only what the design says."""
    c.keys(it, p, ["kind", "from"], ["type", "text", "requires", "fp_cost", "stamina_cost", "shop", "set", "flame_color"])
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
    """The canonical form back into the shape of extension.json (filled slots keep their numbers, the others are null)."""
    by_slot = {s["slot"]: s for s in spec["spells"]}
    slots = {}
    for n in range(1, spec["maximum"] + 1):
        s = by_slot.get(n)
        slots[s["id"] if s else "<id-%d>" % n] = {k: v for k, v in s.items() if k not in ("slot", "id")} if s else None
    return {"innovate_items": {"spells": {"maximum": spec["maximum"], "slots": slots}}}


def build_view(spec: dict) -> dict:
    """What decides the bytes of the build (the text fields and the flame colour do not: they are put into the running game)."""
    return {"format": spec["format"],
            "spells": [{k: v for k, v in it.items() if k not in ("text", "name", "description", "flame_color")} for it in spec["spells"]]}


def dumps(spec: dict) -> str:
    return json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


SELECT_PREFIXES = ("innovate_items.spells.slots", "spells.slots")      # where a spell sits in extension.json, as `--add` writes it
RESERVED_IDS = ("all",)                                                 # `--add all` means every spell: no spell may be called that


def selection_of(which) -> "str | list":
    """What `--add` was given -> "all", or the ids of the spells (syntax only, nothing is looked up).

    A value is `all`, `spells.slots` (the same), `spells.slots.<id>` (the path of a spell in extension.json; the leading
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
            raise SpecError(["%r is not a spell: write spells.slots.<id> (the id is the key of the slot in extension.json), or all" % (raw,)])
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

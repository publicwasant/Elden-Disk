"""The items.draft.json spec: a strict stdlib validator.

Level 2a rules (handbook Part VI): one incantation per build; text (name, description) is stored but not written into the
game; anything that needs files inside the game's archives (colour, icon) is Level 3 and refused."""
from __future__ import annotations

import json
import re

FORMAT = 1
EMPTY_SPEC = '{\n  "format": 1,\n  "items": []\n}\n'      # what the first run writes: nothing to build yet
MAX_ITEMS_2A = 1
CAST_MOTIONS = {"flame-grant-me-strength": 31, "black-flame-blade": 32}
VISUALS = ("flame", "flask")
LEVEL3_KEYS = {"icon", "icon_file", "colour", "color", "text", "flame_color", "model"}


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
            if k in LEVEL3_KEYS:
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


def normalise(data) -> dict:
    """Validate and fill in defaults -> the canonical form. Raises SpecError listing every problem found."""
    c = _Check()
    if not isinstance(data, dict):
        raise SpecError(["the file must contain a JSON object"])
    c.keys(data, "$", ["items"], ["format"])
    if data.get("format", FORMAT) != FORMAT:
        c.bad("$.format", "must be %d" % FORMAT)
    items = data.get("items")
    out = []
    if not isinstance(items, list):
        c.bad("$.items", "must be a list (an empty list means: no items yet)")
        items = []
    seen = set()
    for n, it in enumerate(items):
        p = "$.items[%d]" % n
        if not isinstance(it, dict):
            c.bad(p, "must be an object")
            continue
        c.keys(it, p, ["id", "type", "requires", "fp_cost", "shop"],
               ["name", "description", "stamina_cost", "cast_motion", "effect", "poise_while_casting_seconds"])
        iid = it.get("id")
        if not isinstance(iid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", iid):
            c.bad(p + ".id", "must be 1-40 characters: lower-case letters, digits and '-'")
        elif iid in seen:
            c.bad(p + ".id", "duplicate id")
        else:
            seen.add(iid)
        if it.get("type") != "incantation":
            c.bad(p + ".type", 'only "incantation" is supported')
        o = {"id": iid if isinstance(iid, str) else "", "type": "incantation",
             "name": c.text(it, "name", p, 80), "description": c.text(it, "description", p, 400)}
        req = it.get("requires")
        r = {"intelligence": 0, "faith": 0, "arcane": 0}
        if not isinstance(req, dict):
            c.bad(p + ".requires", "must be an object")
        else:
            c.keys(req, p + ".requires", [], list(r))
            for k in r:
                r[k] = c.integer(req, k, p + ".requires", 0, 99, 0)
        o["requires"] = r
        o["fp_cost"] = c.integer(it, "fp_cost", p, 0, 999, 0)
        o["stamina_cost"] = c.integer(it, "stamina_cost", p, 0, 999, 0)
        cm = it.get("cast_motion", "flame-grant-me-strength")
        if cm not in CAST_MOTIONS:
            c.bad(p + ".cast_motion", "must be one of: " + ", ".join(sorted(CAST_MOTIONS)))
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
            v = eff.get("visual", "flame")
            if v not in VISUALS:
                c.bad(p + ".effect.visual", "must be one of: " + ", ".join(VISUALS))
                v = "flame"
            e["visual"] = v
        o["effect"] = e
        if "poise_while_casting_seconds" in it:
            o["poise_while_casting_seconds"] = c.real(it, "poise_while_casting_seconds", p, 0.1, 10, 2.0)
        shop = it.get("shop")
        s = {"price": 0, "stock": 1}
        if not isinstance(shop, dict):
            c.bad(p + ".shop", "must be an object")
        else:
            c.keys(shop, p + ".shop", ["price"], ["stock"])
            s["price"] = c.integer(shop, "price", p + ".shop", 1, 99999999, 1)
            s["stock"] = c.integer(shop, "stock", p + ".shop", -1, 99, 1)
            if s["stock"] == 0:
                c.bad(p + ".shop.stock", "must be -1 (unlimited) or 1 to 99")
        o["shop"] = s
        out.append(o)
    if c.problems:
        raise SpecError(c.problems)
    return {"format": FORMAT, "items": out}


def parse(text: str) -> dict:
    try:
        data = json.loads(text)
    except ValueError as e:
        raise SpecError(["not valid JSON: %s" % e])
    return normalise(data)


def build_view(spec: dict) -> dict:
    """What decides the bytes of the build (the text fields do not)."""
    return {"format": spec["format"],
            "items": [{k: v for k, v in it.items() if k not in ("name", "description")} for it in spec["items"]]}


def dumps(spec: dict) -> str:
    return json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def select(spec: dict, which: str) -> list:
    """`all` or an item id -> the items to build."""
    if which == "all":
        return list(spec["items"])
    hit = [i for i in spec["items"] if i["id"] == which]
    if not hit:
        raise SpecError(["no item with id %r (have: %s)" % (which, ", ".join(i["id"] for i in spec["items"]))])
    return hit

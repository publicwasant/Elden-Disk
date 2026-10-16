"""The spells as `read` shows them and `write` changes them in the running game (1.7.2; 1.8.0 part 2). Pure: names and ids only.

The document gets a block `creative.innovate_spells.<goods id>`: what spells.resolved.json says of each spell of the last build (its
label `id`, `slot`, the `rows` it owns) and, apart, its `design` in the structure of section 1b (`kind`, `from`, `requires`,
`locations`, `customs`) with the values the game holds now. Every value of the design that is a value of the game can be written back
(the names below are under `design.`):

  requires.status.intelligence | faith | arcane    Magic.<the spell's Magic row>.requirementIntellect | requirementFaith | requirementLuck
  requires.cost.focus_point | stamina              Magic.<...>.mp | stamina
  locations.kale.price | stock                     ShopLineup.<the spell's shop line>.value | sellQuantity
  customs.basic.<Table>.<template id>.<field>      the same field of the spell's own row: Magic / Goods <from> -> the spell's Magic /
                                                   Goods row, SpEffect / Bullet / AtkParam_Pc rows -> their copies (rows.copies)
  customs.advanced.texts.goods_name | goods_info | goods_caption    the text in the game's text tables
  customs.advanced.colors."<key>"(.<place>)       1.8.3 part 2: a colour place of the effect the key points at (`0x4290`), or every
                                                   place of it (spec.COLOR_KEY_RE)
  customs.advanced.colors."Magic.<from>.castSfxId"(.main | .accent)  a design written before 1.8.3 part 2: the fire, the ring
  customs.advanced.colors."SpEffect.<id>"                            a design written before 1.8.3 part 2: the eyes

`id`, `slot`, `rows`, `design.kind` and `design.from` are what the build made; they cannot be written (build again)."""
from __future__ import annotations

from .spec import COLOR_KEY_RE, PLACE_RE

STATUS = {"intelligence": "requirementIntellect", "faith": "requirementFaith", "arcane": "requirementLuck"}
COST = {"focus_point": "mp", "stamina": "stamina"}
SHOP = {"price": "value", "stock": "sellQuantity"}
TEXTS = {"goods_name": "goods_name", "goods_info": "goods_info", "goods_caption": "goods_captions"}
OWN_ROWS = ("Magic", "Goods")
COPIED = ("SpEffect", "Bullet", "AtkParam_Pc")
FIXED = ("id", "slot", "rows", "kind", "from", "type")


class Locked(ValueError):
    """A name of the block that is not a value of the game, or names nothing."""


def node(goods: str, rec: dict) -> dict:
    """One spell of spells.resolved.json -> its node in the document: the build's facts (`id`, `slot`, `rows`) and the `design`."""
    return {"id": rec["id"], "slot": rec["slot"], "rows": rec["rows"], "design": dict(rec.get("design", {}))}


def split(parts) -> list[str]:
    """A path below the spell as given (`customs.basic.SpEffect.1642100.effectEndurance` split at every dot, or with the dotted key in
    one piece) -> the path with the keys of `basic` and `colors` whole: [..., "basic", "SpEffect.1642100.effectEndurance"],
    [..., "colors", "Magic.6421.castSfxId", "main"]."""
    parts = [str(p) for p in parts]
    flat = ".".join(parts).split(".")
    if flat[:1] == ["design"]:
        return ["design", *split(flat[1:])]
    if "basic" in flat[:3] and flat[:2] == ["customs", "basic"]:
        return ["customs", "basic", ".".join(flat[2:])]
    if flat[:3] == ["customs", "advanced", "colors"]:
        rest = flat[3:]
        if rest[:1] in (["Magic"], ["Bullet"], ["SpEffectVfx"]):   # Magic.<id>.castSfxId, Bullet.<id>.sfxId_Bullet, SpEffectVfx... (1.8.3)
            return ["customs", "advanced", "colors", ".".join(rest[:3]), *rest[3:]]
        if rest[:1] == ["Sfx"]:
            return ["customs", "advanced", "colors", ".".join(rest[:2]), *rest[2:]]
        if rest[:1] == ["SpEffect"]:
            return ["customs", "advanced", "colors", ".".join(rest[:2]), *rest[2:]]
    return flat


def target(goods: str, rec: dict, parts) -> tuple:
    """What a name below the spell `goods` writes in the game:
        ("param", "params.<Table>.<id>.<field>")            a field of a row of the six tables
        ("text", goods id, "goods_name" | "goods_info" | "goods_captions")
        ("colour", "main" | "accent" | "eyes")             a design written before 1.8.3 part 2
        ("colours", key, place | None)                       1.8.3 part 2: a colour place of the effect `key` points at, or all of them
    Locked when it is not a value of the game."""
    p = split(parts)
    rows = rec["rows"]
    design = rec.get("design", {})
    where = "creative.innovate_spells.%s.%s" % (goods, ".".join(p))
    if not p or p[0] in FIXED:
        raise Locked(f"{where}: made by the build, not a value of the game (change the design and build again)")
    if p[0] != "design":
        raise Locked(f"{where}: not a value of the spell (its values are under `design`)")
    p = p[1:]
    if not p or p[0] in FIXED:
        raise Locked(f"{where}: made by the build, not a value of the game (change the design and build again)")
    if p[:2] == ["requires", "status"] and len(p) == 3 and p[2] in STATUS:
        return ("param", "params.Magic.%d.%s" % (rows["magic"], STATUS[p[2]]))
    if p[:2] == ["requires", "cost"] and len(p) == 3 and p[2] in COST:
        return ("param", "params.Magic.%d.%s" % (rows["magic"], COST[p[2]]))
    if p[:2] == ["locations", "kale"] and len(p) == 3 and p[2] in SHOP:
        if not rows.get("shop"):
            raise Locked(f"{where}: this spell has no shop line")
        return ("param", "params.ShopLineup.%d.%s" % (rows["shop"], SHOP[p[2]]))
    if p[:2] == ["customs", "basic"] and len(p) == 3:
        try:
            table, tid, field = p[2].split(".", 2)
        except ValueError:
            raise Locked(f"{where}: a key of basic is <Table>.<row id>.<field>") from None
        if table in OWN_ROWS:
            if str(design.get("from")) != tid:
                raise Locked(f"{where}: {table} {tid} is not the row this spell is made from ({design.get('from')})")
            return ("param", "params.%s.%d.%s" % (table, rows["magic" if table == "Magic" else "goods"], field))
        if table in COPIED:
            copies = rows.get("copies", {}).get(table, {})
            if tid not in copies:
                why = ("the build did not record its copies (build again)" if "copies" not in rows
                       else f"{table} {tid} is not a row this spell copied (copied: {', '.join(copies) or 'none'})")
                raise Locked(f"{where}: {why}")
            return ("param", "params.%s.%d.%s" % (table, copies[tid], field))
        raise Locked(f"{where}: {table} is not a table a spell is made of")
    if p[:3] == ["customs", "advanced", "texts"] and len(p) == 4 and p[3] in TEXTS:
        return ("text", rows["goods"], TEXTS[p[3]])
    if p[:3] == ["customs", "advanced", "colors"] and len(p) in (4, 5):
        key, sub = p[3], (p[4] if len(p) == 5 else None)
        now = design.get("customs", {}).get("advanced", {}).get("colors", {}).get(key)
        legacy = isinstance(now, (str, list)) or (isinstance(now, dict) and bool({"main", "accent"} & set(now)))
        if COLOR_KEY_RE.fullmatch(key) and not legacy and (sub is None or PLACE_RE.fullmatch(sub)):
            return ("colours", key, None if sub is None else "0x%x" % int(sub, 16))
        if key.startswith("Magic.") and key.endswith(".castSfxId"):
            if sub in (None, "main"):
                return ("colour", "main")
            if sub == "accent":
                return ("colour", "accent")
        if key.startswith("SpEffect.") and sub is None:
            return ("colour", "eyes")
    raise Locked(f"{where}: not a value of the game")


def reads(goods: str, rec: dict) -> dict:
    """{path below the spell (a tuple): "params.<Table>.<id>.<field>"} of every value of the node that a row of the game holds (to show
    what the game holds now)."""
    design = rec.get("design", {})
    out = {}
    for path in _paths(design):
        try:
            kind, *what = target(goods, rec, ["design", *path])
        except Locked:
            continue
        if kind == "param":
            out[("design", *path)] = what[0]
    return out


def _paths(d: dict, prefix=()):
    for k, v in d.items():
        if isinstance(v, dict) and k not in ("colors",):
            yield from _paths(v, prefix + (k,))
        elif not isinstance(v, dict):
            yield list(prefix + (k,))


def put(d: dict, path, value) -> None:
    """Set `value` at `path` (keys as `split` gives them) in the nested dict `d`."""
    cur = d
    for k in path[:-1]:
        cur = cur.setdefault(k, {})
    cur[path[-1]] = value

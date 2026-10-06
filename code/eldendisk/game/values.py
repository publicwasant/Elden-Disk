"""Names of the values `read --query` and `write --set` understand.

A name is a path into the `disk-state.json` document (`character.attributes.vigor`) or a short form of it. Short forms
exist for typing: `character.` may be left out, `attrs` = `attributes`, `hp` = `hit_point`, `fp` = `focus_point`,
`max` = `maximum`.

One rule for bare group names: reading `hp` or `runes` shows the whole group (current, maximum, base / total, baseline,
delta); writing `hp` or `runes` means the one value you can set (`...current`, `...total`).

Pure functions, no memory access. Which offsets a value lives at stays in the profile (offsets.json) and the layout.
"""
from __future__ import annotations

import difflib
from fnmatch import fnmatchcase

from .layout import ATTR_NAMES

VITALS = ("hit_point", "focus_point", "stamina")
POLICY_KEY = {   # settable value -> the key of the writer's edit policy
    "character.level": "level",
    "character.runes.total": "runes",
    **{f"character.attributes.{a}": a for a in ATTR_NAMES},
    "character.vitals.hit_point.current": "hp",
    "character.vitals.focus_point.current": "fp",
    "character.vitals.stamina.current": "stamina",
}
WRITABLE = tuple(POLICY_KEY)
_SEGMENTS = {"attrs": "attributes", "rune": "runes", "animation": "animations", "hp": "hit_point", "fp": "focus_point",
             "max": "maximum"}
_ROOTS = ("character", "systems")
_READ_ONLY_WHY = (
    ("character.vitals.", ("maximum", "base"),
     "computed by the game from your stats (set the attribute, or use hp/fp/stamina for the current value)"),
    ("character.runes.", ("baseline", "delta"), "computed by the tool from the runes seen when reading started"),
)


class UnknownName(ValueError):
    def __init__(self, name: str, suggestions: list[str]):
        self.name, self.suggestions = name, suggestions
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"unknown name {name!r}{hint}")


def normalize(name: str) -> str:
    """The canonical dotted path of `name` (wildcards pass through). Does not check that the path exists."""
    n = name.strip().lower()
    segs = [_SEGMENTS.get(s, s) for s in n.split(".") if s != ""]
    if segs and segs[0] == "character":
        segs = segs[1:] or ["character"]
        if segs == ["character"]:
            return "character"
    if segs and segs[0] != "systems":
        if segs[0] in VITALS:
            segs.insert(0, "vitals")
        elif segs[0] in ATTR_NAMES:
            segs.insert(0, "attributes")
        elif segs[0] == "stamina":
            segs.insert(0, "vitals")
        segs.insert(0, "character")
    return ".".join(segs) if segs else ""


def suggest(name: str, candidates) -> list[str]:
    """Close matches for a mistyped name: by the last part first (`vigr` -> attributes.vigor), then by the whole path."""
    paths = list(candidates)
    tails: dict[str, list[str]] = {}
    for p in paths:
        tails.setdefault(p.rsplit(".", 1)[-1], []).append(p)
    wanted = normalize(name)
    out: list[str] = []
    for t in difflib.get_close_matches(wanted.rsplit(".", 1)[-1], list(tails), n=3, cutoff=0.6):
        out += tails[t]
    out += difflib.get_close_matches(wanted, paths, n=3, cutoff=0.6)
    return list(dict.fromkeys(out))[:3]


def is_pattern(name: str) -> bool:
    return any(c in name for c in "*?[")


def write_targets(name: str) -> list[str]:
    """Policy keys (`level`, `runes`, `vigor`, `hp` ...) that `--set NAME=` / `--refill` mean. ValueError otherwise."""
    path = normalize(name)
    if is_pattern(path):
        rest = path.removeprefix("character.")
        if is_pattern(rest.split(".")[0]) or path in ("", "character"):
            raise ValueError(f"{name!r}: a pattern must name a group, e.g. attributes.* (not everything at once)")
        hits = [p for p in WRITABLE if fnmatchcase(p, path)]
        if not hits:
            raise ValueError(f"{name!r}: matches no value you can set (settable: {', '.join(POLICY_KEY.values())})")
        return [POLICY_KEY[p] for p in hits]
    if path in ("character.runes", *(f"character.vitals.{v}" for v in VITALS)):
        path += ".total" if path.endswith("runes") else ".current"
    if path in POLICY_KEY:
        return [POLICY_KEY[path]]
    for prefix, fields, why in _READ_ONLY_WHY:
        if path.startswith(prefix) and path.rsplit(".", 1)[1] in fields:
            raise ValueError(f"{name!r} cannot be set: {why}")
    if path.startswith(("character.effects", "character.animations", "systems")):
        raise ValueError(f"{name!r} cannot be set: it is not a stored character value")
    if path in ("character", "character.attributes", "character.vitals"):
        raise ValueError(f"{name!r} is a group: name one value, or use a pattern such as attributes.*")
    raise UnknownName(name, suggest(name, WRITABLE))

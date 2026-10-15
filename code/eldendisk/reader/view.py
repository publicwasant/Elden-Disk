"""Looking things up in the document `read` builds, and turning them into rows (pure functions, no console code).

`select(doc, name)` finds the value(s) a name means (names: `game.values`); `rows(...)` lays them out for the console;
`flatten` / `changes` give the change stream of `--live`.
"""
from __future__ import annotations

import json
from fnmatch import fnmatchcase
from typing import NamedTuple

from ..game.values import DISK, FULL_ROOTS, PARAMS, UnknownName, is_pattern, normalize, suggest

TICKING = (".buff_duration",)     # countdowns: the live views paint them in their own colour, they are never "changes"
VOLATILE = (*TICKING, "systems.status.ignored.buffs", "systems.status.ignored.animations")
# buff countdowns and the counters of ignored buffs / animations change every few frames; the change stream
# (the fallback for consoles that cannot redraw in place) leaves them out
LISTS = ("character.buffs", "character.animations", "creative.resurrect.great_enemies")   # these come and go (a boss is in the
# last one only while it is defeated): no match now is not a wrong name


class Row(NamedTuple):
    indent: int
    key: str
    value: str | None   # None = a heading (a group)
    path: str = ""      # the dotted path of the value (for highlighting what changed)


def flatten(value, prefix: str = "") -> dict[str, object]:
    """{dotted path: scalar} of every leaf of `value`."""
    out: dict[str, object] = {}
    _flatten_into(out, value, prefix)
    return out


def _flatten_into(out: dict, value, prefix: str) -> None:
    """One dict for the whole tree (a whole table is millions of leaves: no dict per level copied into its parent)."""
    if isinstance(value, dict):
        for k, v in value.items():
            _flatten_into(out, v, f"{prefix}.{k}" if prefix else str(k))
    else:
        out[prefix] = value


def _walk(path: str, value) -> object:
    cur = value
    for seg in path.split("."):
        if not isinstance(cur, dict) or seg not in cur:
            raise KeyError(path)
        cur = cur[seg]
    return cur


def _names_a_list(path: str) -> bool:
    """True when `path` (a name or a pattern) points into the buff or animation list."""
    return any(path == m or path.startswith(m + ".") for m in LISTS)


def _wanted(names) -> list[str]:
    if names is None:
        return []
    return [n for n in ([names] if isinstance(names, str) else names) if n and n.strip()]


def label(names) -> str:
    """The names as typed, for messages and the banner."""
    return " ".join(_wanted(names)) or "all values"


def select(doc: dict, names: str | list[str] | None) -> list[tuple[str, object]]:
    """[(canonical path, value or subtree)] for one name or several; the whole document (what `disk.json` holds) for none. A path selected twice (`runes` and `runes.total`) is listed once, in the order first asked.

    UnknownName if a name matches nothing, except for names inside the buff and animation lists: they are empty
    when nothing is active, so no match there gives nothing.
    """
    wanted = _wanted(names)
    if not wanted:
        return [("", doc)]
    out: list[tuple[str, object]] = []
    for name in wanted:
        for path, value in _select_disk(doc, name):
            if all(path != p for p, _ in out):
                out.append((path, value))
    return out


def _select_disk(doc: dict, name: str) -> list[tuple[str, object]]:
    """`disk`, `disk.*`: the whole document under `disk`; `disk.<path>`: that path, shown as `disk.<path>` (the name as `disk.json`
    holds it, 1.8.0). A name without `disk.` is selected and shown as before."""
    head, _dot, rest = name.strip().partition(".")
    if head.lower() != DISK:
        return _select_one(doc, name)
    if rest.strip() in ("", "*"):
        return [(DISK, doc)]
    return [(f"{DISK}.{path}" if path else DISK, value) for path, value in _select_one(doc, rest)]


def _canonical(leaves: dict[str, object]) -> dict[str, str]:
    """{lower-case path: path as the document spells it}, for every leaf and every group above it."""
    out: dict[str, str] = {}
    for p in leaves:
        parts = p.split(".")
        for i in range(1, len(parts) + 1):
            q = ".".join(parts[:i])
            out.setdefault(q.lower(), q)
    return out


SPELLS = "creative.innovate_spells."
ENEMIES = "creative.resurrect.great_enemies."


def _enemy_key(name: str) -> str:
    return "_".join(w for w in "".join(c if c.isalnum() else " " for c in str(name).lower()).split())


def _by_enemy_name(doc: dict, path: str) -> str:
    """`creative.resurrect.great_enemies.<name>...` -> the same path with the boss's id (`margit`, `mohg_lord_of_blood`)."""
    head, _dot, rest = path[len(ENEMIES):].partition(".")
    enemies = ((doc.get("creative") or {}).get("resurrect") or {}).get("great_enemies") or {}
    if head in enemies or not head or is_pattern(head):
        return path
    keys = {rid: _enemy_key(e.get("name", "")) for rid, e in enemies.items() if isinstance(e, dict)}
    hits = [rid for rid, k in keys.items() if k == head] or [rid for rid, k in keys.items() if k.startswith(head + "_") or k == head]
    if len({keys[r] for r in hits}) == 1:
        return ENEMIES + hits[0] + ("." + rest if rest else "")
    return path


def _by_label(doc: dict, path: str) -> str:
    """`creative.innovate_spells.<label>...` -> the same path with the spell's goods id (a spell is named by both); a great enemy by
    its name the same way."""
    if path.startswith(ENEMIES):
        return _by_enemy_name(doc, path)
    if not path.startswith(SPELLS):
        return path
    head, _dot, rest = path[len(SPELLS):].partition(".")
    spells = (doc.get("creative") or {}).get("innovate_spells") or {}
    if head in spells:
        return path
    for goods, s in spells.items():
        if isinstance(s, dict) and str(s.get("id", "")).lower() == head:
            return SPELLS + goods + ("." + rest if rest else "")
    return path


INVENTORY = "character.inventory."


def _by_item_name(doc: dict, path: str) -> list[str] | None:
    """`character.inventory.<name>...` (1.8.1) -> the paths of every item of that name, in any kind (`gold_pickled_fowl_foot`, as a
    boss is found by name); None when `<name>` is a kind of the inventory, a pattern, or no item's name."""
    head, _dot, rest = path[len(INVENTORY):].partition(".")
    inv = (doc.get("character") or {}).get("inventory") or {}
    if not head or head in inv or is_pattern(head):
        return None
    hits = [f"{INVENTORY}{group}.{iid}" + ("." + rest if rest else "") for group, items in inv.items() if isinstance(items, dict)
            for iid, item in items.items() if isinstance(item, dict) and item.get("name") and _enemy_key(item["name"]) == head]
    return hits or None


def _select_one(doc: dict, name: str) -> list[tuple[str, object]]:
    path = _by_label(doc, normalize(name))
    if path.startswith(INVENTORY):
        named = _by_item_name(doc, path)
        if named:
            out = []
            for p in named:
                try:
                    out.append((p, _walk(p, doc)))
                except KeyError:
                    pass
            if out:
                return out
    leaves = flatten(doc)
    if is_pattern(path):
        hits = [(p, v) for p, v in leaves.items() if fnmatchcase(p.lower(), path)]
        if hits:
            return hits
    else:
        if path.startswith(FULL_ROOTS):   # `params` / `creative` names are typed in any letter case (effectEndurance), the rest is lower-case
            path = _canonical(leaves).get(path, path)
        try:
            return [(path, _walk(path, doc))]
        except KeyError:
            pass
        if path in leaves:            # a key with dots in it (`creative....basic.SpEffect.1642100.effectEndurance`)
            return [(path, leaves[path])]
        under = [(p, v) for p, v in leaves.items() if p.startswith(path + ".")]
        if under:                     # the first parts of such a key (`....colors.Magic.6421.castSfxId`)
            return under
    if _names_a_list(path):
        return []       # the lists come and go (a buff ends, an animation stops): no match now is not a wrong name
    known = (set(leaves) | {p.rsplit(".", 1)[0] for p in leaves if "." in p}) - {"character", "systems"}
    raise UnknownName(name, suggest(name, sorted(known)))


_FULL = tuple(r + "." for r in FULL_ROOTS)                 # paths whose numbers are shown as they are
_FULL_OR_EQUIPMENT = _FULL + ("character.equipment.",)


def fmt(key: str, value, path: str = "") -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        if key == "delta":
            return f"{value:+,}"
        return str(value) if key in ("pid", "code") or path.startswith(_FULL_OR_EQUIPMENT) \
            else f"{value:,}"   # ids: no commas
    if isinstance(value, float):
        return repr(value) if path.startswith(_FULL) else f"{value:.2f}"   # params: -1.0 and 0.01 as they are
    if isinstance(value, list):
        return ", ".join(fmt(key, v, path) for v in value) if all(not isinstance(v, (dict, list)) for v in value) \
            else json.dumps(value)
    return str(value)


def _rows(value: dict, indent: int, prefix: str, out: list[Row]) -> list[Row]:
    """The rows of the tree into `out` (a list, not nested generators: a whole table of the game is millions of rows)."""
    for key, v in value.items():
        key = str(key)
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(v, dict):
            out.append(Row(indent, key, None, path))
            _rows(v, indent + 1, path, out)
        else:
            out.append(Row(indent, key, fmt(key, v, path), path))
    return out


def _flat_rows(value, prefix: str, out: list[Row]) -> None:
    """One `full.path  value` row per leaf, in the order of `flatten`, without building its dict first."""
    if isinstance(value, dict):
        for key, v in value.items():
            _flat_rows(v, f"{prefix}.{key}" if prefix else str(key), out)
    else:
        out.append(Row(0, prefix, fmt(prefix.rsplit(".", 1)[-1], value, prefix), prefix))


def _graft(tree: dict, parts: list[str], value) -> None:
    """Put `value` into the nested `tree` at `parts` (a group is merged into what is already there)."""
    for part in parts[:-1]:
        tree = tree.setdefault(part, {})
    if not parts:
        if isinstance(value, dict):
            _merge(tree, value)
    elif isinstance(value, dict):
        _merge(tree.setdefault(parts[-1], {}), value)
    else:
        tree[parts[-1]] = value


def _merge(dst: dict, src: dict) -> None:
    for key, v in src.items():
        if isinstance(v, dict):
            _merge(dst.setdefault(key, {}), v)
        else:
            dst[key] = v


def rows(selection: list[tuple[str, object]], flat: bool = False) -> list[Row]:
    """Console rows for a selection: the selected values placed in their tree (`character` > `runes` > `total`),
    exactly as the whole document is printed, so a wildcard or several names read like `read` itself. One single
    value is one `path  value` row. `flat`: every value is one `full.path  value` row, no headings."""
    if flat:
        out: list[Row] = []
        for top, sub in selection:
            _flat_rows(sub, top, out)
        return out
    if len(selection) == 1 and selection[0][0] and not isinstance(selection[0][1], dict):
        path, value = selection[0]
        return [Row(0, path, fmt(path.rsplit(".", 1)[-1], value, path), path)]
    tree: dict = {}
    for path, value in selection:
        _graft(tree, path.split(".") if path else [], value)
    return _rows(tree, 0, "", [])


def as_json(selection: list[tuple[str, object]]) -> str:
    if len(selection) == 1 and selection[0][0] == "":
        return json.dumps(selection[0][1], indent=2)
    return json.dumps(dict(selection), indent=2)


def changes(prev: dict[str, object], cur: dict[str, object]) -> list[tuple[str, object, object]]:
    """[(path, old, new)] between two flattened views; a missing side is None. Buff countdowns are ignored."""
    out = []
    for path in sorted(prev.keys() | cur.keys()):
        if path.endswith(VOLATILE):
            continue
        old, new = prev.get(path), cur.get(path)
        if old != new:
            out.append((path, old, new))
    return out

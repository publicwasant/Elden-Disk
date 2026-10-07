"""Looking things up in the document `read` builds, and turning them into rows (pure functions, no console code).

`select(doc, name)` finds the value(s) a name means (names: `game.values`); `rows(...)` lays them out for the console;
`flatten` / `changes` give the change stream of `--live`.
"""
from __future__ import annotations

import json
from fnmatch import fnmatchcase
from typing import Iterator, NamedTuple

from ..game.values import UnknownName, is_pattern, normalize, suggest

TICKING = (".buff_duration",)     # countdowns: the live views paint them in their own colour, they are never "changes"
VOLATILE = (*TICKING, "systems.status.ignored.effects", "systems.status.ignored.animations")
# buff countdowns and the counters of ignored effects / animations change every few frames; the change stream
# (the fallback for consoles that cannot redraw in place) leaves them out
LISTS = ("character.effects", "character.animations")   # these come and go: no match now is not a wrong name


class Row(NamedTuple):
    indent: int
    key: str
    value: str | None   # None = a heading (a group)
    path: str = ""      # the dotted path of the value (for highlighting what changed)


def flatten(value, prefix: str = "") -> dict[str, object]:
    """{dotted path: scalar} of every leaf of `value`."""
    out: dict[str, object] = {}
    if isinstance(value, dict):
        for k, v in value.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    else:
        out[prefix] = value
    return out


def _walk(path: str, value) -> object:
    cur = value
    for seg in path.split("."):
        if not isinstance(cur, dict) or seg not in cur:
            raise KeyError(path)
        cur = cur[seg]
    return cur


def _names_a_list(path: str) -> bool:
    """True when `path` (a name or a pattern) points into the effect or animation list."""
    return any(path == m or path.startswith(m + ".") for m in LISTS)


def _wanted(names) -> list[str]:
    if names is None:
        return []
    return [n for n in ([names] if isinstance(names, str) else names) if n and n.strip()]


def label(names) -> str:
    """The names as typed, for messages and the banner."""
    return " ".join(_wanted(names)) or "all values"


def select(doc: dict, names: str | list[str] | None) -> list[tuple[str, object]]:
    """[(canonical path, value or subtree)] for one name or several; the whole document (what `disk-state.json`
    holds) for none. A path selected twice (`runes` and `runes.total`) is listed once, in the order first asked.

    UnknownName if a name matches nothing, except for names inside the effect and animation lists: they are empty
    when nothing is active, so no match there gives nothing.
    """
    wanted = _wanted(names)
    if not wanted:
        return [("", doc)]
    out: list[tuple[str, object]] = []
    for name in wanted:
        for path, value in _select_one(doc, name):
            if all(path != p for p, _ in out):
                out.append((path, value))
    return out


def _select_one(doc: dict, name: str) -> list[tuple[str, object]]:
    path = normalize(name)
    leaves = flatten(doc)
    if is_pattern(path):
        hits = [(p, v) for p, v in leaves.items() if fnmatchcase(p, path)]
        if hits:
            return hits
    else:
        try:
            return [(path, _walk(path, doc))]
        except KeyError:
            pass
    if _names_a_list(path):
        return []       # the lists come and go (an effect ends, an animation stops): no match now is not a wrong name
    known = (set(leaves) | {p.rsplit(".", 1)[0] for p in leaves if "." in p}) - {"character", "systems"}
    raise UnknownName(name, suggest(name, sorted(known)))


def fmt(key: str, value) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        if key == "delta":
            return f"{value:+,}"
        return str(value) if key in ("pid", "code") else f"{value:,}"
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, list):
        return ", ".join(fmt(key, v) for v in value) if all(not isinstance(v, (dict, list)) for v in value) \
            else json.dumps(value)
    return str(value)


def _rows(value: dict, indent: int, prefix: str) -> Iterator[Row]:
    for key, v in value.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(v, dict):
            yield Row(indent, str(key), None, path)
            yield from _rows(v, indent + 1, path)
        else:
            yield Row(indent, str(key), fmt(str(key), v), path)


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
        return [Row(0, path, fmt(path.rsplit(".", 1)[-1], value), path)
                for top, sub in selection for path, value in flatten(sub, top).items()]
    if len(selection) == 1 and selection[0][0] and not isinstance(selection[0][1], dict):
        path, value = selection[0]
        return [Row(0, path, fmt(path.rsplit(".", 1)[-1], value), path)]
    tree: dict = {}
    for path, value in selection:
        _graft(tree, path.split(".") if path else [], value)
    return list(_rows(tree, 0, ""))


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

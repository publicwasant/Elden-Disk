"""Looking things up in the document `read` builds, and turning them into rows (pure functions, no console code).

`select(doc, name)` finds the value(s) a name means (names: `game.values`); `rows(...)` lays them out for the console;
`flatten` / `changes` give the change stream of `--live`.
"""
from __future__ import annotations

import json
from fnmatch import fnmatchcase
from typing import Iterator, NamedTuple

from ..game.values import UnknownName, is_pattern, normalize, suggest

VOLATILE = (".buff_duration", "systems.status.ignored.effects", "systems.status.ignored.animations")
# buff countdowns and the counters of ignored effects / animations change every few frames; the change stream
# (the fallback for consoles that cannot redraw in place) leaves them out
MONITORED = ("character.effects", "character.animations")   # the lists the monitors own


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


def visible(doc: dict) -> dict:
    """The document as `read` shows it without a name: the values only. The effect and animation lists are long and
    belong to their monitors (`--live-effects`, `--live-animations`); ask for them by name (`--query effects`).
    `disk-state.json` carries them either way."""
    ch = doc.get("character")
    if not isinstance(ch, dict):
        return doc
    return {**doc, "character": {k: v for k, v in ch.items() if f"character.{k}" not in MONITORED}}


def _names_a_list(path: str) -> bool:
    """True when `path` (a name or a pattern) asks for the effect or animation list itself."""
    return any(path == m or path.startswith(m + ".") for m in MONITORED)


def select(doc: dict, name: str | None) -> list[tuple[str, object]]:
    """[(canonical path, value or subtree)] for `name`; the values of the whole document for None (see `visible`).

    A name that points into the effect or animation lists reads them; a wildcard such as `character.*` does not
    drag them in. UnknownName if nothing matches.
    """
    if not name or not name.strip():
        return [("", visible(doc))]
    path = normalize(name)
    leaves = flatten(doc if _names_a_list(path) else visible(doc))
    if is_pattern(path):
        hits = [(p, v) for p, v in leaves.items() if fnmatchcase(p, path)]
        if hits:
            return hits
    else:
        try:
            return [(path, _walk(path, doc))]
        except KeyError:
            pass
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


def rows(selection: list[tuple[str, object]]) -> list[Row]:
    """Console rows for a selection: a group becomes a heading with its values below, a leaf one `path  value` row."""
    out: list[Row] = []
    for path, value in selection:
        if isinstance(value, dict):
            if path:
                out.append(Row(0, path, None, path))
            out.extend(_rows(value, 1 if path else 0, path))
        else:
            out.append(Row(0, path, fmt(path.rsplit(".", 1)[-1], value), path))
    return out


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

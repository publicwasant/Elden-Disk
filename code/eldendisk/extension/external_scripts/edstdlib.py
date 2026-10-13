"""edstdlib: the Elden-Disk standard library for external scripts (1.7.2). Two things: `Interface` and `tools`.

    from edstdlib import *

    class BlueEyes(Interface):
        every = 0.5                                       # seconds between two calls of loop()

        def loop(self):
            x = tools.read()                              # the game now, as one object
            rct = x.extension.innovate_items.spells[2230000]
            if x.character.vitals.hit_point.current < 500:
                rct.customs.advanced.colors["SpEffect.1642100"] = "#FF909E"
                tools.write(x)                            # only what changed is written

`Interface` is the base of a script: `setup()` once, `loop()` again and again (every `every` seconds), `teardown()` once at the end,
each script in a thread of its own. `tools` is the tool itself:

  tools.read()        the document `read --export` writes (`systems`, `character`, `params`) and the `extension` block (the spells of the
                      last build with what the game holds now), as an object: `x.character.attributes.vigor`; a key that is not a name
                      is read with [ ]: `spells[2230000]`, `colors["SpEffect.1642100"]`, `basic["SpEffect.1642100.effectEndurance"]`;
                      a spell also by its label: `spells.reverse_cursed_technique`.
  tools.write(obj)    write what was changed in a snapshot of tools.read() (assign a value: `x.character.attributes.vigor = 60`);
                      `obj` is the snapshot or any part of it (then only what changed under it). True when every change was written;
                      what was refused is in the log. Everything `read` shows can be written except `systems` (and what is computed:
                      maxima, buffs, animations, the ids a build made).
  tools.dead()        end this script now (its status: stopped).
  tools.log(text)     a line in the log and on the `run` console; tools.log(text, "warn") / "error" / "ok" / "debug".

When no character is in the world, `x.character` is None and reading in it skips that call of loop() (the script waits)."""
from __future__ import annotations

import threading

__version__ = "0.2.0"
__all__ = ["Interface", "Tools", "tools"]

_backend = None                       # what reads and writes the game: backend.LiveBackend (or a test's fake)
_local = threading.local()            # the script that runs in this thread (the framework sets it)


class _NotInWorld(Exception):
    """No character in the world (title screen, loading): the framework skips that call of loop()."""


class _Dead(BaseException):
    """tools.dead(): ends the script that called it (BaseException, so `except Exception` in a script does not catch it)."""


def _use(backend):
    """Make `backend` the one tools talks to; -> the one before (for the framework and tests only)."""
    global _backend
    old, _backend = _backend, backend
    return old


def _b():
    if _backend is None:
        raise RuntimeError("edstdlib is not connected to a game: scripts are run by `eldendisk run` (or "
                           "`eldendisk extension external-scripts --run`)")
    return _backend


def current():
    return getattr(_local, "script", None)


def _set_current(script) -> None:
    _local.script = script


# ---------------------------------------------------------------------------------------------------------------------------- Interface
class Interface:
    """The base of every script: override `loop()`, and `setup()` / `teardown()` when needed. `every`: seconds between the start of two
    calls of loop() (at least 0.05). `name`: in the log and the status (default: the class name). `enabled = False`: not run."""
    name: str | None = None
    every: float = 1.0
    enabled: bool = True

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        if not cls.__dict__.get("name"):
            cls.name = cls.__name__

    def setup(self) -> None:
        """Once, in the script's thread, before the first loop()."""

    def loop(self) -> None:
        """Every `every` seconds until the script ends."""
        raise NotImplementedError(f"{type(self).__name__} has no loop()")

    def teardown(self) -> None:
        """Once at the end, whatever happened (the game closing, an error, tools.dead())."""

    # the framework's
    @property
    def _stop(self) -> threading.Event:
        ev = self.__dict__.get("_ed_stop")
        if ev is None:
            ev = self.__dict__.setdefault("_ed_stop", threading.Event())
        return ev

    def stop(self) -> None:
        self._stop.set()

    def wait(self, seconds: float) -> bool:
        return not self._stop.wait(max(0.0, seconds))

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()


# ---------------------------------------------------------------------------------------------------------------------------- the snapshot
class Node:
    """A part of a snapshot of tools.read(). Attributes and [ ] read; assignment changes the snapshot and marks the value for tools.write.
    A key with dots ("SpEffect.1642100") is one key: `colors["SpEffect.1642100"]`, or `colors.SpEffect[1642100]`."""
    __slots__ = ("_root", "_path", "_data")

    def __init__(self, root: "Snapshot", path: tuple, data):
        object.__setattr__(self, "_root", root)
        object.__setattr__(self, "_path", path)
        object.__setattr__(self, "_data", data)

    def _key(self, key):
        data = self._data
        if not isinstance(data, dict):
            if data is None and self._path[:1] == ("character",):
                raise _NotInWorld("no character in the world")
            raise KeyError(f"{'.'.join(map(str, self._path))} is not an object")
        k = str(key)
        if k in data:
            return k
        low = {str(x).lower(): x for x in data}
        if k.lower() in low:
            return low[k.lower()]
        for name, v in data.items():                       # a spell by its label
            if isinstance(v, dict) and v.get("id") == k:
                return name
        if any(str(x).startswith(k + ".") for x in data):  # the first part of a dotted key: colors.SpEffect -> [1642100]
            return _Prefix(self, k)
        raise KeyError(f"{'.'.join(map(str, self._path + (k,)))}: no such value (there are: {', '.join(map(str, data)) or 'none'})")

    def _child(self, key):
        k = self._key(key)
        if isinstance(k, _Prefix):
            return k
        v = self._data[k]
        if isinstance(v, (dict, list)) or v is None:
            if isinstance(v, list):
                return list(v)
            if v is None and self._path + (k,) == ("character",):
                return Node(self._root, ("character",), None)
            return Node(self._root, self._path + (k,), v) if v is not None else None
        return v

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._child(name)
        except KeyError as exc:
            raise AttributeError(str(exc)) from None

    def __getitem__(self, key):
        return self._child(key)

    def __setattr__(self, name, value):
        self[name] = value

    def __setitem__(self, key, value):
        k = self._key(key)
        if isinstance(k, _Prefix):
            raise KeyError(f"{'.'.join(map(str, self._path + (key,)))}: give the whole key")
        self._data[k] = value
        self._root._changed[self._path + (k,)] = value

    def __contains__(self, key) -> bool:
        try:
            self._key(key)
            return True
        except (KeyError, _NotInWorld):
            return False

    def __iter__(self):
        return iter(self._data) if isinstance(self._data, dict) else iter(())

    def __len__(self) -> int:
        return len(self._data) if isinstance(self._data, dict) else 0

    def keys(self):
        return list(self._data) if isinstance(self._data, dict) else []

    def items(self):
        return [(k, self._child(k)) for k in self.keys()]

    def get(self, key, default=None):
        try:
            return self._child(key)
        except (KeyError, _NotInWorld):
            return default

    def to_dict(self):
        """A plain copy (dicts and lists)."""
        import copy
        return copy.deepcopy(self._data)

    def __repr__(self) -> str:
        return f"<{'.'.join(map(str, self._path)) or 'snapshot'}: {self._data!r:.200}>"

    def _not_a_number(self, *_a):
        """A group used as a number (`x.character.runes += 50`): say which values it has, not "unsupported operand type"."""
        where = ".".join(map(str, self._path)) or "the snapshot"
        keys = self.keys()
        hint = f": use one of its values, e.g. {where}.{keys[0]}" if keys else ""
        raise TypeError(f"{where} is a group ({', '.join(map(str, keys)) or 'empty'}), not a number{hint}")

    __add__ = __radd__ = __iadd__ = __sub__ = __rsub__ = __isub__ = __mul__ = __rmul__ = __imul__ = _not_a_number
    __truediv__ = __rtruediv__ = __floordiv__ = __mod__ = __neg__ = __int__ = __float__ = _not_a_number
    __lt__ = __le__ = __gt__ = __ge__ = _not_a_number


class _Prefix:
    """`colors.SpEffect` before `[1642100]`: the first part of a dotted key."""

    def __init__(self, node: Node, prefix: str):
        self.node, self.prefix = node, prefix

    def __getitem__(self, rest):
        return self.node[f"{self.prefix}.{rest}"]

    def __setitem__(self, rest, value):
        self.node[f"{self.prefix}.{rest}"] = value

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]


class Snapshot(Node):
    """What tools.read() returns: the whole document, and what was changed in it since (for tools.write)."""
    __slots__ = ("_changed",)

    def __init__(self, doc: dict):
        object.__setattr__(self, "_changed", {})
        super().__init__(self, (), doc)


# ---------------------------------------------------------------------------------------------------------------------------- tools
class Tools:
    """The tool for a script (one object, `tools`). See the module text."""

    @staticmethod
    def read() -> Snapshot:
        import copy
        return Snapshot(copy.deepcopy(_b().document()))

    @staticmethod
    def write(obj) -> bool:
        if not isinstance(obj, Node):
            raise TypeError("tools.write takes a snapshot of tools.read() (or a part of it) after a value in it was changed, "
                            "for example: x = tools.read(); x.character.attributes.vigor = 60; tools.write(x)")
        root, under = obj._root, obj._path
        mine = {p: v for p, v in root._changed.items() if p[:len(under)] == under}
        if not mine:
            return True
        done, problems = _b().write(mine)
        for p in mine:
            root._changed.pop(p, None)
        for why in problems:
            Tools.log(f"not written: {why}", "warn")
        return not problems

    @staticmethod
    def dead() -> None:
        raise _Dead()

    @staticmethod
    def log(text, level: str = "info") -> None:
        s = current()
        lv = {"info": "I", "ok": "OK", "warn": "W", "warning": "W", "error": "E", "debug": "D"}.get(str(level).lower(), "I")
        _b().log(lv, f"{s.name if s is not None else 'script'}: {text}")


tools = Tools()

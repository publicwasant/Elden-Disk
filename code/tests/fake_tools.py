"""A backend for edstdlib without the game (tests only): a document, the writes applied to it, the log lines kept."""
import copy

from eldendisk.creative.scripts import edstdlib as ed

DOC = {
    "systems": {"status": {"pid": 1, "tool_state": "CONNECTED"}},
    "character": {
        "level": 150,
        "vitals": {"hit_point": {"current": 1000, "maximum": 2000, "base": 2000},
                   "focus_point": {"current": 50, "maximum": 300, "base": 300},
                   "stamina": {"current": 150, "maximum": 150, "base": 150}},
        "runes": {"total": 1234, "baseline": 1234, "delta": 0},
        "attributes": {"vigor": 60, "mind": 20, "endurance": 20, "strength": 20, "dexterity": 20, "intelligence": 10, "faith": 60,
                       "arcane": 10},
        "buffs": {"21951000": {"name": "reverse_cursed_technique", "categories": "CREATIVE"}},
        "animations": {},
        "equipment": {"magic": {"selected": {"slot": 1, "id": 2230000}, "slots": {"1": 2230000, "2": 6420}}},
    },
    "params": {"effects": {"1621000": {"name": "Black Flame", "effectEndurance": 2.0}}},
    "creative": {"innovate_spells": {"2230000": {
        "id": "reverse_cursed_technique", "slot": 1,
        "rows": {"goods": 2230000, "magic": 2230000, "sp_effect": [21951000], "bullet": [], "atk": [], "shop": 100508},
        "design": {
            "kind": "projectile", "from": 6421,
            "requires": {"status": {"faith": 60}, "cost": {"focus_point": 120}},
            "customs": {"basic": {"SpEffect.1642100.effectEndurance": 20.0},
                        "advanced": {"texts": {"goods_name": "Reverse Cursed Technique"},
                                     "colors": {"Magic.6421.castSfxId": {"0x4290": [0.5647, 0.8353, 1.0, 0.075],
                                                                         "0x4334": "#90D5FF"},
                                                "SpEffectVfx.20090050.midstSfxId": {"0x2a0": [0.5647, 0.8353, 1.0, 1.0]}}}},
        },
    }}},
}


class FakeBackend:
    def __init__(self, doc=None, *, refuse=(), alive=True):
        self.doc = copy.deepcopy(DOC if doc is None else doc)
        self.refuse, self.is_alive = set(refuse), alive
        self.writes, self.lines, self.reads = [], [], 0
        self._old = None

    def __enter__(self):
        self._old = ed._use(self)
        return self

    def __exit__(self, *exc):
        ed._use(self._old)

    def alive(self):
        return self.is_alive

    def log(self, level, msg):
        self.lines.append((level, msg))

    def document(self):
        self.reads += 1
        return self.doc

    def write(self, changes):
        done, problems = {}, []
        for path, value in changes.items():
            name = ".".join(map(str, path))
            if path[0] == "systems" or name in self.refuse:
                problems.append(f"{name}: refused")
                continue
            cur = self.doc
            for k in path[:-1]:
                cur = cur[k]
            cur[path[-1]] = value
            done[name] = value
            self.writes.append((name, value))
        return done, problems

    def run(self, script, loops=1):
        """setup(), `loops` calls of loop(), teardown(), in this thread (what the host does, without its threads)."""
        ed._set_current(script)
        try:
            script.setup()
            for _ in range(loops):
                try:
                    script.loop()
                except ed._NotInWorld:
                    pass
        finally:
            script.teardown()
            ed._set_current(None)
        return script

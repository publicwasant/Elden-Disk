"""The colours of Reverse Cursed Technique only while it is the spell in use: the fire, the ring and the sparks take the design's colours
when the spell is selected in the magic slots (before the cast, so the cast shows them) and go back to the game's own when another spell
is selected (Flame, Grant Me Strength looks as the game made it again, the game's own sparks are ice again). The effect files are
shared, so the colours can only follow the spell in time. 1.8.3 part 2: every key of `colors` (but the eyes) with all its places."""
from edstdlib import *


class RctColoursFollowTheSpell(Interface):
    every = 0.2
    spell = "reverse_cursed_technique"

    def setup(self):
        rct = tools.read().creative.innovate_spells[self.spell]
        self.magic = rct.rows.magic                               # the spell's id in the magic slots
        colors = rct.design.customs.advanced.colors
        self.saved = {k: dict(colors[k].items())                 # every place of every key, as `run` painted them
                      for k in colors if not k.startswith("SpEffectVfx.")}   # (the eyes glow only while the buff lasts)
        self.on = True                                            # `run` painted them: they are on now

    def put(self, x, on):
        colors = x.creative.innovate_spells[self.spell].design.customs.advanced.colors
        for k, places in self.saved.items():
            colors[k] = places if on else None                    # None: the game's own colours

    def loop(self):
        x = tools.read()
        chosen = x.character.equipment.magic.selected.id == self.magic
        if chosen == self.on:
            return
        self.put(x, chosen)
        if tools.write(x):                                        # the log says it: `reverse_cursed_technique colours: ...`
            self.on = chosen

    def teardown(self):
        if not self.on:                                           # leave the design's colours as `run` left them
            x = tools.read()
            self.put(x, True)
            tools.write(x)

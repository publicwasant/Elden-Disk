"""The colours of Reverse Cursed Technique only while it is the spell in use: the fire and the ring take the design's colours when the
spell is selected in the magic slots (before the cast, so the cast shows them) and go back to the game's own when another spell is selected
(Flame, Grant Me Strength looks as the game made it again). The effect files are shared, so the colours can only follow the spell in time."""
from edstdlib import *


class RctColoursFollowTheSpell(Interface):
    every = 0.2
    spell = "reverse_cursed_technique"

    def setup(self):
        rct = tools.read().creative.innovate_spells[self.spell]
        self.magic = rct.rows.magic                               # the spell's id in the magic slots
        self.key = f"Magic.{rct.design['from']}.castSfxId"         # `from` is a word of Python: read with [ ]
        fire = rct.design.customs.advanced.colors[self.key]
        self.main, self.accent = fire.main, fire.accent           # the design's colours, as `run` painted them
        self.on = True                                            # `run` painted them: they are on now

    def loop(self):
        x = tools.read()
        chosen = x.character.equipment.magic.selected.id == self.magic
        if chosen == self.on:
            return
        fire = x.creative.innovate_spells[self.spell].design.customs.advanced.colors[self.key]
        fire.main = self.main if chosen else None                 # None: the game's own colours
        fire.accent = self.accent if chosen else None
        if tools.write(x):                                        # the log says it: `reverse_cursed_technique colours: ...`
            self.on = chosen

    def teardown(self):
        if not self.on:                                           # leave the design's colours as `run` left them
            x = tools.read()
            fire = x.creative.innovate_spells[self.spell].design.customs.advanced.colors[self.key]
            fire.main, fire.accent = self.main, self.accent
            tools.write(x)

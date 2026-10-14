"""The colours of Reverse Cursed Technique only while it is the spell in use: the fire and the ring take the design's colours when the
spell is selected in the magic slots (before the cast, so the cast shows them) and go back to the game's own when another spell is selected
(Flame, Grant Me Strength looks as the game made it again). The effect files are shared, so the colours can only follow the spell in time."""

from eldendisk.creative.scripts.edstdlib import tools, Interface

class RctColoursFollowTheSpell(Interface):
    every = 0.2
    spell = "reverse_cursed_technique"

    def __init__(self):
        self.on = None
        self.accent = None
        self.main = None
        self.key = None
        self.magic = None

    def setup(self):
        rct = tools.read().creative.innovate_spells[self.spell]

        # the spell's id in the magic slots
        self.magic = rct.rows.magic

        # `from` is a word of Python: read with [ ]
        self.key = f"Magic.{rct.design['from']}.castSfxId"

        fire = rct.design.customs.advanced.colors[self.key]

        # the design's colours, as `run` painted them
        self.main, self.accent = fire.main, fire.accent

        # `run` painted them: they are on now
        self.on = True

    def loop(self):
        disk = tools.read()
        chosen = disk.character.equipment.magic.selected.id == self.magic
        if chosen == self.on:
            return
        fire = disk.creative.innovate_spells[self.spell].design.customs.advanced.colors[self.key]
        # None: the game's own colors
        fire.main = self.main if chosen else None
        fire.accent = self.accent if chosen else None

        # the log says it: `reverse_cursed_technique colors: ...`
        if tools.write(disk):
            self.on = chosen

    def teardown(self):
        # leave the design's colors as `run` left them
        if not self.on:
            disk = tools.read()
            fire = disk.creative.innovate_spells[self.spell].design.customs.advanced.colors[self.key]
            fire.main, fire.accent = self.main, self.accent
            tools.write(disk)

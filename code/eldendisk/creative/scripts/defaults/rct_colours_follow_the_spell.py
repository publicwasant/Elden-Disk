"""The colours of Reverse Cursed Technique only while it is the spell in use: the fire, the ring and the sparks take the design's colours
when the spell is selected in the magic slots (before the cast, so the cast shows them) and go back to the game's own when another spell
is selected (Flame, Grant Me Strength looks as the game made it again, the game's own sparks are ice again). The effect files are
shared, so the colours can only follow the spell in time. 1.8.3 part 2: every key of `colors` (but the eyes) with all its places."""

from eldendisk.creative.scripts.edstdlib import tools, Interface

class RctColoursFollowTheSpell(Interface):
    every = 0.2
    spell = "reverse_cursed_technique"

    def __init__(self):
        self.on = None
        self.saved = None
        self.magic = None

    def setup(self):
        spells = tools.read().creative.get("innovate_spells") or {}     # none without a build of this session (`run --regulation FILE`)
        if self.spell not in spells:
            tools.log(f"{self.spell} is not in the last build (or this session has no build of its own): no colours to follow", "warn")
            tools.dead()
        rct = spells[self.spell]

        # the spell's id in the magic slots
        self.magic = rct.rows.magic

        colors = rct.design.customs.advanced.colors

        # every place of every key, as `run` painted them (the eyes keep theirs: they glow only while the buff lasts)
        self.saved = {k: dict(colors[k].items()) for k in colors if not k.startswith("SpEffectVfx.")}

        # `run` painted them: they are on now
        self.on = True

    def put(self, disk, on):
        colors = disk.creative.innovate_spells[self.spell].design.customs.advanced.colors
        for k, places in self.saved.items():
            # None: the game's own colors
            colors[k] = places if on else None

    def loop(self):
        disk = tools.read()
        if "equipment" not in disk.character:      # the magic slots cannot be read now: wait, change nothing
            return
        chosen = disk.character.equipment.magic.selected.id == self.magic
        if chosen == self.on:
            return
        self.put(disk, chosen)

        # the log says it: `reverse_cursed_technique colors: ...`
        if tools.write(disk):
            self.on = chosen

    def teardown(self):
        # leave the design's colors as `run` left them
        if self.on is False:            # None: setup() ended before anything was painted
            disk = tools.read()
            if "level" not in disk.character:      # the game closed (or no character): its memory is gone, nothing to put back
                return
            self.put(disk, True)
            tools.write(disk)

"""The colours of Dismantle only while it is the spell in use (1.8.4 part 6): the claw marks on the ones it hits (Sfx.530172, Beast Claw's
hit) take the design's colours, the white cut, when Dismantle is selected in the magic slots (before the cast, so the cuts show them),
and go back to the game's own when another spell is selected (Beast Claw's own hit is the game's again). The effect file is shared,
so the colours can only follow the spell in time, as those of Reverse Cursed Technique do: every key of `colors` with all its places."""

from eldendisk.creative.scripts.edstdlib import tools, Interface

class DismantleColoursFollowTheSpell(Interface):
    every = 0.2
    spell = "dismantle"

    def __init__(self):
        self.on = None
        self.saved = None
        self.magic = None

    def setup(self):
        spells = tools.read().creative.get("innovate_spells") or {}     # none without a build of this session (`run --regulation FILE`)
        if self.spell not in spells:
            tools.log(f"{self.spell} is not in the last build (or this session has no build of its own): no colours to follow", "warn")
            tools.dead()
        rec = spells[self.spell]

        # the spell's id in the magic slots
        self.magic = rec.rows.magic

        colors = rec.design.customs.get("advanced", {}).get("colors", {})

        # every place of every key, as `run` painted them
        self.saved = {k: dict(colors[k].items()) for k in colors if not k.startswith("SpEffectVfx.")}
        if not self.saved:
            tools.log(f"{self.spell} has no colours in its design: nothing to follow", "warn")
            tools.dead()

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

        # the log says it: `dismantle colors: ...`
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

"""Experiment 5: a value of a spell's design. The Positive Curse Energy Eyes of Reverse Cursed Technique turn red-pink while HP is below 30 %
and back to blue above (no rebuild, no look through the memory: the copies `run` painted are painted again). 1.8.3 part 2: every colour
place of the eyes' effect gets the colour (a hex colour keeps each place's own brightness)."""
from edstdlib import *

BLUE, PINK = "#90D5FF", "#FF909E"
EYES = "SpEffectVfx.20090050.midstSfxId"


class EyesFollowHp(Interface):
    def setup(self):
        self.every = 0.5
        self.shown = None

    def loop(self):
        x = tools.read()
        hp = x.character.vitals.hit_point
        want = PINK if hp.current < 0.3 * hp.maximum else BLUE
        if want != self.shown:
            colors = x.creative.innovate_spells.reverse_cursed_technique.design.customs.advanced.colors
            colors[EYES] = {place: want for place in colors[EYES].keys()}
            if tools.write(x):
                self.shown = want
                tools.log(f"eyes {want}", "ok")

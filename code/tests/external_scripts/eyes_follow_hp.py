"""Experiment 5: a value of a spell's design. The Positive Curse Energy Eyes of Reverse Cursed Technique turn red-pink while HP is below 30 %
and back to blue above (no rebuild, no look through the memory: the copies `run` painted are painted again)."""
from edstdlib import *

BLUE, PINK = "#90D5FF", "#FF909E"


class EyesFollowHp(Interface):
    def setup(self):
        self.every = 0.5
        self.shown = None

    def loop(self):
        x = tools.read()
        hp = x.character.vitals.hit_point
        want = PINK if hp.current < 0.3 * hp.maximum else BLUE
        if want != self.shown:
            rct = x.creative.innovate_spells.reverse_cursed_technique
            rct.design.customs.advanced.colors["SpEffect.1642100"] = want
            if tools.write(x):
                self.shown = want
                tools.log(f"eyes {want}", "ok")

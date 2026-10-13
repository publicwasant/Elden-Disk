"""Experiment 2: read only. A warning when HP drops below 30 %, once until it is above again."""
from edstdlib import *


class LowHp(Interface):
    every = 0.2

    def setup(self):
        self.warned = False

    def loop(self):
        hp = tools.read().character.vitals.hit_point
        low = hp.current < 0.3 * hp.maximum
        if low and not self.warned:
            tools.log(f"HP {hp.current}/{hp.maximum}", "warn")
        elif not low and self.warned:
            tools.log(f"HP back to {hp.current}/{hp.maximum}")
        self.warned = low

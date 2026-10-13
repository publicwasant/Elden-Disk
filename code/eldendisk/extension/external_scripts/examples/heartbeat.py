"""Experiment 1: the life of a script. A line every 5 seconds while the game runs."""
from edstdlib import *


class Heartbeat(Interface):
    every = 5.0

    def setup(self):
        self.beats = 0
        x = tools.read()
        tools.log(f"hello: level {x.character.level}, {x.character.runes.total} runes")

    def loop(self):
        self.beats += 1
        x = tools.read()
        tools.log(f"beat {self.beats}: HP {x.character.vitals.hit_point.current}")

    def teardown(self):
        tools.log(f"goodbye after {self.beats} beats")

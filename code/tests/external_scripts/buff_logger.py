"""Experiment 3: read only. A line when a buff comes on the character and when it goes (the buff of a spell of the design is
named by the spell's label)."""
from edstdlib import *


class BuffLogger(Interface):
    every = 0.25

    def setup(self):
        self.before = set(tools.read().character.buffs.keys())

    def loop(self):
        buffs = tools.read().character.buffs
        now = set(buffs.keys())
        for i in sorted(now - self.before):
            tools.log(f"+ {i} {buffs[i].name}")
        for i in sorted(self.before - now):
            tools.log(f"- {i}")
        self.before = now

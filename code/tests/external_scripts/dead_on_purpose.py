"""Experiment 6: a script that ends itself after 3 loops (tools.dead(): stopped), and one that fails (an error: dead). The others go on."""
from edstdlib import *


class EndsItself(Interface):
    every = 1.0

    def setup(self):
        self.n = 0

    def loop(self):
        self.n += 1
        tools.log(f"loop {self.n}")
        if self.n == 3:
            tools.dead()


class Fails(Interface):
    every = 1.0

    def loop(self):
        raise RuntimeError("on purpose")

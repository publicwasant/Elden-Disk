"""Experiment 7: a script that never returns from loop(). After 10 s it is reported as stuck; the others go on, and the game closes
as always (the host ends anyway)."""
import time

from edstdlib import *


class HangOnPurpose(Interface):
    every = 1.0

    def loop(self):
        tools.log("going to sleep for good")
        while True:
            time.sleep(1)

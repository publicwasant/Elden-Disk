"""Experiment 4: read and write. FP back to full when it drops below 20 %."""
from edstdlib import *


class KeepFp(Interface):
    every = 0.5

    def loop(self):
        x = tools.read()
        fp = x.character.vitals.focus_point
        if fp.current < 0.2 * fp.maximum:
            fp.current = fp.maximum
            if tools.write(x):
                tools.log("FP refilled", "ok")

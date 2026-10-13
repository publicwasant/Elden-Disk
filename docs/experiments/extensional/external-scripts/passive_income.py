from edstdlib import *

class PassiveIncome(Interface):
    every = 5.0

    def setup(self):
        self.runes_per_five_seconds = 15000

    def loop(self):
        owned = tools.read()
        if owned.systems.status.tool_state == "CONNECTED":
            owned.character.runes.total += self.runes_per_five_seconds
            if tools.write(owned):
                tools.log(f"+{self.runes_per_five_seconds} runes in your pocket!")

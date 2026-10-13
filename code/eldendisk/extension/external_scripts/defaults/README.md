# External scripts

Every `*.py` file in this folder is a script that `eldendisk run` starts next to the game (vault ON), once a character is in the world.
A file whose name starts with `_` is a helper, not a script. Copy one from `code/tests/external_scripts/` (the example scripts the tests run) to begin. The build embeds these scripts in
the exe (they are its default scripts); `--scripts-dir PATH` (a folder or a `.py` file, anywhere) adds more after the exe is built.

```python
from edstdlib import *

class Hello(Interface):
    every = 5.0                     # seconds between two calls of loop()

    def loop(self):
        x = tools.read()
        tools.log(f"HP {x.character.vitals.hit_point.current}")
```

`eldendisk extension external-scripts --list` shows the scripts and how the last run ended for each.

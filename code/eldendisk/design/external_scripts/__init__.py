"""External scripts (1.7.2): small Python programs of the tool's users (and its developers) that run next to the game while `run`
holds the session, each in a thread of its own, with the game given to them by `edstdlib` (edstdlib.py).

  edstdlib.py   the interface: the library the scripts import (`from edstdlib import *`: Interface, tools)
  host.py       finds the scripts, runs them, keeps their pace, watches them, ends them
  backend.py    what edstdlib reads and writes the running game with (the reader and the writer of `read` and `write`); the ONE
                file of the design package that touches the game (tests/test_architecture.py: EXCEPTIONS)
  defaults/     the default scripts: the build embeds them in the exe (`--scripts-dir PATH` adds more afterwards)
  (example scripts, which the tests also run: code/tests/external_scripts/)
"""
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
DEFAULTS_DIR = PKG_DIR / "defaults"
FOLDER_NAME = "external-scripts"           # the folder of scripts next to the exe (and inside it when embedded)

import sys as _sys

from . import edstdlib as _edstdlib

# `from edstdlib import *` works once this package is imported (the source tree and the exe alike; the scripts are files outside it)
_sys.modules.setdefault("edstdlib", _edstdlib)

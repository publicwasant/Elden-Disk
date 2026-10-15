"""The look through the game's memory: game/scan.py (moved there in 1.8.1, the reader finds the item names with it). This module IS
that module (the same object), so `from . import scan` here and a test that changes `scan.CHUNK` change the one the walk uses."""
import sys

from ..game import scan as _scan

sys.modules[__name__] = _scan

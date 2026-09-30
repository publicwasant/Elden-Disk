"""Lab 4: classify SpEffect entries by hand, then check with the project's own code.

Run from the folder that contains elden_telemetry/:  python labs/lab4_classify.py
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # project root

from elden_telemetry.profile_loader import ActiveEffect, EntryLayout, Effects, PassiveEffect, Profile, SpEffectLayout
from elden_telemetry.telemetry import Sampler

ENTRIES = [  # (id, duration, timer)
    (311100, -1.0, -1.0),
    (1660000, 80.0, 76.04),
    (1605000, 30.0, 0.0),
    (4600, 30.0, 30.0),
    (45, 0.1, 0.02),
    (3971, 180.0, 179.6),
]
EFFECTS = Effects(
    active={1660000: ActiveEffect("Golden Vow"), 1605000: ActiveEffect("Flame! Grant Me Strength"),
            3971: ActiveEffect("Gold-Pickled Fowl Foot")},
    passive={311100: PassiveEffect("Gold Scarab", "TALISMAN", "Gold Scarab")},
)
NOW = datetime(2026, 9, 30, 3, 27, 23, tzinfo=timezone.utc)


def run(mode):
    lay = SpEffectLayout(0x178, 0x8, EntryLayout(0x8, 0x30, 0x48, 0x40, mode))
    prof = Profile("00" * 32, "lab", 0, 0, 0x580, 0x68, 0x6C, 0x3C, lay)
    active, passive, ignored = Sampler(None, prof, EFFECTS, 0)._classify(ENTRIES, NOW)
    print(f"--- timer_mode = {mode!r}")
    print("passive:", [p["id"] for p in passive])
    print("active :", [(a["id"], a["remaining_seconds"]) for a in active])
    print("ignored:", ignored)


run("remaining")
run("elapsed")

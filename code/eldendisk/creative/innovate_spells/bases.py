"""The regulation.bin versions this design knows. A recipe is written against exact rows of one version, so an
unknown file is refused instead of guessed at."""
from __future__ import annotations

RECIPE_VERSION = 2          # raise it whenever the same design gives other rows: a build or a secured file of an older version is built again
                            # (2: positive_curse_energy_eyes moved from the Fowl Foot's SpEffectVfx 5364, on the chest, to 20090050/20090051 on the eyes)

# base version -> sha256 of the game's original (untouched) regulation.bin file
BASES = {
    "1.17.1": "766521f9508de3a3532df61c45a1c2d93340f1ff7ed8306ab20df761712ca2ab",
}
CURRENT_BASE = "1.17.1"


def version_of(sha256_hex: str) -> str | None:
    for ver, h in BASES.items():
        if h == sha256_hex:
            return ver
    return None

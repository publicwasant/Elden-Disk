"""The names of the game's param tables (1.8.0 part 4): every table of its regulation.bin, by the name the file gives it
(`EquipParamGoods`, `Magic`, `SpEffectParam`, `NpcParam` ...), in any letter case. The short names of the workbench before 1.8.0
(`Goods`, `SpEffect`, `ShopLineup`) and Paramdex's (`MagicParam`, `BulletParam`, `AtkParam`) still name the same tables. Pure."""
from __future__ import annotations

from .paramlayouts import LAYOUTS

ALIASES = {"goods": "EquipParamGoods", "speffect": "SpEffectParam", "shoplineup": "ShopLineupParam", "magicparam": "Magic",
           "bulletparam": "Bullet", "atkparam": "AtkParam_Pc", "atkpc": "AtkParam_Pc", "atknpc": "AtkParam_Npc"}
TABLES = {**ALIASES, **{name.lower(): name for name in LAYOUTS}}
WORKBENCH = ("EquipParamGoods", "Magic", "SpEffectParam", "Bullet", "AtkParam_Pc", "ShopLineupParam")   # the six of 1.6.3 / 1.7.0


def canonical(text: str) -> str | None:
    """The game's name of the table `text` names, or None when it names none."""
    return TABLES.get(str(text).strip().lower())


def has_fields(table: str) -> bool:
    """Does the layout of `table` know its fields? (Not for the few whose rows the game made longer than Paramdex knows.)"""
    return LAYOUTS[table]["fields"] is not None

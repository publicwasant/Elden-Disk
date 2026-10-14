"""The Z4 spell exactly as it was tested in the game (handbook Part VI). A FIXED copy: the tests must not depend
creative.json, which is the user's file to edit (price, visual, ...). The golden hash belongs to this spec."""
import json

ID = "reverse_curse_technique"
SPELL = {
    "type": "incantation",
    "text": {"goods_name": "Reverse Curse Technique",
             "goods_info": "Heals over time while you cast",
             "goods_captions": "Heals over time while you cast; you can be hit but the cast is not interrupted."},
    "requires": {"intelligence": 45, "faith": 15, "arcane": 10},
    "fp_cost": 80,
    "cast_motion": "black-flame-blade",
    "effect": {"heal_hp_per_tick": 60, "restore_fp_per_tick": 4, "stamina_regen_speed": 100, "tick_seconds": 0.5,
               "duration_seconds": 15, "visual": "flame"},
    "poise_while_casting_seconds": 2.0,
    "shop": {"price": 34590, "stock": 1},
}


def file_of(slots: dict, maximum: int = 64) -> dict:
    """creative.json with these filled slots (in this order, from slot 1) and empty ones up to `maximum`."""
    slots = dict(slots)
    n = len(slots)
    while len(slots) < maximum:
        n += 1
        slots["<id-%d>" % n] = None
    return {"innovate_spells": {"maximum": maximum, "slots": slots}}


def spell_of(d: dict, which: str = ID) -> dict:
    return d["innovate_spells"]["slots"][which]


Z4 = file_of({ID: SPELL})
Z4_TEXT = json.dumps(Z4, indent=2) + "\n"

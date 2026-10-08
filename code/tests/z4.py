"""The Z4 item exactly as it was tested in the game (handbook Part VI). A FIXED copy: the tests must not depend on
items.draft.json, which is the user's file to edit (price, visual, ...). The golden hash belongs to this spec."""
import json

Z4 = {
    "format": 1,
    "items": [{
        "id": "reverse-curse-technique",
        "type": "incantation",
        "name": "Reverse Curse Technique",
        "description": "Heals over time while you cast; you can be hit but the cast is not interrupted.",
        "requires": {"intelligence": 45, "faith": 15, "arcane": 10},
        "fp_cost": 80,
        "cast_motion": "black-flame-blade",
        "effect": {"heal_hp_per_tick": 60, "restore_fp_per_tick": 4, "stamina_regen_speed": 100, "tick_seconds": 0.5,
                   "duration_seconds": 15, "visual": "flame"},
        "poise_while_casting_seconds": 2.0,
        "shop": {"price": 34590, "stock": 1},
    }],
}
Z4_TEXT = json.dumps(Z4, indent=2) + "\n"

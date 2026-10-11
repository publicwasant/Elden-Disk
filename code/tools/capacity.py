"""Developer tool (not shipped): how many slots of which kinds fit under the gate's envelope. Offline; the game is not needed.

    python tools/capacity.py --source <game>/regulation.bin --mix projectile=4,attack=4,buff=12 [--mix ...] [--each 1,8,16,32,64] [--write-design FILE]

`--mix` builds a design with that many slots of each kind, in that order (clone, enchant, projectile and attack copy a fixed game
spell: Black Flame 6210, Black Flame Blade 6250, sorcery 4440; buff is the heal-over-time spell without `from`), the first 7 slots with a
shop line (price 1000 + the slot number). `--each` measures every kind alone for those slot counts. Every slot gets numbers of its own (a real design is not 20 identical slots, which would compress better). For each design it prints what the gate sees: re-encoded blocks, how
much the body and the compressed frame grew, and the limits (preflight.MAX_*) it breaks. The verdict is the gate's, not the game's:
the numbers go up only after a bigger file passed in the game (envelope_test.py builds that file). The frame growth is not smooth
(it depends on how well the new rows compress), so a neighbouring count can pass where this one fails."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eldendisk.extension.innovate_items import bases, preflight                      # noqa: E402
from eldendisk.extension.innovate_items.spells import build, gate, recipes, spec     # noqa: E402

KINDS = ("buff", "clone", "enchant", "projectile", "attack")
FROM = {"clone": 6210, "enchant": 6250, "projectile": 6210, "attack": 4440}
BUFF = {
    "type": "incantation", "text": {"goods_name": "Capacity buff", "goods_captions": "Heals over time."},
    "requires": {"intelligence": 45, "faith": 15, "arcane": 10}, "fp_cost": 80, "cast_motion": "black-flame-blade",
    "effect": {"heal_hp_per_tick": 60, "restore_fp_per_tick": 4, "stamina_regen_speed": 100, "tick_seconds": 0.5,
               "duration_seconds": 15, "visual": "flame"},
    "poise_while_casting_seconds": 2.0,
}
MAXIMUM = 64


def parse_mix(text: str) -> list[tuple[str, int]]:
    """`projectile=4,attack=4` -> [("projectile", 4), ("attack", 4)]; a bad kind or count is a ValueError."""
    out = []
    for part in text.split(","):
        kind, _, n = part.strip().partition("=")
        if kind not in KINDS or not n.isdigit() or int(n) < 1:
            raise ValueError("bad mix %r: use kind=count with kind one of %s" % (part, ", ".join(KINDS)))
        out.append((kind, int(n)))
    if sum(n for _, n in out) > MAXIMUM:
        raise ValueError("a design has at most %d slots" % MAXIMUM)
    return out


VARY = {   # a `set` that makes every slot's copied rows differ from the other slots' (identical rows would compress better than a real design)
    "enchant": lambda i: {"SpEffect.1626000.effectEndurance": 100 + i},
    "projectile": lambda i: {"SpEffect.1621000.effectEndurance": 10 + i, "Bullet.10621000.life": 1 + i / 10},
    "attack": lambda i: {"AtkParam_Pc.44400.atkMag": 100 + i},
}


def design(mix: list[tuple[str, int]], vary: bool = True) -> dict:
    """The extension.json for this mix (slots in the order of the mix; the first 7 have a shop line, price 1000 + the slot number). `vary`: every slot gets its own
    numbers (cost, effect, `set`), as a real design has; identical slots compress better and would make the frame look smaller."""
    slots, i = {}, 0
    for kind, n in mix:
        for _ in range(n):
            i += 1
            if kind == "buff":
                s = dict(BUFF)
                s["effect"], s["requires"] = dict(BUFF["effect"]), dict(BUFF["requires"])
                if vary:
                    s["fp_cost"] = 20 + i
                    s["effect"]["heal_hp_per_tick"], s["effect"]["duration_seconds"] = 20 + i, 10 + i
            else:
                s = {"kind": kind, "from": FROM[kind], "fp_cost": 5 + (i if vary else 0)}
                if vary and kind in VARY:
                    s["set"] = VARY[kind](i)
            if i <= len(recipes.SHOP_LINES):
                s["shop"] = {"price": 1000 + i, "stock": -1}      # 1001, 1002, ...: the price in the merchant's list says which slot it is
            slots["%s_%d" % (kind, i)] = s
    for j in range(i + 1, MAXIMUM + 1):
        slots["<id-%d>" % j] = None
    return {"innovate_items": {"spells": {"maximum": MAXIMUM, "slots": slots}}}


def measure(src, mix: list[tuple[str, int]]) -> dict:
    """Build the design WITHOUT the gate raising, and report what the gate sees."""
    spells = spec.normalise(design(mix))["spells"]
    res = build.make(src, spells)
    v = gate.verify(res.data, src, spells)
    st = v.stats
    return {"slots": len(spells), "blocks": st.get("changed_blocks"), "body": st.get("body_growth"), "frame": st.get("frame_growth"),
            "problems": list(v.problems), "ok": v.ok}


def label(mix) -> str:
    return " + ".join("%d %s" % (n, k) for k, n in mix)


def limits_broken(r: dict) -> str:
    out = []
    if r["blocks"] is not None and r["blocks"] > preflight.MAX_CHANGED_BLOCKS:
        out.append("blocks")
    if r["body"] is not None and r["body"] > preflight.MAX_BODY_GROWTH:
        out.append("body")
    if r["frame"] is not None and r["frame"] > preflight.MAX_FRAME_GROWTH:
        out.append("frame")
    return ",".join(out)


def row(mix, r: dict) -> str:
    other = [p for p in r["problems"] if not p.startswith(("R2:", "R7:"))]
    verdict = "ok" if r["ok"] else "STOP: " + (limits_broken(r) or "see below") + ("; " + other[0][:80] if other else "")
    return "%-34s %5d %7s %10s %10s  %s" % (label(mix), r["slots"], r["blocks"], "{:,}".format(r["body"] or 0), "{:,}".format(r["frame"] or 0), verdict)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", required=True, help="the game's own regulation.bin (1.17.1)")
    ap.add_argument("--mix", action="append", default=[], help="kind=count,kind=count (repeatable)")
    ap.add_argument("--each", help="every kind alone for these slot counts, for example 1,8,16,32,64")
    ap.add_argument("--write-design", metavar="FILE", help="write the design of the FIRST --mix to FILE (an extension.json; for envelope_test.py --spec) and exit")
    a = ap.parse_args(argv)
    try:
        mixes = [parse_mix(m) for m in a.mix]
        if a.each:
            counts = [int(x) for x in a.each.split(",")]
            mixes += [[(k, n)] for k in KINDS for n in counts if 1 <= n <= MAXIMUM]
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    if not mixes:
        print("give --mix or --each", file=sys.stderr)
        return 2
    if a.write_design:
        Path(a.write_design).write_text(json.dumps(design(mixes[0]), indent=2) + "\n", encoding="utf-8")
        print("written %s (%s)" % (a.write_design, label(mixes[0])))
        return 0
    base = Path(a.source).read_bytes()
    if hashlib.sha256(base).hexdigest() != bases.BASES[bases.CURRENT_BASE]:
        print("the source is not the original regulation.bin of 1.17.1", file=sys.stderr)
        return 2
    src = build.prepare(base)
    print("gate: %d blocks, body +%s, frame +%s\n" % (preflight.MAX_CHANGED_BLOCKS, "{:,}".format(preflight.MAX_BODY_GROWTH),
                                                    "{:,}".format(preflight.MAX_FRAME_GROWTH)))
    print("%-34s %5s %7s %10s %10s  %s" % ("design", "slots", "blocks", "body", "frame", "gate"))
    for mix in mixes:
        print(row(mix, measure(src, mix)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

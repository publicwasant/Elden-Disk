"""Dismantle follows the lock-on (1.8.4 parts 2-4): locked on, ONE cut flies at the target, slower and turning hard, and circles it,
cutting it again every 0.05 s while it lasts (part 4), cast with the motion of O, Flame!; not locked on, the fan of part 1, cast with
Catch Flame's motion (the build's). Locked on costs 2.5 times the FP. On the ones hit, next to the blood: Beast Claw's claw marks
(530172 in both modes; their colours: the design's Sfx.530172), played by the game's unused SpEffectVfx row 999999999. The game reads these rows at
every cast, so the script writes the fields of the other mode into the running game when the lock-on changes, and nothing while it
stays. `teardown()` puts the build's values back. A cast within `every` seconds of locking on or off may still be in the mode before."""

from eldendisk.creative.scripts.edstdlib import tools, Interface

# the template's rows (Bestial Sling) and the game's row the blood is a copy of: the script finds their copies in the last build
MAGIC, FAN, BLOOD = "6800", "10680000", "474"
# the game's debug row of SpEffectVfx: no SpEffect of the game shows it and it plays nothing, so the script makes it Dismantle's claw marks
# (written in the running game only: the game's file keeps it as it is)
MARKS = 999999999
UNUSED = {"midstSfxId": -1, "midstDmyId": -1, "existEffectForLarge": 0, "isVisibleDeadChr": 0}     # row MARKS in the game's file
# the template's own values of the fields the design does not name (Bestial Sling's fan, 10680000): the build's, even when the game
# holds the locked-on ones (a script started again while locked on)
TEMPLATE = {("Bullet", "homingAngle"): 0, ("Bullet", "homingBeginDist"): 0.0, ("Bullet", "hormingStopRange"): 0.0,
            ("Bullet", "lockShootLimitAng"): 30, ("Bullet", "isUseSharedHitList"): 1, ("Bullet", "dmgHitRecordLifeTime"): 999.0}
# param table -> (its name in the design's keys, the template's row)
ROWS = {"Magic": ("Magic", MAGIC), "Bullet": ("Bullet", FAN), "SpEffectParam": ("SpEffect", BLOOD), "SpEffectVfxParam": (None, None)}

LOCKED_FP = 1.8          # locked on, the FP a cast costs: the build's x this
# part 4, locked on: one cut that circles the target. The game's cast lets a bullet fire its shots one after the other for about
# 0.1 s only (shootInterval: 2 of 38 got out), and a HitBulletID written in the running game is not used: so one cut, slow enough
# and turning hard enough to stay around the target, cuts it again each time it forgets the hit
REHIT = 0.05             # seconds a cut remembers a hit: it cuts the same target again after this
SPEED = 120.0            # m/s, as the fan: a target 30 m away is reached in 0.25 s
TURN = 5760              # degrees a second it turns towards the target: SPEED x 48 keeps it around the target at about 1.2 m
LIFE = 3.5               # seconds it lasts: the way to the target and the cuts around it

# field -> (not locked on, locked on); None: the value the build gave it (the design's, or the template's); a function: of it
MODES = {
    ("Magic", "mp"): (None, lambda built: round(built * LOCKED_FP)),     # the FP of a cast (the design's requires.cost.focus_point)
    ("Magic", "refType"): (None, 25),                        # Catch Flame's motion (the build's, 106) / O, Flame!'s
    ("Bullet", "numShoot"): (None, 1),                       # the fan's 38 cuts / one
    ("Bullet", "shootAngle"): (None, 0),                     # the fan's first cut / straight at the target
    ("Bullet", "shootAngleInterval"): (None, 0),
    ("Bullet", "lockShootLimitAng"): (None, 180),            # it leaves aimed at the target wherever it is around you
    ("Bullet", "initVellocity"): (None, SPEED),              # 120 m/s / slower, to turn around the target
    ("Bullet", "maxVellocity"): (None, SPEED),
    ("Bullet", "life"): (None, LIFE),                        # 0.84 s (100 m) / LIFE
    ("Bullet", "homingAngle"): (None, TURN),                 # none / it follows the target
    ("Bullet", "homingBeginDist"): (None, 0.1),              # metres before it starts to turn (Bestial Sling's homing stones: 0.1)
    ("Bullet", "hormingStopRange"): (None, 0),               # it never stops following (Elden Stars)
    ("Bullet", "hitRadius"): (None, 1.0),                    # narrow: the target, not the ones around it
    ("Bullet", "hitRadiusMax"): (None, 1.0),
    ("Bullet", "isUseSharedHitList"): (None, 0),
    ("Bullet", "dmgHitRecordLifeTime"): (None, REHIT),       # a target once a cast (999) / again every REHIT seconds
    ("SpEffectParam", "effectEndurance"): (None, 0.04),      # the blood lasts 0.5 s / 0.04: it bursts again with each cut
    ("SpEffectParam", "vfxId1"): (MARKS, MARKS),             # the blood's SpEffect also shows the row of the claw marks
    ("SpEffectVfxParam", "midstSfxId"): (530172, 530172),    # Beast Claw's claw marks, in both modes (part 6; its colours: Sfx.530172)
    ("SpEffectVfxParam", "midstDmyId"): (220, 220),          # at the middle of the body (as the blood)
    ("SpEffectVfxParam", "existEffectForLarge"): (1, 1),     # on big enemies and bosses too
    ("SpEffectVfxParam", "isVisibleDeadChr"): (1, 1),        # on the cut that kills, too
}


class DismantleFollowsTheLockOn(Interface):
    every = 0.1
    spell = "dismantle"

    def __init__(self):
        self.ids = None         # param table -> the id of the row in the game
        self.built = None       # (table, field) -> the build's value
        self.locked = None      # the mode written last: True locked on, False not, None nothing written yet

    def setup(self):
        disk = tools.read()
        spells = disk.creative.get("innovate_spells") or {}     # none without a build of this session (`run --regulation FILE`)
        if self.spell not in spells:
            tools.log(f"{self.spell} is not in the last build (or this session has no build of its own): nothing to follow", "warn")
            tools.dead()
        rec = spells[self.spell]
        self.ids = {"Magic": rec.rows.magic, "Bullet": rec.rows.copies.Bullet[FAN], "SpEffectParam": rec.rows.copies.SpEffect[BLOOD],
                    "SpEffectVfxParam": MARKS}

        # the build's values: the design's where it names the field, else what the game holds now (the template's)
        basic = rec.design.customs.basic
        cost = rec.design.get("requires", {}).get("cost", {}).get("focus_point")
        self.built = {}
        for table, field in MODES:
            design, template = ROWS[table]
            key = f"{design}.{template}.{field}"
            if (table, field) == ("Magic", "mp") and cost is not None:
                self.built[(table, field)] = cost
            elif table == "SpEffectVfxParam":
                self.built[(table, field)] = UNUSED[field]          # the game's own (it may hold the script's from a run before)
            elif key in basic:
                self.built[(table, field)] = basic[key]
            elif (table, field) in TEMPLATE:
                self.built[(table, field)] = TEMPLATE[(table, field)]
            else:
                self.built[(table, field)] = disk.params[table][self.ids[table]][field]
        self.follow(disk)

    def put(self, disk, locked):
        for (table, field), values in MODES.items():
            v, built = values[1 if locked else 0], self.built[(table, field)]
            disk.params[table][self.ids[table]][field] = built if v is None else v(built) if callable(v) else v

    def follow(self, disk):
        ch = disk.character
        if "lock_on" not in ch:
            ch.level                    # no character in the world: this call is skipped (the script waits)
            tools.log("this game version has no character.lock_on (offsets.json player_to_lock_on): nothing to follow", "warn")
            tools.dead()
        locked = bool(ch.lock_on)
        if locked == self.locked:
            return
        self.put(disk, locked)
        if tools.write(disk.params):
            self.locked = locked
            tools.log(f"{self.spell}: {'one target (locked on)' if locked else 'the fan (not locked on)'}", "debug")

    def loop(self):
        self.follow(tools.read())

    def teardown(self):
        # the build's values (part 1): the spell as it was built, and the game's unused row as it was
        if self.ids is None or self.locked is None:
            return
        disk = tools.read()
        if "Magic" not in disk.params:  # the game closed: its memory is gone, nothing to put back
            return
        for (table, field), v in self.built.items():
            disk.params[table][self.ids[table]][field] = v
        tools.write(disk.params)

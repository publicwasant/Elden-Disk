"""Dismantle follows the lock-on (1.8.4 part 2): locked on, all 38 cuts go at the one target, cast with the motion of O, Flame!; not
locked on, the fan of part 1, cast with Catch Flame's motion (the build's). The game reads its Magic and Bullet rows at every cast,
so the script writes the fields of the other mode into the running game when the lock-on changes, and nothing while it stays.
`teardown()` puts the build's values back. A cast within `every` seconds of locking on or off may still be in the mode before."""

from eldendisk.creative.scripts.edstdlib import tools, Interface

# the template's rows (Bestial Sling): the script finds their copies in the last build
MAGIC, FAN = "6800", "10680000"

# field -> (not locked on, locked on); None: the value the build gave it (the design's, or the template's)
MODES = {
    ("Magic", "refType"): (None, 25),                        # Catch Flame's motion (the build's, 106) / O, Flame!'s
    ("Bullet", "shootAngle"): (None, 0),                     # the fan's first cut / straight at the target
    ("Bullet", "shootAngleInterval"): (None, 0),             # 5 degrees between two / all on one line
    ("Bullet", "homingAngle"): (None, 720),                  # degrees a second a cut turns towards the target
    ("Bullet", "lockShootLimitAng"): (None, 180),            # the cuts leave aimed at the target wherever it is around you
    ("Bullet", "hitRadius"): (None, 0.5),                    # narrow: the target, not the ones around it
    ("Bullet", "hitRadiusMax"): (None, 0.5),
    ("Bullet", "isUseSharedHitList"): (None, 0),             # each cut on its own: 38 hits (1: the 38 together hit once)
}


class DismantleFollowsTheLockOn(Interface):
    every = 0.1
    spell = "dismantle"

    def __init__(self):
        self.ids = None         # "Magic" / "Bullet" -> the id of the copy in the game
        self.built = None       # (table, field) -> the build's value
        self.locked = None      # the mode written last: True locked on, False not, None nothing written yet

    def setup(self):
        disk = tools.read()
        spells = disk.creative.innovate_spells
        if self.spell not in spells:
            tools.log(f"{self.spell} is not in the last build: nothing to follow", "warn")
            tools.dead()
        rec = spells[self.spell]
        self.ids = {"Magic": rec.rows.magic, "Bullet": rec.rows.copies.Bullet[FAN]}

        # the build's values: the design's where it names the field, else what the game holds now (the template's)
        basic = rec.design.customs.basic
        self.built = {}
        for table, field in MODES:
            key = f"{table}.{MAGIC if table == 'Magic' else FAN}.{field}"
            self.built[(table, field)] = basic[key] if key in basic else disk.params[table][self.ids[table]][field]
        self.follow(disk)

    def put(self, disk, locked):
        for (table, field), values in MODES.items():
            v = values[1 if locked else 0]
            disk.params[table][self.ids[table]][field] = self.built[(table, field)] if v is None else v

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
        # the build's values (part 1): the spell as it was built
        if self.ids is None or self.locked is None:
            return
        disk = tools.read()
        for (table, field), v in self.built.items():
            disk.params[table][self.ids[table]][field] = v
        tools.write(disk.params)

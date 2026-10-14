"""Elden-Disk: the Elden Ring Memory Disk I/O Tools (spec 1.8.0 part 2).

The portal
  run                 back up the save, swap in the regulation.bin of creative.json, launch the game offline, put everything back when it exits
  vault               status | list | verify | restore | keep | prune

The game (core)
  read                [* | all | NAME | ID | PATH ...] [--live] [--tree | --flat | --json]
  read                monitor | monitor-buffs | monitor-animations [--mapped | --unmapped]
  write               NAME=VALUE ... (NAME=default: the game's own value); `write` alone lists the names

Creative
  scripts             [* | all] | start | restart | stop | status [NAME[:ID[:PROCESS_ID]] | * | all] | add | remove | change PATH
  innovate-spells     [build [* | all | NAME | ID ...] | secure | apply]
  resurrect           NAME | ID | PATH ... | * | all [--dry-run] [--when-loaded]

Data
  export              the document to <TOOLS-DIR>\\output\\disk.json [--live]
  reset               [* | all | runes | buffs | animations | monitor]: the read baselines start again from now
  check               [FILE]: a regulation.bin against the game, row by row
  probe               where the game's param tables lie in memory

Tooling
  hash                SHA-256 of eldenring.exe (the key of its profile in offsets.json)

Every write needs the portal: the session `run` started with the vault ON, for this very game process. Every command prints concise
lines; with -v it prints the log itself, live (the lines that go to <vault>\\eldendisk.log).
Exit codes: 0 done, 1 error, 2 not supported, 3 anti-cheat running, 4 restore pending, 5 no portal, 130 interrupted.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":   # run as a script (frozen exe, `python eldendisk/__main__.py`)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eldendisk import __version__  # noqa: E402
from eldendisk.commands.common import add_vault_option, add_verbose  # noqa: E402
from eldendisk import logsetup  # noqa: E402
from eldendisk.logbook import book  # noqa: E402
from eldendisk.paths import HERE, default_out_dir, get_resource_path  # noqa: E402


def _lazy(module: str, name: str):
    """The command `name` of eldendisk.commands.<module>, imported only when that command runs (1.8.0 part 3: a command loads its
    own code, not every command's: `read` does not import the build, `vault` not the reader)."""
    def command(args):
        import importlib
        return getattr(importlib.import_module(f"eldendisk.commands.{module}"), name)(args)
    command.__name__ = command.__qualname__ = name
    return command


cmd_hash = _lazy("hash", "cmd_hash")
cmd_innovate = _lazy("innovate", "cmd_innovate")
read_words = _lazy("read", "read_words")
cmd_check = _lazy("read", "cmd_check")
cmd_export = _lazy("read", "cmd_export")
cmd_probe = _lazy("read", "cmd_probe")
cmd_reset = _lazy("read", "cmd_reset")
cmd_resurrect = _lazy("resurrect", "cmd_resurrect")
cmd_run = _lazy("run", "cmd_run")
cmd_scripts = _lazy("scripts", "cmd_scripts")
cmd_vault = _lazy("vault", "cmd_vault")
cmd_write = _lazy("write", "cmd_write")

READ_DEFAULTS = dict(query=None, param=None, param_check=None, probe_params=False, export=False, live=False, live_buffs=False,
                     live_animations=False, mapped=False, unmapped=False, flat=False, json=False, quiet=False, hz=60.0, timeout=15.0,
                     no_idle=False, out=default_out_dir(), export_interval=0.5, timer_interval=2.0, state_ids=None, spec=None, creative_dir=None,
                     words=None, file=None)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="eldendisk", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"eldendisk {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="COMMAND")

    offsets_default = str(get_resource_path("offsets.json", default_dir=HERE))

    def offsets(p):
        p.add_argument("--offsets", default=offsets_default, metavar="FILE",
                       help="offsets.json, the pointer chains of each game version (default: %(default)s)")

    def names(p):
        p.add_argument("--names", dest="state_ids", default=None, metavar="FILE",
                       help="names.json, the names of the buffs and the animations (default: the one next to the exe, else the one in it)")

    def creative_files(p, spec=True):
        if spec:
            p.add_argument("--spec", metavar="FILE", default=None,
                           help="the creative file (default: creative.json next to the exe, else the copy in the exe)")
        p.add_argument("--creative-dir", metavar="DIR", default=None,
                       help="where builds, secured files and the scripts' status are kept (default: <vault>\\creative)")

    def outputs(p, tree=True):
        g = p.add_mutually_exclusive_group()
        if tree:
            g.add_argument("--tree", action="store_true", help="the values as a tree (the default)")
        g.add_argument("--flat", action="store_true", help="one `full.path  value` row per value")
        g.add_argument("--json", action="store_true", help="the result as JSON")

    def hz(p):
        p.add_argument("--hz", type=float, default=60.0, help="reads per second, 1-120 (default: 60)")

    def timeout(p):
        p.add_argument("--timeout", type=float, default=15.0, metavar="SEC",
                       help="seconds to wait for the game and a loaded world (default: 15)")

    # ---- the portal ----
    r = sub.add_parser("run", help="open the portal: back up the save, swap in the build, launch the game offline, restore when it exits")
    r.add_argument("--save-dir", help="the game's save folder (default: auto-detected / remembered in the Windows Registry)")
    add_vault_option(r)
    r.add_argument("--game-dir", help="folder containing eldenring.exe (default: auto-detect via Steam)")
    r.add_argument("--regulation", metavar="FILE", help="swap this regulation.bin in for the session instead of the one built from "
                   "creative.json (an experiment); needs the vault ON")
    creative_files(r)
    offsets(r)
    g = r.add_mutually_exclusive_group()
    g.add_argument("--vault-on", dest="protect", action="store_true",
                   help="back the save up before the game and restore it after (the default)")
    g.add_argument("--vault-off", dest="protect", action="store_false",
                   help="no backup, no restore, nothing swapped or written: the game's changes stay (for reading while farming)")
    r.set_defaults(protect=True)
    r.add_argument("--no-archive-contaminated", action="store_true",
                   help="do not keep a copy of a modified save in the vault before restoring it")
    r.add_argument("--keep", type=int, default=5, metavar="N",
                   help="after a finished session keep the newest N snapshots; 0 = never prune (default: 5)")
    r.add_argument("--launch-timeout", type=float, default=120.0, metavar="SEC",
                   help="seconds to wait for eldenring.exe to appear (default: 120)")
    add_verbose(r)
    r.set_defaults(fn=cmd_run)

    v = sub.add_parser("vault", help="the vault: status, list, verify, restore, keep, prune")
    add_vault_option(v)
    add_verbose(v)
    vs = v.add_subparsers(dest="vault_cmd", required=True, metavar="FUNCTION")
    s = vs.add_parser("restore", help="finish an unended session: put the snapshot back (safe to repeat)")
    s.add_argument("--snapshot", help="restore this snapshot by name instead (the current save is kept as <ts>-pre-restore)")
    s.add_argument("--save-dir", help="the game's save folder (default: auto-detect / remembered in the Windows Registry)")
    s.add_argument("--no-archive-contaminated", action="store_true",
                   help="do not keep a copy of a modified save in the vault before restoring it")
    s = vs.add_parser("keep", help="take the CURRENT save as the new baseline and end an unresolved session")
    s.add_argument("--yes", action="store_true", help="do it (without it only explains what would happen)")
    vs.add_parser("status", help="the session record, the last snapshot, the vault's size")
    s = vs.add_parser("list", help="the snapshots with their size and verification")
    s.add_argument("--fast", action="store_true", help="skip re-hashing")
    s = vs.add_parser("verify", help="hash a snapshot again against its manifest")
    s.add_argument("snapshot", help="snapshot name, e.g. 20261004-213015")
    s = vs.add_parser("prune", help="delete old snapshots (refused while a session is unresolved)")
    s.add_argument("--keep", type=int, required=True, metavar="N", help="number of newest snapshots to keep")
    for sp in vs.choices.values():
        add_vault_option(sp, leaf=True)
        add_verbose(sp, leaf=True)
        sp.set_defaults(fn=cmd_vault)

    # ---- the game ----
    rd = sub.add_parser("read", help="the game's values: the document or a part of it, or the monitors (read-only)",
                        description="read [* | all | NAME | ID | PATH ...] [--live] [--tree | --flat | --json]\n"
                                    "read monitor | monitor-buffs | monitor-animations [--mapped | --unmapped]",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    rd.set_defaults(**READ_DEFAULTS)
    rd.add_argument("words", nargs="*", metavar="NAME",
                    help="nothing, * or all: the whole document; or names: hp, attrs.*, character.runes, params.effects.1621000, "
                         "params.Magic.6230.mp*, creative.resurrect.great_enemies; or monitor, monitor-buffs, monitor-animations")
    rd.add_argument("--live", action="store_true", help="do not stop: keep the values current (at --hz)")
    outputs(rd)
    m = rd.add_mutually_exclusive_group()
    m.add_argument("--mapped", action="store_true", help="the monitors: only ids that are in names.json")
    m.add_argument("--unmapped", action="store_true", help="the monitors: only ids that are NOT in names.json yet (the default)")
    rd.add_argument("-q", "--quiet", action="store_true",
                    help="monitor-buffs: hide short-lived internal buffs (0 <= duration < 1 s)")
    hz(rd)
    timeout(rd)
    offsets(rd)
    names(rd)
    creative_files(rd)
    add_vault_option(rd)
    add_verbose(rd)
    rd.set_defaults(fn=read_words)

    w = sub.add_parser("write", help="change values in the running game (inside the portal); `write` alone lists the names",
                       description="write NAME=VALUE ... | write NAME=default | write")
    w.add_argument("pairs", nargs="*", metavar="NAME=VALUE",
                   help="vigor=99 hp=1914 params.effects.1621000.effectEndurance=-1 params.Magic.6230.mp=10 params.Magic.6230=default "
                        "creative.resurrect.great_enemies.margit.defeated=false ...")
    offsets(w)
    creative_files(w)
    add_vault_option(w)
    add_verbose(w)
    w.set_defaults(fn=cmd_write)

    # ---- creative ----
    sc = sub.add_parser("scripts", help="your Python scripts next to the game: list them, start, restart, stop, status, add, remove, change",
                        description="scripts [* | all]\n"
                                    "scripts start | restart | stop | status [NAME[:ID[:PROCESS_ID]] | * | all] [--when-loaded]\n"
                                    "scripts add | remove | change PATH",
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    sc.add_argument("words", nargs="*", metavar="WORD", help="a function (start, restart, stop, status, add, remove, change) and its "
                                                             "script (NAME, NAME:ID, NAME:ID:PROCESS_ID, * or all) or PATH")
    sc.add_argument("--when-loaded", dest="when_loaded", action="store_true",
                    help="start: start the scripts once a character is in the world (what `run` starts)")
    outputs(sc)
    offsets(sc)
    names(sc)
    creative_files(sc)
    add_vault_option(sc)
    add_verbose(sc)
    sc.set_defaults(fn=cmd_scripts)

    ii = sub.add_parser("innovate-spells", help="new spells: show them, build, secure, apply their texts and colours",
                        description="innovate-spells | build [* | all | NAME | ID ...] [--dry-run] [--source FILE] | secure | "
                                    "apply [--when-loaded]")
    ii.add_argument("function", nargs="?", choices=("build", "secure", "apply"), help="nothing: the spells with their ids")
    ii.add_argument("names", nargs="*", metavar="NAME", help="build: the spells to build (the key of a slot in creative.json, or the "
                                                             "goods id); nothing, * or all: every spell")
    ii.add_argument("--dry-run", action="store_true", help="build: build and check in memory, write nothing")
    ii.add_argument("--source", metavar="FILE", default=None,
                    help="build, secure: the game's original regulation.bin to build on (default: the one in the game folder)")
    ii.add_argument("--game-dir", default=None, help="folder containing eldenring.exe (default: auto-detect via Steam)")
    ii.add_argument("--when-loaded", dest="when_loaded", action="store_true",
                    help="apply: wait until a character is in the world, write once and end (what `run` starts)")
    offsets(ii)
    creative_files(ii)
    add_vault_option(ii)
    add_verbose(ii)
    ii.set_defaults(fn=cmd_innovate)

    ru = sub.add_parser("resurrect", help="a great enemy you have beaten, alive again until the game closes (inside the portal)",
                        description="resurrect NAME | ID | PATH ... | * | all [--dry-run] [--when-loaded]")
    ru.add_argument("names", nargs="*", metavar="NAME",
                    help="a name in any letter case or a part of it (margit, \"mohg lord\"), the id (10000850), the path "
                         "(creative.resurrect.great_enemies.10000850), or * / all: every defeated one")
    ru.add_argument("--dry-run", action="store_true", help="say what would come back; write nothing")
    ru.add_argument("--when-loaded", dest="when_loaded", action="store_true",
                    help="the list of creative.json (resurrect.great_enemies.activate), once a character is in the world (what `run` starts)")
    offsets(ru)
    creative_files(ru)
    add_vault_option(ru)
    add_verbose(ru)
    ru.set_defaults(fn=cmd_resurrect)

    # ---- data ----
    ex = sub.add_parser("export", help="the document (the single source of truth) to <TOOLS-DIR>\\output\\disk.json")
    ex.set_defaults(**READ_DEFAULTS)
    ex.add_argument("--live", action="store_true", help="do not stop: write it again each time it changes")
    hz(ex)
    ex.add_argument("--out", default=default_out_dir(), metavar="DIR", help="the folder of disk.json (default: %(default)s)")
    ex.add_argument("--export-interval", type=float, default=0.5, metavar="SEC",
                    help="--live: minimum seconds between two writes (default: 0.5)")
    ex.add_argument("--timer-interval", type=float, default=2.0, metavar="SEC",
                    help="--live: seconds between writes that only change a buff countdown; 0 = never (default: 2)")
    ex.add_argument("--no-idle", action="store_true",
                    help="--live: keep reading while the game window is unfocused (default: pause and report IDLE)")
    timeout(ex)
    offsets(ex)
    names(ex)
    creative_files(ex)
    add_vault_option(ex)
    add_verbose(ex)
    ex.set_defaults(fn=cmd_export)

    rs = sub.add_parser("reset", help="the read baselines start again from now (runes.delta = 0, the monitors' history); writes nothing to the game",
                        description="reset [* | all | runes | buffs | animations | monitor]")
    rs.set_defaults(**READ_DEFAULTS)
    rs.add_argument("words", nargs="*", metavar="NAME", help="runes, buffs, animations, monitor (both); nothing, * or all: every one")
    timeout(rs)
    offsets(rs)
    names(rs)
    add_vault_option(rs)
    add_verbose(rs)
    rs.set_defaults(fn=cmd_reset)

    ck = sub.add_parser("check", help="a regulation.bin against the running game, row by row (exit code 0 only when they agree)",
                        description="check [FILE]")
    ck.set_defaults(**READ_DEFAULTS)
    ck.add_argument("file", nargs="?", default=None, metavar="FILE",
                    help="the regulation.bin to compare (default: the one in the game folder: what the game loaded)")
    ck.add_argument("--json", action="store_true", help="every difference as JSON")
    timeout(ck)
    offsets(ck)
    add_vault_option(ck)
    add_verbose(ck)
    ck.set_defaults(fn=cmd_check)

    pr = sub.add_parser("probe", help="where the game's param tables lie in memory (for a new game version)")
    pr.set_defaults(**READ_DEFAULTS)
    pr.add_argument("--json", action="store_true", help="the result as JSON")
    timeout(pr)
    offsets(pr)
    add_vault_option(pr)
    add_verbose(pr)
    pr.set_defaults(fn=cmd_probe)

    # ---- tooling ----
    h = sub.add_parser("hash", help="SHA-256 of eldenring.exe (the key of its profile in offsets.json)")
    h.add_argument("--game-dir", help="folder containing eldenring.exe (default: auto-detect via Steam)")
    add_verbose(h)
    h.set_defaults(fn=cmd_hash)
    return ap


def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.cmd in ("read", "export"):
        if not 1 <= args.hz <= 120:
            ap.error("--hz must be between 1 and 120")
        if args.export_interval < 0 or args.timer_interval < 0:
            ap.error("--export-interval and --timer-interval must not be negative")
    if args.cmd in ("read", "export", "reset", "check", "probe") and args.timeout <= 0:
        ap.error("--timeout must be positive")
    if args.cmd == "read" and args.json and args.live:
        ap.error("--json is for a one-shot read (export --live keeps a file current)")
    if args.cmd == "scripts" and args.when_loaded and (args.words or ["start"])[0] != "start":
        ap.error("--when-loaded goes with scripts start")
    if args.cmd == "innovate-spells":
        if args.function != "build" and (args.dry_run or args.names):
            ap.error("names and --dry-run go with innovate-spells build")
        if args.function != "apply" and args.when_loaded:
            ap.error("--when-loaded goes with innovate-spells apply")
        if args.function not in ("build", "secure") and args.source:
            ap.error("--source goes with innovate-spells build or secure")
    if args.cmd == "resurrect" and args.when_loaded and args.dry_run:
        ap.error("--dry-run and --when-loaded cannot be combined")
    if args.cmd == "run" and args.keep < 0:
        ap.error("--keep must not be negative")
    if args.cmd == "run" and args.launch_timeout <= 0:
        ap.error("--launch-timeout must be positive")
    logsetup.start(args, logsetup.argv_of(argv), real=argv is None)
    try:
        code = args.fn(args)
    except KeyboardInterrupt:
        book.w("client", "interrupted")
        code = 130
    except (OSError, ValueError, RuntimeError) as exc:
        book.e("client", str(exc))
        code = 1
    logsetup.finish(code)
    return code


if __name__ == "__main__":
    sys.exit(main())

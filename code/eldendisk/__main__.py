"""CLI: eldendisk run | read | write | vault | design | innovate-items | external-scripts | hash

  run               host: back up the save, launch the game offline, restore the save when it exits (leave this open)
  read              look at the game's values: print, --query, --export, --live, --live-buffs, --live-animations (read-only)
  write             edit values in the running game (--set, --refill, --reset), give it the spells' text (--text) or the fire colour
                    (--flame-color); only inside a session started by `run`
  vault             save vault tools (status, list, verify, restore, keep, prune)
  design            the design (design.json): what it holds, what is secured, the last build
  innovate-items    build things for the game outside the game: `innovate-items spells --add all|--secure`
  external-scripts  your own scripts next to the game: `external-scripts [--run]`

Every command prints concise lines; with -v it prints the log itself, live (the same lines that go to
<vault>/eldendisk.log).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":   # run as a script (frozen exe, `python eldendisk/__main__.py`)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eldendisk import __version__  # noqa: E402
from eldendisk.commands.common import add_vault_option, add_verbose  # noqa: E402
from eldendisk.commands.design import cmd_design  # noqa: E402
from eldendisk.commands.hash import cmd_hash  # noqa: E402
from eldendisk.commands.read import cmd_read  # noqa: E402
from eldendisk.commands.run import cmd_run  # noqa: E402
from eldendisk.commands.vault import cmd_vault  # noqa: E402
from eldendisk.commands.write import cmd_write  # noqa: E402
from eldendisk import logsetup  # noqa: E402
from eldendisk.logbook import book  # noqa: E402
from eldendisk.paths import HERE, default_out_dir, get_resource_path  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="eldendisk", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"eldendisk {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    offsets_default = str(get_resource_path("offsets.json", default_dir=HERE))
    state_ids_default = str(get_resource_path("chr_state_ids.json", default_dir=HERE))

    # ---- run (host) ----
    r = sub.add_parser("run", help="host: back up the save, launch the game offline, restore the save when it exits")
    r.add_argument("--save-dir", help="live save folder (default: auto-detected / remembered in the Windows Registry)")
    add_vault_option(r)
    r.add_argument("--game-dir", help="folder containing eldenring.exe (default: auto-detect via Steam)")
    r.add_argument("--regulation", metavar="FILE", help="swap this regulation.bin in for the session instead of building one "
                   "from the design (an experiment); needs the vault ON")
    r.add_argument("--spec", metavar="FILE", default=None, help="the design: the spells to build into regulation.bin (default: design.json next to the exe, "
                   "else the copy embedded in it); with the vault ON `run` swaps the secured file when the design is unchanged, else builds")
    r.add_argument("--design-dir", metavar="DIR", default=None, help="where the built and secured files go (default: %%LOCALAPPDATA%%\\EldenDisk\\design)")
    r.add_argument("--offsets", default=offsets_default, help="offsets.json, checked before launching (default: %(default)s)")
    r.add_argument("--scripts-dir", metavar="PATH", nargs="+", action="extend", default=[],
                   help="more external scripts to start next to the game, besides the ones the exe carries (external_scripts/defaults when "
                        "it was built): folders (their *.py) or .py files, anywhere; vault ON only")
    g = r.add_mutually_exclusive_group()
    g.add_argument("--vault-on", dest="protect", action="store_true",
                   help="back the save up before the game and restore it after (the default)")
    g.add_argument("--vault-off", dest="protect", action="store_false",
                   help="no backup, no restore: the game's changes stay; `write` is not allowed (for reading while farming)")
    r.set_defaults(protect=True)
    r.add_argument("--no-archive-contaminated", action="store_true",
                   help="do not keep a copy of a modified save in the vault before restoring it")
    r.add_argument("--keep", type=int, default=5, metavar="N",
                   help="after a finished session keep the newest N snapshots; 0 = never prune (default: 5)")
    r.add_argument("--launch-timeout", type=float, default=120.0, metavar="SEC",
                   help="seconds to wait for eldenring.exe to appear (default: 120)")
    add_verbose(r)
    r.set_defaults(fn=cmd_run)

    # ---- read ----
    rd = sub.add_parser("read", help="look at the game's values: print, query, export, live (read-only)")
    rd.add_argument("--query", metavar="NAME", nargs="+",
                    help="one or several values or groups, e.g. runes, hp, attrs.*, character.runes.* character.buffs.*  "
                         "(no flag: every value)")
    rd.add_argument("--flat", action="store_true",
                    help="print values as one 'full.path  value' row each instead of the tree (works with --query and --live)")
    rd.add_argument("--export", action="store_true", help="write disk-state.json once and exit")
    rd.add_argument("--live", action="store_true",
                    help="do not stop: keep showing (with --export: keep writing; with --query: those values)")
    rd.add_argument("--probe-params", action="store_true",
                    help="list where the param files of the other tables are in memory (read-only, once; with --json too)")
    rd.add_argument("--param", metavar="TABLE.ID[.FIELD]", nargs="+",
                    help="rows of the game's tables, once: Goods, Magic, SpEffect, Bullet, AtkParam_Pc, ShopLineup, e.g. "
                         "Magic.6230  Bullet.10621000  Magic.6230.mp*  (all fields, or a field / pattern; a tree, --flat for one path per "
                         "value, --json)")
    rd.add_argument("--param-check", metavar="FILE", nargs="?", const="", default=None,
                    help="compare the rows of the six tables in a regulation.bin with the running game, row by row; no FILE: the "
                         "regulation.bin in the game's folder (what the game loaded; `run` puts the build there); exit code 0 only when "
                         "they agree (add --json for every difference)")
    rd.add_argument("--live-buffs", action="store_true", help="buffs monitor: one row per buff id, kept current")
    rd.add_argument("--live-animations", action="store_true", help="animation monitor: one row per animation id (for chr_state_ids.json)")
    rd.add_argument("--mapped", action="store_true",
                    help="--live-buffs / --live-animations: only ids that are in chr_state_ids.json")
    rd.add_argument("--unmapped", action="store_true",
                    help="--live-buffs / --live-animations: only ids that are NOT in chr_state_ids.json yet")
    rd.add_argument("--json", action="store_true", help="print the result as JSON (one-shot only)")
    rd.add_argument("--timeout", type=float, default=15.0, metavar="SEC",
                    help="one-shot: seconds to wait for the game and a loaded world (default: 15)")
    rd.add_argument("--offsets", default=offsets_default, help="offsets.json (default: %(default)s)")
    rd.add_argument("--state-ids", default=state_ids_default, help="chr_state_ids.json, names of buffs and animations (default: %(default)s)")
    add_vault_option(rd)
    rd.add_argument("--hz", type=float, default=60.0, help="reads per second, 1-120 (default: 60)")
    rd.add_argument("-q", "--quiet", action="store_true",
                    help="--live-buffs: hide short-lived internal buffs (0 <= duration < 1 s); keeps permanent (-1) and timed buffs")
    rd.add_argument("--no-idle", action="store_true",
                    help="--export --live: keep reading while the game window is unfocused (default: pause and report IDLE)")
    rd.add_argument("--out", default=default_out_dir(), help="--export: directory for disk-state.json (default: %(default)s)")
    rd.add_argument("--export-interval", type=float, default=0.5, metavar="SEC",
                    help="--export --live: minimum seconds between file writes (default: 0.5)")
    rd.add_argument("--timer-interval", type=float, default=2.0, metavar="SEC",
                    help="--export --live: seconds between writes that only change a buff countdown; 0 = never (default: 2)")
    add_verbose(rd)
    rd.set_defaults(fn=cmd_read)

    # ---- write ----
    w = sub.add_parser("write", help="edit values in the running game (needs a session started by `run`)")
    w.add_argument("--set", nargs="+", action="extend", default=[], metavar="NAME=VALUE",
                   help="set values once, e.g. --set vigor=99 level=150 (names: level, runes, attributes, hp, fp, stamina; "
                        "full or short; a group pattern such as attrs.* works). Game params: --set "
                        "params.effects.1621000.effectEndurance=-1 (Black Flame; a pattern such as "
                        "\"params.effects.*.effectEndurance\" sets every row; typed in full) or any row of the six tables: "
                        "params.Magic.6230.mp=10 (Goods, Magic, SpEffect, Bullet, AtkParam_Pc, ShopLineup)")
    w.add_argument("--reset", nargs="+", action="extend", default=[], metavar="NAME",
                   help="put the game's own values back: params.effects.1621000.effectEndurance (one field), "
                        "params.effects.1621000 (one row), params.Magic.6230.mp (a field changed in this game process), "
                        "params.Magic.6230 (a row), or all")
    w.add_argument("--refill", metavar="LIST", help="refill current hp, fp, stamina to their maximum once, e.g. hp,fp,stamina")
    w.add_argument("--text", action="store_true",
                   help="put the text of the design's spells (name, short line, description) into the running game; `run` does this by "
                        "itself after the game is up. Stands alone (only --wait or --when-loaded, --spec and --design-dir go with it)")
    w.add_argument("--flame-color", action="store_true",
                   help="recolour the fire of Flame, Grant Me Strength (the fire while casting and the burst) in the running game with the design's "
                        "`flame_color`; `run` does this by itself after the game is up. Stands alone (only --wait, --spec and "
                        "--design-dir go with it)")
    w.add_argument("--when-loaded", dest="when_loaded", action="store_true",
                   help="--text, --flame-color: wait until a character is in the world, write once, and end (what `run` starts); "
                        "waits without a time limit, so it does not go with --wait")
    w.add_argument("--wait", nargs="?", type=float, const=300.0, default=0, metavar="SEC",
                   help="--text, --flame-color: wait up to SEC seconds (default 300) for the game to have loaded what it needs")
    w.add_argument("--spec", metavar="FILE", default=None, help="--text, --flame-color: the design (default: design.json next to the exe, else the embedded copy)")
    w.add_argument("--design-dir", metavar="DIR", default=None, help="--text, --flame-color: where the built files are (default: <vault>\\design)")
    add_vault_option(w)
    w.add_argument("--offsets", default=offsets_default, help="offsets.json (default: %(default)s)")
    add_verbose(w)
    w.set_defaults(fn=cmd_write)

    # ---- vault ----
    v = sub.add_parser("vault", help="save vault tools: status, list, verify, restore, keep, prune")
    add_vault_option(v)
    add_verbose(v)
    vs = v.add_subparsers(dest="vault_cmd", required=True)
    s = vs.add_parser("restore", help="restore the save after an interrupted session (safe to repeat)")
    s.add_argument("--snapshot", help="restore this snapshot by name instead (the current save is kept as <ts>-pre-restore)")
    s.add_argument("--save-dir", help="live save folder (default: auto-detect / remembered in the Windows Registry)")
    s.add_argument("--no-archive-contaminated", action="store_true",
                   help="do not keep a copy of a modified save in the vault before restoring it")
    s = vs.add_parser("keep", help="accept the CURRENT save as the new baseline and end an unresolved session")
    s.add_argument("--yes", action="store_true", help="do it (without it only explains what would happen)")
    vs.add_parser("status", help="session record, last snapshot, vault size")
    s = vs.add_parser("list", help="list snapshots with size and verification result")
    s.add_argument("--fast", action="store_true", help="skip re-hashing")
    s = vs.add_parser("verify", help="re-hash one snapshot against its manifest")
    s.add_argument("snapshot", help="snapshot name, e.g. 20261004-213015")
    s = vs.add_parser("prune", help="delete old snapshots (refused while a session is unresolved)")
    s.add_argument("--keep", type=int, required=True, metavar="N", help="number of newest snapshots to keep")
    for sp in vs.choices.values():
        add_vault_option(sp, leaf=True)
        add_verbose(sp, leaf=True)
        sp.set_defaults(fn=cmd_vault)

    # ---- design: the overview, and the things it builds and runs (one command each; before 1.8.0 under `extension`) ----
    d = sub.add_parser("design", help="the design (design.json): what it holds, what is secured, the last build")
    d.add_argument("--list", action="store_true", help="the same (the overview is what `design` shows)")
    d.add_argument("--design-dir", metavar="DIR", default=None, help="where the built files go (default: <vault>\\design)")
    d.add_argument("--spec", metavar="FILE", default=None, help="the design (default: design.json next to the exe, else the embedded copy)")
    add_vault_option(d, leaf=True)
    add_verbose(d, leaf=True)
    d.set_defaults(fn=cmd_design)

    ii = sub.add_parser("innovate-items", help="new items for the game, built outside it (kinds: spells)")
    add_vault_option(ii, leaf=True)
    add_verbose(ii, leaf=True)
    ik = ii.add_subparsers(dest="items_kind")
    ci = ik.add_parser("spells", help="build a regulation.bin with the spells of the design, or secure the one you tried")
    ci.add_argument("--add", metavar="all|PATH", nargs="+",
                    help="which spells to build: `all`, or the path of each spell in design.json (spells.slots.<id>; several can be given). "
                         "Built every time, and `run` then builds the same selection until `--add` changes it; without any --add "
                         "`run` builds every spell")
    ci.add_argument("--secure", action="store_true",
                    help="after you tried the build in the game (game closed): check it again and keep it as regulation.secured.bin; "
                         "`run` then swaps it without building while the design does not change")
    ci.add_argument("--dry-run", action="store_true", help="build and check in memory, write nothing")
    ci.add_argument("--source", metavar="FILE", default=None,
                    help="the game's original regulation.bin to build on (default: the one in the game folder)")
    ci.add_argument("--game-dir", default=None, help="folder containing eldenring.exe (default: auto-detect via Steam)")
    ci.add_argument("--design-dir", metavar="DIR", default=None, help="where the built files go (default: <vault>\\design)")
    ci.add_argument("--spec", metavar="FILE", default=None, help="the design")
    add_vault_option(ci, leaf=True)
    add_verbose(ci, leaf=True)
    ii.set_defaults(fn=cmd_design)

    xs = sub.add_parser("external-scripts", help="your Python scripts that run next to the game (edstdlib): list them, or run them "
                                                 "(`run` does that by itself, vault ON)")
    xs.add_argument("--run", action="store_true",
                    help="run every script of the folder until the game closes (needs the session `run` started; `run` starts this by itself)")
    xs.add_argument("--when-loaded", dest="when_loaded", action="store_true",
                    help="with --run: start the scripts once a character is in the world (what `run` starts)")
    xs.add_argument("--scripts-dir", metavar="PATH", nargs="+", action="extend", default=[],
                    help="more scripts besides the ones the exe carries (external_scripts/defaults when it was built): folders (their *.py) "
                         "or .py files, anywhere")
    xs.add_argument("--offsets", default=offsets_default, help="offsets.json (default: %(default)s)")
    xs.add_argument("--state-ids", dest="state_ids", default=state_ids_default, help="chr_state_ids.json (default: %(default)s)")
    xs.add_argument("--design-dir", metavar="DIR", default=None, help="where the design's files are")
    xs.add_argument("--spec", metavar="FILE", default=None, help="the design")
    add_vault_option(xs, leaf=True)
    add_verbose(xs, leaf=True)
    xs.set_defaults(fn=cmd_design)

    # ---- tooling ----
    h = sub.add_parser("hash", help="print SHA-256 of eldenring.exe (key for offsets.json)")
    h.add_argument("--game-dir", help="folder containing eldenring.exe (default: auto-detect via Steam)")
    add_verbose(h)
    h.set_defaults(fn=cmd_hash)
    return ap


def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.cmd == "read":
        if not 1 <= args.hz <= 120:
            ap.error("--hz must be between 1 and 120")
        if args.export_interval < 0 or args.timer_interval < 0:
            ap.error("--export-interval and --timer-interval must not be negative")
        if args.timeout <= 0:
            ap.error("--timeout must be positive")
        monitor = args.live_buffs or args.live_animations
        if args.probe_params and (args.export or args.query is not None or args.live or monitor or args.flat or args.param or args.param_check is not None):
            ap.error("--probe-params stands alone (only --json goes with it)")
        if args.param and (args.export or args.query is not None or args.live or monitor):
            ap.error("--param stands alone (only --flat or --json go with it)")
        if args.param_check is not None and (args.export or args.query is not None or args.live or monitor or args.flat or args.param
                                 or args.probe_params):
            ap.error("--param-check stands alone (only --json goes with it)")
        if args.export and args.query is not None:
            ap.error("--export and --query cannot be combined")
        if monitor and (args.export or args.query is not None or args.live):
            ap.error("--live-buffs / --live-animations stand alone (they can be used together)")
        if args.mapped and args.unmapped:
            ap.error("--mapped and --unmapped cannot be combined")
        if (args.mapped or args.unmapped) and not monitor:
            ap.error("--mapped / --unmapped go with --live-buffs / --live-animations")
        if args.flat and (args.export or monitor or args.json):
            ap.error("--flat is for the printed values (read, --query, --live), not --export, --json or the monitors")
        if args.json and (args.live or args.export or monitor):
            ap.error("--json is for the one-shot print and --query only")
    if args.cmd == "write" and not args.text and not args.flame_color and not args.set and not args.refill and not args.reset:
        ap.error("nothing to do: give --set NAME=VALUE, --refill LIST and/or --reset NAME, or --text, or --flame-color")
    if args.cmd == "write" and args.text and args.flame_color:
        ap.error("--text and --flame-color are separate steps: run them one at a time")
    if args.cmd == "write" and (args.text or args.flame_color) and (args.set or args.refill or args.reset):
        ap.error("--text and --flame-color stand alone (they do not go with --set, --refill or --reset)")
    if args.cmd == "write" and not args.text and not args.flame_color and (args.wait or args.when_loaded or args.spec or args.design_dir):
        ap.error("--wait, --when-loaded, --spec and --design-dir go with --text or --flame-color")
    if args.cmd == "write" and args.when_loaded and args.wait:
        ap.error("--when-loaded waits without a time limit: it does not go with --wait")
    if args.cmd == "write" and args.wait < 0:
        ap.error("--wait must not be negative")
    if args.cmd == "external-scripts" and args.when_loaded and not args.run:
        ap.error("--when-loaded goes with --run")
    if args.cmd == "innovate-items" and not getattr(args, "items_kind", None):
        ap.error("give the kind of item: innovate-items spells")
    if args.cmd == "innovate-items" and args.secure and (args.add is not None or args.dry_run):
        ap.error("--secure stands alone (it does not build; --add and --dry-run build)")
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

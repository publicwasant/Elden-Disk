"""CLI: eldendisk run | read | write | vault | extension | build | hash

  run    host: back up the save, launch the game offline, restore the save when it exits (leave this open)
  read   look at the game's values: print, --query, --export, --live, --live-buffs, --live-animations (read-only)
  write  edit values in the running game (--set, --refill, --reset); only inside a session started by `run`
  vault  save vault tools (status, list, verify, restore, keep, prune)
  extension  build things for the game outside the game: `extension --list`, `extension customize-items --add all`

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
from eldendisk.commands.build import cmd_build, cmd_hash  # noqa: E402
from eldendisk.commands.common import add_vault_option, add_verbose  # noqa: E402
from eldendisk.commands.extension import cmd_extension  # noqa: E402
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
                   "from the spec (an experiment); needs the vault ON")
    r.add_argument("--spec", metavar="FILE", default=None, help="the items to build into regulation.bin (default: items.json next to the exe, "
                   "else the copy embedded in it); with the vault ON `run` builds it every time")
    r.add_argument("--extension-dir", metavar="DIR", default=None, help="where the built regulation.bin goes (default: %%LOCALAPPDATA%%\\EldenDisk\\extension)")
    r.add_argument("--offsets", default=offsets_default, help="offsets.json, checked before launching (default: %(default)s)")
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
                        "\"params.effects.*.effectEndurance\" sets every row; typed in full)")
    w.add_argument("--reset", nargs="+", action="extend", default=[], metavar="NAME",
                   help="put the game's own values back: params.effects.1621000.effectEndurance (one field), "
                        "params.effects.1621000 (one row), or all")
    w.add_argument("--refill", metavar="LIST", help="refill current hp, fp, stamina to their maximum once, e.g. hp,fp,stamina")
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

    # ---- extension ----
    e = sub.add_parser("extension", help="build things for the game outside the game (customize-items)")
    e.add_argument("--list", action="store_true", help="show every extension, its spec and its last output")
    e.add_argument("--extension-dir", metavar="DIR", default=None,
                   help="where the built files go (default: %%LOCALAPPDATA%%\\EldenDisk\\extension)")
    e.add_argument("--spec", metavar="FILE", default=None, help="the items to build (default: items.json next to the exe, else the embedded copy)")
    add_verbose(e)
    es = e.add_subparsers(dest="ext_name")
    ci = es.add_parser("customize-items", help="build a regulation.bin with the items of the spec (sources/items.json)")
    ci.add_argument("--add", metavar="all|ID", help="build all items of the spec, or the one with this id (built every time)")
    ci.add_argument("--dry-run", action="store_true", help="build and check in memory, write nothing")
    ci.add_argument("--source", metavar="FILE", default=argparse.SUPPRESS,
                    help="the game's original regulation.bin to build on (default: the one in the game folder)")
    ci.add_argument("--game-dir", default=argparse.SUPPRESS, help="folder containing eldenring.exe (default: auto-detect via Steam)")
    ci.add_argument("--extension-dir", metavar="DIR", default=argparse.SUPPRESS, help="where the built files go")
    ci.add_argument("--spec", metavar="FILE", default=argparse.SUPPRESS, help="the items to build")
    add_verbose(ci, leaf=True)
    e.set_defaults(fn=cmd_extension)

    # ---- tooling ----
    h = sub.add_parser("hash", help="print SHA-256 of eldenring.exe (key for offsets.json)")
    h.add_argument("--game-dir", help="folder containing eldenring.exe (default: auto-detect via Steam)")
    add_verbose(h)
    h.set_defaults(fn=cmd_hash)

    b = sub.add_parser("build", help="build standalone eldendisk.exe using PyInstaller or Nuitka")
    b.add_argument("-e", "--engine", choices=["pyinstaller", "nuitka"], default="pyinstaller",
                   help="build engine to use (default: pyinstaller)")
    b.add_argument("-c", "--clean", action="store_true", help="clean build cache directories before compiling")
    b.add_argument("-em", "--embed-configs", action="store_true",
                   help="embed offsets.json and chr_state_ids.json directly into the executable")
    b.add_argument("-i", "--icon", help="path to icon file (.ico)")
    add_verbose(b)
    b.set_defaults(fn=cmd_build)
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
    if args.cmd == "write" and not args.set and not args.refill:
        ap.error("nothing to do: give --set NAME=VALUE and/or --refill LIST")
    if args.cmd == "extension" and not args.list and not args.ext_name:
        ap.error("give --list or an extension name (customize-items)")
    if args.cmd == "extension" and args.ext_name == "customize-items" and args.list:
        ap.error("--list stands alone")
    if args.cmd == "run" and args.keep < 0:
        ap.error("--keep must not be negative")
    if args.cmd == "run" and args.launch_timeout <= 0:
        ap.error("--launch-timeout must be positive")
    logsetup.start(args, logsetup.argv_of(argv))
    try:
        code = args.fn(args)
    except KeyboardInterrupt:
        book.w("cli", "interrupted")
        code = 130
    except (OSError, ValueError, RuntimeError) as exc:
        book.e("cli", str(exc))
        code = 1
    logsetup.finish(code)
    return code


if __name__ == "__main__":
    sys.exit(main())

"""`extension --list` and `extension customize-items --add all|ID`: build things for the game outside the game.

customize-items reads the spec (`sources/items.json`, embedded in the exe), takes the game's own regulation.bin as the base
and builds a new one, every time. The file is not put into the game here: `run` (vault ON) builds it too and swaps it in for
the session, and the vault puts the game's own file back."""
from __future__ import annotations

from pathlib import Path

from .. import extension, ui
from ..extension.customize_items import service
from ..logbook import book
from ..paths import describe_resource, get_resource_path


def spec_file(args) -> Path:
    """`--spec FILE`, else items.json next to the exe, else the embedded copy, else sources/ in the source tree."""
    if getattr(args, "spec", None):
        return Path(args.spec)
    return get_resource_path(service.SPEC_FILE, default_dir=service.SOURCES_DIR)


def game_file(args) -> Path | None:
    """The game's regulation.bin: `--source FILE`, else the one in the game folder. None when the game cannot be found."""
    if getattr(args, "source", None):
        return Path(args.source)
    try:
        from ..host.launcher import find_game_dir
        return find_game_dir(getattr(args, "game_dir", None)) / "regulation.bin"
    except (FileNotFoundError, OSError, ImportError):     # ImportError: no registry (not Windows)
        return None


def build_items(args, base: Path | None, which: str = "all", dry_run: bool = False) -> service.Report:
    """The build both `extension customize-items` and `run` do. Prints its progress; raises ExtensionError."""
    ci = extension.open_customize_items(getattr(args, "extension_dir", None), spec_file(args))
    book.d("config", f"spec: {ci.spec_path} ({describe_resource(ci.spec_path)})")
    items = ci.items(which)
    if not items:
        book.i("extension", f"customize-items: no items in {ci.spec_path}: nothing to build")
        return ci.build(items, base, dry_run)
    book.i("extension", f"customize-items: building {', '.join(i['id'] for i in items)} on {base} and checking (about 15 s)")
    rep = ci.build(items, base, dry_run)
    for w in rep.warnings:
        book.w("extension", w)
    book.ok("extension", f"customize-items: {', '.join(rep.items)} built and checked ({rep.changed_blocks} blocks re-encoded)"
                         + ("" if rep.dry_run else f" -> {rep.output}"))
    return rep


def cmd_list(args) -> int:
    ci = extension.open_customize_items(args.extension_dir, spec_file(args))
    try:
        n = len(ci.load_spec()["items"])
        text = f"{n} item{'s' if n != 1 else ''} in the spec"
    except service.ExtensionError as exc:
        n, text = 0, str(exc).splitlines()[0]
    built = ci.output_path.is_file()
    ui.result("info", f"extensions (files in {extension.data_dir(args.extension_dir)})")
    ui.fields([("customize-items", text), ("spec", f"{ci.spec_path} ({describe_resource(ci.spec_path)})"),
               ("last output", str(ci.output_path) if built else "none yet (built by `run` or `extension customize-items --add all`)")])
    return 0


def cmd_customize_items(args) -> int:
    ci = extension.open_customize_items(args.extension_dir, spec_file(args))
    if args.add is None:
        ui.fields([("spec", f"{ci.spec_path} ({describe_resource(ci.spec_path)})"), ("output", str(ci.output_path))])
        ui.out("     build with: eldendisk extension customize-items --add all")
        return 0
    try:
        rep = build_items(args, game_file(args), args.add, args.dry_run)
    except service.ExtensionError as exc:
        book.e("extension", str(exc))
        return 1
    if rep.items:
        verb = "would write" if rep.dry_run else "wrote"
        ui.fields([("sha256", rep.sha256[:16] + "…"), ("content", rep.decrypted_sha256[:16] + "…"),
                   (verb, str(rep.output)), ("next", "`eldendisk run` (vault ON) builds and swaps it in for the session"
                                                    if not rep.dry_run else "run again without --dry-run to write it")])
    return 0


def cmd_extension(args) -> int:
    if args.list:
        return cmd_list(args)
    if args.ext_name == "customize-items":
        return cmd_customize_items(args)
    ui.result("error", "give --list, or an extension name: customize-items")
    return 2

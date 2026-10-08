"""`extension --list`, `extension customize-items --add all|ID` and `extension customize-items --secure`.

customize-items reads the draft (`items.draft.json`, embedded in the exe), takes the game's own regulation.bin as the base and
builds a new one; the gate judges the file. `--secure` confirms the build you tried in the game: it is kept as
regulation.secured.bin, and `run` (vault ON) swaps that copy in without building again while the draft does not change.
Nothing is put into the game here: `run` swaps it in for the session and the vault puts the game's own file back."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .. import extension, ui
from ..extension.customize_items import service, spec as specmod
from ..logbook import book
from ..paths import describe_resource, get_resource_path

MAX_DIFF_LINES = 12


def spec_file(args) -> Path:
    """`--spec FILE`, else items.draft.json next to the exe, else the embedded copy, else the package in the source tree."""
    if getattr(args, "spec", None):
        return Path(args.spec)
    return get_resource_path(service.SPEC_FILE, default_dir=service.PKG_DIR)


def game_file(args) -> Path | None:
    """The game's regulation.bin: `--source FILE`, else the one in the game folder. None when the game cannot be found."""
    if getattr(args, "source", None):
        return Path(args.source)
    try:
        from ..host.launcher import find_game_dir
        return find_game_dir(getattr(args, "game_dir", None)) / "regulation.bin"
    except (FileNotFoundError, OSError, ImportError):     # ImportError: no registry (not Windows)
        return None


@dataclass
class Prepared:
    path: Path | None            # the regulation.bin to swap in, or None
    mode: str                    # "none" | "secured" | "built"
    report: service.Report | None = None


def _show_diff(diff: list) -> None:
    for line in diff[:MAX_DIFF_LINES]:
        book.i("ext", "  " + line)
    if len(diff) > MAX_DIFF_LINES:
        book.i("ext", f"  … and {len(diff) - MAX_DIFF_LINES} more (see the draft and {service.SECURED_FILE})")


def prepare_regulation(args, game_dir_file: Path | None, which: str = "all", dry_run: bool = False,
                       allow_secured: bool = False) -> Prepared:
    """What both `extension customize-items --add` and `run` do. Prints why, and what changed, before any long build.
    Raises ExtensionError / GateFailed. `allow_secured`: swap the secured file without building when nothing changed (`run`)."""
    ci = extension.open_customize_items(getattr(args, "extension_dir", None), spec_file(args))
    book.d("config", f"draft: {ci.spec_path} ({describe_resource(ci.spec_path)})")
    items = ci.items(which)
    if not items:
        book.i("ext", f"customize-items: no items in {ci.spec_path}: nothing to build")
        return Prepared(None, "none")
    names = ", ".join(i["id"] for i in items)
    base, base_sha = ci.read_base(game_dir_file)
    if allow_secured:
        d = ci.decide(items, base_sha)
        if d.use_secured:
            book.ok("ext", f"customize-items: {names} unchanged since it was secured: using {ci.secured_bin} (no build)")
            return Prepared(ci.secured_bin, "secured")
        for r in d.reasons:
            book.i("ext", f"customize-items: building because {r}")
        _show_diff(d.diff)
    book.i("ext", f"customize-items: building {names} on {game_dir_file} and checking (about 20 s)")
    rep = ci.build(items, base, dry_run)
    for n in rep.notes:
        book.d("ext", f"gate: {n}")
    book.ok("ext", f"customize-items: {names} built, gate passed ({rep.changed_blocks} blocks re-encoded)"
                         + ("" if rep.dry_run else f" -> {rep.output}"))
    return Prepared(rep.output if rep.built else None, "built" if rep.built else "none", rep)


def cmd_list(args) -> int:
    ci = extension.open_customize_items(args.extension_dir, spec_file(args))
    try:
        items = ci.load_spec()["items"]
        n = len(items)
        text = f"{n} item{'s' if n != 1 else ''} in the draft"
    except service.ExtensionError as exc:
        items, text = None, str(exc).splitlines()[0]
    ui.result("info", f"extensions (files in {extension.data_dir(args.extension_dir)})")
    rows = [("customize-items", text), ("draft", f"{ci.spec_path} ({describe_resource(ci.spec_path)})")]
    try:
        rec = ci.read_secured()
    except ValueError as exc:
        rec, rows_secured = None, f"unreadable ({exc}): `run` will build again"
    else:
        rows_secured = None
    if rows_secured:
        rows.append(("secured", rows_secured))
    elif rec is None:
        rows.append(("secured", "none yet: `run` builds; after you tried it in the game, close the game and run "
                                "`extension customize-items --secure`"))
    else:
        rows.append(("secured", f"{rec.get('secured_at', '?')} ({ci.secured_bin})"))
        if items is not None:
            diff = service.diff_specs(specmod.build_view(rec["spec"]),
                                      specmod.build_view({"format": specmod.FORMAT, "items": items}))
            rows.append(("draft vs secured", "same: `run` swaps the secured file, no build" if not diff
                         else f"{len(diff)} change(s): `run` builds"))
            for line in diff[:MAX_DIFF_LINES]:
                rows.append(("", line))
    rows.append(("last build", str(ci.output_path) if ci.output_path.is_file()
                 else "none yet (built by `run` or `extension customize-items --add all`)"))
    ui.fields(rows)
    return 0


def cmd_secure(args) -> int:
    ci = extension.open_customize_items(args.extension_dir, spec_file(args))
    try:
        items = ci.items("all")
        rep = ci.secure(items, game_file(args))
    except service.ExtensionError as exc:
        book.e("ext", str(exc))
        return 1
    for n in rep.notes:
        book.d("ext", f"gate: {n}")
    book.ok("ext", f"customize-items: {', '.join(rep.items)} secured -> {rep.output}")
    ui.fields([("sha256", rep.sha256[:16] + "…"), ("record", str(ci.secured_path)),
               ("next", "`eldendisk run` swaps the secured file without building while the draft does not change")])
    return 0


def cmd_customize_items(args) -> int:
    ci = extension.open_customize_items(args.extension_dir, spec_file(args))
    if args.secure:
        return cmd_secure(args)
    if args.add is None:
        ui.fields([("draft", f"{ci.spec_path} ({describe_resource(ci.spec_path)})"), ("build", str(ci.output_path)),
                   ("secured", str(ci.secured_bin))])
        ui.out("     build with: eldendisk extension customize-items --add all")
        ui.out("     after you tried it in the game (game closed): eldendisk extension customize-items --secure")
        return 0
    try:
        prep = prepare_regulation(args, game_file(args), args.add, args.dry_run)
    except service.ExtensionError as exc:      # includes GateFailed
        book.e("ext", str(exc))
        return 1
    rep = prep.report
    if rep is not None and rep.items:
        verb = "would write" if rep.dry_run else "wrote"
        ui.fields([("sha256", rep.sha256[:16] + "…"), ("content", rep.decrypted_sha256[:16] + "…"),
                   (verb, str(rep.output)), ("next", "`eldendisk run` (vault ON) swaps it in for the session; when it works in the game, "
                                                    "close the game and run `extension customize-items --secure`"
                                                    if not rep.dry_run else "run again without --dry-run to write it")])
    return 0


def cmd_extension(args) -> int:
    if args.list:
        return cmd_list(args)
    if args.ext_name == "customize-items":
        return cmd_customize_items(args)
    ui.result("error", "give --list, or an extension name: customize-items")
    return 2

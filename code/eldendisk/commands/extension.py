"""`extension --list`, `extension innovate-items spells --add all|PATH ...` and `extension innovate-items spells --secure`.

innovate-items spells reads the design (`extension.json`, embedded in the exe), takes the game's own regulation.bin as the base and
builds a new one; the gate judges the file. `--secure` confirms the build you tried in the game: it is kept as
regulation.secured.bin, and `run` (vault ON) swaps that copy in without building again while the design does not change.
`--add` also chooses WHICH spells later builds hold: `--add spells.slots.<id> ...` builds those only and `run` goes on building the
same selection (and reuses the build while nothing changed) until `--add all` or another `--add` changes it; without any `--add`
every spell is built. The choice is kept in the build record (`spells.build.json`).
Nothing is put into the game here: `run` swaps it in for the session and the vault puts the game's own file back."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .. import extension, ui
from ..extension.innovate_items.spells import service, spec as specmod
from ..logbook import book
from ..vault import VaultError, resolve_vault
from ..paths import describe_resource, get_resource_path

MAX_DIFF_LINES = 12


def spec_file(args) -> Path:
    """`--spec FILE`, else extension.json next to the exe, else the embedded copy, else code/ in the source tree."""
    if getattr(args, "spec", None):
        return Path(args.spec)
    return get_resource_path(service.SPEC_FILE, default_dir=service.CODE_DIR)


def ext_dir(args, vault_dir: Path | str | None = None) -> Path:
    """Where the extensions keep their files: `--extension-dir`, else `<vault>/extension`. The vault is the one the other commands
    use (`--vault`, else the one remembered in the Registry, else the default); `run` passes the one it already resolved."""
    if vault_dir is None and not getattr(args, "extension_dir", None):
        try:
            vault_dir = resolve_vault(getattr(args, "vault", None))
        except VaultError as exc:
            raise service.ExtensionError(str(exc))
    return extension.data_dir(getattr(args, "extension_dir", None), vault_dir or "")


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
    mode: str                    # "none" | "secured" | "last" (the latest build, unchanged) | "built"
    report: service.Report | None = None


def _show_diff(diff: list) -> None:
    for line in diff[:MAX_DIFF_LINES]:
        book.i("ext", "  " + line)
    if len(diff) > MAX_DIFF_LINES:
        book.i("ext", f"  … and {len(diff) - MAX_DIFF_LINES} more (see the design and {service.SECURED_FILE})")


def prepare_regulation(args, game_dir_file: Path | None, which=None, dry_run: bool = False,
                       allow_secured: bool = False, vault_dir: Path | str | None = None) -> Prepared:
    """What both `extension innovate-items spells --add` and `run` do. Prints why, and what changed, before any long build.
    Raises ExtensionError / GateFailed. `which`: what `--add` was given (a list of `all` / spell paths) or None for `run`, which
    builds the selection the last `--add` made (every spell when there was none). `allow_secured` (`run`): swap the secured
    file, or the latest build, without building when nothing changed."""
    ci = extension.open_spells(ext_dir(args, vault_dir), spec_file(args))
    book.d("config", f"design: {ci.spec_path} ({describe_resource(ci.spec_path)})")
    chosen = which is not None
    if chosen:
        try:
            sel = specmod.selection_of(which)
        except specmod.SpecError as e:
            raise service.ExtensionError("; ".join(e.problems))
    else:
        sel, note = ci.selection()
        if note:
            book.w("ext", f"innovate-items spells: {note}")
    spells = ci.items(sel)
    if sel != "all":
        sel = [i["id"] for i in spells]            # slot order, so the same choice is always written the same way
    ui.mark_spell_ids(i["id"] for i in spells)
    if not spells:
        book.i("ext", f"innovate-items spells: no spells in {ci.spec_path}: nothing to build")
        return Prepared(None, "none")
    names = ", ".join(i["id"] for i in spells)
    if sel != "all":
        left = [i["id"] for i in ci.items("all") if i["id"] not in sel]
        book.i("ext", f"innovate-items spells: building only {names}"
               + (" (chosen with the last --add; `--add all` builds every spell)" if not chosen else "")
               + (f"; left out: {', '.join(left)}" if left else ""))
    base, base_sha = ci.read_base(game_dir_file)
    if allow_secured:
        d = ci.decide(spells, base_sha)
        if d.use_secured:
            book.ok("ext", f"innovate-items spells: {names} unchanged since it was secured: using {ci.secured_bin} (no build)")
            return Prepared(ci.secured_bin, "secured")
        last = ci.decide_last(spells, sel, base_sha)
        if last.use_secured:
            book.ok("ext", f"innovate-items spells: {names} unchanged since the last build: using {ci.output_path} (no build; "
                           "not secured yet)")
            return Prepared(ci.output_path, "last")
        for r in d.reasons + [r for r in last.reasons if r != "no build yet"]:
            book.i("ext", f"innovate-items spells: building because {r}")
        _show_diff(d.diff or last.diff)
    book.i("ext", f"innovate-items spells: building {names} on {game_dir_file} and checking (about 20 s)")
    rep = ci.build(spells, base, dry_run, selection=sel)
    for n in rep.notes:
        book.d("ext", f"gate: {n}")
    book.ok("ext", f"innovate-items spells: {names} built, gate passed ({rep.changed_blocks} blocks re-encoded)"
                         + ("" if rep.dry_run else f" -> {rep.output}"))
    return Prepared(rep.output if rep.built else None, "built" if rep.built else "none", rep)


def cmd_list(args) -> int:
    ci = extension.open_spells(ext_dir(args), spec_file(args))
    try:
        spells = ci.load_spec()["spells"]
        n = len(spells)
        text = f"{n} spell{'s' if n != 1 else ''} in the design"
    except service.ExtensionError as exc:
        spells, text = None, str(exc).splitlines()[0]
    ui.result("info", f"extensions (files in {ext_dir(args)})")
    rows = [("innovate-items spells", text), ("design", f"{ci.spec_path} ({describe_resource(ci.spec_path)})")]
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
                                "`extension innovate-items spells --secure`"))
    else:
        rows.append(("secured", f"{rec.get('committed_at', '?')} ({ci.secured_bin})"))
        if spells is not None:
            diff = service.diff_specs(specmod.build_view(rec["spec"]),
                                      specmod.build_view({"format": specmod.FORMAT, "spells": spells}))
            rows.append(("design vs secured", "same: `run` swaps the secured file, no build" if not diff
                         else f"{len(diff)} change(s): `run` builds"))
            for line in diff[:MAX_DIFF_LINES]:
                rows.append(("", line))
    sel, note = ci.selection()
    rows.append(("selection", note or ("every spell (no --add yet, or the last was `--add all`)" if sel == "all" else
                                       f"{', '.join(sel)} (chosen with --add; `run` builds only these; `--add all` builds every spell)")))
    rows.append(("last build", str(ci.output_path) if ci.output_path.is_file()
                 else "none yet (built by `run` or `extension innovate-items spells --add all`)"))
    ui.fields(rows)
    return 0


def cmd_secure(args) -> int:
    ci = extension.open_spells(ext_dir(args), spec_file(args))
    try:
        sel, note = ci.selection()                      # the build holds the spells of the last --add: that is what is checked and kept
        if note:
            book.w("ext", f"innovate-items spells: {note}")
        spells = ci.items(sel)
        ui.mark_spell_ids(i["id"] for i in spells)
        rep = ci.secure(spells, game_file(args))
    except service.ExtensionError as exc:
        book.e("ext", str(exc))
        return 1
    for n in rep.notes:
        book.d("ext", f"gate: {n}")
    book.ok("ext", f"innovate-items spells: {', '.join(rep.spells)} secured -> {rep.output}")
    ui.fields([("sha256", rep.sha256[:16] + "…"), ("record", str(ci.secured_path)),
               ("next", "`eldendisk run` swaps the secured file without building while the design does not change")])
    return 0


def cmd_spells(args) -> int:
    ci = extension.open_spells(ext_dir(args), spec_file(args))
    if args.secure:
        return cmd_secure(args)
    if args.add is None:
        ui.fields([("design", f"{ci.spec_path} ({describe_resource(ci.spec_path)})"), ("build", str(ci.output_path)),
                   ("secured", str(ci.secured_bin))])
        sel, _note = ci.selection()
        ui.out("     build with: eldendisk extension innovate-items spells --add all   (or --add spells.slots.<id> [spells.slots.<id> ...])")
        ui.out("     selection now: " + ("every spell" if sel == "all" else f"{', '.join(sel)} (`run` builds only these)"))
        ui.out("     after you tried it in the game (game closed): eldendisk extension innovate-items spells --secure")
        return 0
    try:
        prep = prepare_regulation(args, game_file(args), args.add, args.dry_run)
    except service.ExtensionError as exc:      # includes GateFailed
        book.e("ext", str(exc))
        return 1
    rep = prep.report
    if rep is not None and rep.spells:
        verb = "would write" if rep.dry_run else "wrote"
        ui.fields([("sha256", rep.sha256[:16] + "…"), ("content", rep.decrypted_sha256[:16] + "…"),
                   (verb, str(rep.output)), ("next", "`eldendisk run` (vault ON) swaps it in for the session; when it works in the game, "
                                                    "close the game and run `extension innovate-items spells --secure`"
                                                    if not rep.dry_run else "run again without --dry-run to write it")])
    return 0


def cmd_extension(args) -> int:
    try:
        if args.list:
            return cmd_list(args)
        if args.ext_name == "innovate-items" and getattr(args, "items_kind", None) == "spells":
            return cmd_spells(args)
    except service.ExtensionError as exc:      # includes a vault that cannot be found (ext_dir)
        book.e("ext", str(exc))
        return 1
    ui.result("error", "give --list, or an extension and a kind: innovate-items spells")
    return 2

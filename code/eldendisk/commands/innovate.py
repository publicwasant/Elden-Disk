"""`innovate-spells [build | secure | apply]` (1.8.0 part 2; `innovate-items spells --add | --secure` and `write --text | --flame-color`
before): new spells for the game, made outside the game.

    innovate-spells                              the spells of creative.json with their ids, built or secured
    innovate-spells build [* | all | NAME | ID ...] [--dry-run] [--source FILE]
                                                 build a regulation.bin with them; the gate judges the file
    innovate-spells secure                       after you tried the build in the game (game closed): keep it as regulation.secured.bin
    innovate-spells apply [--when-loaded]        put the spells' texts and colours into the running game (memory only)

`build` reads creative.json (section `innovate_spells`; the exe embeds a copy), takes the game's own regulation.bin as the base and builds
a new one; the gate judges the file. `secure` confirms the build you tried in the game: it is kept as regulation.secured.bin, and `run`
(vault ON) swaps that copy in without building again while the spells do not change. `build NAME ...` also chooses WHICH spells later
builds hold: `run` goes on building the same selection (and reuses the build while nothing changed) until `build` (every spell) or
another selection changes it. The choice is kept in the build record (`spells.build.json`). A spell is named by the key of its slot in
creative.json (NAME) or by its goods id in the game (ID: 2230000 + slot - 1).
Nothing is put into the game files here: `run` swaps the build in for the session and the vault puts the game's own file back."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .. import creative, ui
from ..creative.innovate_spells import recipes, service, spec as specmod
from ..logbook import CREATIVE_TAG, book
from ..vault import VaultError, resolve_vault
from ..paths import describe_resource, get_resource_path
from .common import log_config

MAX_DIFF_LINES = 12
TITLE = "creative · innovate-spells"


def spec_file(args) -> Path:
    """`--spec FILE`, else creative.json next to the exe, else the embedded copy, else code/ in the source tree."""
    if getattr(args, "spec", None):
        return Path(args.spec)
    return get_resource_path(service.SPEC_FILE, default_dir=service.CODE_DIR)


def creative_folder(args, vault_dir: Path | str | None = None) -> Path:
    """Where the creative features keep their files: `--creative-dir`, else `<vault>/creative`. The vault is the one the other commands
    use (`--vault`, else the one remembered in the Registry, else the default); `run` passes the one it already resolved."""
    if vault_dir is None and not getattr(args, "creative_dir", None):
        try:
            vault_dir = resolve_vault(getattr(args, "vault", None))
        except VaultError as exc:
            raise service.CreativeError(str(exc))
    if not getattr(args, "creative_dir", None) and vault_dir:
        _moved_to_creative(Path(vault_dir))
    folder = creative.data_dir(getattr(args, "creative_dir", None), vault_dir or "")
    _moved_spells(folder)
    return folder


def _rename(old: Path, new: Path, why: str) -> None:
    try:
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)
        book.i(CREATIVE_TAG, f"{old} renamed to {new} ({why})")
    except OSError as exc:          # another step of `run` did it at the same moment, or the folder is in use
        if not new.exists():
            book.w(CREATIVE_TAG, f"could not rename {old} to {new} ({exc}); the files are looked for in {new}")


def _moved_to_creative(vault_dir: Path) -> None:
    """1.8.0 renamed `<vault>/extension` (1.7.2), then `<vault>/design`, to `<vault>/creative`: the folder of an older vault is renamed once
    (the builds, the secured file and the scripts' status keep working). Nothing happens when the new folder exists already."""
    new = vault_dir / creative.SUBDIR
    if new.exists():
        return
    for name in creative.OLD_SUBDIRS:
        old = vault_dir / name
        if old.is_dir():
            _rename(old, new, f"1.8.0: `{name}` is `creative` now")
            return


def _moved_spells(folder: Path) -> None:
    """`<creative>/innovate-items/spells` (before 1.8.0) is `<creative>/innovate-spells` now: moved once."""
    old, new = folder / service.OLD_NAME, folder / service.NAME
    if not old.is_dir() or new.exists():
        return
    _rename(old, new, "1.8.0: `innovate-items spells` is `innovate-spells` now")
    try:
        old.parent.rmdir()              # innovate-items, when it is empty now
    except OSError:
        pass


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
    """What changed since the last build, as a small tree under the line that says why the build happens."""
    shown = diff[:MAX_DIFF_LINES]
    more = len(diff) - len(shown)
    for n, line in enumerate(shown):
        book.i(CREATIVE_TAG, ("  └─ " if n == len(shown) - 1 and not more else "  ├─ ") + line)
    if more > 0:
        book.i(CREATIVE_TAG, f"  └─ … and {more} more (see creative.json and {service.SECURED_FILE})")


def _colour_text(rgb, color: bool) -> str:
    shown = specmod.colour_text(rgb)
    return f"{ui.swatch(rgb, color)} " + (shown if isinstance(shown, str) else " ".join(f"{c:g}" for c in rgb))


def _facts(s: dict, rows: dict | None = None, color: bool = False) -> list[tuple[str, str]]:
    """What a spell holds that is worth a glance, for its rows in the block: only what creative.json says, in its words (status, cost,
    sold at, fire, eyes), and the ids the game really uses (`rows`: recipes.spell_rows) once it is built. `color`: a little square in
    each colour."""
    out = []
    text = s.get("text") or {}
    if text.get("goods_name"):
        out.append(("name", text["goods_name"]))
    need = [f"{k} {v}" for k, v in (s.get("requires") or {}).items() if v]
    if need:
        out.append(("status", " · ".join(need)))
    cost = ([f"focus point {s['fp_cost']}"] if s.get("fp_cost") is not None else []) + ([f"stamina {s['stamina_cost']}"] if s.get("stamina_cost") else [])
    if cost:
        out.append(("cost", " · ".join(cost)))
    shop = s.get("shop")
    if shop:
        out.append(("sold", f"Kalé · {shop.get('price')} runes" + (f", stock {shop['stock']}" if shop.get("stock") is not None else "")))
    if s.get("flame_color"):
        fire = _colour_text(s["flame_color"], color)
        if s.get("flame_accent_color"):
            fire += "   accent " + _colour_text(s["flame_accent_color"], color)
        out.append(("fire", fire))
    if "positive_curse_energy_eyes" in s:
        eyes = s["positive_curse_energy_eyes"]
        out.append(("eyes", _colour_text(eyes["color"], color) if "color" in eyes else "the game's own"))
    if rows:
        ids = [f"goods {rows['goods']}", f"magic {rows['magic']}"]
        if rows.get("sp_effect"):
            ids.append("SpEffect " + ", ".join(map(str, rows["sp_effect"])))
        for key, label in (("bullet", "Bullet"), ("atk", "AtkParam_Pc")):
            if rows.get(key):
                ids.append(f"{label} " + ", ".join(map(str, rows[key])))
        if rows.get("shop"):
            ids.append(f"shop line {rows['shop']}")
        out.append(("game", " · ".join(ids)))
    out.append(("slot", str(s.get("slot"))))
    return out


def _spell_rows(blk, spells: list, rows: dict) -> None:
    """The spells of the build in the block: one line each (id, slot, kind) and what creative.json says under it."""
    color = ui.use_color(blk.stream)
    for sp in spells:
        kind = sp.get("kind", "buff")
        head = f"{sp['id']}  slot {sp['slot']} · {kind}" + (f" of {sp['from']}" if "from" in sp else "")
        blk.note(head)
        blk.rows([r for r in _facts(sp, rows.get(sp["id"]), color) if r[0] != "slot"])


def _show_error(exc: Exception) -> None:
    """The lines of an error (a creative.json that is not valid, a gate that failed) inside the block, one by one; the command does not
    say them again (`exc.shown`)."""
    for line in str(exc).splitlines() or [""]:
        book.e(CREATIVE_TAG, line)
    exc.shown = True


def say_error(exc: Exception, tag: str = CREATIVE_TAG) -> None:
    """For the caller of prepare_regulation: say the error unless the block already did."""
    if not getattr(exc, "shown", False):
        book.e(tag, str(exc))


def prepare_regulation(args, game_dir_file: Path | None, which=None, dry_run: bool = False,
                       allow_secured: bool = False, vault_dir: Path | str | None = None, summary: bool = False) -> Prepared:
    """What both `innovate-spells build` and `run` do, in one block on the console: why the build happens, what changed in the spells,
    the build and the gate, then the spells with the ids the game really uses. Raises CreativeError / GateFailed (their lines are in the
    block already: `exc.shown`). `which`: what `build` was given (a list of `all` / spell names) or None for `run`, which builds the
    selection the last `build` made (every spell when there was none). `allow_secured` (`run`): swap the secured file, or the latest
    build, without building when nothing changed. `summary`: the hashes and what to do next in the block."""
    ci = creative.open_spells(creative_folder(args, vault_dir), spec_file(args))
    log_config("creative", ci.spec_path)
    with ui.block(TITLE, verbose=getattr(args, "verbose", False)) as blk:
        try:
            return _prepare(args, ci, blk, game_dir_file, which, dry_run, allow_secured, summary)
        except service.CreativeError as exc:      # includes GateFailed
            _show_error(exc)
            raise


def _prepare(args, ci, blk, game_dir_file, which, dry_run, allow_secured, summary) -> Prepared:
    chosen = which is not None
    if chosen:
        try:
            sel = specmod.selection_of(which)
        except specmod.SpecError as e:
            raise service.CreativeError("; ".join(e.problems))
    else:
        sel, note = ci.selection()
        if note:
            book.w(CREATIVE_TAG, note)
    spells = ci.items(sel)
    if sel != "all":
        sel = [i["id"] for i in spells]            # slot order, so the same choice is always written the same way
    ui.mark_spell_ids(i["id"] for i in spells)
    if not spells:
        book.i(CREATIVE_TAG, f"no spells in {ci.spec_path}: nothing to build")
        blk.close("nothing to build", "info")
        return Prepared(None, "none")
    names = ", ".join(i["id"] for i in spells)
    if sel != "all":
        left = [i["id"] for i in ci.items("all") if i["id"] not in sel]
        book.i(CREATIVE_TAG, f"building only {names}"
               + (" (chosen with the last `innovate-spells build`; `build all` builds every spell)" if not chosen else "")
               + (f"; left out: {', '.join(left)}" if left else ""))
    base, base_sha = ci.read_base(game_dir_file)
    if allow_secured:
        d = ci.decide(spells, base_sha)
        last = ci.decide_last(spells, sel, base_sha)
        if (d.use_secured or last.use_secured) and ci.refresh_designs(spells):   # the texts and colours as they are now (not built)
            book.d(CREATIVE_TAG, "spells.resolved.json: the design's texts and colours written as they are now")
        if d.use_secured:
            book.ok(CREATIVE_TAG, f"{names} unchanged since it was secured: using {ci.secured_bin} (no build)")
            blk.close("no build", "ok")
            return Prepared(ci.secured_bin, "secured")
        if last.use_secured:
            book.ok(CREATIVE_TAG, f"{names} unchanged since the last build: using {ci.output_path} (no build; not secured yet)")
            blk.close("no build", "ok")
            return Prepared(ci.output_path, "last")
        for r in d.reasons + [r for r in last.reasons if r != "no build yet"]:
            book.i(CREATIVE_TAG, f"building because {r}")
        _show_diff(d.diff or last.diff)
    with ui.working(CREATIVE_TAG, f"building {names} on {game_dir_file} and checking", short=f"building {names}") as step:
        rep = ci.build(spells, base, dry_run, selection=sel)
        for n in rep.notes:
            book.d(CREATIVE_TAG, f"gate: {n}")
        step.done(f"{names} built, gate passed ({rep.changed_blocks} blocks re-encoded)")
    _spell_rows(blk, spells, rep.rows)
    if summary and rep.spells:
        _summary(blk, rep)
    blk.close("dry run: nothing written" if rep.dry_run else f"wrote {rep.output}", "ok")
    return Prepared(rep.output if rep.built else None, "built" if rep.built else "none", rep)


def _summary(blk, rep: service.Report) -> None:
    """The hashes of the file and what to do next: under the spells in the block (on `-v`, where there is no block, as before)."""
    verb = "would write" if rep.dry_run else "wrote"
    rows = [("sha256", rep.sha256[:16] + "…"), ("content", rep.decrypted_sha256[:16] + "…"), (verb, str(rep.output)),
            ("next", "`eldendisk run` (vault ON) swaps it in for the session; when it works in the game, close the game and run "
                     "`innovate-spells secure`" if not rep.dry_run else "run again without --dry-run to write it")]
    if blk.active:
        blk.rows(rows)
    else:
        ui.fields(rows)


def cmd_list(args) -> int:
    """`innovate-spells`: the spells of creative.json with their ids, and what is built and secured."""
    ci = creative.open_spells(creative_folder(args), spec_file(args))
    try:
        spells = ci.load_spec()["spells"]
    except service.CreativeError as exc:
        say_error(exc)
        return 1
    ui.result("info", f"innovate-spells: {len(spells)} spell{'s' if len(spells) != 1 else ''} in {ci.spec_path} "
                      f"({describe_resource(ci.spec_path)}); files in {ci.dir}")
    sel, note = ci.selection()
    resolved = (ci.read_resolved() or {}).get("spells", {})
    built = {r.get("id"): goods for goods, r in resolved.items() if isinstance(r, dict)}
    rows = []
    for s in spells:
        goods = recipes.ITEM_BASE + s["slot"] - 1
        where = "built" if s["id"] in built else ("left out of the build" if sel != "all" and s["id"] not in sel else "not built yet")
        name = (s.get("text") or {}).get("goods_name")
        rows.append((s["id"], f"id {goods} · slot {s['slot']} · {s.get('kind', 'buff')}" + (f" of {s['from']}" if "from" in s else "")
                     + (f" · {name}" if name else "") + f" · {where}"))
    try:
        rec = ci.read_secured()
    except ValueError as exc:
        rows.append(("secured", f"unreadable ({exc}): `run` will build again"))
    else:
        if rec is None:
            rows.append(("secured", "none yet: `run` builds; after you tried it in the game, close the game and run `innovate-spells secure`"))
        else:
            diff = service.diff_specs(specmod.design_view(rec["spec"]), specmod.design_view({"format": specmod.FORMAT, "spells": spells}))
            rows.append(("secured", f"{rec.get('committed_at', '?')} ({ci.secured_bin}): "
                         + ("the same: `run` swaps it, no build" if not diff else f"{len(diff)} change(s) since: `run` builds")))
            for line in diff[:MAX_DIFF_LINES]:
                rows.append(("", line))
    rows.append(("selection", note or ("every spell" if sel == "all" else f"{', '.join(sel)} (`run` builds only these; `build all` builds every spell)")))
    rows.append(("last build", str(ci.output_path) if ci.output_path.is_file() else "none yet (`run`, or `innovate-spells build`)"))
    ui.fields(rows)
    return 0


def cmd_secure(args) -> int:
    ci = creative.open_spells(creative_folder(args), spec_file(args))
    with ui.block(TITLE + " · secure", verbose=getattr(args, "verbose", False)) as blk:
        try:
            sel, note = ci.selection()                  # the build holds the spells of the last `build`: that is what is checked and kept
            if note:
                book.w(CREATIVE_TAG, note)
            spells = ci.items(sel)
            ui.mark_spell_ids(i["id"] for i in spells)
            rep = ci.secure(spells, game_file(args))
        except service.CreativeError as exc:
            _show_error(exc)
            blk.close("not secured", "error")
            return 1
        for n in rep.notes:
            book.d(CREATIVE_TAG, f"gate: {n}")
        book.ok(CREATIVE_TAG, f"{', '.join(rep.spells)} secured -> {rep.output}")
        rows = [("sha256", rep.sha256[:16] + "…"), ("record", str(ci.secured_path)),
                ("next", "`eldendisk run` swaps the secured file without building while the spells do not change")]
        if blk.active:
            blk.rows(rows)
        else:
            ui.fields(rows)
        blk.close("secured", "ok")
    return 0


def which_of(ci, words: list[str]) -> list[str]:
    """`build` words -> what selection_of takes: ["all"] for nothing / `*` / `all`; a goods id (2230000 + slot - 1) -> the name of the
    spell in that slot; `creative.innovate_spells.<goods id>` the same; a name as it is."""
    words = [w.strip() for w in words if w.strip()]
    if not words or any(w in ("*", "all") for w in words):
        if len(words) > 1:
            raise service.CreativeError("`*` and `all` stand alone: they build every spell")
        return ["all"]
    by_slot = {s["slot"]: s["id"] for s in ci.items("all")}
    out = []
    for w in words:
        key = w
        low = w.lower()
        if low.startswith("creative.innovate_spells."):
            key = w.split(".", 2)[2]
        if key.isdigit():
            slot = int(key) - recipes.ITEM_BASE + 1
            if slot not in by_slot:
                raise service.CreativeError(f"{w}: no spell has that id (the ids: "
                                            + ", ".join(f"{recipes.ITEM_BASE + s - 1} {i}" for s, i in sorted(by_slot.items())) + ")")
            key = by_slot[slot]
        out.append(key)
    return out


def cmd_build(args) -> int:
    ci = creative.open_spells(creative_folder(args), spec_file(args))
    try:
        which = which_of(ci, list(getattr(args, "names", None) or []))
        prepare_regulation(args, game_file(args), which, getattr(args, "dry_run", False), summary=True)
    except service.CreativeError as exc:      # includes GateFailed
        say_error(exc)
        return 1
    return 0


def cmd_apply(args) -> int:
    """`innovate-spells apply [--when-loaded]`: the spells' texts, then their colours, into the running game (memory only)."""
    from .write import cmd_apply_both
    from .run import creative_has_flame, creative_has_text
    try:
        vault = resolve_vault(getattr(args, "vault", None))
    except VaultError as exc:
        book.e("write", str(exc))
        return 5
    texts, colours = creative_has_text(args, vault), creative_has_flame(args, vault)
    if not (texts or colours):
        book.i(CREATIVE_TAG, "innovate-spells: no spell of the build has a text or a colour: nothing to apply")
        return 0
    return cmd_apply_both(args, texts, colours)     # one attach for both (1.8.0 part 3)


FUNCTIONS = {"build": cmd_build, "secure": cmd_secure, "apply": cmd_apply}


def cmd_innovate(args) -> int:
    """`innovate-spells [build | secure | apply]`."""
    fn = getattr(args, "function", None)
    names = list(getattr(args, "names", None) or [])
    try:
        if fn is None:
            return cmd_list(args)
        if fn not in FUNCTIONS:
            book.e(CREATIVE_TAG, f"unknown function {fn!r}: innovate-spells [build | secure | apply]")
            return 2
        if names and fn != "build":
            book.e(CREATIVE_TAG, f"`innovate-spells {fn}` takes no names (it works on the spells of the last build)")
            return 2
        return FUNCTIONS[fn](args)
    except service.CreativeError as exc:      # includes a vault that cannot be found (creative_folder)
        say_error(exc)
        return 1

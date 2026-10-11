"""`write --set NAME=VALUE... --refill LIST --reset NAME...`: apply edits once to the running game, inside an authorised
session. Names under `params.` edit the game's own tables (and `--reset` puts the game's own values back).

`write --text [--wait [SEC]]` (1.7.1) puts the text of the design's spells (name, short line, long description) into the running
game: it rebuilds the game's three text tables and switches the game to them (writer/text.py). `run` starts it by itself after the
game is up. Needs the same authorised session; the text lasts until the game closes."""
from __future__ import annotations

import time
from pathlib import Path

from ..console import require_windows_x64
from ..logbook import book
from ..extension.innovate_items.fmg import Fmg, FmgError
from ..game.attach import EXIT_ERROR, EXIT_NO_SESSION, EXIT_UNSUPPORTED, AttachError, Target, locate
from ..game.layout import Layout
from ..game.params import ParamLockedError, ParamNameError
from ..game.processes import process_started
from ..vault import VaultError, authorise, resolve_vault
from ..vault import session as vault_session
from ..writer.paramedit import SNAPSHOT_NAME, Snapshot
from ..writer import text as wtext
from ..writer.writer import MemoryWriter, WritableProcessMemory, WriteGate, parse_policy, plan_params
from .extension import ext_dir, spec_file
from .. import extension
from ..extension.innovate_items.spells.service import ExtensionError

TEXT_TABLES = {"GoodsName": "goods_name", "GoodsInfo": "goods_info", "GoodsCaption": "goods_captions"}   # game table -> field of `text`
WAIT_DEFAULT = 300.0        # seconds `--wait` waits for the game to have loaded its text
POLL, SETTLE = 1.0, 3.0     # seconds between looks; seconds to see that the game kept the new tables
_sleep, _clock = time.sleep, time.monotonic      # tests replace these


def new_table(old: wtext.Table, rows: dict) -> bytes | None:
    """The game's table `old` with `rows` (goods id -> text) in it, in its file form; an empty text takes the id out. None when the
    result says what `old` says already (so nothing is allocated and nothing is switched). Raises FmgError."""
    fmg = Fmg.read(old.data)
    before = dict(fmg.entries)
    for gid, text in rows.items():
        if text:
            fmg.entries[gid] = text
        else:
            fmg.entries.pop(gid, None)
    return None if fmg.entries == before else fmg.write()


def _find_tables(mem, target: Target, wait: float):
    """The three tables, or None. With `wait` it keeps looking until it sees the same tables twice in a row (the game fills its text
    while it starts), up to `wait` seconds."""
    seen, t0 = None, _clock()
    while True:
        found = {n: wtext.locate(mem, target.base, target.profile.text, n) for n in TEXT_TABLES}
        if all(found.values()):
            key = {n: (t.base, len(t.data)) for n, t in found.items()}
            if wait <= 0 or key == seen:
                return found
            seen = key
        else:
            seen = None
        if wait <= 0 or _clock() - t0 >= wait:
            return None
        _sleep(POLL)


def _put_text(mem, gate, target: Target, texts: dict, wait: float) -> int:
    after: dict[str, bytes] = {}
    for attempt in (1, 2):
        found = _find_tables(mem, target, wait)
        if found is None:
            book.e("write", "the game's text tables were not found" + (f" within {wait:g} s" if wait > 0 else "")
                   + ": the game is still starting (use --wait), or it is not the version offsets.json describes")
            return 1
        for name, field in TEXT_TABLES.items():
            old = found[name]
            try:
                new = new_table(old, {gid: t[field] for gid, t in texts.items()})
                if new is None:
                    after[name] = old.data
                    book.d("write", f"text {name}: already as the design says")
                    continue
                base = wtext.swap(mem, gate, old, new)
            except (FmgError, wtext.TextError) as exc:
                book.e("write", f"text {name}: {exc}")
                return 1
            after[name] = new
            book.d("write", f"text {name}: {len(old.data)} -> {len(new)} bytes, now at {base:#x}")
        if wait <= 0:
            break
        _sleep(SETTLE)
        kept = {n: wtext.locate(mem, target.base, target.profile.text, n) for n in TEXT_TABLES}
        if all(t is not None and t.data == after[n] for n, t in kept.items()):
            break
        if attempt == 2:
            book.e("write", "the game replaced its text tables again after they were set; run `eldendisk write --text` again")
            return 1
        book.w("write", "the game replaced its text tables after they were set (it was still loading); setting them once more")
    shown = sum(1 for t in texts.values() if any(t.values()))
    book.ok("write", f"text: {shown} spell{'s' if shown != 1 else ''} named in the game (name, short line, description); "
                     "it lasts until the game closes")
    return 0


def cmd_write_text(args) -> int:
    """`write --text [--wait [SEC]]`: see the module text."""
    require_windows_x64()
    wait = float(getattr(args, "wait", 0) or 0)
    try:
        ci = extension.open_spells(ext_dir(args), spec_file(args))
        sel, note = ci.selection()          # the spells the build holds: the last `--add` chose them
        if note:
            book.w("write", f"innovate-items spells: {note}")
        texts = ci.texts(sel)
    except ExtensionError as exc:
        book.e("write", str(exc))
        return 1
    try:
        vault_root = resolve_vault(args.vault)
        record = vault_session.load(vault_root)
    except VaultError as exc:
        book.e("write", str(exc))
        return EXIT_NO_SESSION
    t0 = _clock()
    while True:
        try:
            target: Target = locate(Path(args.offsets))
            break
        except AttachError as exc:     # the game may still be starting (its modules cannot be listed yet): with --wait, look again
            if wait <= 0 or exc.code != EXIT_ERROR or "not running" in str(exc) or _clock() - t0 >= wait:
                book.e("write", str(exc))
                return exc.code
            _sleep(POLL)
    if target.profile.text is None or not set(TEXT_TABLES) <= set(target.profile.text.files):
        book.e("write", "this game version has no `text` block (rva, array, files GoodsName GoodsInfo GoodsCaption) in offsets.json")
        return EXIT_UNSUPPORTED
    problems = authorise(record, game_pid=target.pid, game_started=target.started,
                         exe_sha256=target.sha256, started_of=process_started)
    if problems:
        book.e("write", "refused, no edit was made:")
        for p in problems:
            book.e("write", f"  {p}")
        return EXIT_NO_SESSION
    mem = WritableProcessMemory(target.pid)
    try:
        gate = WriteGate()
        gate.open()   # only after the session, anti-cheat and profile checks above
        return _put_text(mem, gate, target, texts, wait)
    finally:
        mem.close()


def cmd_write(args) -> int:
    if getattr(args, "text", False):
        return cmd_write_text(args)
    require_windows_x64()
    try:
        policy = parse_policy(args.set, args.refill, getattr(args, "reset", None))
    except ValueError as exc:   # unknown or unsettable name, bad value
        book.e("write", str(exc))
        return 1
    if policy.empty:
        book.i("write", "nothing to do")
        return 0

    try:
        vault_root = resolve_vault(args.vault)
        record = vault_session.load(vault_root)
    except VaultError as exc:
        book.e("write", str(exc))
        return EXIT_NO_SESSION
    try:
        target: Target = locate(Path(args.offsets))
    except AttachError as exc:
        book.e("write", str(exc))
        return exc.code

    snapshot = Snapshot(vault_root / SNAPSHOT_NAME, target.pid, target.started)    # the game's own values, for --reset
    snapshot.load()
    try:   # what the params names mean needs the profile; a read-only field is refused before the session is looked at
        policy, notes = plan_params(target.profile.params, policy, snapshot)
    except ParamLockedError as exc:
        book.e("write", f"{exc}; nothing was written")
        return EXIT_UNSUPPORTED
    except ParamNameError as exc:
        book.e("write", f"{exc}; nothing was written")
        return 1
    for note in notes:
        book.i("write", note)

    problems = authorise(record, game_pid=target.pid, game_started=target.started,
                         exe_sha256=target.sha256, started_of=process_started)
    if problems:
        book.e("write", "refused, no edit was made:")
        for p in problems:
            book.e("write", f"  {p}")
        return EXIT_NO_SESSION

    mem = WritableProcessMemory(target.pid)
    try:
        gate = WriteGate()
        gate.open()   # only after the session, anti-cheat and profile checks above
        writer = MemoryWriter(mem, Layout(mem, target.profile, target.base), policy, gate,
                              log=lambda m: book.d("write", m), snapshot=snapshot)
        results = writer.apply_once()
    finally:
        mem.close()
        try:
            snapshot.save()
        except OSError as exc:
            book.w("write", f"could not save {SNAPSHOT_NAME} ({exc}); --reset of these values will not find the game's own value")

    failed = [r.name for r in results if not r.wrote]
    for r in results:
        if r.wrote:
            book.ok("write", f"{r.name} = {r.value}" + (f"  ({r.note})" if r.note else ""))
    if writer.skipped or failed:
        for why in writer.skipped:
            book.e("write", f"not applied: {why}")
        if failed:
            book.e("write", f"failed or did not stick: {', '.join(failed)}")
        return 1
    if not results:
        book.i("write", "values already match")
    return 0

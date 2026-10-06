"""`read`: look at the game's values. Read-only; it never opens a write handle.

    read                          every value once, then exit
    read --query NAME             one value or group once (`character.runes`, `hp`, `attrs.*`), then exit
    read --export                 write disk-state.json once, then exit
    read --live                   the same, continuously (with --query / --export: that one, continuously)
    read --live-effects           effects monitor        read --live-animations   animation monitor
                                  (--mapped / --unmapped: only ids that are / are not in chr_state_ids.json)

`--live` means "do not stop". One attach and one loop serve every mode (spec 1.6.2 section 5).
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path

from .. import ui
from ..console import require_windows_x64
from ..game.attach import EXIT_ERROR, EXIT_EAC, AttachError, Target, eac_loaded, locate, open_read
from ..game.processes import is_window_active, process_started
from ..game.profile import load_effects
from ..game.values import UnknownName
from ..logbook import book
from ..paths import describe_resource
from ..reader import view
from ..reader.animations import AnimationsMonitor
from ..reader.effects import EffectsMonitor
from ..reader.export import ExportWriter, JsonLogger
from ..reader.sampler import Sampler
from ..vault import VaultError, authorise, resolve_vault
from ..vault import session as vault_session
from .common import begin

RESCAN_S = 2.0       # how often EAC and the session record are re-checked
EXPORT_NAME = "disk-state.json"


def _wait_for_game(offsets: Path, timeout: float | None = None) -> Target:
    """Wait (saying so once) until eldenring.exe runs, then attach; `timeout` None = wait for ever. Other errors end it."""
    deadline = None if timeout is None else time.monotonic() + timeout
    warned = False
    while True:
        try:
            return locate(offsets)
        except AttachError as exc:
            if "not running" not in str(exc) or (deadline is not None and time.monotonic() >= deadline):
                raise
            if not warned:
                book.i("read", "waiting for eldenring.exe (start it with `eldendisk run`; Ctrl+C to stop)")
                warned = True
            time.sleep(1.0)


def _in_session(vault: Path, target: Target) -> bool:
    """True while a valid RUNNING session record covers this very game process (labels the export)."""
    try:
        record = vault_session.load(vault)
    except VaultError:
        return False
    return record is not None and not authorise(record, game_pid=target.pid, game_started=target.started,
                                                exe_sha256=target.sha256, started_of=process_started)


def _export_log(message: str) -> None:
    """ExportWriter reports `warning: ...` and `[STATE] detail`; show them as warnings and state changes."""
    if message.startswith("warning:"):
        book.w("export", message[len("warning:"):].strip())
    else:
        book.i("export", "state " + re.sub(r"^\[(\w+)\]\s*", r"\1 ", message).strip())


def _continuous(args) -> bool:
    return bool(args.live or args.live_effects or args.live_animations)


def _mode_text(args) -> str:
    if args.live_effects or args.live_animations:
        return ", ".join(n for n, on in (("effects", args.live_effects), ("animations", args.live_animations)) if on) + " (live)"
    if args.export:
        return f"export to {args.out} (live)"
    return f"{args.query or 'all values'} (live)"


def cmd_read(args) -> int:
    require_windows_x64()
    continuous = _continuous(args)
    timeout = None if continuous else args.timeout
    try:
        target = _wait_for_game(Path(args.offsets), timeout)
    except AttachError as exc:
        book.e("read", str(exc))
        return exc.code
    except KeyboardInterrupt:
        return 130

    book.d("config", f"offsets: {args.offsets} ({describe_resource(args.offsets)})")
    book.d("config", f"effects: {args.effects} ({describe_resource(args.effects)})")
    vault = Path()
    try:
        vault = resolve_vault(args.vault)
    except VaultError as exc:
        if args.export:   # the export is labelled by the session record, so a vault that cannot be found is an error
            book.e("read", str(exc))
            return EXIT_ERROR
        book.w("read", str(exc))
        vault = None
    profile = target.profile
    if continuous:
        begin(args, "read", [("game", f"eldenring.exe, pid {target.pid}"), ("profile", str(profile.label)),
                             ("mode", _mode_text(args))])
    if profile.buffs_note:
        book.w("read", profile.buffs_note)

    mem = open_read(target)
    sampler = Sampler(mem, profile, load_effects(Path(args.effects)), target.base)
    try:
        if args.live_effects or args.live_animations:
            return _monitors(args, target, mem, sampler, vault)
        export = _exporter(args, target, vault)
        if args.export and not args.live:
            return _export_once(args, target, mem, sampler, export)
        if not args.export and not args.live:
            return _query_once(args, mem, sampler, export)
        return _live(args, target, mem, sampler, export, vault)
    except KeyboardInterrupt:
        book.i("read", "stopped; the game keeps running")
        return 130
    finally:
        mem.close()


def _exporter(args, target: Target, vault: Path | None) -> ExportWriter:
    """The object that builds `disk-state.json` documents; it writes them only when it has a logger (`--export`)."""
    profile = target.profile
    logger = JsonLogger(Path(args.out), target.exe_path.parent, filename=EXPORT_NAME) if args.export else None
    export = ExportWriter(logger, interval=0.0 if not args.live else args.export_interval,
                          timer_interval=0.0 if not args.live else args.timer_interval, verbose=args.live, log=_export_log)
    export.pid, export.sha, export.label = target.pid, target.sha256, profile.label
    export.anti_cheat = "DISABLED_OFFLINE"
    export.effects_supported = profile.sp_effect is not None
    export.animations_supported = profile.anim is not None
    export.sandbox = bool(vault) and _in_session(vault, target)
    return export


def _first_sample(args, mem, sampler: Sampler):
    """The first CONNECTED sample, or None after `--timeout` seconds (the game is on the title screen or loading)."""
    deadline = time.monotonic() + (args.timeout if not _continuous(args) else 10**9)
    while True:
        s = sampler.sample()
        if s.state == "CONNECTED":
            return s
        if not mem.alive():
            book.e("read", "eldenring.exe exited")
            return None
        if time.monotonic() >= deadline:
            book.e("read", f"no loaded world after {args.timeout:g} s ({s.error or 'title screen or loading'}); "
                           "load a character first")
            return None
        time.sleep(0.25)


def _query_once(args, mem, sampler: Sampler, export: ExportWriter) -> int:
    sample = _first_sample(args, mem, sampler)
    if sample is None:
        return EXIT_ERROR
    doc = export.build("CONNECTED", sample)
    try:
        selection = view.select(doc, args.query)
    except UnknownName as exc:
        book.e("read", str(exc))
        return EXIT_ERROR
    book.d("read", f"query {args.query or '(all)'}: {len(selection)} result(s)")
    if args.json:
        ui.out(view.as_json(selection))
    else:
        ui.rows(view.rows(selection))
    return 0


def _export_once(args, target: Target, mem, sampler: Sampler, export: ExportWriter) -> int:
    sample = _first_sample(args, mem, sampler)
    if sample is None:
        return EXIT_ERROR
    export.emit("CONNECTED", sample)
    export.close()   # retries a write that a reader or the scanner held up
    if export.writes == 0:
        book.e("export", f"could not write {export.logger.path}: the file is busy")
        return EXIT_ERROR
    size = export.logger.path.stat().st_size
    book.ok("export", f"{EXPORT_NAME} ({size / 1024:.1f} KB) written to {export.logger.path.parent}")
    return 0


class _Redraw:
    """Draws a block of lines on the terminal when they differ from what is shown (at most 30 times a second)."""
    MIN_DRAW_S = 1 / 30

    def __init__(self):
        self.screen = ui.Screen()
        self._shown: list[str] | None = None
        self._last = 0.0

    def show(self, lines: list[str]) -> None:
        now = time.monotonic()
        if (lines == self._shown and self.screen.height) or now - self._last < self.MIN_DRAW_S:
            return
        self.screen.show(lines)
        self._shown, self._last = lines, now

    def detach(self) -> None:
        self.screen.detach()

    def close(self) -> None:
        self.screen.close()


class _LiveValues:
    """`--live`: the values, kept current.

    On a terminal the tree is redrawn where it stands and a value that just changed is highlighted for `HOLD_S`.
    Elsewhere (an IDE run window, a pipe) the tree is printed once and then one line per changed value follows.
    Buff countdowns and the counters of ignored effects / animations do not count as changes.
    """
    HOLD_S = 1.0       # how long a changed value stays highlighted

    def __init__(self, name: str | None, export: ExportWriter, sampler: Sampler):
        self.name, self.export, self.sampler = name, export, sampler
        self.flat: dict[str, object] | None = None
        self.waiting = False
        self.painter = _Redraw() if ui.can_redraw() else None
        self.hot: dict[str, float] = {}

    def check(self, sample) -> bool:
        """False (after saying why) when the name matches nothing."""
        try:
            view.select(self.export.build("CONNECTED", sample), self.name)
            return True
        except UnknownName as exc:
            book.e("read", str(exc))
            return False

    def close(self) -> None:
        if self.painter is not None:
            self.painter.close()

    def tick(self) -> None:
        sample = self.sampler.sample()
        if sample.state != "CONNECTED":
            if not self.waiting:
                if self.painter is not None:
                    self.painter.detach()   # the message below must not be overwritten
                book.i("read", f"waiting for a loaded world{': ' + sample.error if sample.error else ''}")
                self.waiting = True
            return
        if self.waiting:
            book.i("read", "world loaded")
            self.waiting = False
        selection = view.select(self.export.build("CONNECTED", sample), self.name)
        flat = {}
        for path, value in selection:
            flat.update(view.flatten(value, path))
        now = time.monotonic()
        if self.flat is not None:
            for path, _old, _new in view.changes(self.flat, flat):
                self.hot[path] = now
        first, previous, self.flat = self.flat is None, self.flat, flat
        if self.painter is not None:
            self.hot = {p: t for p, t in self.hot.items() if now - t < self.HOLD_S}
            screen = self.painter.screen
            self.painter.show(ui.format_rows(view.rows(selection), color=ui.use_color(screen.stream),
                                             hot=frozenset(self.hot), columns=screen.size()[0]))
        elif first:
            ui.rows(view.rows(selection))
        else:
            stamp = datetime.now().strftime("%H:%M:%S")
            for path, old, new in view.changes(previous, flat):
                key = path.rsplit(".", 1)[-1]
                ui.out(f" {stamp}  {path}  {view.fmt(key, old)} \u2192 {view.fmt(key, new)}")


class _Board:
    """`--live-effects` / `--live-animations` on a terminal: one table per monitor, redrawn where it stands."""

    def __init__(self, monitors):
        self.monitors = monitors
        self.painter = _Redraw()

    def close(self) -> None:
        self.painter.close()

    def tick(self) -> None:
        screen = self.painter.screen
        columns, rows = screen.size()
        color = ui.use_color(screen.stream)
        budget = rows - 1 - (len(self.monitors) - 1)   # the blank lines between tables
        want = {m: len(m.lines(m._now())) + 2 for m in self.monitors}
        share, left = {}, budget
        for i, m in enumerate(sorted(self.monitors, key=lambda m: want[m])):   # small tables first, the rest is shared
            share[m] = max(3, min(want[m], left // (len(self.monitors) - i)))
            left -= share[m]
        lines: list[str] = []
        for m in self.monitors:
            if lines:
                lines.append("")
            lines += ui.format_ledger(m.name, m.summary(), m.lines(m._now()), color=color, columns=columns,
                                      max_rows=share[m], waiting=m.waiting)
        self.painter.show(lines)


class _TableReload:
    """Re-reads chr_state_ids.json when it changed, so names added while a monitor runs show up at once."""

    def __init__(self, path: Path, sampler: Sampler):
        self.path, self.sampler = Path(path), sampler
        self._stamp = self._mtime()

    def _mtime(self):
        try:
            st = self.path.stat()
            return st.st_mtime_ns, st.st_size
        except OSError:
            return None

    def check(self) -> None:
        stamp = self._mtime()
        if stamp == self._stamp:
            return
        self._stamp = stamp
        if stamp is None:
            return
        try:
            table = load_effects(self.path)
        except ValueError as exc:
            book.w("read", f"{self.path.name} changed but cannot be read, keeping the old names: {exc}")
            return
        self.sampler.effects = table
        book.i("read", f"{self.path.name} reloaded ({len(table.table)} ids)")


def _live(args, target: Target, mem, sampler: Sampler, export: ExportWriter, vault: Path | None) -> int:
    stream = None
    if not args.export:
        sample = _first_sample(args, mem, sampler)
        if sample is None:
            return EXIT_ERROR
        stream = _LiveValues(args.query, export, sampler)
        if not stream.check(sample):
            return EXIT_ERROR
    book.ok("read", "attached, reading (Ctrl+C to stop)")
    try:
        return _loop(args, target, mem, sampler, [], export, vault, stream)
    finally:
        if stream is not None:
            stream.close()
        if args.export:
            export.close()


def _monitors(args, target: Target, mem, sampler: Sampler, vault: Path | None) -> int:
    both = args.live_effects and args.live_animations
    show = "mapped" if args.mapped else "unmapped" if args.unmapped else "all"
    redraw = ui.can_redraw()

    def out_for(name: str):
        if redraw:
            return None   # the table shows it
        prefix = f"[{name}] " if both else ""
        return lambda line: print(prefix + line, flush=True)

    monitors = []
    if args.live_effects:
        monitors.append(EffectsMonitor(sampler, out_for("effects"), quiet=args.quiet, show=show))
    if args.live_animations:
        monitors.append(AnimationsMonitor(sampler, out_for("animations"), show=show))
    for m in monitors:
        why = m.unsupported(target.profile)
        if why:
            book.e("read", f"{m.name}: {why}")
            return EXIT_ERROR
    for m in monitors:
        m.start()
    board = _Board(monitors) if redraw else None
    book.ok("read", "attached, reading (Ctrl+C to stop)")
    try:
        return _loop(args, target, mem, sampler, monitors, None, vault, board,
                     _TableReload(Path(args.effects), sampler))
    finally:
        if board is not None:
            board.close()


def _loop(args, target: Target, mem, sampler: Sampler, monitors, export: ExportWriter | None, vault: Path | None,
          stream: _LiveValues | _Board | None, reload: _TableReload | None = None) -> int:
    period = 1.0 / args.hz
    next_tick = time.monotonic()
    next_scan = next_tick + RESCAN_S
    last_sample = None
    live_export = export is not None and export.logger is not None
    while True:
        if not mem.alive():
            if live_export:
                export.emit("DISCONNECTED", sample=last_sample)
            return 0

        now = time.monotonic()
        if now >= next_scan:
            if eac_loaded(target.pid):
                if live_export:
                    export.anti_cheat = "ACTIVE_EAC"
                    export.emit("EAC_DETECTED", note="EasyAntiCheat module appeared; stopped reading")
                book.e("read", "EasyAntiCheat appeared in eldenring.exe; stopped reading")
                return EXIT_EAC
            if export is not None:
                export.sandbox = bool(vault) and _in_session(vault, target)
            if reload is not None:
                reload.check()
            next_scan = now + RESCAN_S

        for m in monitors:
            m.tick()

        if stream is not None:
            stream.tick()
        elif live_export:
            if not args.no_idle and not is_window_active(target.pid):
                export.emit("IDLE", sample=last_sample)
            else:
                last_sample = sampler.sample()
                export.emit(last_sample.state, last_sample)

        next_tick += period
        delay = next_tick - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        else:
            next_tick = time.monotonic()   # fell behind: do not try to catch up

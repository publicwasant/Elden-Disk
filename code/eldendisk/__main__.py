"""CLI: python -m eldendisk run | effects | animations | hash | build | sandbox"""
from __future__ import annotations

import argparse
import struct
import sys
import time
from datetime import datetime
from pathlib import Path

if __package__ is None or __package__ == "":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from eldendisk import __version__
    import eldendisk.game_launcher as gl
    from eldendisk.disk import Sampler, build_document, doc_signature, iso
    from eldendisk.json_logger import JsonLogger
    from eldendisk.memory_reader import is_window_active
    from eldendisk.profile_loader import load_effects, load_profile
else:
    from . import __version__
    from . import game_launcher as gl
    from .disk import Sampler, build_document, doc_signature, iso
    from .json_logger import JsonLogger
    from .memory_reader import is_window_active
    from .profile_loader import load_effects, load_profile

HERE = Path(__file__).resolve().parent.parent
EXIT_UNSUPPORTED, EXIT_EAC = 2, 3


def runtime_dirs() -> tuple[Path | None, Path | None]:
    """(external_dir, embedded_dir) when running as a compiled exe, else (None, None).

    external_dir: the folder the user sees the exe in. embedded_dir: where bundled data is unpacked at runtime
    (PyInstaller: sys._MEIPASS; Nuitka: next to the compiled __main__).
    """
    if getattr(sys, "frozen", False):  # PyInstaller
        meipass = getattr(sys, "_MEIPASS", None)
        return Path(sys.executable).resolve().parent, (Path(meipass) if meipass else None)
    compiled = globals().get("__compiled__")  # Nuitka
    if compiled is not None:
        containing = getattr(compiled, "containing_dir", None)
        external = Path(containing) if containing else Path(sys.argv[0]).resolve().parent
        return external, Path(__file__).resolve().parent
    return None, None


def get_resource_path(filename: str, default_dir: Path | None = None) -> Path:
    """Resolve a config file.

    Compiled exe: a file next to the exe wins (so users can update offsets without rebuilding), then the copy
    embedded by `build --embed-configs`. Source run: default_dir, then the project folders.
    """
    external, embedded = runtime_dirs()
    if external is not None:
        if (external / filename).exists():
            return external / filename
        if embedded is not None and (embedded / filename).exists():
            return embedded / filename
    if default_dir is not None and (default_dir / filename).exists():
        return default_dir / filename
    if (HERE / filename).exists():
        return HERE / filename
    if (HERE.parent / filename).exists():
        return HERE.parent / filename
    return Path(filename)


def describe_resource(path: Path | str) -> str:
    """'embedded' | 'external' | 'source' | 'missing' - where a resolved config file lives (for -v output)."""
    p = Path(path)
    if not p.exists():
        return "missing"
    external, embedded = runtime_dirs()
    if embedded is not None:
        try:
            p.resolve().relative_to(embedded.resolve())
            return "embedded"
        except ValueError:
            pass
    return "external" if external is not None else "source"


def _require_windows_x64() -> None:
    if sys.platform != "win32":
        sys.exit("This tool only runs on Windows.")
    if struct.calcsize("P") != 8:
        sys.exit("64-bit Python is required.")


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


class Monitor:
    def __init__(self, args, logger: JsonLogger):
        self.args = args
        self.logger = logger
        self.pid: int | None = None
        self.anti_cheat = "UNKNOWN"
        self.sha: str | None = None
        self.label: str | None = None
        self.effects_supported = False
        self.animations_supported = False
        self.sandbox_supported = True
        self.sampler: Sampler | None = None
        self._last_verbose: tuple | None = None
        self._last_written_doc: dict | None = None
        self._last_written_sig: dict | None = None
        self._last_write_t = 0.0
        self._busy_warned = False
        self._last_character: dict | None = None
        self.mode = "telemetry"
        self.read_only = True  # False only while a sandbox session holds a write handle
        self.sandbox = False

    def _should_write(self, doc: dict, sig: dict | None = None, now_mono: float | None = None) -> bool:
        """Write at once when anything but a buff countdown changed; countdown-only changes at most every timer_interval."""
        if self._last_written_doc is None:
            return True
        if doc == self._last_written_doc:
            return False
        sig = doc_signature(doc) if sig is None else sig
        now_mono = time.monotonic() if now_mono is None else now_mono
        if sig != self._last_written_sig:
            return True
        return now_mono - self._last_write_t >= getattr(self.args, "timer_interval", 0.5)

    def emit(self, state: str, sample=None, note: str | None = None, now_mono: float | None = None) -> None:
        if sample is not None and sample.character is not None:
            self._last_character = sample.character

        doc = build_document(
            now=None, state=state, pid=self.pid, anti_cheat=self.anti_cheat,
            exe_sha256=self.sha, profile_label=self.label,
            effects_supported=self.effects_supported,
            animations_supported=self.animations_supported,
            sandbox_supported=self.sandbox_supported,
            sample=sample,
            last_character=self._last_character, note=note,
            mode=self.mode, read_only=self.read_only, sandbox=self.sandbox,
        )
        mono = time.monotonic() if now_mono is None else now_mono
        sig = doc_signature(doc)
        if self._should_write(doc, sig, mono):
            if self.logger.write(doc):
                self._last_written_doc, self._last_written_sig, self._last_write_t = doc, sig, mono
                self._busy_warned = False
            elif not self._busy_warned:
                self._busy_warned = True
                _log("warning: output file busy, sample skipped (further skips are not repeated)")

        if self.args.verbose:
            err_msg = doc["systems"]["errors"]["message"] if "errors" in doc["systems"] else None
            key = (state, err_msg)
            if key != self._last_verbose:
                self._last_verbose = key
                _log(f"[{state}]" + (f" {key[1]}" if key[1] else ""))


def _writer_api():
    """Imported lazily: plain `run`, `effects` and `animations` never load the write module."""
    if __package__ is None or __package__ == "":
        from eldendisk.memory_writer import MemoryWriter, WritableProcessMemory
    else:
        from .memory_writer import MemoryWriter, WritableProcessMemory
    return MemoryWriter, WritableProcessMemory


def _run_loop(args, gate=None, policy=None) -> int:
    """State streaming loop. With a WriteGate (sandbox session only) it also applies the edit policy through a write handle."""
    _require_windows_x64()
    if __package__ is None or __package__ == "":
        from eldendisk.memory_reader import ProcessMemory, find_pid, list_modules
    else:
        from .memory_reader import ProcessMemory, find_pid, list_modules

    try:
        game_dir = gl.find_game_dir(args.game_dir)
    except FileNotFoundError:
        if not getattr(args, "attach", False):
            raise
        game_dir = None

    logger = JsonLogger(Path(args.out), game_dir, filename="disk-state.json")
    mon = Monitor(args, logger)
    if getattr(args, "verbose", False):
        _log(f"[config] offsets={args.offsets} ({describe_resource(args.offsets)})")
        _log(f"[config] effects={args.effects} ({describe_resource(args.effects)})")
    mem = None
    try:
        # 1. get a PID
        if getattr(args, "attach", False):
            mon.pid = find_pid(gl.GAME_EXE)
            while mon.pid is None:
                mon.emit("WAITING_FOR_PROCESS")
                time.sleep(1)
                mon.pid = find_pid(gl.GAME_EXE)
        else:
            mon.emit("WAITING_FOR_PROCESS")
            mon.pid = gl.launch(game_dir).pid

        # 2. wait for the main module
        main_mod, deadline = None, time.monotonic() + 60
        while main_mod is None and time.monotonic() < deadline:
            mods = list_modules(mon.pid)
            main_mod = next((m for m in mods or [] if m.name.lower() == gl.GAME_EXE), None)
            if main_mod is None:
                time.sleep(0.5)
        if main_mod is None:
            mon.emit("DISCONNECTED", note="eldenring.exe module not found within 60 s")
            _log("error: could not find eldenring.exe module")
            return 1

        exe_path = Path(main_mod.path)
        logger = mon.logger = JsonLogger(Path(args.out), exe_path.parent, filename="disk-state.json")

        # 3. never attach with EAC loaded
        if gl.has_eac(m.name for m in mods):
            mon.anti_cheat = "ACTIVE_EAC"
            if gate is not None:
                gate.close("EAC loaded")
            mon.emit("EAC_ACTIVE", note="EasyAntiCheat modules loaded; not attaching")
            _log("EAC is loaded. Start the game with this tool (offline), not via Steam's normal Play.")
            return EXIT_EAC
        mon.anti_cheat = "DISABLED_OFFLINE"

        # 4. version pin
        mon.sha = gl.sha256_file(exe_path)
        profile, reason = load_profile(Path(args.offsets), mon.sha)
        if profile is None:
            mon.emit("UNSUPPORTED_VERSION", note=reason)
            _log(f"UNSUPPORTED_VERSION: {reason}\nexe sha256: {mon.sha}\nAdd a profile to {args.offsets} (see README).")
            return EXIT_UNSUPPORTED
        mon.label = profile.label
        mon.effects_supported = profile.sp_effect is not None
        mon.animations_supported = profile.anim is not None
        mon.sandbox_supported = True
        if profile.buffs_note:
            _log(f"note: {profile.buffs_note}")
        writer = None
        if gate is not None:  # sandbox session: open write capability
            MemoryWriter, WritableProcessMemory = _writer_api()
            mem = WritableProcessMemory(mon.pid)
            mon.mode = "sandbox"
            mon.read_only = False
            mon.sandbox = True
        else:
            mem = ProcessMemory(mon.pid)
            mon.mode = "telemetry"
            mon.read_only = True
            mon.sandbox = False
        mon.sampler = Sampler(mem, profile, load_effects(Path(args.effects)), main_mod.base)
        if gate is not None and policy is not None:
            writer = MemoryWriter(mem, mon.sampler, policy, gate, hz=getattr(args, "write_hz", 4.0), log=_log)

        # 5. poll at 60FPS
        period = 1.0 / args.hz
        next_scan = time.monotonic() + 2
        last_sample = None

        while True:
            if not mem.alive():
                mon.emit("DISCONNECTED", sample=last_sample)
                return 0

            if time.monotonic() >= next_scan:
                mods = list_modules(mon.pid)
                if mods and gl.has_eac(m.name for m in mods):
                    if gate is not None:
                        gate.close("EAC detected")
                    mon.anti_cheat = "ACTIVE_EAC"
                    mon.emit("EAC_DETECTED", note="EasyAntiCheat module appeared; stopped reading")
                    return EXIT_EAC
                next_scan = time.monotonic() + 2

            if writer is not None:
                writer.tick()  # gated + rate-limited; a no-op unless the session is RUNNING

            # Check window active focus -> IDLE state
            if not getattr(args, "no_idle", False) and not is_window_active(mon.pid):
                mon.emit("IDLE", sample=last_sample)
                time.sleep(period)
                continue

            s = mon.sampler.sample()
            last_sample = s
            mon.emit(s.state, s)
            time.sleep(period)
    except KeyboardInterrupt:
        _log("stopped (the game keeps running)")
        return 130
    finally:
        if mem is not None:
            mem.close()
    return 0


def cmd_run(args, gate=None, policy=None) -> int:
    """Host launcher & save guard. Automatically handles pre-session save snapshot and post-session restore."""
    _require_windows_x64()
    if getattr(args, "attach", False) or gate is not None:
        return _run_loop(args, gate=gate, policy=policy)

    from eldendisk.game_launcher import GameFolderGuard
    from eldendisk.memory_reader import find_pid, list_process_names
    from eldendisk.sandbox import Hooks, SandboxSession
    from eldendisk.save_vault import SaveVault, SessionLog

    if find_pid(gl.GAME_EXE) is not None:
        _log("eldenring.exe is already running; attaching in read-only mode")
        return _run_loop(args, gate=gate, policy=policy)

    game_dir = gl.find_game_dir(args.game_dir)
    sha = gl.sha256_file(game_dir / gl.GAME_EXE)
    vault_path = Path(getattr(args, "vault", DEFAULT_VAULT))
    vault, live = SaveVault(vault_path), _live_dir(args)

    def extra() -> list[str]:
        out = []
        profile, reason = load_profile(Path(args.offsets), sha)
        if profile is None:
            out.append(f"no usable profile for this eldenring.exe ({reason})")
        root, gd = vault_path.resolve(), game_dir.resolve()
        if root == gd or gd in root.parents:
            out.append("the vault must not be inside the game folder")
        return out

    hooks = Hooks(
        game_running=lambda: False,
        anticheat_running=lambda: bool(gl.anticheat_processes(list_process_names())),
        run_game=lambda g: _run_loop(args, gate=g, policy=policy),
        wait_game_exit=_wait_game_exit, extra_preflight=extra,
        game_guard=GameFolderGuard(game_dir), game_dir=game_dir, exe_sha256=sha,
    )
    log = SessionLog(echo=_log)
    return SandboxSession(vault, live, hooks, log=log).run()


def cmd_effects(args) -> int:
    """Live SpEffect viewer: prints the list once, then only additions/removals."""
    _require_windows_x64()
    if __package__ is None or __package__ == "":
        from eldendisk.memory_reader import ProcessMemory, find_pid, list_modules
        from eldendisk.profile_loader import Effects
    else:
        from .memory_reader import ProcessMemory, find_pid, list_modules
        from .profile_loader import Effects

    pid = find_pid(gl.GAME_EXE)
    if pid is None:
        raise RuntimeError("eldenring.exe is not running")
    mods = list_modules(pid) or []
    main_mod = next((m for m in mods if m.name.lower() == gl.GAME_EXE), None)
    if main_mod is None:
        raise RuntimeError("eldenring.exe module not found")
    if gl.has_eac(m.name for m in mods):
        raise RuntimeError("EAC is loaded; not attaching")
    profile, reason = load_profile(Path(args.offsets), gl.sha256_file(Path(main_mod.path)))
    if profile is None:
        raise RuntimeError(reason)
    if profile.sp_effect is None:
        raise RuntimeError(profile.buffs_note or "sp_effect layout incomplete")

    mem = ProcessMemory(pid)
    sampler = Sampler(mem, profile, Effects({}), main_mod.base)
    prev: dict[int, tuple[float, float]] | None = None
    last_err = None
    print("Ctrl+C to stop. Format: id | duration | timer   (+ = appeared, - = disappeared)")
    try:
        while mem.alive():
            entries, err = sampler.raw_effects()
            if entries is None:
                if err != last_err:
                    print(f"[waiting] {err}")
                    last_err = err
            else:
                last_err = None
                cur = {eid: (dur, timer) for eid, dur, timer in entries
                       if not args.quiet or dur < 0 or dur >= 1.0}
                if prev is None:
                    print(f"--- {len(cur)} effects now active ---")
                    for eid, (d, t) in sorted(cur.items()):
                        print(f"  {eid:>10} | {d:10.2f} | {t:10.2f}")
                else:
                    for eid in sorted(cur.keys() - prev.keys()):
                        print(f"+ {eid:>10} | {cur[eid][0]:10.2f} | {cur[eid][1]:10.2f}")
                    for eid in sorted(prev.keys() - cur.keys()):
                        print(f"- {eid:>10}")
                prev = cur
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        mem.close()
    return 0


def cmd_animations(args) -> int:
    """Live character animation state viewer for building chr_state_ids.json (game must be running offline)."""
    _require_windows_x64()
    if __package__ is None or __package__ == "":
        from eldendisk.memory_reader import ProcessMemory, find_pid, list_modules
    else:
        from .memory_reader import ProcessMemory, find_pid, list_modules

    pid = find_pid(gl.GAME_EXE)
    if pid is None:
        raise RuntimeError("eldenring.exe is not running")
    mods = list_modules(pid) or []
    main_mod = next((m for m in mods if m.name.lower() == gl.GAME_EXE), None)
    if main_mod is None:
        raise RuntimeError("eldenring.exe module not found")
    if gl.has_eac(m.name for m in mods):
        raise RuntimeError("EAC is loaded; not attaching")
    profile, reason = load_profile(Path(args.offsets), gl.sha256_file(Path(main_mod.path)))
    if profile is None:
        raise RuntimeError(reason)
    if profile.anim is None:
        raise RuntimeError("anim layout incomplete in profile")

    mem = ProcessMemory(pid)
    sampler = Sampler(mem, profile, load_effects(Path(args.effects)), main_mod.base)

    print("Ctrl+C to stop. Format: id | timestamp (+ is appeared, - is disappeared)")
    prev_anim: int | None = None
    last_err = None
    first = True

    try:
        while mem.alive():
            player, reason = sampler.locate_player()
            if player is None:
                if reason != last_err:
                    print(f"[waiting] {reason}")
                    last_err = reason
                time.sleep(0.5)
                continue

            last_err = None
            cur_anim = sampler.read_animation_id(player)
            if cur_anim is not None and cur_anim > 0:
                ts = iso(datetime.now().astimezone())
                if first:
                    print("--- 1 animations now active ---")
                    print(f"+   {cur_anim:>10} |   {ts}")
                    prev_anim = cur_anim
                    first = False
                elif cur_anim != prev_anim:
                    if prev_anim is not None:
                        print(f"-   {prev_anim:>10} |   {ts}")
                    print(f"+   {cur_anim:>10} |   {ts}")
                    prev_anim = cur_anim

            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        mem.close()
    return 0


def cmd_hash(args) -> int:
    d = gl.find_game_dir(args.game_dir)
    print(gl.sha256_file(d / gl.GAME_EXE))
    return 0


def _build_layout() -> dict:
    code_dir = HERE
    project_root = code_dir.parent if code_dir.name == "code" else code_dir
    build_root = project_root / "build"
    dist_dir = build_root / "dist" / __version__ / f"eldendisk-v{__version__}-x64" / "eldendisk"
    return {
        "code_dir": code_dir,
        "project_root": project_root,
        "build_root": build_root,
        "dist_dir": dist_dir,
        "work_dir": build_root / "work",
        "entry_point": code_dir / "eldendisk" / "__main__.py",
    }


def _config_files(layout: dict) -> list[Path]:
    """offsets.json and chr_state_ids.json, from code/ or the project root (only those that exist)."""
    out = []
    for name in ("offsets.json", "chr_state_ids.json"):
        for base in (layout["code_dir"], layout["project_root"]):
            if (base / name).exists():
                out.append(base / name)
                break
    return out


def build_command(engine: str, *, embed: bool, icon: str | None, layout: dict, configs: list[Path]) -> list[str]:
    """The compiler command line for `engine` (pure, so it can be unit-tested without compiling)."""
    entry, dist_dir = layout["entry_point"], layout["dist_dir"]
    icon_path = Path(icon).resolve() if icon and Path(icon).exists() else None
    if icon and icon_path is None:
        _log(f"warning: icon file not found: {icon}")
    sep = ";" if sys.platform == "win32" else ":"

    if engine == "pyinstaller":
        cmd = [sys.executable, "-m", "PyInstaller", "--onefile", "--name=eldendisk",
               f"--distpath={dist_dir}", f"--workpath={layout['work_dir']}", f"--specpath={layout['work_dir']}"]
        if icon_path:
            cmd.append(f"--icon={icon_path}")
        if embed:
            cmd += [f"--add-data={c}{sep}." for c in configs]
    else:  # nuitka
        cmd = [sys.executable, "-m", "nuitka", "--onefile", f"--output-dir={dist_dir}",
               "--output-filename=eldendisk.exe"]
        if icon_path:
            cmd.append(f"--windows-icon-from-ico={icon_path}")
        if embed:
            cmd += [f"--include-data-files={c}={c.name}" for c in configs]
    cmd.append(str(entry))
    return cmd


def cmd_build(args) -> int:
    import shutil
    import subprocess

    engine = (args.engine or "pyinstaller").lower()
    if engine not in ("pyinstaller", "nuitka"):
        _log(f"error: unsupported build engine '{args.engine}'")
        return 1

    layout = _build_layout()
    dist_dir = layout["dist_dir"]

    if args.clean:
        _log("[INFO] Cleaning previous build artifacts...")
        if layout["build_root"].exists():
            shutil.rmtree(layout["build_root"], ignore_errors=True)

    dist_dir.mkdir(parents=True, exist_ok=True)
    layout["work_dir"].mkdir(parents=True, exist_ok=True)
    configs = _config_files(layout)
    label = "PyInstaller" if engine == "pyinstaller" else "Nuitka"
    _log(f"[INFO] Initializing {label} engine...")
    _log(f"[INFO] Building eldendisk.exe (Onefile mode) for version {__version__}...")

    cmd = build_command(engine, embed=args.embed_configs, icon=args.icon, layout=layout, configs=configs)
    try:
        res = subprocess.run(cmd, check=False)
    except OSError as exc:
        _log(f"error during build: {exc}")
        return 1
    if res.returncode != 0:
        _log(f"[ERROR] {label} build failed.")
        return 1

    if not args.embed_configs:  # editable configs travel next to the exe, for both engines
        for c in configs:
            shutil.copy2(c, dist_dir / c.name)

    rel_exe = f"./build/dist/{__version__}/eldendisk-v{__version__}-x64/eldendisk/eldendisk.exe"
    _log(f"[SUCCESS] Build complete! Standalone executable located at: {rel_exe} ✓")
    return 0


def default_vault_path() -> str:
    external_dir, _ = runtime_dirs()
    base = external_dir or HERE
    return str(base / "backup" / "vault")


DEFAULT_VAULT = default_vault_path()


def _wait_game_exit() -> bool:
    """Block until no eldenring.exe exists (FR-6); a second Ctrl+C is handled by the session (postpones restore)."""
    if __package__ is None or __package__ == "":
        import eldendisk.memory_reader as mr
    else:
        from . import memory_reader as mr
    warned = False
    while mr.find_pid(gl.GAME_EXE) is not None:
        if not warned:
            _log("waiting for eldenring.exe to exit before restoring the save (Ctrl+C again to postpone)")
            warned = True
        time.sleep(0.5)
    time.sleep(1.0)  # let the game release its save files (A3)
    return True


def _live_dir(args) -> Path:
    from eldendisk.save_vault import find_save_dir, save_registry_save_dir
    if getattr(args, "save_dir", None):
        p = Path(args.save_dir)
        if p.is_dir():
            save_registry_save_dir(str(p))
        return p
    return find_save_dir()


def _sb_restore(args) -> int:
    _require_windows_x64()
    from eldendisk.memory_reader import find_pid
    from eldendisk.sandbox import restore_pending
    from eldendisk.save_vault import SaveVault, SessionLog

    vault, log = SaveVault(Path(args.vault)), SessionLog(echo=_log)
    running = lambda: find_pid(gl.GAME_EXE) is not None
    if not args.snapshot:
        return restore_pending(vault, game_running=running, archive=args.archive_contaminated, log=log)
    if vault.read_marker() is not None:
        log.write("an unresolved session exists; run `sandbox restore` without --snapshot first")
        return 1
    if running():
        log.write("eldenring.exe is running; close it before restoring")
        return 1
    live, snap_dir = _live_dir(args), vault.snapshot_path(args.snapshot)
    safety = vault.snapshot(live, suffix="-pre-restore")  # what is there now stays recoverable
    log.write(f"current save kept as {safety.dir.name}")
    vault.restore(snap_dir, live)
    problems = vault.verify_live(live, vault.load_manifest(snap_dir)["files"])
    if problems:
        log.write("verification failed: " + "; ".join(problems[:3]))
        return 4
    log.write(f"restored {args.snapshot} and verified")
    return 0


def _sb_status(args) -> int:
    from eldendisk.save_vault import SaveVault
    s = SaveVault(Path(args.vault)).status()
    if s["marker_error"]:
        print(f"MARKER UNREADABLE: {s['marker_error']}")
    elif s["marker"]:
        print(f"UNRESOLVED SESSION since {s['marker']['created']}: live save is NOT trusted. Run `sandbox restore`.")
        print(f"  snapshot: {s['marker']['snapshot_dir']}")
    else:
        print("no unresolved session; live save trusted")
    print(f"snapshots: {s['snapshots']}  last: {s['last'] or '-'}  vault size: {s['vault_bytes'] / 2**20:.1f} MiB")
    if s["last"]:
        print("last snapshot: " + ("verified" if not s["last_problems"] else "PROBLEMS: " + "; ".join(s["last_problems"][:3])))
    return 4 if s["marker"] or s["marker_error"] else 0


def _sb_list(args) -> int:
    from eldendisk.save_vault import SaveVault
    rows = SaveVault(Path(args.vault)).list_snapshots(verify=not args.fast)
    for r in rows:
        v = {True: "verified", False: "DAMAGED", None: "not checked" if r["has_manifest"] else "no manifest"}[r["verified"]]
        print(f"{r['name']}  {r['size'] / 2**20:7.1f} MiB  {v}")
    if not rows:
        print("no snapshots")
    return 0


def _sb_verify(args) -> int:
    from eldendisk.save_vault import SaveVault
    v = SaveVault(Path(args.vault))
    problems = v.verify_snapshot(v.snapshot_path(args.snapshot))
    print("OK: snapshot matches its manifest" if not problems else "\n".join(problems))
    return 0 if not problems else 1


def _sb_prune(args) -> int:
    from eldendisk.save_vault import SaveVault
    gone = SaveVault(Path(args.vault)).prune(args.keep)
    print(f"deleted {len(gone)} snapshot(s)" + (": " + ", ".join(gone) if gone else ""))
    return 0


def cmd_sandbox_edit(args) -> int:
    _require_windows_x64()
    if __package__ is None or __package__ == "":
        from eldendisk.memory_reader import find_pid, list_modules
        from eldendisk.memory_writer import WritableProcessMemory, MemoryWriter, WriteGate, parse_policy
    else:
        from .memory_reader import find_pid, list_modules
        from .memory_writer import WritableProcessMemory, MemoryWriter, WriteGate, parse_policy

    verbose = getattr(args, "verbose", False)
    log_func = _log if verbose else (lambda _m: None)

    set_list = getattr(args, "set", None)
    refill_str = getattr(args, "refill", None)
    policy = parse_policy(set_list, refill_str)
    if policy.empty:
        if verbose:
            _log("sandbox: no edits specified (use --set NAME=VALUE or --refill LIST)")
        return 0

    pid = find_pid(gl.GAME_EXE)
    if pid is None:
        _log("error: eldenring.exe is not running. Launch the game first with `eldendisk run`.")
        return 1

    mods = list_modules(pid) or []
    main_mod = next((m for m in mods if m.name.lower() == gl.GAME_EXE), None)
    if main_mod is None:
        _log("error: eldenring.exe module not found")
        return 1

    if gl.has_eac(m.name for m in mods):
        _log("error: EasyAntiCheat is loaded in eldenring.exe. Memory edits are refused.")
        return EXIT_EAC

    sha = gl.sha256_file(Path(main_mod.path))
    profile, reason = load_profile(Path(args.offsets), sha)
    if profile is None:
        _log(f"error: no verified profile for eldenring.exe ({reason})")
        return EXIT_UNSUPPORTED

    mem = WritableProcessMemory(pid)
    try:
        sampler = Sampler(mem, profile, load_effects(Path(args.effects)), main_mod.base)
        gate = WriteGate()
        gate.open()
        writer = MemoryWriter(mem, sampler, policy, gate, hz=1.0, log=log_func)
        results = writer.apply_once()
        if verbose:
            if results:
                _log(f"[sandbox] Applied {len(results)} edit(s) on-the-fly successfully. ✓")
            else:
                _log("[sandbox] Memory values already match policy.")
    finally:
        mem.close()

    return 0


def cmd_sandbox(args) -> int:
    cmd = getattr(args, "sandbox_cmd", None)
    if cmd in ("restore", "status", "list", "verify", "prune"):
        return {"restore": _sb_restore, "status": _sb_status,
                "list": _sb_list, "verify": _sb_verify, "prune": _sb_prune}[cmd](args)
    return cmd_sandbox_edit(args)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="eldendisk", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    offsets_default = str(get_resource_path("offsets.json", default_dir=HERE))
    effects_default = str(get_resource_path("chr_state_ids.json", default_dir=HERE))
    if not Path(effects_default).exists() and (HERE / "effects.json").exists():
        effects_default = str(get_resource_path("effects.json", default_dir=HERE))
    external_dir, _embedded = runtime_dirs()
    out_default = str((external_dir or HERE) / "output")

    r = sub.add_parser("run", help="launch the game offline and write disk-state.json")
    r.add_argument("--save-dir", help="live save folder (default: auto-detected / remembered in Windows Registry)")
    r.add_argument("--vault", default=DEFAULT_VAULT, help="snapshot vault directory (default: %(default)s)")
    r.add_argument("--attach", action="store_true", help="attach to an already-running eldenring.exe instead of launching")
    r.add_argument("--game-dir", help="folder containing eldenring.exe (default: auto-detect via Steam)")
    r.add_argument("--out", default=out_default,
                   help="directory for disk-state.json (default: <project>/code/output)")
    r.add_argument("--offsets", default=offsets_default, help="offsets.json (default: %(default)s)")
    r.add_argument("--effects", default=effects_default, help="chr_state_ids.json (default: %(default)s)")
    r.add_argument("--hz", type=float, default=60.0, help="polls per second, 1-120 (default: 60)")
    r.add_argument("--timer-interval", type=float, default=0.5, metavar="SEC",
                   help="min seconds between writes that only change a buff countdown; 0 = every change (default: 0.5)")
    r.add_argument("--no-idle", action="store_true",
                   help="keep reading while the game window is unfocused (default: pause and report IDLE)")
    r.add_argument("-v", "--verbose", action="store_true", help="print state changes and diagnostics")
    r.set_defaults(fn=cmd_run)

    e = sub.add_parser("effects", help="live SpEffect viewer for building chr_state_ids.json (game must be running offline)")
    e.add_argument("--offsets", default=offsets_default, help="offsets.json (default: %(default)s)")
    e.add_argument("--effects", default=effects_default, help=argparse.SUPPRESS)  # deprecated no-op (kept for old scripts)
    e.add_argument("-q", "--quiet", action="store_true",
                   help="hide short-lived internal effects (0 <= duration < 1 s); keeps permanent (-1) and timed buffs")
    e.set_defaults(fn=cmd_effects)

    a = sub.add_parser("animations", help="live character animation state viewer for building chr_state_ids.json")
    a.add_argument("--offsets", default=offsets_default, help="offsets.json (default: %(default)s)")
    a.add_argument("--effects", default=effects_default, help="chr_state_ids.json (default: %(default)s)")
    a.add_argument("-q", "--quiet", action="store_true", help=argparse.SUPPRESS)  # deprecated no-op (kept for old scripts)
    a.set_defaults(fn=cmd_animations)

    h = sub.add_parser("hash", help="print SHA-256 of eldenring.exe (key for offsets.json)")
    h.add_argument("--game-dir", help="folder containing eldenring.exe (default: auto-detect via Steam)")
    h.set_defaults(fn=cmd_hash)

    b = sub.add_parser("build", help="build standalone eldendisk.exe using PyInstaller or Nuitka")
    b.add_argument("-e", "--engine", choices=["pyinstaller", "nuitka"], default="pyinstaller",
                   help="build engine to use (default: pyinstaller)")
    b.add_argument("-c", "--clean", action="store_true", help="clean build cache directories before compiling")
    b.add_argument("-em", "--embed-configs", action="store_true",
                   help="embed offsets.json and chr_state_ids.json directly into the executable")
    b.add_argument("-i", "--icon", help="path to icon file (.ico)")
    b.set_defaults(fn=cmd_build)

    sb = sub.add_parser("sandbox", help="on-the-fly memory edits and save-protected session management")
    sb.add_argument("--vault", default=DEFAULT_VAULT, help="snapshot vault directory (default: %(default)s)")
    sb.add_argument("--save-dir", help="live save folder (default: auto-detected / remembered in config.json)")
    sb.add_argument("--game-dir", help="folder containing eldenring.exe (default: auto-detect via Steam)")
    sb.add_argument("--set", action="append", metavar="NAME=VALUE",
                    help="hold/set a value (level, runes, vigor, mind, endurance, strength, dexterity, intelligence, faith, arcane, hp, fp, stamina); repeatable")
    sb.add_argument("--refill", metavar="LIST", help="hold current hp,fp,stamina at maximum, e.g. hp,fp,stamina")
    sb.add_argument("--write-hz", type=float, default=4.0, help="edit applications per second, 1-30 (default: 4)")
    sb.add_argument("--archive-contaminated", action="store_true", help="keep modified save in vault before restoring")
    sb.add_argument("--out", default=out_default, help="directory for disk-state.json")
    sb.add_argument("--offsets", default=offsets_default, help="offsets.json (default: %(default)s)")
    sb.add_argument("--effects", default=effects_default, help="chr_state_ids.json (default: %(default)s)")
    sb.add_argument("--hz", type=float, default=60.0, help="polls per second, 1-120 (default: 60)")
    sb.add_argument("--timer-interval", type=float, default=0.5, metavar="SEC", help="see `run --timer-interval`")
    sb.add_argument("--no-idle", action="store_true", help="keep reading while the game window is unfocused")
    sb.add_argument("-v", "--verbose", action="store_true", help="print state changes and diagnostics")
    sb.set_defaults(fn=cmd_sandbox)

    sbs = sb.add_subparsers(dest="sandbox_cmd", required=False)

    def _vault_opt(sp):
        sp.add_argument("--vault", default=DEFAULT_VAULT, help="snapshot vault directory (default: %(default)s)")

    s = sbs.add_parser("restore", help="restore the save after an interrupted session (safe to repeat)")
    _vault_opt(s)
    s.add_argument("--snapshot", help="restore this snapshot by name instead (the current save is kept as <ts>-pre-restore)")
    s.add_argument("--save-dir", help="live save folder (default: auto-detect)")
    s.add_argument("--archive-contaminated", action="store_true", help="keep the modified save in the vault before restoring")

    s = sbs.add_parser("status", help="marker, last snapshot, vault size")
    _vault_opt(s)
    s = sbs.add_parser("list", help="list snapshots with size and verification result")
    _vault_opt(s)
    s.add_argument("--fast", action="store_true", help="skip re-hashing")
    s = sbs.add_parser("verify", help="re-hash one snapshot against its manifest")
    _vault_opt(s)
    s.add_argument("snapshot", help="snapshot name, e.g. 20261004-213015")
    s = sbs.add_parser("prune", help="delete old snapshots (refused while a session is unresolved)")
    _vault_opt(s)
    s.add_argument("--keep", type=int, required=True, metavar="N", help="number of newest snapshots to keep")
    for sp in sbs.choices.values():
        sp.set_defaults(fn=cmd_sandbox)

    args = ap.parse_args(argv)
    if args.cmd == "run" and not 1 <= args.hz <= 120:
        ap.error("--hz must be between 1 and 120")
        if not 1 <= args.write_hz <= 30:
            ap.error("--write-hz must be between 1 and 30")
    try:
        return args.fn(args)
    except (OSError, ValueError, RuntimeError) as exc:
        _log(f"error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""CLI: python -m eldendisk run | effects | animations | hash | build"""
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
    from eldendisk.disk import Sampler, build_document
    from eldendisk.json_logger import JsonLogger
    from eldendisk.memory_reader import is_window_active
    from eldendisk.profile_loader import load_effects, load_profile
else:
    from . import __version__
    from . import game_launcher as gl
    from .disk import Sampler, build_document
    from .json_logger import JsonLogger
    from .memory_reader import is_window_active
    from .profile_loader import load_effects, load_profile

HERE = Path(__file__).resolve().parent.parent
EXIT_UNSUPPORTED, EXIT_EAC = 2, 3


def get_resource_path(filename: str, default_dir: Path | None = None) -> Path:
    """Resolve file path dynamically, supporting sys._MEIPASS when frozen."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / filename).exists():
            return exe_dir / filename
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            p = Path(meipass) / filename
            if p.exists():
                return p
        for ancestor in (exe_dir.parent, exe_dir.parent.parent, exe_dir.parent.parent.parent):
            if (ancestor / filename).exists():
                return ancestor / filename
            if (ancestor / "code" / filename).exists():
                return ancestor / "code" / filename
    if default_dir is not None and (default_dir / filename).exists():
        return default_dir / filename
    if (HERE / filename).exists():
        return HERE / filename
    if (HERE.parent / filename).exists():
        return HERE.parent / filename
    return Path(filename)


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
        self.buffs = False
        self.sampler: Sampler | None = None
        self._last_verbose: tuple | None = None
        self._last_written_doc: dict | None = None
        self._last_character: dict | None = None

    def _should_write(self, doc: dict) -> bool:
        if self._last_written_doc is None:
            return True
        return doc != self._last_written_doc

    def emit(self, state: str, sample=None, note: str | None = None) -> None:
        if sample is not None and sample.character is not None:
            self._last_character = sample.character

        doc = build_document(
            now=None, state=state, pid=self.pid, anti_cheat=self.anti_cheat,
            exe_sha256=self.sha, profile_label=self.label, buffs_supported=self.buffs, sample=sample,
            last_character=self._last_character, note=note,
        )
        if self._should_write(doc):
            if self.logger.write(doc):
                self._last_written_doc = doc
            else:
                _log("warning: output file busy, sample skipped")

        if self.args.verbose:
            key = (state, doc["system_status"]["last_error"])
            if key != self._last_verbose:
                self._last_verbose = key
                _log(f"[{state}]" + (f" {key[1]}" if key[1] else ""))


def cmd_run(args) -> int:
    _require_windows_x64()
    if __package__ is None or __package__ == "":
        from eldendisk.memory_reader import ProcessMemory, find_pid, list_modules
    else:
        from .memory_reader import ProcessMemory, find_pid, list_modules

    try:
        game_dir = gl.find_game_dir(args.game_dir)
    except FileNotFoundError:
        if not args.attach:
            raise
        game_dir = None

    logger = JsonLogger(Path(args.out), game_dir, filename="disk-state.json")
    mon = Monitor(args, logger)
    mem = None
    try:
        # 1. get a PID
        if args.attach:
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
        mon.label, mon.buffs = profile.label, profile.sp_effect is not None
        if profile.buffs_note:
            _log(f"note: {profile.buffs_note}")
        mem = ProcessMemory(mon.pid)
        mon.sampler = Sampler(mem, profile, load_effects(Path(args.effects)), main_mod.base)

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
                    mon.anti_cheat = "ACTIVE_EAC"
                    mon.emit("EAC_DETECTED", note="EasyAntiCheat module appeared; stopped reading")
                    return EXIT_EAC
                next_scan = time.monotonic() + 2

            # Check window active focus -> IDLE state
            if not is_window_active(mon.pid):
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
            wcm, w = sampler._follow(sampler.base + profile.world_chr_man_rva, "WorldChrMan")
            if w is not None:
                if w.error != last_err:
                    print(f"[waiting] {w.error or 'world not loaded'}")
                    last_err = w.error
                time.sleep(0.5)
                continue

            player, w = sampler._follow(wcm + profile.world_chr_man_to_player, "PlayerIns")
            if w is not None:
                if w.error != last_err:
                    print(f"[waiting] {w.error or 'player not loaded'}")
                    last_err = w.error
                time.sleep(0.5)
                continue

            last_err = None
            cur_anim = sampler._read_anim_id(player)
            if cur_anim is not None and cur_anim > 0:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
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


def cmd_build(args) -> int:
    engine = (args.engine or "pyinstaller").lower()
    if engine not in ("pyinstaller", "nuitka"):
        _log(f"error: unsupported build engine '{args.engine}'")
        return 1

    code_dir = HERE
    project_root = code_dir.parent if code_dir.name == "code" else code_dir
    build_root = project_root / "build"
    dist_dir = build_root / "dist" / __version__
    work_dir = build_root / "work"
    entry_point = code_dir / "eldendisk" / "__main__.py"

    if args.clean:
        _log("[INFO] Cleaning previous build artifacts...")
        import shutil
        if build_root.exists():
            shutil.rmtree(build_root, ignore_errors=True)

    if engine == "pyinstaller":
        _log("[INFO] Initializing PyInstaller engine...")
        _log(f"[INFO] Building eldendisk.exe (Onefile mode) for version {__version__}...")

        dist_dir.mkdir(parents=True, exist_ok=True)
        work_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--name=eldendisk",
            f"--distpath={dist_dir}",
            f"--workpath={work_dir}",
            f"--specpath={work_dir}",
        ]

        if args.icon:
            icon_path = Path(args.icon).resolve()
            if icon_path.exists():
                cmd.append(f"--icon={icon_path}")
            else:
                _log(f"warning: icon file not found: {args.icon}")

        offsets_src = code_dir / "offsets.json" if (code_dir / "offsets.json").exists() else project_root / "offsets.json"
        chr_src = code_dir / "chr_state_ids.json" if (code_dir / "chr_state_ids.json").exists() else project_root / "chr_state_ids.json"
        schema_src = code_dir / "eldendisk" / "disk.schema.json"

        sep = ";" if sys.platform == "win32" else ":"
        if schema_src.exists():
            cmd.append(f"--add-data={schema_src}{sep}eldendisk")

        if args.embed_configs:
            if offsets_src.exists():
                cmd.append(f"--add-data={offsets_src}{sep}.")
            if chr_src.exists():
                cmd.append(f"--add-data={chr_src}{sep}.")

        cmd.append(str(entry_point))

        try:
            import subprocess
            res = subprocess.run(cmd, check=False)
            if res.returncode != 0:
                _log("[ERROR] PyInstaller build failed.")
                return 1

            # Copy external config files to dist directory only for non-embedded distribution
            if not args.embed_configs:
                import shutil
                if offsets_src.exists():
                    shutil.copy2(offsets_src, dist_dir / "offsets.json")
                if chr_src.exists():
                    shutil.copy2(chr_src, dist_dir / "chr_state_ids.json")
        except Exception as exc:
            _log(f"error during build: {exc}")
            return 1

        _log(f"[SUCCESS] Build complete! Standalone executable located at: ./build/dist/{__version__}/eldendisk.exe")
        return 0

    elif engine == "nuitka":
        _log("[INFO] Initializing Nuitka engine...")
        _log(f"[INFO] Building eldendisk.exe (Onefile mode) for version {__version__}...")
        dist_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable, "-m", "nuitka",
            "--standalone",
            "--onefile",
            f"--output-dir={dist_dir}",
            "--target-filename=eldendisk.exe",
        ]
        if args.icon:
            cmd.append(f"--windows-icon-from-ico={args.icon}")
        cmd.append(str(entry_point))

        try:
            import subprocess
            res = subprocess.run(cmd, check=False)
            if res.returncode != 0:
                _log("[ERROR] Nuitka build failed.")
                return 1
        except Exception as exc:
            _log(f"error during build: {exc}")
            return 1

        _log(f"[SUCCESS] Build complete! Standalone executable located at: ./build/dist/{__version__}/eldendisk.exe")
        return 0

    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="eldendisk", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    offsets_default = str(get_resource_path("offsets.json", default_dir=HERE))
    effects_default = str(get_resource_path("chr_state_ids.json", default_dir=HERE))
    if not Path(effects_default).exists() and (HERE / "effects.json").exists():
        effects_default = str(get_resource_path("effects.json", default_dir=HERE))
    out_default = str(Path(sys.executable).parent / "output") if getattr(sys, "frozen", False) else str(HERE / "output")

    r = sub.add_parser("run", help="launch the game offline and write telemetry JSON")
    r.add_argument("--attach", action="store_true", help="attach to an already-running eldenring.exe instead of launching")
    r.add_argument("--game-dir", help="folder containing eldenring.exe (default: auto-detect via Steam)")
    r.add_argument("--out", default=out_default,
                   help="directory for disk-state.json (default: <project>/code/output)")
    r.add_argument("--offsets", default=offsets_default, help="offsets.json (default: <project>/offsets.json)")
    r.add_argument("--effects", default=effects_default, help="chr_state_ids.json (default: <project>/chr_state_ids.json)")
    r.add_argument("--hz", type=float, default=60.0, help="polls per second, 1-120 (default: 60)")
    r.add_argument("-v", "--verbose", action="store_true", help="print state changes and diagnostics")
    r.set_defaults(fn=cmd_run)

    e = sub.add_parser("effects", help="live SpEffect viewer for building chr_state_ids.json (game must be running offline)")
    e.add_argument("--offsets", default=offsets_default, help="offsets.json (default: <project>/offsets.json)")
    e.add_argument("--effects", default=effects_default, help="chr_state_ids.json (default: <project>/chr_state_ids.json)")
    e.add_argument("-q", "--quiet", action="store_true",
                   help="hide short-lived internal effects (0 <= duration < 1 s); keeps permanent (-1) and timed buffs")
    e.set_defaults(fn=cmd_effects)

    a = sub.add_parser("animations", help="live character animation state viewer for building chr_state_ids.json")
    a.add_argument("--offsets", default=offsets_default, help="offsets.json (default: <project>/offsets.json)")
    a.add_argument("--effects", default=effects_default, help="chr_state_ids.json (default: <project>/chr_state_ids.json)")
    a.add_argument("-q", "--quiet", action="store_true", help="quiet mode")
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

    args = ap.parse_args(argv)
    if args.cmd == "run" and not 1 <= args.hz <= 120:
        ap.error("--hz must be between 1 and 120")
    try:
        return args.fn(args)
    except (FileNotFoundError, OSError, ValueError, RuntimeError) as exc:
        _log(f"error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

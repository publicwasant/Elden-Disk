"""Development pipeline for EldenDisk: tests -> build `./build/dist/eldendisk.exe` -> status. It ends there; it does not start the game.

    python code/tools/dev_pipeline.py [--skip-tests] [--no-embed] [--engine pyinstaller|nuitka] [--icon ICO] [--keep-app-data]

1. Tests: runs the whole test suite (pytest); a failure stops the pipeline.
2. Build: compiles `./build/dist/eldendisk.exe` (PyInstaller; `--engine nuitka` for Nuitka). The build always starts clean
   (`./build` is removed first) and embeds offsets.json, chr_state_ids.json and extension.json in the exe; `--no-embed` leaves
   them next to the exe instead. It also removes the tool's own folder `%LOCALAPPDATA%\\EldenDisk` (the vault and its save
   snapshots, the extensions' files, the exports), never while a vault in it owes a restore or the game or the tool runs;
   `--keep-app-data` keeps it. A README.md (quick start + the exe's command reference, from `docs/guilde/`) is written next to
   the exe. Building the exe is a developer's job, so it lives here and not in the `eldendisk` command line.
3. Status: where the exe is, its size and SHA-256, the version, what was embedded, how long each step took, and the command
   that starts it. Everything the exe produces goes to `%LOCALAPPDATA%\\EldenDisk`, so the exe can be copied anywhere.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Resolve root directory
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent if SCRIPT_DIR.name == "tools" and SCRIPT_DIR.parent.name == "code" else SCRIPT_DIR.parent
if (ROOT_DIR / "code").exists():
    CODE_DIR = ROOT_DIR / "code"
else:
    CODE_DIR = ROOT_DIR

sys.path.insert(0, str(CODE_DIR))
from eldendisk import __version__, ui
from eldendisk.game.processes import find_pid
from eldendisk.paths import app_data_dir
from eldendisk.vault.session import LEGACY_MARKER_NAME, SESSION_NAME

ENGINES = ("pyinstaller", "nuitka")
EXE_NAME = "eldendisk.exe"
REL_EXE = "./build/dist/eldendisk.exe"


_TINT = re.compile(r"^(SUCCESS|ERROR|WARNING)\b|^(Step \d+/\d+)\b|^(Done)\b")
_TINT_KIND = {"SUCCESS": "ok", "ERROR": "error", "WARNING": "warn", "Done": "ok"}


def _tint(msg: str, color: bool) -> str:
    """The same colours as the tool's console: SUCCESS green, ERROR red, WARNING yellow, `Step n/2` and `Done` bold."""
    if not color:
        return msg
    m = _TINT.match(msg)
    if not m:
        return msg
    word = m.group(0)
    kind = _TINT_KIND.get(word, "bold")
    return ui.paint(word, kind, True) + msg[len(word):]


def log(msg: str) -> None:
    color = ui.use_color(sys.stdout)
    print(f"{ui.paint('[E2E Pipeline]', 'dim', color)} {_tint(msg, color)}", flush=True)


def tests_temp_dir() -> Path:
    """The tests' temporary files: a folder of their own in the system's temp folder (pytest clears it at the start of each run).
    Without it pytest keeps numbered folders and a `pytest-current` link in %TEMP%/pytest-of-<user>, and Windows may refuse to
    remove that link at exit ("Exception ignored in atexit callback ... PermissionError"). Not inside ./build: the tests make vaults
    that owe a restore on purpose, and the build's clean refuses to remove a folder that holds one."""
    return Path(tempfile.gettempdir()) / "eldendisk-pytest"


def run_precheck() -> bool:
    log("Step 1/2: Running the tests (pytest)...")
    cmd = [sys.executable, "-m", "pytest", f"--basetemp={tests_temp_dir()}"]
    res = subprocess.run(cmd, cwd=str(CODE_DIR))
    if res.returncode != 0:
        log("ERROR: the tests failed. Aborting pipeline.")
        return False
    log("SUCCESS: tests passed.")
    return True


# ---------------------------------------------------------------- building eldendisk.exe
def build_layout() -> dict:
    """Where everything is (worked out when called, so a test can point ROOT_DIR / CODE_DIR somewhere else)."""
    build_root = ROOT_DIR / "build"
    dist_dir = build_root / "dist"
    return {
        "code_dir": CODE_DIR,
        "project_root": ROOT_DIR,
        "build_root": build_root,
        "dist_dir": dist_dir,                       # the exe is dist_dir / eldendisk.exe
        "work_dir": build_root / "work",
        "entry_point": CODE_DIR / "eldendisk" / "__main__.py",
    }


def unresolved_sessions(build_root: Path) -> list[Path]:
    """Vaults under `build_root` that still owe a restore (a session record or a 1.6.0/1.6.1 marker)."""
    if not build_root.is_dir():
        return []
    names = (SESSION_NAME, LEGACY_MARKER_NAME)
    return sorted({f.parent for n in names for f in build_root.rglob(n) if f.is_file()})


GAME_EXE, TOOL_EXE = "eldenring.exe", "eldendisk.exe"


def _local_app_data() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) if base else Path.home() / "AppData" / "Local"


def app_data_problems(target: Path) -> list[str]:
    """Why `target` (the tool's folder %LOCALAPPDATA%\\EldenDisk: the vault with its save snapshots, the extensions' files, the exports)
    must not be removed now; [] when it may. Only that exact folder is ever removed; nothing while a vault in it owes a restore or
    while the game or the tool runs (a session in progress keeps the only clean copy of the save there)."""
    if target.name != "EldenDisk" or target.parent != _local_app_data() or target.is_symlink():
        return [f"{target} is not %LOCALAPPDATA%\\EldenDisk: not removed"]
    out = [f'unresolved session in {v}; run `eldendisk vault restore --vault "{v}"` first (or build with --keep-app-data)'
           for v in unresolved_sessions(target)]
    for exe in (GAME_EXE, TOOL_EXE):
        if find_pid(exe) is not None:
            out.append(f"{exe} is running: close it first (or build with --keep-app-data)")
    return out


def config_files(layout: dict) -> list[Path]:
    """offsets.json, chr_state_ids.json and the extensions' design extension.json (from code/ or the project root); only those
    that exist."""
    out = []
    for name in ("offsets.json", "chr_state_ids.json", "extension.json"):
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
        log(f"WARNING: icon file not found: {icon}")
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
               f"--output-filename={EXE_NAME}"]
        if icon_path:
            cmd.append(f"--windows-icon-from-ico={icon_path}")
        if embed:
            cmd += [f"--include-data-files={c}={c.name}" for c in configs]
    cmd.append(str(entry))
    return cmd


def exe_readme(layout: dict) -> str | None:
    """README.md for the folder of the exe: the intro `docs/guilde/README-exe.md` followed by `docs/guilde/cli-commands-exe.md`
    (the one source of the command reference). None when those files are not there (a source tree without docs/)."""
    docs = layout["project_root"] / "docs" / "guilde"
    try:
        intro = (docs / "README-exe.md").read_text(encoding="utf-8")
        reference = (docs / "cli-commands-exe.md").read_text(encoding="utf-8")
    except OSError:
        return None
    if reference.startswith("# "):      # its title becomes the "Command reference" heading of the intro
        reference = reference.split("\n", 1)[1].lstrip("\n") if "\n" in reference else ""
    return intro.replace("{version}", __version__).rstrip("\n") + "\n\n" + reference.rstrip("\n") + "\n"


def run_build(clean: bool = True, embed: bool = True, engine: str = "pyinstaller", icon: str | None = None,
              app_data: bool = False) -> bool:
    """Compile ./build/dist/eldendisk.exe. `clean` (the default) removes ./build first, except while a vault inside it still
    owes a restore. `app_data` (with `clean`; what the pipeline does unless --keep-app-data) also removes %LOCALAPPDATA%\\EldenDisk,
    the tool's own folder (the vault and its save snapshots, the extensions' files, the exports), except while a vault in it owes a
    restore or the game or the tool runs; nothing is removed when either check fails."""
    log(f"Step 2/2: Building standalone {EXE_NAME} for version {__version__} ({engine}, onefile; this takes a while)...")
    if engine not in ENGINES:
        log(f"ERROR: unsupported build engine '{engine}' (use one of: {', '.join(ENGINES)})")
        return False
    layout = build_layout()
    dist_dir = layout["dist_dir"]

    if clean:
        owed = unresolved_sessions(layout["build_root"])
        if owed:   # a vault someone put inside ./build: cleaning would destroy the only clean save
            for v in owed:
                log(f'ERROR: unresolved session in {v}; run `eldendisk vault restore --vault "{v}"` before cleaning')
            return False
        target = app_data_dir()
        if app_data and target.exists():
            problems = app_data_problems(target)
            if problems:
                for p in problems:
                    log(f"ERROR: {p}")
                return False
            log(f"cleaning the tool's own folder {target} (vault, save snapshots, extension files, exports)")
            try:
                shutil.rmtree(target)
            except OSError as exc:
                log(f"ERROR: could not remove all of {target}: {exc}")
                return False
        if layout["build_root"].exists():
            log("cleaning previous build artifacts")
            shutil.rmtree(layout["build_root"], ignore_errors=True)

    dist_dir.mkdir(parents=True, exist_ok=True)
    layout["work_dir"].mkdir(parents=True, exist_ok=True)
    configs = config_files(layout)
    cmd = build_command(engine, embed=embed, icon=icon, layout=layout, configs=configs)
    try:
        res = subprocess.run(cmd, check=False)
    except OSError as exc:
        log(f"ERROR: could not start the build: {exc}")
        return False
    if res.returncode != 0:
        log(f"ERROR: {engine} build failed. Aborting pipeline.")
        return False

    if not embed:  # editable configs travel next to the exe
        for c in configs:
            shutil.copy2(c, dist_dir / c.name)

    readme = exe_readme(layout)
    if readme is None:
        log("WARNING: docs/guilde/README-exe.md or docs/guilde/cli-commands-exe.md not found: no README.md next to the exe")
    else:
        try:
            (dist_dir / "README.md").write_text(readme, encoding="utf-8")
        except OSError as exc:
            log(f"WARNING: could not write README.md next to the exe: {exc}")

    log(f"SUCCESS: Executable compiled successfully: {REL_EXE}")
    return True


def _fmt_seconds(sec: float) -> str:
    m, r = divmod(sec, 60)
    return f"{int(m)} min {r:04.1f} s" if m else f"{r:.1f} s"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _path_text(text: str, color: bool, links: bool) -> str:
    """A path in the status: clickable (OSC 8) when the terminal supports it, its file name orange on a colour console."""
    if links:
        return ui.linkify(text, color=color)
    return ui.paint_tails(text) if color else text


def status_lines(*, layout: dict, engine: str, embed: bool, configs: list[Path], tests_s: float | None, build_s: float,
                 total_s: float, color: bool = False, links: bool = False) -> list[str]:
    """What the pipeline prints at the end (pure apart from reading the finished exe, so a test can check it).
    `color` / `links`: the look of the tool's console (dim labels, orange file names, clickable paths, cyan start command); both
    off gives plain text."""
    dist = layout["dist_dir"]
    exe = dist / EXE_NAME
    size = exe.stat().st_size
    rows = [
        ("exe", str(exe)),
        ("size", f"{size / (1 << 20):.1f} MB ({size:,} bytes)"),
        ("sha256", _sha256(exe)),
        ("version", f"{__version__} ({engine}, onefile)"),
        ("configs", (", ".join(c.name for c in configs) + (" embedded in the exe" if embed else f" copied next to the exe ({dist})"))
         if configs else "none found"),
        ("readme", str(dist / "README.md") if (dist / "README.md").exists() else "not written (no docs/guilde/)"),
        ("tests", "skipped" if tests_s is None else _fmt_seconds(tests_s)),
        ("build", _fmt_seconds(build_s)),
        ("total", _fmt_seconds(total_s)),
        ("data", f"{app_data_dir()} (the vault, the extensions' files and the exports; the exe can be copied anywhere)"),
        ("start it", f"{REL_EXE.replace('/', chr(92))} run -v"),
    ]
    width = max(len(k) for k, _ in rows)

    def value(key: str, v: str) -> str:
        if key in ("exe", "readme", "data"):
            return _path_text(v, color, links)
        if key == "sha256":
            return ui.paint(v, "dim", color)
        if key == "start it":
            return ui.paint(v, "cyan", color)
        return v
    return [f"  {ui.paint(k.ljust(width), 'dim', color)}  {value(k, v)}" for k, v in rows]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EldenDisk development pipeline: run the tests, then build "
                                     f"{REL_EXE}, then print where it is. It does not start the game.")
    parser.add_argument("--skip-tests", action="store_true", help="skip the tests")
    parser.add_argument("--no-embed", action="store_true",
                        help="do not embed offsets.json, chr_state_ids.json and extension.json in the exe (copy them next to it)")
    parser.add_argument("--engine", choices=ENGINES, default="pyinstaller", help="compiler for the exe (default: pyinstaller)")
    parser.add_argument("--icon", metavar="ICO", default=None, help="icon file (.ico) for the exe")
    parser.add_argument("--keep-app-data", action="store_true",
                        help="do not remove %%LOCALAPPDATA%%\\EldenDisk (the vault and its save snapshots, the extensions' files, the "
                             "exports) before the build; by default it is removed, never while a vault in it owes a restore or the game runs")
    args = parser.parse_args(argv)

    started = time.monotonic()
    tests_s = None
    if not args.skip_tests:
        if not run_precheck():
            return 1
        tests_s = time.monotonic() - started
    else:
        log("Step 1/2: tests skipped (--skip-tests)")

    t0 = time.monotonic()
    if not run_build(clean=True, embed=not args.no_embed, engine=args.engine, icon=args.icon, app_data=not args.keep_app_data):
        return 1
    build_s = time.monotonic() - t0

    layout = build_layout()
    log("Done:")
    color, links = ui.use_color(sys.stdout), ui.use_links(sys.stdout)
    for line in status_lines(layout=layout, engine=args.engine, embed=not args.no_embed, configs=config_files(layout),
                             tests_s=tests_s, build_s=build_s, total_s=time.monotonic() - started, color=color, links=links):
        print(line, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

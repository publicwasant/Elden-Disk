"""`build` (standalone eldendisk.exe) and `hash` (SHA-256 of eldenring.exe, the key for offsets.json)."""
from __future__ import annotations

import sys
from pathlib import Path

from .. import __version__
from ..logbook import book
from ..game.processes import GAME_EXE, sha256_file
from ..host.launcher import find_game_dir
from ..paths import HERE
from ..vault.recover import EXIT_RESTORE_PENDING
from ..vault.session import LEGACY_MARKER_NAME, SESSION_NAME


def _unresolved_sessions(build_root: Path) -> list[Path]:
    """Vaults under `build_root` that still owe a restore (a session record or a 1.6.0/1.6.1 marker)."""
    if not build_root.is_dir():
        return []
    names = (SESSION_NAME, LEGACY_MARKER_NAME)
    return sorted({f.parent for n in names for f in build_root.rglob(n) if f.is_file()})


def cmd_hash(args) -> int:
    d = find_game_dir(args.game_dir)
    digest = sha256_file(d / GAME_EXE)
    book.d("hash", f"{d / GAME_EXE}: {digest}")
    print(digest)   # the result, alone on stdout so that it can be piped
    return 0


def _build_layout() -> dict:
    code_dir = HERE
    project_root = code_dir.parent if code_dir.name == "code" else code_dir
    build_root = project_root / "build"
    dist_dir = build_root / "dist" / "eldendisk"
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
        book.w("build", f"icon file not found: {icon}")
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
        book.e("build", f"unsupported build engine '{args.engine}'")
        return 1

    layout = _build_layout()
    dist_dir = layout["dist_dir"]

    if args.clean:
        owed = _unresolved_sessions(layout["build_root"])
        if owed:   # the default vault of the built exe lives inside build/: cleaning would destroy the only clean save
            for v in owed:
                book.e("build", f'unresolved session in {v}; run `eldendisk vault restore --vault "{v}"` before cleaning')
            return EXIT_RESTORE_PENDING
        book.i("build", "cleaning previous build artifacts")
        if layout["build_root"].exists():
            shutil.rmtree(layout["build_root"], ignore_errors=True)

    dist_dir.mkdir(parents=True, exist_ok=True)
    layout["work_dir"].mkdir(parents=True, exist_ok=True)
    configs = _config_files(layout)
    label = "PyInstaller" if engine == "pyinstaller" else "Nuitka"
    book.i("build", f"building eldendisk.exe {__version__} with {label} (onefile); this takes a while")

    cmd = build_command(engine, embed=args.embed_configs, icon=args.icon, layout=layout, configs=configs)
    try:
        res = subprocess.run(cmd, check=False)
    except OSError as exc:
        book.e("build", f"could not start the build: {exc}")
        return 1
    if res.returncode != 0:
        book.e("build", f"{label} build failed")
        return 1

    if not args.embed_configs:  # editable configs travel next to the exe, for both engines
        for c in configs:
            shutil.copy2(c, dist_dir / c.name)

    rel_exe = "./build/dist/eldendisk/eldendisk.exe"
    book.ok("build", f"done: {rel_exe}")
    return 0

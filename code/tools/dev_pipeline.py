"""End-to-End (E2E) Development Run Pipeline for EldenDisk.

Execution Flow:
1. Pre-check: Executes unit tests to validate source code.
2. Build: Executes `python -m eldendisk build -c -em` (embedded configs; `--no-embed` to disable) to compile the executable.
3. Launch: Executes `./build/dist/eldendisk/eldendisk.exe run -v` (the live log; also kept in <vault>/eldendisk.log).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
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
from eldendisk import __version__


def log(msg: str) -> None:
    print(f"[E2E Pipeline] {msg}", flush=True)


def run_precheck() -> bool:
    log("Step 1/3: Running unit tests pre-check (pytest)...")
    cmd = [sys.executable, "-m", "pytest"]
    res = subprocess.run(cmd, cwd=str(CODE_DIR))
    if res.returncode != 0:
        log("ERROR: Unit tests pre-check failed. Aborting pipeline.")
        return False
    log("SUCCESS: Pre-check passed.")
    return True


def run_build(clean: bool = True, embed: bool = True) -> bool:
    log(f"Step 2/3: Building standalone eldendisk.exe for version {__version__}...")
    cmd = [sys.executable, "-m", "eldendisk", "build"]
    if clean:
        cmd.append("-c")
    if embed:
        cmd.append("-em")
    res = subprocess.run(cmd, cwd=str(CODE_DIR))
    if res.returncode != 0:
        log("ERROR: Build failed. Aborting pipeline.")
        return False
    log("SUCCESS: Executable compiled successfully.")
    return True


def run_launch(dry_run: bool = False) -> int:
    exe_path = ROOT_DIR / "build" / "dist" / "eldendisk" / "eldendisk.exe"
    if not exe_path.exists():
        log(f"ERROR: Executable not found at {exe_path}")
        return 1

    rel_path = "./build/dist/eldendisk/eldendisk.exe"
    if dry_run:
        log(f"Step 3/3: [Dry Run] Executing {rel_path} --help ...")
        cmd = [str(exe_path), "--help"]
    else:
        log(f"Step 3/3: Executing {rel_path} run -v ...")
        log(f"If this run is killed (IDE stop button), restore the save with: {exe_path} vault restore")
        cmd = [str(exe_path), "run", "-v"]

    return _run_exe(cmd)


def _exe_env() -> dict:
    """IDE run windows are not terminals but show ANSI colours: ask the exe for them (NO_COLOR still wins)."""
    env = dict(os.environ)
    if "NO_COLOR" not in env:
        env.setdefault("FORCE_COLOR", "1")
    return env


def _run_exe(cmd: list[str], attempts: int = 10, delay: float = 1.5) -> int:
    """Start the freshly built exe. Right after the build, Windows Defender (or another scanner) often still holds the
    new file and CreateProcess fails with [WinError 5] Access is denied; that passes within a few seconds, so retry."""
    for i in range(1, attempts + 1):
        try:
            return subprocess.run(cmd, env=_exe_env()).returncode
        except PermissionError as exc:
            if i == attempts:
                log(f"ERROR: cannot start the executable after {attempts} tries ({exc}). "
                    "Check antivirus quarantine / exclusions for the build folder.")
                return 1
            log(f"executable still locked ({exc}); retry {i}/{attempts - 1} in {delay:g}s ...")
            time.sleep(delay)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="EldenDisk E2E Development Run Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="run dry-run help check instead of full game launch")
    parser.add_argument("--skip-tests", action="store_true", help="skip pre-check unit tests")
    parser.add_argument("--no-embed", action="store_true", help="do not embed configuration files during build")
    args = parser.parse_args()

    if not args.skip_tests:
        if not run_precheck():
            return 1

    if not run_build(clean=True, embed=not args.no_embed):
        return 1

    return run_launch(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())

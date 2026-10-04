"""End-to-End (E2E) Development Run Pipeline for EldenDisk.

Execution Flow:
1. Pre-check: Executes unit tests to validate source code.
2. Build: Executes `python -m eldendisk build -c -em` to compile standalone executable.
3. Launch: Executes `./dist/eldendisk.exe run -v` to launch telemetry via compiled binary.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Resolve root directory
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent if SCRIPT_DIR.name == "tools" and SCRIPT_DIR.parent.name == "code" else SCRIPT_DIR.parent
if (ROOT_DIR / "code").exists():
    CODE_DIR = ROOT_DIR / "code"
else:
    CODE_DIR = ROOT_DIR


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
    log("Step 2/3: Building standalone eldendisk.exe...")
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
    exe_path = ROOT_DIR / "dist" / "eldendisk.exe"
    if not exe_path.exists():
        log(f"ERROR: Executable not found at {exe_path}")
        return 1

    if dry_run:
        log("Step 3/3: [Dry Run] Executing ./dist/eldendisk.exe --help ...")
        cmd = [str(exe_path), "--help"]
    else:
        log("Step 3/3: Executing ./dist/eldendisk.exe run -v ...")
        cmd = [str(exe_path), "run", "-v"]

    res = subprocess.run(cmd)
    return res.returncode


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

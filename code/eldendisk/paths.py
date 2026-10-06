"""Where the tool lives and where its files go: runtime folders (script / PyInstaller / Nuitka), config lookup, defaults."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent   # <project>/code when run from source


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


def default_out_dir() -> str:
    external_dir, _ = runtime_dirs()
    return str((external_dir or HERE) / "output")

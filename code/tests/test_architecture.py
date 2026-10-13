"""Module boundaries of spec 1.6.2 section 2, enforced over the imports of every module (lazy ones included)."""
import ast
import importlib
from pathlib import Path

import pytest

import eldendisk

PKG = Path(eldendisk.__file__).parent

# top-level package -> internal prefixes it may import (anything else inside `eldendisk` is a violation)
ALLOWED = {
    "vault": ["eldendisk.vault"],
    "game": ["eldendisk.game"],
    "host": ["eldendisk.host", "eldendisk.vault", "eldendisk.paths", "eldendisk.game.processes"],
    "reader": ["eldendisk.reader", "eldendisk.game", "eldendisk.paths", "eldendisk.vault.session"],
    "writer": ["eldendisk.writer", "eldendisk.game", "eldendisk.vault.session"],
    "design": ["eldendisk.design"],        # builds files; knows nothing of the vault, the host or the game
}

# the files that may go past their package's boundary, and how far. 1.7.2: the external scripts (design/external_scripts) run next to
# the game, so ONE file of them touches it: backend.py, which reads through the reader and writes through the writer of `read` and
# `write` (the same chains, checks, gate and session). edstdlib, the host and the scripts themselves still see only the design package.
EXCEPTIONS = {
    "design/external_scripts/backend.py": ["eldendisk.game", "eldendisk.reader", "eldendisk.writer", "eldendisk.vault"],
}


def modules():
    return sorted(p for p in PKG.rglob("*.py") if "__pycache__" not in p.parts)


def dotted(path: Path) -> list[str]:
    parts = ["eldendisk", *path.relative_to(PKG).with_suffix("").parts]
    return parts[:-1] if parts[-1] == "__init__" else parts


def internal_imports(path: Path) -> set[str]:
    """Absolute dotted names of every `eldendisk` module the file imports."""
    is_pkg = path.name == "__init__.py"
    here = dotted(path)
    package = here if is_pkg else here[:-1]
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - (node.level - 1)]
                mod = ".".join(base + ([node.module] if node.module else []))
            else:
                mod = node.module or ""
            found.add(mod)
            for a in node.names:   # `from pkg import module` imports pkg.module
                sub = PKG.parent.joinpath(*mod.split("."), a.name)
                if sub.with_suffix(".py").exists() or sub.is_dir():
                    found.add(f"{mod}.{a.name}")
    return {m for m in found if m == "eldendisk" or m.startswith("eldendisk.")}


def under(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + ".")


@pytest.mark.parametrize("path", [p for p in modules() if len(dotted(p)) > 1 and dotted(p)[1] in ALLOWED],
                         ids=lambda p: p.relative_to(PKG).as_posix())
def test_package_imports_stay_inside_their_boundary(path):
    owner = dotted(path)[1]
    allowed = ALLOWED[owner] + EXCEPTIONS.get(path.relative_to(PKG).as_posix(), [])
    bad = sorted(m for m in internal_imports(path)
                 if m != "eldendisk" and not any(under(m, a) for a in allowed))
    assert not bad, f"{path.relative_to(PKG).as_posix()} ({owner}) must not import {bad}"


def test_the_rules_actually_see_imports():
    assert "eldendisk.game.memory" in internal_imports(PKG / "game" / "attach.py")
    assert "eldendisk.vault" in internal_imports(PKG / "host" / "host.py")
    assert "eldendisk.writer.writer" in internal_imports(PKG / "commands" / "write.py")


def test_the_host_and_the_vault_never_open_the_game():
    for sub in ("host", "vault"):
        for f in (PKG / sub).rglob("*.py"):
            text = f.read_text(encoding="utf-8")
            for word in ("ProcessMemory", "ReadProcessMemory", "PROCESS_VM_READ", "game.memory", "game.layout"):
                assert word not in text, f"{f.relative_to(PKG).as_posix()} mentions {word}"


def test_only_the_write_command_the_scripts_backend_and_the_writer_package_touch_the_writer():
    """`write`, and since 1.7.2 the backend of the external scripts (it writes through the same MemoryWriter, after the same session
    check, and checks the session again while the scripts run)."""
    users = {p.relative_to(PKG).as_posix() for p in modules()
             if any(under(m, "eldendisk.writer") for m in internal_imports(p)) and "writer" not in p.relative_to(PKG).parts[:1]}
    assert users == {"commands/write.py", "design/external_scripts/backend.py"}


def test_the_reader_never_imports_the_writer_and_the_writer_never_imports_the_reader():
    for f in (PKG / "reader").rglob("*.py"):
        assert not any(under(m, "eldendisk.writer") for m in internal_imports(f)), f
    for f in (PKG / "writer").rglob("*.py"):
        assert not any(under(m, "eldendisk.reader") for m in internal_imports(f)), f


@pytest.mark.parametrize("path", modules(), ids=lambda p: p.relative_to(PKG).as_posix())
def test_every_module_imports(path):
    name = ".".join(dotted(path))
    if name.endswith("__main__"):
        pytest.skip("entry point")
    importlib.import_module(name)


def test_no_stale_top_level_modules():
    top = {p.name for p in PKG.glob("*.py")}
    assert top == {"__init__.py", "__main__.py", "console.py", "logbook.py", "logsetup.py", "paths.py", "ui.py"}


def test_the_engines_never_see_the_console_or_the_logbook():
    """Vault, host, game, reader and writer report through injected callables; only commands and the CLI own the console."""
    for pkg in ALLOWED:
        for f in (PKG / pkg).rglob("*.py"):
            bad = [m for m in internal_imports(f) if m in ("eldendisk.logbook", "eldendisk.ui", "eldendisk.logsetup")]
            assert not bad, f"{f.relative_to(PKG).as_posix()} imports {bad}"


def test_the_design_package_uses_only_the_standard_library():
    """The exe is built without third-party packages; cryptography, zstandard and jsonschema are for the dev tests only."""
    import sys
    std = set(sys.stdlib_module_names)
    for f in (PKG / "design").rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module] if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module else []
            for n in names:     # `edstdlib` is the external scripts' own name for design/external_scripts/edstdlib.py
                assert n.split(".")[0] in std | {"eldendisk", "edstdlib"}, f"{f.relative_to(PKG).as_posix()} imports {n}"

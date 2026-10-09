"""gate.second_decode: the optional second decoder is imported by name inside try, never a plain import (stdlib-only rule
and Python 3.13 has no compression.zstd). The rest of the gate needs the real file: see test_ext_golden.py."""
import sys
import types

from eldendisk.extension.innovate_spells import gate


def test_without_the_module_it_is_only_a_note(monkeypatch):
    monkeypatch.setitem(sys.modules, "compression.zstd", None)       # import raises ImportError
    assert gate.second_decode(b"x") == ("unavailable", None)


def test_a_working_module_returns_its_bytes(monkeypatch):
    fake = types.ModuleType("compression.zstd")
    fake.decompress = lambda frame: frame[::-1]
    monkeypatch.setitem(sys.modules, "compression", types.ModuleType("compression"))
    monkeypatch.setitem(sys.modules, "compression.zstd", fake)
    assert gate.second_decode(b"abc") == ("ok", b"cba")


def test_a_module_that_raises_is_an_error_not_a_crash(monkeypatch):
    fake = types.ModuleType("compression.zstd")

    def boom(frame):
        raise ValueError("corrupt")

    fake.decompress = boom
    monkeypatch.setitem(sys.modules, "compression", types.ModuleType("compression"))
    monkeypatch.setitem(sys.modules, "compression.zstd", fake)
    assert gate.second_decode(b"abc") == ("error", "corrupt")


def test_ids_are_compared_exactly_and_seconds_with_a_float32_tolerance():
    from eldendisk.extension.innovate_spells.recipes import _same
    assert not _same(21950112, 21950111) and _same(21950111.0, 21950111) and not _same(80.5, 80)
    assert _same(0.5, 0.5) and _same(0.5000001, 0.5) and not _same(0.51, 0.5) and _same(15.0, 15)

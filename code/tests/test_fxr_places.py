"""tools/fxr_places.py: where the colours of an effect file (FXR version 5) sit, on a small file made here."""
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import fxr_places  # noqa: E402

P6, P7, FIELDS = 0x100, 0x200, 0x400


def fxr(props, actions, fields: bytes, version=5) -> bytes:
    """A file with these properties [(type, field count, field offset)], actions [(id, first fields, second fields, offset)] and
    the field bytes at FIELDS."""
    d = bytearray(FIELDS + len(fields))
    d[0:4] = b"FXR\0"
    struct.pack_into("<HHii", d, 4, 0, version, 1, 301262)
    pairs = [0] * 22
    pairs[10:12] = [P6, len(actions)]
    pairs[12:14] = [P7, len(props)]
    struct.pack_into("<22i", d, 0x10, *pairs)
    for i, (ta, fc, fo) in enumerate(props):
        struct.pack_into("<hBBiiiii", d, P7 + 40 * i, ta, 0, 1, 0, fc, 0, fo, 0)
    for i, (aid, f1, f2, fo) in enumerate(actions):
        struct.pack_into("<iiiiiiiii", d, P6 + 64 * i, 0x1000000 + aid, 0, f1, 0, f2, 0, 0, 0, fo)
    d[FIELDS:] = fields
    return bytes(d)


def floats(*v):
    return struct.pack("<%df" % len(v), *v)


def test_constant_and_linear_colours_and_the_bloom_of_a_drawing_action():
    gold, white = (0.875, 0.75, 0.44, 1.0), (1.0, 1.0, 1.0, 1.0)
    const = floats(*gold)                                                           # FIELDS + 0
    linear = struct.pack("<i", 2) + floats(*gold, *white) + floats(0.0, 1.0) + floats(*white, *gold)   # FIELDS + 16
    action = floats(0, 0, 0) + floats(0, 0, 0, 0, 0, 1.0, 0.75, 0.5, 0.5, 0)       # FIELDS + 92: 3 first fields, 10 second
    other = floats(0, 0) + floats(*([0.5] * 10))                                    # FIELDS + 144: a light (609) is not a bloom
    d = fxr([(0x23, 4, FIELDS), (0x43, 19, FIELDS + 16), (0x10, 1, FIELDS), (0x13, 0, 0)],
            [(604, 3, 10, FIELDS + 92), (609, 2, 10, FIELDS + 144)], const + linear + action + other)
    assert fxr_places.places(d) == [(FIELDS, False), (FIELDS + 20, False), (FIELDS + 36, False),       # the colour; min; max
                                    (FIELDS + 60, False), (FIELDS + 76, False),                        # the two keys
                                    (FIELDS + 92 + 12 + 20, True)]                                     # the bloom
    assert d[FIELDS + 76:FIELDS + 92] == floats(*gold)


def test_an_effect_file_of_another_version_or_a_broken_colour_is_refused():
    with pytest.raises(fxr_places.FxrError, match="version 5"):
        fxr_places.places(fxr([], [], b"", version=4))
    with pytest.raises(fxr_places.FxrError, match="keys"):
        fxr_places.places(fxr([(0x43, 19, FIELDS)], [], struct.pack("<i", 9) + bytes(72)))


def test_the_plan_text_is_what_writer_fxr_plans_holds(tmp_path, capsys):
    f = tmp_path / "f000301262.fxr"
    f.write_bytes(fxr([(0x23, 4, FIELDS)], [], floats(0.875, 0.75, 0.44, 1.0)))
    assert fxr_places.main([str(f)]) == 0
    out = capsys.readouterr().out
    assert out.startswith('    "301262": {') and "(0x400, \"0000603f0000403fae47e13e0000803f\", False)," in out

"""tools/dump_tae.py: a small TAE file built here (the layout of the format notes), read back."""
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import dump_tae as dt  # noqa: E402


def build_tae(anims):
    """anims: {animation id: [(start, end, type, [numbers])]} -> the bytes of a TAE file (header 0xB8 long, then the tables)."""
    body = bytearray()
    base = 0xC0

    def here():
        return base + len(body)

    table_at = here()
    body += b"\0" * (16 * len(anims))
    entries = []
    for anim_id, events in anims.items():
        heads_at = here()
        body += b"\0" * (24 * len(events))
        for k, (start, end, kind, nums) in enumerate(events):
            t0 = here(); body += struct.pack("<f", start)
            t1 = here(); body += struct.pack("<f", end)
            d = here(); body += struct.pack("<qq", kind, d + 16) + struct.pack(f"<{len(nums)}i", *nums)
            struct.pack_into("<qqq", body, heads_at - base + 24 * k, t0, t1, d)
        anim_at = here()
        body += struct.pack("<qqqqiiii", heads_at, 0, 0, 0, len(events), 0, 0, 0)
        entries.append((anim_id, anim_at))
    for i, (anim_id, anim_at) in enumerate(entries):
        struct.pack_into("<qq", body, table_at - base + 16 * i, anim_id, anim_at)
    head = bytearray(base)
    head[:4] = b"TAE "
    struct.pack_into("<I", head, 0x08, 0x1000C)
    struct.pack_into("<i", head, 0x50, 2000)                  # the file's own id
    struct.pack_into("<i", head, 0x54, len(anims))
    struct.pack_into("<q", head, 0x58, table_at)
    return bytes(head + body)


def test_events_are_read_with_animation_times_type_and_numbers():
    blob = build_tae({7000: [(0.5, 0.6, 96, [524400, 7, 0]), (1.0, 1.0, 0, [1, 2])],
                      7001: [(0.0, 2.0, 96, [8010, 3] + [0] * 8)]})
    ev = dt.parse_tae(blob)
    assert [(e.animation, e.kind) for e in ev] == [(7000, 96), (7000, 0), (7001, 96)]
    assert ev[0].start == pytest.approx(0.5) and ev[0].end == pytest.approx(0.6) and ev[0].ints[:3] == (524400, 7, 0)
    assert ev[2].ints[:2] == (8010, 3)


def test_wanted_needs_an_id_that_exists():
    e = dt.Event(1, 0, 1, 96, (524400, 3, 0))
    assert dt.wanted(e, {524400}) and not dt.wanted(e, {524401}) and not dt.wanted(e, set())


def test_refusals_say_what_is_wrong():
    blob = bytearray(build_tae({1: [(0, 1, 96, [5])]}))
    with pytest.raises(dt.TaeError, match="not a TAE"):
        dt.parse_tae(b"BND4" + bytes(200))
    bad = bytearray(blob); struct.pack_into("<I", bad, 0x08, 0x10000)
    with pytest.raises(dt.TaeError, match="version"):
        dt.parse_tae(bytes(bad))
    # the data link of the first event no longer points 16 bytes after the type
    anim_at = struct.unpack_from("<q", blob, 0xC0 + 8)[0]
    heads = struct.unpack_from("<q", blob, anim_at)[0]
    data = struct.unpack_from("<q", blob, heads + 16)[0]
    bad = bytearray(blob); struct.pack_into("<q", bad, data + 8, 5)
    with pytest.raises(dt.TaeError, match="data link"):
        dt.parse_tae(bytes(bad))
    with pytest.raises(dt.TaeError):
        dt.parse_tae(bytes(blob[:0xC8]))


def test_candidates_start_with_the_main_file():
    c = dt.candidates()
    assert c == ["/chr/c0000.anibnd.dcx"]
    c = dt.candidates(True)
    assert c[0] == "/chr/c0000.anibnd.dcx" and "/chr/c0000_a00_lo.anibnd.dcx" in c and len(c) == 301


def test_a_file_without_animations_has_no_events():
    head = bytearray(0xC0)
    head[:4] = b"TAE "
    struct.pack_into("<I", head, 0x08, 0x1000C)
    struct.pack_into("<i", head, 0x50, 2107)
    assert dt.parse_tae(bytes(head)) == []


def test_the_header_of_a_real_file_is_read_at_the_right_place():
    # what the real files showed: id at 0x50, then the count and the 64-bit table offset (0x110)
    head = bytearray(0x120)
    head[:4] = b"TAE "
    struct.pack_into("<I", head, 0x08, 0x1000C)
    struct.pack_into("<iiq", head, 0x50, 2041, 33, 0x110)
    with pytest.raises(dt.TaeError, match="read past the end|unexpected"):
        dt.parse_tae(bytes(head[:0x100]))          # 33 animations announced, table beyond the end of this short file

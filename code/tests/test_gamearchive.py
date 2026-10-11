"""tools/gamearchive.py, the game archive reader (Data0-3.bhd/.bdt): AES-128-ECB vector, path hash, index parsing, one file read. No game files needed."""
import io
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import gamearchive as archive  # noqa: E402

P = bytes.fromhex("00112233445566778899aabbccddeeff")


def test_ecb_aes128_fips197():
    key = bytes(range(16))
    assert archive.ecb_decrypt(key, bytes.fromhex("69c4e0d86a7b0430d8cdb78070b4c55a")) == P


def test_ecb_rejects_partial_block_and_odd_key():
    with pytest.raises(ValueError):
        archive.ecb_decrypt(bytes(16), b"x" * 15)
    with pytest.raises(ValueError):
        archive.ecb_decrypt(bytes(32), bytes(16))


def test_path_hash_is_case_blind_and_uses_the_multiplier():
    assert archive.path_hash("/Msg/EngUS/Item.msgbnd.dcx") == archive.path_hash("/msg/engus/item.msgbnd.dcx")
    assert archive.path_hash("ab") == ord("a") * 0x85 + ord("b")


def _index(entries):
    """A BHD5 with one bucket: entries = [(hash, size, offset, key, ranges)]."""
    head = bytearray(b"BHD5") + struct.pack("<4B", 0xFF, 1, 0, 0) + struct.pack("<5i", 1, 0, 1, 36, 8)
    head += b"\0" * 8                                  # salt -> the bucket table sits at 36
    table_at = len(head)
    body = bytearray(8)                                  # bucket: count, offset
    entries_at = table_at + 8
    aes_at = entries_at + 40 * len(entries)
    blobs = bytearray()
    out = bytearray()
    for h, size, off, key, ranges in entries:
        at = aes_at + len(blobs) if key else 0
        out += struct.pack("<QiiQQQ", h, size, 0, off, 0, at)
        if key:
            blobs += key + struct.pack("<i", len(ranges)) + b"".join(struct.pack("<qq", *r) for r in ranges)
    struct.pack_into("<ii", body, 0, len(entries), entries_at)
    return bytes(head) + bytes(body) + bytes(out) + bytes(blobs)


def test_parse_index_and_read_entry():
    key = bytes(range(16))
    cipher = bytes.fromhex("69c4e0d86a7b0430d8cdb78070b4c55a")
    plain_tail = b"T" * 16
    bdt = io.BytesIO(b"\xAA" * 32 + cipher + plain_tail)             # the file starts at 32; only the first block is encrypted
    h = archive.path_hash("/msg/engUS/item.msgbnd.dcx")
    idx = archive.parse_index(_index([(h, 32, 32, key, [(0, 16)]), (7, 16, 0, b"", [])]))
    assert set(idx) == {h, 7}
    assert archive.read_entry(bdt, idx[h]) == P + plain_tail
    assert idx[7].aes_key == b"" and idx[7].ranges == ()


def test_read_entry_refuses_a_short_bdt():
    entry = archive.Entry(1, 64, 0, b"", ())
    with pytest.raises(archive.ArchiveError):
        archive.read_entry(io.BytesIO(b"x" * 8), entry)


def test_decrypt_index_refuses_the_wrong_key():
    with pytest.raises(archive.ArchiveError):
        archive.decrypt_index(bytes(256), (3233, 17))      # toy modulus: 256 bytes of zero never give BHD5

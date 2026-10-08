"""The building blocks of customize-items on synthetic data: AES, FSE sequence coding, zstd frames, block rewriting,
BND4/PARAM containers, field definitions."""
import random
import struct

import pytest

from eldendisk.extension.customize_items import aes, container, fse, reblock, zstd
from eldendisk.extension.customize_items.defs import Def
from tests import ext_helpers as H


# ---------------- AES ----------------
def test_aes256_fips_197_vector():
    key = bytes(range(32))
    pt = bytes.fromhex("00112233445566778899aabbccddeeff")
    ct = bytes.fromhex("8ea2b7ca516745bfeafc49904b496089")
    assert aes.cbc_encrypt(key, bytes(16), pt) == ct and aes.cbc_decrypt(key, bytes(16), ct) == pt


def test_aes_cbc_matches_the_cryptography_library_and_roundtrips():
    ciph = pytest.importorskip("cryptography.hazmat.primitives.ciphers")
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    rnd = random.Random(3)
    key, iv, data = (bytes(rnd.randrange(256) for _ in range(n)) for n in (32, 16, 16 * 50))
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ref = enc.update(data) + enc.finalize()
    assert aes.cbc_encrypt(key, iv, data) == ref and aes.cbc_decrypt(key, iv, ref) == data


# ---------------- FSE sequence coding ----------------
def test_sequence_section_roundtrips_and_decodes_like_a_real_zstd():
    rnd = random.Random(11)
    for trial in range(5):
        frame, body = H.make_frame(seed=trial, blocks=2)
        assert zstd.decode_frame(frame) == body                               # our decoder
        zs = pytest.importorskip("zstandard")
        assert zs.ZstdDecompressor().decompressobj().decompress(frame) == body   # the reference decoder


def test_encode_sequences_triples_roundtrip():
    rnd = random.Random(5)
    seqs = [(rnd.randint(0, 400), rnd.randint(3, 300), rnd.randint(4, 70000)) for _ in range(300)]
    sec = fse.encode_sequences(seqs)
    got, _ = fse.decode_triples(sec)
    assert got == seqs


# ---------------- reblock.rewrite ----------------
def _source(blocks=14, seed=7):
    # the number of blocks is chosen so that raw-literal header forms give the tail some play
    frame, body = H.make_frame(seed=seed, blocks=blocks)
    return reblock.Source(H.dcx_of(frame, body)), body


def _changed(body, spots):
    b = bytearray(body)
    for pos in spots:
        b[pos] ^= 0x5A
    return bytes(b)


def test_rewrite_keeps_untouched_blocks_and_decodes_to_the_new_body():
    src, body = _source()
    assert src.body == body
    new = _changed(body, [3 * reblock.BS + 100, 3 * reblock.BS + 40000])
    frame, edit, converted = reblock.rewrite(src, new)
    assert 3 in edit and zstd.decode_frame(frame) == new
    blocks, end = zstd.split_blocks(frame)
    assert end == len(frame) and all(t == 2 for _p, t, _s, _l in blocks[:-1])      # compressed blocks only, plus the empty last
    assert blocks[-1][1:3] == (0, 0)
    ob = {i: src.content(i) for i in range(len(src.blocks))}
    same = [i for i, (p, t, s, l) in enumerate(blocks) if frame[p + 3:p + 3 + s] == ob[i]]
    assert {0, 1, 2} <= set(same)                                                  # blocks before the edit are byte-identical
    zs = pytest.importorskip("zstandard")
    assert zs.ZstdDecompressor().decompressobj().decompress(frame) == new          # an independent decoder agrees


def test_rewrite_shapes_the_tail_like_the_original_and_is_deterministic():
    src, body = _source(blocks=16, seed=21)
    new = _changed(body, [reblock.BS * 5 + 7])
    f1, _, _ = reblock.rewrite(src, new)
    f2, _, _ = reblock.rewrite(src, new)
    assert f1 == f2 and (0x4C + len(f1)) % 16 == 16 - reblock.TAIL_ZEROS


def test_rewrite_of_an_unchanged_body_returns_the_original_frame():
    src, body = _source()
    frame, edit, conv = reblock.rewrite(src, body)
    assert frame == src.frame and not edit and not conv


def test_rewrite_refuses_a_body_of_another_length():
    src, body = _source()
    with pytest.raises(reblock.BuildError):
        reblock.rewrite(src, body + b"x")


def test_source_refuses_a_wrong_header_or_trailing_bytes():
    frame, body = H.make_frame()
    dcx = bytearray(H.dcx_of(frame, body))
    bad = bytearray(dcx)
    bad[0x28:0x2C] = b"DFLT"
    with pytest.raises(reblock.BuildError):
        reblock.Source(bytes(bad))
    bad = bytearray(dcx)
    bad[-1] = 1
    with pytest.raises(reblock.BuildError):
        reblock.Source(bytes(bad))


# ---------------- containers ----------------
def test_encrypt_decrypt_is_deterministic_and_checks_the_magic():
    dcx = b"DCX\0" + bytes(range(60))
    a, b = container.encrypt(dcx), container.encrypt(dcx)
    assert a == b and container.decrypt(a)[:len(dcx)] == dcx and len(a) % 16 == 0
    assert container.encrypt(dcx + b"x") != a
    with pytest.raises(container.ContainerError):
        container.decrypt(container.encrypt(b"NOPE" + bytes(60)))
    with pytest.raises(container.ContainerError):
        container.decrypt(b"short")


def test_param_roundtrip_find_and_sort():
    rows = [(i, bytes([i]) * 16) for i in (1, 5, 9)]
    blob = H.param_blob(rows)
    p = container.Param(blob)
    assert p.build() == blob and p.find(5)[2] == bytearray(bytes([5]) * 16) and p.find(6) is None
    p.find(9)[0] = 3                                                        # relabel, as the recipes do
    out = container.Param(p.build())
    assert out.ids() == [1, 3, 5] and out.find(3)[2] == bytearray(bytes([9]) * 16)


def test_param_refuses_unsorted_or_inconsistent_files():
    with pytest.raises(container.ContainerError):
        container.Param(H.param_blob([(5, bytes(16)), (1, bytes(16))]))
    p = container.Param(H.param_blob([(1, bytes(16))]))
    p.rows.append([2, 0, bytearray(16)])
    with pytest.raises(container.ContainerError):
        p.build()                                                           # the row count must not change


def test_bnd4_roundtrip_and_lookup():
    blob = H.bnd4_blob([("N:\\GR\\data\\Param\\Magic.param", b"a" * 40), ("N:\\GR\\data\\Param\\Other.param", b"b" * 33),
                        ("N:\\GR\\data\\Param\\Last.param", b"c" * 7)])
    b = container.Bnd4(blob)
    assert b.build() == blob and b.get("Other").data == b"b" * 33
    b.get("Magic").data = b"z" * 40
    assert container.Bnd4(b.build()).get("Magic").data == b"z" * 40
    with pytest.raises(container.ContainerError):
        b.get("Missing")


# ---------------- field definitions ----------------
def test_defs_set_get_and_bitfields_do_not_disturb_neighbours():
    d = Def("magic")
    row = bytearray(d.size)
    d.set(row, "mp", 80)
    d.set(row, "requirementLuck", 10)
    d.set(row, "isEnchant", 1)
    assert (d.get(row, "mp"), d.get(row, "requirementLuck"), d.get(row, "isEnchant")) == (80, 10, 1)
    d.set(row, "isShieldEnchant", 1)
    d.set(row, "isEnchant", 0)
    assert d.get(row, "isShieldEnchant") == 1 and d.get(row, "isEnchant") == 0
    sp = Def("sp")
    r2 = bytearray(sp.size)
    sp.set(r2, "effectEndurance", 15.0)
    assert sp.get(r2, "effectEndurance") == 15.0
    with pytest.raises(KeyError):
        d.set(row, "nope", 1)


def test_the_definitions_have_the_sizes_of_the_game_rows():
    assert {k: Def(k).size for k in ("goods", "magic", "sp", "shop")} == {"goods": 176, "magic": 168, "sp": 912, "shop": 52}

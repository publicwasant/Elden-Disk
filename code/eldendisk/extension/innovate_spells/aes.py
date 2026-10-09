"""AES-256 in CBC mode, standard library only (the game's regulation.bin is AES-256-CBC, IV = first 16 bytes).

A table-driven implementation: slow next to a C library (about a dozen seconds for the 2 MB file), but it needs
nothing outside the standard library and behaves the same on every platform, which is what the tests rely on.
"""
from __future__ import annotations

import struct


def _xtime(a: int) -> int:
    a <<= 1
    return (a ^ 0x11B) & 0xFF if a & 0x100 else a


def _build_tables():
    # S-box from the multiplicative inverse in GF(2^8) plus the affine transform
    sbox = [0] * 256
    p = q = 1
    while True:
        p = p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)           # p *= 3
        q ^= q << 1
        q ^= q << 2
        q ^= q << 4
        q &= 0xFF
        if q & 0x80:
            q ^= 0x09
        x = q ^ ((q << 1) | (q >> 7)) & 0xFF ^ ((q << 2) | (q >> 6)) & 0xFF ^ ((q << 3) | (q >> 5)) & 0xFF ^ ((q << 4) | (q >> 4)) & 0xFF
        sbox[p] = (x ^ 0x63) & 0xFF
        if p == 1:
            break
    sbox[0] = 0x63
    inv = [0] * 256
    for i, s in enumerate(sbox):
        inv[s] = i

    def mul(a, b):
        r = 0
        while b:
            if b & 1:
                r ^= a
            a = _xtime(a)
            b >>= 1
        return r

    te = [[0] * 256 for _ in range(4)]
    td = [[0] * 256 for _ in range(4)]
    for i in range(256):
        s = sbox[i]
        w = (mul(s, 2) << 24) | (s << 16) | (s << 8) | mul(s, 3)
        v = inv[i]
        d = (mul(v, 14) << 24) | (mul(v, 9) << 16) | (mul(v, 13) << 8) | mul(v, 11)
        for k in range(4):
            te[k][i] = w
            td[k][i] = d
            w = ((w >> 8) | (w << 24)) & 0xFFFFFFFF
            d = ((d >> 8) | (d << 24)) & 0xFFFFFFFF
    return sbox, inv, te, td


SBOX, INV_SBOX, TE, TD = _build_tables()


def _expand_key(key: bytes) -> list[int]:
    if len(key) != 32:
        raise ValueError("AES-256 needs a 32-byte key")
    nk, rounds = 8, 14
    w = list(struct.unpack(">8I", key))
    rcon = 1
    for i in range(nk, 4 * (rounds + 1)):
        t = w[i - 1]
        if i % nk == 0:
            t = ((t << 8) | (t >> 24)) & 0xFFFFFFFF
            t = (SBOX[t >> 24] << 24) | (SBOX[(t >> 16) & 255] << 16) | (SBOX[(t >> 8) & 255] << 8) | SBOX[t & 255]
            t ^= rcon << 24
            rcon = _xtime(rcon)
        elif i % nk == 4:
            t = (SBOX[t >> 24] << 24) | (SBOX[(t >> 16) & 255] << 16) | (SBOX[(t >> 8) & 255] << 8) | SBOX[t & 255]
        w.append(w[i - nk] ^ t)
    return w


def _inv_mix_word(x: int) -> int:
    # InvMixColumns of one word through the decryption tables (which already contain it)
    return (TD[0][SBOX[x >> 24]] ^ TD[1][SBOX[(x >> 16) & 255]] ^ TD[2][SBOX[(x >> 8) & 255]] ^ TD[3][SBOX[x & 255]])


def _decrypt_keys(ek: list[int]) -> list[int]:
    dk = []
    for r in range(14, -1, -1):
        row = ek[4 * r:4 * r + 4]
        dk += row if r in (0, 14) else [_inv_mix_word(x) for x in row]
    return dk


def _encrypt_block(ek, s0, s1, s2, s3):
    te0, te1, te2, te3, sb = TE[0], TE[1], TE[2], TE[3], SBOX
    s0 ^= ek[0]; s1 ^= ek[1]; s2 ^= ek[2]; s3 ^= ek[3]
    k = 4
    for _ in range(13):
        t0 = te0[s0 >> 24] ^ te1[(s1 >> 16) & 255] ^ te2[(s2 >> 8) & 255] ^ te3[s3 & 255] ^ ek[k]
        t1 = te0[s1 >> 24] ^ te1[(s2 >> 16) & 255] ^ te2[(s3 >> 8) & 255] ^ te3[s0 & 255] ^ ek[k + 1]
        t2 = te0[s2 >> 24] ^ te1[(s3 >> 16) & 255] ^ te2[(s0 >> 8) & 255] ^ te3[s1 & 255] ^ ek[k + 2]
        t3 = te0[s3 >> 24] ^ te1[(s0 >> 16) & 255] ^ te2[(s1 >> 8) & 255] ^ te3[s2 & 255] ^ ek[k + 3]
        s0, s1, s2, s3 = t0, t1, t2, t3
        k += 4
    r0 = ((sb[s0 >> 24] << 24) | (sb[(s1 >> 16) & 255] << 16) | (sb[(s2 >> 8) & 255] << 8) | sb[s3 & 255]) ^ ek[k]
    r1 = ((sb[s1 >> 24] << 24) | (sb[(s2 >> 16) & 255] << 16) | (sb[(s3 >> 8) & 255] << 8) | sb[s0 & 255]) ^ ek[k + 1]
    r2 = ((sb[s2 >> 24] << 24) | (sb[(s3 >> 16) & 255] << 16) | (sb[(s0 >> 8) & 255] << 8) | sb[s1 & 255]) ^ ek[k + 2]
    r3 = ((sb[s3 >> 24] << 24) | (sb[(s0 >> 16) & 255] << 16) | (sb[(s1 >> 8) & 255] << 8) | sb[s2 & 255]) ^ ek[k + 3]
    return r0, r1, r2, r3


def _decrypt_block(dk, s0, s1, s2, s3):
    td0, td1, td2, td3, ib = TD[0], TD[1], TD[2], TD[3], INV_SBOX
    s0 ^= dk[0]; s1 ^= dk[1]; s2 ^= dk[2]; s3 ^= dk[3]
    k = 4
    for _ in range(13):
        t0 = td0[s0 >> 24] ^ td1[(s3 >> 16) & 255] ^ td2[(s2 >> 8) & 255] ^ td3[s1 & 255] ^ dk[k]
        t1 = td0[s1 >> 24] ^ td1[(s0 >> 16) & 255] ^ td2[(s3 >> 8) & 255] ^ td3[s2 & 255] ^ dk[k + 1]
        t2 = td0[s2 >> 24] ^ td1[(s1 >> 16) & 255] ^ td2[(s0 >> 8) & 255] ^ td3[s3 & 255] ^ dk[k + 2]
        t3 = td0[s3 >> 24] ^ td1[(s2 >> 16) & 255] ^ td2[(s1 >> 8) & 255] ^ td3[s0 & 255] ^ dk[k + 3]
        s0, s1, s2, s3 = t0, t1, t2, t3
        k += 4
    r0 = ((ib[s0 >> 24] << 24) | (ib[(s3 >> 16) & 255] << 16) | (ib[(s2 >> 8) & 255] << 8) | ib[s1 & 255]) ^ dk[k]
    r1 = ((ib[s1 >> 24] << 24) | (ib[(s0 >> 16) & 255] << 16) | (ib[(s3 >> 8) & 255] << 8) | ib[s2 & 255]) ^ dk[k + 1]
    r2 = ((ib[s2 >> 24] << 24) | (ib[(s1 >> 16) & 255] << 16) | (ib[(s0 >> 8) & 255] << 8) | ib[s3 & 255]) ^ dk[k + 2]
    r3 = ((ib[s3 >> 24] << 24) | (ib[(s2 >> 16) & 255] << 16) | (ib[(s1 >> 8) & 255] << 8) | ib[s0 & 255]) ^ dk[k + 3]
    return r0, r1, r2, r3


def cbc_encrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    """CBC without padding: len(data) must be a multiple of 16."""
    if len(iv) != 16 or len(data) % 16:
        raise ValueError("IV must be 16 bytes and data a multiple of 16")
    ek = _expand_key(key)
    n = len(data) // 4
    words = struct.unpack(">%dI" % n, data)
    out = []
    c0, c1, c2, c3 = struct.unpack(">4I", iv)
    enc = _encrypt_block
    for i in range(0, n, 4):
        c0, c1, c2, c3 = enc(ek, words[i] ^ c0, words[i + 1] ^ c1, words[i + 2] ^ c2, words[i + 3] ^ c3)
        out += (c0, c1, c2, c3)
    return struct.pack(">%dI" % n, *out)


def cbc_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    if len(iv) != 16 or len(data) % 16:
        raise ValueError("IV must be 16 bytes and data a multiple of 16")
    dk = _decrypt_keys(_expand_key(key))
    n = len(data) // 4
    words = struct.unpack(">%dI" % n, data)
    out = []
    p0, p1, p2, p3 = struct.unpack(">4I", iv)
    dec = _decrypt_block
    for i in range(0, n, 4):
        c0, c1, c2, c3 = words[i:i + 4]
        r0, r1, r2, r3 = dec(dk, c0, c1, c2, c3)
        out += (r0 ^ p0, r1 ^ p1, r2 ^ p2, r3 ^ p3)
        p0, p1, p2, p3 = c0, c1, c2, c3
    return struct.pack(">%dI" % n, *out)

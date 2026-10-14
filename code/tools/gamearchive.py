"""Dev tool library (not part of the exe): the game's own archives (`Data0-3.bhd` / `.bdt`): find one file by its path and read it.
Read-only; standard library only. Used by tools/dump_msgbnd.py, which found where the game's text lives (Level 3, 1.7.1).

    Data<N>.bhd = RSA( BHD5 index )      the key is in eldenring.exe (five PEM public keys, in the order Data0..Data3, DLC)
    BHD5 entry  = hash of the path, size, offset in Data<N>.bdt, an AES-128 key and the byte ranges it encrypts (ECB)
    the file    = DCX bytes (text: item.msgbnd.dcx, menu.msgbnd.dcx under /msg/<lang>/)

Nothing is written to the game folder. The caller gets the DCX bytes as the game stores them (decrypted, still compressed).
"""
from __future__ import annotations

import base64
import re
import struct
from dataclasses import dataclass
from pathlib import Path

from eldendisk.creative.innovate_spells import aes

ARCHIVES = ("Data0", "Data1", "Data2", "Data3")
_PEM = re.compile(rb"-----BEGIN RSA PUBLIC KEY-----.*?-----END RSA PUBLIC KEY-----", re.S)
_ENTRY = struct.Struct("<QiiQQQ")          # hash, padded size, unpadded size (0 here), offset, sha offset, aes offset


class ArchiveError(Exception):
    pass


def ecb_decrypt(key: bytes, data: bytes) -> bytes:
    """AES-128 in ECB mode without padding (the game archives encrypt each file this way), with the tables of the package's aes.py."""
    if len(key) != 16 or len(data) % 16:
        raise ValueError("AES-128 needs a 16-byte key and data in whole 16-byte blocks")
    w = list(struct.unpack(">4I", key))
    rcon = 1
    for i in range(4, 44):
        t = w[i - 1]
        if i % 4 == 0:
            t = ((t << 8) | (t >> 24)) & 0xFFFFFFFF
            t = (aes.SBOX[t >> 24] << 24) | (aes.SBOX[(t >> 16) & 255] << 16) | (aes.SBOX[(t >> 8) & 255] << 8) | aes.SBOX[t & 255]
            t ^= rcon << 24
            rcon = aes._xtime(rcon)
        w.append(w[i - 4] ^ t)
    dk = []
    for r in range(10, -1, -1):
        row = w[4 * r:4 * r + 4]
        dk += row if r in (0, 10) else [aes._inv_mix_word(x) for x in row]
    td0, td1, td2, td3, ib = aes.TD[0], aes.TD[1], aes.TD[2], aes.TD[3], aes.INV_SBOX
    words = struct.unpack(">%dI" % (len(data) // 4), data)
    out = []
    for i in range(0, len(words), 4):
        s0, s1, s2, s3 = (words[i + j] ^ dk[j] for j in range(4))
        k = 4
        for _ in range(9):
            t0 = td0[s0 >> 24] ^ td1[(s3 >> 16) & 255] ^ td2[(s2 >> 8) & 255] ^ td3[s1 & 255] ^ dk[k]
            t1 = td0[s1 >> 24] ^ td1[(s0 >> 16) & 255] ^ td2[(s3 >> 8) & 255] ^ td3[s2 & 255] ^ dk[k + 1]
            t2 = td0[s2 >> 24] ^ td1[(s1 >> 16) & 255] ^ td2[(s0 >> 8) & 255] ^ td3[s3 & 255] ^ dk[k + 2]
            t3 = td0[s3 >> 24] ^ td1[(s2 >> 16) & 255] ^ td2[(s1 >> 8) & 255] ^ td3[s0 & 255] ^ dk[k + 3]
            s0, s1, s2, s3 = t0, t1, t2, t3
            k += 4
        out += [((ib[s0 >> 24] << 24) | (ib[(s3 >> 16) & 255] << 16) | (ib[(s2 >> 8) & 255] << 8) | ib[s1 & 255]) ^ dk[k],
                ((ib[s1 >> 24] << 24) | (ib[(s0 >> 16) & 255] << 16) | (ib[(s3 >> 8) & 255] << 8) | ib[s2 & 255]) ^ dk[k + 1],
                ((ib[s2 >> 24] << 24) | (ib[(s1 >> 16) & 255] << 16) | (ib[(s0 >> 8) & 255] << 8) | ib[s3 & 255]) ^ dk[k + 2],
                ((ib[s3 >> 24] << 24) | (ib[(s2 >> 16) & 255] << 16) | (ib[(s1 >> 8) & 255] << 8) | ib[s0 & 255]) ^ dk[k + 3]]
    return struct.pack(">%dI" % len(out), *out)


@dataclass(frozen=True)
class Entry:
    hash: int
    size: int
    offset: int
    aes_key: bytes
    ranges: tuple[tuple[int, int], ...]


def path_hash(path: str) -> int:
    """The 64-bit hash of a path such as `/msg/engUS/item.msgbnd.dcx` (lower case, leading slash, multiplier 0x85)."""
    h = 0
    for ch in path.lower():
        h = (h * 0x85 + ord(ch)) & 0xFFFFFFFFFFFFFFFF
    return h


def keys_from_exe(exe: bytes) -> list[tuple[int, int]]:
    """The (n, e) of every RSA public key embedded in eldenring.exe, in file order."""
    keys = []
    for pem in _PEM.findall(exe):
        der = base64.b64decode(b"".join(pem.split(b"\n")[1:-1]))
        keys.append(_rsa_numbers(der))
    if not keys:
        raise ArchiveError("no RSA public key found in the exe")
    return keys


def _rsa_numbers(der: bytes) -> tuple[int, int]:
    def header(o):
        ln = der[o + 1]
        o += 2
        if ln & 0x80:
            k = ln & 0x7F
            ln = int.from_bytes(der[o:o + k], "big")
            o += k
        return o, ln
    o, _ = header(0)
    o, ln = header(o)
    n = int.from_bytes(der[o:o + ln], "big")
    o, ln2 = header(o + ln)
    return n, int.from_bytes(der[o:o + ln2], "big")


def decrypt_index(raw: bytes, key: tuple[int, int]) -> bytes:
    """The BHD5 bytes: each 256-byte block is raised to e mod n; the first byte of the result is always 0 and is dropped."""
    n, e = key
    size = (n.bit_length() + 7) // 8
    out = bytearray()
    for i in range(0, len(raw) - size + 1, size):
        out += pow(int.from_bytes(raw[i:i + size], "big"), e, n).to_bytes(size, "big")[1:]
    if out[:4] != b"BHD5":
        raise ArchiveError("this key does not open this index (no BHD5 magic)")
    return bytes(out)


def parse_index(dec: bytes) -> dict[int, Entry]:
    """Every file of one archive by path hash."""
    _unk, _size, buckets, buckets_at, _salt = struct.unpack_from("<5i", dec, 8)
    found: dict[int, Entry] = {}
    for b in range(buckets):
        count, at = struct.unpack_from("<ii", dec, buckets_at + b * 8)
        for i in range(count):
            h, size, _unp, off, _sha, aes_at = _ENTRY.unpack_from(dec, at + i * _ENTRY.size)
            key, ranges = b"", ()
            if aes_at:
                key = dec[aes_at:aes_at + 16]
                (n,) = struct.unpack_from("<i", dec, aes_at + 16)
                ranges = tuple(struct.unpack_from("<qq", dec, aes_at + 20 + 16 * r) for r in range(n))
            found[h] = Entry(h, size, off, key, ranges)
    return found


def read_entry(bdt, entry: Entry) -> bytes:
    """The file's bytes from an open Data<N>.bdt: read, then decrypt the encrypted ranges."""
    bdt.seek(entry.offset)
    data = bytearray(bdt.read(entry.size))
    if len(data) != entry.size:
        raise ArchiveError("the .bdt ends before the file does")
    for start, end in entry.ranges:
        if start < 0:        # (-1, -1) = nothing encrypted
            continue
        end = min(end, len(data))
        start = min(start, end)
        span = (end - start) // 16 * 16
        data[start:start + span] = ecb_decrypt(entry.aes_key, bytes(data[start:start + span]))
    return bytes(data)


def read_file(game_dir: Path, path: str, exe: bytes | None = None) -> bytes:
    """Find `path` in Data0..Data3 of the game folder and return its DCX bytes."""
    game_dir = Path(game_dir)
    exe = exe if exe is not None else (game_dir / "eldenring.exe").read_bytes()
    keys = keys_from_exe(exe)
    wanted = path_hash(path)
    for i, name in enumerate(ARCHIVES):
        bhd = game_dir / f"{name}.bhd"
        if not bhd.is_file() or i >= len(keys):
            continue
        entry = parse_index(decrypt_index(bhd.read_bytes(), keys[i])).get(wanted)
        if entry is not None:
            with open(game_dir / f"{name}.bdt", "rb") as bdt:
                return read_entry(bdt, entry)
    raise ArchiveError(f"{path} is not in Data0..Data3 of {game_dir}")

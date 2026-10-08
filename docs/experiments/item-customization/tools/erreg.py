"""regulation.bin <-> DCX bytes (AES-256-CBC, IV = first 16 bytes). Key verified by the DCX magic after decrypting."""
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
KEY = bytes([0x99,0xBF,0xFC,0x36,0x6A,0x6B,0xC8,0xC6,0xF5,0x82,0x7D,0x09,0x36,0x02,0xD6,0x76,
             0xC4,0x28,0x92,0xA0,0x1C,0x20,0x7F,0xB0,0x24,0xD3,0xAF,0x4E,0x49,0x3F,0xEF,0x99])
def decrypt(raw: bytes) -> bytes:
    iv, body = raw[:16], raw[16:]
    assert len(body) % 16 == 0
    return Cipher(algorithms.AES(KEY), modes.CBC(iv)).decryptor().update(body)
def encrypt(dcx: bytes, iv: bytes | None = None) -> bytes:
    iv = iv or os.urandom(16)
    pad = (-len(dcx)) % 16
    return iv + Cipher(algorithms.AES(KEY), modes.CBC(iv)).encryptor().update(dcx + b"\0" * pad)

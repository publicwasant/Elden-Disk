"""Lab 1: bytes, endianness, floats. Runs anywhere (pure Python)."""
import struct

runes = 10_273_265
print(hex(runes), struct.pack("<I", runes).hex(" "))          # 0x9cc1f1  f1 c1 9c 00
print(struct.unpack("<I", bytes.fromhex("f1c19c00"))[0])      # 10273265

for f in (30.0, -1.0, 0.1):
    raw = struct.pack("<f", f)
    print(f, raw.hex(" "), struct.unpack("<f", raw)[0])       # 0.1 -> 0.10000000149011612

ptr = 0x7FF3A2CBE970
print(struct.pack("<Q", ptr).hex(" "))                        # 70 e9 cb a2 f3 7f 00 00

# Same 4 bytes, three interpretations
b = bytes.fromhex("0000f041")
print(struct.unpack("<I", b)[0], struct.unpack("<f", b)[0], b)

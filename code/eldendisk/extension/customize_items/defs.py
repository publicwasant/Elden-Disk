"""Typed access to the fields of a PARAM row (layouts from paramdefs.py, which is generated from Paramdex)."""
from __future__ import annotations

import struct

from .paramdefs import PARAMDEFS

_FMT = {"s8": "<b", "u8": "<B", "s16": "<h", "u16": "<H", "s32": "<i", "u32": "<I", "f32": "<f", "b32": "<i"}

# short file name inside the BND4 -> key in PARAMDEFS
TABLE_FILES = {"goods": "EquipParamGoods", "magic": "Magic", "sp": "SpEffectParam", "shop": "ShopLineupParam"}


class Def:
    def __init__(self, key: str):
        d = PARAMDEFS[key]
        self.key, self.size, self.fields = key, d["size"], d["fields"]
        self.order = list(self.fields)

    def get(self, row, name):
        t, off, _size, bpos, bits, _arr = self.fields[name]
        v = struct.unpack_from(_FMT[t], row, off)[0]
        return (v >> bpos) & ((1 << bits) - 1) if bits else v

    def set(self, row, name, val) -> None:
        t, off, _size, bpos, bits, arr = self.fields[name]
        if arr != 1 or t not in _FMT:
            raise KeyError("field %s cannot be set (type %s, array %d)" % (name, t, arr))
        if bits:
            v = struct.unpack_from(_FMT[t], row, off)[0]
            mask = ((1 << bits) - 1) << bpos
            struct.pack_into(_FMT[t], row, off, (v & ~mask) | ((int(val) << bpos) & mask))
        else:
            struct.pack_into(_FMT[t], row, off, val)

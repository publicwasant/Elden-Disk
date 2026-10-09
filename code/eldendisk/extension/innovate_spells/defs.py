"""Typed access to the fields of a PARAM row (layouts from paramdefs.py, which is generated from Paramdex)."""
from __future__ import annotations

import math
import struct

from .paramdefs import PARAMDEFS

_FMT = {"s8": "<b", "u8": "<B", "s16": "<h", "u16": "<H", "s32": "<i", "u32": "<I", "f32": "<f", "b32": "<i"}

# short file name inside the BND4 -> key in PARAMDEFS
TABLE_FILES = {"goods": "EquipParamGoods", "magic": "Magic", "sp": "SpEffectParam", "shop": "ShopLineupParam"}


_RANGE = {"s8": (-1 << 7, (1 << 7) - 1), "u8": (0, 255), "s16": (-1 << 15, (1 << 15) - 1), "u16": (0, 65535),
          "s32": (-1 << 31, (1 << 31) - 1), "u32": (0, (1 << 32) - 1)}


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

    def problem(self, name, val):
        """None when `val` can be written to field `name` (a whole number or float32 that fits its type or bit width, never
        clamped), else the reason it cannot."""
        if name not in self.fields:
            return "%s has no field %r" % (self.key, name)
        t, _off, _size, _bpos, bits, arr = self.fields[name]
        if arr != 1 or t not in _FMT or t == "b32":
            return "%s.%s cannot be set (type %s, array %d)" % (self.key, name, t, arr)
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            return "%s.%s needs a number" % (self.key, name)
        if t == "f32":
            if not math.isfinite(val) or abs(val) > 3.4e38:
                return "%s.%s must be a finite number that fits a float32" % (self.key, name)
            return None
        if isinstance(val, float):
            if not val.is_integer():
                return "%s.%s is a whole-number field (%s)" % (self.key, name, t)
            val = int(val)
        lo, hi = (0, (1 << bits) - 1) if bits else _RANGE[t]
        if not lo <= val <= hi:
            return "%s.%s must be from %d to %d (%s%s)" % (self.key, name, lo, hi, t, ", %d bit" % bits if bits else "")
        return None

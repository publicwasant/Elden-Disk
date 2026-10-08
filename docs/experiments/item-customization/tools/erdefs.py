"""Paramdex ER defs -> field offsets. Field = (name, type, offset, size, bitpos, bits, array_len, default)."""
import os, re, struct
import xml.etree.ElementTree as ET
DEFS = os.environ.get("PARAMDEX_ER_DEFS", "Paramdex/ER/Defs").rstrip("/\\") + "/"
SIZES = {"s8":1,"u8":1,"dummy8":1,"s16":2,"u16":2,"s32":4,"u32":4,"f32":4,"f64":8,"b32":4}
FMT = {"s8":"<b","u8":"<B","s16":"<h","u16":"<H","s32":"<i","u32":"<I","f32":"<f","f64":"<d","b32":"<i"}

class Def:
    def __init__(self, xmlname):
        root = ET.parse(DEFS + xmlname + ".xml").getroot()
        self.param_type = root.findtext("ParamType")
        self.fields = {}
        self.order = []
        off = 0; bit_unit = None   # (type, byte offset, bits used)
        for f in root.find("Fields"):
            d = f.get("Def")
            m = re.match(r"(\w+)\s+(\w+)(?:\[(\d+)\])?(?::(\d+))?(?:\s*=\s*(\S+))?$", d.strip())
            t, name, arr, bits, dflt = m.groups()
            if t in ("fixstr", "fixstrW"):
                size = int(arr) * (2 if t == "fixstrW" else 1); bit_unit = None
                fld = (name, t, off, size, 0, 0, int(arr), dflt); off += size
            elif bits:
                bits = int(bits); sz = SIZES[t]
                if bit_unit and SIZES[bit_unit[0]] == sz and bit_unit[2] + bits <= sz * 8:
                    bpos = bit_unit[2]; base = bit_unit[1]; bit_unit = (t, base, bpos + bits)
                else:
                    base = off; bpos = 0; off += sz; bit_unit = (t, base, bits)
                fld = (name, t, base, sz, bpos, bits, 1, dflt)
            else:
                n = int(arr) if arr else 1; sz = SIZES[t] * n; bit_unit = None
                fld = (name, t, off, sz, 0, 0, n, dflt); off += sz
            self.fields[name] = fld; self.order.append(name)
        self.size = off
    def get(self, row, name):
        n, t, o, sz, bp, bits, arr, _ = self.fields[name]
        if t == "fixstrW": return bytes(row[o:o+sz]).decode("utf-16le").split("\0")[0]
        if t == "fixstr": return bytes(row[o:o+sz]).split(b"\0")[0].decode("shift_jis", "replace")
        if arr > 1 and t != "dummy8": return list(struct.unpack_from("<%d%s" % (arr, FMT[t][1]), row, o))
        if bits:
            v = struct.unpack_from(FMT[t], row, o)[0]; return (v >> bp) & ((1 << bits) - 1)
        if t == "dummy8": return bytes(row[o:o+sz])
        return struct.unpack_from(FMT[t], row, o)[0]
    def set(self, row, name, val):
        n, t, o, sz, bp, bits, arr, _ = self.fields[name]
        if bits:
            v = struct.unpack_from(FMT[t], row, o)[0]; mask = ((1 << bits) - 1) << bp
            v = (v & ~mask) | ((int(val) << bp) & mask)
            struct.pack_into(FMT[t], row, o, v); return
        assert arr == 1 and t not in ("fixstr", "fixstrW", "dummy8"), "unsupported set: " + name
        struct.pack_into(FMT[t], row, o, val)

def names(txtname):
    out = {}
    try:
        for line in open("/home/claude/soulsmods/paramdex/ER/Names/%s.txt" % txtname, encoding="utf-8"):
            if " " in line.strip():
                i, n = line.strip().split(" ", 1)
                try: out[int(i)] = n
                except ValueError: pass
    except FileNotFoundError: pass
    return out

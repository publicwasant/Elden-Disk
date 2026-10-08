import erlib, erdefs
from blockedit import SRC
from reencode import O, build, BS
raw, dcx, body, hdr, bnd = erlib.load_regulation(SRC)
P = erlib.Param(bnd.get("Magic").data); d = erdefs.Def("MagicParam")
n = 0
for row in P.rows:
    if row[0] < 999999990 and d.get(row[2], "mp") > 1:
        d.set(row[2], "mp", 1); n += 1
bnd.get("Magic").data = P.build()
nb = bnd.build()
direct = sorted({i for i in range(len(O.body) // BS + 1) if nb[i*BS:(i+1)*BS] != O.body[i*BS:(i+1)*BS]})
print(n, "spells changed; blocks", direct)
build("AllSpells1FP", nb, direct)

"""Checks run on the finished bytes BEFORE they are written. They are necessary, not sufficient: the only real test of a
regulation.bin is the game itself (handbook Part IV/VI), so a pass here means "nothing we know the game rejects".

Rules (each one is a lesson from a rejected or accepted test file in the handbook):
 R1 the frame decodes to exactly the intended body;
 R2 no stored/RLE block that the original frame did not have in the same place, and edited blocks are compressed blocks;
 R3 blocks whose decoded bytes did not change are byte-identical to the original (the only allowed difference is the
    literal-size-header form of raw-literal blocks, used to shape the tail);
 R4 DCX header: sizes correct, other bytes untouched; file length is 16 + a multiple of 16; exactly 2 zero bytes after the frame;
 R5 BND4: same entries, only the four tables differ;
 R6 PARAM tables: same row size and count, sorted, same header and strings; only rows named in the recipe's footprint differ.
"""
from __future__ import annotations

import struct

from . import zstd
from .container import Bnd4, Param
from .defs import TABLE_FILES
from .reblock import BS, TAIL_ZEROS, Source

MAX_CHANGED_BLOCKS = 11      # the most blocks any in-game-tested file (Z4) had re-encoded


def _raw_lit_split(c: bytes):
    """(literals, rest) of a compressed block whose literals are raw, else None."""
    if c[0] & 3:
        return None
    sf = (c[0] >> 2) & 3
    hl = 1 if sf in (0, 2) else 2 if sf == 1 else 3
    n = (c[0] >> 3) if hl == 1 else ((c[0] >> 4) | (c[1] << 4)) if hl == 2 else ((c[0] >> 4) | (c[1] << 4) | (c[2] << 12))
    return bytes(c[hl:hl + n]), bytes(c[hl + n:])


def check(src: Source, new_dcx: bytes, newbody: bytes, footprint):
    """-> (problems, warnings, stats). stats: changed_blocks and `decoded`, what the frame really decodes to (when it decodes)."""
    bad, warn = [], []
    # ---- R4 header and tail
    if new_dcx[:4] != b"DCX\0" or new_dcx[0x28:0x2C] != b"ZSTD":
        bad.append("R4: not a DCX/ZSTD container")
        return bad, warn, {}
    usize, csize = struct.unpack(">II", new_dcx[0x1C:0x24])
    frame = new_dcx[0x4C:0x4C + csize]
    if bytes(new_dcx[:0x1C]) != bytes(src.header[:0x1C]) or bytes(new_dcx[0x24:0x4C]) != bytes(src.header[0x24:0x4C]):
        bad.append("R4: the DCX header changed outside the two size fields")
    if usize != len(newbody):
        bad.append("R4: header says %d decoded bytes, body has %d" % (usize, len(newbody)))
    tail = new_dcx[0x4C + csize:]
    if len(tail) != TAIL_ZEROS or any(tail):
        bad.append("R4: expected exactly %d zero bytes after the frame, found %d bytes" % (TAIL_ZEROS, len(tail)))
    if (len(new_dcx) - 0x4C - csize + 0x4C + csize) % 16:
        bad.append("R4: the container is not a multiple of 16 bytes")
    # ---- R1 decodes
    try:
        got = zstd.decode_frame(frame)
    except Exception as e:       # any decoder failure is a failed check
        bad.append("R1: the frame does not decode (%s)" % e)
        return bad, warn, {}
    if got != newbody:
        bad.append("R1: the frame does not decode to the intended body")
    decoded = got
    # ---- R2 / R3 blocks
    try:
        blocks, end = zstd.split_blocks(frame)
    except Exception as e:
        bad.append("R2: the frame cannot be split into blocks (%s)" % e)
        return bad, warn, {}
    if end != len(frame):
        bad.append("R2: the frame has bytes after its last block")
    if frame[:6] != src.frame[:6]:
        bad.append("R2: the frame header changed")
    if len(blocks) != len(src.blocks):
        bad.append("R2: %d blocks, the original has %d" % (len(blocks), len(src.blocks)))
        return bad, warn, {}
    changed = converted = 0
    for i, (p, ty, size, last) in enumerate(blocks):
        sp_, sty, ssize, slast = src.blocks[i]
        c = frame[p + 3:p + 3 + (1 if ty == 1 else size)]
        same_decoded = newbody[i * BS:(i + 1) * BS] == src.body[i * BS:(i + 1) * BS]
        if last != slast:
            bad.append("R2: block %d: last-block flag changed" % i)
        if (ty != 2) != (sty != 2):
            bad.append("R2: block %d: type %d where the original has type %d (stored/RLE blocks are never accepted by the game)" % (i, ty, sty))
            continue
        if ty != 2:
            if frame[p:p + 3 + (1 if ty == 1 else size)] != src.frame[sp_:sp_ + 3 + (1 if sty == 1 else ssize)]:
                bad.append("R3: block %d (not compressed) differs from the original" % i)
            continue
        oc = src.content(i)
        if c == oc:
            continue
        if same_decoded:
            a, b = _raw_lit_split(c), _raw_lit_split(oc)
            if a and b and a == b:
                continue                                  # only the literal-size header form differs
            if src.lit_type.get(i) == 3 and (c[0] & 3) == 0:
                converted += 1                            # treeless literals turned into raw ones (their Huffman tree was replaced)
                continue
            bad.append("R3: block %d has the same decoded bytes but different encoded bytes" % i)
            continue
        changed += 1
        if len(c) >= 1 << 17:
            bad.append("R2: block %d is larger than 128 KiB" % i)
    if changed + converted > MAX_CHANGED_BLOCKS:
        warn.append("R2: %d blocks were re-encoded (more than %d, the most we have tested in the game)" % (changed + converted, MAX_CHANGED_BLOCKS))
    # ---- R5 / R6 BND4 and tables
    try:
        nb = Bnd4(newbody)
        ob = Bnd4(src.body)
    except Exception as e:
        bad.append("R5: BND4 unreadable (%s)" % e)
        return bad, warn, {"changed_blocks": changed + converted, "decoded": decoded}
    if len(nb.entries) != len(ob.entries) or bytes(nb.head[:0x40]) != bytes(ob.head[:0x40]):
        bad.append("R5: the BND4 header or entry count changed")
    else:
        targets = set(TABLE_FILES.values())
        for a, b in zip(nb.entries, ob.entries):
            short = a.name.replace("\\", "/").rsplit("/", 1)[-1][:-len(".param")]
            if (a.name, a.id) != (b.name, b.id):
                bad.append("R5: entry %s changed name or id" % b.name)
            elif short not in targets and a.data != b.data:
                bad.append("R5: entry %s changed but is not one of the edited tables" % b.name)
    for key, fname in TABLE_FILES.items():
        try:
            a, b = Param(nb.get(fname).data), Param(ob.get(fname).data)
        except Exception as e:
            bad.append("R6: table %s unreadable (%s)" % (key, e))
            continue
        if (a.count, a.row_size, bytes(a.head), a.tail) != (b.count, b.row_size, bytes(b.head), b.tail):
            bad.append("R6: table %s changed its size, header or strings" % key)
            continue
        ra, rb = {r[0]: bytes(r[2]) for r in a.rows}, {r[0]: bytes(r[2]) for r in b.rows}
        removed, added = set(rb) - set(ra), set(ra) - set(rb)
        modified = {i for i in set(ra) & set(rb) if ra[i] != rb[i]}
        if (removed, added, modified) != (footprint.removed[key], footprint.added[key], footprint.modified[key]):
            bad.append("R6: table %s: rows removed %s / added %s / changed %s differ from the recipe's declared %s / %s / %s" % (
                key, sorted(removed), sorted(added), sorted(modified), sorted(footprint.removed[key]),
                sorted(footprint.added[key]), sorted(footprint.modified[key])))
        if [r[0] for r in a.rows] != sorted(ra):
            bad.append("R6: table %s is not sorted by id" % key)
    return bad, warn, {"changed_blocks": changed + converted, "decoded": decoded}

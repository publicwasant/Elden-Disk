"""Checks run on the finished bytes BEFORE they are written. They are necessary, not sufficient: the only real test of a
regulation.bin is the game itself (handbook Part IV/VI), so a pass here means "nothing we know the game rejects".

Rules (each one is a lesson from a rejected or accepted test file in the handbook):
 R1 the frame decodes to exactly the intended body;
 R2 no stored/RLE block that the original frame did not have in the same place, and edited blocks are compressed blocks; blocks
    appended at the end (the body is longer) are compressed blocks in front of the original's empty last block;
 R3 blocks whose decoded bytes did not change are byte-identical to the original (the only allowed differences: the
    literal-size-header form of raw-literal blocks, used to shape the tail; and a block right after a changed block, re-encoded
    because that block could not end in the repeat-offset state the original expected -- reblock.rewrite_grow);
 R4 DCX header: sizes correct, other bytes untouched; file length is 16 + a multiple of 16; exactly 2 zero bytes after the frame;
 R5 BND4: same entries, every entry inside the body and none overlapping another, only the four tables differ;
 R6 PARAM tables (read by following each record's own pointer): same row size and strings, every old row byte for byte the same and
    moved by exactly the shift of its table, sorted; only rows named in the recipe's footprint were added, none removed or changed;
 R7 growth: no more than what the game was seen to accept (decoded body, compressed frame, blocks re-encoded).
"""
from __future__ import annotations

import struct

from . import zstd
from .container import Bnd4, ParamView
from .defs import TABLE_FILES, Def
from .reblock import BS, TAIL_ZEROS, Source

# What the game was seen to accept (handbook Part VI; T6 = 64 new rows in each of the four tables). Beyond these the file is
# untested: the gate stops, and the way forward is a new in-game test that raises the number, never a bypass.
MAX_CHANGED_BLOCKS = 27      # blocks re-encoded (T6: 13; T7, 2026-10-10: 20 with a grown fifth table, Bullet; T9, 2026-10-10: 26 with a sixth, AtkParam_Pc; T10, 2026-10-11: 27, a 20-slot design)
MAX_BODY_GROWTH = 219_000    # decoded bytes added (passed: 219 KB; 466 KB failed whatever the content)
MAX_FRAME_GROWTH = 292_000   # compressed frame bytes added (T6: +234,768; T9: +242,464; T10: +291,040)


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
    n_src = (len(src.body) + BS - 1) // BS                   # blocks that hold data (the frame has one more: the empty last block)
    nadd = (len(newbody) + BS - 1) // BS - n_src             # blocks appended because the body is longer
    if nadd < 0:
        bad.append("R2: the body is shorter than the original")
        return bad, warn, {}
    if len(blocks) != len(src.blocks) + nadd:
        bad.append("R2: %d blocks, expected %d (the original has %d, %d appended)" % (len(blocks), len(src.blocks) + nadd, len(src.blocks), nadd))
        return bad, warn, {}
    changed = converted = 0
    for i, (p, ty, size, last) in enumerate(blocks):
        if n_src <= i < n_src + nadd:                         # an appended block
            if ty != 2:
                bad.append("R2: appended block %d is not a compressed block (stored/RLE blocks are never accepted by the game)" % i)
            if last:
                bad.append("R2: appended block %d has the last-block flag" % i)
            if size >= 1 << 17:
                bad.append("R2: block %d is larger than 128 KiB" % i)
            continue
        si = i if i < n_src else i - nadd                     # the matching block of the original
        sp_, sty, ssize, slast = src.blocks[si]
        c = frame[p + 3:p + 3 + (1 if ty == 1 else size)]
        same_decoded = newbody[i * BS:(i + 1) * BS] == src.body[si * BS:(si + 1) * BS] if si < n_src else True
        if last != slast:
            bad.append("R2: block %d: last-block flag changed" % i)
        if (ty != 2) != (sty != 2):
            bad.append("R2: block %d: type %d where the original has type %d (stored/RLE blocks are never accepted by the game)" % (i, ty, sty))
            continue
        if ty != 2:
            if frame[p:p + 3 + (1 if ty == 1 else size)] != src.frame[sp_:sp_ + 3 + (1 if sty == 1 else ssize)]:
                bad.append("R3: block %d (not compressed) differs from the original" % i)
            continue
        oc = src.content(si)
        if c == oc:
            continue
        if same_decoded:
            a, b = _raw_lit_split(c), _raw_lit_split(oc)
            if a and b and a == b:
                continue                                  # only the literal-size header form differs
            if src.lit_type.get(si) == 3 and (c[0] & 3) == 0:
                converted += 1                            # treeless literals turned into raw ones (their Huffman tree was replaced)
                continue
            if si > 0 and newbody[(i - 1) * BS:i * BS] != src.body[(si - 1) * BS:si * BS]:
                converted += 1                            # re-encoded because the block before it (changed) ends in another repeat-offset state
                continue
            bad.append("R3: block %d has the same decoded bytes but different encoded bytes" % i)
            continue
        changed += 1
        if len(c) >= 1 << 17:
            bad.append("R2: block %d is larger than 128 KiB" % i)
    if changed + converted > MAX_CHANGED_BLOCKS:
        warn.append("R2: %d blocks were re-encoded (more than %d, the most we have tested in the game)" % (changed + converted, MAX_CHANGED_BLOCKS))
    # ---- R7 growth
    grown, comp_grown = len(newbody) - len(src.body), csize - struct.unpack(">I", src.header[0x20:0x24])[0]
    if grown > MAX_BODY_GROWTH:
        warn.append("R7: the body grew by %d bytes (more than %d, the most the game was seen to accept)" % (grown, MAX_BODY_GROWTH))
    if comp_grown > MAX_FRAME_GROWTH:
        warn.append("R7: the frame grew by %d bytes (more than %d, the most the game was seen to accept)" % (comp_grown, MAX_FRAME_GROWTH))
    # ---- R5 / R6 BND4 and tables
    stats = {"changed_blocks": changed + converted, "decoded": decoded, "body_growth": grown, "frame_growth": comp_grown}
    try:
        nb = Bnd4(newbody)
        ob = Bnd4(src.body)
    except Exception as e:
        bad.append("R5: BND4 unreadable (%s)" % e)
        return bad, warn, stats
    if len(nb.entries) != len(ob.entries) or bytes(nb.head[:0x40]) != bytes(ob.head[:0x40]):
        bad.append("R5: the BND4 header or entry count changed")
    else:
        targets = set(TABLE_FILES.values())
        spans = []
        for a, b in zip(nb.entries, ob.entries):
            short = a.name.replace("\\", "/").rsplit("/", 1)[-1][:-len(".param")]
            if (a.name, a.id) != (b.name, b.id):
                bad.append("R5: entry %s changed name or id" % b.name)
            elif short not in targets and a.data != b.data:
                bad.append("R5: entry %s changed but is not one of the edited tables" % b.name)
            if bytes(a.hdr[:8]) + bytes(a.hdr[0x1C:]) != bytes(b.hdr[:8]) + bytes(b.hdr[0x1C:]):
                bad.append("R5: entry %s: its header changed outside size and offset" % b.name)
            off = struct.unpack_from("<I", a.hdr, 0x18)[0]
            spans.append((off, off + len(a.data), b.name))
        spans.sort()
        if spans and spans[-1][1] > len(newbody):
            bad.append("R5: entry %s reaches past the end of the body" % spans[-1][2])
        for x, y in zip(spans, spans[1:]):
            if x[1] > y[0]:
                bad.append("R5: entries %s and %s overlap" % (x[2], y[2]))
    for key, fname in TABLE_FILES.items():
        size = Def(key).size
        try:
            a, b = ParamView(nb.get(fname).data, size), ParamView(ob.get(fname).data, size)
        except Exception as e:
            bad.append("R6: table %s unreadable (%s)" % (key, e))
            continue
        shift = a.strings_off - b.strings_off
        mask = lambda h: bytes(h[4:0x0A]) + bytes(h[0x0C:0x10]) + bytes(h[0x18:0x30]) + bytes(h[0x38:0x40])    # not: strings_off, count, type-name ptr, data_start
        at_end = shift == 0 and a.count > b.count            # grew at its END (grow.py `_grow_end`): nothing moves but the first rows
        if mask(a.head) != mask(b.head) or (a.tail[:len(b.tail)] != b.tail if at_end else a.tail != b.tail):
            bad.append("R6: table %s changed its header or strings" % key)
            continue
        want_start = 0x40 + 24 * a.count if at_end else b.data_start + shift
        if struct.unpack_from("<Q", a.head, 0x10)[0] != a.strings_off or struct.unpack_from("<Q", a.head, 0x30)[0] != want_start:
            bad.append("R6: table %s: the header pointers are not the original ones moved by %d" % (key, shift))
        oa, ob_ = a.offsets(), b.offsets()
        ra, rb = {r[0]: bytes(r[2]) for r in a.rows}, {r[0]: bytes(r[2]) for r in b.rows}
        removed, added = set(rb) - set(ra), set(ra) - set(rb)
        modified = {i for i in set(ra) & set(rb) if ra[i] != rb[i]}
        if (removed, added, modified) != (footprint.removed[key], footprint.added[key], footprint.modified[key]):
            bad.append("R6: table %s: rows removed %s / added %s / changed %s differ from the recipe's declared %s / %s / %s" % (
                key, sorted(removed), sorted(added), sorted(modified), sorted(footprint.removed[key]),
                sorted(footprint.added[key]), sorted(footprint.modified[key])))
        moved = [i for i in rb if i in oa and oa[i] != (ob_[i][0] + shift, ob_[i][1] + shift)]
        if at_end:
            # the rows that made room for the records: the FIRST rows of the data, copied behind the old strings; all others stay
            first_kept = min((ob_[i][0] for i in rb if i not in moved), default=None)
            behind = b.strings_off + len(b.tail)
            if any(ob_[i][0] >= first_kept or oa[i][0] < behind or oa[i][1] != ob_[i][1] for i in moved):
                bad.append("R6: table %s: a row that moved is not one of the first rows, or was not copied behind the strings" % key)
        elif moved:
            bad.append("R6: table %s: row %d is not where it should be (every old row moves by exactly %d)" % (key, moved[0], shift))
        if a.count != b.count + len(added):
            bad.append("R6: table %s: %d rows, expected %d" % (key, a.count, b.count + len(added)))
    return bad, warn, stats

"""Adding rows to PARAM tables inside the decoded body of regulation.bin. Standard library only.

Why this way. The game accepts a body that is a little longer (test T4-T6: up to 64 new rows in each of four tables), but every
64 KiB block of the frame that changes has to be re-encoded, and a table in the middle of the file cannot be moved without
shifting everything behind it. So nothing is moved except what is in the way, and tables grow BACKWARDS:

  before:  [ ... E3 | E2 | E1 | TABLE: head, records, rows, strings | next ... ]      (E1..E3: whole entries of the BND4 archive)
  after:   [ ... E3 old bytes (now unused) | ...gap | TABLE: head', records', new rows, padding | old rows, old strings | next ... ]
           and E3..E1 copied to the end of the body, their BND4 entry headers pointing to the copies

The head, the record table (one record per row, sorted by id; now with the new rows) and the new rows are written in the space the
evicted entries left; the old rows and the old strings are not touched at all (so the blocks that hold them stay byte for byte the
game's own). Every pointer in the table moves by the same amount X (the size of the added records and rows, rounded to 16).

Order matters in exactly one place: the evicted entries must be COPIED before the space they leave is overwritten (the first
version of this code did it the other way round and corrupted the copies; tests/test_ext_grow.py keeps that case)."""
from __future__ import annotations

import struct

from .container import Bnd4
from .reblock import BuildError

REC = 24                      # bytes per row record


class GrowError(BuildError):
    pass


def _short(name: str) -> str:
    return name.replace("\\", "/").rsplit("/", 1)[-1][:-len(".param")]


def grow(body: bytes, jobs: dict):
    """body: the decoded BND4. jobs: {table short name: {"rows": [(id, row bytes)], "name_from": id of an existing row whose
    name pointer the new rows share}}. -> (new body, [one report dict per table, in file order]).
    Raises GrowError when a table cannot grow (id in use, not the original layout, not enough room in front of it...)."""
    nb = bytearray(body)
    bnd = Bnd4(body)
    fhs = bnd.fhs
    index = {}
    for i, e in enumerate(bnd.entries):
        index.setdefault(_short(e.name), []).append(i)
    for short in jobs:
        if len(index.get(short, [])) != 1:
            raise GrowError("%s.param: %d matches in the archive" % (short, len(index.get(short, []))))
    targets = {index[s][0]: s for s in jobs}
    end_mode = {i for i, s in targets.items() if jobs[s].get("mode") == "end"}      # these grow at their END (grow_end below), not backwards

    def hpos(i):
        return 0x40 + i * fhs

    def entry(i):
        return struct.unpack_from("<I", nb, hpos(i) + 0x18)[0], struct.unpack_from("<Q", nb, hpos(i) + 8)[0]

    def pred(front):
        """The entry that ends where `front` begins (within the 16-byte alignment). None: nothing lies in front at all.
        -1: something does, but not directly (a hole the code cannot account for)."""
        best, any_below = None, False
        for i in range(len(bnd.entries)):
            o, s = entry(i)
            if o + s <= front:
                any_below = True
                if front - (o + s) < 16 and (best is None or o + s > entry(best)[0] + entry(best)[1]):
                    best = i
        return best if best is not None else (-1 if any_below else None)

    reports, done, free = [], set(), []       # free: [start, end) of space our own growth left behind (stale copies, nothing points there)
    for ti in sorted(targets, key=lambda i: entry(i)[0]):                  # in file order
        short = targets[ti]
        if ti in end_mode:
            continue
        rows = list(jobs[short]["rows"])
        if not rows:
            continue
        t_off, t_size = entry(ti)
        blob = bytes(nb[t_off:t_off + t_size])
        strings_off, count, data_start = struct.unpack_from("<I", blob, 0)[0], struct.unpack_from("<H", blob, 0x0A)[0], struct.unpack_from("<Q", blob, 0x30)[0]
        if count == 0 or (strings_off - data_start) % count:
            raise GrowError("%s is not in the original layout (it has been grown already?)" % short)
        rs = (strings_off - data_start) // count
        recs = [struct.unpack_from("<iIQQ", blob, 0x40 + REC * i) for i in range(count)]
        if any(r[1] != 0 or r[2] != data_start + i * rs for i, r in enumerate(recs)) or data_start != 0x40 + REC * count:
            raise GrowError("%s is not in the original layout (it has been grown already?)" % short)
        have = {r[0] for r in recs}
        ids = [rid for rid, _ in rows]
        if len(set(ids)) != len(ids):
            raise GrowError("%s: a new id appears twice" % short)
        clash = sorted(set(ids) & have)
        if clash:
            raise GrowError("%s: id %s is already used by a row of the game" % (short, clash[0]))
        if any(len(rd) != rs for _, rd in rows):
            raise GrowError("%s: a new row is not %d bytes long" % (short, rs))
        name_row = [r for r in recs if r[0] == jobs[short]["name_from"]]
        if not name_row:
            raise GrowError("%s: row %s (the name source) is missing" % (short, jobs[short]["name_from"]))
        K = len(rows)
        X = (K * (REC + rs) + 15) // 16 * 16                    # space the table needs in front of it
        # --- which entries must make room: the ones directly in front of the table, as many as it takes
        evicted, front = [], t_off
        while t_off - front < X:
            j = pred(front)
            if j is None:
                raise GrowError("%s: not enough room in front of the table for %d rows" % (short, K))
            if j < 0:
                raise GrowError("%s: the entries in front of the table are not contiguous" % short)
            if j in targets and j not in done:
                raise GrowError("%s: the entry in front of it (%s) is a table that has not grown yet" % (short, _short(bnd.entries[j].name)))
            evicted.append(j)
            front = entry(j)[0]
            for a, b in free:                                     # a table we grew sits right here: its stale space in front is free too
                if b == front:
                    front = a
        NS = t_off - X
        # --- the new head, records, rows
        head = bytearray(blob[:0x40])
        n2 = count + K
        struct.pack_into("<I", head, 0, strings_off + X)
        struct.pack_into("<Q", head, 0x10, strings_off + X)
        struct.pack_into("<H", head, 0x0A, n2)
        struct.pack_into("<Q", head, 0x30, data_start + X)
        new_rows_at = 0x40 + REC * n2
        if new_rows_at + rs * K > data_start + X:
            raise GrowError("%s: internal error: the new rows do not fit in front of the old ones" % short)
        allrecs = [(r[0], r[2] + X, r[3] + X) for r in recs]
        for q, (rid, _) in enumerate(sorted(rows)):
            allrecs.append((rid, new_rows_at + q * rs, name_row[0][3] + X))
        allrecs.sort(key=lambda r: r[0])
        region = bytearray(head)
        for rid, doff, noff in allrecs:
            region += struct.pack("<iIQQ", rid, 0, doff, noff)
        for _, rd in sorted(rows):
            region += rd
        region += b"\0" * (data_start + X - len(region))
        assert len(region) == data_start + X
        # --- 1. copy the evicted entries to the end of the body (their old bytes are about to be overwritten)
        for j in evicted:
            o, s = entry(j)
            at = len(nb)
            nb += nb[o:o + s]
            nb += b"\0" * ((-len(nb)) % 16)
            struct.pack_into("<I", nb, hpos(j) + 0x18, at)
        # --- 2. write the new head/records/rows over [NS, old data start): the old head and records are inside it
        nb[NS:t_off + data_start] = bytes(region)
        struct.pack_into("<I", nb, hpos(ti) + 0x18, NS)
        struct.pack_into("<Q", nb, hpos(ti) + 8, t_size + X)
        struct.pack_into("<Q", nb, hpos(ti) + 0x10, t_size + X)
        free.append((front, NS))
        reports.append({"table": short, "rows": K, "shift": X, "evicted": [_short(bnd.entries[j].name) for j in evicted],
                        "start": NS})
        done.add(ti)
    for ti in sorted(end_mode, key=lambda i: entry(i)[0]):
        reports.append(_grow_end(nb, bnd, ti, targets[ti], jobs[targets[ti]], entry, hpos))
    return bytes(nb), reports


def _grow_end(nb: bytearray, bnd, ti: int, short: str, job: dict, entry, hpos) -> dict:
    """Grow the table at index `ti` at its END (used where the entry in front of the table is too big to move: AtkParam_Pc, behind
    which lies a 6 MB table, while the entry behind it is 28 KB).

      before:  [ T: head | N records | N rows (old) | strings ] [ next entries ... ]
      after:   [ T: head | N+K records | K new rows | rest of the hole | old rows m.. | strings | pad | the first m old rows ] [ ... ]

    The records grow by 24*K bytes into the front of the row data; the first m rows (the ones that lay there) are copied behind the
    strings and their records point at the copies; the K new rows go into the hole that is left. Every other row and the strings
    stay where they are, byte for byte. The entries that lie behind the table and are in the way are copied to the end of the body
    (as the front version does with the ones in front). Header: row count; `data_start` (0x30) = end of the records; `strings_off`
    and the type-name pointer are unchanged. Only the new, relocated rows and the records are written."""
    rows = sorted(job["rows"])
    t_off, t_size = entry(ti)
    blob = bytes(nb[t_off:t_off + t_size])
    strings_off, count, data_start = struct.unpack_from("<I", blob, 0)[0], struct.unpack_from("<H", blob, 0x0A)[0], struct.unpack_from("<Q", blob, 0x30)[0]
    if count == 0 or (strings_off - data_start) % count or data_start != 0x40 + REC * count:
        raise GrowError("%s is not in the original layout (it has been grown already?)" % short)
    rs = (strings_off - data_start) // count
    recs = [struct.unpack_from("<iIQQ", blob, 0x40 + REC * i) for i in range(count)]
    if any(r[1] != 0 or r[2] != data_start + i * rs for i, r in enumerate(recs)):
        raise GrowError("%s is not in the original layout (it has been grown already?)" % short)
    ids = [rid for rid, _ in rows]
    clash = sorted(set(ids) & {r[0] for r in recs})
    if len(set(ids)) != len(ids) or clash:
        raise GrowError("%s: a new id appears twice or is already used by a row of the game (%s)" % (short, clash[:1]))
    if any(len(rd) != rs for _, rd in rows):
        raise GrowError("%s: a new row is not %d bytes long" % (short, rs))
    name_row = [r for r in recs if r[0] == job["name_from"]]
    if not name_row:
        raise GrowError("%s: row %s (the name source) is missing" % (short, job["name_from"]))
    K, n2 = len(rows), count + len(rows)
    rec_end = 0x40 + REC * n2
    m = -(-(rec_end + K * rs - data_start) // rs)                    # rows of the front of the data that make room for the records and the new rows
    if m > count:
        raise GrowError("%s: too small to grow at its end" % short)
    tail_at = (t_size + 15) // 16 * 16                                # the relocated rows go here (relative to the table)
    new_size = tail_at + m * rs
    # --- room behind the table: evict the entries that are in the way
    end_abs = t_off + t_size
    limit = None
    evicted = []
    while True:
        later = [(entry(i)[0], i) for i in range(len(bnd.entries)) if entry(i)[0] >= end_abs and i != ti and i not in evicted]
        nxt = min(later)[0] if later else None
        if nxt is not None and t_off + new_size <= nxt:
            break
        if nxt is None:
            break                                                       # nothing behind it at all: the table may grow into the end of the body
        j = min(later)[1]
        if nxt - end_abs >= 16 and not evicted:
            pass                                                        # a hole of ours behind the table is fine
        evicted.append(j)
        end_abs = entry(j)[0] + entry(j)[1]
    if len(nb) < t_off + new_size:                                      # the grown table may reach past the old end of the body: the copies go behind it
        nb += b"\0" * (t_off + new_size - len(nb))
    nb += b"\0" * ((-len(nb)) % 16)
    for j in evicted:                                                   # copy first, overwrite after
        o, s_ = entry(j)
        at = len(nb)
        nb += nb[o:o + s_]
        nb += b"\0" * ((-len(nb)) % 16)
        struct.pack_into("<I", nb, hpos(j) + 0x18, at)
    # --- the records, the new rows
    new_at = rec_end
    allrecs = []
    for i, (rid, pad, doff, noff) in enumerate(recs):
        allrecs.append((rid, doff if i >= m else tail_at + i * rs, noff))
    for q, (rid, _) in enumerate(rows):
        allrecs.append((rid, new_at + q * rs, name_row[0][3]))
    allrecs.sort(key=lambda r: r[0])
    old_front = blob[data_start:data_start + m * rs]                    # the first m rows, copied before their place is overwritten
    region = bytearray()
    for rid, doff, noff in allrecs:
        region += struct.pack("<iIQQ", rid, 0, doff, noff)
    for _, rd in rows:
        region += rd
    region += b"\0" * (data_start + m * rs - rec_end - K * rs)
    nb[t_off + 0x40:t_off + data_start + m * rs] = bytes(region)
    nb[t_off + t_size:t_off + tail_at] = b"\0" * (tail_at - t_size)
    nb[t_off + tail_at:t_off + new_size] = old_front
    struct.pack_into("<H", nb, t_off + 0x0A, n2)
    struct.pack_into("<Q", nb, t_off + 0x30, rec_end)
    struct.pack_into("<Q", nb, hpos(ti) + 8, new_size)
    struct.pack_into("<Q", nb, hpos(ti) + 0x10, new_size)
    return {"table": short, "rows": K, "mode": "end", "relocated": m, "evicted": [_short(bnd.entries[j].name) for j in evicted], "start": t_off}

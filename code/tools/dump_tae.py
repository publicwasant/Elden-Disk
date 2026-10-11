"""Level 3 research (read-only): which effects does an animation of the player spawn? Reads the time-act files (TAE) of the player
(chr/c0000*.anibnd.dcx) and lists the events that carry the id of an effect file.

    python tools/dump_tae.py --game "D:\\SteamLibrary\\steamapps\\common\\ELDEN RING\\Game" --out taedump --ids ids.json
    python tools/dump_tae.py --game ... --out taedump --ffx 524400 --ffx 524401

--ids is a json file of effect ids (an object keyed by id, or a list of ids; the effect files the game holds): an event is listed when
one of the whole numbers (4 bytes) in its first 40 data bytes is such an id (1000 or more). --ffx N lists the events that carry N.
Writes only into --out: tae_events.txt.gz (one line per listed event: file, animation, start-end seconds, event type, the numbers)
and report.txt (the files read, the event types counted). Run it from the `code` folder; send me report.txt and the .gz.
A TAE file is read the way the format is documented by the community (header, animation table, event headers, event data); a file
that does not parse is named in the report and skipped.
"""
from __future__ import annotations

import argparse
import gzip
import json
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gamearchive as archive                      # noqa: E402

PARAM_BYTES = 40
MIN_ID = 1000


class TaeError(Exception):
    pass


@dataclass(frozen=True)
class Event:
    animation: int
    start: float
    end: float
    kind: int
    ints: tuple[int, ...]       # the first PARAM_BYTES of the event data as 4-byte whole numbers


def _u(blob, fmt, at):
    try:
        return struct.unpack_from(fmt, blob, at)
    except struct.error as exc:
        raise TaeError(f"read past the end at {at:#x}") from exc


def parse_tae(blob: bytes) -> list[Event]:
    """All events of a TAE file (version 0x1000C, Sekiro; 0x1000D is taken to be the same - the checks below refuse it if it is not). Offsets are absolute and 64-bit. Layout (packed, no padding):
    header: 'TAE ', 4 flag bytes, version u32 at 0x08, file size u32, ... the file's own id i32 at 0x50, animation count i32 at 0x54,
    animation table offset i64 at 0x58 (the real files of Elden Ring show 0x110; the layout of the older games is 4 bytes earlier).
    animation table: (id i64, offset i64) each. animation: event headers offset i64, groups offset i64, times offset i64,
    file offset i64, event count i32, ... event header: start-time offset i64, end-time offset i64, data offset i64.
    event data: type i64, then an i64 pointing 16 bytes after the type, then the parameters."""
    if blob[:4] != b"TAE ":
        raise TaeError("not a TAE file")
    version, = _u(blob, "<I", 0x08)
    if version not in (0x1000C, 0x1000D):
        raise TaeError(f"TAE version {version:#x}, only 0x1000C and 0x1000D are known")
    count, = _u(blob, "<i", 0x54)
    table, = _u(blob, "<q", 0x58)
    if count == 0:
        return []
    if not 0 < count < 1_000_000 or not 0 < table < len(blob):
        raise TaeError(f"unexpected header: {count} animations, table at {table:#x}")
    events: list[Event] = []
    for i in range(count):
        anim_id, anim_at = _u(blob, "<qq", table + 16 * i)
        heads, _groups, _times, _file, n = _u(blob, "<qqqqi", anim_at)
        if not 0 <= n < 100_000:
            raise TaeError(f"animation {anim_id}: {n} events")
        for k in range(n):
            t0, t1, data = _u(blob, "<qqq", heads + 24 * k)
            start, = _u(blob, "<f", t0)
            end, = _u(blob, "<f", t1)
            kind, link = _u(blob, "<qq", data)
            if link != data + 16:
                raise TaeError(f"animation {anim_id} event {k}: data link {link:#x} is not {data + 16:#x}")
            size = min(PARAM_BYTES, len(blob) - (data + 16)) // 4 * 4
            ints = _u(blob, f"<{size // 4}i", data + 16) if size > 0 else ()
            events.append(Event(anim_id, round(start, 4), round(end, 4), kind, ints))
    return events


def wanted(event: Event, ids: set[int]) -> bool:
    return any(v in ids for v in event.ints)


def candidates(everything: bool = False) -> list[str]:
    """The player's animation binder; with `everything` also the split ones (c0000_aNN_lo/hi), which hold no TAE in 1.17.1."""
    names = ["/chr/c0000.anibnd.dcx"]
    for n in range(100 if everything else 0):
        for tail in ("", "_lo", "_hi"):
            names.append(f"/chr/c0000_a{n:02d}{tail}.anibnd.dcx")
    return names


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ids", help="json of the effect ids that exist (an object keyed by id, or a list)")
    ap.add_argument("--ffx", type=int, action="append", default=[], help="an effect id to look for (may be repeated)")
    ap.add_argument("--all", action="store_true", help="also try the split binders c0000_aNN_lo/hi (slow; they hold no TAE files)")
    a = ap.parse_args()
    if not a.ids and not a.ffx:
        ap.error("give --ids FILE and/or --ffx N")
    ids = {int(k) for k in json.loads(Path(a.ids).read_text(encoding="utf-8"))} if a.ids else set()
    ids = {i for i in ids if i >= MIN_ID} | set(a.ffx)
    game, out = Path(a.game), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    exe = (game / "eldenring.exe").read_bytes()
    import dump_msgbnd
    report: list[str] = []

    def say(line=""):
        print(line)
        report.append(line)

    kinds: Counter = Counter()
    listed = 0
    with gzip.open(out / "tae_events.txt.gz", "wt", encoding="utf-8") as fh:
        for path in candidates(a.all):
            try:
                raw = archive.read_file(game, path, exe)
            except archive.ArchiveError:
                continue
            try:
                fmt, blob = dump_msgbnd.undcx(game, raw)
                files = [(fid, name, data) for fid, name, data in dump_msgbnd.bnd4_files(blob) if data[:4] == b"TAE "]
            except Exception as exc:
                say(f"{path}: could not open: {type(exc).__name__}: {exc}")
                continue
            say(f"{path}: {len(raw)} bytes ({fmt} -> {len(blob)}), {len(files)} TAE files; reading them ...")
            for fid, name, data in files:
                short = name.replace("\\", "/").rsplit("/", 1)[-1]
                try:
                    events = parse_tae(data)
                except TaeError as exc:
                    say(f"  {short}: {exc}")
                    continue
                for e in events:
                    kinds[e.kind] += 1
                    if wanted(e, ids):
                        listed += 1
                        fh.write(f"{short}\tanim {e.animation}\t{e.start}-{e.end}\ttype {e.kind}\t{' '.join(map(str, e.ints))}\n")
    say(f"{listed} events carry an effect id; event types seen: " + ", ".join(f"{k}:{n}" for k, n in sorted(kinds.items())))
    (out / "report.txt").write_text("\n".join(report), encoding="utf-8")
    print(f"\nreport: {out / 'report.txt'}\nevents: {out / 'tae_events.txt.gz'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Level 3, step 3 (read-only): find the effect (FXR) files of the game and copy out the ones you name.

    python tools/dump_sfx.py --game "D:\\SteamLibrary\\steamapps\\common\\ELDEN RING\\Game" --out sfxdump --sfx 524402 [--sfx N ...]

`--sfx` is a number from a SpEffectVfx row (524402 is the burning body of Flame, Grant Me Strength). Writes only into --out:
    names.txt      every file name in the effect archive, with its size
    <name>.fxr     each file whose name carries one of the numbers
    report.txt     what was found, and anything that could not be opened
The archive is large (88 MB compressed): this takes about a minute. Run it from the `code` folder.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dump_menu                                    # noqa: E402  (the binder reader)
import dump_msgbnd                                  # noqa: E402  (the DCX opener)
import gamearchive as archive                       # noqa: E402

BNDS = ("/sfx/sfxbnd_commoneffects.ffxbnd.dcx", "/sfx/sfxbnd_commoneffects_dlc02.ffxbnd.dcx")


def matching(items, numbers):
    """The items whose name carries one of these numbers as a whole run of digits (000524402 matches 524402)."""
    pats = [re.compile(rf"(?<!\d)0*{n}(?!\d)") for n in numbers]
    return [i for i in items if any(p.search(dump_menu.short(i.name)) for p in pats)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sfx", type=int, action="append", default=[])
    a = ap.parse_args()
    game, out = Path(a.game), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    exe = (game / "eldenring.exe").read_bytes()
    report: list[str] = []

    def say(line=""):
        print(line)
        report.append(line)

    names = []
    for path in BNDS:
        try:
            dcx = archive.read_file(game, path, exe)
        except archive.ArchiveError as exc:
            say(f"{path}: {exc}")
            continue
        say(f"{path}: {len(dcx)} bytes, DCX format {dcx[0x28:0x2C]!r}")
        if len(dcx) < 0x50 or dcx[:4] != b"DCX\0":
            say("  not a DCX (too small to be the real archive?)")
            continue
        try:
            fmt, blob = dump_msgbnd.undcx(game, dcx)
            say(f"  {fmt} -> {len(blob)} bytes, magic {blob[:4]!r}")
            items = dump_menu.bhf4_items(blob, (b"BND4",))
        except Exception as exc:
            say(f"  could not open it: {type(exc).__name__}: {exc}")
            continue
        say(f"  {len(items)} files")
        for fam, n in dump_menu.families(items)[:15]:
            say(f"    {n:>6}  {fam}")
        names += [f"{path.rsplit('/', 1)[-1]}\t{i.size}\t{dump_menu.short(i.name)}" for i in items]
        say(f"  header {blob[:0x40].hex()}")
        for item in matching(items, a.sfx):
            file = dump_menu.short(item.name)
            data = blob[item.offset:item.offset + item.size]
            at = 0x40 + item.index * 36
            say(f"  found {item.name}: size {item.size}, unpacked {item.unpacked}, offset {item.offset} of {len(blob)}")
            say(f"    entry {blob[at:at + 36].hex()}")
            say(f"    first bytes {data[:16].hex()} ({len(data)} bytes read)")
            if len(data) != item.size or data[:4] != b"FXR\0" and file.endswith(".fxr"):
                say("    this does not look like the file: not saved (send this report)")
                continue
            (out / file).write_bytes(data)
            say(f"    saved -> {file}")
        for n in a.sfx:
            if not matching(items, [n]):
                say(f"  {n}: no file of this archive carries this number")
    (out / "names.txt").write_text("\n".join(names), encoding="utf-8")
    (out / "report.txt").write_text("\n".join(report), encoding="utf-8")
    print(f"\nreport: {out / 'report.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

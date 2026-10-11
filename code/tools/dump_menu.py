"""Level 3, step 2 (read-only): where the game keeps its icons. Copies the small menu index files out of Data0-3 and lists them.

    python tools/dump_menu.py --game "D:\\SteamLibrary\\steamapps\\common\\ELDEN RING\\Game" --out menudump [--icon 12345] [--textures]

Writes only into --out (never into the game folder):
    00_solo.tpfbhd        the index of the split texture file 00_solo.tpfbdt (the names of the pictures and where they are)
    01_common.sblytbnd.dcx / .bnd / 01_common/   the layouts of the common menu atlas (which picture sits where)
    01_common.tpf.dcx     only with --textures (67 MB): the common atlas pictures themselves
    report.txt            what was found: the picture names (grouped), the entry of --icon N, anything that could not be opened
Run it from the `code` folder. Attach report.txt, 00_solo.tpfbhd and the .dcx/.bnd of the layouts if you want me to read them.
"""
from __future__ import annotations

import argparse
import re
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gamearchive as archive                      # noqa: E402  (tools/gamearchive.py)

HI = "/menu/hi"
INDEX = f"{HI}/00_solo.tpfbhd"
LAYOUTS = f"{HI}/01_common.sblytbnd.dcx"
ATLAS = f"{HI}/01_common.tpf.dcx"

ENTRY = 36        # bytes of one file header in the binders of this game (format byte 0x74)


class MenuError(Exception):
    pass


@dataclass(frozen=True)
class Item:
    index: int
    name: str
    size: int            # bytes in the data file
    unpacked: int        # bytes after decompression (= size when the file has no such field)
    offset: int          # where in the data file (tpfbdt)
    id: int              # -1 when the format has no ids


def bhf4_items(blob: bytes, magics: tuple = (b"BHF4",)) -> list[Item]:
    """The files listed by a BHF4 (the header file of a split binder, e.g. 00_solo.tpfbhd), or by a BND4 when `magics` says so
    (the entries are laid out the same way; offsets are then into `blob` itself). Refuses a layout it does not know, with the
    header in the message, rather than guessing.

    One file header (36 bytes, as in regulation.bin): flags u32, -1 i32, size u64, unpacked size u64, data offset u32,
    index i32, name offset u32."""
    if blob[:4] not in magics:
        raise MenuError(f"not a {b'/'.join(magics).decode()} (starts with {blob[:4]!r})")
    count, = struct.unpack_from("<i", blob, 0x0C)
    head, = struct.unpack_from("<q", blob, 0x10)
    entry, = struct.unpack_from("<q", blob, 0x20)
    unicode_names = blob[0x30]
    if head != 0x40 or entry != ENTRY or not 0 <= count < 1_000_000 or 0x40 + count * ENTRY > len(blob):
        raise MenuError(f"unexpected binder layout (header {blob[:0x40].hex()})")
    items = []
    for i in range(count):
        csize, usize, off, fid, at = struct.unpack_from("<qqIiI", blob, head + i * ENTRY + 8)
        items.append(Item(i, _cstring(blob, at, bool(unicode_names)), csize, usize, off, fid))
    return items


def _cstring(blob: bytes, at: int, wide: bool) -> str:
    if at <= 0 or at >= len(blob):
        return ""
    if wide:
        end = at
        while end + 1 < len(blob) and blob[end:end + 2] != b"\0\0":
            end += 2
        return blob[at:end].decode("utf-16le", "replace")
    end = blob.find(b"\0", at)
    return blob[at:end if end >= 0 else len(blob)].decode("shift_jis", "replace")


def short(name: str) -> str:
    return name.replace("\\", "/").rsplit("/", 1)[-1]


def families(items: list[Item]) -> list[tuple[str, int]]:
    """Names with every run of digits turned into `#`, counted: how many pictures of each kind."""
    return Counter(re.sub(r"\d+", "#", short(i.name)) for i in items).most_common()


def find_icon(items: list[Item], icon: int) -> list[Item]:
    """The pictures whose name carries this icon number (as 5 digits, or plain)."""
    pat = re.compile(rf"(?<!\d)0*{icon}(?!\d)")
    return [i for i in items if pat.search(short(i.name))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--icon", type=int, action="append", default=[], help="an iconId to look for (may be repeated)")
    ap.add_argument("--textures", action="store_true", help="also copy 01_common.tpf.dcx (67 MB)")
    a = ap.parse_args()
    game, out = Path(a.game), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    exe = (game / "eldenring.exe").read_bytes()
    report: list[str] = []

    def say(line=""):
        print(line)
        report.append(line)

    def get(path):
        try:
            return archive.read_file(game, path, exe)
        except archive.ArchiveError as exc:
            say(f"{path}: {exc}")
            return None

    raw = get(INDEX)
    if raw is not None:
        (out / "00_solo.tpfbhd").write_bytes(raw)
        say(f"{INDEX}: {len(raw)} bytes, magic {raw[:4]!r}")
        try:
            items = bhf4_items(raw)
        except Exception as exc:
            say(f"  could not open the BHF4: {type(exc).__name__}: {exc}")
            items = []
        say(f"  {len(items)} pictures")
        for fam, n in families(items)[:40]:
            say(f"    {n:>6}  {fam}")
        for icon in a.icon:
            found = find_icon(items, icon)
            say(f"  icon {icon}: " + (", ".join(f"{i.name} ({i.size} bytes at {i.offset})" for i in found[:10]) or "no picture has this number"))
        (out / "pictures.txt").write_text("\n".join(f"{i.index}\t{i.id}\t{i.size}\t{i.unpacked}\t{i.offset}\t{i.name}" for i in items),
                                          encoding="utf-8")

    dcx = get(LAYOUTS)
    if dcx is not None:
        (out / "01_common.sblytbnd.dcx").write_bytes(dcx)
        say(f"{LAYOUTS}: {len(dcx)} bytes, DCX format {dcx[0x28:0x2C]!r}")
        try:
            import dump_msgbnd
            fmt, blob = dump_msgbnd.undcx(game, dcx)
            (out / "01_common.sblytbnd.bnd").write_bytes(blob)
            say(f"  {fmt} -> {len(blob)} bytes, magic {blob[:4]!r}")
            folder = out / "01_common"
            folder.mkdir(exist_ok=True)
            for fid, fname, data in dump_msgbnd.bnd4_files(blob):
                (folder / (short(fname) or f"{fid}.bin")).write_bytes(data)
                say(f"    {fid:>5}  {len(data):>8}  {short(fname)}")
        except Exception as exc:
            say(f"  could not open the layouts: {type(exc).__name__}: {exc}")

    if a.textures:
        big = get(ATLAS)
        if big is not None:
            (out / "01_common.tpf.dcx").write_bytes(big)
            say(f"{ATLAS}: {len(big)} bytes copied")

    (out / "report.txt").write_text("\n".join(report), encoding="utf-8")
    print(f"\nreport: {out / 'report.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

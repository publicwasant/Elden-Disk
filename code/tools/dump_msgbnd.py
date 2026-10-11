"""Level 3, step 1 (read-only): copy the game's text archives out of Data0-3 and open them, so we can see what is inside.

    python tools/dump_msgbnd.py --game "D:\\SteamLibrary\\steamapps\\common\\ELDEN RING\\Game" --out msgdump

Writes only into --out (never into the game folder): for every file `<name>.dcx` (as the game stores it, decrypted),
`<name>.bnd` (decompressed), `<name>/` (the files inside, usually .fmg) and `report.txt`. Run it from the `code` folder.
"""
from __future__ import annotations

import argparse
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gamearchive as archive                      # noqa: E402  (tools/gamearchive.py)
from eldendisk.extension.innovate_items import zstd   # noqa: E402

LANG = "engUS"
FILES = [f"/msg/{LANG}/{n}.msgbnd.dcx" for n in ("item", "menu", "item_dlc01", "item_dlc02", "menu_dlc01", "menu_dlc02")]


def oodle_decompress(game: Path, src: bytes, raw_len: int) -> bytes:
    import ctypes
    dll = ctypes.WinDLL(str(game / "oo2core_6_win64.dll"))
    fn = dll.OodleLZ_Decompress
    fn.restype = ctypes.c_ssize_t
    fn.argtypes = [ctypes.c_char_p, ctypes.c_ssize_t, ctypes.c_char_p, ctypes.c_ssize_t, ctypes.c_int, ctypes.c_int,
                   ctypes.c_int, ctypes.c_void_p, ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_ssize_t, ctypes.c_int]
    dst = ctypes.create_string_buffer(raw_len)
    got = fn(src, len(src), dst, raw_len, 1, 0, 0, None, 0, None, None, None, 0, 3)
    if got != raw_len:
        raise RuntimeError(f"oodle returned {got}, expected {raw_len}")
    return dst.raw


def undcx(game: Path, dcx: bytes) -> tuple[str, bytes]:
    if dcx[:4] != b"DCX\0":
        raise ValueError("not a DCX")
    usize, csize = struct.unpack(">II", dcx[0x1C:0x24])
    fmt = dcx[0x28:0x2C].decode("ascii", "replace")
    body = dcx[0x4C:0x4C + csize]
    if fmt == "DFLT":
        return fmt, zlib.decompress(body)
    if fmt == "ZSTD":
        return fmt, zstd.decode_frame(body)[:usize]
    if fmt == "KRAK":
        return fmt, oodle_decompress(game, body, usize)
    raise ValueError(f"DCX format {fmt} is not handled")


def bnd4_files(blob: bytes):
    """(id, name, bytes) of every file of a BND4 whose file headers are 36 bytes (the layout regulation.bin uses:
    flags, -1, size, size, data offset u32, id, name offset). Any other layout is refused, with the header in the message."""
    if blob[:4] != b"BND4":
        raise ValueError("not a BND4")
    count, = struct.unpack_from("<I", blob, 0x0C)
    hsize, = struct.unpack_from("<Q", blob, 0x10)
    fhs, = struct.unpack_from("<Q", blob, 0x20)
    if fhs != 36 or blob[0x30] != 1:
        raise ValueError(f"unexpected BND4 layout, header: {blob[:0x40].hex()}")
    out = []
    for i in range(count):
        o = hsize + i * fhs
        size, size2 = struct.unpack_from("<QQ", blob, o + 8)
        off, fid, name_at = struct.unpack_from("<IiI", blob, o + 0x18)
        end = name_at
        while blob[end:end + 2] != b"\0\0" or (end - name_at) % 2:
            end += 1
        out.append((fid, blob[name_at:end].decode("utf-16le"), blob[off:off + size2]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    game, out = Path(a.game), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    exe = (game / "eldenring.exe").read_bytes()
    report = []

    def say(line):
        print(line)
        report.append(line)

    for path in FILES:
        name = path.rsplit("/", 1)[-1][:-len(".msgbnd.dcx")]
        try:
            dcx = archive.read_file(game, path, exe)
        except archive.ArchiveError as exc:
            say(f"{path}: {exc}")
            continue
        (out / f"{name}.dcx").write_bytes(dcx)
        say(f"{path}: {len(dcx)} bytes, DCX header {dcx[:4]!r} format {dcx[0x28:0x2C]!r}")
        try:
            fmt, blob = undcx(game, dcx)
        except Exception as exc:         # keep going: the raw .dcx is already saved
            say(f"  could not open the DCX: {type(exc).__name__}: {exc}")
            continue
        (out / f"{name}.bnd").write_bytes(blob)
        say(f"  {fmt} -> {len(blob)} bytes, magic {blob[:4]!r}")
        try:
            files = bnd4_files(blob)
        except Exception as exc:
            say(f"  could not open the BND4: {type(exc).__name__}: {exc}")
            continue
        folder = out / name
        folder.mkdir(exist_ok=True)
        for fid, fname, data in files:
            short = fname.replace("\\", "/").rsplit("/", 1)[-1] or f"{fid}.bin"
            (folder / short).write_bytes(data)
            say(f"    {fid:>5}  {len(data):>8}  {short}")
    (out / "report.txt").write_text("\n".join(report), encoding="utf-8")
    print(f"\nreport: {out / 'report.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""`check FILE`: do the rows of a regulation.bin equal the rows in the running game? (read-only)

The file side opens the container (AES → DCX → zstd → BND4 → the six .param files) and takes every row as bytes; the game
side reads the same six tables from memory. Rows are matched by id and compared byte for byte; a row that differs is then
decoded on both sides and the fields that differ are named. A value that was changed with `write` shows up here too, which is
the point: after a restart of the game process (or before any `write`) the two must agree.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

from ..creative.innovate_spells import container, zstd
from ..creative.innovate_spells.container import Bnd4, ContainerError
from ..game.paramlayouts import LAYOUTS
from ..game.paramtables import decode_row

# workbench table -> the name of its file inside the archive
FILES = {"Goods": "EquipParamGoods", "Magic": "Magic", "SpEffect": "SpEffectParam", "Bullet": "Bullet",
         "AtkParam_Pc": "AtkParam_Pc", "ShopLineup": "ShopLineupParam"}
SHOWN_ROWS = 20          # rows with differences printed per table (all of them are in --json)
SHOWN_FIELDS = 8         # differing fields printed per row


class CheckFileError(Exception):
    """The file is not a regulation.bin this tool can open."""


def file_rows(path: Path) -> dict[str, dict[int, bytes]]:
    """{table: {row id: row bytes}} of the six workbench tables of a regulation.bin."""
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise CheckFileError(f"{path}: {exc.strerror or exc}") from None
    try:
        dcx = container.decrypt(data)
        if dcx[:4] != b"DCX\0" or dcx[0x28:0x2C] != b"ZSTD":
            raise CheckFileError(f"{path}: not a DCX/ZSTD container (is it a regulation.bin?)")
        csize = struct.unpack(">I", dcx[0x20:0x24])[0]
        bnd = Bnd4(zstd.decode_frame(dcx[0x4C:0x4C + csize]))
        out: dict[str, dict[int, bytes]] = {}
        for table, name in FILES.items():
            blob, size = bnd.get(name).data, LAYOUTS[table]["size"]
            count = struct.unpack_from("<H", blob, 0xA)[0]
            rows: dict[int, bytes] = {}
            for i in range(count):
                rid, _pad, off, _name = struct.unpack_from("<IIQQ", blob, 0x40 + i * 24)
                if off + size > len(blob):
                    raise CheckFileError(f"{path}: {table} row {rid} reaches past the end of its file")
                rows[rid] = blob[off:off + size]
            out[table] = rows
        return out
    except CheckFileError:
        raise
    except (ContainerError, struct.error, IndexError, ValueError, KeyError, zstd.ZErr) as exc:
        raise CheckFileError(f"{path}: cannot be read as a regulation.bin ({exc})") from None


@dataclass
class TableDiff:
    table: str
    in_file: int
    in_game: int
    equal: int = 0
    differ: dict[int, list[tuple[str, object, object]]] = field(default_factory=dict)   # id -> [(field, file, game)]
    only_file: list[int] = field(default_factory=list)
    only_game: list[int] = field(default_factory=list)
    error: str | None = None

    @property
    def same(self) -> bool:
        return self.error is None and not (self.differ or self.only_file or self.only_game)


def compare(table: str, from_file: dict[int, bytes], from_game: dict[int, bytes]) -> TableDiff:
    diff = TableDiff(table, len(from_file), len(from_game))
    for rid in sorted(from_file):
        mine = from_game.get(rid)
        if mine is None:
            diff.only_file.append(rid)
        elif mine == from_file[rid]:
            diff.equal += 1
        else:
            a, b = decode_row(table, from_file[rid]), decode_row(table, mine)
            changed = [(name, a[name], b[name]) for name in a if a[name] != b[name]]
            # bytes differ but no named field does: padding or reserved bytes
            diff.differ[rid] = changed or [("(bytes not in a named field)", from_file[rid].hex(), mine.hex())]
    diff.only_game = sorted(set(from_game) - set(from_file))
    return diff


def as_json(diffs: list[TableDiff]) -> dict:
    return {"param_check": {d.table: {
        "rows_in_file": d.in_file, "rows_in_game": d.in_game, "equal": d.equal, "error": d.error,
        "differ": {str(rid): [{"field": f, "file": a, "game": b} for f, a, b in fields] for rid, fields in d.differ.items()},
        "only_in_file": d.only_file, "only_in_game": d.only_game} for d in diffs}}


def lines(diffs: list[TableDiff]) -> list[str]:
    out = []
    for d in diffs:
        if d.error:
            out.append(f"  {d.table:<12} not read: {d.error}")
            continue
        head = f"  {d.table:<12} {d.in_file} rows in the file, {d.in_game} in the game: {d.equal} equal"
        extra = [f"{len(x)} {what}" for x, what in ((d.differ, "differ"), (d.only_file, "only in the file"),
                                                   (d.only_game, "only in the game")) if x]
        out.append(head + (", " + ", ".join(extra) if extra else ""))
        for rid in list(d.differ)[:SHOWN_ROWS]:
            fields = d.differ[rid]
            shown = ", ".join(f"{f}: file {a}, game {b}" for f, a, b in fields[:SHOWN_FIELDS])
            more = f", … ({len(fields)} fields)" if len(fields) > SHOWN_FIELDS else ""
            out.append(f"      {d.table}.{rid}  {shown}{more}")
        if len(d.differ) > SHOWN_ROWS:
            out.append(f"      … {len(d.differ) - SHOWN_ROWS} more rows differ (--json lists all)")
        for ids, what in ((d.only_file, "only in the file"), (d.only_game, "only in the game")):
            if ids:
                out.append(f"      {what}: {', '.join(map(str, ids[:10]))}" + (f", … ({len(ids)})" if len(ids) > 10 else ""))
    return out

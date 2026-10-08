"""The real thing: the game's own regulation.bin 1.17.1 -> the Z4 item, byte for byte what was tested in the game.

Needs the pristine file (not in the repository): set ELDENDISK_REGULATION_ORIG to it, or the test is skipped.
The expected hash is the SHA-256 of the decrypted container of the Z4 file that passed in-game (handbook Part VI)."""
import copy
import hashlib
import json
import os
import struct
from pathlib import Path

import pytest

from eldendisk.extension.customize_items import bases, build, container, preflight, recipes, reblock, spec, zstd
from eldendisk.extension.customize_items.service import CustomizeItems

ORIG = os.environ.get("ELDENDISK_REGULATION_ORIG")
pytestmark = pytest.mark.skipif(not ORIG or not Path(ORIG).is_file(), reason="set ELDENDISK_REGULATION_ORIG to the pristine regulation.bin")
Z4_DECRYPTED_SHA256 = "1aa16ee0dbcbc5902cef2b6eb29bd542f42b2158fcdb44c221c187280db5277b"
Z4 = spec.normalise(json.loads((Path(spec.__file__).parent / "sources" / "items.json").read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def base():
    data = Path(ORIG).read_bytes()
    assert hashlib.sha256(data).hexdigest() == bases.BASES[bases.CURRENT_BASE], "ELDENDISK_REGULATION_ORIG is not the 1.17.1 original"
    return data


@pytest.fixture(scope="module")
def src(base):
    return build.prepare(base)


@pytest.fixture(scope="module")
def built(base, src):
    return build.build(base, Z4["items"], src)


def test_z4_comes_out_byte_identical_to_the_file_tested_in_the_game(built):
    assert built.decrypted_sha256 == Z4_DECRYPTED_SHA256 and built.warnings == []
    dcx = container.decrypt(built.data)
    assert len(dcx) == 2071472 and (len(built.data) - 16) % 16 == 0


def test_the_result_is_a_deterministic_function_of_the_input(base, src, built):
    again = build.build(base, copy.deepcopy(Z4["items"]), src)
    assert again.data == built.data


def test_the_result_passes_every_preflight_rule_and_an_independent_decoder(built, src):
    dcx = container.decrypt(built.data)
    csize = struct.unpack(">I", dcx[0x20:0x24])[0]
    frame = dcx[0x4C:0x4C + csize]
    zs = pytest.importorskip("zstandard")
    body = zs.ZstdDecompressor().decompressobj().decompress(frame)
    assert body == zstd.decode_frame(frame) and len(body) == len(src.body)
    newbody, fp = build.plan(src, Z4["items"])
    assert body == newbody and preflight.check(src, dcx, newbody, fp)[0] == []


def test_untouched_blocks_are_the_games_own_bytes(built, src):
    dcx = container.decrypt(built.data)
    csize = struct.unpack(">I", dcx[0x20:0x24])[0]
    blocks, _ = zstd.split_blocks(dcx[0x4C:0x4C + csize])
    frame = dcx[0x4C:0x4C + csize]
    same = sum(1 for i, (p, t, s, l) in enumerate(blocks) if frame[p:p + 3 + s] == src.frame[src.blocks[i][0]:src.blocks[i][0] + 3 + src.blocks[i][2]])
    assert same >= len(blocks) - 25 and len(blocks) == 827                          # a handful of blocks differ, all others identical


# ---- the preflight must notice damage (each case breaks one rule) ----
@pytest.fixture(scope="module")
def parts(built, src):
    dcx = bytearray(container.decrypt(built.data))
    newbody, fp = build.plan(src, Z4["items"])
    return dcx, newbody, fp


def rules(src, dcx, body, fp):
    return " ".join(preflight.check(src, bytes(dcx), body, fp)[0])


def test_preflight_notices_a_wrong_header_size(parts, src):
    dcx, body, fp = parts
    bad = bytearray(dcx)
    struct.pack_into(">I", bad, 0x1C, len(body) + 1)
    assert "R4" in rules(src, bad, body, fp)


def test_preflight_notices_a_changed_header_field(parts, src):
    dcx, body, fp = parts
    bad = bytearray(dcx)
    bad[0x10] ^= 1
    assert "R4" in rules(src, bad, body, fp)


def test_preflight_notices_a_tail_of_the_wrong_shape(parts, src):
    dcx, body, fp = parts
    assert "R4" in rules(src, bytes(dcx) + b"\0" * 16, body, fp)
    assert "R4" in rules(src, bytes(dcx[:-1]), body, fp)


def test_preflight_notices_a_frame_that_decodes_to_something_else(parts, src):
    dcx, body, fp = parts
    other = bytearray(body)
    other[10] ^= 1
    assert "R1" in rules(src, dcx, bytes(other), fp)


def test_preflight_notices_a_stored_block(parts, src):
    dcx, body, fp = parts
    csize = struct.unpack(">I", dcx[0x20:0x24])[0]
    frame = bytes(dcx[0x4C:0x4C + csize])
    blocks, _ = zstd.split_blocks(frame)
    p, ty, size, last = blocks[1]
    content = frame[p + 3:p + 3 + size]
    # block 1 re-stored as a raw block holding its decoded 64 KiB
    raw = body[reblock.BS:2 * reblock.BS]
    hdr = struct.pack("<I", (len(raw) << 3) | (0 << 1) | last)[:3]
    bad_frame = frame[:p] + hdr + raw + frame[p + 3 + size:]
    bad = bytearray(dcx[:0x4C]) + bad_frame
    struct.pack_into(">I", bad, 0x20, len(bad_frame))
    bad += b"\0" * ((-len(bad)) % 16)
    assert "stored/RLE" in rules(src, bad, body, fp)


def test_preflight_notices_rows_outside_the_footprint(built, src):
    dcx = container.decrypt(built.data)
    newbody, fp = build.plan(src, Z4["items"])
    smaller = recipes.Footprint()
    smaller.removed, smaller.added = copy.deepcopy(fp.removed), copy.deepcopy(fp.added)   # forgets the poise row
    assert "R6" in rules(src, dcx, newbody, smaller)


def test_preflight_notices_a_changed_table_that_is_not_ours(built, src):
    dcx = container.decrypt(built.data)
    newbody, fp = build.plan(src, Z4["items"])
    bnd = container.Bnd4(newbody)
    e = next(x for x in bnd.entries if not x.name.endswith(("Magic.param", "EquipParamGoods.param", "SpEffectParam.param", "ShopLineupParam.param")))
    e.data = e.data[:-1] + bytes([e.data[-1] ^ 1])
    assert "R5" in rules(src, dcx, bnd.build(), fp)


# ---- the recipe refuses a file that is not the original ----
def test_the_recipe_refuses_a_base_where_a_row_it_needs_is_missing(src):
    from eldendisk.extension.customize_items.defs import TABLE_FILES, Def
    bnd = container.Bnd4(src.body)
    D = {k: Def(k) for k in TABLE_FILES}
    P = {k: container.Param(bnd.get(f).data) for k, f in TABLE_FILES.items()}
    P["magic"].rows = [r for r in P["magic"].rows if r[0] != 6050]
    with pytest.raises(recipes.RecipeError):
        recipes.apply_incantation(P, D, Z4["items"][0], recipes.Footprint())


# ---- the whole flow through the service, with the real build ----
def test_service_builds_on_the_game_file(tmp_path, base):
    game = tmp_path / "game.bin"
    game.write_bytes(base)
    ci = CustomizeItems(tmp_path / "ext")                      # the spec shipped in sources/
    rep = ci.build(ci.items("all"), game)
    assert rep.built and rep.decrypted_sha256 == Z4_DECRYPTED_SHA256 and not rep.warnings
    assert game.read_bytes() == base and ci.output_path.is_file()

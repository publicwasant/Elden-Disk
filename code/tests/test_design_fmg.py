"""FMG, the game's text table: lossless reading, canonical writing. No game files needed."""
import struct

import pytest

from eldendisk.extension.innovate_items.fmg import Fmg, FmgError


def test_fmg_roundtrip_groups_gaps_and_empty_text():
    f = Fmg({10: "Dagger", 11: "Sword", 12: None, 40: "Bow", 7: "First"}, 0xFF)
    g = Fmg.read(f.write())
    assert g.entries == f.entries and g.unk14 == 0xFF
    blob = f.write()
    assert struct.unpack_from("<ii", blob, 0x0C) == (3, 5)                  # ids 7 | 10-12 | 40
    assert struct.unpack_from("<I", blob, 4)[0] == len(blob)


def test_fmg_non_ascii_text_and_new_id():
    f = Fmg.read(Fmg({1: "a"}).write())
    f.entries[2230000] = "เวทมนตร์\nบรรทัดสอง"
    assert Fmg.read(f.write()).entries[2230000] == "เวทมนตร์\nบรรทัดสอง"


def test_fmg_refuses_what_it_does_not_know():
    with pytest.raises(FmgError):
        Fmg.read(b"\0" * 64)
    blob = bytearray(Fmg({1: "a"}).write())
    struct.pack_into("<i", blob, 0x10, 9)                                   # string count lies
    with pytest.raises(FmgError):
        Fmg.read(bytes(blob))


def test_fmg_cut_short_is_an_error_not_an_endless_search():
    blob = Fmg({1: "abc", 2: "def"}).write()
    with pytest.raises(FmgError):
        Fmg.read(blob[:-4])                                                 # the last string has lost its end

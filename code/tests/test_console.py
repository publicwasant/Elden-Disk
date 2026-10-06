from eldendisk.console import printable


def test_symbols_pass_through_on_a_unicode_console():
    assert printable("saved ✓", "utf-8") == "saved ✓"


def test_a_legacy_code_page_gets_plain_words_not_escapes():
    assert printable("saved ✓", "cp874") == "saved OK"
    assert printable("restore failed ✖️", "cp1252") == "restore failed FAILED"
    assert "\\u" not in printable("a ✓ b → c — d", "ascii")


def test_unknown_characters_are_replaced_not_raised():
    assert printable("café 中", "ascii") == "caf? ?"

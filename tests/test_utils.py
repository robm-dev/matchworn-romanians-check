from mws_monitor.utils import normalize_name, parse_market_value


def test_normalize_name_handles_diacritics():
    assert normalize_name("Joško Gvardiol") == "josko gvardiol"
    assert normalize_name("  Pedri González ") == "pedri gonzalez"


def test_parse_market_value():
    assert parse_market_value("€200.00m") == 200_000_000
    assert parse_market_value("€750k") == 750_000
    assert parse_market_value("") == 0

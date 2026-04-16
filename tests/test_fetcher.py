from src.fetcher import parse_price


# ── parse_price ─────────────────────────────────────────────────────────────

def test_parse_price_simple():
    assert parse_price("150 €") == 150.0


def test_parse_price_vb():
    assert parse_price("VB 200 €") == 200.0


def test_parse_price_thousands():
    assert parse_price("1.200 €") == 1200.0


def test_parse_price_cents():
    assert parse_price("3,50 €") == 3.5


def test_parse_price_german_full():
    assert parse_price("1.200,50 €") == 1200.5


def test_parse_price_free():
    assert parse_price("Zu verschenken") == 0.0


def test_parse_price_unknown():
    assert parse_price("Price unknown") is None


def test_parse_price_empty():
    assert parse_price("") is None

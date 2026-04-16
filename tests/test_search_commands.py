import logging
import os
import tomllib
from unittest.mock import patch

from src.config import get_searches, list_searches, add_search, search_label, setup_logging
from src.fetcher import parse_price


# ── search_label ────────────────────────────────────────────────────────────

def test_search_label_extracts_term():
    assert search_label({"url": "https://www.kleinanzeigen.de/s-fahrraeder/k0"}) == "fahrraeder"


def test_search_label_with_filters():
    assert search_label({
        "url": "https://www.kleinanzeigen.de/s-anderes-beispiel/anzeige:angebote/preis:100:500/c217"}) == "anderes-beispiel"


def test_search_label_fallback_to_url():
    assert search_label({"url": "https://example.com/no-match"}) == "https://example.com/no-match"


def test_search_label_empty_url():
    assert search_label({}) == ""


def test_search_label_skips_postal_code():
    assert search_label({"url": "https://www.kleinanzeigen.de/s-12459/teppich/k0l9628"}) == "teppich"


def test_search_label_skips_postal_code_with_radius():
    assert search_label({"url": "https://www.kleinanzeigen.de/s-12459/bekväm/k0l9628r10"}) == "bekväm"


def test_search_label_skips_sortierung():
    assert search_label(
        {"url": "https://www.kleinanzeigen.de/s-sortierung:preis/logitech-spotlight/k0"}) == "logitech-spotlight"


def test_search_label_category_with_postal_code():
    assert search_label({"url": "https://www.kleinanzeigen.de/s-garten-pflanzen/12459/c89l9628r5"}) == "garten-pflanzen"


def test_search_label_explicit_name_overrides_url():
    assert search_label(
        {"url": "https://www.kleinanzeigen.de/s-12459/teppich/k0l9628", "name": "mein-teppich"}) == "mein-teppich"


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


# ── get_searches ────────────────────────────────────────────────────────────

def test_get_searches_missing_key():
    assert get_searches({}) == []


def test_get_searches_returns_list():
    searches = [{"url": "https://example.com"}]
    assert get_searches({"searches": searches}) == searches


# ── add_search ──────────────────────────────────────────────────────────────

def test_add_search_minimal(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("")

    with patch("src.config.CONFIG_FILE", config_file):
        add_search("https://www.kleinanzeigen.de/s-test/k0")

    parsed = tomllib.loads(config_file.read_text())
    assert len(parsed["searches"]) == 1
    assert parsed["searches"][0]["url"] == "https://www.kleinanzeigen.de/s-test/k0"


def test_add_search_all_options(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("")

    with patch("src.config.CONFIG_FILE", config_file):
        add_search(
            "https://www.kleinanzeigen.de/s-test/k0",
            addition_prompt="Only blue ones",
            max_price=100,
            deep_eval=True,
        )

    parsed = tomllib.loads(config_file.read_text())
    s = parsed["searches"][0]
    assert s["url"] == "https://www.kleinanzeigen.de/s-test/k0"
    assert s["max_price"] == 100
    assert s["deep_eval"] is True
    assert s["addition_prompt"] == "Only blue ones"


def test_add_search_appends_to_existing(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[assistant]\ncommon_prompt = "test"\n\n'
        '[[searches]]\nurl = "https://existing.example.com"\n'
    )

    with patch("src.config.CONFIG_FILE", config_file):
        add_search("https://new.example.com", max_price=50)

    parsed = tomllib.loads(config_file.read_text())
    assert len(parsed["searches"]) == 2
    assert parsed["searches"][0]["url"] == "https://existing.example.com"
    assert parsed["searches"][1]["url"] == "https://new.example.com"
    assert parsed["searches"][1]["max_price"] == 50
    assert parsed["assistant"]["common_prompt"] == "test"


# ── list_searches ───────────────────────────────────────────────────────────

def test_list_searches_empty(capsys):
    with patch("src.config.load_config", return_value={}):
        list_searches()
    assert "No searches configured" in capsys.readouterr().out


def test_list_searches_with_entries(capsys):
    config = {
        "searches": [
            {"url": "https://example.com/1", "max_price": 200, "deep_eval": True, "addition_prompt": "Blue only"},
            {"url": "https://example.com/2"},
        ]
    }
    with patch("src.config.load_config", return_value=config):
        list_searches()

    out = capsys.readouterr().out
    assert "https://example.com/1" in out
    assert "https://example.com/2" in out
    assert "max_price = 200" in out
    assert "deep_eval = true" in out
    assert "Blue only" in out


# ── setup_logging: LOG_TIMESTAMP ───────────────────────────────────────────

def _stdout_formatter() -> logging.Formatter:
    """Return the formatter attached to the root logger's stdout StreamHandler."""
    for h in logging.getLogger().handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
            return h.formatter
    raise AssertionError("No StreamHandler found on root logger")


def test_log_timestamp_true_overrides_non_tty():
    with patch("src.config.sys.stdout") as mock_stdout, patch.dict("os.environ", {"LOG_TIMESTAMP": "true"}):
        mock_stdout.isatty.return_value = False
        setup_logging()
    assert "asctime" in _stdout_formatter()._fmt


def test_log_timestamp_false_overrides_tty():
    with patch("src.config.sys.stdout") as mock_stdout, patch.dict("os.environ", {"LOG_TIMESTAMP": "false"}):
        mock_stdout.isatty.return_value = True
        setup_logging()
    assert "asctime" not in _stdout_formatter()._fmt


def test_log_timestamp_unset_uses_isatty_true():
    with patch("src.config.sys.stdout") as mock_stdout, patch.dict("os.environ", {}, clear=False):
        os.environ.pop("LOG_TIMESTAMP", None)
        mock_stdout.isatty.return_value = True
        setup_logging()
    assert "asctime" in _stdout_formatter()._fmt


def test_log_timestamp_unset_uses_isatty_false():
    with patch("src.config.sys.stdout") as mock_stdout, patch.dict("os.environ", {}, clear=False):
        os.environ.pop("LOG_TIMESTAMP", None)
        mock_stdout.isatty.return_value = False
        setup_logging()
    assert "asctime" not in _stdout_formatter()._fmt

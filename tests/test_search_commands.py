import tomllib
from unittest.mock import patch

from src.config import get_searches, list_searches, add_search


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

"""Tests for evaluator JSON parsing and retry logging."""
import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from src.evaluator import _try_parse_json, _call_model
from src.models.listing import Listing

FAKE_LISTING = Listing(
    id="999", title="Test", price="10 €", location="Berlin",
    url="https://www.kleinanzeigen.de/s-anzeige/test/999",
)


# ── _try_parse_json ─────────────────────────────────────────────────────────

class TestTryParseJson:
    def test_valid_json(self):
        raw = '{"match": true, "item": "Bike", "reason": "Good"}'
        assert _try_parse_json(raw) == {"match": True, "item": "Bike", "reason": "Good"}

    def test_markdown_code_fence(self):
        raw = '```json\n{"match": true, "item": "Bike", "reason": "Good"}\n```'
        assert _try_parse_json(raw) == {"match": True, "item": "Bike", "reason": "Good"}

    def test_markdown_code_fence_no_lang(self):
        raw = '```\n{"match": false, "item": "X", "reason": "Bad"}\n```'
        assert _try_parse_json(raw) == {"match": False, "item": "X", "reason": "Bad"}

    def test_preamble_text(self):
        raw = 'Here is the result:\n{"match": true, "item": "Lamp", "reason": "Nice"}'
        assert _try_parse_json(raw) == {"match": True, "item": "Lamp", "reason": "Nice"}

    def test_unescaped_quotes_in_reason(self):
        # The LLM puts unescaped quotes inside the reason string — json.loads will fail,
        # but the regex fallback should extract the fields.
        raw = '{"match": true, "item": "Bike", "reason": "The item is "great" for hiking"}'
        result = _try_parse_json(raw)
        assert result is not None
        assert result["match"] is True
        assert result["item"] == "Bike"
        assert "great" in result["reason"]

    def test_prefilter_match_only(self):
        raw = '{"match": false}'
        assert _try_parse_json(raw) == {"match": False}

    def test_garbage_returns_none(self):
        assert _try_parse_json("not json at all") is None

    def test_match_case_insensitive(self):
        raw = '{"match": True, "item": "X", "reason": "Y"}'  # Python-style True
        # json.loads will fail, regex should still extract
        result = _try_parse_json(raw)
        assert result is not None
        assert result["match"] is True


# ── retry logging ────────────────────────────────────────────────────────────

@patch("src.evaluator.requests.post")
def test_retry_counter_shows_correct_total(mock_post, caplog):
    """With retries=2, the last attempt should log 'attempt 3/3', not 'attempt 3/2'."""
    mock_post.side_effect = Exception("connection error")

    with caplog.at_level(logging.WARNING, logger="src.evaluator"):
        result = _call_model(
            api_key="key", model="m", system_prompt="sys",
            listing=FAKE_LISTING, search={}, retries=2,
        )

    assert result.error is True
    # All three log messages should show /3 as the denominator
    for record in caplog.records:
        if "attempt" in record.message:
            assert "/3" in record.message, f"Expected /3 in: {record.message}"
    assert "3/3" in caplog.records[-1].message


@patch("src.evaluator.requests.post")
def test_unparseable_response_retries(mock_post, caplog):
    """An unparseable response is retried and logged with correct attempt counter."""
    bad_resp = MagicMock()
    bad_resp.raise_for_status.return_value = None
    bad_resp.json.return_value = {"choices": [{"message": {"content": "not json at all"}}]}
    mock_post.return_value = bad_resp

    with caplog.at_level(logging.WARNING, logger="src.evaluator"):
        result = _call_model(
            api_key="key", model="m", system_prompt="sys",
            listing=FAKE_LISTING, search={}, retries=1,
        )

    assert result.error is True
    assert any("unparseable" in r.message for r in caplog.records)

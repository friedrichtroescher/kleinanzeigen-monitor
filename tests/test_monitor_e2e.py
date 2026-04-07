import json
from unittest.mock import MagicMock, patch

from src.models.app_config import AppConfig
from src.models.listing import Listing
from main import run_monitor

# ── Fixtures ────────────────────────────────────────────────────────────────

MINIMAL_CONFIG = {
    "model": {"id": "test-model"},
    "network": {"retries": 0},
    "assistant": {"common_prompt": ""},
    "searches": [
        {
            "url": "https://www.kleinanzeigen.de/s-test/k0",
            "max_price": 500,
            "deep_eval": False,
            "addition_prompt": "Good condition only.",
        }
    ],
}

FAKE_LISTING = Listing(
    id="123456",
    title="Test Fahrrad 26 Zoll",
    price="250 €",
    location="München",
    url="https://www.kleinanzeigen.de/s-anzeige/test/123456",
)

OPENROUTER_MATCH_RESPONSE = {
    "choices": [{"message": {"content": json.dumps({"match": True, "item": "Fahrrad 26\"", "reason": "Good condition, fair price."})}}]
}

OPENROUTER_NO_MATCH_RESPONSE = {
    "choices": [{"message": {"content": json.dumps({"match": False, "item": "Fahrrad 26\"", "reason": "Price too high."})}}]
}


def make_app(dry_run: bool = True, dont_skip_seen: bool = True) -> AppConfig:
    return AppConfig(
        config=MINIMAL_CONFIG,
        api_key="test-api-key",
        telegram_token="test-token",
        telegram_chat="test-chat",
        dry_run=dry_run,
        dont_skip_seen=dont_skip_seen,
    )


def mock_openrouter_response(payload: dict) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def _fake_search_page(listings: list[Listing]) -> MagicMock:
    """Build a minimal Kleinanzeigen-shaped HTML response for fetch_listings."""
    articles = "".join(
        f"""
        <article data-adid="{l.id}">
            <h2 class="ellipsis">{l.title}</h2>
            <p class="aditem-main--middle--price-shipping--price">{l.price}</p>
            <div class="aditem-main--top--left">{l.location}</div>
            <a href="{l.url}">link</a>
        </article>
        """
        for l in listings
    )
    html = f"<html><body>{articles}</body></html>"
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status.return_value = None
    return mock_resp


# ── Tests ────────────────────────────────────────────────────────────────────

@patch("src.evaluator.requests.post")
@patch("src.fetcher.requests.get")
@patch("main.save_seen")
@patch("main.load_seen")
def test_match_logs_in_dry_run(mock_load_seen, _, mock_fetch, mock_openrouter):
    """A matching listing in dry_run mode completes without raising."""
    mock_load_seen.return_value = set()
    mock_fetch.return_value = _fake_search_page([FAKE_LISTING])
    mock_openrouter.return_value = mock_openrouter_response(OPENROUTER_MATCH_RESPONSE)

    app = make_app(dry_run=True)
    run_monitor(app)


@patch("src.evaluator.requests.post")
@patch("src.fetcher.requests.get")
@patch("main.save_seen")
@patch("main.load_seen")
def test_no_match_does_not_send(mock_load_seen, _, mock_fetch, mock_openrouter):
    """A non-matching listing never reaches send_telegram."""
    mock_load_seen.return_value = set()
    mock_fetch.return_value = _fake_search_page([FAKE_LISTING])
    mock_openrouter.return_value = mock_openrouter_response(OPENROUTER_NO_MATCH_RESPONSE)

    with patch("main.send_telegram") as mock_send:
        app = make_app(dry_run=False)
        run_monitor(app)
        mock_send.assert_not_called()


@patch("src.evaluator.requests.post")
@patch("src.fetcher.requests.get")
@patch("main.save_seen")
@patch("main.load_seen")
def test_seen_listing_is_skipped(mock_load_seen, _, mock_fetch, mock_openrouter):
    """A listing already in seen.json is not evaluated."""
    mock_load_seen.return_value = {FAKE_LISTING.id}
    mock_fetch.return_value = _fake_search_page([FAKE_LISTING])

    app = make_app(dry_run=True, dont_skip_seen=False)
    run_monitor(app)
    mock_openrouter.assert_not_called()


@patch("src.evaluator.requests.post")
@patch("src.fetcher.requests.get")
@patch("main.save_seen")
@patch("main.load_seen")
def test_dont_skip_seen_evaluates_anyway(mock_load_seen, _, mock_fetch, mock_openrouter):
    """With dont_skip_seen=True, already-seen listings are still evaluated."""
    mock_load_seen.return_value = {FAKE_LISTING.id}
    mock_fetch.return_value = _fake_search_page([FAKE_LISTING])
    mock_openrouter.return_value = mock_openrouter_response(OPENROUTER_MATCH_RESPONSE)

    app = make_app(dry_run=True, dont_skip_seen=True)
    run_monitor(app)
    mock_openrouter.assert_called_once()


@patch("src.evaluator.requests.post")
@patch("src.fetcher.requests.get")
@patch("main.save_seen")
@patch("main.load_seen")
def test_deep_eval_skips_step2_on_no_match(mock_load_seen, _, mock_fetch, mock_openrouter):
    """With deep_eval=True, a step1 rejection skips the detail fetch entirely."""
    mock_load_seen.return_value = set()
    mock_fetch.return_value = _fake_search_page([FAKE_LISTING])
    mock_openrouter.return_value = mock_openrouter_response(
        {"choices": [{"message": {"content": json.dumps({"match": False})}}]}
    )

    config = {**MINIMAL_CONFIG, "searches": [{**MINIMAL_CONFIG["searches"][0], "deep_eval": True}]}
    app = AppConfig(**{**make_app().__dict__, "config": config})
    run_monitor(app)

    mock_openrouter.assert_called_once()
    assert mock_fetch.call_count == 1  # only search page, not detail page


@patch("src.evaluator.requests.post")
@patch("src.fetcher.requests.get")
@patch("main.save_seen")
@patch("main.load_seen")
def test_openrouter_failure_does_not_crash(mock_load_seen, _, mock_fetch, mock_openrouter):
    """If OpenRouter fails all retries, run_monitor completes without raising."""
    mock_load_seen.return_value = set()
    mock_fetch.return_value = _fake_search_page([FAKE_LISTING])
    mock_openrouter.side_effect = Exception("connection error")

    app = make_app(dry_run=True)
    run_monitor(app)  # should not raise


@patch("src.evaluator.requests.post")
@patch("src.fetcher.requests.get")
@patch("main.save_seen")
@patch("main.load_seen")
def test_evaluation_error_does_not_persist_to_seen(mock_load_seen, mock_save_seen, mock_fetch, mock_openrouter):
    """If evaluation errors out, the listing id is not saved to seen.json so it will be retried next run."""
    mock_load_seen.return_value = set()
    mock_fetch.return_value = _fake_search_page([FAKE_LISTING])
    mock_openrouter.side_effect = Exception("connection error")

    app = make_app(dry_run=True)
    run_monitor(app)

    saved = mock_save_seen.call_args[0][0]
    assert FAKE_LISTING.id not in saved
"""Telegram notification."""
import logging
import sys

import requests

from .models.evaluationResult import EvaluationResult
from .models.listing import Listing

log = logging.getLogger(__name__)


def send_telegram(token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        log.warning("Telegram error: %s", e)
        return False


def send_test_message(token: str, chat_id: str) -> None:
    msg = (
        "Kleinanzeigen Monitor test run successful!\n"
        "\n"
        "Example match:\n"
        "[RENNRAD] Trek Emonda SL5 54cm - 750 EUR\n"
        "Munich, Bavaria\n"
        "Shimano 105, good condition, matches the prompt\n"
        "https://www.kleinanzeigen.de/s-anzeige/beispiel"
    )
    log.info("Sending test message via Telegram...")
    if send_telegram(token, chat_id, msg):
        log.info("Success! Message sent.")
    else:
        log.error("Error sending message.")
        sys.exit(1)


def format_message(listing: Listing, evaluation: EvaluationResult) -> str:
    return (
        f"{evaluation.item} - {listing.price} – {listing.location}\n"
        f"{evaluation.reason}\n"
        f"{listing.url}"
    )

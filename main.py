#!/usr/bin/env python3
"""Kleinanzeigen Monitor – universal crawler with AI evaluation and Telegram notifications."""

import logging
import sys
import time

from src.config import resolve, setup_parser, load_app_config
from src.evaluator import evaluate_listing
from src.fetcher import fetch_listings
from src.models.app_config import AppConfig
from src.notifier import format_message, send_telegram, send_test_message
from src.persistence import load_seen, save_seen

log = logging.getLogger(__name__)


def run_monitor(app: AppConfig) -> None:
    config = app.config
    model = config.get("model", {}).get("id", "google/gemini-2.0-flash-lite-001")
    seen = load_seen()
    new_seen = set()
    matches = 0

    retries = config.get("network", {}).get("retries", 2)
    searches = config.get("searches", [])

    if not searches:
        log.error("No searches configured in config.toml.")
        sys.exit(1)

    for search in searches:
        url = search.get("url", "")
        if not url:
            log.warning("Search has no URL – skipped.")
            continue

        deep_eval = resolve(search, config, "deep_eval", False)
        max_price = resolve(search, config, "max_price", None)
        log.info("Crawling: %s (max_price=%s, deep_eval=%s)", url, max_price, deep_eval)
        listings = fetch_listings(url, retries=retries)
        log.info("%d listings found", len(listings))

        for listing in listings:
            if listing.id in seen and not app.dont_skip_seen:
                continue

            log.info("New: [%s] %s", listing.id, listing.title[:60])

            evaluation = evaluate_listing(
                app.api_key, model, listing, search, config,
                max_price=max_price,
                deep_eval=deep_eval,
                retries=retries,
            )

            if evaluation.error:
                log.warning("  -> skipping seen.json update for %s due to evaluation error", listing.id)
                continue

            new_seen.add(listing.id)

            if evaluation.match:
                msg = format_message(listing, evaluation)
                if app.dry_run:
                    log.info("  -> [dry-run] would send: %s", msg)
                    matches += 1
                elif send_telegram(app.telegram_token, app.telegram_chat, msg):
                    log.info("  -> Telegram message sent")
                    matches += 1

            time.sleep(0.5)

        seen.update(new_seen)
        save_seen(seen)
        time.sleep(2)

    log.info("Done. %d matches sent. %d IDs known.", matches, len(seen))


def main() -> None:
    args = setup_parser().parse_args()
    app = load_app_config(args)

    if args.test_telegram:
        send_test_message(app.telegram_token, app.telegram_chat)
        return

    run_monitor(app)


if __name__ == "__main__":
    main()
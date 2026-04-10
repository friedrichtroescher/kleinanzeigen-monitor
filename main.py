#!/usr/bin/env python3
"""Kleinanzeigen Monitor – universal crawler with AI evaluation and Telegram notifications."""

import logging
import sys
import time

from src.config import resolve, search_label, setup_parser, load_app_config, get_searches, list_searches, add_search
from src.evaluator import evaluate_listing
from src.fetcher import fetch_listings
from src.models.app_config import AppConfig
from src.notifier import format_message, send_telegram, send_test_message
from src.persistence import load_seen, save_seen
from src.telemetry import (
    init_telemetry, shutdown_telemetry, tracer,
    listings_fetched, listings_new, listings_matched, eval_errors, run_duration,
    search_duration, prefilter_rejections, detail_fetch_failures, scrape_rejections,
)

log = logging.getLogger(__name__)


def run_monitor(app: AppConfig) -> None:
    with tracer.start_as_current_span("run_monitor") as root_span:
        start = time.monotonic()
        config = app.config
        model = config.get("model", {}).get("id", "google/gemini-2.0-flash-lite-001")
        seen = load_seen()
        new_seen = set()
        matches = 0

        retries = config.get("network", {}).get("retries", 2)
        searches = get_searches(config)

        if not searches:
            log.error("No searches configured in config.toml.")
            sys.exit(1)

        root_span.set_attribute("search.count", len(searches))

        for search in searches:
            url = search.get("url", "")
            if not url:
                log.warning("Search has no URL – skipped.")
                continue

            deep_eval = resolve(search, config, "deep_eval", False)
            max_price = resolve(search, config, "max_price", None)
            label = search_label(search)
            attrs = {"search.name": label}

            with tracer.start_as_current_span("process_search", attributes={
                "search.name": label,
                "search.url": url,
                "search.max_price": str(max_price) if max_price is not None else "",
                "search.deep_eval": deep_eval,
            }):
                # Initialize all counters for this search so time series exist in Prometheus
                for c in (listings_fetched, listings_new, listings_matched, eval_errors,
                          prefilter_rejections, detail_fetch_failures, scrape_rejections):
                    c.add(0, attrs)
                search_start = time.monotonic()
                log.info("Crawling: %s (max_price=%s, deep_eval=%s)", url, max_price, deep_eval)
                listings = fetch_listings(url, retries=retries, search_name=label)
                log.info("%d listings found", len(listings))
                listings_fetched.add(len(listings), attrs)

                for listing in listings:
                    if listing.id in seen and not app.dont_skip_seen:
                        continue

                    listings_new.add(1, attrs)
                    log.info("New: [%s] %s", listing.id, listing.title[:60])

                    evaluation = evaluate_listing(
                        app.api_key, model, listing, search, config,
                        max_price=max_price,
                        deep_eval=deep_eval,
                        retries=retries,
                        search_name=label,
                    )

                    if evaluation.error:
                        eval_errors.add(1, attrs)
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
                        listings_matched.add(1, attrs)

                    time.sleep(0.5)

                search_duration.record(time.monotonic() - search_start, attrs)
                seen.update(new_seen)
                save_seen(seen)
                time.sleep(2)

        log.info("Done. %d matches sent. %d IDs known.", matches, len(seen))
        run_duration.record(time.monotonic() - start)


def main() -> None:
    parser = setup_parser()
    args = parser.parse_args()

    if args.command == "search":
        if args.search_action == "add":
            add_search(args.url, addition_prompt=args.addition_prompt, max_price=args.max_price,
                       deep_eval=args.deep_eval)
        else:
            list_searches()
        return

    if args.command == "run":
        app = load_app_config(args)
        init_telemetry()
        try:
            if args.test_telegram:
                send_test_message(app.telegram_token, app.telegram_chat)
                return
            run_monitor(app)
        finally:
            shutdown_telemetry()
        return

    parser.print_help()


if __name__ == "__main__":
    main()

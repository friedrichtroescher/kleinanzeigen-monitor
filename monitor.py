#!/usr/bin/env python3
"""Kleinanzeigen Monitor – universal crawler with AI evaluation and Telegram notifications."""

import argparse
import logging
import os
import sys
import time

from dotenv import load_dotenv

from config import ENV_FILE, load_config, resolve, setup_logging
from evaluator import SYSTEM_PROMPT_PREFILTER, build_system_prompt, evaluate_listing, format_detail_context
from fetcher import fetch_listing_detail, fetch_listings
from notifier import format_message, send_telegram, send_test_message
from persistence import load_seen, save_seen

log = logging.getLogger(__name__)


def run_monitor(config: dict, api_key: str, telegram_token: str, telegram_chat: str, dry_run: bool = False, dont_skip_seen: bool = False) -> None:
    model = config.get("model", {}).get("id", "google/gemini-2.0-flash-lite-001")
    system_prompt = build_system_prompt(config)
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
            ad_id = listing["id"]
            new_seen.add(ad_id)

            if ad_id in seen and not dont_skip_seen:
                continue

            log.info("Neu: [%s] %s", ad_id, listing["title"][:60])

            if deep_eval:
                step1 = evaluate_listing(
                    api_key, model,
                    SYSTEM_PROMPT_PREFILTER,
                    listing, search,
                    max_price=max_price,
                    required_fields=frozenset({"match"}),
                    retries=retries,
                )
                match = step1.get("match", False)
                log.info("  -> step1 match=%s", match)

                if match:
                    detail = fetch_listing_detail(listing["url"], retries=retries)
                    if detail:
                        extra = format_detail_context(detail)
                        evaluation = evaluate_listing(api_key, model, system_prompt, listing, search, max_price=max_price, extra_context=extra, retries=retries)
                    else:
                        log.warning("  -> step2 fetch failed, using step1 result (no detail)")
                        evaluation = {"match": True, "item": listing["title"], "reason": "Detail page unavailable"}
                    match = evaluation.get("match", False)
                    log.info("  -> step2 match=%s: %s", match, evaluation.get("reason", ""))
                else:
                    evaluation = step1
            else:
                evaluation = evaluate_listing(api_key, model, system_prompt, listing, search, max_price=max_price, retries=retries)
                match = evaluation.get("match", False)
                log.info("  -> match=%s: %s", match, evaluation.get("reason", ""))

            if match:
                msg = format_message(listing, evaluation)
                if dry_run:
                    log.info("  -> [dry-run] would send: %s", msg)
                    matches += 1
                elif send_telegram(telegram_token, telegram_chat, msg):
                    log.info("  -> Telegram message sent")
                    matches += 1

            time.sleep(0.5)

        seen.update(new_seen)
        save_seen(seen)
        time.sleep(2)

    log.info("Done. %d matches sent. %d IDs known.", matches, len(seen))


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(
        description=(
            "Monitors Kleinanzeigen searches and sends Telegram notifications for new\n"
            "listings that match your criteria, evaluated by an AI model via OpenRouter.\n\n"
            "Configured via config.toml and .env (see config.example.toml / .env.example)."
        ),
        epilog=(
            "examples:\n"
            "  monitor.py                           normal run\n"
            "  monitor.py --dry-run                 test without sending notifications\n"
            "  monitor.py --dry-run --dont-skip-seen\n"
            "                                       debug evaluation against known listings\n"
            "  monitor.py --test-telegram           verify Telegram is configured correctly"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--test-telegram", action="store_true", help="Send a test Telegram message to verify bot credentials, then exit.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and evaluate listings, but do not send Telegram messages. Logs what would have been sent instead.")
    parser.add_argument("--dont-skip-seen", action="store_true", help="Evaluate all fetched listings, even ones already recorded in seen.json. Useful for debugging evaluation logic.")
    args = parser.parse_args()

    load_dotenv(ENV_FILE)
    try:
        config = load_config()
    except FileNotFoundError as e:
        log.error("%s", e)
        sys.exit(1)

    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    telegram_chat = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not telegram_token or not telegram_chat:
        log.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env (see .env.example).")
        sys.exit(1)

    if args.test_telegram:
        send_test_message(telegram_token, telegram_chat)
        return

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        log.error("OPENROUTER_API_KEY must be set in .env (see .env.example).")
        sys.exit(1)

    run_monitor(config, api_key, telegram_token, telegram_chat, dry_run=args.dry_run, dont_skip_seen=args.dont_skip_seen)


if __name__ == "__main__":
    main()

# CLAUDE.md

## Project Overview

Kleinanzeigen Monitor — scrapes kleinanzeigen.de search pages, evaluates each listing via an LLM (OpenRouter), and sends matches to Telegram. Runs as a cron job.

## Tech Stack

- Python 3.11+, managed with `uv`
- `requests` + `BeautifulSoup4` for scraping
- OpenRouter API (OpenAI-compatible) for AI evaluation
- Telegram Bot API for notifications
- `python-dotenv` for secrets
- TOML config (`config.toml`)

## Project Structure

```
main.py                  # Entry point: CLI parsing → run_monitor() loop
src/
  config.py              # Config loading, logging setup, argparse, path constants
  fetcher.py             # HTML scraping: search pages + detail pages
  evaluator.py           # LLM evaluation via OpenRouter (optional 2-step deep_eval)
  notifier.py            # Telegram message formatting + sending
  persistence.py         # seen.json read/write (deduplication state)
  models/
    app_config.py        # AppConfig dataclass (runtime config bundle)
    listing.py           # Listing dataclass (id, title, price, location, url)
    listingDetail.py     # ListingDetail dataclass (description, attributes, shipping)
    evaluationResult.py  # EvaluationResult dataclass (match, item, reason, error)
setup.py                 # One-time cron installation from config.toml schedule
setup.sh                 # Shell wrapper: uv sync + run setup.py
config.toml              # User config (searches, model, schedule, prompts) — NOT in git
config.toml.example      # Template for config.toml
```

## Key Concepts

- **Search loop**: For each `[[searches]]` block in config.toml, fetch the Kleinanzeigen search page, parse listings, evaluate new ones via LLM, send matches to Telegram.
- **Deduplication**: `seen.json` stores all listing IDs ever processed. Listings with evaluation errors are NOT added (will be retried next run).
- **deep_eval**: Optional 2-step evaluation — step 1 is a cheap prefilter on title/price only; step 2 fetches the detail page for a thorough evaluation. Configurable globally in `[assistant]` or per `[[searches]]`.
- **Config resolution**: Per-search values override `[assistant]` globals, which override built-in defaults. See `resolve()` in `config.py`.

## Commands

```bash
# Run
uv run main.py                          # Normal run
uv run main.py --dry-run                # Evaluate but don't send Telegram messages
uv run main.py --dry-run --dont-skip-seen  # Re-evaluate all listings (debug mode)
uv run main.py --test-telegram          # Send a test message to verify Telegram config

# Tests
uv run pytest tests/ -v

# Setup (one-time)
./setup.sh                              # Install deps + cron jobs
```

## Configuration

- **Secrets** (`.env`): `OPENROUTER_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- **App config** (`config.toml`): model ID, schedule, retries, log level, common prompt, search definitions
- Both files are gitignored. See `.env.example` and `config.toml.example` for templates.

## Testing

Tests are in `tests/test_monitor_e2e.py`. They mock `requests.get` (fetcher), `requests.post` (OpenRouter), and `load_seen`/`save_seen` (persistence). Run with `uv run pytest tests/ -v`.

## Code Conventions

- Dataclasses for all models (no Pydantic)
- `logging` module throughout, configured in `config.py`
- No type: ignore, no broad except (except in evaluator retry loop where it's intentional)
- German user-facing config/prompts, English code and docstrings
- File naming: snake_case for modules, camelCase for some model files (`evaluationResult.py`, `listingDetail.py`)

## Important Notes

- `config.toml` and `seen.json` contain personal data — never commit them
- The monitor script is designed to be idempotent: running it multiple times is safe due to seen.json deduplication
- OpenRouter reasoning models are not supported (different response format)
- All paths are relative to `BASE_DIR` (project root), defined in `src/config.py`

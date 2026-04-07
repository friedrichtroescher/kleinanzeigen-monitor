"""Configuration loading, path constants, and logging setup."""
import argparse
import logging
import os
import sys
import tomllib
from pathlib import Path

from dotenv import load_dotenv

from .models.app_config import AppConfig

BASE_DIR = Path(__file__).parent.parent
SEEN_FILE = BASE_DIR / "seen.json"
ENV_FILE = BASE_DIR / ".env"
CONFIG_FILE = BASE_DIR / "config.toml"
LOG_FILE = BASE_DIR / "monitor.log"

log = logging.getLogger(__name__)


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError("config.toml not found. Copy config.toml.example and fill it in.")
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)


def load_app_config(args: argparse.Namespace) -> AppConfig:
    setup_logging() # basic logging before we have users config
    load_dotenv(ENV_FILE)
    try:
        config = load_config()
    except FileNotFoundError as e:
        log.error(str(e))
        sys.exit(1)

    setup_logging(config)

    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    telegram_chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not telegram_token or not telegram_chat:
        log.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env (see .env.example).")
        sys.exit(1)

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        log.error("OPENROUTER_API_KEY must be set in .env (see .env.example).")
        sys.exit(1)

    return AppConfig(
        config=config,
        api_key=api_key,
        telegram_token=telegram_token,
        telegram_chat=telegram_chat,
        dry_run=args.dry_run,
        dont_skip_seen=args.dont_skip_seen,
    )


def resolve(search: dict, config: dict, key: str, default):
    """Resolve a config key: search-level overrides [assistant] global, which overrides default."""
    if key in search:
        return search[key]
    return config.get("assistant", {}).get(key, default)


def setup_logging(config: dict | None = None) -> None:
    raw = config.get("logging", {}).get("level", "INFO") if config else "INFO"
    level = logging.getLevelName(raw.upper() if isinstance(raw, str) else "")
    if not isinstance(level, int):
        print(f"[warning] Invalid logging.level {raw!r} — falling back to INFO", file=sys.stderr)
        level = logging.INFO

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    sh = logging.StreamHandler(sys.stdout)
    fh.setFormatter(fmt)
    sh.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(fh)
    root.addHandler(sh)


def setup_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Monitors Kleinanzeigen searches and sends Telegram notifications for new\n"
            "listings that match your criteria, evaluated by an AI model via OpenRouter.\n\n"
            "Configured via config.toml and .env (see config.example.toml / .env.example)."
        ),
        epilog=(
            "examples:\n"
            "  main.py                           normal run\n"
            "  main.py --dry-run                 test without sending notifications\n"
            "  main.py --dry-run --dont-skip-seen\n"
            "                                       debug evaluation against known listings\n"
            "  main.py --test-telegram           verify Telegram is configured correctly"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--test-telegram", action="store_true", help="Send a test Telegram message to verify bot credentials, then exit.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and evaluate listings, but do not send Telegram messages. Logs what would have been sent instead.")
    parser.add_argument("--dont-skip-seen", action="store_true", help="Evaluate all fetched listings, even ones already recorded in seen.json. Useful for debugging evaluation logic.")
    return parser
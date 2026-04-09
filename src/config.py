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
        prog="monitor",
        description=(
            "Monitors Kleinanzeigen searches and sends Telegram notifications for new\n"
            "listings that match your criteria, evaluated by an AI model via OpenRouter.\n\n"
            "Configured via config.toml and .env (see config.example.toml / .env.example)."
        ),
        epilog=(
            "examples:\n"
            "  ./monitor run                      normal run\n"
            "  ./monitor run --dry-run             test without sending notifications\n"
            "  ./monitor run --dry-run --dont-skip-seen\n"
            "                                       debug evaluation against known listings\n"
            "  ./monitor run --test-telegram       verify Telegram is configured correctly\n"
            "  ./monitor search list             list all configured search URLs\n"
            '  ./monitor search add "https://www.kleinanzeigen.de/s-foo/k0" --prompt "..."\n'
            "                                       add a new search to config.toml"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run the monitor (fetch, evaluate, notify)")
    run_parser.add_argument("--test-telegram", action="store_true", help="Send a test Telegram message to verify bot credentials, then exit.")
    run_parser.add_argument("--dry-run", action="store_true", help="Fetch and evaluate listings, but do not send Telegram messages. Logs what would have been sent instead.")
    run_parser.add_argument("--dont-skip-seen", action="store_true", help="Evaluate all fetched listings, even ones already recorded in seen.json. Useful for debugging evaluation logic.")

    search_parser = subparsers.add_parser("search", help="Manage search URLs in config.toml")
    search_sub = search_parser.add_subparsers(dest="search_action")
    search_sub.add_parser("list", help="List all configured search URLs")
    add_parser = search_sub.add_parser("add", help="Add a new search to config.toml")
    add_parser.add_argument("url", help="Kleinanzeigen search URL")
    add_parser.add_argument("--prompt", dest="addition_prompt", help="Evaluation prompt for this search")
    add_parser.add_argument("--max-price", type=int, help="Maximum price filter")
    add_parser.add_argument("--deep-eval", action="store_true", default=None, help="Enable deep evaluation (fetch detail pages)")

    return parser


def get_searches(config: dict) -> list[dict]:
    """Return the list of [[searches]] blocks from a loaded config."""
    return config.get("searches", [])


def list_searches() -> None:
    searches = get_searches(load_config())
    if not searches:
        print("No searches configured in config.toml.")
        return
    for i, s in enumerate(searches, 1):
        url = s.get("url", "(no url)")
        prompt = s.get("addition_prompt", "")
        max_price = s.get("max_price")
        deep = s.get("deep_eval")
        parts = [f"  {url}"]
        if max_price is not None:
            parts.append(f"  max_price = {max_price}")
        if deep is not None:
            parts.append(f"  deep_eval = {str(deep).lower()}")
        if prompt:
            parts.append(f'  prompt = "{prompt}"')
        print(f"[{i}]")
        print("\n".join(parts))


def add_search(url: str, addition_prompt: str | None = None, max_price: int | None = None, deep_eval: bool | None = None) -> None:
    block = '\n[[searches]]\n'
    block += f'url = "{url}"\n'
    if max_price is not None:
        block += f'max_price = {max_price}\n'
    if deep_eval is not None:
        block += f'deep_eval = {"true" if deep_eval else "false"}\n'
    if addition_prompt:
        block += f'addition_prompt = "{addition_prompt}"\n'

    with open(CONFIG_FILE, "a") as f:
        f.write(block)
    print(f"Added search: {url}")

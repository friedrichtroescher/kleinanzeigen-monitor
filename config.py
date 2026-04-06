"""Configuration loading, path constants, and logging setup."""

import logging
import sys
import tomllib
from pathlib import Path

BASE_DIR = Path(__file__).parent
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


def resolve(search: dict, config: dict, key: str, default):
    """Resolve a config key: search-level overrides [assistant] global, which overrides default."""
    if key in search:
        return search[key]
    return config.get("assistant", {}).get(key, default)


def setup_logging() -> None:
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)

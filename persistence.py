"""Seen listings state persistence."""

import json

from config import SEEN_FILE


def load_seen() -> set:
    if not SEEN_FILE.exists():
        SEEN_FILE.write_text("[]")
        return set()
    text = SEEN_FILE.read_text().strip()
    if text:
        return set(json.loads(text))
    return set()


def save_seen(seen: set) -> None:
    SEEN_FILE.write_text(json.dumps(sorted(seen), indent=2))

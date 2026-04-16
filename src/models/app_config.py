from dataclasses import dataclass


@dataclass
class AppConfig:
    config: dict
    api_key: str
    telegram_token: str
    telegram_chat: str
    dry_run: bool
    dont_skip_seen: bool

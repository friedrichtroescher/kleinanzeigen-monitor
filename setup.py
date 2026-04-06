#!/usr/bin/env python3
"""One-time setup: install cron jobs from config.toml."""

import logging
import subprocess
import sys

from config import BASE_DIR, load_config, setup_logging
from persistence import load_seen  # ensures seen.json is created if missing

log = logging.getLogger(__name__)


def install_cron(config: dict) -> None:
    times = config.get("schedule", {}).get("times", [9, 15])
    uv = "/opt/homebrew/bin/uv"
    script_dir = str(BASE_DIR)

    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = [l for l in result.stdout.splitlines() if "kleinanzeigen-monitor" not in l]

    new_entries = [
        f"0 {hour} * * *  cd {script_dir} && {uv} run monitor.py >> {script_dir}/monitor.log 2>&1"
        for hour in sorted(set(times))
    ]

    new_crontab = "\n".join(existing + new_entries) + "\n"
    proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True)
    if proc.returncode == 0:
        log.info("Cron updated: %d entries (%s)", len(new_entries), ", ".join(f"{h}:00" for h in sorted(set(times))))
    else:
        log.error("Failed to set crontab.")
        sys.exit(1)


def main() -> None:
    setup_logging()

    log.info("Initializing seen.json if missing...")
    load_seen()

    try:
        config = load_config()
    except FileNotFoundError as e:
        log.error("%s", e)
        sys.exit(1)
    log.info("Installing cron jobs from config.toml...")
    install_cron(config)

    print(f"""
Setup complete!

Next steps:
  1. Fill in .env: nano {BASE_DIR}/.env
     OPENROUTER_API_KEY=sk-or-v1-...
     TELEGRAM_BOT_TOKEN=...
     TELEGRAM_CHAT_ID=...

  2. Configure searches in config.toml

  3. Test: cd {BASE_DIR} && uv run monitor.py --test
  4. Check cron: crontab -l
""")


if __name__ == "__main__":
    main()

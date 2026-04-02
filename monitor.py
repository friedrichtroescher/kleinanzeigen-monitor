#!/usr/bin/env python3
"""Kleinanzeigen Monitor – universeller Crawler mit KI-Bewertung und Telegram-Benachrichtigung."""

import argparse
import json
import logging
import os
import sys
import time
import tomllib
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
SEEN_FILE = BASE_DIR / "seen.json"
ENV_FILE = BASE_DIR / ".env"
CONFIG_FILE = BASE_DIR / "config.toml"
LOG_FILE = BASE_DIR / "monitor.log"


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


log = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SYSTEM_PROMPT_TEMPLATE = """Du bewertest Kleinanzeigen-Inserate.

Kaeufer-Profil:
{profile}

Fuer jedes Inserat erhaeltst du: Suchname, Maximalpreis und Prompt.
Bewerte das Inserat anhand dieser Kriterien und antworte NUR mit validem JSON (kein Markdown):
{{"match": true/false, "reason": "kurze Begruendung auf Deutsch", "category": "suchname oder irrelevant"}}

{extra}"""


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        log.error("config.toml nicht gefunden.")
        sys.exit(1)
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)


def build_system_prompt(config: dict) -> str:
    assistant = config.get("assistant", {})
    profile = assistant.get("profile", "Ich suche gebrauchte Gegenstaende in gutem Zustand.")
    extra_notes = assistant.get("extra_notes", "").strip()
    extra_block = f"Zusaetzliche Hinweise:\n{extra_notes}\n" if extra_notes else ""
    return SYSTEM_PROMPT_TEMPLATE.format(profile=profile, extra=extra_block)


def load_seen() -> set:
    if SEEN_FILE.exists():
        text = SEEN_FILE.read_text().strip()
        if text:
            return set(json.loads(text))
    return set()


def save_seen(seen: set) -> None:
    SEEN_FILE.write_text(json.dumps(sorted(seen), indent=2))


def fetch_listings(url: str, retries: int = 2) -> list[dict]:
    for attempt in range(1 + retries):
        try:
            resp = requests.get(url, headers=BROWSER_HEADERS, timeout=15)
            resp.raise_for_status()
            break
        except requests.RequestException as e:
            if attempt < retries:
                wait = 5 * (attempt + 1)
                log.warning("Fehler beim Abrufen von %s: %s – Retry %d/%d in %ds", url, e, attempt + 1, retries, wait)
                time.sleep(wait)
            else:
                log.warning("Fehler beim Abrufen von %s: %s – Alle Versuche fehlgeschlagen", url, e)
                return []

    soup = BeautifulSoup(resp.text, "html.parser")
    listings = []

    for article in soup.select("article[data-adid]"):
        ad_id = article.get("data-adid", "").strip()
        if not ad_id:
            continue

        title_el = article.select_one(".ellipsis") or article.select_one("h2")
        title = title_el.get_text(strip=True) if title_el else "(kein Titel)"

        price_el = article.select_one(".aditem-main--middle--price-shipping--price")
        price = price_el.get_text(strip=True) if price_el else "Preis unbekannt"

        loc_el = article.select_one(".aditem-main--top--left")
        location = loc_el.get_text(strip=True) if loc_el else "Ort unbekannt"

        link_el = article.select_one("a[href]")
        href = link_el["href"] if link_el else ""
        if href.startswith("/"):
            href = "https://www.kleinanzeigen.de" + href

        listings.append({"id": ad_id, "title": title, "price": price, "location": location, "url": href})

    return listings


def evaluate_listing(api_key: str, model: str, system_prompt: str, listing: dict, search: dict) -> dict:
    user_msg = (
        f"Suche: {search['name']}\n"
        f"Maximalpreis: {search.get('max_price', 0)} EUR\n"
        f"Prompt: {search.get('prompt', '')}\n"
        f"\n"
        f"Titel: {listing['title']}\n"
        f"Preis: {listing['price']}\n"
        f"Ort: {listing['location']}\n"
        f"URL: {listing['url']}"
    )
    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "max_tokens": 256,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        # Markdown-Codeblock entfernen falls vorhanden (```json ... ```)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        return json.loads(raw)
    except (json.JSONDecodeError, requests.RequestException, KeyError) as e:
        log.warning("Bewertungsfehler fuer %s: %s", listing["id"], e)
        return {"match": False, "reason": "Bewertungsfehler", "category": "irrelevant"}


def send_telegram(token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        log.warning("Telegram-Fehler: %s", e)
        return False


def format_message(listing: dict, evaluation: dict) -> str:
    category = evaluation.get("category", "?").upper()
    reason = evaluation.get("reason", "")
    return (
        f"[{category}] {listing['title']} - {listing['price']}\n"
        f"{listing['location']}\n"
        f"{reason}\n"
        f"{listing['url']}"
    )


def run_monitor(config: dict, api_key: str, telegram_token: str, telegram_chat: str) -> None:
    model = config.get("model", {}).get("id", "google/gemini-2.0-flash-lite-001")
    system_prompt = build_system_prompt(config)
    seen = load_seen()
    new_seen = set()
    matches = 0

    retries = config.get("network", {}).get("retries", 2)
    searches = config.get("searches", [])

    if not searches:
        log.error("Keine Suchen in config.toml konfiguriert.")
        sys.exit(1)

    for search in searches:
        url = search.get("url", "")
        name = search.get("name", "?")
        if not url:
            log.warning("Suche '%s' hat keine URL – uebersprungen.", name)
            continue

        log.info("Crawle [%s]: %s", name, url)
        listings = fetch_listings(url, retries=retries)
        log.info("%d Inserate gefunden", len(listings))

        for listing in listings:
            ad_id = listing["id"]
            new_seen.add(ad_id)

            if ad_id in seen:
                continue

            log.info("Neu: [%s] %s", ad_id, listing["title"][:60])
            evaluation = evaluate_listing(api_key, model, system_prompt, listing, search)
            category = evaluation.get("category", "irrelevant")
            match = evaluation.get("match", False)

            log.info("  -> %s, match=%s: %s", category, match, evaluation.get("reason", ""))

            if match:
                msg = format_message(listing, evaluation)
                if send_telegram(telegram_token, telegram_chat, msg):
                    log.info("  -> Telegram-Nachricht gesendet")
                    matches += 1

            time.sleep(0.5)

        seen.update(new_seen)
        save_seen(seen)  # nach jeder Such-URL zwischenspeichern
        time.sleep(2)

    log.info("Fertig. %d Treffer gesendet. %d IDs bekannt.", matches, len(seen))


def run_test(telegram_token: str, telegram_chat: str) -> None:
    msg = (
        "Kleinanzeigen Monitor Testlauf erfolgreich!\n"
        "\n"
        "Beispiel-Treffer:\n"
        "[RENNRAD] Trek Emonda SL5 54cm - 750 EUR\n"
        "Muenchen, Bayern\n"
        "Shimano 105, guter Zustand, passt dem Prompt\n"
        "https://www.kleinanzeigen.de/s-anzeige/beispiel"
    )
    log.info("Sende Test-Nachricht via Telegram...")
    if send_telegram(telegram_token, telegram_chat, msg):
        log.info("Erfolg! Nachricht gesendet.")
    else:
        log.error("Fehler beim Senden.")
        sys.exit(1)


def install_cron(config: dict) -> None:
    """Liest Zeiten aus config.toml und aktualisiert crontab."""
    times = config.get("schedule", {}).get("times", [9, 15])
    uv = "/opt/homebrew/bin/uv"
    script_dir = str(BASE_DIR)

    import subprocess
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = [l for l in result.stdout.splitlines() if "kleinanzeigen-monitor" not in l]

    new_entries = [
        f"0 {hour} * * *  cd {script_dir} && {uv} run monitor.py >> {script_dir}/monitor.log 2>&1"
        for hour in sorted(set(times))
    ]

    new_crontab = "\n".join(existing + new_entries) + "\n"
    proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True)
    if proc.returncode == 0:
        log.info("Cron aktualisiert: %d Eintraege (%s Uhr)", len(new_entries), ", ".join(f"{h}:00" for h in sorted(set(times))))
    else:
        log.error("Fehler beim Setzen der Crontab.")
        sys.exit(1)


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description="Kleinanzeigen Monitor")
    parser.add_argument("--test", action="store_true", help="Sende Test-Nachricht via Telegram")
    parser.add_argument("--install-cron", action="store_true", help="Cron-Jobs aus config.toml installieren")
    args = parser.parse_args()

    load_dotenv(ENV_FILE)
    config = load_config()

    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    telegram_chat = os.environ.get("TELEGRAM_CHAT_ID", "")

    if args.install_cron:
        install_cron(config)
        return

    if not telegram_token or not telegram_chat:
        log.error("TELEGRAM_BOT_TOKEN und TELEGRAM_CHAT_ID muessen in .env gesetzt sein.")
        sys.exit(1)

    if args.test:
        run_test(telegram_token, telegram_chat)
        return

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        log.error("OPENROUTER_API_KEY muss in .env gesetzt sein.")
        sys.exit(1)

    run_monitor(config, api_key, telegram_token, telegram_chat)


if __name__ == "__main__":
    main()

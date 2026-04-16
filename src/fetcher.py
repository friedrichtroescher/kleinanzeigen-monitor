"""Kleinanzeigen scraping."""
import logging
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .models.listing import Listing
from .models.listingDetail import ListingDetail
from .telemetry import scrape_rejections

log = logging.getLogger(__name__)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def parse_price(price_str: str) -> Optional[float]:
    """Extract a numeric EUR value from a Kleinanzeigen price string.

    Handles formats like '150 €', 'VB 1.200 €', '3,50 €', 'Zu verschenken'.
    Returns None for unparseable strings ('Price unknown', free-text, etc.).
    """
    s = price_str.strip().replace("€", "").replace("VB", "").strip()
    if not s or not any(c.isdigit() for c in s):
        return 0.0 if "verschenken" in price_str.lower() else None
    s = re.sub(r"[^\d.,]", "", s)
    # German format: 1.200,50 → 1200.50 / 1.200 → 1200
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.search(r"\.\d{3}(?:\.|$)", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def _get_with_retry(url: str, retries: int, search_name: str = "") -> Optional[requests.Response]:
    for attempt in range(1 + retries):
        try:
            resp = requests.get(url, headers=BROWSER_HEADERS, timeout=15)
            if resp.status_code in (403, 429):
                scrape_rejections.add(1, {"http.status_code": resp.status_code, "search.name": search_name})
                log.warning("Scraping rejected (%d) for %s", resp.status_code, url)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            if attempt < retries:
                wait = 5 * (attempt + 1)
                log.warning("Error fetching %s: %s – Retry %d/%d in %ds", url, e, attempt + 1, retries, wait)
                time.sleep(wait)
            else:
                log.warning("Error fetching %s: %s – All attempts failed", url, e)
    return None


def fetch_listings(url: str, retries: int = 2, search_name: str = "") -> list[Listing]:
    resp = _get_with_retry(url, retries, search_name=search_name)
    if resp is None:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    listings = []

    for article in soup.select("article[data-adid]"):
        ad_id = article.get("data-adid", "").strip()
        if not ad_id:
            continue

        title_el = article.select_one(".ellipsis") or article.select_one("h2")
        title = title_el.get_text(strip=True) if title_el else "(no title)"

        price_el = article.select_one(".aditem-main--middle--price-shipping--price")
        price = price_el.get_text(strip=True) if price_el else "Price unknown"

        loc_el = article.select_one(".aditem-main--top--left")
        location = " ".join(loc_el.get_text().split()) if loc_el else "Location unknown"

        link_el = article.select_one("a[href]")
        href = link_el["href"] if link_el else ""
        if href.startswith("/"):
            href = "https://www.kleinanzeigen.de" + href

        listings.append(Listing(id=ad_id, title=title, price=price, location=location, url=href))

    return listings


def fetch_listing_details(url: str, retries: int = 2, search_name: str = "") -> ListingDetail:
    resp = _get_with_retry(url, retries, search_name=search_name)
    if resp is None:
        return ListingDetail()

    try:
        soup = BeautifulSoup(resp.text, "lxml")

        desc_el = soup.select_one("#viewad-description-text")
        description = desc_el.get_text(separator="\n", strip=True) if desc_el else ""

        attributes: dict[str, str] = {}
        for li in soup.select(".addetailslist--detail"):
            val_el = li.select_one(".addetailslist--detail--value")
            val = val_el.get_text(strip=True) if val_el else ""
            label = li.get_text(strip=True).replace(val, "").strip().rstrip(":")
            if label and val:
                attributes[label] = val

        shipping_el = soup.select_one("span.boxedarticle--details--shipping")
        shipping_text = shipping_el.get_text(strip=True) if shipping_el else ""
        shipping = shipping_text if shipping_text else "Shipping available"

        return ListingDetail(description=description, attributes=attributes, shipping=shipping)
    except Exception as e:
        log.warning("Error parsing detail page %s: %s", url, e)
        return ListingDetail()

"""Reusable HTML extraction helpers."""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

from utils.text_normalizer import clean_text, strip_html


def extract_title(html: str) -> str:
    """Extract event title from H1 first, then document title."""
    h1_match = re.search(r"<h1[^>]*>([^<]+)</h1>", html or "", re.IGNORECASE)
    if h1_match:
        return clean_text(h1_match.group(1))
    title_match = re.search(r"<title[^>]*>([^<]+)</title>", html or "", re.IGNORECASE)
    return clean_text(title_match.group(1)) if title_match else ""


def extract_label_value(html: str, labels: List[str]) -> str:
    """Extract first matching Label: Value text from page content."""
    text = _line_text(html)
    for label in labels:
        pattern = re.compile(rf"{re.escape(label)}\s*[:\-]\s*(.+)$", re.IGNORECASE | re.MULTILINE)
        match = pattern.search(text)
        if match:
            return clean_text(match.group(1))
    return ""


def extract_body_text(html: str, max_length: int) -> str:
    """Extract and trim body text with a max length guard."""
    text = strip_html(html)
    if len(text) <= max_length:
        return text
    return f"{text[:max_length].rstrip()}..."


def extract_first_image_url(html: str, base_url: str) -> str:
    """Extract first image URL and convert it to absolute URL."""
    match = re.search(r'<img[^>]*src="([^"]+)"', html or "", re.IGNORECASE)
    if not match:
        return ""
    return urljoin(base_url, clean_text(match.group(1)))


def extract_date_time_block(html: str) -> Tuple[str, str]:
    """Extract date-time pair from free text blocks in HTML."""
    text = strip_html(html)
    long_date_match = re.search(
        r"(\d{1,2}\s+[A-Za-zçğıöşüÇĞİÖŞÜ]+[, ]+\s*\d{4}).{0,50}?(\d{1,2}[:\.]\d{2})",
        text,
        re.IGNORECASE,
    )
    if long_date_match:
        return clean_text(long_date_match.group(1)), long_date_match.group(2).replace(".", ":")

    dotted_date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)
    if dotted_date_match:
        return clean_text(dotted_date_match.group(1)), ""

    return "", ""


def _line_text(html: str) -> str:
    with_breaks = re.sub(r"</?(?:div|p|li|br|tr|td|th|h\d|span)[^>]*>", "\n", html or "", flags=re.IGNORECASE)
    plain = re.sub(r"<[^>]+>", " ", with_breaks)
    lines = [clean_text(line) for line in plain.splitlines() if clean_text(line)]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Price-specific extraction helpers
# ---------------------------------------------------------------------------

# JSON-LD Event/Offer schema keys we look for
_JSONLD_OFFER_PRICE_KEYS = ("price", "lowPrice", "minPrice")
_JSONLD_OFFER_HIGH_KEYS  = ("highPrice", "maxPrice")


def extract_jsonld_price(html: str) -> Optional[Dict[str, object]]:
    if not html or len(html) < 200 or '<script' not in html.lower():
        return None

    pattern = re.compile(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(html):
        raw = match.group(1).strip()
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue

        result = _parse_jsonld_node(data)
        if result:
            return result

    return None


def _parse_jsonld_node(node: object) -> Optional[Dict[str, object]]:
    """Recursively search a JSON-LD node for Event offers price data."""
    if isinstance(node, list):
        for item in node:
            found = _parse_jsonld_node(item)
            if found:
                return found
        return None

    if not isinstance(node, dict):
        return None

    node_type = str(node.get("@type", "")).lower()

    # Support ItemList wrapping Event nodes
    if node_type in ("itemlist", "list"):
        for item in node.get("itemListElement", []):
            found = _parse_jsonld_node(item.get("item", item) if isinstance(item, dict) else item)
            if found:
                return found

    offers_raw = node.get("offers")
    if offers_raw is None:
        return None

    offers_list = offers_raw if isinstance(offers_raw, list) else [offers_raw]

    min_price: Optional[float] = None
    max_price: Optional[float] = None
    currency:  Optional[str]   = None

    for offer in offers_list:
        if not isinstance(offer, dict):
            continue

        for key in _JSONLD_OFFER_PRICE_KEYS:
            raw_val = offer.get(key)
            if raw_val is not None:
                try:
                    val = float(str(raw_val).replace(",", "."))
                    if min_price is None or val < min_price:
                        min_price = val
                except (ValueError, TypeError):
                    pass

        for key in _JSONLD_OFFER_HIGH_KEYS:
            raw_val = offer.get(key)
            if raw_val is not None:
                try:
                    max_price = float(str(raw_val).replace(",", "."))
                except (ValueError, TypeError):
                    pass

        if currency is None:
            currency = offer.get("priceCurrency") or offer.get("currency")

    if min_price is None and max_price is None:
        return None

    return {"min": min_price, "max": max_price, "currency": currency or "TRY"}


# Meta tag patterns for price detection
_META_PRICE_PATTERNS = [
    re.compile(r'<meta[^>]+property=["\']event:price["\'][^>]+content=["\']([^"\']+)', re.IGNORECASE),
    re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']event:price', re.IGNORECASE),
    re.compile(r'<meta[^>]+name=["\']price["\'][^>]+content=["\']([^"\']+)', re.IGNORECASE),
    re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']price', re.IGNORECASE),
    re.compile(r'<meta[^>]+itemprop=["\']price["\'][^>]+content=["\']([^"\']+)', re.IGNORECASE),
    re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+itemprop=["\']price', re.IGNORECASE),
]


def extract_meta_price(html: str) -> Optional[str]:
    """Extract price string from common HTML meta tag patterns.

    Checks (in order):
    - ``<meta property="event:price">``
    - ``<meta name="price">``
    - ``<meta itemprop="price">``

    Returns the raw content string or ``None`` if nothing found.
    """
    if not html or len(html) < 200 or '<meta' not in html.lower():
        return None

    for pattern in _META_PRICE_PATTERNS:
        match = pattern.search(html)
        if match:
            value = clean_text(match.group(1))
            if value:
                return value

    return None

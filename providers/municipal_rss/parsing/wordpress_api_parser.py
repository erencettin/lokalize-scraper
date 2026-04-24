"""Parser for WordPress REST API event payloads."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from providers.municipal_rss.constants import WORDPRESS_VENUE_KEYS
from providers.municipal_rss.models import RawRssItem, RssFeedSource
from providers.municipal_rss.parsing.base_parser import RssFeedParser
from providers.municipal_rss.parsing.date_extractor import WordPressDateExtractor
from utils.html_extractor import extract_label_value
from utils.text_normalizer import clean_text, strip_html


class WordpressApiParser(RssFeedParser):
    """Convert WordPress JSON entries into raw municipal RSS items."""

    def __init__(self, date_extractor: WordPressDateExtractor) -> None:
        self._date_extractor = date_extractor

    def parse(self, raw_content: Any, source: RssFeedSource) -> List[RawRssItem]:
        if not isinstance(raw_content, list):
            return []
        parsed = [self._parse_entry(entry) for entry in raw_content if isinstance(entry, dict)]
        return [item for item in parsed if item is not None]

    def _parse_entry(self, entry: Dict[str, Any]) -> Optional[RawRssItem]:
        title = self._text(entry.get("title"))
        link = clean_text(str(entry.get("link") or ""))
        excerpt = self._text(entry.get("excerpt"))
        content = self._text(entry.get("content"))
        date_raw = clean_text(str(entry.get("date_gmt") or entry.get("date") or ""))
        if not title or not link.startswith("http") or not date_raw:
            return None
        post_date = self._date_extractor.parse_date(date_raw)
        event_date = self._date_extractor.extract_event_date(entry, content or excerpt, post_date)
        return RawRssItem(
            title=title,
            link=link,
            description=excerpt or title,
            pub_date=date_raw,
            event_date=event_date.isoformat() if event_date else "",
            venue=self._extract_venue(entry, content or excerpt),
            price_text=self._extract_price(entry),
        )

    def _extract_price(self, entry: Dict[str, Any]) -> str:
        for key in ("cost", "price", "ticket_price", "event_price"):
            val = self._text(entry.get(key))
            if val:
                return val
        for container in self._containers(entry):
            for key in ("ucret", "ucretsiz", "bilet_ucreti", "event_price", "price", "cost"):
                val = self._text(container.get(key))
                if val:
                    return val
        return ""

    def _text(self, value: Any) -> str:
        if isinstance(value, dict):
            rendered = value.get("rendered")
            return clean_text(strip_html(str(rendered))) if rendered else ""
        return clean_text(strip_html(str(value or "")))

    def _extract_venue(self, entry: Dict[str, Any], text: str) -> str:
        for container in self._containers(entry):
            venue = self._extract_venue_from_container(container)
            if venue:
                return venue
        label_value = extract_label_value(text, ["Mekan", "Yer", "Salon", "Sahne", "Venue"])
        if label_value:
            return label_value
        match = re.search(r"(Mekan|Yer|Salon|Sahne|Venue)\s*[:\-]\s*([^|,\n\r]+)", text, re.IGNORECASE)
        return clean_text(match.group(2)) if match else ""

    def _containers(self, entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        keys = (None, "acf", "meta", "event", "event_listing")
        values = [entry if key is None else entry.get(key) for key in keys]
        return [value for value in values if isinstance(value, dict)]

    def _extract_venue_from_container(self, container: Dict[str, Any]) -> str:
        for key in WORDPRESS_VENUE_KEYS:
            if key not in container:
                continue
            value = container.get(key)
            if isinstance(value, dict):
                rendered = value.get("rendered") or value.get("value")
                return clean_text(strip_html(str(rendered or "")))
            return clean_text(strip_html(str(value or "")))
        return ""

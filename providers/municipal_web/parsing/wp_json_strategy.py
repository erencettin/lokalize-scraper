"""WordPress JSON event parser with HTML card fallback."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import pytz

from providers.municipal_web.constants import ISTANBUL_TIMEZONE, MONTH_NAMES, TURKISH_MONTHS
from providers.municipal_web.models import MunicipalSite, RawEventItem
from providers.municipal_web.parsing.base_strategy import SiteParser
from providers.municipal_web.parsing.html_card_strategy import HtmlCardStrategy
from utils.date_parser import DateParser
from utils.text_normalizer import clean_text, strip_html


@dataclass
class WpJsonStrategy(SiteParser):
    """Parse WP JSON payloads and fallback to HTML card extraction."""

    fallback_strategy: HtmlCardStrategy
    detail_strategy: Optional[SiteParser] = None

    def parse_list(self, html: str, site: MunicipalSite) -> List[RawEventItem]:
        parsed = self._parse_wp_json(html, site)
        return parsed if parsed else self.fallback_strategy.parse_list(html, site)

    def parse_detail(self, html: str, item: RawEventItem, site: MunicipalSite) -> RawEventItem:
        if self.detail_strategy is not None:
            return self.detail_strategy.parse_detail(html, item, site)
        return item

    def _parse_wp_json(self, payload: str, site: MunicipalSite) -> List[RawEventItem]:
        text = clean_text(payload)
        if not text.startswith("{") and not text.startswith("["):
            return []
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return []
        entries = self._normalize_entries(data)
        return [item for item in (self._parse_entry(entry, site) for entry in entries) if item]

    def _normalize_entries(self, data: Any) -> List[Dict[str, Any]]:
        if isinstance(data, dict):
            for key in ("items", "events", "data", "posts", "results"):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            return []
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []

    def _parse_entry(self, entry: Dict[str, Any], site: MunicipalSite) -> Optional[RawEventItem]:
        title = clean_text(strip_html(self._json_text(entry.get("title")) or self._json_text(entry.get("name"))))
        if not title:
            return None
        start_dt = self._json_datetime(entry)
        date_text, time_text = self._to_date_time(start_dt)
        return RawEventItem(
            title=title,
            link=self._json_text(entry.get("link")) or site.base_url,
            venue=self._json_text(entry.get("venue")) or site.name,
            date=date_text,
            time=time_text,
            description=strip_html(self._json_text(entry.get("excerpt")) or self._json_text(entry.get("content")) or title),
            image_url=self._json_image_url(entry, site.base_url),
            price_text=self._json_text(entry.get("cost")) or self._json_text(entry.get("price")) or self._json_text(entry.get("ticket_price")),
        )

    def _json_text(self, value: Any) -> str:
        if isinstance(value, list):
            for item in value:
                extracted = self._json_text(item)
                if extracted:
                    return extracted
            return ""
        if isinstance(value, dict):
            for key in ("rendered", "text", "name", "title"):
                nested = value.get(key)
                if nested:
                    return clean_text(strip_html(str(nested)))
            return ""
        return clean_text(strip_html(str(value))) if value is not None else ""

    def _json_datetime(self, entry: Dict[str, Any]) -> Optional[datetime]:
        keys = ("event_date", "event_start", "start_date", "start", "date_gmt", "date", "modified_gmt")
        parsed = self._try_datetime_fields(entry, keys)
        if parsed is not None:
            return parsed
        acf = entry.get("acf")
        return self._try_datetime_fields(acf, ("event_date", "start_date", "date", "date_time", "time"))

    def _try_datetime_fields(self, payload: Any, keys: tuple[str, ...]) -> Optional[datetime]:
        if not isinstance(payload, dict):
            return None
        for key in keys:
            raw = payload.get(key)
            if not raw:
                continue
            parsed = DateParser.parse_iso_date(str(raw)) or self._extract_datetime_from_text(str(raw))
            if parsed is not None:
                return parsed
        return None

    def _extract_datetime_from_text(self, text: str) -> Optional[datetime]:
        normalized = clean_text(text).lower()
        date_match = re.search(r"(\d{1,2})\s+([a-zçğıöşü]+)[, ]+\s*(\d{4})", normalized)
        time_match = re.search(r"(\d{1,2})[:\.](\d{2})", normalized)
        if not date_match:
            return None
        day, month_key, year = int(date_match.group(1)), date_match.group(2), int(date_match.group(3))
        month = TURKISH_MONTHS.get(month_key)
        if not month:
            return None
        hour = int(time_match.group(1)) if time_match else 0
        minute = int(time_match.group(2)) if time_match else 0
        local_tz = pytz.timezone(ISTANBUL_TIMEZONE)
        return local_tz.localize(datetime(year, month, day, hour, minute)).astimezone(pytz.UTC)

    def _to_date_time(self, start_dt: Optional[datetime]) -> tuple[str, str]:
        if start_dt is None:
            return "", ""
        local_dt = start_dt.astimezone(pytz.timezone(ISTANBUL_TIMEZONE))
        date_text = f"{local_dt.day} {MONTH_NAMES.get(local_dt.month, MONTH_NAMES[3])} {local_dt.year}"
        return date_text, local_dt.strftime("%H:%M")

    def _json_image_url(self, entry: Dict[str, Any], base_url: str) -> str:
        embedded = entry.get("_embedded")
        if isinstance(embedded, dict):
            media = embedded.get("wp:featuredmedia")
            if isinstance(media, list) and media and isinstance(media[0], dict):
                for key in ("source_url", "guid", "url"):
                    value = media[0].get(key)
                    if value:
                        return urljoin(base_url, str(value))
        for key in ("jetpack_featured_media_url", "featured_image", "image"):
            value = entry.get(key)
            image_url = self._extract_image_url_value(value)
            if image_url:
                return urljoin(base_url, image_url)
        return ""

    def _extract_image_url_value(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            direct = value.get("url") or value.get("src") or value.get("link")
            if isinstance(direct, str):
                return direct
            sizes = value.get("sizes")
            if isinstance(sizes, dict):
                for size_key in ("full", "large", "medium", "thumbnail"):
                    size_value = sizes.get(size_key)
                    if isinstance(size_value, dict):
                        candidate = size_value.get("url") or size_value.get("source_url")
                        if isinstance(candidate, str):
                            return candidate
        return ""

"""biletimGO partner API provider."""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime
from typing import List, Optional

import cloudscraper
import pytz

from config import settings
from models.normalized_event import (
    NormalizedEvent,
    NormalizedOccurrence,
    NormalizedSource,
    PriceInfo,
)
from providers.base_provider import BaseProvider
from providers.biletimgo import category_map

_API_URL = "https://www.biletimgo.com/api/v1/etkinlik-listesi"
_TZ = pytz.timezone("Europe/Istanbul")
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return html.unescape(_TAG_RE.sub(" ", text)).strip()


def _parse_local_dt(value: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            naive = datetime.strptime(value.strip(), fmt)
            return _TZ.localize(naive)
        except ValueError:
            continue
    return None


def _extract_city(address: str) -> str:
    """Extract city name from Turkish address format 'Street, PostCode District / City'."""
    if "/" in address:
        city = address.rsplit("/", 1)[-1].strip()
        if city:
            return city
    return "İstanbul"


class BiletimgoProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__("BiletimGO", mode="http")
        self._logger = logging.getLogger(__name__)

    def fetch_and_parse(self) -> List[NormalizedEvent]:
        if not settings.biletimgo_enabled:
            self._logger.info("BiletimGO: disabled by config, skipping")
            return []
        token = settings.biletimgo_access_token.strip()
        if not token:
            self._logger.warning("BiletimGO: access token missing, skipping")
            return []

        raw = self._fetch(token)
        if raw is None:
            return []

        events = self._normalize(raw)
        self._logger.info("BiletimGO: parsed %d events", len(events))
        return events

    # ------------------------------------------------------------------
    def _fetch(self, token: str) -> Optional[list]:
        try:
            scraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )
            resp = scraper.get(
                _API_URL,
                params={"access_token": token},
                timeout=settings.biletimgo_timeout_seconds,
            )
        except Exception as exc:
            self._logger.error("BiletimGO: connection failed (%s): %s", type(exc).__name__, exc)
            return None

        if resp.status_code != 200:
            self._logger.error(
                "BiletimGO: HTTP %s — body: %s",
                resp.status_code,
                resp.text[:500],
            )
            return None

        try:
            data = resp.json()
        except Exception as exc:
            self._logger.error("BiletimGO: JSON parse failed — body: %s", resp.text[:500])
            return None

        if data.get("error") != "success":
            self._logger.error("BiletimGO: API error response: %s", data.get("error"))
            return None

        items = data.get("data")
        if not isinstance(items, list):
            self._logger.warning("BiletimGO: unexpected 'data' shape")
            return None

        return items

    def _normalize(self, items: list) -> List[NormalizedEvent]:
        now_utc = datetime.now(pytz.UTC)
        results: List[NormalizedEvent] = []

        for item in items:
            try:
                event = self._build_event(item, now_utc)
                if event is not None:
                    results.append(event)
            except Exception as exc:
                self._logger.debug("BiletimGO: skipping item id=%s (%s)", item.get("id"), exc)

        return results

    def _build_event(self, item: dict, now_utc: datetime) -> Optional[NormalizedEvent]:
        title = (item.get("etkinlik") or "").strip()
        if not title:
            return None

        start_str = item.get("baslangic") or ""
        start_dt = _parse_local_dt(start_str)
        if start_dt is None:
            self._logger.debug("BiletimGO: cannot parse date '%s' for '%s'", start_str, title)
            return None

        start_utc = start_dt.astimezone(pytz.UTC)
        if start_utc < now_utc:
            return None

        end_str = item.get("bitis") or ""
        end_dt = _parse_local_dt(end_str)

        raw_category = item.get("kategori") or ""
        category_id = category_map.resolve(raw_category)

        address = (item.get("adres") or "").strip()
        city = _extract_city(address) if address else "İstanbul"
        venue = (item.get("konum") or "").strip()

        raw_detail = (item.get("detay") or "").strip()
        description = _strip_html(raw_detail) if raw_detail else None

        event_url = (item.get("url") or "").strip() or None
        image_url = (item.get("gorsel") or "").strip() or None
        external_id = str(item.get("id")) if item.get("id") is not None else None
        organizer = (item.get("organizator") or "").strip()

        source = NormalizedSource(
            provider="BiletimGO",
            external_id=external_id,
            title=title,
            source_url=event_url or _API_URL,
            ticket_url=event_url,
            price=PriceInfo(is_unknown=True),
            brand_name=organizer or "biletimGO",
            is_official_seller=True,
        )

        occurrence = NormalizedOccurrence(
            start_at_utc=start_utc,
            local_date=start_dt.strftime("%Y-%m-%d"),
            local_time=start_dt.strftime("%H:%M"),
            timezone="Europe/Istanbul",
            venue_name=venue or title,
            sources=[source],
        )

        return NormalizedEvent(
            title=title,
            description=description,
            type=category_id,
            category=category_id,
            city_name=city,
            image_url=image_url,
            occurrences=[occurrence],
            source="biletimgo",
            providers=["BiletimGO"],
            provider_label="biletimGO",
            external_id=external_id,
            address=address or None,
            venue=venue or None,
        )

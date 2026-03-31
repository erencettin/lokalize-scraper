"""Build normalized events from municipal RSS raw items."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

import pytz

from config import settings
from models.normalized_event import NormalizedEvent, NormalizedOccurrence, NormalizedSource, PriceInfo
from providers.municipal_rss.constants import CATEGORY_MAP, DEFAULT_CITY_NAME, DEFAULT_VENUE, EXTERNAL_ID_HASH_LENGTH, EXTERNAL_ID_PREFIX, ISTANBUL_TIMEZONE, MAX_DESCRIPTION_LENGTH, TURKISH_MONTHS
from providers.municipal_rss.models import RawRssItem
from utils.date_parser import DateParser
from utils.price_parser import PriceParser
from utils.text_normalizer import clean_text


class EventBuilder:
    """Converts raw RSS parser items into NormalizedEvent objects."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self._istanbul_tz = pytz.timezone(ISTANBUL_TIMEZONE)
        self._price_pattern = re.compile(
            r"(?:ucretsiz|ücretsiz|free|bedava|"
            r"₺\s*\d[\d.,]*(?:\s*-\s*₺?\s*\d[\d.,]*)?|"
            r"\d[\d.,]*(?:\s*-\s*\d[\d.,]*)?\s*(?:tl|try|₺))",
            re.IGNORECASE,
        )

    def build(self, item: RawRssItem) -> Optional[NormalizedEvent]:
        title = clean_text(item.title)
        link = clean_text(item.link)
        if not title or not link.startswith("http"):
            return None
        start_at_utc = self.parse_pub_date(item.event_date or item.pub_date)
        if start_at_utc is None:
            return None
        description = self._truncate(clean_text(item.description or title))
        price = self._build_price(item)
        return NormalizedEvent(
            title=title,
            description=description,
            type=self._resolve_type(f"{title} {description} {item.category}"),
            city_name=settings.municipal_rss_city_name.strip() or DEFAULT_CITY_NAME,
            image_url=clean_text(item.image_url) or None,
            occurrences=[self._build_occurrence(start_at_utc, title, link, clean_text(item.venue) or DEFAULT_VENUE, price)],
        )

    def parse_pub_date(self, value: str) -> Optional[datetime]:
        raw = clean_text(value)
        if not raw:
            return None
        parsed = self._parse_timestamp(raw) or self._parse_iso_datetime(raw)
        parsed = parsed or self._parse_turkish_datetime(raw) or self._parse_rfc2822(raw)
        if parsed is not None:
            return parsed
        fallback = DateParser.parse_turkish_date(raw, ISTANBUL_TIMEZONE)
        if fallback is None:
            self._logger.warning("MunicipalRSS: unsupported date value=%s", raw)
        return fallback

    def _parse_timestamp(self, raw: str) -> Optional[datetime]:
        if not raw.isdigit():
            return None
        try:
            timestamp = float(raw)
            timestamp = timestamp / 1000.0 if timestamp > 100000000000 else timestamp
            return datetime.utcfromtimestamp(timestamp).replace(tzinfo=pytz.UTC)
        except Exception as exc:
            self._logger.warning("MunicipalRSS: timestamp parse failed value=%s reason=%s", raw, exc)
            return None

    def _parse_iso_datetime(self, raw: str) -> Optional[datetime]:
        candidate = self._normalize_iso_candidate(raw)
        if not candidate:
            return None
        parsed = DateParser.parse_iso_date(candidate)
        if parsed is not None:
            return parsed
        try:
            dt = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            localized = self._istanbul_tz.localize(dt) if dt.tzinfo is None else dt
            return localized.astimezone(pytz.UTC)
        except Exception as exc:
            self._logger.warning("MunicipalRSS: ISO parse failed value=%s reason=%s", raw, exc)
            return None

    def _normalize_iso_candidate(self, raw: str) -> str:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
            return f"{raw}T00:00:00+03:00"
        if re.match(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}", raw):
            return raw.replace(" ", "T", 1)
        return raw if re.match(r"^\d{4}-\d{2}-\d{2}T", raw) else ""

    def _parse_turkish_datetime(self, raw: str) -> Optional[datetime]:
        normalized = clean_text(raw).lower()
        month_match = re.search(r"(\d{1,2})\s+([a-zçğıöşü]+)\s+(\d{4}).{0,20}?(\d{2}:\d{2})", normalized)
        if month_match:
            month = TURKISH_MONTHS.get(month_match.group(2))
            if month is not None:
                return self._to_utc(int(month_match.group(3)), month, int(month_match.group(1)), month_match.group(4))
        dotted = re.search(r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}:\d{2})", normalized)
        if dotted:
            return self._to_utc(int(dotted.group(3)), int(dotted.group(2)), int(dotted.group(1)), dotted.group(4))
        return None

    def _to_utc(self, year: int, month: int, day: int, hm_text: str) -> Optional[datetime]:
        hour, minute = [int(part) for part in hm_text.split(":")]
        try:
            local_dt = self._istanbul_tz.localize(datetime(year, month, day, hour, minute))
            return local_dt.astimezone(pytz.UTC)
        except Exception as exc:
            self._logger.warning("MunicipalRSS: local datetime build failed reason=%s", exc)
            return None

    def _parse_rfc2822(self, raw: str) -> Optional[datetime]:
        try:
            parsed = parsedate_to_datetime(raw)
            localized = self._istanbul_tz.localize(parsed) if parsed.tzinfo is None else parsed
            return localized.astimezone(pytz.UTC)
        except Exception as exc:
            self._logger.warning("MunicipalRSS: RFC2822 parse failed value=%s reason=%s", raw, exc)
            return None

    def _build_occurrence(
        self,
        start_at_utc: datetime,
        title: str,
        link: str,
        venue_name: str,
        price: PriceInfo,
    ) -> NormalizedOccurrence:
        local_date, local_time, timezone_name = DateParser.to_local_parts(start_at_utc, ISTANBUL_TIMEZONE)
        return NormalizedOccurrence(
            start_at_utc=start_at_utc,
            local_date=local_date,
            local_time=local_time,
            timezone=timezone_name,
            venue_name=venue_name,
            sources=[self._build_source(title, link, price)],
        )

    def _build_source(self, title: str, link: str, price: PriceInfo) -> NormalizedSource:
        digest = hashlib.sha256(link.encode("utf-8")).hexdigest()[:EXTERNAL_ID_HASH_LENGTH]
        return NormalizedSource(
            provider="MunicipalRSS",
            external_id=f"{EXTERNAL_ID_PREFIX}-{digest}",
            title=title,
            source_url=link,
            price=price,
            ticket_status="unknown",
        )

    def _build_price(self, item: RawRssItem) -> PriceInfo:
        return PriceParser.resolve_from_text_candidates(
            candidates=self._extract_price_candidates(item),
            currency="TRY",
            source="municipal_rss_feed",
            legal_mode="public_feed",
            strategy="municipal_rss_text_scan",
            confidence=0.65,
            is_authoritative=False,
            is_derived=True,
            note="Feed text parsing; set unknown when explicit price is absent.",
            requires_terms_review=False,
        )

    def _extract_price_candidates(self, item: RawRssItem) -> list[str]:
        candidates: list[str] = []
        for text in (item.description, item.title, item.category):
            cleaned = clean_text(text)
            if not cleaned:
                continue
            matches = self._price_pattern.findall(cleaned)
            if matches:
                candidates.extend(clean_text(match) for match in matches if clean_text(match))
        return candidates

    def _resolve_type(self, text: str) -> str:
        lowered = clean_text(text).lower()
        for key, mapped in CATEGORY_MAP.items():
            if key in lowered:
                return mapped
        return "experience"

    def _truncate(self, text: str) -> str:
        return text if len(text) <= MAX_DESCRIPTION_LENGTH else f"{text[:MAX_DESCRIPTION_LENGTH].rstrip()}..."

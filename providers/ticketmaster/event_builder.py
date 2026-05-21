"""Build normalized events from Ticketmaster intermediate models."""

from __future__ import annotations

import logging
import unicodedata
import urllib.parse
from datetime import datetime
from typing import Optional

import pytz

from config import settings
from models.normalized_event import NormalizedEvent, NormalizedOccurrence, NormalizedSource, PriceInfo

from providers.ticketmaster.constants import (
    AFFILIATE_DEEP_LINK_TEMPLATE,
    AFFILIATE_URL_PREFIX,
    DEFAULT_CURRENCY,
    DEFAULT_EVENT_TYPE,
    DEFAULT_TICKET_STATUS,
    DEFAULT_VENUE_NAME,
    ISTANBUL_TIMEZONE,
    MAX_DESCRIPTION_LENGTH,
)
from providers.ticketmaster.models import RawTicketmasterEvent
from providers.ticketmaster.price_extractor import PriceExtractor
from utils.date_parser import DateParser
from utils.price_parser import PriceParser
from utils.text_normalizer import clean_text


class EventBuilder:
    """Converts RawTicketmasterEvent into shared NormalizedEvent objects."""

    def __init__(self, price_extractor: Optional[PriceExtractor] = None) -> None:
        self._logger = logging.getLogger(__name__)
        self._price_extractor = price_extractor or PriceExtractor()
        self._istanbul_tz = pytz.timezone(ISTANBUL_TIMEZONE)

    def build(self, item: RawTicketmasterEvent) -> Optional[NormalizedEvent]:
        """Build one normalized event or return None when essential data is missing."""
        if not item.event_id or not item.title:
            return None
        # Prefer affiliate URL from feed; if missing, construct an Impact Radius deep link
        # so every outbound URL goes through affiliate tracking (ircid=23908).
        effective_url = item.primary_event_url
        if not effective_url and item.source_url.startswith("http"):
            encoded = urllib.parse.quote(item.source_url, safe="")
            effective_url = AFFILIATE_DEEP_LINK_TEMPLATE.format(encoded_url=encoded)
            self._logger.debug(
                "Ticketmaster: constructed affiliate deep link event_id=%s brand=%r",
                item.event_id, item.brand_name,
            )
        if not effective_url or not effective_url.startswith("http"):
            return None
        # City filter: skip events not in the configured city.
        # venue_city is extracted from feed data; fallback to config city when missing.
        resolved_city = item.venue_city or settings.ticketmaster_city
        if _normalize_city(resolved_city) != _normalize_city(settings.ticketmaster_city):
            self._logger.debug(
                "Ticketmaster: skip event_id=%s reason=city_mismatch venue_city=%r target=%r",
                item.event_id, resolved_city, settings.ticketmaster_city,
            )
            return None

        start_at_utc = self._extract_datetime(item)
        if start_at_utc is None:
            self._logger.info("Ticketmaster: skip event_id=%s reason=missing_or_invalid_date", item.event_id)
            return None
        price = self._build_price(item)
        occurrence = self._build_occurrence(item, start_at_utc, price, effective_url)
        return NormalizedEvent(
            title=item.title,
            description=self._truncate_description(item.description),
            type=item.event_type or DEFAULT_EVENT_TYPE,
            city_name=item.venue_city or settings.ticketmaster_city,
            image_url=item.image_url or None,
            occurrences=[occurrence],
        )

    def _extract_datetime(self, item: RawTicketmasterEvent) -> Optional[datetime]:
        if item.date_time_utc:
            parsed = DateParser.parse_iso_date(item.date_time_utc)
            if parsed is not None:
                return parsed
        if not item.local_date:
            return None
        time_part = item.local_time or "00:00:00"
        if len(time_part) == 5:
            time_part = f"{time_part}:00"
        try:
            naive = datetime.fromisoformat(f"{item.local_date}T{time_part}")
            return self._istanbul_tz.localize(naive).astimezone(pytz.UTC)
        except Exception as exc:
            self._logger.warning("Ticketmaster: local datetime parse failed event_id=%s reason=%s", item.event_id, exc)
            return None

    def _build_occurrence(
        self,
        item: RawTicketmasterEvent,
        start_at_utc: datetime,
        price: PriceInfo,
        effective_url: str,
    ) -> NormalizedOccurrence:
        local_date, local_time, timezone_name = DateParser.to_local_parts(start_at_utc, ISTANBUL_TIMEZONE)
        return NormalizedOccurrence(
            start_at_utc=start_at_utc,
            local_date=local_date,
            local_time=local_time,
            timezone=timezone_name,
            venue_name=item.venue_name or DEFAULT_VENUE_NAME,
            sources=[self._build_source(item, price, effective_url)],
        )

    def _build_source(self, item: RawTicketmasterEvent, price: PriceInfo, effective_url: str) -> NormalizedSource:
        sales_start_at = None
        if item.sales_start_at:
            from utils.date_parser import DateParser
            sales_start_at = DateParser.parse_iso_date(item.sales_start_at)
        # Derive ticket_status: prefer Discovery Feed 2.0 eventStatus, fall back to DEFAULT_TICKET_STATUS.
        ticket_status = item.event_status or DEFAULT_TICKET_STATUS
        return NormalizedSource(
            provider="Ticketmaster",
            external_id=item.event_id,
            title=item.title,
            source_url=effective_url,           # affiliate URL when available
            ticket_url=f"Ticketmaster|{effective_url}",
            price=price,
            ticket_status=ticket_status,
            sales_start_at=sales_start_at,
            brand_name=item.brand_name or None,
            is_official_seller=item.is_official_seller,
        )

    def _build_price(self, item: RawTicketmasterEvent) -> PriceInfo:
        if item.raw_price_ranges:
            return self._price_extractor.extract_price(item.raw_price_ranges, origin=item.price_origin or "discovery_list")
        if item.price_min is None and item.price_max is None:
            return PriceParser.unknown_price(
                source="ticketmaster_discovery_v2_events",
                legal_mode="official_api",
                strategy="ticketmaster_price_unavailable",
            )
        return PriceParser.resolve_structured_range(
            min_value=item.price_min,
            max_value=item.price_max,
            currency=item.price_currency or DEFAULT_CURRENCY,
            source="ticketmaster_discovery_v2_events",
            legal_mode="official_api",
            strategy="ticketmaster_price_fields",
            confidence=0.95,
            is_authoritative=True,
            is_derived=False,
        )

    def _truncate_description(self, text: str) -> Optional[str]:
        cleaned = clean_text(text)
        if not cleaned:
            return None
        return cleaned[:MAX_DESCRIPTION_LENGTH]


def _normalize_city(name: str) -> str:
    """ASCII-fold city name so 'Istanbul' matches 'İstanbul'."""
    nfkd = unicodedata.normalize("NFKD", name.strip())
    return nfkd.encode("ascii", "ignore").decode("ascii").lower()

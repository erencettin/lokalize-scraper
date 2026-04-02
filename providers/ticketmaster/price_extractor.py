"""Price extraction and optional detail price enrichment for Ticketmaster."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Protocol

from config import settings
from models.normalized_event import PriceInfo
from providers.ticketmaster.constants import DEFAULT_CURRENCY
from providers.ticketmaster.models import RawTicketmasterEvent
from utils.price_parser import PriceParser


class TicketmasterDetailClient(Protocol):
    """Protocol used by PriceExtractor to request detail payloads."""

    def fetch_event_detail(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Fetch detail payload by event id."""
        ...


class PriceExtractor:
    """Encapsulates price parsing, formatting and detail fallback behavior."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self._detail_price_calls = 0

    def extract_price(self, price_ranges: List[Dict[str, Any]], *, origin: str = "discovery_list") -> PriceInfo:
        """Extract and format price from Ticketmaster priceRanges."""
        if not price_ranges:
            return PriceParser.unknown_price(
                source=self._resolve_source(origin),
                legal_mode="official_api",
                strategy="ticketmaster_price_range",
            )
        first = price_ranges[0] if isinstance(price_ranges[0], dict) else {}
        min_value = self._safe_float(first.get("min"))
        max_value = self._safe_float(first.get("max"))
        currency = first.get("currency") if isinstance(first.get("currency"), str) else DEFAULT_CURRENCY
        confidence = 0.98 if origin == "discovery_list" else 0.97
        return PriceParser.resolve_structured_range(
            min_value=min_value,
            max_value=max_value,
            currency=currency,
            source=self._resolve_source(origin),
            legal_mode="official_api",
            strategy="ticketmaster_price_range",
            confidence=confidence,
            is_authoritative=True,
            is_derived=False,
        )

    def needs_detail_fallback(self, price: PriceInfo) -> bool:
        """Return True when min/max are missing and detail fetch may help."""
        return price.min_value is None and price.max_value is None

    def enrich_with_detail(
        self,
        item: RawTicketmasterEvent,
        http_client: TicketmasterDetailClient,
        event_id: str,
    ) -> RawTicketmasterEvent:
        """Apply price from list response only.

        Türkiye market (source: wts-tr) doesn't support priceRanges in the
        Ticketmaster Inventory Status API. Detail fetching is disabled globally
        to avoid burning 800+ API calls per sync with zero payoff.
        Ref: https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/
        """
        current_price = self.extract_price(item.raw_price_ranges, origin=item.price_origin or "none")
        self._apply_price(item, current_price)
        # Detail price fetch is intentionally skipped for TR market — priceRanges
        # is only supported in US, CA, AU, NZ, MX markets.
        return item

    def _can_fetch_detail(self) -> bool:
        """Always returns False — detail fetch disabled for Türkiye market."""
        return False

    def _apply_price(self, item: RawTicketmasterEvent, price: PriceInfo) -> None:
        item.price_min = price.min_value
        item.price_max = price.max_value
        item.price_currency = price.currency or DEFAULT_CURRENCY

    def _safe_float(self, value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            parsed = float(value)
            return round(parsed, 2) if parsed >= 0 else None
        except (TypeError, ValueError):
            return None

    def _resolve_source(self, origin: str) -> str:
        if origin == "discovery_detail":
            return "ticketmaster_discovery_v2_event_detail"
        return "ticketmaster_discovery_v2_events"

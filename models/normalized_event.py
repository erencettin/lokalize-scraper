from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


# ---------------------------------------------------------------------------
# Provider-level price models (test/debug only — backend is source of truth)
# ---------------------------------------------------------------------------

@dataclass
class ProviderPrice:
    """Single provider price payload for test validation and debug inspection.

    In production the backend recomputes sorting and display from OccurrenceSource
    rows via BuildProviderPrices().  This dataclass is used only in unit tests
    (tests/utils/test_resolved_event_price.py) to verify the resolve() logic.
    """

    provider_name: str
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    currency: str = "TRY"
    price_text: Optional[str] = None
    source_url: Optional[str] = None
    is_free: bool = False


_FREE_PRICE_TEXTS = frozenset(
    {"ucretsiz", "cretsiz", "free", "bedava", "0", "0.00"}
)


@dataclass
class ResolvedEventPrice:
    """Resolved price view for a single event across all providers.

    Computed by :meth:`resolve` — used in unit tests only.  In production the
    equivalent logic lives in EventMapperExtensions.cs (backend).

    Sorting rules (mirrors backend):
    - TRY currency first, then USD, EUR, others.
    - Within same currency: MinPrice ascending (None counts as infinity).
    - Equal prices: provider_name alphabetical (case-insensitive).
    """

    provider_prices: List[ProviderPrice]
    best_min_price: Optional[Decimal]
    is_free: bool
    has_multiple_providers: bool
    all_prices_equal: bool
    display_price_text: str

    _CURRENCY_PRIORITY: dict = field(default_factory=lambda: {"TRY": 0, "USD": 1, "EUR": 2})

    @staticmethod
    def resolve(prices: List[ProviderPrice]) -> "ResolvedEventPrice":
        """Apply sorting and display rules, return a resolved view."""
        if not prices:
            return ResolvedEventPrice(
                provider_prices=[],
                best_min_price=None,
                is_free=False,
                has_multiple_providers=False,
                all_prices_equal=False,
                display_price_text="Fiyat bilgisi mevcut değil",
            )

        _currency_priority = {"TRY": 0, "USD": 1, "EUR": 2}

        def _sort_key(p: ProviderPrice) -> tuple:
            currency_rank = _currency_priority.get(p.currency.upper(), 99)
            price_val = p.min_price if p.min_price is not None else Decimal("Infinity")
            return (currency_rank, price_val, p.provider_name.lower())

        sorted_prices = sorted(prices, key=_sort_key)

        is_free = any(
            p.is_free or p.min_price == Decimal(0)
            for p in prices
        )
        known = [p.min_price for p in prices if p.min_price is not None]
        best_min = min(known) if known else None
        has_multiple = len(prices) > 1

        # all_prices_equal: per currency group, all known prices are identical
        from itertools import groupby as _groupby
        currency_groups: dict = {}
        for p in prices:
            if p.min_price is not None:
                currency_groups.setdefault(p.currency.upper(), set()).add(p.min_price)
        all_equal = all(len(v) <= 1 for v in currency_groups.values()) if currency_groups else False

        # display_price_text (card-level; provider name NOT embedded — separate widget)
        if is_free:
            display_text = "Ucretsiz"
        elif best_min is not None:
            first_with_price = next((p for p in sorted_prices if p.min_price is not None), None)
            symbol = ResolvedEventPrice._currency_symbol(first_with_price.currency if first_with_price else "TRY")
            if has_multiple:
                display_text = f"{best_min:,.0f} {symbol}'den baslayan"
            else:
                display_text = f"{best_min:,.0f} {symbol}"
        else:
            display_text = "Fiyat bilgisi mevcut degil"

        return ResolvedEventPrice(
            provider_prices=sorted_prices,
            best_min_price=best_min,
            is_free=is_free,
            has_multiple_providers=has_multiple,
            all_prices_equal=all_equal,
            display_price_text=display_text,
        )

    @staticmethod
    def _is_free_text(text: Optional[str]) -> bool:
        if not text:
            return False
        return text.strip().lower().replace("\u00fc", "u") in _FREE_PRICE_TEXTS

    @staticmethod
    def _currency_symbol(currency: str) -> str:
        return {"TRY": "\u20ba", "USD": "$", "EUR": "\u20ac"}.get(currency.upper(), currency)


# ---------------------------------------------------------------------------


class PriceResolution(BaseModel):
    strategy: str = "unknown"
    confidence: float = 0.0
    legal_mode: str = "unknown"
    source: str = "unknown"
    is_authoritative: bool = False
    is_derived: bool = False
    requires_terms_review: bool = False
    note: Optional[str] = None


class PriceInfo(BaseModel):
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    text: Optional[str] = None  # e.g. "500 TRY - 1200 TRY", "Free"
    currency: str = "TRY"
    is_free: bool = False
    is_unknown: bool = True
    resolution: PriceResolution = Field(default_factory=PriceResolution)


class NormalizedSource(BaseModel):
    provider: str
    external_id: Optional[str] = None
    title: str  # Provider-specific title if different
    description: Optional[str] = None  # Provider-specific description
    source_url: HttpUrl
    deep_link_url: Optional[HttpUrl] = None
    price: PriceInfo = Field(default_factory=PriceInfo)
    ticket_status: str = "unknown"  # on_sale, off_sale, sold_out, cancelled, postponed, rescheduled, coming_soon, free, unknown
    ticket_url: Optional[str] = None
    sales_start_at: Optional[datetime] = None
    brand_name: Optional[str] = None       # Display brand (e.g. "Biletix")
    is_official_seller: Optional[bool] = None


class NormalizedOccurrence(BaseModel):
    start_at_utc: Optional[datetime] = None   # None for ongoing/date-selectable attractions
    local_date: str  # YYYY-MM-DD
    local_time: Optional[str] = None           # None for ongoing/date-selectable attractions
    timezone: str = "Europe/Istanbul"
    venue_name: str
    district: Optional[str] = None
    sources: List[NormalizedSource] = Field(default_factory=list)


class NormalizedEvent(BaseModel):
    title: str
    description: Optional[str] = None
    type: str  # e.g., concert, theatre
    city_name: str
    image_url: Optional[HttpUrl] = None
    occurrences: List[NormalizedOccurrence] = Field(default_factory=list)
    attraction_id: Optional[str] = None              # TM attraction ID (artist / team)
    attraction_upcoming_count: Optional[int] = None  # TM upcomingEvents._total — global demand proxy
    source: str = "unknown"
    provider: Optional[str] = None  # Backward-compatible single provider field.
    providers: List[str] = Field(default_factory=list)
    provider_tags: List[str] = Field(default_factory=list)
    provider_label: Optional[str] = None
    source_urls: List[str] = Field(default_factory=list)
    external_id: Optional[str] = None
    category: Optional[str] = None
    address: Optional[str] = None
    venue: Optional[str] = None
    link: Optional[HttpUrl] = None
    source_url: Optional[HttpUrl] = None
    ticket_info: Optional[str] = None
    ticket_url: Optional[str] = None
    thumbnail_url: Optional[HttpUrl] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    fetched_at: Optional[datetime] = None

"""Data contracts for Ticketmaster provider internals."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RawTicketmasterEvent:
    """Intermediate model parsed from Ticketmaster API response."""

    event_id: str = ""
    title: str = ""
    source_url: str = ""
    date_time_utc: str = ""
    local_date: str = ""
    local_time: str = ""
    venue_name: str = ""
    description: str = ""
    image_url: str = ""
    event_type: str = "show"
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    price_currency: str = "TRY"
    price_origin: str = "discovery_list"
    classifications: List[Dict[str, Any]] = field(default_factory=list)
    raw_price_ranges: List[Dict[str, Any]] = field(default_factory=list)
    sales_start_at: Optional[str] = None
    # Discovery Feed 2.0 fields
    primary_event_url: str = ""          # affiliate-tracked URL (ticketmaster.evyy.net/c/...)
    event_status: str = ""               # onsale, offsale, cancelled, postponed, rescheduled
    brand_name: str = ""                 # e.g. "Biletix"
    is_official_seller: Optional[bool] = None
    venue_city: str = ""                 # city extracted from venue data

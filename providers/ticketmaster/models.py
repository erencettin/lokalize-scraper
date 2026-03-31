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

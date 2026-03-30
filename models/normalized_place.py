from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass(slots=True)
class NormalizedPlace:
    source: str
    external_id: Optional[str]
    title: str
    category: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    phone: Optional[str] = None
    hours: Optional[str] = None
    thumbnail_url: Optional[str] = None
    source_url: Optional[str] = None
    city: str = ""
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


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
    ticket_status: str = "unknown"  # on_sale, sold_out, coming_soon, free, unknown
    sales_start_at: Optional[datetime] = None


class NormalizedOccurrence(BaseModel):
    start_at_utc: datetime
    local_date: str  # YYYY-MM-DD
    local_time: str  # HH:MM
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
    thumbnail_url: Optional[HttpUrl] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    fetched_at: Optional[datetime] = None

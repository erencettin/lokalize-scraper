from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, HttpUrl

class PriceInfo(BaseModel):
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    text: Optional[str] = None # e.g. "₺500 - ₺1200", "Free"
    currency: str = "TRY"

class NormalizedSource(BaseModel):
    provider: str
    external_id: Optional[str] = None
    title: str # Provider-specific title if different
    description: Optional[str] = None # Provider-specific description
    source_url: HttpUrl
    deep_link_url: Optional[HttpUrl] = None
    price: PriceInfo = PriceInfo()
    ticket_status: str = "unknown" # on_sale, sold_out, coming_soon, free, unknown
    sales_start_at: Optional[datetime] = None

class NormalizedOccurrence(BaseModel):
    start_at_utc: datetime
    local_date: str  # YYYY-MM-DD
    local_time: str  # HH:MM
    timezone: str = "Europe/Istanbul"
    venue_name: str
    district: Optional[str] = None
    sources: List[NormalizedSource] = []

class NormalizedEvent(BaseModel):
    title: str
    description: Optional[str] = None
    type: str  # e.g., concert, theatre
    city_name: str
    image_url: Optional[HttpUrl] = None
    occurrences: List[NormalizedOccurrence] = []
    source: str = "unknown"
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

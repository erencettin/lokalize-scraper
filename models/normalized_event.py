from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, HttpUrl

class PriceInfo(BaseModel):
    value: Optional[float] = None
    text: Optional[str] = None
    currency: str = "TRY"

class NormalizedSource(BaseModel):
    provider: str
    external_id: Optional[str] = None
    title: str
    source_url: HttpUrl
    deep_link_url: Optional[HttpUrl] = None
    price: PriceInfo = PriceInfo()
    availability_status: str = "unknown"
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

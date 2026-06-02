from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BiletcomVenue:
    id: int
    name: str
    address: Optional[str]
    city: Optional[str]
    country: Optional[str]
    latitude: Optional[str]
    longitude: Optional[str]


@dataclass
class BiletcomPrice:
    id: int
    label: str
    type: str
    amount: float
    currency: str


@dataclass
class BiletcomOptionDates:
    single_date: Optional[str]   # "YYYY-MM-DD"
    start_date: Optional[str]
    end_date: Optional[str]
    sale_start_date: Optional[str]
    sale_end_date: Optional[str]


@dataclass
class BiletcomOption:
    id: int
    name: str
    is_date_selectable: bool
    is_hour_selectable: bool
    dates: BiletcomOptionDates
    venue: Optional[BiletcomVenue]
    prices: List[BiletcomPrice] = field(default_factory=list)


@dataclass
class BiletcomActivity:
    id: int
    name: str
    slug: str
    description: Optional[str]
    details: Optional[str]
    url: Optional[str]
    affiliate_url: Optional[str]
    logo: Optional[str]
    photos: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    min_price: Optional[float] = None
    max_price: Optional[float] = None


@dataclass
class BiletcomListing:
    """Lightweight item returned by GET /list."""
    id: int
    name: str
    slug: str
    description: Optional[str]
    min_price: Optional[float]
    max_price: Optional[float]

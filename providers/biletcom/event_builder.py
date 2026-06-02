"""Builds NormalizedEvent objects from Bilet.com API data."""
from __future__ import annotations

import html
import logging
import re
import unicodedata
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

import pytz

from models.normalized_event import (
    NormalizedEvent,
    NormalizedOccurrence,
    NormalizedSource,
    PriceInfo,
    PriceResolution,
)
from providers.biletcom import category_map
from providers.biletcom.constants import ONGOING_ATTRACTION_HOUR
from providers.biletcom.models import BiletcomActivity, BiletcomListing, BiletcomOption, BiletcomVenue

_TZ = pytz.timezone("Europe/Istanbul")
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_TAG_RE = re.compile(r"<[^>]+>")
_BLOCK_TAG_RE = re.compile(
    r"<(?:br\s*/?\s*|/?p|/?div|/?li|/?h[1-6]|/?ul|/?ol)[^>]*>",
    re.IGNORECASE,
)

_TURKISH_CITIES = {
    "istanbul": "İstanbul",
    "ankara": "Ankara",
    "izmir": "İzmir",
    "antalya": "Antalya",
    "bursa": "Bursa",
    "kocaeli": "Kocaeli",
    "eskisehir": "Eskişehir",
    "konya": "Konya",
    "adana": "Adana",
    "mersin": "Mersin",
    "gaziantep": "Gaziantep",
}

_DEFAULT_CITY = "İstanbul"


def _strip_html(text: str) -> str:
    decoded = html.unescape(text)
    decoded = _BLOCK_TAG_RE.sub("\n", decoded)
    cleaned = _TAG_RE.sub("", decoded)
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in cleaned.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(l for l in lines if l)).strip()


def _city_from_venue(venue: Optional[BiletcomVenue]) -> str:
    if not venue or not venue.city:
        return _DEFAULT_CITY
    key = venue.city.strip().lower()
    nfkd = unicodedata.normalize("NFKD", key)
    ascii_key = "".join(c for c in nfkd if not unicodedata.combining(c))
    return _TURKISH_CITIES.get(ascii_key, venue.city.strip()) or _DEFAULT_CITY


def _parse_date_str(date_str: str) -> Optional[datetime]:
    """Parse YYYY-MM-DD into a timezone-aware local datetime at ONGOING_ATTRACTION_HOUR."""
    try:
        naive = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(
            hour=ONGOING_ATTRACTION_HOUR, minute=0, second=0, microsecond=0
        )
        return _TZ.localize(naive)
    except ValueError:
        return None


def _synthetic_tomorrow() -> datetime:
    """Return tomorrow at ONGOING_ATTRACTION_HOUR in Istanbul time."""
    now_local = datetime.now(_TZ)
    tomorrow = (now_local + timedelta(days=1)).replace(
        hour=ONGOING_ATTRACTION_HOUR, minute=0, second=0, microsecond=0
    )
    return tomorrow


def _extract_dates(activity: BiletcomActivity, options: List[BiletcomOption]) -> List[datetime]:
    """Extract concrete future dates from options or fall back to synthetic date."""
    now_utc = datetime.now(pytz.UTC)
    seen: set[str] = set()
    dates: List[datetime] = []

    for opt in options:
        d = opt.dates
        candidate: Optional[datetime] = None

        if d.single_date:
            candidate = _parse_date_str(d.single_date)
        elif d.start_date:
            candidate = _parse_date_str(d.start_date)

        if candidate:
            key = candidate.strftime("%Y-%m-%d")
            if key not in seen and candidate.astimezone(pytz.UTC) > now_utc:
                seen.add(key)
                dates.append(candidate)

    # Try slug / name for date-embedded events (e.g. "…-2025-01-18")
    if not dates:
        for text in (activity.slug or "", activity.name or ""):
            for m in _DATE_RE.finditer(text):
                candidate = _parse_date_str(m.group(1))
                if candidate:
                    key = candidate.strftime("%Y-%m-%d")
                    if key not in seen and candidate.astimezone(pytz.UTC) > now_utc:
                        seen.add(key)
                        dates.append(candidate)
            if dates:
                break

    return dates


def _primary_venue(options: List[BiletcomOption]) -> Optional[BiletcomVenue]:
    for opt in options:
        if opt.venue:
            return opt.venue
    return None


class EventBuilder:
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def build(
        self,
        listing: BiletcomListing,
        activity: BiletcomActivity,
        options: List[BiletcomOption],
    ) -> Optional[NormalizedEvent]:
        title = (activity.name or "").strip()
        if not title:
            return None

        venue = _primary_venue(options)
        city = _city_from_venue(venue)

        description: Optional[str] = None
        if activity.description:
            description = _strip_html(activity.description)[:2000] or None
        if not description and activity.details:
            description = _strip_html(activity.details)[:2000] or None

        type_id = category_map.resolve(
            activity.categories,
            title=title,
            slug=activity.slug or "",
        )

        min_price = activity.min_price or listing.min_price
        max_price = activity.max_price or listing.max_price

        price = PriceInfo(
            min_value=min_price,
            max_value=max_price,
            currency="TRY",
            is_free=False,
            is_unknown=(min_price is None),
            resolution=PriceResolution(
                strategy="provider",
                confidence=1.0,
                source="bilet.com",
                is_authoritative=True,
            ),
        )

        affiliate_url = activity.affiliate_url or activity.url
        source_url = activity.url or affiliate_url or f"https://www.bilet.com/etkinlik/{activity.slug}"

        source = NormalizedSource(
            provider="bilet.com",
            external_id=str(activity.id),
            title=title,
            description=description,
            source_url=source_url,
            ticket_url=affiliate_url,
            price=price,
            ticket_status="on_sale",
            brand_name="bilet.com",
            is_official_seller=True,
        )

        dates = _extract_dates(activity, options)
        is_ongoing = not dates
        if is_ongoing:
            dates = [_synthetic_tomorrow()]

        image_url: Optional[str] = activity.logo or (activity.photos[0] if activity.photos else None)

        occurrences: List[NormalizedOccurrence] = []
        for dt in dates:
            dt_utc = dt.astimezone(pytz.UTC)
            occ = NormalizedOccurrence(
                start_at_utc=dt_utc,
                local_date=dt.strftime("%Y-%m-%d"),
                local_time=dt.strftime("%H:%M"),
                timezone="Europe/Istanbul",
                venue_name=(venue.name if venue else title),
                district=None,
                sources=[source],
            )
            occurrences.append(occ)

        if not occurrences:
            return None

        lat: Optional[float] = None
        lon: Optional[float] = None
        if venue and venue.latitude and venue.longitude:
            try:
                lat = float(venue.latitude)
                lon = float(venue.longitude)
            except (ValueError, TypeError):
                pass

        return NormalizedEvent(
            title=title,
            description=description,
            type=type_id,
            category=type_id,
            city_name=city,
            image_url=image_url,
            occurrences=occurrences,
            source="bilet.com",
            providers=["bilet.com"],
            provider_label="bilet.com",
            external_id=str(activity.id),
            address=(venue.address if venue else None),
            venue=(venue.name if venue else None),
            latitude=lat,
            longitude=lon,
        )

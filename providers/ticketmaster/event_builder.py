"""Build normalized events from Ticketmaster intermediate models."""

from __future__ import annotations

import logging
import unicodedata
from datetime import datetime
from typing import Optional

import pytz

from models.normalized_event import NormalizedEvent, NormalizedOccurrence, NormalizedSource, PriceInfo

from providers.ticketmaster.constants import (
    BILETIX_SOURCE_ATTRIBUTION,
    DEFAULT_CURRENCY,
    DEFAULT_EVENT_TYPE,
    DEFAULT_TICKET_STATUS,
    DEFAULT_VENUE_NAME,
    ISTANBUL_TIMEZONE,
    MAX_DESCRIPTION_LENGTH,
)
from providers.ticketmaster.models import RawTicketmasterEvent
from providers.ticketmaster.price_extractor import PriceExtractor
from utils.date_parser import DateParser
from utils.price_parser import PriceParser
from utils.text_normalizer import clean_text


# Ticketmaster returns city names in English; map to canonical DB names.
# Keys are pre-normalized (ASCII, no diacritics) — _normalize_city_key() is applied
# to the API value before lookup, so Turkish İ/Ş/Ğ/etc. are handled automatically.
_TM_CITY_MAP: dict[str, str] = {
    # Major metros
    "istanbul": "İstanbul",
    "ankara": "Ankara",
    "izmir": "İzmir",
    "antalya": "Antalya",
    "bursa": "Bursa",
    "adana": "Adana",
    "gaziantep": "Gaziantep",
    "konya": "Konya",
    "mersin": "Mersin",
    "kayseri": "Kayseri",
    "eskisehir": "Eskişehir",
    "samsun": "Samsun",
    "trabzon": "Trabzon",
    "denizli": "Denizli",
    "malatya": "Malatya",
    "manisa": "Manisa",
    "diyarbakir": "Diyarbakır",
    # Muğla / resort districts
    "mugla": "Muğla",
    "bodrum": "Muğla",
    "marmaris": "Muğla",
    "fethiye": "Muğla",
    # Aegean / Marmara
    "aydin": "Aydın",
    "balikesir": "Balıkesir",
    "canakkale": "Çanakkale",
    "edirne": "Edirne",
    "kirklareli": "Kırklareli",
    "tekirdag": "Tekirdağ",
    "kocaeli": "Kocaeli",
    "izmit": "Kocaeli",
    "yalova": "Yalova",
    "sakarya": "Sakarya",
    "adapazari": "Sakarya",
    "bolu": "Bolu",
    "duzce": "Düzce",
    "usak": "Uşak",
    "kutahya": "Kütahya",
    "afyonkarahisar": "Afyonkarahisar",
    "afyon": "Afyonkarahisar",
    # Mediterranean
    "isparta": "Isparta",
    "burdur": "Burdur",
    "hatay": "Hatay",
    "antakya": "Hatay",
    "iskenderun": "Hatay",
    "osmaniye": "Osmaniye",
    "kahramanmaras": "Kahramanmaraş",
    "kilis": "Kilis",
    # Central Anatolia
    "nevsehir": "Nevşehir",
    "kapadokya": "Nevşehir",
    "cappadocia": "Nevşehir",
    "nigde": "Niğde",
    "aksaray": "Aksaray",
    "karaman": "Karaman",
    "kirsehir": "Kırşehir",
    "yozgat": "Yozgat",
    "corum": "Çorum",
    "amasya": "Amasya",
    "tokat": "Tokat",
    "sivas": "Sivas",
    "kirikkale": "Kırıkkale",
    "cankiri": "Çankırı",
    # Black Sea
    "zonguldak": "Zonguldak",
    "bartin": "Bartın",
    "karabuk": "Karabük",
    "kastamonu": "Kastamonu",
    "sinop": "Sinop",
    "ordu": "Ordu",
    "giresun": "Giresun",
    "gumushane": "Gümüşhane",
    "bayburt": "Bayburt",
    "rize": "Rize",
    "artvin": "Artvin",
    # Eastern Anatolia
    "erzurum": "Erzurum",
    "erzincan": "Erzincan",
    "agri": "Ağrı",
    "igdir": "Iğdır",
    "ardahan": "Ardahan",
    "kars": "Kars",
    "van": "Van",
    "bitlis": "Bitlis",
    "mus": "Muş",
    "bingol": "Bingöl",
    "elazig": "Elazığ",
    "tunceli": "Tunceli",
    # Southeast
    "sanliurfa": "Şanlıurfa",
    "urfa": "Şanlıurfa",
    "mardin": "Mardin",
    "batman": "Batman",
    "sirnak": "Şırnak",
    "hakkari": "Hakkari",
    "siirt": "Siirt",
    "adiyaman": "Adıyaman",
}


def _normalize_city_key(text: str) -> str:
    """Lowercase and strip combining characters for city map lookup.

    Turkish dotless-i (ı, U+0131) has no NFKD decomposition so it survives
    the combining-char filter unchanged. Map keys use plain ASCII 'i', so we
    must replace ı→i before normalising, otherwise cities like Balıkesir,
    Diyarbakır, Aydın, Kırklareli all miss the lookup and events get dropped.
    """
    lowered = text.strip().lower().replace("ı", "i")
    nfkd = unicodedata.normalize("NFKD", lowered)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _resolve_city(venue_city: Optional[str]) -> Optional[str]:
    """Map a Ticketmaster venue city string to a canonical DB city name."""
    if not venue_city:
        return None
    return _TM_CITY_MAP.get(_normalize_city_key(venue_city))


class EventBuilder:
    """Converts RawTicketmasterEvent into shared NormalizedEvent objects."""

    def __init__(self, price_extractor: Optional[PriceExtractor] = None) -> None:
        self._logger = logging.getLogger(__name__)
        self._price_extractor = price_extractor or PriceExtractor()
        self._istanbul_tz = pytz.timezone(ISTANBUL_TIMEZONE)

    def build(self, item: RawTicketmasterEvent) -> Optional[NormalizedEvent]:
        """Build one normalized event or return None when essential data is missing."""
        if not item.event_id or not item.title:
            self._logger.info(
                "Ticketmaster: skip reason=missing_id_or_title event_id=%r title=%r",
                item.event_id, item.title,
            )
            return None
        # Prefer affiliate URL from feed (primaryEventUrl); fall back to plain source URL.
        # Do NOT construct fake evyy deep links — the format is proprietary and breaks.
        effective_url = item.primary_event_url or item.source_url
        if not effective_url or not effective_url.startswith("http"):
            self._logger.info(
                "Ticketmaster: skip event_id=%s title=%r reason=no_valid_url primary=%r source=%r",
                item.event_id, item.title, item.primary_event_url, item.source_url,
            )
            return None

        city_name = _resolve_city(item.venue_city)
        if city_name is None:
            self._logger.info(
                "Ticketmaster: skip event_id=%s title=%r reason=unrecognised_city venue_city=%r",
                item.event_id, item.title, item.venue_city,
            )
            return None

        start_at_utc = self._extract_datetime(item)
        if start_at_utc is None:
            self._logger.info(
                "Ticketmaster: skip event_id=%s title=%r reason=missing_or_invalid_date",
                item.event_id, item.title,
            )
            return None
        price = self._build_price(item)
        occurrence = self._build_occurrence(item, start_at_utc, price, effective_url)
        return NormalizedEvent(
            title=item.title,
            description=self._resolve_description(item),
            type=item.event_type or DEFAULT_EVENT_TYPE,
            city_name=city_name,
            image_url=item.image_url or None,
            occurrences=[occurrence],
            attraction_id=item.attraction_id,
            attraction_upcoming_count=item.attraction_upcoming_count,
        )

    def _extract_datetime(self, item: RawTicketmasterEvent) -> Optional[datetime]:
        if item.date_time_utc:
            parsed = DateParser.parse_iso_date(item.date_time_utc)
            if parsed is not None:
                return parsed
        if not item.local_date:
            return None
        time_part = item.local_time or "00:00:00"
        if len(time_part) == 5:
            time_part = f"{time_part}:00"
        try:
            naive = datetime.fromisoformat(f"{item.local_date}T{time_part}")
            return self._istanbul_tz.localize(naive).astimezone(pytz.UTC)
        except Exception as exc:
            self._logger.warning("Ticketmaster: local datetime parse failed event_id=%s reason=%s", item.event_id, exc)
            return None

    def _build_occurrence(
        self,
        item: RawTicketmasterEvent,
        start_at_utc: datetime,
        price: PriceInfo,
        effective_url: str,
    ) -> NormalizedOccurrence:
        local_date, local_time, timezone_name = DateParser.to_local_parts(start_at_utc, ISTANBUL_TIMEZONE)
        return NormalizedOccurrence(
            start_at_utc=start_at_utc,
            local_date=local_date,
            local_time=local_time,
            timezone=timezone_name,
            venue_name=item.venue_name or DEFAULT_VENUE_NAME,
            sources=[self._build_source(item, price, effective_url)],
        )

    def _build_source(self, item: RawTicketmasterEvent, price: PriceInfo, effective_url: str) -> NormalizedSource:
        sales_start_at = None
        if item.sales_start_at:
            from utils.date_parser import DateParser
            sales_start_at = DateParser.parse_iso_date(item.sales_start_at)
        # Derive ticket_status: prefer Discovery Feed 2.0 eventStatus, fall back to DEFAULT_TICKET_STATUS.
        ticket_status = item.event_status or DEFAULT_TICKET_STATUS
        return NormalizedSource(
            provider="Ticketmaster",
            external_id=item.event_id,
            title=item.title,
            source_url=effective_url,           # affiliate URL when available
            ticket_url=f"Ticketmaster|{effective_url}",
            price=price,
            ticket_status=ticket_status,
            sales_start_at=sales_start_at,
            brand_name=item.brand_name or None,
            is_official_seller=item.is_official_seller,
        )

    def _build_price(self, item: RawTicketmasterEvent) -> PriceInfo:
        if item.raw_price_ranges:
            return self._price_extractor.extract_price(item.raw_price_ranges, origin=item.price_origin or "discovery_list")
        if item.price_min is None and item.price_max is None:
            return PriceParser.unknown_price(
                source="ticketmaster_discovery_v2_events",
                legal_mode="official_api",
                strategy="ticketmaster_price_unavailable",
            )
        return PriceParser.resolve_structured_range(
            min_value=item.price_min,
            max_value=item.price_max,
            currency=item.price_currency or DEFAULT_CURRENCY,
            source="ticketmaster_discovery_v2_events",
            legal_mode="official_api",
            strategy="ticketmaster_price_fields",
            confidence=0.95,
            is_authoritative=True,
            is_derived=False,
        )

    def _truncate_description(self, text: str) -> Optional[str]:
        cleaned = clean_text(text)
        if not cleaned:
            return None
        return cleaned[:MAX_DESCRIPTION_LENGTH]

    def _resolve_description(self, item: RawTicketmasterEvent) -> Optional[str]:
        """Prefer the API-provided description; fall back to scraped Biletix "about" text.

        Discovery API leaves description fields empty for Biletix-branded events.
        When that happens and we scraped "Etkinliğe Dair" from biletix.com (with
        Biletix's permission, granted 2026-06-08), attribute the source explicitly.
        """
        if item.description:
            return self._truncate_description(item.description)
        about = clean_text(item.about_description or "")
        if not about:
            return None
        suffix = f" — {BILETIX_SOURCE_ATTRIBUTION}"
        return about[:MAX_DESCRIPTION_LENGTH - len(suffix)] + suffix



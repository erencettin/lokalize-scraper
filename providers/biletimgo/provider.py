"""biletimGO partner API provider."""

from __future__ import annotations

import html
import logging
import re
import unicodedata
from urllib.parse import unquote
from datetime import datetime
from typing import List, Optional

import cloudscraper
import pytz

from config import settings
from models.normalized_event import (
    NormalizedEvent,
    NormalizedOccurrence,
    NormalizedSource,
    PriceInfo,
)
from providers.base_provider import BaseProvider
from providers.biletimgo import category_map

_API_URL = "https://www.biletimgo.com/api/v1/etkinlik-listesi"
_TZ = pytz.timezone("Europe/Istanbul")
_TAG_RE = re.compile(r"<[^>]+>")
_BLOCK_TAG_RE = re.compile(
    r"<(?:br\s*/?\s*|/?p|/?div|/?li|/?h[1-6]|/?ul|/?ol|/?section)[^>]*>",
    re.IGNORECASE,
)
_BULLET_RE = re.compile(r"[ \t]*[•●][ \t]*")

# BiletimGO API returns all active events in a single call.
# The API documentation only supports access_token — no server-side category filtering.
# Category field is present in each event and handled client-side.


def _full_unescape(text: str) -> str:
    while True:
        decoded = html.unescape(text)
        if decoded == text:
            return decoded
        text = decoded


def _strip_html(text: str) -> str:
    decoded = html.unescape(unquote(text))
    decoded = _BLOCK_TAG_RE.sub("\n", decoded)
    cleaned = _TAG_RE.sub("", decoded)
    cleaned = _BULLET_RE.sub("\n• ", cleaned)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.split("\n")]
    lines = [l for l in lines if l]
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return result.strip()


_FIYAT_RANGE_RE = re.compile(r"^\s*(\d[\d.,]*)\s*[-–]\s*(\d[\d.,]*)\s*$")
_FIYAT_SINGLE_RE = re.compile(r"^\s*(\d[\d.,]*)\s*$")


def _parse_fiyat(fiyat: Optional[str]) -> PriceInfo:
    """Parse biletimGO 'fiyat' field into PriceInfo.

    Formats (from API docs):
      "450"              → min=max=450
      "300 - 500"        → min=300, max=500
      "Aktif Bilet Yok"  → is_unknown=True
      None / ""          → is_unknown=True
    """
    if not fiyat:
        return PriceInfo(is_unknown=True)

    raw = fiyat.strip()
    lower = raw.lower()

    if not any(c.isdigit() for c in raw):
        # "Aktif Bilet Yok" or any non-numeric string
        return PriceInfo(is_unknown=True)

    if "ücretsiz" in lower or raw == "0":
        return PriceInfo(min_value=0, max_value=0, currency="TRY", is_free=True, is_unknown=False)

    m = _FIYAT_RANGE_RE.match(raw)
    if m:
        try:
            min_v = float(m.group(1).replace(",", "."))
            max_v = float(m.group(2).replace(",", "."))
            return PriceInfo(min_value=min_v, max_value=max_v, currency="TRY", is_free=False, is_unknown=False)
        except ValueError:
            pass

    m = _FIYAT_SINGLE_RE.match(raw)
    if m:
        try:
            val = float(m.group(1).replace(",", "."))
            return PriceInfo(min_value=val, max_value=val, currency="TRY", is_free=False, is_unknown=False)
        except ValueError:
            pass

    return PriceInfo(is_unknown=True)


def _parse_local_dt(value: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            naive = datetime.strptime(value.strip(), fmt)
            return _TZ.localize(naive)
        except ValueError:
            continue
    return None


# Canonical Turkish city names (81 provinces) as stored in the DB.
_TURKISH_CITIES: list[str] = [
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Aksaray", "Amasya",
    "Ankara", "Antalya", "Ardahan", "Artvin", "Aydın", "Balıkesir",
    "Bartın", "Batman", "Bayburt", "Bilecik", "Bingöl", "Bitlis",
    "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum",
    "Denizli", "Diyarbakır", "Düzce", "Edirne", "Elazığ", "Erzincan",
    "Erzurum", "Eskişehir", "Gaziantep", "Giresun", "Gümüşhane",
    "Hakkari", "Hatay", "Iğdır", "Isparta", "İstanbul", "İzmir",
    "Kahramanmaraş", "Karabük", "Karaman", "Kars", "Kastamonu",
    "Kayseri", "Kilis", "Kırıkkale", "Kırklareli", "Kırşehir",
    "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa", "Mardin",
    "Mersin", "Muğla", "Muş", "Nevşehir", "Niğde", "Ordu",
    "Osmaniye", "Rize", "Sakarya", "Samsun", "Şanlıurfa", "Siirt",
    "Sinop", "Şırnak", "Sivas", "Tekirdağ", "Tokat", "Trabzon",
    "Tunceli", "Uşak", "Van", "Yalova", "Yozgat", "Zonguldak",
]

def _normalize_key(text: str) -> str:
    """Lowercase + strip combining chars (handles Turkish İ/Ş/Ğ → ASCII)."""
    nfkd = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# Lookup table: normalised (NFKD) lowercase → canonical DB name
_CITY_LOOKUP: dict[str, str] = {_normalize_key(c): c for c in _TURKISH_CITIES}


def _extract_city(address: str) -> Optional[str]:
    """Return canonical DB city name from a Turkish address, or None if not recognised.

    Searches each '/' and ',' segment from right to left so that 'District / City'
    and 'City / District / Venue' formats both resolve correctly.  NFKD normalization
    ensures Turkish İ/Ş/Ğ variants are handled robustly.
    """
    # Split on both '/' and ',' to handle comma-separated address formats.
    raw_segments = address.replace(",", "/").split("/")
    segments = [s.strip() for s in raw_segments]
    # Right-to-left: city is usually the last/second-last segment in Turkish addresses.
    for segment in reversed(segments):
        city = _CITY_LOOKUP.get(_normalize_key(segment))
        if city is not None:
            return city
    # Last-resort: scan each word in the address for a city name match.
    for word in address.replace("/", " ").replace(",", " ").split():
        city = _CITY_LOOKUP.get(_normalize_key(word))
        if city is not None:
            return city
    return None


_DEFAULT_CITY = "İstanbul"


def _extract_city_with_fallback(address: str, venue: str) -> str:
    """Try address first, then venue name, then return default city.

    BiletimGO is a Turkish-focused platform; the majority of events are in İstanbul.
    Returning a default prevents dropping valid events due to address parsing failures.
    """
    city = _extract_city(address) if address else None
    if city:
        return city
    city = _extract_city(venue) if venue else None
    if city:
        return city
    return _DEFAULT_CITY


class BiletimgoProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__("BiletimGO", mode="http")
        self._logger = logging.getLogger(__name__)

    def fetch_and_parse(self) -> List[NormalizedEvent]:
        if not settings.biletimgo_enabled:
            self._logger.info("BiletimGO: disabled by config, skipping")
            return []
        token = settings.biletimgo_access_token.strip()
        if not token:
            self._logger.warning("BiletimGO: access token missing, skipping")
            return []

        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )

        all_raw = self._fetch_all(scraper, token)
        if all_raw is None:
            return []

        events = self._normalize(all_raw)
        self._logger.info("BiletimGO: parsed %d events from %d raw items", len(events), len(all_raw))
        return events

    # ------------------------------------------------------------------
    def _fetch_all(self, scraper, token: str) -> Optional[list]:
        """Fetch all active events in a single API call (API only supports access_token)."""
        try:
            resp = scraper.get(
                _API_URL,
                params={"access_token": token},
                timeout=settings.biletimgo_timeout_seconds,
            )
        except Exception as exc:
            self._logger.error("BiletimGO: connection failed (%s): %s", type(exc).__name__, exc)
            return None

        if resp.status_code != 200:
            self._logger.error("BiletimGO: HTTP %s — body: %s", resp.status_code, resp.text[:300])
            return None

        try:
            data = resp.json()
        except Exception:
            self._logger.error("BiletimGO: JSON parse failed — body: %s", resp.text[:300])
            return None

        if data.get("error") != "success":
            self._logger.error("BiletimGO: API error: %s", data.get("error"))
            return None

        items = data.get("data")
        if not isinstance(items, list):
            self._logger.warning("BiletimGO: unexpected 'data' shape")
            return None

        self._logger.info("BiletimGO: fetched %d raw events", len(items))
        return items

    def _normalize(self, items: list) -> List[NormalizedEvent]:
        now_utc = datetime.now(pytz.UTC)
        results: List[NormalizedEvent] = []

        for item in items:
            try:
                event = self._build_event(item, now_utc)
                if event is not None:
                    results.append(event)
            except Exception as exc:
                self._logger.debug("BiletimGO: skipping item id=%s (%s)", item.get("id"), exc)

        return results

    def _build_event(self, item: dict, now_utc: datetime) -> Optional[NormalizedEvent]:
        title = _full_unescape((item.get("etkinlik") or "").strip())
        if not title:
            return None

        start_str = item.get("baslangic") or ""
        start_dt = _parse_local_dt(start_str)
        if start_dt is None:
            self._logger.debug("BiletimGO: cannot parse date '%s' for '%s'", start_str, title)
            return None

        start_utc = start_dt.astimezone(pytz.UTC)
        if start_utc < now_utc:
            return None

        raw_category = item.get("kategori") or ""
        category_id = category_map.resolve(raw_category)

        address = _full_unescape((item.get("adres") or "").strip())
        venue = _full_unescape((item.get("konum") or "").strip())
        city = _extract_city_with_fallback(address, venue)
        if city == _DEFAULT_CITY and not address:
            self._logger.debug("BiletimGO: no address for '%s', defaulting to %s", title, _DEFAULT_CITY)

        raw_detail = (item.get("detay") or "").strip()
        description = (_strip_html(raw_detail)[:4800] if raw_detail else None) or None

        event_url = (item.get("url") or "").strip() or None
        image_url = (item.get("gorsel") or "").strip() or None
        external_id = str(item.get("id")) if item.get("id") is not None else None
        organizer = _full_unescape((item.get("organizator") or "").strip())
        fiyat_raw = (item.get("fiyat") or "").strip() or None
        price = _parse_fiyat(fiyat_raw)

        source = NormalizedSource(
            provider="BiletimGO",
            external_id=external_id,
            title=title,
            source_url=event_url or _API_URL,
            ticket_url=event_url,
            price=price,
            brand_name=organizer or "biletimGO",
            is_official_seller=True,
        )

        occurrence = NormalizedOccurrence(
            start_at_utc=start_utc,
            local_date=start_dt.strftime("%Y-%m-%d"),
            local_time=start_dt.strftime("%H:%M"),
            timezone="Europe/Istanbul",
            venue_name=venue or title,
            sources=[source],
        )

        return NormalizedEvent(
            title=title,
            description=description,
            type=category_id,
            category=category_id,
            city_name=city,
            image_url=image_url,
            occurrences=[occurrence],
            source="BiletimGO",
            providers=["BiletimGO"],
            provider_label="biletimGO",
            external_id=external_id,
            address=address or None,
            venue=venue or None,
        )

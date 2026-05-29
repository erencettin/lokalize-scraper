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

# All BiletimGO categories — one request per category ensures complete coverage.
_BILETIMGO_CATEGORIES = [
    "Festival",
    "Konser",
    "Sahne",
    "Topluluklar",
    "Parti",
    "Eğitim",
    "Kamp",
    "Tiyatro",
    "Stand-Up",
    "Workshop",
    "Çocuk Etkinlikleri",
    "Diğer",
]


def _strip_html(text: str) -> str:
    decoded = html.unescape(unquote(text))
    decoded = _BLOCK_TAG_RE.sub("\n", decoded)
    cleaned = _TAG_RE.sub("", decoded)
    cleaned = _BULLET_RE.sub("\n• ", cleaned)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.split("\n")]
    lines = [l for l in lines if l]
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return result.strip()


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

    Searches each '/' segment from right to left so that 'District / City' and
    'City / District / Venue' formats both resolve correctly.  NFKD normalization
    ensures Turkish İ/Ş/Ğ variants are handled robustly.
    """
    segments = [s.strip() for s in address.split("/")]
    # Right-to-left: city is usually the last segment in Turkish addresses.
    for segment in reversed(segments):
        city = _CITY_LOOKUP.get(_normalize_key(segment))
        if city is not None:
            return city
    return None


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

        seen_ids: set[str] = set()
        all_raw: list = []

        for kategori in _BILETIMGO_CATEGORIES:
            items = self._fetch_category(scraper, token, kategori)
            if items is None:
                continue
            for item in items:
                item_id = str(item.get("id")) if item.get("id") is not None else None
                if item_id and item_id in seen_ids:
                    continue
                if item_id:
                    seen_ids.add(item_id)
                all_raw.append(item)
            self._logger.info("BiletimGO: kategori=%r fetched=%d total_so_far=%d", kategori, len(items), len(all_raw))

        events = self._normalize(all_raw)
        self._logger.info("BiletimGO: parsed %d events from %d categories", len(events), len(_BILETIMGO_CATEGORIES))
        return events

    # ------------------------------------------------------------------
    def _fetch_category(self, scraper, token: str, kategori: str) -> Optional[list]:
        try:
            resp = scraper.get(
                _API_URL,
                params={"access_token": token, "kategori": kategori},
                timeout=settings.biletimgo_timeout_seconds,
            )
        except Exception as exc:
            self._logger.error("BiletimGO: connection failed kategori=%r (%s): %s", kategori, type(exc).__name__, exc)
            return None

        if resp.status_code != 200:
            self._logger.error("BiletimGO: HTTP %s kategori=%r — body: %s", resp.status_code, kategori, resp.text[:300])
            return None

        try:
            data = resp.json()
        except Exception:
            self._logger.error("BiletimGO: JSON parse failed kategori=%r — body: %s", kategori, resp.text[:300])
            return None

        if data.get("error") != "success":
            self._logger.error("BiletimGO: API error kategori=%r: %s", kategori, data.get("error"))
            return None

        items = data.get("data")
        if not isinstance(items, list):
            self._logger.warning("BiletimGO: unexpected 'data' shape kategori=%r", kategori)
            return None

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
        title = html.unescape((item.get("etkinlik") or "").strip())
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

        end_str = item.get("bitis") or ""
        end_dt = _parse_local_dt(end_str)

        raw_category = item.get("kategori") or ""
        category_id = category_map.resolve(raw_category)

        address = html.unescape((item.get("adres") or "").strip())
        city = _extract_city(address) if address else None
        if city is None:
            self._logger.debug("BiletimGO: unrecognised city in address '%s', skipping '%s'", address, title)
            return None
        venue = html.unescape((item.get("konum") or "").strip())

        raw_detail = (item.get("detay") or "").strip()
        description = (_strip_html(raw_detail)[:4800] if raw_detail else None) or None

        event_url = (item.get("url") or "").strip() or None
        image_url = (item.get("gorsel") or "").strip() or None
        external_id = str(item.get("id")) if item.get("id") is not None else None
        organizer = html.unescape((item.get("organizator") or "").strip())

        source = NormalizedSource(
            provider="BiletimGO",
            external_id=external_id,
            title=title,
            source_url=event_url or _API_URL,
            ticket_url=event_url,
            price=PriceInfo(is_unknown=True),
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

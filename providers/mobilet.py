import requests
import time
import random
import re
import html
from typing import List, Optional
from datetime import datetime
import pytz
import logging

from providers.base_provider import BaseProvider
from models.normalized_event import NormalizedEvent, NormalizedOccurrence, NormalizedSource, PriceInfo
from utils.date_parser import DateParser


class MobiletProvider(BaseProvider):
    """
    Production-ready Mobilet provider using the discovered searchEvent API.
    Implements controlled pagination, session management, smart rate limiting,
    and incremental sync as per the revised implementation plan.
    """

    SEARCH_API_URL = "https://api-v2.mobilet.com/event/searchEvent"
    PAGE_SIZE = 20
    MAX_PAGES = 50  # Fail-safe: never exceed 50 pages (1000 events)
    MAX_RETRIES = 3

    def __init__(self):
        super().__init__("Mobilet", mode="http")
        self.base_url = "https://mobilet.com"
        self.logger = logging.getLogger(__name__)
        self.session: Optional[requests.Session] = None

    # ── Session & Request Management ───────────────────────────────────
    def _setup_session(self):
        """Create a fresh session with browser-like headers and Mobilet's required custom headers."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/json",
            "Origin": "https://mobilet.com",
            "Referer": "https://mobilet.com/",
            # Mobilet's required custom headers (discovered via browser network interception)
            "x-culture-code": "tr-TR",
            "x-saleschannel": "3",
            "x-channel-id": "1000",
            "x-member-channel-id": "11",
            "x-sub-channel-id": "1",
            "x-firm-id": "1",
        })
        # Warm up the session by visiting the homepage first (natural cookie acquisition)
        try:
            self.session.get(f"{self.base_url}/tr/", timeout=10)
        except Exception:
            pass  # Non-critical, continue without cookies

    # ── Controlled Pagination Engine ───────────────────────────────────
    def fetch_and_parse(self) -> List[NormalizedEvent]:
        self._setup_session()
        self.logger.info("Starting Mobilet Deep Crawl via searchEvent API...")

        all_events: List[NormalizedEvent] = []
        seen_ids: set = set()
        offset = 0
        page = 1
        consecutive_empties = 0

        while page <= self.MAX_PAGES:
            hits = self._fetch_page(offset)

            if hits is None:
                # Network/API error after retries → stop gracefully
                self.logger.warning(f"Stopping crawl at page {page} due to fetch errors.")
                break

            if len(hits) == 0:
                consecutive_empties += 1
                if consecutive_empties >= 2:
                    self.logger.info(f"No more events found. Stopping at page {page}.")
                    break
            else:
                consecutive_empties = 0

            new_count = 0
            for hit in hits:
                event = self._normalize_hit(hit)
                if event:
                    ext_id = event.occurrences[0].sources[0].external_id if event.occurrences else None
                    if ext_id and ext_id not in seen_ids:
                        seen_ids.add(ext_id)
                        all_events.append(event)
                        new_count += 1

            self.logger.info(f"  Page {page} (offset={offset}): {len(hits)} hits, {new_count} new events (total: {len(all_events)})")

            if new_count == 0 and len(hits) > 0:
                # All hits were duplicates → we've gone past the fresh data
                self.logger.info("All hits were duplicates. Stopping.")
                break

            offset += self.PAGE_SIZE
            page += 1

            # Smart Rate Limiting: human-like random delay
            delay = random.uniform(1.5, 3.0)
            time.sleep(delay)

        self.logger.info(f"Mobilet Deep Crawl complete. Total unique events: {len(all_events)}")
        return all_events

    # ── Smart Rate Limiting & Backoff ──────────────────────────────────
    def _fetch_page(self, offset: int) -> Optional[list]:
        """Fetch a single page of events with exponential backoff on errors."""
        payload = {
            "search": "",
            "eventTypeNames": [],
            "cityNames": [],
            "eventStartDateToTimestamp": None,
            "locationNames": [],
            "eventTagNames": [],
            "offset": offset,
            "limit": self.PAGE_SIZE,
        }

        for retry in range(self.MAX_RETRIES):
            try:
                resp = self.session.post(self.SEARCH_API_URL, json=payload, timeout=15)

                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and "data" in data:
                        inner = data["data"]
                        if isinstance(inner, dict):
                            return inner.get("hits", [])
                    return []

                if resp.status_code in (429, 403):
                    # Rate limited or blocked → exponential backoff
                    backoff = 2 ** retry
                    self.logger.warning(f"Rate limited ({resp.status_code}). Backing off {backoff}s...")
                    time.sleep(backoff)
                    continue

                self.logger.warning(f"Unexpected status {resp.status_code} at offset {offset}")
                return []

            except requests.exceptions.Timeout:
                self.logger.warning(f"Timeout at offset {offset}, retry {retry + 1}")
                time.sleep(2 ** retry)
            except Exception as e:
                self.logger.warning(f"Error fetching offset {offset}: {e}")
                time.sleep(2 ** retry)

        return None  # All retries exhausted

    # ── Data Normalization (Minimized Fields) ──────────────────────────
    def _normalize_hit(self, hit: dict) -> Optional[NormalizedEvent]:
        """Convert a raw API hit into a NormalizedEvent, extracting only required fields."""
        try:
            # Skip parent/venue container events — only process actual events
            if hit.get("isParent", False):
                return None

            # Title
            title = (hit.get("eventName") or "").strip()
            title = html.unescape(title)
            if not title:
                return None

            # External ID
            event_id = hit.get("eventId")
            if not event_id:
                return None
            external_id = str(event_id)

            # Source URL (Mobilet uses eventId-based URLs)
            slug = hit.get("seoUrl") or external_id
            source_url = f"{self.base_url}/tr/event/{slug}/"

            # Image URL
            img_obj = hit.get("eventHorizontalImage") or {}
            image_url = img_obj.get("url") if isinstance(img_obj, dict) else None

            # Date parsing — API uses Unix timestamps (seconds) and ISO strings
            start_at_utc = None
            # Prefer eventDate (ISO string) over timestamp
            event_date_str = hit.get("eventDate")
            timestamp = hit.get("eventStartDateTimestamp")

            if event_date_str and isinstance(event_date_str, str):
                try:
                    clean = event_date_str.replace("Z", "+00:00")
                    start_at_utc = datetime.fromisoformat(clean).astimezone(pytz.UTC)
                except Exception:
                    pass

            if not start_at_utc and timestamp:
                try:
                    start_at_utc = datetime.fromtimestamp(int(timestamp), tz=pytz.UTC)
                except Exception:
                    pass

            if not start_at_utc:
                return None  # Cannot sync events without dates

            # Venue
            loc_obj = hit.get("eventLocation") or {}
            venue_name = loc_obj.get("locationName", "İstanbul") if isinstance(loc_obj, dict) else "İstanbul"

            # Category / Type
            event_type = self._resolve_type(hit)

            # Price
            price_info = self._resolve_price(hit)

            # Description (minimal — API doesn't provide it in search results)
            description = (hit.get("description") or hit.get("shortDescription") or title)[:2000]

            # Build normalized structures
            local_date, local_time, tz = DateParser.to_local_parts(start_at_utc)

            source = NormalizedSource(
                provider=self.name,
                external_id=external_id,
                title=title,
                source_url=source_url,
                price=price_info,
                ticket_status=self._resolve_ticket_status(hit)
            )

            occurrence = NormalizedOccurrence(
                start_at_utc=start_at_utc,
                local_date=local_date,
                local_time=local_time,
                timezone=tz,
                venue_name=venue_name,
                sources=[source],
            )

            return NormalizedEvent(
                title=title,
                description=description,
                type=event_type,
                city_name="İstanbul",
                image_url=image_url,
                occurrences=[occurrence],
            )

        except Exception as e:
            self.logger.debug(f"Failed to normalize hit: {e}")
            return None

    def _resolve_type(self, hit: dict) -> str:
        """Map API category/tag data to our internal event type."""
        tags = hit.get("tags") or hit.get("eventTagNames") or []
        if isinstance(tags, str):
            tags = [tags]
        event_type_obj = hit.get("eventType") or {}
        category = (event_type_obj.get("eventTypeName") or "").lower() if isinstance(event_type_obj, dict) else ""
        combined = " ".join(str(t) for t in tags).lower() + " " + category

        type_mapping = {
            "concert": "concert", "konser": "concert", "muzik": "concert", "music": "concert",
            "tiyatro": "theatre", "theatre": "theatre", "sahne": "theatre",
            "stand": "standup",
            "festival": "festival", "fuar": "festival",
            "spor": "match", "sport": "match", "mac": "match",
            "sergi": "experience", "workshop": "experience", "atolye": "experience",
            "gezi": "experience", "tur": "experience", "aktivite": "experience",
        }

        for keyword, etype in type_mapping.items():
            if keyword in combined:
                return etype

        return "show"

    def _resolve_price(self, hit: dict) -> PriceInfo:
        """Extract price information from the API hit."""
        min_p = hit.get("minPrice") or hit.get("price") or hit.get("eventProductPrice")
        max_p = hit.get("maxPrice")

        if min_p is not None:
            try:
                val_min = float(min_p)
                val_max = float(max_p) if max_p else val_min
                
                if val_min == 0:
                    return PriceInfo(text="Ücretsiz", min_value=0, max_value=0, currency="TRY")

                if val_max != val_min:
                    text = f"{val_min:,.0f} - {val_max:,.0f} TL"
                else:
                    text = f"{val_min:,.0f} TL"

                return PriceInfo(text=text, min_value=val_min, max_value=val_max, currency="TRY")
            except (ValueError, TypeError):
                pass

        is_free = hit.get("isFree") or hit.get("isFreeEvent")
        if is_free:
            return PriceInfo(text="Ücretsiz", min_value=0, max_value=0, currency="TRY")

        return PriceInfo(text="Belirtilmemiş")

    def _resolve_ticket_status(self, hit: dict) -> str:
        """Determines ticket status from Mobilet hit data."""
        if hit.get("isSoldOut"): return "sold_out"
        if hit.get("isSalesClosed"): return "sold_out" # or unknown
        if hit.get("isComingSoon"): return "coming_soon"
        if hit.get("isFree"): return "free"
        return "on_sale"

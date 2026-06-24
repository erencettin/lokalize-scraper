"""Parse Ticketmaster API payloads into typed intermediate models."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from providers.ticketmaster.constants import DEFAULT_EVENT_TYPE, DEFAULT_VENUE_NAME, TICKETMASTER_CATEGORY_MAP
from providers.ticketmaster.models import RawTicketmasterEvent
from utils.constants import CATEGORY_MAP as SHARED_CATEGORY_MAP
from utils.text_normalizer import clean_text, strip_html


class ResponseParser:
    """Converts Ticketmaster JSON payloads into RawTicketmasterEvent objects."""

    def parse_page_response(self, payload: Dict[str, Any]) -> Tuple[List[RawTicketmasterEvent], Optional[int]]:
        """Parse one page response and return typed events plus total page count."""
        raw_events, total_pages = self._extract_page_payload(payload)
        parsed_events: List[RawTicketmasterEvent] = []
        for raw_event in raw_events:
            parsed = self.parse_event(raw_event)
            if parsed is not None:
                parsed_events.append(parsed)
        return parsed_events, total_pages

    def parse_event(self, raw: Dict[str, Any]) -> Optional[RawTicketmasterEvent]:
        """Parse one raw Ticketmaster event record (Discovery Feed 2.0 and standard API)."""
        if not isinstance(raw, dict):
            return None

        # --- IDs ---
        # Discovery Feed: "eventId" | Standard API: "id"
        event_id = clean_text(str(raw.get("eventId") or raw.get("id") or ""))

        # --- Title ---
        # Discovery Feed: "eventName" | Standard API: "name"
        title = clean_text(str(raw.get("eventName") or raw.get("name") or ""))

        # --- Dates ---
        # Discovery Feed: flat top-level fields | Standard API: dates.start.*
        dates_obj = raw.get("dates") if isinstance(raw.get("dates"), dict) else {}
        start = dates_obj.get("start", {}) if isinstance(dates_obj.get("start"), dict) else {}
        date_time_utc = clean_text(str(raw.get("eventStartDateTime") or start.get("dateTime") or ""))
        local_date    = clean_text(str(raw.get("eventStartLocalDate") or start.get("localDate") or ""))
        local_time    = clean_text(str(raw.get("eventStartLocalTime") or start.get("localTime") or ""))

        # --- Sales start ---
        # Discovery Feed: "onsaleStartDateTime" | Standard API: sales.public.startDateTime
        sales = raw.get("sales") if isinstance(raw.get("sales"), dict) else {}
        public_sales = sales.get("public") if isinstance(sales.get("public"), dict) else {}
        sales_start_raw = clean_text(str(
            raw.get("onsaleStartDateTime") or public_sales.get("startDateTime") or ""
        ))

        # --- Affiliate / Discovery Feed 2.0 specific fields ---
        # primaryEventUrl is the affiliate-tracked URL (ticketmaster.evyy.net/c/...).
        # Do NOT fall back to "url" here — that would overwrite the affiliate link with
        # a plain biletix.com URL for Biletix-branded events. source_url carries "url".
        primary_event_url = clean_text(str(raw.get("primaryEventUrl") or ""))

        # eventStatus: Discovery Feed top-level | Standard API: dates.status.code
        status_block = dates_obj.get("status") if isinstance(dates_obj.get("status"), dict) else {}
        event_status = clean_text(str(raw.get("eventStatus") or status_block.get("code") or "")).lower()

        brand_name = clean_text(str(raw.get("brandName") or ""))
        raw_official_seller = raw.get("officialSeller")
        is_official_seller: Optional[bool] = None
        if isinstance(raw_official_seller, bool):
            is_official_seller = raw_official_seller

        # --- Classifications ---
        # Standard API: nested array | Discovery Feed: flat strings
        price_ranges = self._extract_list(raw.get("priceRanges"))
        classifications = self._extract_list(raw.get("classifications"))
        if not classifications:
            classifications = self._build_classifications_from_feed(raw)

        # --- Image ---
        # Discovery Feed: "eventImageUrl" (single URL) | Standard API: images array
        image_url = clean_text(str(raw.get("eventImageUrl") or ""))
        if not image_url:
            image_url = self._extract_image_url(self._extract_list(raw.get("images")))

        # --- Description ---
        # Discovery Feed adds "eventInfo" / "eventNotes" alongside standard "info" / "pleaseNote"
        description = self._extract_description(raw)

        # --- Attraction (artist / team) metadata ---
        # Standard Discovery API: _embedded.attractions[]. Discovery Feed 2.0 may omit this.
        # Take only the first attraction — multi-headliner events are rare and secondary acts
        # would dilute the signal.
        attractions = self._extract_list(raw.get("_embedded", {}).get("attractions"))
        first_attraction = attractions[0] if attractions else {}
        attraction_id = clean_text(str(first_attraction.get("id") or "")) or None
        attraction_name = clean_text(str(first_attraction.get("name") or "")) or None
        upcoming_obj = first_attraction.get("upcomingEvents") if isinstance(first_attraction.get("upcomingEvents"), dict) else {}
        attraction_upcoming_count: Optional[int] = upcoming_obj.get("_total") if isinstance(upcoming_obj.get("_total"), int) else None

        # Promoter / organizer — standard API: promoter.name or promoters[0].name
        promoter_name: Optional[str] = None
        promoter_obj = raw.get("promoter")
        if isinstance(promoter_obj, dict):
            promoter_name = clean_text(str(promoter_obj.get("name") or "")) or None
        if not promoter_name:
            promoters_list = self._extract_list(raw.get("promoters"))
            if promoters_list:
                promoter_name = clean_text(str(promoters_list[0].get("name") or "")) or None

        return RawTicketmasterEvent(
            event_id=event_id,
            title=title,
            source_url=clean_text(str(raw.get("url") or "")),
            venue_city=self._extract_venue_city(raw),
            date_time_utc=date_time_utc,
            local_date=local_date,
            local_time=local_time,
            venue_name=self._extract_venue_name(raw),
            description=description,
            image_url=image_url,
            event_type=self._resolve_category(classifications, title),
            price_origin="discovery_list" if price_ranges else "none",
            classifications=classifications,
            raw_price_ranges=price_ranges,
            sales_start_at=sales_start_raw or None,
            primary_event_url=primary_event_url,
            event_status=event_status,
            brand_name=brand_name,
            is_official_seller=is_official_seller,
            attraction_id=attraction_id,
            attraction_name=attraction_name,
            attraction_upcoming_count=attraction_upcoming_count,
            promoter_name=promoter_name,
        )

    def _extract_page_payload(self, payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        embedded = payload.get("_embedded") if isinstance(payload, dict) else {}
        events = embedded.get("events") if isinstance(embedded, dict) else []
        page_info = payload.get("page") if isinstance(payload, dict) else {}
        total_pages = page_info.get("totalPages") if isinstance(page_info, dict) else None
        if not isinstance(events, list):
            events = []
        if not isinstance(total_pages, int):
            total_pages = None
        return events, total_pages

    def _extract_description(self, raw: Dict[str, Any]) -> str:
        # Discovery Feed: eventInfo / eventNotes | Standard API: info / pleaseNote
        raw_description = (
            raw.get("eventInfo") or raw.get("info") or
            raw.get("eventNotes") or raw.get("pleaseNote") or ""
        )
        return strip_html(raw_description) if isinstance(raw_description, str) else ""

    def _build_classifications_from_feed(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build a classifications-compatible structure from Discovery Feed flat fields."""
        segment = clean_text(str(raw.get("classificationSegment") or ""))
        genre   = clean_text(str(raw.get("classificationGenre") or ""))
        if not segment and not genre:
            return []
        entry: Dict[str, Any] = {}
        if segment:
            entry["segment"] = {"name": segment}
        if genre:
            entry["genre"] = {"name": genre}
        return [entry]

    def _extract_list(self, value: Any) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def _extract_image_url(self, images: List[Dict[str, Any]]) -> str:
        selected_url = ""
        selected_width = -1
        for image in images:
            image_url = image.get("url")
            if not isinstance(image_url, str) or not image_url.startswith("http"):
                continue
            width = image.get("width")
            score = int(width) if isinstance(width, int) else 0
            if score > selected_width:
                selected_width = score
                selected_url = image_url
        return selected_url

    def _extract_venue_name(self, raw: Dict[str, Any]) -> str:
        # Discovery Feed 2.0: raw["venue"]["venueName"]
        venue_block = raw.get("venue")
        if isinstance(venue_block, dict):
            name = clean_text(str(venue_block.get("venueName") or ""))
            if name:
                return name
        # Standard Discovery API: raw["_embedded"]["venues"][0]["name"]
        embedded = raw.get("_embedded")
        venues = embedded.get("venues") if isinstance(embedded, dict) else []
        first = venues[0] if isinstance(venues, list) and venues else {}
        name = clean_text(str(first.get("name") or "")) if isinstance(first, dict) else ""
        return name or DEFAULT_VENUE_NAME

    def _extract_venue_city(self, raw: Dict[str, Any]) -> str:
        # Discovery Feed 2.0: raw["venue"]["venueCity"]
        venue_block = raw.get("venue")
        if isinstance(venue_block, dict):
            city = clean_text(str(venue_block.get("venueCity") or ""))
            if city:
                return city
        # Standard Discovery API: raw["_embedded"]["venues"][0]["city"]["name"]
        embedded = raw.get("_embedded")
        venues = embedded.get("venues") if isinstance(embedded, dict) else []
        first = venues[0] if isinstance(venues, list) and venues else {}
        city_block = first.get("city") if isinstance(first, dict) else {}
        city_name = city_block.get("name") if isinstance(city_block, dict) else ""
        return clean_text(str(city_name or ""))

    def _resolve_category(self, classifications: List[Dict[str, Any]], title: str) -> str:
        lower_title = title.lower()

        # 1. Title overrides — highest precision, checked before classification data.
        if any(token in lower_title for token in ("stand up", "stand-up", "standup")):
            return "standup"
        if any(token in lower_title for token in ("konser", "concert", " tour")):
            return "concert"

        # 2. Primary-segment direct mapping — event type comes straight from the segment name.
        #    No title confirmation needed; primary segment reflects event type, not venue.
        primary_segment = self._get_primary_segment(classifications)
        if primary_segment in ("music", "muzik", "müzik"):
            return "concert"
        if primary_segment in ("sports", "spor"):
            return "match"
        if primary_segment in ("arts", "theatre", "theater", "sahne", "tiyatro"):
            return "theatre"
        if primary_segment in ("family", "aile"):
            return "kids"
        if primary_segment in ("education", "egitim", "eğitim", "eğitim & fazlası", "egitim & fazlasi"):
            return "workshop"
        if primary_segment in ("miscellaneous",):
            return "social"

        # 3. Token-based map for remaining classifications.
        tokens = " ".join(self._collect_tokens(classifications))
        for keyword, mapped in TICKETMASTER_CATEGORY_MAP.items():
            if keyword in tokens:
                return mapped
        for keyword, mapped in SHARED_CATEGORY_MAP.items():
            if keyword in tokens:
                return mapped

        return DEFAULT_EVENT_TYPE

    def _get_primary_segment(self, classifications: List[Dict[str, Any]]) -> str:
        """Return the first valid segment name (lowercase) from Ticketmaster classifications."""
        for item in classifications:
            segment = item.get("segment")
            name = segment.get("name") if isinstance(segment, dict) else ""
            cleaned = clean_text(str(name or "")).lower()
            if cleaned and cleaned not in ("undefined", ""):
                return cleaned
        return ""

    def _collect_tokens(self, classifications: List[Dict[str, Any]]) -> List[str]:
        tokens: List[str] = []
        for item in classifications:
            for key in ("segment", "genre", "subGenre"):
                node = item.get(key)
                name = node.get("name") if isinstance(node, dict) else ""
                cleaned = clean_text(str(name or "")).lower()
                if cleaned:
                    tokens.append(cleaned)
        return tokens

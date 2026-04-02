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
        """Parse one raw Ticketmaster event record."""
        print(f"[TM_PRICE] priceRanges={raw.get('priceRanges') if isinstance(raw, dict) else None}", flush=True)
        if not isinstance(raw, dict):
            return None
        start = raw.get("dates", {}).get("start", {}) if isinstance(raw.get("dates"), dict) else {}
        title = clean_text(str(raw.get("name") or ""))
        event_id = clean_text(str(raw.get("id") or ""))
        price_ranges = self._extract_list(raw.get("priceRanges"))
        if price_ranges:
            import logging
            logging.getLogger(__name__).info(f"Ticketmaster List API priceRanges FOUND for event_id={event_id}: {price_ranges}")
        classifications = self._extract_list(raw.get("classifications"))
        return RawTicketmasterEvent(
            event_id=event_id,
            title=title,
            source_url=clean_text(str(raw.get("url") or "")),
            date_time_utc=clean_text(str(start.get("dateTime") or "")),
            local_date=clean_text(str(start.get("localDate") or "")),
            local_time=clean_text(str(start.get("localTime") or "")),
            venue_name=self._extract_venue_name(raw),
            description=self._extract_description(raw),
            image_url=self._extract_image_url(self._extract_list(raw.get("images"))),
            event_type=self._resolve_category(classifications, title),
            price_origin="discovery_list" if price_ranges else "none",
            classifications=classifications,
            raw_price_ranges=price_ranges,
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
        raw_description = raw.get("info") or raw.get("pleaseNote") or ""
        return strip_html(raw_description) if isinstance(raw_description, str) else ""

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
        embedded = raw.get("_embedded")
        venues = embedded.get("venues") if isinstance(embedded, dict) else []
        first = venues[0] if isinstance(venues, list) and venues else {}
        name = first.get("name") if isinstance(first, dict) else ""
        cleaned = clean_text(str(name or ""))
        return cleaned or DEFAULT_VENUE_NAME

    def _resolve_category(self, classifications: List[Dict[str, Any]], title: str) -> str:
        lower_title = title.lower()
        if any(token in lower_title for token in ("stand up", "stand-up", "standup")):
            return "standup"
        tokens = " ".join(self._collect_tokens(classifications))
        for keyword, mapped in TICKETMASTER_CATEGORY_MAP.items():
            if keyword in tokens:
                return mapped
        for keyword, mapped in SHARED_CATEGORY_MAP.items():
            if keyword in tokens:
                return mapped
        return DEFAULT_EVENT_TYPE

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

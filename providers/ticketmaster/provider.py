"""Ticketmaster provider orchestration layer."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

import pytz
import requests

from config import settings
from models.normalized_event import NormalizedEvent
from providers.base_provider import BaseProvider
from providers.ticketmaster.biletix_detail_fetcher import BiletixDetailFetcher
from providers.ticketmaster.constants import BILETIX_DOMAIN, ERROR_PREVIEW_LENGTH
from providers.ticketmaster.event_builder import EventBuilder
from providers.ticketmaster.http_client import TicketmasterHttpClient
from providers.ticketmaster.price_extractor import PriceExtractor
from providers.ticketmaster.response_parser import ResponseParser
from services.matching_service import build_occurrence_dedup_key


class TicketmasterProvider(BaseProvider):
    """Fetches Ticketmaster events and maps them to the normalized contract."""

    def __init__(
        self,
        http_client: Optional[TicketmasterHttpClient] = None,
        response_parser: Optional[ResponseParser] = None,
        event_builder: Optional[EventBuilder] = None,
        price_extractor: Optional[PriceExtractor] = None,
        biletix_detail_fetcher: Optional[BiletixDetailFetcher] = None,
    ) -> None:
        super().__init__("Ticketmaster", mode="http")
        self._logger = logging.getLogger(__name__)
        self._price_extractor = price_extractor or PriceExtractor()
        self._http = http_client or TicketmasterHttpClient()
        self._parser = response_parser or ResponseParser()
        self._builder = event_builder or EventBuilder(price_extractor=self._price_extractor)
        self._biletix_detail = biletix_detail_fetcher or BiletixDetailFetcher()
        self._last_fetched_pages = 0

    @property
    def session(self) -> Optional[requests.Session]:
        """Compatibility property used by existing tests."""
        return self._http.session

    @session.setter
    def session(self, value: Optional[requests.Session]) -> None:
        self._http.session = value

    def fetch_and_parse(self) -> List[NormalizedEvent]:
        """Main provider entrypoint preserving BaseProvider interface."""
        if not settings.ticketmaster_enabled:
            self._logger.info("Ticketmaster: disabled by config, skipping provider")
            return []
        if not settings.ticketmaster_api_key.strip():
            self._logger.warning("Ticketmaster: API key missing, skipping provider safely")
            return []
        self._http.setup_session()
        if settings.biletix_detail_enabled:
            self._biletix_detail.setup_session()
        try:
            raw_events = self._fetch_all_events()
            parsed, skipped = self._normalize_events(raw_events)
            self._logger.info("Ticketmaster: summary pages=%s raw=%s parsed=%s skipped=%s", self._last_fetched_pages, len(raw_events), len(parsed), skipped)
            return parsed
        finally:
            self._http.close_session()
            if settings.biletix_detail_enabled:
                self._biletix_detail.close_session()

    def _fetch_all_events(self) -> List[Dict[str, Any]]:
        events = self._http.fetch_all_pages()
        self._last_fetched_pages = self._http.last_fetched_pages
        self._logger.info("Ticketmaster: fetched raw events=%s", len(events))
        return events

    def _normalize_events(self, raw_events: List[Dict[str, Any]]) -> tuple[List[NormalizedEvent], int]:
        import concurrent.futures
        parsed: List[NormalizedEvent] = []
        skipped = 0
        deduped = 0
        seen: Set[str] = set()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            for normalized in executor.map(self._normalize_with_detail, raw_events):
                if normalized is None:
                    skipped += 1
                    continue
                key = self._dedup_key(normalized)
                if key in seen:
                    deduped += 1
                    continue
                seen.add(key)
                parsed.append(normalized)
        self._logger.info(
            "Ticketmaster: normalize done raw=%s parsed=%s skipped=%s deduped=%s",
            len(raw_events), len(parsed), skipped, deduped,
        )
        return parsed, skipped

    def _normalize_with_detail(self, raw_event: Dict[str, Any]) -> Optional[NormalizedEvent]:
        item = self._parser.parse_event(raw_event)
        if item is None:
            self._logger.info(
                "Ticketmaster: skip reason=parse_failed raw_id=%r",
                raw_event.get("id") or raw_event.get("eventId"),
            )
            return None
        item = self._price_extractor.enrich_with_detail(item, self._http, item.event_id)
        item = self._enrich_with_biletix_about(item)
        normalized = self._builder.build(item)
        if normalized is None:
            return None
        if not self._is_within_lookahead(normalized.occurrences[0].start_at_utc):
            self._logger.info(
                "Ticketmaster: skip event_id=%s title=%r reason=outside_lookahead date=%s",
                item.event_id, item.title,
                normalized.occurrences[0].start_at_utc.date(),
            )
            return None
        return normalized

    def _enrich_with_biletix_about(self, item):
        """Fill in the missing description for Biletix events by scraping their detail page.

        Discovery API leaves eventInfo/eventNotes/info/pleaseNote (and brandName) empty for
        Biletix-sourced events, so brand_name can't be used for detection — we instead check
        whether source_url points at biletix.com (affiliate redirects embed the target URL as
        a literal substring, e.g. "...?u=https%3A%2F%2Fwww.biletix.com%2F..."). Biletix granted
        permission (2026-06-08) to scrape "Etkinliğe Dair" with attribution — see
        BILETIX_SOURCE_ATTRIBUTION in event_builder.
        """
        if not settings.biletix_detail_enabled:
            return item
        if item.description or not item.source_url:
            return item
        if BILETIX_DOMAIN not in item.source_url.lower():
            return item
        try:
            item.about_description = self._biletix_detail.fetch_about_description(item.source_url)
        except Exception as exc:
            self._logger.warning("Ticketmaster: biletix detail fetch failed event_id=%s reason=%s", item.event_id, exc)
        return item

    def _normalize_event(self, raw_event: Dict[str, Any]) -> Optional[NormalizedEvent]:
        """Compatibility helper that normalizes without any HTTP detail call."""
        item = self._parser.parse_event(raw_event)
        if item is None:
            return None
        normalized = self._builder.build(item)
        if normalized is None:
            return None
        return normalized if self._is_within_lookahead(normalized.occurrences[0].start_at_utc) else None

    def _fetch_page(self, page: int) -> Optional[Dict[str, Any]]:
        """Compatibility wrapper used by legacy tests."""
        return self._http.fetch_page(page)

    def _extract_page_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Compatibility wrapper that preserves old return shape."""
        embedded = payload.get("_embedded") if isinstance(payload, dict) else {}
        events = embedded.get("events") if isinstance(embedded, dict) else []
        page_info = payload.get("page") if isinstance(payload, dict) else {}
        total_pages = page_info.get("totalPages") if isinstance(page_info, dict) else None
        if not isinstance(events, list):
            events = []
        if not isinstance(total_pages, int):
            total_pages = None
        return {"events": events, "total_pages": total_pages}

    def _is_within_lookahead(self, start_at_utc: datetime) -> bool:
        now = datetime.now(pytz.UTC)
        if start_at_utc < now:
            return False
        lookahead_days = max(settings.ticketmaster_lookahead_days, 0)
        return True if lookahead_days == 0 else start_at_utc <= now + timedelta(days=lookahead_days)

    def _dedup_key(self, event: NormalizedEvent) -> str:
        first = event.occurrences[0]
        return build_occurrence_dedup_key(event.title, first.local_date, first.local_time)

    def _safe_error(self, exc: Exception) -> str:
        raw = f"{type(exc).__name__}: {exc}"
        key = settings.ticketmaster_api_key.strip()
        if key:
            raw = raw.replace(key, "***")
        return raw[:ERROR_PREVIEW_LENGTH]

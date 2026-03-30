"""Municipal RSS provider orchestration layer."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

import pytz

from config import settings
from models.normalized_event import NormalizedEvent
from providers.base_provider import BaseProvider
from providers.municipal_rss.constants import FEED_DELAY_SECONDS, PARSER_ATATURK_KITAPLIGI, PARSER_KULTURSANAT, PARSER_RSS_XML, PARSER_WORDPRESS
from providers.municipal_rss.event_builder import EventBuilder
from providers.municipal_rss.feed_registry import FeedRegistry
from providers.municipal_rss.http_client import RssHttpClient
from providers.municipal_rss.models import RawRssItem, RssFeedSource
from providers.municipal_rss.parsing import AtaturkKitapligiParser, KultursanatParser, RssFeedParser, RssXmlParser, WordpressApiParser
from providers.municipal_rss.parsing.date_extractor import WordPressDateExtractor
from services.matching_service import build_occurrence_dedup_key


class MunicipalRssProvider(BaseProvider):
    """Fetch municipal RSS/API sources and emit normalized events."""

    def __init__(
        self,
        http_client: Optional[RssHttpClient] = None,
        feed_registry: Optional[FeedRegistry] = None,
        event_builder: Optional[EventBuilder] = None,
    ) -> None:
        super().__init__("MunicipalRSS", mode="http")
        self._logger = logging.getLogger(__name__)
        self._http = http_client or RssHttpClient()
        self._registry = feed_registry or FeedRegistry()
        self._builder = event_builder or EventBuilder()
        date_extractor = WordPressDateExtractor(self._builder.parse_pub_date)
        self._parsers: Dict[str, RssFeedParser] = {
            PARSER_RSS_XML: RssXmlParser(),
            PARSER_WORDPRESS: WordpressApiParser(date_extractor),
            PARSER_KULTURSANAT: KultursanatParser(),
            PARSER_ATATURK_KITAPLIGI: AtaturkKitapligiParser(),
        }

    @property
    def session(self):
        """Compatibility accessor for tests that stub HTTP session."""
        return self._http.session

    @session.setter
    def session(self, value) -> None:
        self._http.session = value

    def fetch_and_parse(self) -> List[NormalizedEvent]:
        """Main provider entrypoint preserving BaseProvider interface."""
        if not settings.municipal_rss_enabled:
            self._logger.info("MunicipalRSS: disabled by config, skipping provider")
            return []
        sources = self._registry.get_sources()
        if not sources:
            self._logger.warning("MunicipalRSS: no RSS URLs configured, skipping")
            return []

        self._http.setup_session()
        try:
            return self._collect_events(sources)
        finally:
            self._http.close_session()

    def _collect_events(self, sources: List[RssFeedSource]) -> List[NormalizedEvent]:
        events: List[NormalizedEvent] = []
        seen: Set[str] = set()
        for index, source in enumerate(sources):
            for item in self._fetch_source_items(source):
                event = self._builder.build(item)
                if event is None or not self._is_eligible(event):
                    continue
                dedup_key = self._dedup_key(event)
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                events.append(event)
            if index < len(sources) - 1:
                time.sleep(FEED_DELAY_SECONDS)
        self._logger.info("MunicipalRSS: total parsed events=%s", len(events))
        return events

    def _fetch_source_items(self, source: RssFeedSource) -> List[RawRssItem]:
        parser = self._parsers[source.parser_type]
        if source.parser_type == PARSER_RSS_XML:
            return parser.parse(self._http.fetch_xml(source.url) or "", source)
        if source.parser_type == PARSER_WORDPRESS:
            items = parser.parse(self._http.fetch_json(source.url), source)
            return items if items or not source.fallback_url else parser.parse(self._http.fetch_json(source.fallback_url), source)
        return parser.parse(self._http.fetch_text(source.url), source)

    def _is_eligible(self, event: NormalizedEvent) -> bool:
        return bool(event.occurrences) and self._is_within_lookahead(event.occurrences[0].start_at_utc)

    def _is_within_lookahead(self, start_at_utc: datetime) -> bool:
        now = datetime.now(pytz.UTC)
        if start_at_utc < now:
            return False
        lookahead_days = max(settings.municipal_rss_lookahead_days, 0)
        return True if lookahead_days == 0 else start_at_utc <= now + timedelta(days=lookahead_days)

    def _dedup_key(self, event: NormalizedEvent) -> str:
        occurrence = event.occurrences[0]
        return build_occurrence_dedup_key(event.title, occurrence.local_date, occurrence.local_time)

"""Municipal web provider orchestration layer."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Set

import pytz

from config import settings
from models.normalized_event import NormalizedEvent
from providers.base_provider import BaseProvider
from providers.municipal_web.event_builder import EventBuilder
from providers.municipal_web.http_client import MunicipalHttpClient
from providers.municipal_web.models import MunicipalSite, RawEventItem
from providers.municipal_web.site_registry import SiteRegistry
from services.matching_service import MatchingService


class MunicipalWebProvider(BaseProvider):
    """Fetch municipal websites and emit normalized events."""

    def __init__(
        self,
        http_client: Optional[MunicipalHttpClient] = None,
        site_registry: Optional[SiteRegistry] = None,
        event_builder: Optional[EventBuilder] = None,
    ) -> None:
        super().__init__("MunicipalWeb", mode="http")
        self._logger = logging.getLogger(__name__)
        self._http = http_client or MunicipalHttpClient()
        self._registry = site_registry or SiteRegistry()
        self._builder = event_builder or EventBuilder()

    def fetch_and_parse(self) -> List[NormalizedEvent]:
        """Main provider entrypoint preserving BaseProvider interface."""
        if not settings.municipal_web_enabled:
            self._logger.info("MunicipalWeb: disabled by config, skipping provider")
            return []

        self._http.setup_session()
        try:
            import concurrent.futures
            events: List[NormalizedEvent] = []
            seen: Set[str] = set()
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(self._fetch_site, site): site for site in self._registry.get_sites()}
                for future in concurrent.futures.as_completed(futures):
                    try:
                        site_events = future.result()
                        site = futures[future]
                        self._logger.info("MunicipalWeb: site=%s events=%s", site.name, len(site_events))
                        for event in site_events:
                            key = self._dedup_key(event)
                            if key in seen:
                                continue
                            seen.add(key)
                            events.append(event)
                    except Exception as e:
                        self._logger.error("MunicipalWeb: site fetch failed reason=%s", str(e))
            self._logger.info("MunicipalWeb: total parsed events=%s", len(events))
            return events
        finally:
            self._http.close_session()

    def _fetch_site(self, site: MunicipalSite) -> List[NormalizedEvent]:
        results: List[NormalizedEvent] = []
        max_items = max(settings.municipal_web_max_items_per_site, 1)

        for list_url in site.list_urls:
            if not self._http.can_fetch(list_url):
                self._logger.info("MunicipalWeb: robots disallow list url=%s", list_url)
                continue

            raw_items = site.parser.parse_list(self._http.fetch_text(list_url), site)
            for item in raw_items[:max_items]:
                normalized = self._build_from_item(item, site)
                if normalized is not None and self._is_within_lookahead(normalized.occurrences[0].start_at_utc):
                    results.append(normalized)

            if results:
                break
        return results

    def _build_from_item(self, item: RawEventItem, site: MunicipalSite) -> Optional[NormalizedEvent]:
        detailed = item
        if site.requires_detail:
            if not item.link or not self._http.can_fetch(item.link):
                return None
            detail_html = self._http.fetch_text(item.link)
            if not detail_html:
                return None
            detailed = site.parser.parse_detail(detail_html, item, site)
            detailed.raw_html = detail_html
        else:
            detailed = site.parser.parse_detail("", item, site)
        return self._builder.build(detailed, site)

    def _dedup_key(self, event: NormalizedEvent) -> str:
        return MatchingService.build_occurrence_dedup_key(event)

    def _is_within_lookahead(self, start_at_utc: datetime) -> bool:
        now = datetime.now(pytz.UTC)
        if start_at_utc < now:
            return False
        lookahead_days = max(settings.municipal_web_lookahead_days, 0)
        return True if lookahead_days == 0 else start_at_utc <= now + timedelta(days=lookahead_days)

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from clients.supabase_client import SupabaseClient
from config import settings
from providers.serpapi_events import SerpApiEventsProvider


@dataclass(slots=True)
class EventsSyncStats:
    fetched: int = 0
    saved: int = 0
    deactivated: int = 0
    failed: int = 0
    request_count: int = 0


class EventsSyncService:
    def __init__(
        self,
        provider: Optional[SerpApiEventsProvider] = None,
        supabase_client: Optional[SupabaseClient] = None,
    ) -> None:
        self._logger = logging.getLogger(__name__)
        self._provider = provider or SerpApiEventsProvider()
        self._supabase = supabase_client or SupabaseClient()

    def run(self, *, dry_run: bool = False, city: Optional[str] = None) -> EventsSyncStats:
        stats = EventsSyncStats()
        resolved_city = (city or settings.serpapi_city).strip()

        try:
            events = self._provider.fetch_events(resolved_city)
            stats.fetched = len(events)
            stats.request_count = self._provider.request_count
        except Exception as exc:
            self._logger.error(
                "EventsSyncService: provider failed city=%s error=%s",
                resolved_city,
                type(exc).__name__,
            )
            stats.failed += 1
            return stats

        if not events:
            self._logger.info("EventsSyncService: no nearby events fetched city=%s", resolved_city)
            return stats

        try:
            stats.saved = self._supabase.upsert_serpapi_events(events, dry_run=dry_run)
            active_external_ids = {item.external_id for item in events if item.external_id}
            stats.deactivated = self._supabase.deactivate_missing_serpapi_events(
                city=resolved_city,
                active_external_ids=active_external_ids,
                dry_run=dry_run,
            )
        except Exception as exc:
            self._logger.error(
                "EventsSyncService: persistence failed city=%s error=%s detail=%s",
                resolved_city,
                type(exc).__name__,
                str(exc),
            )
            stats.failed += 1
            return stats

        self._logger.info(
            "EventsSyncService: completed city=%s fetched=%s saved=%s deactivated=%s dry_run=%s requests=%s",
            resolved_city,
            stats.fetched,
            stats.saved,
            stats.deactivated,
            dry_run,
            stats.request_count,
        )
        return stats

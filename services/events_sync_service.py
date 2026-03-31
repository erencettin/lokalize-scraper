from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from config import settings
from providers.serpapi_events import SerpApiEventsProvider
from services.sync_service import SyncService


@dataclass(slots=True)
class EventsSyncStats:
    fetched: int = 0
    saved: int = 0
    deactivated: int = 0
    failed: int = 0
    request_count: int = 0


class EventsSyncService:
    """
    Syncs SerpAPI events through the canonical C# backend pipeline.

    Instead of writing directly to Supabase (which caused duplicates when the
    same event was also ingested by the Ticketmaster/Municipal pipeline via C#),
    this service now POSTs to the .NET API endpoint POST /api/events/sync/bulk.

    This ensures C# MatchingService deduplication runs for ALL providers,
    preventing duplicate event cards in the Flutter app.
    """

    def __init__(
        self,
        provider: Optional[SerpApiEventsProvider] = None,
        sync_service: Optional[SyncService] = None,
    ) -> None:
        self._logger = logging.getLogger(__name__)
        self._provider = provider or SerpApiEventsProvider()
        self._sync_service = sync_service or SyncService()

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
            self._logger.info("EventsSyncService: no events fetched city=%s", resolved_city)
            return stats

        if dry_run:
            self._logger.info(
                "EventsSyncService: dry_run=True — skipping backend sync fetched=%s city=%s",
                stats.fetched,
                resolved_city,
            )
            stats.saved = stats.fetched
            return stats

        # Route through the C# backend pipeline (same as Ticketmaster/Municipal)
        # This ensures C# MatchingService deduplication runs for all providers.
        sync_run_id = f"serpapi-{uuid.uuid4().hex[:8]}-{datetime.now().strftime('%H%M%S')}"
        try:
            success = self._sync_service.sync_events_to_backend_bulk(events, sync_run_id)
            sync_status = getattr(self._sync_service, "last_backend_sync_status", "unknown")

            if success and sync_status in ("success", "skipped"):
                stats.saved = stats.fetched
                self._logger.info(
                    "EventsSyncService: backend sync completed city=%s fetched=%s saved=%s sync_run_id=%s",
                    resolved_city,
                    stats.fetched,
                    stats.saved,
                    sync_run_id,
                )
            else:
                stats.failed += 1
                self._logger.error(
                    "EventsSyncService: backend sync failed city=%s sync_run_id=%s",
                    resolved_city,
                    sync_run_id,
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

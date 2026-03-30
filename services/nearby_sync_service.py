from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from clients.supabase_client import SupabaseClient
from config import settings
from providers.serpapi_local import SerpApiLocalProvider


@dataclass(slots=True)
class NearbySyncStats:
    fetched: int = 0
    saved: int = 0
    deactivated: int = 0
    failed: int = 0
    request_count: int = 0


class NearbySyncService:
    def __init__(
        self,
        provider: Optional[SerpApiLocalProvider] = None,
        supabase_client: Optional[SupabaseClient] = None,
    ) -> None:
        self._logger = logging.getLogger(__name__)
        self._provider = provider or SerpApiLocalProvider()
        self._supabase = supabase_client or SupabaseClient()

    def run(self, *, dry_run: bool = False, city: Optional[str] = None) -> NearbySyncStats:
        stats = NearbySyncStats()
        resolved_city = (city or settings.serpapi_city).strip()

        try:
            places = self._provider.fetch_places(resolved_city)
            stats.fetched = len(places)
            stats.request_count = self._provider.request_count
        except Exception as exc:
            self._logger.error(
                "NearbySyncService: provider failed city=%s error=%s",
                resolved_city,
                type(exc).__name__,
            )
            stats.failed += 1
            return stats

        if not places:
            self._logger.info("NearbySyncService: no nearby places fetched city=%s", resolved_city)
            return stats

        try:
            stats.saved = self._supabase.upsert_nearby_places(places, dry_run=dry_run)
            active_external_ids = {item.external_id for item in places if item.external_id}
            stats.deactivated = self._supabase.deactivate_missing_nearby_places(
                source="serpapi_google_local",
                city=resolved_city,
                active_external_ids=active_external_ids,
                dry_run=dry_run,
            )
        except Exception as exc:
            self._logger.error(
                "NearbySyncService: persistence failed city=%s error=%s detail=%s",
                resolved_city,
                type(exc).__name__,
                str(exc),
            )
            stats.failed += 1
            return stats

        self._logger.info(
            "NearbySyncService: completed city=%s fetched=%s saved=%s deactivated=%s dry_run=%s requests=%s",
            resolved_city,
            stats.fetched,
            stats.saved,
            stats.deactivated,
            dry_run,
            stats.request_count,
        )
        return stats

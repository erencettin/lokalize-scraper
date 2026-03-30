from typing import List, Optional
from models.normalized_event import NormalizedEvent, NormalizedOccurrence
from clients.supabase_client import SupabaseClient
from clients.backend_client import BackendClient
from config import settings
from utils.text_normalizer import TextNormalizer
from utils.date_parser import DateParser
from utils.price_parser import PriceParser
from utils.provider_enrichment import build_provider_payload_from_event
from services.matching_service import MatchingService
from datetime import datetime
import pytz
import logging

class SyncService:
    def __init__(
        self,
        supabase_client: Optional[SupabaseClient] = None,
        backend_client: Optional[BackendClient] = None,
    ):
        self._supabase = supabase_client or SupabaseClient()
        self._backend = backend_client or BackendClient(base_url=settings.backend_url)
        self._text_normalizer = TextNormalizer()
        self._date_parser = DateParser()
        self._price_parser = PriceParser()
        self._items_cache = {} 
        self.last_backend_sync_status = "unknown"

    def sync_events_to_backend_bulk(self, events: List[NormalizedEvent], sync_run_id: str) -> bool:
        """
        V4: Maps normalized events to .NET API DTOs and performs bulk sync.
        """
        backend_enabled = getattr(self._backend, "enabled", True)
        if not backend_enabled:
            self.last_backend_sync_status = "skipped"
            skip_reason = getattr(self._backend, "skip_reason", None)
            if isinstance(skip_reason, str) and skip_reason.strip():
                for line in skip_reason.splitlines():
                    logging.warning(line)
            else:
                logging.warning("⚠️ Backend sync atlandı.")
            return True

        dtos = []
        for event in events:
            for occurrence in event.occurrences:
                # Map occurrences and their sources to flat DTOs for the backend
                for source in occurrence.sources:
                    min_p, max_p = self._price_parser.parse_prices(source.price.text)
                    provider_payload = build_provider_payload_from_event(event, occurrence, source)
                    
                    dto = {
                        "provider": provider_payload.get("provider") or source.provider,
                        "providers": provider_payload.get("providers", []),
                        "providerTags": provider_payload.get("provider_tags", []),
                        "providerLabel": provider_payload.get("provider_label"),
                        "sourceUrls": provider_payload.get("source_urls", []),
                        # snake_case aliases for consumers that are not camelCase-aware yet
                        "provider_tags": provider_payload.get("provider_tags", []),
                        "provider_label": provider_payload.get("provider_label"),
                        "source_urls": provider_payload.get("source_urls", []),
                        "externalId": source.external_id,
                        "title": event.title,
                        "description": event.description,
                        "imageUrl": str(event.image_url) if event.image_url else None,
                        "type": event.type,
                        "cityName": event.city_name,
                        "venueName": occurrence.venue_name,
                        "localStartDate": occurrence.local_date,
                        "localStartTime": occurrence.local_time,
                        "startAtUtc": occurrence.start_at_utc.isoformat(),
                        "sourceUrl": str(source.source_url),
                        "minPrice": source.price.min_value if source.price.min_value is not None else min_p,
                        "maxPrice": source.price.max_value if source.price.max_value is not None else max_p,
                        "priceText": source.price.text,
                        "ticketStatus": source.ticket_status
                    }
                    dtos.append(dto)
        
        if not dtos:
            logging.warning("No events to sync in bulk.")
            self.last_backend_sync_status = "skipped"
            return True

        success = self._backend.sync_events_bulk(dtos, sync_run_id)
        self.last_backend_sync_status = "success" if success else "failed"
        return success

    def trigger_stale_cleanup(self, sync_run_id: str):
        """V4: Triggers lifecycle cleanup in the backend."""
        return self._backend.deactivate_stale(sync_run_id)

    def sync_event(self, event: NormalizedEvent, existing_items_override: List[dict] = None) -> dict:
        """
        Coordinates the high-level sync process for an event and all its occurrences.
        Legacy method for direct supabase sync.
        """
        stats = {"inserted": 0, "updated": 0, "failed": 0}
        
        # 1. Fetch or use cached existing items
        if existing_items_override is not None:
            existing_items = existing_items_override
        else:
            city_name = event.city_name
            if city_name not in self._items_cache:
                self._items_cache[city_name] = self._fetch_relevant_items(city_name)
            existing_items = self._items_cache[city_name]
            
        if existing_items is None:
            existing_items = []
            
        matcher = MatchingService(existing_items)

        for occurrence in event.occurrences:
            try:
                res = self._sync_occurrence(event, occurrence, matcher)
                if res == "inserted": stats["inserted"] += 1
                elif res == "updated": stats["updated"] += 1
            except Exception as e:
                logging.error(f"Failed to sync occurrence for {event.title} at {occurrence.start_at_utc}: {e}")
                stats["failed"] += 1
        
        return stats

    def _sync_occurrence(self, event: NormalizedEvent, occurrence: NormalizedOccurrence, matcher: MatchingService):
        # Legacy method for direct Supabase sync
        # Implementation omitted for brevity/unused in V4 bulk flow
        pass
        
    def deactivate_expired_events(self, city_name: str):
        # Legacy
        pass

    def deactivate_stale_sources(self, city_name: str, provider: str, run_start_time: datetime) -> int:
        # Legacy
        return 0

    def cleanup_orphaned_items(self, city_name: str) -> int:
        # Legacy
        return 0

    def _fetch_relevant_items(self, city_name: str) -> List[dict]:
        # Legacy
        return []

    def _resolve_city_id(self, city_name: str) -> str:
        # Legacy
        return "11111111-1111-1111-1111-111111111111"

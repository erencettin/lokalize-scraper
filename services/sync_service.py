import itertools
import logging
import time
from typing import Iterator, List, Optional

from clients.backend_client import BackendClient
from config import settings
from models.normalized_event import NormalizedEvent
from utils.price_parser import PriceParser
from utils.provider_enrichment import build_provider_payload_from_event

_CHUNK_SIZE = 50
_INTER_CHUNK_SLEEP_SECONDS = 1.5


class SyncService:
    def __init__(
        self,
        backend_client: Optional[BackendClient] = None,
    ):
        self._backend = backend_client or BackendClient(base_url=settings.backend_url)
        self._price_parser = PriceParser()
        self.last_backend_sync_status = "unknown"

    def _build_dtos(self, events: List[NormalizedEvent]) -> Iterator[dict]:
        for event in events:
            for occurrence in event.occurrences:
                for source in occurrence.sources:
                    min_p, max_p = self._price_parser.parse_prices(source.price.text or "")
                    resolved_min = source.price.min_value if source.price.min_value is not None else min_p
                    resolved_max = source.price.max_value if source.price.max_value is not None else max_p
                    price_resolution = (
                        source.price.resolution.model_dump(mode="json")
                        if getattr(source.price, "resolution", None) is not None
                        else {
                            "strategy": "unknown",
                            "confidence": 0.0,
                            "legal_mode": "unknown",
                            "source": "unknown",
                            "is_authoritative": False,
                            "is_derived": False,
                            "requires_terms_review": False,
                            "note": None,
                        }
                    )
                    provider_payload = build_provider_payload_from_event(event, occurrence, source)
                    yield {
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
                        "minPrice": resolved_min,
                        "maxPrice": resolved_max,
                        "currency": source.price.currency,
                        "priceText": source.price.text,
                        "ticketStatus": source.ticket_status,
                        "ticketUrl": str(source.ticket_url) if source.ticket_url else None,
                        "salesStartAt": source.sales_start_at.isoformat() if source.sales_start_at else None,
                        "isPriceUnknown": source.price.is_unknown,
                        "isFree": source.price.is_free,
                        "priceConfidence": price_resolution.get("confidence"),
                        "priceResolution": price_resolution,
                        "price_resolution": price_resolution,
                    }

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

        dto_stream = self._build_dtos(events)
        first_chunk = list(itertools.islice(dto_stream, _CHUNK_SIZE))

        if not first_chunk:
            logging.warning("No events to sync in bulk.")
            self.last_backend_sync_status = "skipped"
            return True

        # Debug log for price tracking (first 5)
        for d in first_chunk[:5]:
            logging.info(
                f"Syncing DTO: Title='{d['title']}' Provider='{d['provider']}' "
                f"MinPrice='{d['minPrice']}' Currency='{d['currency']}'"
            )

        all_success = True
        chunk_num = 0
        current_chunk = first_chunk

        while current_chunk:
            chunk_num += 1
            logging.info(f"Syncing chunk {chunk_num} ({len(current_chunk)} events)...")
            success = self._backend.sync_events_bulk(current_chunk, sync_run_id)
            if not success:
                logging.error(f"Chunk {chunk_num} failed.")
                all_success = False
            current_chunk = list(itertools.islice(dto_stream, _CHUNK_SIZE))
            if current_chunk:
                time.sleep(_INTER_CHUNK_SLEEP_SECONDS)

        self.last_backend_sync_status = "success" if all_success else "partial_failure"
        return all_success

    def trigger_stale_cleanup(self, sync_run_id: str):
        """V4: Triggers lifecycle cleanup in the backend."""
        return self._backend.deactivate_stale(sync_run_id)

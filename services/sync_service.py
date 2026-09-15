import logging
import time
from typing import Iterator, List, Optional

from clients.backend_client import BackendClient
from config import settings
from models.normalized_event import NormalizedEvent
from utils.change_detector import ChangeDetector
from utils.price_parser import PriceParser
from utils.provider_enrichment import build_provider_payload_from_event

_CHUNK_SIZE = 50
_INTER_CHUNK_SLEEP_SECONDS = 1.5
_CHUNK_MAX_ATTEMPTS = 3
_CHUNK_RETRY_BACKOFF_SECONDS = [5, 10]


class SyncService:
    def __init__(
        self,
        backend_client: Optional[BackendClient] = None,
        change_detector: Optional[ChangeDetector] = None,
    ):
        self._backend = backend_client or BackendClient(base_url=settings.backend_url)
        self._price_parser = PriceParser()
        self._change_detector = change_detector or ChangeDetector()
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
                        "localEndTime": occurrence.local_end_time,
                        "startAtUtc": occurrence.start_at_utc.isoformat() if occurrence.start_at_utc else None,
                        "sourceUrl": str(source.source_url),
                        "minPrice": resolved_min,
                        "maxPrice": resolved_max,
                        "currency": source.price.currency,
                        "priceText": source.price.text,
                        "ticketStatus": source.ticket_status,
                        "ticketUrl": str(source.ticket_url) if source.ticket_url else None,
                        "salesStartAt": source.sales_start_at.isoformat() if source.sales_start_at else None,
                        "brandName": source.brand_name or None,
                        "isOfficialSeller": source.is_official_seller,
                        "attractionId": event.attraction_id,
                        "attractionUpcomingCount": event.attraction_upcoming_count,
                        "performerName": event.performer_name,
                        "organizerName": event.organizer_name,
                        "venueLatitude": event.latitude,
                        "venueLongitude": event.longitude,
                        "venueAddress": event.address,
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

        all_dtos = list(self._build_dtos(events))

        if not all_dtos:
            logging.warning("No events to sync in bulk.")
            self.last_backend_sync_status = "skipped"
            return True

        changed_entries = self._change_detector.compute_changes(all_dtos)
        skipped_count = len(all_dtos) - len(changed_entries)
        logging.info(
            f"Change detection: {len(changed_entries)} changed, {skipped_count} unchanged "
            f"(skipped) out of {len(all_dtos)} events."
        )

        if not changed_entries:
            logging.info("No changed events to sync.")
            self.last_backend_sync_status = "skipped"
            return True

        # Debug log for price tracking (first 5)
        for dto, _key, _hash in changed_entries[:5]:
            logging.info(
                f"Syncing DTO: Title='{dto['title']}' Provider='{dto['provider']}' "
                f"MinPrice='{dto['minPrice']}' Currency='{dto['currency']}'"
            )

        all_success = True
        chunk_num = 0

        for chunk_start in range(0, len(changed_entries), _CHUNK_SIZE):
            chunk_num += 1
            chunk = changed_entries[chunk_start : chunk_start + _CHUNK_SIZE]
            chunk_dtos = [dto for dto, _key, _hash in chunk]
            logging.info(f"Syncing chunk {chunk_num} ({len(chunk_dtos)} events)...")
            success = False
            for attempt in range(1, _CHUNK_MAX_ATTEMPTS + 1):
                success = self._backend.sync_events_bulk(chunk_dtos, sync_run_id)
                if success:
                    break
                if attempt < _CHUNK_MAX_ATTEMPTS:
                    wait = _CHUNK_RETRY_BACKOFF_SECONDS[attempt - 1]
                    logging.warning(f"Chunk {chunk_num} attempt {attempt} failed, retrying in {wait}s...")
                    time.sleep(wait)
            if success:
                for _dto, key, new_hash in chunk:
                    self._change_detector.mark_synced(key, new_hash)
            else:
                logging.error(f"Chunk {chunk_num} failed after {_CHUNK_MAX_ATTEMPTS} attempts.")
                all_success = False
            if chunk_start + _CHUNK_SIZE < len(changed_entries):
                time.sleep(_INTER_CHUNK_SLEEP_SECONDS)

        self._change_detector.save()
        self.last_backend_sync_status = "success" if all_success else "partial_failure"
        return all_success

    def trigger_stale_cleanup(self, sync_run_id: str, provider: str | None = None):
        """V4: Triggers lifecycle cleanup in the backend.

        Pass provider when only one provider was synced in this run — this
        scopes the cleanup to that provider's sources only and avoids
        cross-killing other providers' sources.
        Pass None (default) only when ALL providers have run together.
        """
        return self._backend.deactivate_stale(sync_run_id, provider=provider)

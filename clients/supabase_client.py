from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Sequence, Set

import pytz
from supabase import Client, create_client

from config import settings
from models.normalized_event import NormalizedEvent
from models.normalized_place import NormalizedPlace
from utils.text_normalizer import TextNormalizer


class SupabaseClient:
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self._url = settings.supabase_url
        self._key = settings.supabase_key
        self.client: Client = create_client(self._url, self._key)

    # ---------------------------------------------------------------------
    # Legacy Discovery Methods
    # ---------------------------------------------------------------------
    def get_discovery_items(self, city_id: str):
        return (
            self.client.from_("discovery_items")
            .select("*, discovery_item_sources(*)")
            .eq("city_id", city_id)
            .eq("is_active", True)
            .execute()
        )

    def upsert_discovery_item(self, data: dict):
        return (
            self.client.from_("discovery_items")
            .upsert(data, on_conflict="canonical_key")
            .execute()
        )

    def upsert_source(self, data: dict):
        return (
            self.client.from_("discovery_item_sources")
            .upsert(data, on_conflict="provider,external_id")
            .execute()
        )

    def create_run(self, provider: str, started_at: str):
        data = {
            "provider": provider,
            "startedat": started_at,
            "status": "running",
            "itemsfound": 0,
            "itemsinserted": 0,
            "itemsupdated": 0,
            "itemsdeactivated": 0,
            "itemsfailed": 0,
        }
        return self.client.from_("crawlerruns").insert(data).execute()

    def finish_run(self, run_id: str, stats: dict, status: str = "success", error_msg: str = None):
        data = {
            "finishedat": datetime.now(pytz.UTC).isoformat(),
            "status": status,
            "itemsfound": stats.get("found", 0),
            "itemsinserted": stats.get("inserted", 0),
            "itemsupdated": stats.get("updated", 0),
            "itemsdeactivated": stats.get("deactivated", 0),
            "itemsfailed": stats.get("failed", 0),
            "errormessage": error_msg,
        }
        return self.client.from_("crawlerruns").update(data).eq("id", run_id).execute()

    # ---------------------------------------------------------------------
    # Nearby Places Methods
    # ---------------------------------------------------------------------
    def upsert_nearby_places(self, places: Sequence[NormalizedPlace], *, dry_run: bool = False) -> int:
        if not places:
            return 0

        payload = [self._to_nearby_place_row(place) for place in places]
        if dry_run:
            return len(payload)

        try:
            self.client.from_("nearby_places").upsert(
                payload,
                on_conflict="source,external_id,city",
            ).execute()
            return len(payload)
        except Exception as exc:
            self._logger.warning(
                "SupabaseClient: bulk nearby_places upsert failed; retrying row-by-row count=%s error=%s detail=%s",
                len(payload),
                type(exc).__name__,
                self._format_exception(exc),
            )

        saved = 0
        for row in payload:
            try:
                self.client.from_("nearby_places").upsert(
                    row,
                    on_conflict="source,external_id,city",
                ).execute()
                saved += 1
            except Exception as row_exc:
                self._logger.error(
                    "SupabaseClient: nearby_places row failed source=%s external_id=%s city=%s title=%s error=%s detail=%s",
                    row.get("source"),
                    row.get("external_id"),
                    row.get("city"),
                    row.get("title"),
                    type(row_exc).__name__,
                    self._format_exception(row_exc),
                )

        return saved

    def deactivate_missing_nearby_places(
        self,
        *,
        source: str,
        city: str,
        active_external_ids: Set[str],
        dry_run: bool = False,
    ) -> int:
        rows = (
            self.client.from_("nearby_places")
            .select("id,external_id")
            .eq("source", source)
            .eq("city", city)
            .eq("is_active", True)
            .execute()
        )
        data = rows.data or []
        to_deactivate = [
            item["id"]
            for item in data
            if item.get("external_id") and item.get("external_id") not in active_external_ids
        ]

        if dry_run:
            return len(to_deactivate)

        now_iso = datetime.now(timezone.utc).isoformat()
        for row_id in to_deactivate:
            (
                self.client.from_("nearby_places")
                .update({"is_active": False, "updated_at": now_iso})
                .eq("id", row_id)
                .execute()
            )
        return len(to_deactivate)

    # ---------------------------------------------------------------------
    # SerpAPI Events Methods (Canonical EF tables)
    # ---------------------------------------------------------------------
    def upsert_serpapi_events(self, events: Sequence[NormalizedEvent], *, dry_run: bool = False) -> int:
        if not events:
            return 0

        event_rows = []
        occurrence_rows = []
        source_rows = []

        for item in events:
            if not item.external_id:
                continue

            event_id = self._event_id(item.city_name, item.external_id)
            occurrence = item.occurrences[0] if item.occurrences else None
            occurrence_id = self._occurrence_id(event_id, occurrence.local_date if occurrence else "", occurrence.local_time if occurrence else "", occurrence.venue_name if occurrence else item.venue or "")
            source_id = self._source_id(occurrence_id, item.external_id)
            now_iso = datetime.now(timezone.utc).isoformat()

            event_rows.append(
                {
                    "Id": event_id,
                    "Title": item.title,
                    "NormalizedTitle": TextNormalizer.normalize_for_match(item.title),
                    "Description": item.description,
                    "Type": item.type,
                    "CityName": item.city_name,
                    "ImageUrl": str(item.thumbnail_url or item.image_url) if (item.thumbnail_url or item.image_url) else None,
                    "MinPriceTotal": None,
                    "ProviderCount": 1,
                    "CreatedAt": now_iso,
                    "LastSeenAt": now_iso,
                    "UpdatedAt": now_iso,
                    "IsActive": True,
                }
            )

            start_at_utc = occurrence.start_at_utc.isoformat() if occurrence else None
            local_date = occurrence.local_date if occurrence else datetime.now(timezone.utc).date().isoformat()
            local_time = occurrence.local_time if occurrence else "20:00"
            venue_name = occurrence.venue_name if occurrence else (item.venue or "Belirtilmedi")
            occurrence_rows.append(
                {
                    "Id": occurrence_id,
                    "EventId": event_id,
                    "StartAtUtc": start_at_utc,
                    "LocalStartDate": local_date,
                    "LocalStartTime": local_time,
                    "VenueName": venue_name,
                    "NormalizedVenue": TextNormalizer.normalize_for_match(venue_name),
                    "MinPrice": None,
                    "CreatedAt": now_iso,
                    "LastSeenAt": now_iso,
                    "UpdatedAt": now_iso,
                    "IsActive": True,
                }
            )

            source_rows.append(
                {
                    "Id": source_id,
                    "OccurrenceId": occurrence_id,
                    "ProviderName": "serpapi_google_events",
                    "ExternalId": item.external_id,
                    "SourceUrl": str(item.source_url or item.link) if (item.source_url or item.link) else "https://www.google.com",
                    "MinPrice": None,
                    "MaxPrice": None,
                    "PriceText": item.ticket_info,
                    "TicketStatus": "unknown",
                    "LastSyncAtUtc": now_iso,
                    "CreatedAt": now_iso,
                    "LastSeenAt": now_iso,
                    "UpdatedAt": now_iso,
                    "IsActive": True,
                }
            )

        if dry_run:
            return len(event_rows)

        if event_rows:
            self._upsert_rows_with_fallback(
                table="Events",
                rows=event_rows,
                on_conflict="Id",
                key_fields=("Id", "Title", "CityName"),
            )
        if occurrence_rows:
            self._upsert_rows_with_fallback(
                table="Occurrences",
                rows=occurrence_rows,
                on_conflict="Id",
                key_fields=("Id", "EventId", "LocalStartDate"),
            )
        if source_rows:
            self._upsert_rows_with_fallback(
                table="OccurrenceSources",
                rows=source_rows,
                on_conflict="OccurrenceId,ProviderName,ExternalId",
                key_fields=("Id", "OccurrenceId", "ProviderName", "ExternalId"),
            )

        return len(event_rows)

    def deactivate_missing_serpapi_events(
        self,
        *,
        city: str,
        active_external_ids: Set[str],
        dry_run: bool = False,
    ) -> int:
        events_res = self.client.from_("Events").select("Id").eq("CityName", city).execute()
        event_ids = [row["Id"] for row in (events_res.data or []) if row.get("Id")]
        if not event_ids:
            return 0

        occ_res = self.client.from_("Occurrences").select("Id,EventId").in_("EventId", event_ids).execute()
        occurrence_ids = [row["Id"] for row in (occ_res.data or []) if row.get("Id")]
        if not occurrence_ids:
            return 0

        source_res = (
            self.client.from_("OccurrenceSources")
            .select("Id,ExternalId")
            .eq("ProviderName", "serpapi_google_events")
            .in_("OccurrenceId", occurrence_ids)
            .eq("IsActive", True)
            .execute()
        )
        sources = source_res.data or []
        to_deactivate = [
            row["Id"]
            for row in sources
            if row.get("ExternalId") and row.get("ExternalId") not in active_external_ids
        ]

        if dry_run:
            return len(to_deactivate)

        now_iso = datetime.now(timezone.utc).isoformat()
        for source_id in to_deactivate:
            self.client.from_("OccurrenceSources").update(
                {"IsActive": False, "UpdatedAt": now_iso}
            ).eq("Id", source_id).execute()
        return len(to_deactivate)

    # ---------------------------------------------------------------------
    # Internal Helpers
    # ---------------------------------------------------------------------
    @staticmethod
    def _to_nearby_place_row(place: NormalizedPlace) -> dict:
        return {
            "source": place.source,
            "external_id": place.external_id,
            "title": place.title,
            "category": place.category,
            "address": place.address,
            "latitude": place.latitude,
            "longitude": place.longitude,
            "rating": place.rating,
            "reviews_count": place.reviews_count,
            "phone": place.phone,
            "hours": place.hours,
            "thumbnail_url": place.thumbnail_url,
            "source_url": place.source_url,
            "city": place.city,
            "fetched_at": place.fetched_at.isoformat(),
            "is_active": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _event_id(city: str, external_id: str) -> str:
        key = f"serpapi_google_events|{city.lower()}|{external_id.lower()}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, key))

    @staticmethod
    def _occurrence_id(event_id: str, local_date: str, local_time: str, venue_name: str) -> str:
        key = f"{event_id}|{local_date}|{local_time}|{venue_name.lower()}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, key))

    @staticmethod
    def _source_id(occurrence_id: str, external_id: str) -> str:
        key = f"{occurrence_id}|serpapi_google_events|{external_id.lower()}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, key))

    def _upsert_rows_with_fallback(
        self,
        *,
        table: str,
        rows: Sequence[dict],
        on_conflict: str,
        key_fields: Sequence[str],
    ) -> None:
        if not rows:
            return

        try:
            self.client.from_(table).upsert(rows, on_conflict=on_conflict).execute()
            return
        except Exception as exc:
            self._logger.warning(
                "SupabaseClient: bulk upsert failed table=%s count=%s error=%s detail=%s",
                table,
                len(rows),
                type(exc).__name__,
                self._format_exception(exc),
            )

        for row in rows:
            try:
                self.client.from_(table).upsert(row, on_conflict=on_conflict).execute()
            except Exception as row_exc:
                key_preview = {field: row.get(field) for field in key_fields}
                self._logger.error(
                    "SupabaseClient: row upsert failed table=%s keys=%s error=%s detail=%s",
                    table,
                    key_preview,
                    type(row_exc).__name__,
                    self._format_exception(row_exc),
                )

    @staticmethod
    def _format_exception(exc: Exception) -> str:
        parts = []
        for name in ("code", "message", "details", "hint"):
            value = getattr(exc, name, None)
            if value:
                parts.append(f"{name}={value}")
        if parts:
            return "; ".join(parts)
        return str(exc)

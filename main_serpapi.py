"""
SerpAPI Events + SerpAPI Local provider'larini calistirir.
Ticketmaster ve Municipal bu script'te DEVRE DISI.
Aylik 250 istek limiti oldugu icin dikkatli kullanir.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

from clients.serpapi_client import SerpApiClient
from config import settings
from providers.serpapi_events import SerpApiEventsProvider
from providers.serpapi_local import SerpApiLocalProvider
from services.events_sync_service import EventsSyncService
from services.nearby_sync_service import NearbySyncService


MAX_REQUESTS_PER_RUN = 30
OUTPUT_DIR = os.path.join("data", "serpapi")
EVENTS_PATH = os.path.join(OUTPUT_DIR, "events.json")
STATS_PATH = os.path.join(OUTPUT_DIR, "stats.json")


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _serialize_item(item: Any) -> Dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    if is_dataclass(item):
        return asdict(item)
    if hasattr(item, "dict"):
        return item.dict()
    if hasattr(item, "__dict__"):
        return dict(item.__dict__)
    return {"value": str(item)}


def _apply_request_cap(client: SerpApiClient, max_requests: int) -> None:
    original_search = client.search

    def capped_search(
        *,
        engine: str,
        query: str,
        location: str | None = None,
        hl: str = "tr",
        gl: str = "tr",
    ) -> Dict[str, Any]:
        if client.request_count >= max_requests:
            print(f"⚠️ 🔍 SerpAPI request limiti doldu ({max_requests}). Query atlandi: {query}")
            return {"error": f"max_requests_per_run_reached_{max_requests}"}
        return original_search(engine=engine, query=query, location=location, hl=hl, gl=gl)

    client.search = capped_search  # type: ignore[method-assign]


def main() -> None:
    print("🔍 SerpAPI sync basladi.")
    try:
        shared_client = SerpApiClient()
        _apply_request_cap(shared_client, MAX_REQUESTS_PER_RUN)

        local_provider = SerpApiLocalProvider(serpapi_client=shared_client)
        events_provider = SerpApiEventsProvider(serpapi_client=shared_client)

        captured_places: List[Any] = []
        captured_events: List[Any] = []

        original_fetch_places = local_provider.fetch_places
        original_fetch_events = events_provider.fetch_events

        def fetch_places_with_capture(city: str | None = None) -> List[Any]:
            places = original_fetch_places(city)
            captured_places.clear()
            captured_places.extend(places)
            return places

        def fetch_events_with_capture(city: str | None = None) -> List[Any]:
            events = original_fetch_events(city)
            captured_events.clear()
            captured_events.extend(events)
            return events

        local_provider.fetch_places = fetch_places_with_capture  # type: ignore[method-assign]
        events_provider.fetch_events = fetch_events_with_capture  # type: ignore[method-assign]

        dry_run = settings.sync_mode.lower() == "dry_run"
        resolved_city = settings.serpapi_city

        nearby_service = NearbySyncService(provider=local_provider)
        events_service = EventsSyncService(provider=events_provider)

        nearby_stats = nearby_service.run(dry_run=dry_run, city=resolved_city)
        events_stats = events_service.run(dry_run=dry_run, city=resolved_city)

        combined_records: List[Dict[str, Any]] = []
        for place in captured_places:
            payload = _serialize_item(place)
            payload["_record_type"] = "serpapi_local"
            combined_records.append(payload)

        for event in captured_events:
            payload = _serialize_item(event)
            payload["_record_type"] = "serpapi_events"
            combined_records.append(payload)

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(EVENTS_PATH, "w", encoding="utf-8") as events_file:
            json.dump(combined_records, events_file, ensure_ascii=False, indent=2, default=_json_default)

        requests_used = shared_client.request_count
        stats_payload = {
            "last_fetch": datetime.now(timezone.utc).isoformat(),
            "total_events": len(combined_records),
            "requests_used": requests_used,
        }
        with open(STATS_PATH, "w", encoding="utf-8") as stats_file:
            json.dump(stats_payload, stats_file, ensure_ascii=False, indent=2, default=_json_default)

        print(
            f"✅ 🔍 SerpAPI tamamlandi. kayit={len(combined_records)} "
            f"requests_used={requests_used}/{MAX_REQUESTS_PER_RUN}"
        )
        print(f"✅ Cikti dosyalari: {EVENTS_PATH}, {STATS_PATH}")
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 🔍 SerpAPI sync genel hata: {type(exc).__name__} - {exc}")


if __name__ == "__main__":
    main()

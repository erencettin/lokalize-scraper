"""
Ticketmaster + Municipal RSS + Municipal Web provider'larini calistirir.
SerpAPI bu script'te DEVRE DISI.
Mevcut provider ve service siniflarini import eder.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from config import settings
from providers.municipal_rss import MunicipalRssProvider
from providers.municipal_web import MunicipalWebProvider
from providers.ticketmaster import TicketmasterProvider
from services.sync_service import SyncService


OUTPUT_DIR = os.path.join("data", "ticketmaster_municipal")
EVENTS_PATH = os.path.join(OUTPUT_DIR, "events.json")
STATS_PATH = os.path.join(OUTPUT_DIR, "stats.json")


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _serialize_item(item: Any) -> Dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    if hasattr(item, "dict"):
        return item.dict()
    if hasattr(item, "__dict__"):
        return dict(item.__dict__)
    return {"value": str(item)}


def _run_provider(
    provider: Any,
    sync_service: SyncService,
    sync_run_id: str,
    total_stats: Dict[str, int],
    provider_counts: Dict[str, int],
    collected_events: List[Any],
) -> None:
    provider_name = getattr(provider, "name", provider.__class__.__name__)
    icon = {
        "Ticketmaster": "🎫",
        "MunicipalRSS": "📰",
        "MunicipalWeb": "🌐",
    }.get(provider_name, "⚠️")

    print(f"{icon} {provider_name} baslatiliyor...")
    provider_stats = {"found": 0, "synced": 0, "failed": 0}
    provider_counts[provider_name] = 0

    try:
        events = provider.fetch_and_parse()
        provider_stats["found"] = len(events)
        provider_counts[provider_name] = len(events)
        collected_events.extend(events)
        print(f"{icon} {provider_name} tamamlandi, event sayisi: {len(events)}")

        if events:
            success = sync_service.sync_events_to_backend_bulk(events, sync_run_id)
            if success:
                provider_stats["synced"] = len(events)
                print(f"✅ {provider_name} backend sync basarili: {len(events)}")
            else:
                provider_stats["failed"] = len(events)
                print(f"❌ {provider_name} backend sync basarisiz")
    except Exception as exc:  # noqa: BLE001
        provider_stats["failed"] = max(provider_stats["failed"], 1)
        print(f"❌ {provider_name} hatasi: {type(exc).__name__} - {exc}")

    for key in provider_stats:
        total_stats[key] = total_stats.get(key, 0) + provider_stats[key]


def main() -> None:
    print("🎫 Ticketmaster & Municipal sync basladi.")
    try:
        providers: List[Any] = []
        if settings.ticketmaster_enabled:
            providers.append(TicketmasterProvider())
            print("🎫 TicketmasterProvider aktif.")
        else:
            print("⚠️ TicketmasterProvider devre disi.")

        if settings.municipal_rss_enabled:
            providers.append(MunicipalRssProvider())
            print("📰 MunicipalRssProvider aktif.")
        else:
            print("⚠️ MunicipalRssProvider devre disi.")

        if settings.municipal_web_enabled:
            providers.append(MunicipalWebProvider())
            print("🌐 MunicipalWebProvider aktif.")
        else:
            print("⚠️ MunicipalWebProvider devre disi.")

        sync_service = SyncService()
        sync_run_id = f"tm-muni-{uuid.uuid4().hex[:8]}-{datetime.now().strftime('%H%M%S')}"
        total_stats = {"found": 0, "synced": 0, "failed": 0}
        provider_counts: Dict[str, int] = {}
        collected_events: List[Any] = []

        for provider in providers:
            _run_provider(
                provider=provider,
                sync_service=sync_service,
                sync_run_id=sync_run_id,
                total_stats=total_stats,
                provider_counts=provider_counts,
                collected_events=collected_events,
            )

        if providers:
            print("🔄 Stale cleanup tetikleniyor...")
            sync_service.trigger_stale_cleanup(sync_run_id)
            print("✅ Stale cleanup tamamlandi.")
        else:
            print("⚠️ Calisacak provider bulunamadi.")

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        serialized_events = [_serialize_item(event) for event in collected_events]
        with open(EVENTS_PATH, "w", encoding="utf-8") as events_file:
            json.dump(serialized_events, events_file, ensure_ascii=False, indent=2, default=_json_default)

        stats_payload = {
            "last_fetch": datetime.now(timezone.utc).isoformat(),
            "total_events": len(serialized_events),
            "provider_counts": provider_counts,
        }
        with open(STATS_PATH, "w", encoding="utf-8") as stats_file:
            json.dump(stats_payload, stats_file, ensure_ascii=False, indent=2, default=_json_default)

        print(f"✅ Ticketmaster & Municipal ciktilari yazildi: {EVENTS_PATH}, {STATS_PATH}")
    except Exception as exc:  # noqa: BLE001
        print(f"❌ Ticketmaster & Municipal sync genel hata: {type(exc).__name__} - {exc}")


if __name__ == "__main__":
    main()

"""
Supabase'deki SerpAPI tarafından doğrudan yazılmış duplicate Event kayıtlarını temizler.

Sorun: SerpAPI events_sync_service eski versiyonu doğrudan Supabase'e yazıyordu.
Bu veriler C# pipeline'ının yazdığı kayıtlarla çakışınca 2 kart oluşuyordu.

Bu script:
1. SerpAPI tarafından yazılan kayıtları tespit eder (OccurrenceSources.ProviderName = 'serpapi_google_events' OR 'Google')
2. Aynı normalized title + date + city'e sahip birden fazla Event varsa duplicate'leri bulur
3. Daha yeni olanı (SerpAPI-direct yazılan) deaktive eder, C# yazan eski kaydı korur

KULLANIM:
  python scripts/cleanup_serpapi_duplicates.py --dry-run   (önce bununla test et)
  python scripts/cleanup_serpapi_duplicates.py             (gerçek temizlik)
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timezone
from supabase import create_client, Client
from utils.text_normalizer import TextNormalizer


def main() -> None:
    parser = argparse.ArgumentParser(description="SerpAPI duplicate event cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Sadece göster, silme")
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        print("❌ SUPABASE_URL veya SUPABASE_SERVICE_ROLE_KEY eksik")
        sys.exit(1)

    supabase: Client = create_client(url, key)
    dry_run = args.dry_run
    print(f"{'[DRY-RUN] ' if dry_run else ''}SerpAPI duplicate cleanup başlatılıyor...")

    # 1. Tüm aktif Event'leri çek
    events_res = supabase.table("Events").select("Id,Title,NormalizedTitle,CityName,CreatedAt,IsActive").eq("IsActive", True).execute()
    all_events = events_res.data or []
    print(f"Aktif event sayısı: {len(all_events)}")

    # 2. NormalizedTitle + CityName bazında grupla
    from collections import defaultdict
    groups: dict[str, list[dict]] = defaultdict(list)
    for event in all_events:
        title_key = TextNormalizer.normalize_for_match(event.get("NormalizedTitle") or event.get("Title") or "")
        city_key = TextNormalizer.normalize_for_match(event.get("CityName") or "")
        key_combined = f"{title_key}|{city_key}"
        groups[key_combined].append(event)

    duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"Duplicate grup sayısı: {len(duplicate_groups)}")

    # 3. Her duplicate grupta SerpAPI-direct yazılanı bul
    events_to_deactivate = []
    for group_key, group_events in duplicate_groups.items():
        # Hangi eventlerin SerpAPI-direct OccurrenceSource'u var?
        event_ids = [e["Id"] for e in group_events]

        occ_res = supabase.table("Occurrences").select("Id,EventId").in_("EventId", event_ids).execute()
        occurrences = occ_res.data or []
        occ_ids = [o["Id"] for o in occurrences]
        occ_event_map = {o["Id"]: o["EventId"] for o in occurrences}

        if not occ_ids:
            continue

        source_res = supabase.table("OccurrenceSources").select("Id,OccurrenceId,ProviderName,ExternalId").in_("OccurrenceId", occ_ids).execute()
        sources = source_res.data or []

        # SerpAPI-direct provider names (eski pipeline)
        serpapi_direct_providers = {"serpapi_google_events", "google"}
        serpapi_event_ids = set()
        for s in sources:
            if s.get("ProviderName", "").lower() in serpapi_direct_providers:
                event_id = occ_event_map.get(s.get("OccurrenceId", ""))
                if event_id:
                    serpapi_event_ids.add(event_id)

        # C# pipeline tarafından yazılan eventleri bul (SerpAPI-direct değil)
        non_serpapi_event_ids = {e["Id"] for e in group_events} - serpapi_event_ids

        if serpapi_event_ids and non_serpapi_event_ids:
            # Hem C# hem SerpAPI yazmış: SerpAPI-direct olanı deaktive et
            for event_id in serpapi_event_ids:
                event_info = next((e for e in group_events if e["Id"] == event_id), None)
                print(f"  DUPLICATE: '{event_info.get('Title', '?')[:40]}' [{event_id}] — SerpAPI-direct, deaktive edilecek")
                events_to_deactivate.append(event_id)
        elif len(group_events) > 1 and not non_serpapi_event_ids:
            # Hepsi SerpAPI-direct: en eskisi hariç diğerlerini deaktive et
            sorted_group = sorted(group_events, key=lambda e: e.get("CreatedAt", ""))
            for event in sorted_group[1:]:
                print(f"  DUPLICATE (all-serpapi): '{event.get('Title', '?')[:40]}' [{event['Id']}] — deaktive edilecek")
                events_to_deactivate.append(event["Id"])

    print(f"\nDeaktive edilecek event sayısı: {len(events_to_deactivate)}")

    if not events_to_deactivate:
        print("✅ Duplicate bulunamadı, temizlik gerekmiyor.")
        return

    if dry_run:
        print("[DRY-RUN] Gerçek silme yapılmadı. --dry-run olmadan tekrar çalıştır.")
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    deactivated = 0
    for event_id in events_to_deactivate:
        try:
            supabase.table("Events").update({"IsActive": False, "UpdatedAt": now_iso}).eq("Id", event_id).execute()
            deactivated += 1
        except Exception as e:
            print(f"  ❌ Deaktivasyon hatası event_id={event_id}: {e}")

    print(f"✅ {deactivated}/{len(events_to_deactivate)} duplicate event deaktive edildi.")


if __name__ == "__main__":
    main()

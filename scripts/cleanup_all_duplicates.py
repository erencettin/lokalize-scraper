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
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase: Client = create_client(url, key)

    events_res = supabase.table("Events").select("Id,Title,NormalizedTitle,CityName,CreatedAt,IsActive").eq("IsActive", True).execute()
    all_events = events_res.data or []

    from collections import defaultdict
    groups: dict[str, list[dict]] = defaultdict(list)
    for event in all_events:
        title_key = TextNormalizer.normalize_for_match(event.get("NormalizedTitle") or event.get("Title") or "")
        city_key = TextNormalizer.normalize_for_match(event.get("CityName") or "")
        key_combined = f"{title_key}|{city_key}"
        groups[key_combined].append(event)

    duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"Found {len(duplicate_groups)} duplicated event groups.")

    events_to_deactivate = []
    for group_key, group_events in duplicate_groups.items():
        sorted_group = sorted(group_events, key=lambda e: e.get("CreatedAt", ""))
        # keep oldest active
        for event in sorted_group[1:]:
            events_to_deactivate.append(event["Id"])

    print(f"Deactivating {len(events_to_deactivate)} older duplicate events...")

    now_iso = datetime.now(timezone.utc).isoformat()
    for event_id in events_to_deactivate:
        supabase.table("Events").update({"IsActive": False, "UpdatedAt": now_iso}).eq("Id", event_id).execute()

    print("Cleanup done!")

if __name__ == "__main__":
    main()

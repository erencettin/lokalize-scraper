from clients.supabase_client import SupabaseClient
from datetime import datetime
import pytz
import logging

logging.basicConfig(level=logging.INFO)

def test_upsert():
    s = SupabaseClient()
    now_iso = datetime.now(pytz.UTC).isoformat()
    
    # Payload similar to SyncService
    item_data = {
        "canonical_key": "test-item-unique-123",
        "type": "theatre",
        "title": "Test Item",
        "normalized_title": "test item",
        "description": "Test description",
        "city_id": "11111111-1111-1111-1111-111111111111",
        "venue_name": "Test Venue",
        "normalized_venue_name": "test venue",
        "discover_at": now_iso,
        "start_at": now_iso,
        "status": "scheduled",
        "is_active": True,
        "first_seen_at": now_iso,
        "last_seen_at": now_iso
    }
    
    print(f"Sending item_data with discover_at={now_iso}")
    try:
        # Note: Using the current client.upsert directly to see behavior
        res = s.client.from_("discovery_items").upsert(item_data, on_conflict="canonical_key").execute()
        print(f"Result: {res.data}")
    except Exception as e:
        print(f"Upsert failed: {e}")

if __name__ == "__main__":
    test_upsert()

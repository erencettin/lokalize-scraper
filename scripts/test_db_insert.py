import logging
import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from clients.supabase_client import SupabaseClient

logging.basicConfig(level=logging.INFO)

def test_manual_insert():
    supabase = SupabaseClient()
    
    # 1. Get an existing item id to link to
    res_item = supabase.client.from_("discovery_items").select("id").limit(1).execute()
    if not res_item.data:
        print("No items in discovery_items to link to.")
        return
        
    item_id = res_item.data[0]["id"]
    print(f"Linking to item: {item_id}")
    
    # 2. Try manual insert into sources for Biletix
    source_data = {
        "item_id": item_id,
        "provider": "Biletix",
        "external_id": "test_biletix_id_999",
        "title": "Manual Biletix Test",
        "source_url": "https://www.biletix.com/test",
        "is_active": True
    }
    
    try:
        res = supabase.client.from_("discovery_item_sources").upsert(source_data, on_conflict="provider,external_id").execute()
        if res.data:
            print(f"MANUAL INSERT SUCCESS: {res.data}")
        else:
            print("MANUAL INSERT FAILED: No data returned")
    except Exception as e:
        print(f"MANUAL INSERT CRASHED: {e}")

if __name__ == "__main__":
    test_manual_insert()

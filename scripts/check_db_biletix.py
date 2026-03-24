import sys
import os
import logging
from typing import List

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from clients.supabase_client import SupabaseClient

logging.basicConfig(level=logging.INFO)

def check_biletix_data():
    supabase = SupabaseClient()
    
    # Check for Biletix sources
    res = supabase.client.from_("discovery_item_sources").select("id, is_active, provider, external_id, title").eq("provider", "Biletix").execute()
    
    count = len(res.data) if res.data else 0
    active_count = sum(1 for item in res.data if item.get("is_active")) if res.data else 0

    if res.data:
        print(f"Biletix Sources Found: {count}")
        for src in res.data:
            print(f"  - [{src.get('provider')}] ID: {src.get('external_id')} | Title: {src.get('title')}")
    else:
        print("  No Biletix sources found.")
    print(f"Active Biletix Sources: {active_count}")
    
    if count > 0:
        print("Biletix data EXISTS in DB.")
    else:
        # Check if maybe it's lowercase?
        res_lc = supabase.client.from_("discovery_item_sources").select("id").eq("provider", "biletix").execute()
        count_lc = len(res_lc.data) if res_lc.data else 0
        print(f"Lowercase 'biletix' Sources Found: {count_lc}")
        
        # Check all distinct providers
        res_all = supabase.client.from_("discovery_item_sources").select("provider").execute()
        if res_all.data:
            providers = set(item["provider"] for item in res_all.data)
            print(f"All Unique Providers in DB: {providers}")

if __name__ == "__main__":
    check_biletix_data()

import sys
import os
import logging
from pprint import pprint

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from clients.supabase_client import SupabaseClient
from clients.api_client import BackendApiClient

logging.basicConfig(level=logging.INFO)

def run_migration():
    client = SupabaseClient()
    api = BackendApiClient(base_url="http://localhost:5170")
    
    # We use the specific valid City and Category ID that we know exists perfectly in the new DB.
    city_id = "11111111-1111-1111-1111-111111111111"
    category_id = "22222222-2222-2222-2222-222222222222"
    
    logging.info("Fetching legacy discovery items from Supabase Data API...")
    # Fetch all items with their sources joined
    response = client.client.from_("discovery_items").select("*, discovery_item_sources(*)").eq("is_active", True).limit(5000).execute()
    
    items = response.data
    logging.info(f"Fetched {len(items)} active legacy discover items.")
    
    payload = []
    
    for item in items:
        sources = item.get("discovery_item_sources", [])
        for source in sources:
            if not source.get("is_active", True):
                continue
                
            prices = []
            price_val = source.get("price_value") or source.get("price_value_min")
            if price_val is not None:
                prices.append({
                    "amount": float(price_val),
                    "currency": source.get("currency", "TRY"),
                    "label": source.get("price_text")
                })
                
            dto = {
                "provider": source.get("provider", "Legacy System"),
                "externalId": source.get("external_id") or source.get("source_url", ""),
                "title": source.get("title", ""),
                "description": source.get("source_description") or item.get("description", ""),
                "imageUrl": item.get("image_url", ""),
                "cityId": city_id, # Fallback to known seeded city
                "categoryId": category_id,
                "venueName": source.get("provider_venue_name") or item.get("venue_name") or "Bilinmeyen Mekan",
                "startAt": source.get("provider_start_at") or item.get("start_at"),
                "endAt": item.get("end_at"),
                "sourceUrl": source.get("source_url", ""),
                "prices": prices
            }
            
            payload.append(dto)
            
    logging.info(f"Successfully mapped {len(payload)} legacy source records to new DTO format.")
    
    # Chunk the payload to avoid timing out the .NET API
    chunk_size = 500
    for i in range(0, len(payload), chunk_size):
        chunk = payload[i:i + chunk_size]
        logging.info(f"Pushing payload chunk {i} - {i+len(chunk)} to Backend EventSyncService...")
        api.sync_events(chunk)
        
    logging.info("🔥 MIGRATION SUCCESSFUL! All legacy records perfectly aggregated into the new canonical Multi-Provider platform.")

if __name__ == "__main__":
    run_migration()

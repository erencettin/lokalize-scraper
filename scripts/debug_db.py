from clients.supabase_client import SupabaseClient
import logging

logging.basicConfig(level=logging.INFO)
client = SupabaseClient()

# Check discovery_items
items = client.client.from_("discovery_items").select("*").limit(5).execute()
print("Discovery Items Sample:")
for item in items.data:
    print(f"- {item.get('title')} (ID: {item.get('id')})")

# Check discovery_item_sources
sources = client.client.from_("discovery_item_sources").select("*").eq("provider", "Etkinlik.io").limit(5).execute()
print("\nEtkinlik.io Sources Sample:")
for source in sources.data:
    print(f"- {source.get('source_url')} (Item ID: {source.get('item_id')})")

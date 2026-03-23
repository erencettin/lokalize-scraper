from clients.supabase_client import SupabaseClient

def cleanup():
    client = SupabaseClient().client
    
    # 1. Fetch all sources
    sources_res = client.from_("discovery_item_sources").select("id, item_id, provider").execute()
    
    valid_providers = {"Mobilet", "Etkinlik.io", "KulturIstanbul"}
    
    invalid_item_ids = set()
    valid_item_ids = set()
    invalid_source_ids = []
    
    for s in sources_res.data:
        if s["provider"] not in valid_providers:
            invalid_item_ids.add(s["item_id"])
            invalid_source_ids.append(s["id"])
        else:
            valid_item_ids.add(s["item_id"])
            
    # Items that ONLY have invalid providers (so if an item has Mobilet AND Passo, we keep the item, just delete the Passo source)
    items_to_delete = list(invalid_item_ids - valid_item_ids)
    
    print(f"Found {len(invalid_source_ids)} legacy sources and {len(items_to_delete)} legacy items to delete.")
    
    # Delete sources first to avoid foreign key constraint errors if ON DELETE CASCADE is missing
    if invalid_source_ids:
        for i in range(0, len(invalid_source_ids), 50):
            batch = invalid_source_ids[i:i+50]
            client.from_("discovery_item_sources").delete().in_("id", batch).execute()
        print("Deleted legacy sources.")
            
    # Delete items
    if items_to_delete:
        for i in range(0, len(items_to_delete), 50):
            batch = items_to_delete[i:i+50]
            client.from_("discovery_items").delete().in_("id", batch).execute()
        print("Deleted legacy items.")
        
    print("Cleanup complete!")

if __name__ == "__main__":
    cleanup()

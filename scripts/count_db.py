from clients.supabase_client import SupabaseClient

def check_counts():
    client = SupabaseClient().client
    
    # Get total count for items
    res_items = client.from_("discovery_items").select("*", count="exact").execute()
    print(f"Total discovery_items: {res_items.count}")
    
    # Get total count for sources
    res_sources = client.from_("discovery_item_sources").select("*", count="exact").execute()
    print(f"Total discovery_item_sources: {res_sources.count}")

if __name__ == "__main__":
    check_counts()

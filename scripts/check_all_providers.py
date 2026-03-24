from clients.supabase_client import SupabaseClient

def check_all():
    s = SupabaseClient()
    from datetime import datetime, timedelta, timezone
    
    threshold = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    res = s.client.from_("discovery_item_sources").select("provider, created_at, title").eq("provider", "Biletix").gte("created_at", threshold).execute()
    
    print(f"Biletix Sources Created in last 15 mins: {len(res.data) if res.data else 0}")
    if res.data:
        for item in res.data:
            print(f"  - {item['title']} (Created: {item['created_at']})")

if __name__ == "__main__":
    check_all()

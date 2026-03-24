import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.settings import settings
from supabase import create_client

url = settings.SUPABASE_URL
key = settings.SUPABASE_SERVICE_KEY
client = create_client(url, key)

res = client.table("discovery_item_sources").select("id, provider, external_id", count="exact").eq("provider", "Biletix").execute()
print(f"Total Biletix Sources in DB: {res.count}")
if res.data:
    for i, r in enumerate(res.data[:20]):
        print(f"  {i+1}. {r['external_id']}")

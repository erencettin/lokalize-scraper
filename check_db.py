import os
import sys

# Append the repo to the sys path so we can import supabase from pip if installed
sys.path.append("c:/Lokalize/LokalizeApp/temp_scraper_repo")

try:
    from dotenv import load_dotenv
    from supabase import create_client, Client

    load_dotenv("c:/Lokalize/LokalizeApp/temp_scraper_repo/.env")
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    supabase: Client = create_client(url, key)

    res = supabase.table("occurrence_sources").select("provider_name, price_text, min_price").execute()
    print(f"Total occurrence sources: {len(res.data)}")
    prices = []
    for row in res.data:
        pt = row.get("price_text", "")
        if pt and pt not in ("Fiyat bilgisi yok", "Unknown", "Fiyat sağlayıcıda"):
            prices.append(row)
    print(f"Total with real prices: {len(prices)}")
    for p in prices[:15]:
        print(p)
except Exception as e:
    print(f"Error connecting to Supabase: {e}")

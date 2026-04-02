import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client, Client
import json

def main():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase: Client = create_client(url, key)

    title_like = "%Mélanie Pain%"
    
    res = supabase.table("Events").select("Id,Title,CityName,IsActive,CreatedAt").ilike("Title", title_like).execute()
    
    events = res.data or []
    output = []
    for e in events:
        occ_res = supabase.table("Occurrences").select("Id,LocalStartDate,LocalStartTime,VenueName").eq("EventId", e["Id"]).execute()
        e["Occurrences"] = occ_res.data or []
        for o in e["Occurrences"]:
            src_res = supabase.table("OccurrenceSources").select("Id,ProviderName,ExternalId").eq("OccurrenceId", o["Id"]).execute()
            o["Sources"] = src_res.data or []
        output.append(e)

    with open("c:/Lokalize/LokalizeApp/temp_scraper_repo/melanie.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()

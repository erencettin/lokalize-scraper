import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client, Client

def main():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase: Client = create_client(url, key)

    title_like = "%Mélanie Pain%"
    res = supabase.table("Events").select("Id,Title,NormalizedTitle,CreatedAt").ilike("Title", title_like).execute()
    
    events = res.data or []
    for e in events:
        print(f"[{e['CreatedAt']}] ID={e['Id']} Title='{e['Title']}' Normalized='{e['NormalizedTitle']}'")

if __name__ == "__main__":
    main()

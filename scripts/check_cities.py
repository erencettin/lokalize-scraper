from clients.supabase_client import SupabaseClient

def check_cities():
    s = SupabaseClient()
    res = s.client.from_("cities").select("*").execute()
    print("Cities in DB:")
    for city in res.data:
        print(f"  {city['id']}: {city['name']} (Slug: {city['slug']})")

if __name__ == "__main__":
    check_cities()

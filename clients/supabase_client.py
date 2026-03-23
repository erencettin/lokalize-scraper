from supabase import create_client, Client
from config import settings
from models.normalized_event import NormalizedEvent, NormalizedOccurrence, NormalizedSource

class SupabaseClient:
    def __init__(self):
        self._url = settings.supabase_url
        self._key = settings.supabase_key
        self.client: Client = create_client(self._url, self._key)

    def get_discovery_items(self, city_id: str):
        """
        Gets all active discovery items for a city to perform in-memory matching.
        """
        return self.client.from_("discovery_items") \
            .select("*, discovery_item_sources(*)") \
            .eq("city_id", city_id) \
            .eq("is_active", True) \
            .execute()

    def upsert_discovery_item(self, data: dict):
        return self.client.from_("discovery_items").upsert(data).execute()

    def upsert_source(self, data: dict):
        return self.client.from_("discovery_item_sources").upsert(data).execute()

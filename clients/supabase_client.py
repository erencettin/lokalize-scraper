from supabase import create_client, Client
from config import settings
from datetime import datetime
import pytz
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
        # Using canonical_key as conflict target. 
        # Requirement: canonical_key must have a standard UNIQUE constraint (not just partial index)
        return self.client.from_("discovery_items").upsert(data, on_conflict="canonical_key").execute()

    def upsert_source(self, data: dict):
        # Using (provider, external_id) as conflict target.
        # Requirement: ux_discovery_item_sources_provider_external_id must be a standard UNIQUE constraint.
        return self.client.from_("discovery_item_sources").upsert(data, on_conflict="provider,external_id").execute()

    # --- Run Logging ---
    def create_run(self, provider: str, started_at: str):
        data = {
            "provider": provider,
            "startedat": started_at,
            "status": "running",
            "itemsfound": 0,
            "itemsinserted": 0,
            "itemsupdated": 0,
            "itemsdeactivated": 0,
            "itemsfailed": 0
        }
        return self.client.from_("crawlerruns").insert(data).execute()

    def finish_run(self, run_id: str, stats: dict, status: str = "success", error_msg: str = None):
        data = {
            "finishedat": datetime.now(pytz.UTC).isoformat(),
            "status": status,
            "itemsfound": stats.get("found", 0),
            "itemsinserted": stats.get("inserted", 0),
            "itemsupdated": stats.get("updated", 0),
            "itemsdeactivated": stats.get("deactivated", 0),
            "itemsfailed": stats.get("failed", 0),
            "errormessage": error_msg
        }
        return self.client.from_("crawlerruns").update(data).eq("id", run_id).execute()

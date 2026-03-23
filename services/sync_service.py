from typing import List, Optional
from models.normalized_event import NormalizedEvent, NormalizedOccurrence
from clients.supabase_client import SupabaseClient
from utils.text_normalizer import TextNormalizer
from utils.date_parser import DateParser
from services.matching_service import MatchingService
from datetime import datetime
import pytz
import logging

class SyncService:
    def __init__(self):
        self._supabase = SupabaseClient()
        self._text_normalizer = TextNormalizer()
        self._date_parser = DateParser()

    def sync_event(self, event: NormalizedEvent):
        """
        Coordinates the high-level sync process for an event and all its occurrences.
        """
        # 1. Fetch existing items for this city/area to perform in-memory matching
        # (This avoids hitting DB for every occurrence in the loop)
        # Note: In a large system, we'd use a more refined fetch
        existing_items = self._fetch_relevant_items(event.city_name)
        matcher = MatchingService(existing_items)

        for occurrence in event.occurrences:
            try:
                self._sync_occurrence(event, occurrence, matcher)
            except Exception as e:
                logging.error(f"Failed to sync occurrence for {event.title} at {occurrence.start_at_utc}: {e}")

    def _sync_occurrence(self, event: NormalizedEvent, occurrence: NormalizedOccurrence, matcher: MatchingService):
        # 1. Find or Prepare logical attributes
        logical_key = self._text_normalizer.generate_logical_key(event.title, event.city_name)
        fingerprint = self._text_normalizer.generate_fingerprint(
            event.title, occurrence.venue_name, occurrence.local_date, occurrence.local_time
        )
        
        # 2. Match
        match, confidence = matcher.find_match(occurrence, event.title, event.city_name)
        
        # 3. Upsert Discovery Item (Occurrence)
        now_iso = datetime.now(pytz.UTC).isoformat()
        item_data = {
                "canonical_key": logical_key,
    "title": event.title,
    "normalized_title": self._text_normalizer.normalize_for_match(event.title),
    "description": event.description,
    "type": event.type,
    "city_id": self._resolve_city_id(event.city_name),
    "venue_name": occurrence.venue_name,
    "normalized_venue_name": self._text_normalizer.normalize_for_match(occurrence.venue_name),
    "district": occurrence.district,
    "discover_at": now_iso,
    "start_at": occurrence.start_at_utc.isoformat(),
    "end_at": None,
    "sales_start_at": None,
    "image_url": str(event.image_url) if event.image_url else None,
    "status": "scheduled",
    "is_active": True,
    "first_seen_at": now_iso,
    "last_seen_at": now_iso
        }

        if match:
            item_data["id"] = match["id"]
        
        try:
            result = self._supabase.upsert_discovery_item(item_data)
            if not result.data:
                logging.error(f"Failed to upsert discovery item for {event.title}: No data returned")
                return
            item_id = result.data[0]["id"]
            logging.info(f"Successfully upserted/matched item: {event.title} (ID: {item_id})")
        except Exception as e:
            if "23505" in str(e):
                # Duplicate canonical_key. This happens if another provider inserted it during this run 
                # (so it wasn't in our initial matcher cache). Let's fetch the ID manually.
                logging.debug(f"Duplicate constraint caught for {event.title}. Querying existing ID.")
                res = self._supabase.client.from_("discovery_items").select("id").eq("canonical_key", logical_key).execute()
                if res.data:
                    item_id = res.data[0]["id"]
                    logging.info(f"Matched existing item mid-run: {event.title} (ID: {item_id})")
                else:
                    logging.error(f"Could not resolve ID after constraint violation for {event.title}")
                    return
            else:
                raise e

        # 4. Upsert Sources (Multi-provider support)
        for source in occurrence.sources:
            source_data = {
                   "item_id": item_id,
    "provider": source.provider,
    "external_id": source.external_id,
    "title": event.title,
    "source_url": str(source.source_url),
    "deep_link_url": str(source.source_url),
    "provider_venue_name": occurrence.venue_name,
    "provider_start_at": occurrence.start_at_utc.isoformat(),
    "sales_start_at": None,
    "availability_status": "available",
    "currency": source.price.currency if source.price else None,
    "price_value": source.price.value if source.price else None,
    "price_text": source.price.text if source.price else None,
    "last_seen_at": datetime.now(pytz.UTC).isoformat(),
    "is_active": True
        }
            try:
                source_res = self._supabase.upsert_source(source_data)
                if source_res.data:
                    logging.info(f"  - Synced source for {source.provider}: {source.source_url}")
                else:
                    logging.error(f"  - Failed to sync source for {source.provider}: {source.source_url}")
            except Exception as e:
                if "23505" in str(e):
                    logging.debug(f"  - Source already linked for {source.provider}: {source.title}")
                else:
                    logging.error(f"  - Failed to sync source for {source.provider}: {e}")

    def _fetch_relevant_items(self, city_name: str) -> List[dict]:
        city_id = self._resolve_city_id(city_name)
        response = self._supabase.get_discovery_items(city_id)
        return response.data

    def _resolve_city_id(self, city_name: str) -> str:
        # Hardcoded for demo/Istanbul for now, in a real system we'd look this up
        return "11111111-1111-1111-1111-111111111111" # Istanbul Dummy GUID from backend

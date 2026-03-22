from typing import List, Optional
from models.normalized_event import NormalizedEvent, NormalizedOccurrence, NormalizedSource
from clients.supabase_client import SupabaseClient
from utils.text_normalizer import TextNormalizer
from utils.date_parser import DateParser
from services.matching_service import MatchingService
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
        item_data = {
            "title": event.title,
            "normalized_title": self._text_normalizer.normalize_for_match(event.title),
            "description": event.description,
            "type": event.type,
            "city_id": self._resolve_city_id(event.city_name),
            "venue_name": occurrence.venue_name,
            "normalized_venue_name": self._text_normalizer.normalize_for_match(occurrence.venue_name),
            "district": occurrence.district,
            "start_at": occurrence.start_at_utc.isoformat(),
            "local_event_date": occurrence.local_date,
            "local_event_time": occurrence.local_time,
            "timezone": occurrence.timezone,
            "logical_event_key": logical_key,
            "logical_event_confidence": confidence,
            "fingerprint": fingerprint,
            "image_url": str(event.image_url) if event.image_url else None,
            "is_active": True,
            "last_seen_at": "now()"
        }

        if match:
            item_data["id"] = match["id"]
        
        result = self._supabase.upsert_discovery_item(item_data)
        item_id = result.data[0]["id"]

        # 4. Upsert Sources (Multi-provider support)
        for source in occurrence.sources:
            source_data = {
                "item_id": item_id,
                "provider": source.provider,
                "external_id": source.external_id,
                "source_url": str(source.source_url),
                "normalized_source_url": str(source.source_url).lower().split('?')[0], # Basic normalization
                "price_value": source.price.value,
                "price_text": source.price.text,
                "currency": source.price.currency,
                "is_active": True,
                "last_seen_at": "now()",
                "crawled_at": "now()"
            }
            self._supabase.upsert_source(source_data)

    def _fetch_relevant_items(self, city_name: str) -> List[dict]:
        city_id = self._resolve_city_id(city_name)
        response = self._supabase.get_discovery_items(city_id)
        return response.data

    def _resolve_city_id(self, city_name: str) -> str:
        # Hardcoded for demo/Istanbul for now, in a real system we'd look this up
        return "11111111-1111-1111-1111-111111111111" # Istanbul Dummy GUID from backend

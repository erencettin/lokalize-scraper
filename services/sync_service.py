from typing import List, Optional
from models.normalized_event import NormalizedEvent, NormalizedOccurrence
from clients.supabase_client import SupabaseClient
from utils.text_normalizer import TextNormalizer
from utils.date_parser import DateParser
from utils.price_parser import PriceParser
from services.matching_service import MatchingService
from datetime import datetime
import pytz
import logging

class SyncService:
    def __init__(self):
        self._supabase = SupabaseClient()
        self._text_normalizer = TextNormalizer()
        self._date_parser = DateParser()
        self._price_parser = PriceParser()
        self._items_cache = {} # Cache for existing items by city

    def sync_event(self, event: NormalizedEvent, existing_items_override: List[dict] = None) -> dict:
        """
        Coordinates the high-level sync process for an event and all its occurrences.
        Returns a dict of stats: { "inserted": X, "updated": Y, "failed": Z }
        """
        stats = {"inserted": 0, "updated": 0, "failed": 0}
        
        # 1. Fetch or use cached existing items
        if existing_items_override is not None:
            existing_items = existing_items_override
        else:
            city_id = self._resolve_city_id(event.city_name)
            if city_id not in self._items_cache:
                logging.info(f"Fetching existing items from Supabase for city ID: {city_id}...")
                self._items_cache[city_id] = self._fetch_relevant_items(event.city_name)
            existing_items = self._items_cache[city_id]
            
        if existing_items is None:
            existing_items = []
            
        matcher = MatchingService(existing_items)

        for occurrence in event.occurrences:
            try:
                res = self._sync_occurrence(event, occurrence, matcher)
                if res == "inserted": stats["inserted"] += 1
                elif res == "updated": stats["updated"] += 1
            except Exception as e:
                logging.error(f"Failed to sync occurrence for {event.title} at {occurrence.start_at_utc}: {e}")
                stats["failed"] += 1
        
        return stats

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
        
        # Optimization: Truncate description (max 300 chars, null-safe)
        desc = event.description or ""
        short_desc = (desc[:297] + "...") if len(desc) > 300 else desc

        item_data = {
                "canonical_key": logical_key,
    "title": event.title,
    "normalized_title": self._text_normalizer.normalize_for_match(event.title),
    "description": short_desc,
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
            item_id = match["id"]
            # SMART MERGE: Only update description/image if current values are empty or low quality
            existing_desc = match.get("description", "")
            
            # Quality Heuristic: Longer desc is usually better, but avoid overwriting if existing is "established"
            # Also check for Turkish keywords to ensure quality
            is_better = False
            if not existing_desc:
                is_better = True
            elif len(short_desc) > len(existing_desc) + 20: 
                # significantly longer is usually better
                is_better = True
            
            if is_better:
                 item_data["description"] = short_desc
            else:
                 item_data.pop("description", None)
            
            if not match.get("image_url") and event.image_url:
                item_data["image_url"] = str(event.image_url)
            else:
                item_data.pop("image_url", None)

            # Preserve original discovery time
            item_data["discover_at"] = match.get("discover_at") or now_iso
            
            # Always refresh last_seen_at
            item_data["last_seen_at"] = now_iso
            item_data.pop("first_seen_at", None)
        
        try:
            logging.debug(f"Upserting discovery item: {logical_key}")
            result = self._supabase.upsert_discovery_item(item_data)
            if not result.data:
                logging.error(f"Failed to upsert discovery item for {event.title}: No data returned")
                return "failed"
            item_id = result.data[0]["id"]
            status = "updated" if match else "inserted"
            logging.info(f"Successfully {status} item: {event.title} (ID: {item_id})")
        except Exception as e:
            if "23505" in str(e):
                logging.debug(f"Duplicate constraint caught for {event.title}. Querying existing ID.")
                res = self._supabase.client.from_("discovery_items").select("id").eq("canonical_key", logical_key).execute()
                if res.data:
                    item_id = res.data[0]["id"]
                    status = "updated"
                    logging.info(f"Matched existing item mid-run: {event.title} (ID: {item_id})")
                else:
                    logging.error(f"Could not resolve ID after constraint violation for {event.title}")
                    return "failed"
            else:
                raise e

        # 4. Upsert Sources (Multi-provider support)
        for source in occurrence.sources:
            # Parse prices if not already parsed
            min_p, max_p = self._price_parser.parse_prices(source.price.text)
            
            source_data = {
                "item_id": item_id,
                "provider": source.provider,
                "external_id": source.external_id,
                "title": source.title or event.title,
                "source_title": source.title,
                "source_description": source.description,
                "source_url": str(source.source_url),
                "deep_link_url": str(source.source_url),
                "provider_venue_name": occurrence.venue_name,
                "provider_start_at": occurrence.start_at_utc.isoformat(),
                "sales_start_at": source.sales_start_at.isoformat() if source.sales_start_at else None,
                "ticket_status": source.ticket_status,
                "currency": source.price.currency or "TRY",
                "price_text": source.price.text,
                "price_value_min": source.price.min_value if source.price.min_value is not None else min_p,
                "price_value_max": source.price.max_value if source.price.max_value is not None else max_p,
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
                logging.error(f"  - Failed to sync source for {source.provider}: {e}")

    def deactivate_expired_events(self, city_name: str):
        """
        Marks events in the past as is_active = False.
        Scoped by city for targeted cleanup.
        """
        try:
            city_id = self._resolve_city_id(city_name)
            now_utc = datetime.now(pytz.UTC).isoformat()
            
            # Query active items in the past for this city
            res = self._supabase.client.from_("discovery_items") \
                .update({"is_active": False}) \
                .eq("city_id", city_id) \
                .eq("is_active", True) \
                .lt("start_at", now_utc) \
                .execute()
            
            count = len(res.data) if res.data else 0
            if count > 0:
                logging.info(f"Archived {count} expired events for {city_name} (set is_active=False)")
            
        except Exception as e:
            logging.error(f"Failed to deactivate expired events for {city_name}: {e}")

    def deactivate_stale_sources(self, city_name: str, provider: str, run_start_time: datetime) -> int:
        """
        Marks sources as is_active = False if they weren't seen in the current run.
        Returns the number of deactivated sources.
        """
        try:
            city_id = self._resolve_city_id(city_name)
            run_start_iso = run_start_time.isoformat()
            
            res = self._supabase.client.from_("discovery_item_sources") \
                .update({"is_active": False}) \
                .eq("provider", provider) \
                .eq("is_active", True) \
                .lt("last_seen_at", run_start_iso) \
                .execute()
            
            count = len(res.data) if res.data else 0
            if count > 0:
                logging.info(f"Deactivated {count} stale sources for {provider} in {city_name}")
            return count
                
        except Exception as e:
            logging.error(f"Failed to deactivate stale sources for {provider}: {e}")
            return 0

    def cleanup_orphaned_items(self, city_name: str) -> int:
        """
        Lifecycle Rule: Deactivates discovery_items ONLY IF they have ZERO active sources.
        """
        try:
            city_id = self._resolve_city_id(city_name)
            
            # Fetch all active items and their sources
            items_res = self._supabase.client.from_("discovery_items") \
                .select("id, discovery_item_sources(id, is_active)") \
                .eq("city_id", city_id) \
                .eq("is_active", True) \
                .execute()
            
            to_deactivate = []
            if items_res.data:
                for item in items_res.data:
                    sources = item.get("discovery_item_sources", [])
                    # An item is orphaned if ALL its sources are inactive (is_active=False)
                    # or if it has NO sources at all.
                    has_active_source = any(s.get("is_active") == True for s in sources)
                    
                    if not has_active_source:
                        to_deactivate.append(item["id"])
            
            if to_deactivate:
                self._supabase.client.from_("discovery_items") \
                    .update({"is_active": False}) \
                    .in_("id", to_deactivate) \
                    .execute()
                logging.info(f"Cleaned up {len(to_deactivate)} orphaned discovery items in {city_name}")
                return len(to_deactivate)
            return 0
        except Exception as e:
            logging.error(f"Failed to cleanup orphaned items: {e}")
            return 0

    def _fetch_relevant_items(self, city_name: str) -> List[dict]:
        city_id = self._resolve_city_id(city_name)
        response = self._supabase.get_discovery_items(city_id)
        return response.data

    def _resolve_city_id(self, city_name: str) -> str:
        # Hardcoded for demo/Istanbul for now, in a real system we'd look this up
        return "11111111-1111-1111-1111-111111111111" # Istanbul Dummy GUID from backend

from typing import Optional, List, Tuple
from utils.text_normalizer import TextNormalizer
from models.normalized_event import NormalizedEvent, NormalizedOccurrence

class MatchingService:
    def __init__(self, existing_items: List[dict]):
        self.existing_items = existing_items
        self._text_normalizer = TextNormalizer()

    def find_match(self, occurrence: NormalizedOccurrence, event_title: str, city_name: str) -> Tuple[Optional[dict], str]:
        """
        Implements 4-step matching logic:
        1. Exact match by fingerprint (Title + Venue + Date + Time)
        2. Probable match by similar title and venue window
        3. Fallback to new logical event
        """
        # 1. Exact Match via fingerprint
        current_fingerprint = self._text_normalizer.generate_fingerprint(
            event_title, occurrence.venue_name, occurrence.local_date, occurrence.local_time
        )
        
        for item in self.existing_items:
            if item.get("fingerprint") == current_fingerprint:
                return item, "strong"

        # 2. Probable Match (Same logical event, different date)
        # This part usually helps in grouping occurrences under same logical_event_key
        current_logical_key = self._text_normalizer.generate_logical_key(event_title, city_name)
        
        for item in self.existing_items:
            if item.get("logical_event_key") == current_logical_key:
                # If same logical key but different fingerprint, it's a new occurrence of same event
                # We return the "parent" match info to help SyncService group them
                return item, "probable"

        return None, "weak"

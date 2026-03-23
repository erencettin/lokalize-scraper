from datetime import datetime
from typing import List, Optional
from models.normalized_event import NormalizedEvent, NormalizedOccurrence, NormalizedSource, PriceInfo
from utils.text_normalizer import TextNormalizer
from utils.date_parser import DateParser

class NormalizationService:
    def __init__(self):
        # We use static methods from TextNormalizer and DateParser
        pass

    def normalize_event(self, raw_data: dict) -> NormalizedEvent:
        """
        Takes raw provider-specific data and converts it to a standard NormalizedEvent.
        Expected keys in raw_data depend on the provider, but aim for consistency.
        """
        # This is typically called within the provider after parsing.
        # Here we define the logic for post-parsing normalization.
        pass

    def enrich_occurrence(self, occurrence: NormalizedOccurrence, title: str, city: str):
        """
        Adds logical keys and fingerprints to an occurrence.
        """
        occurrence.local_date, occurrence.local_time, _ = DateParser.to_local_parts(
            occurrence.start_at_utc, occurrence.timezone
        )
        
        # We don't store fingerprint/logical_key on the model itself as they are 
        # computed/derived for the DB sync stage, but we can store them if needed.
        pass

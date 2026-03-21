import requests
from typing import List
from providers.base_provider import BaseProvider
from models.normalized_event import NormalizedEvent, NormalizedOccurrence, NormalizedSource, PriceInfo
from datetime import datetime

class KulturIstanbulProvider(BaseProvider):
    def __init__(self):
        super().__init__("KulturIstanbul", mode="http")
        self.api_url = "https://kultur.istanbul/wp-json/wp/v2/etkinlik?per_page=10" # Example API

    def fetch_and_parse(self) -> List[NormalizedEvent]:
        # Implementation would use requests to fetch the JSON from kultur.istanbul WP API
        # and map it to NormalizedEvent objects.
        # For this demo, we return a mock object that matches the structure.
        
        events = []
        
        # Example Mock Data after parsing
        mock_event = NormalizedEvent(
            title="Duman Konseri",
            type="concert",
            city_name="Istanbul",
            description="Duman Harbiye'de sahne alıyor.",
            occurrences=[
                NormalizedOccurrence(
                    start_at_utc=datetime(2026, 5, 20, 18, 0, 0),
                    venue_name="Harbiye Cemil Topuzlu Açıkhava Tiyatrosu",
                    district="Şişli",
                    sources=[
                        NormalizedSource(
                            provider=self.name,
                            external_id="duman-001",
                            title="Duman Konseri - Harbiye",
                            source_url="https://kultur.istanbul/etkinlik/duman-konseri/",
                            price=PriceInfo(value=500, text="500 TL", currency="TRY")
                        )
                    ]
                )
            ]
        )
        
        events.append(mock_event)
        return events

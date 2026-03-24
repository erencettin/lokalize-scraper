import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.sync_service import SyncService
from models.normalized_event import NormalizedEvent, NormalizedOccurrence, NormalizedSource, PriceInfo
from datetime import datetime, timedelta
import pytz
import logging

logging.basicConfig(level=logging.INFO)

def test_optimization():
    print("--- Testing SyncService Optimization ---")
    sync = SyncService()
    
    # 1. Test Truncation
    long_desc = "Bu çok uzun bir açıklamadır. " * 50 # Definitely > 300 chars
    event = NormalizedEvent(
        title="Truncation Test Event",
        description=long_desc,
        type="concert",
        city_name="İstanbul",
        image_url="https://example.com/img.jpg",
        occurrences=[
            NormalizedOccurrence(
                start_at_utc=datetime.now(pytz.UTC) + timedelta(days=1),
                local_date="2026-03-24",
                local_time="20:00",
                timezone="Europe/Istanbul",
                venue_name="Test Venue",
                sources=[NormalizedSource(provider="Test", external_id="t1", title="Test", source_url="https://t.com")]
            )
        ]
    )
    
    print("Syncing event with long description...")
    sync.sync_event(event)

    # 2. Test Deactivation
    print("\n--- Testing Deactivation Logic ---")
    sync.deactivate_expired_events("İstanbul")
    print("Cleanup called for İstanbul.")

if __name__ == "__main__":
    test_optimization()

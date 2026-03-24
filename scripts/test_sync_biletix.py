import logging
import sys
import os
from datetime import datetime
import pytz

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from providers.biletix import BiletixProvider
from services.sync_service import SyncService

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def test_sync_biletix():
    logging.info("Starting isolated Biletix sync test...")
    
    sync_service = SyncService()
    provider = BiletixProvider()
    
    run_start_time = datetime.now(pytz.UTC)
    
    try:
        events = provider.fetch_and_parse()
        logging.info(f"Fetched {len(events)} events from Biletix. Testing first 10.")
        
        for i, event in enumerate(events[:3]):
            print(f"!!! DOING SYNC FOR {event.title} - OCC COUNT: {len(event.occurrences)}", flush=True)
            stats = sync_service.sync_event(event)
            print(f"!!! SYNC RESULT FOR {event.title}: {stats}", flush=True)
            if stats["failed"] > 0:
                logging.error(f"  FAILED to sync event: {event.title}")
        
        logging.info("Biletix sync test finished. Check DB.")
        
    except Exception as e:
        logging.error(f"Biletix sync test failed: {e}")

if __name__ == "__main__":
    test_sync_biletix()

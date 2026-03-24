import logging
import sys
import os

# Add the project root to sys.path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from providers.biletix import BiletixProvider

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def test_biletix():
    provider = BiletixProvider()
    logging.info("Starting Biletix test run (Istanbul)...")
    
    events = provider.fetch_and_parse()
    
    logging.info(f"Test completed. Found {len(events)} events.")
    
    for i, event in enumerate(events[:5]): # Show first 5
        print(f"\n--- Event {i+1} ---")
        print(f"Title: {event.title}")
        print(f"Category: {event.type}")
        print(f"City: {event.city_name}")
        print(f"Image: {event.image_url}")
        print(f"Occurrences: {len(event.occurrences)}")
        
        for j, occ in enumerate(event.occurrences[:2]): # Show first 2 occurrences
            print(f"  Occurrence {j+1}: {occ.local_date} {occ.local_time} @ {occ.venue_name}")
            for source in occ.sources:
                print(f"    Source: {source.provider} | Status: {source.ticket_status}")
                print(f"    Price: {source.price.text} (Min: {source.price.min_value}, Max: {source.price.max_value})")
                print(f"    Link: {source.source_url}")

if __name__ == "__main__":
    test_biletix()

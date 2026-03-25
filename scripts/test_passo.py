"""
Isolated test for PassoProvider — Phase 4 Verification Script
Tests fetching and parsing of first few Passo events without database writes.
"""
import logging
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from providers.passo import PassoProvider

def test_passo():
    logging.info("!!! TEST STARTING NOW - PASSO !!!")
    provider = PassoProvider()
    
    events = provider.fetch_and_parse()
    
    logging.info(f"Total events parsed: {len(events)}")
    
    for i, ev in enumerate(events[:5]):
        print(f"\n--- Event {i+1} ---")
        print(f"  Title: {ev.title}")
        print(f"  Type: {ev.type}")
        print(f"  City: {ev.city_name}")
        print(f"  Image: {ev.image_url}")
        print(f"  Occurrences: {len(ev.occurrences)}")
        for occ in ev.occurrences[:3]:
            print(f"    Venue: {occ.venue_name}")
            print(f"    Date: {occ.local_date} {occ.local_time}")
            for src in occ.sources:
                print(f"    Source URL: {src.source_url}")
                print(f"    Price: {src.price.text if src.price else 'N/A'}")

if __name__ == "__main__":
    test_passo()

import logging
import sys
import os
from playwright.sync_api import sync_playwright

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from providers.passo import PassoProvider

def debug_parsing():
    provider = PassoProvider()
    print("Fetching raw items...")
    raw_items = provider._fetch_all_raw_events()
    print(f"Total raw items fetched: {len(raw_items)}")
    
    if raw_items:
        first_item = raw_items[0]
        print("\n--- All Keys in Item 0 ---")
        print(sorted(first_item.keys()))
        
        print("\n--- Example item (Full JSON) ---")
        import json
        print(json.dumps(first_item, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    debug_parsing()

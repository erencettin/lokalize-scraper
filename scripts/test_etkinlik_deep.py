import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

from providers.etkinlik_io import EtkinlikIoProvider

p = EtkinlikIoProvider()
events = p.fetch_and_parse()

with open("artifacts/test_runs/etkinlik_deep_result.txt", "w", encoding="utf-8") as f:
    f.write(f"Total events: {len(events)}\n\n")
    for i, e in enumerate(events, 1):
        occ = e.occurrences[0]
        src = occ.sources[0]
        f.write(f"{i}. {e.title} | {occ.venue_name} | {src.price.text} | {e.type} | {e.city_name} | {occ.start_at_utc}\n")

print(f"Done! Total: {len(events)} events. See artifacts/test_runs/etkinlik_deep_result.txt")

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from providers.mobilet import MobiletProvider

p = MobiletProvider()
events = p.fetch_and_parse()

with open("mobilet_deep_result.txt", "w", encoding="utf-8") as f:
    f.write(f"Total events: {len(events)}\n\n")
    for i, e in enumerate(events, 1):
        occ = e.occurrences[0]
        src = occ.sources[0]
        f.write(f"{i}. {e.title} | {occ.venue_name} | {src.price.text} | {e.type} | {occ.start_at_utc}\n")
    
print(f"Done! Total: {len(events)} events. See mobilet_deep_result.txt")

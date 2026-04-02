import sys
sys.path.insert(0, r"c:\Lokalize\LokalizeApp\temp_scraper_repo")
from utils.tribe_events_price_extractor import TribeEventsPriceExtractor
e = TribeEventsPriceExtractor()
r = e.extract_from_event({"cost": "200"})
print("strategy:", r.resolution.strategy)
print("source:", r.resolution.source)
print("confidence:", r.resolution.confidence)

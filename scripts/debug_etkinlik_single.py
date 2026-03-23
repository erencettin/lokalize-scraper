import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
from bs4 import BeautifulSoup
import logging
from providers.etkinlik_io import EtkinlikIoProvider

logging.basicConfig(level=logging.DEBUG)

# One of the URLs from the probe
test_url = "https://etkinlik.io/etkinlik/276690/tuzbiber-6li"
meta = {"title": "TuzBiber 6'lı", "category": "Stand-up", "city_name": "İstanbul"}

p = EtkinlikIoProvider()
p._setup_session()
print(f"DEBUGGING URL: {test_url}")

resp = p.session.get(test_url)
print(f"Status: {resp.status_code}")
soup = BeautifulSoup(resp.content, "html.parser")

# Test Date Parsing in isolation
print("\n--- Date Debug ---")
date_spans = soup.select('.etkinlik-detay-tarih span')
print(f"Found {len(date_spans)} spans in .etkinlik-detay-tarih")
for i, span in enumerate(date_spans):
    date_str = span.get_text(strip=True)
    print(f"  [{i}] Span text: '{date_str}'")
    from utils.date_parser import DateParser
    parsed = DateParser.parse_turkish_date(date_str)
    print(f"  [{i}] Parsed: {parsed}")

# Test Venue Parsing
print("\n--- Venue Debug ---")
venue_link = soup.select_one('a[href*="/mekan/"]')
if venue_link:
    print(f"Found venue: '{venue_link.text.strip()}'")
else:
    print("Venue NOT found with 'a[href*=\"/mekan/\"]'")

# Test Full Method
print("\n--- Full _scrape_detail_page Test ---")
event = p._scrape_detail_page(test_url, meta)
if event:
    print(f"SUCCESS: {event.title} at {event.occurrences[0].venue_name} on {event.occurrences[0].start_at_utc}")
else:
    print("FAILURE: _scrape_detail_page returned None")

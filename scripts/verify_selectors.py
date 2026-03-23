import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
from bs4 import BeautifulSoup

# The URL from the subagent's successful navigation
test_url = "https://etkinlik.io/etkinlik/276690/tuzbiber-6li"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

resp = requests.get(test_url, headers=headers)
print(f"Status: {resp.status_code}")
soup = BeautifulSoup(resp.content, "html.parser")

# 1. Date/Time Selectors from Subagent
print("\n--- Date/Time Selectors ---")
meta_spans = soup.select('.etkinlik-header .meta span')
print(f"Found {len(meta_spans)} spans in .etkinlik-header .meta")
for i, span in enumerate(meta_spans):
    print(f"  [{i}]: '{span.get_text(strip=True)}'")

# 2. Venue Selectors from Subagent
print("\n--- Venue Selectors ---")
venue_header = soup.select_one('.mekan-ozet .header')
if venue_header:
    print(f"Venue (mekan-ozet .header): '{venue_header.get_text(strip=True)}'")

venue_link = soup.select_one('a[href*="/mekan/"]')
if venue_link:
    print(f"Venue Link Found: '{venue_link.text.strip()}' -> {venue_link['href']}")

# 3. Image Selectors
print("\n--- Image Selectors ---")
img = soup.select_one('.etkinlik-detay-resim img')
if img:
    print(f"Image Source: '{img.get( 'src' ) or img.get( 'data-src' )}'")

# 4. Description
print("\n--- Description ---")
desc = soup.select_one('.etkinlik-detay-icerik')
if desc:
    print(f"Description Length: {len(desc.get_text())}")

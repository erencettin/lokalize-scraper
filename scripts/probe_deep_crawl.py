import requests
from bs4 import BeautifulSoup
import json

# Check Mobilet Discover API
headers = {"User-Agent": "Mozilla/5.0"}
print("\n--- Mobilet ---")
try:
    res = requests.get("https://mobilet.com/tr/", headers=headers, timeout=10)
    # See if there's a next page or search endpoint we can hit. Mobilet uses React, let's check for __NEXT_DATA__
    soup = BeautifulSoup(res.text, 'html.parser')
    next_data = soup.find('script', id="__NEXT_DATA__")
    if next_data:
        data = json.loads(next_data.string)
        print("Found __NEXT_DATA__. We could extract categories and fetch more.")
    else:
        print("No __NEXT_DATA__ found.")
except Exception as e:
    print("Mobilet check failed:", e)

# Check Etkinlik.io paginated 
print("\n--- Etkinlik.io ---")
try:
    res = requests.get("https://etkinlik.io/istanbul?page=1", headers=headers, timeout=10)
    soup = BeautifulSoup(res.text, 'html.parser')
    cards = soup.select(".event-card")
    print(f"Page 1 HTML has {len(cards)} event cards.")
    
    # Check pagination text
    pagination = soup.select(".pagination")
    if pagination:
         print(f"Pagination block found! Text: {pagination[0].text.strip()[:100]}...")
except Exception as e:
    print("Etkinlik.io check failed:", e)

# Check Kultur Istanbul Post Types
print("\n--- Kultur Istanbul ---")
try:
    res = requests.get("https://kultur.istanbul/wp-json/wp/v2/types", headers=headers, verify=False, timeout=10)
    types = res.json()
    print("Available Post Types:")
    for t in types:
        if 'event' in t or 'etkinlik' in t or 'sergi' in t:
            print(" -", t)
except Exception as e:
    print("Kultur check failed:", e)


import os
from dotenv import load_dotenv
import requests
import json

load_dotenv("c:/Lokalize/LokalizeApp/temp_scraper_repo/.env")
apikey = os.environ.get("TICKETMASTER_API_KEY")

url = "https://app.ticketmaster.com/discovery/v2/events.json"
params = {"apikey": apikey, "countryCode": "TR", "city": "Istanbul", "size": 10, "sort": "date,asc"}
res = requests.get(url, params=params).json()

events = res.get("_embedded", {}).get("events", [])
for ev in events:
    event_id = ev["id"]
    print(f"\nEvent: {ev['name']}")
    detail_url = f"https://app.ticketmaster.com/discovery/v2/events/{event_id}.json"
    detail_res = requests.get(detail_url, params={"apikey": apikey}).json()
    prices = detail_res.get("priceRanges")
    if prices:
        print(f"FOUND PRICES: {prices}")
    else:
        print("No priceRanges in detail API payload.")

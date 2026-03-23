import requests
import json

url = "https://kultur.istanbul/wp-json/wp/v2/event_listing"
headers = {"User-Agent": "Mozilla/5.0"}
res = requests.get(url, headers=headers)
print(f"Status event_listing: {res.status_code}")
if res.status_code == 200:
    print(len(res.json()), "events found")

url2 = "https://kultur.istanbul/wp-json/wp/v2/events"
res2 = requests.get(url2, headers=headers)
print(f"Status events: {res2.status_code}")

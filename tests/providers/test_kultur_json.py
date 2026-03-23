import requests
import json

url = "https://kultur.istanbul/wp-json/wp/v2/event_listing?per_page=1"
headers = {"User-Agent": "Mozilla/5.0"}
res = requests.get(url, headers=headers)
with open("kultur_api.json", "w", encoding="utf-8") as f:
    json.dump(res.json(), f, ensure_ascii=False, indent=2)

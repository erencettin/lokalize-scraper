import requests
import json

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Content-Type": "application/json",
    "Origin": "https://mobilet.com",
    "Referer": "https://mobilet.com/",
    "x-culture-code": "tr-TR",
    "x-saleschannel": "3",
    "x-channel-id": "1000",
    "x-member-channel-id": "11",
    "x-sub-channel-id": "1",
    "x-firm-id": "1",
})

# Warm up
session.get("https://mobilet.com/tr/", timeout=10)

payload = {
    "search": "",
    "eventTypeNames": [],
    "cityNames": [],
    "eventStartDateToTimestamp": None,
    "locationNames": [],
    "eventTagNames": [],
    "offset": 0,
    "limit": 20,
}

resp = session.post("https://api-v2.mobilet.com/event/searchEvent", json=payload, timeout=15)
print(f"Status: {resp.status_code}")
print(f"Content-Type: {resp.headers.get('content-type')}")

data = resp.json()
print(f"Response type: {type(data).__name__}")

if isinstance(data, dict):
    print(f"Top keys: {list(data.keys())}")
    for k, v in data.items():
        if isinstance(v, list):
            print(f"  {k}: list of {len(v)}")
            if len(v) > 0 and isinstance(v[0], dict):
                print(f"    First item keys: {list(v[0].keys())}")
                # Print first item
                sample = v[0]
                for sk, sv in sample.items():
                    print(f"      {sk}: {str(sv)[:120]}")
        elif isinstance(v, (int, float, str, bool)):
            print(f"  {k}: {v}")
        elif isinstance(v, dict):
            print(f"  {k}: dict with keys {list(v.keys())[:10]}")
elif isinstance(data, list):
    print(f"List of {len(data)} items")
    if len(data) > 0 and isinstance(data[0], dict):
        print(f"First item keys: {list(data[0].keys())}")

# Save raw
with open("mobilet_api_response.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print("\nSaved raw response to mobilet_api_response.json")

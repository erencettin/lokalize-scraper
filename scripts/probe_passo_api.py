"""
Passo API Discovery Phase 2 - Testing the discovered ticketingweb endpoint
"""
from curl_cffi import requests
import json
import os

os.makedirs("artifacts/probes", exist_ok=True)

BASE_URL = "https://ticketingweb.passo.com.tr/api/passoweb"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://www.passo.com.tr",
    "Referer": "https://www.passo.com.tr/",
}

def test_all_events(from_=0, size=5):
    print(f"\n=== Testing allevents (from={from_}, size={size}) ===")
    body = {"LanguageId": 118, "from": from_, "size": size}
    resp = requests.post(f"{BASE_URL}/allevents", headers=HEADERS, json=body, impersonate="chrome110", timeout=15)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"Keys: {list(data.keys())}")
        print(f"Total: {data.get('totalItemCount')}")
        with open("artifacts/probes/passo_allevents_sample.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Saved to passo_allevents_sample.json")
        # Print first item
        if data.get("valueList"):
            print(f"First item keys: {list(data['valueList'][0].keys())}")
            print(f"First item: {json.dumps(data['valueList'][0], ensure_ascii=False, indent=2)}")
    return resp.status_code

def test_all_events_istanbul():
    """Try filtering by city/location"""
    print(f"\n=== Testing allevents with Istanbul filter ===")
    bodies_to_try = [
        {"LanguageId": 118, "from": 0, "size": 5, "CityId": 1},  # Istanbul usually city 1 in Turkish systems
        {"LanguageId": 118, "from": 0, "size": 5, "cityId": 1},
        {"LanguageId": 118, "from": 0, "size": 5, "city": "istanbul"},
        {"LanguageId": 118, "from": 0, "size": 5, "VenueId": None},
    ]
    for body in bodies_to_try:
        resp = requests.post(f"{BASE_URL}/allevents", headers=HEADERS, json=body, impersonate="chrome110", timeout=15)
        print(f"  Body: {body} → Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  Total: {data.get('totalItemCount')}")
            print(f"  Sample venue: {data.get('valueList', [{}])[0].get('venueName', 'N/A')}")

def test_event_detail(event_id=1228613):
    """Test getting event detail"""
    print(f"\n=== Testing event detail for id={event_id} ===")
    # Try different patterns
    endpoints = [
        f"{BASE_URL}/geteventdetail/{event_id}",
        f"{BASE_URL}/getevent/{event_id}",
        f"{BASE_URL}/geteventdetail",
    ]
    bodies = [
        None,
        None,
        {"LanguageId": 118, "eventId": event_id},
    ]
    for ep, body in zip(endpoints, bodies):
        try:
            if body:
                resp = requests.post(ep, headers=HEADERS, json=body, impersonate="chrome110", timeout=10)
            else:
                resp = requests.get(ep, headers=HEADERS, impersonate="chrome110", timeout=10)
            print(f"  {ep}: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"  Keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
                with open(f"artifacts/probes/passo_event_{event_id}.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  {ep}: Error - {e}")

def test_settings():
    print(f"\n=== Testing getsettings ===")
    resp = requests.get(f"{BASE_URL}/getsettings", headers=HEADERS, impersonate="chrome110", timeout=10)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"Keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}")
        with open("artifacts/probes/passo_settings.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Saved to passo_settings.json")

if __name__ == "__main__":
    status = test_all_events()
    if status == 200:
        test_all_events_istanbul()
        # Use ID from first successful fetch
        test_event_detail()
    test_settings()

"""Quick test - can we call Passo API directly with requests (no CF on API subdomain)?"""
import requests
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://www.passo.com.tr",
    "Referer": "https://www.passo.com.tr/",
}

resp = requests.post(
    "https://ticketingweb.passo.com.tr/api/passoweb/allevents",
    headers=HEADERS,
    json={"LanguageId": 118, "from": 0, "size": 3},
    timeout=15
)

print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"Total events: {data.get('totalItemCount')}")
    print(f"Keys: {list(data.keys())}")
    if data.get("valueList"):
        print(f"First event keys: {list(data['valueList'][0].keys())}")
        print(json.dumps(data["valueList"][0], ensure_ascii=False, indent=2))
    with open("artifacts/probes/passo_allevents_direct.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Saved to passo_allevents_direct.json!")
else:
    print(f"Response: {resp.text[:300]}")

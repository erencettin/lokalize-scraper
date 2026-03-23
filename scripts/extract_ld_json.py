from bs4 import BeautifulSoup
import json

with open('artifacts/probes/etkinlik_raw.html', 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f, 'html.parser')

scripts = soup.find_all('script', type='application/ld+json')
print(f"Found {len(scripts)} LD+JSON scripts.")

for i, s in enumerate(scripts):
    try:
        data = json.loads(s.string)
        print(f"\n--- Script {i} TYPE: {data.get('@type')} ---")
        if data.get('@type') == 'Event':
            print(f"Name: {data.get('name')}")
            print(f"StartDate: {data.get('startDate')}")
            print(f"Location: {data.get('location', {}).get('name')}")
            print(f"Image: {data.get('image')}")
            print(f"Offers: {data.get('offers', {}).get('url')}")
        else:
            # Print keys if not Event
            print(f"Keys: {list(data.keys())}")
    except Exception as e:
        print(f"Error parsing script {i}: {e}")

import requests

url1 = "https://kultur.istanbul/wp-json/wp/v2/event_listing?per_page=50&page=1"
url2 = "https://kultur.istanbul/wp-json/wp/v2/event_listing?per_page=50&page=2"
headers = {"User-Agent": "Mozilla/5.0"}

print("Fetching page 1...")
r1 = requests.get(url1, headers=headers)
if r1.status_code == 200:
    print(f"Page 1: {len(r1.json())} events")
    print(f"Total Pages Header: {r1.headers.get('X-WP-TotalPages')}")
    print(f"Total Events Header: {r1.headers.get('X-WP-Total')}")
else:
    print("Page 1 Failed")

print("Fetching page 2...")
r2 = requests.get(url2, headers=headers)
if r2.status_code == 200:
    print(f"Page 2: {len(r2.json())} events")
else:
    print("Page 2 Failed")

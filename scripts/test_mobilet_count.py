import requests
import re
import time

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,*/*;q=0.8"
}

categories = ["muzik", "sahne", "spor", "festival-fuar", "aktivite", "gezi-tur"]
all_event_urls = set()

for slug in categories:
    page = 1
    while page <= 20:
        url = f"https://mobilet.com/tr/category/{slug}?page={page}"
        r = requests.get(url, headers=headers, timeout=15)
        links = set(re.findall(r'href="(/tr/event/[^"#?]+/?)"', r.text))
        if not links:
            break
        before = len(all_event_urls)
        all_event_urls.update(links)
        new = len(all_event_urls) - before
        print(f"{slug} page={page}: {len(links)} links, {new} new (total: {len(all_event_urls)})")
        if new == 0:
            break
        time.sleep(1)
        page += 1

print(f"\nTOTAL UNIQUE EVENT URLS: {len(all_event_urls)}")

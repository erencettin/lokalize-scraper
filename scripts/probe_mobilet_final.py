import requests
import json
from bs4 import BeautifulSoup
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

# Load buildId
with open("mobilet_next_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)
build_id = data.get("buildId", "")
print(f"buildId: {build_id}")

# Strategy 1: _next/data endpoint (Next.js SSR data)
print("\n=== Strategy 1: _next/data ===")
next_data_urls = [
    f"https://mobilet.com/_next/data/{build_id}/tr.json",
    f"https://mobilet.com/_next/data/{build_id}/tr/category/muzik.json",
    f"https://mobilet.com/_next/data/{build_id}/tr/category/sahne.json",
]
for url in next_data_urls:
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"  {url.split(build_id)[1]} -> {r.status_code} ({len(r.text)} bytes)")
        if r.status_code == 200:
            d = r.json()
            pp = d.get("pageProps", {})
            print(f"    pageProps keys: {list(pp.keys())[:10]}")
            ist = pp.get("initialState", {})
            if ist:
                api_q = ist.get("api", {}).get("queries", {})
                print(f"    api queries: {list(api_q.keys())[:5]}")
    except Exception as e:
        print(f"  Error: {e}")

# Strategy 2: HTML category pages with pagination 
print("\n=== Strategy 2: HTML Category Pages ===")
category_slugs = ["muzik", "sahne", "spor", "festival-fuar", "aktivite", "gezi-tur"]
for slug in category_slugs:
    url = f"https://mobilet.com/tr/category/{slug}/"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        # Count event links
        event_links = re.findall(r'href="(/tr/event/[^"#?]+/?)"', r.text)
        unique_links = list(set(event_links))
        print(f"  {slug}: {r.status_code}, {len(unique_links)} unique event links")
        
        # Check for "load more" or pagination
        load_more = soup.find(attrs={"data-testid": re.compile("load|more|next", re.I)})
        if load_more:
            print(f"    Load more button found: {load_more}")
    except Exception as e:
        print(f"  {slug}: Error {e}")

# Strategy 3: Check the sitemap
print("\n=== Strategy 3: Sitemap ===")
sitemap_urls = [
    "https://mobilet.com/sitemap.xml",
    "https://mobilet.com/sitemap-0.xml",
    "https://mobilet.com/sitemap_index.xml",
]
for url in sitemap_urls:
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"  {url.split('.com')[1]}: {r.status_code} ({len(r.text)} bytes)")
        if r.status_code == 200:
            event_urls = re.findall(r'<loc>(https://mobilet\.com/tr/event/[^<]+)</loc>', r.text)
            print(f"    Event URLs found: {len(event_urls)}")
            if event_urls:
                print(f"    Sample: {event_urls[0]}")
    except Exception as e:
        print(f"  Error: {e}")

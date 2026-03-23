import requests
from bs4 import BeautifulSoup
import json
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
}

# Step 1: Get the homepage and extract __NEXT_DATA__
print("=== Step 1: Fetching homepage __NEXT_DATA__ ===")
res = requests.get("https://mobilet.com/tr/", headers=headers, timeout=15)
soup = BeautifulSoup(res.text, 'html.parser')
next_data_tag = soup.find('script', id="__NEXT_DATA__")

if next_data_tag:
    data = json.loads(next_data_tag.string)
    # Save full JSON for analysis
    with open("mobilet_next_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved __NEXT_DATA__ ({len(next_data_tag.string)} bytes)")
    
    # Print the top-level keys
    print(f"Top keys: {list(data.keys())}")
    if "props" in data:
        page_props = data.get("props", {}).get("pageProps", {})
        print(f"pageProps keys: {list(page_props.keys())}")
        
        # Check for categories or sections
        for k, v in page_props.items():
            if isinstance(v, list):
                print(f"  {k}: list of {len(v)} items")
                if len(v) > 0 and isinstance(v[0], dict):
                    print(f"    First item keys: {list(v[0].keys())}")
                    if "name" in v[0]:
                        print(f"    Names: {[x.get('name') for x in v[:10]]}")
                    if "slug" in v[0]:
                        print(f"    Slugs: {[x.get('slug') for x in v[:10]]}")
            elif isinstance(v, dict):
                print(f"  {k}: dict with keys {list(v.keys())[:10]}")
else:
    print("No __NEXT_DATA__ found!")

# Step 2: Check category pages
print("\n=== Step 2: Checking category pages ===")
category_urls = [
    "https://mobilet.com/tr/category/muzik/",
    "https://mobilet.com/tr/category/sahne/",
    "https://mobilet.com/tr/category/spor/",
]
for cat_url in category_urls:
    try:
        r = requests.get(cat_url, headers=headers, timeout=15)
        s = BeautifulSoup(r.text, 'html.parser')
        nd = s.find('script', id="__NEXT_DATA__")
        if nd:
            cd = json.loads(nd.string)
            pp = cd.get("props", {}).get("pageProps", {})
            print(f"\n{cat_url}")
            print(f"  pageProps keys: {list(pp.keys())}")
            for k, v in pp.items():
                if isinstance(v, list):
                    print(f"    {k}: {len(v)} items")
                elif isinstance(v, dict) and "items" in v:
                    print(f"    {k}: dict with {len(v.get('items', []))} items, total={v.get('totalCount', '?')}")
                elif isinstance(v, dict):
                    print(f"    {k}: dict with keys {list(v.keys())[:8]}")
    except Exception as e:
        print(f"  Failed: {e}")

# Step 3: Check if there's an API endpoint pattern
print("\n=== Step 3: Testing potential API patterns ===")
api_patterns = [
    "https://mobilet.com/api/events?page=1&size=50",
    "https://mobilet.com/api/v1/events?page=1&size=50",
    "https://mobilet.com/tr/api/events?page=1",
    "https://mobilet.com/_next/data/",
]
for api in api_patterns:
    try:
        r = requests.get(api, headers=headers, timeout=10)
        print(f"  {api} -> {r.status_code} ({len(r.text)} bytes)")
    except Exception as e:
        print(f"  {api} -> Error: {e}")

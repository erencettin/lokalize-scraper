import requests
import json
from bs4 import BeautifulSoup
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,*/*;q=0.8"
}

with open("mobilet_next_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)
build_id = data.get("buildId", "")

results = []

# Strategy 1: _next/data
results.append("STRATEGY_1_NEXT_DATA")
for path in ["/tr.json", "/tr/category/muzik.json"]:
    url = f"https://mobilet.com/_next/data/{build_id}{path}"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        results.append(f"  {path} status={r.status_code} size={len(r.text)}")
    except Exception as e:
        results.append(f"  {path} error={e}")

# Strategy 2: HTML category pages - count event links
results.append("STRATEGY_2_CATEGORIES")
for slug in ["muzik", "sahne", "spor", "festival-fuar", "aktivite", "gezi-tur"]:
    url = f"https://mobilet.com/tr/category/{slug}/"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        event_links = list(set(re.findall(r'href="(/tr/event/[^"#?]+/?)"', r.text)))
        results.append(f"  {slug}: status={r.status_code} events={len(event_links)}")
    except Exception as e:
        results.append(f"  {slug}: error={e}")

# Strategy 3: Sitemap 
results.append("STRATEGY_3_SITEMAP")
for path in ["/sitemap.xml", "/sitemap-0.xml"]:
    url = f"https://mobilet.com{path}"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        event_urls = re.findall(r'<loc>(https://mobilet\.com/tr/event/[^<]+)</loc>', r.text)
        all_urls = re.findall(r'<loc>([^<]+)</loc>', r.text)
        results.append(f"  {path}: status={r.status_code} total_urls={len(all_urls)} event_urls={len(event_urls)}")
        if event_urls:
            results.append(f"    sample: {event_urls[0]}")
    except Exception as e:
        results.append(f"  {path}: error={e}")

with open("probe_clean.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(results))
print("Done - wrote probe_clean.txt")

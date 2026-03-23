"""Probe etkinlik.io RSS + count to file."""
import requests
from bs4 import BeautifulSoup
import time

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
base_url = "https://etkinlik.io/rss/sorgu"
results = []
all_urls = set()

# Base
r = requests.get(base_url, headers=headers, timeout=15)
soup = BeautifulSoup(r.content, 'xml')
items = soup.find_all('item')
for item in items:
    link = item.find('link')
    if link:
        all_urls.add(link.text.strip())
results.append(f"Base: {len(items)} items, total={len(all_urls)}")

# By city
cities = {"Istanbul": 40, "Ankara": 6, "Izmir": 41, "Antalya": 7, "Bursa": 16, "Eskisehir": 26}
for name, cid in cities.items():
    r = requests.get(f"{base_url}?sehirIds={cid}", headers=headers, timeout=15)
    soup = BeautifulSoup(r.content, 'xml')
    items = soup.find_all('item')
    for item in items:
        link = item.find('link')
        if link:
            all_urls.add(link.text.strip())
    results.append(f"City {name} (id={cid}): {len(items)} items, total={len(all_urls)}")
    time.sleep(0.5)

# By type  
types = {"Atolye": 1, "Cevrimici": 2, "Cocuk": 3, "Konser": 4, "Sahne": 5, "Sinema": 6, 
         "Spor": 7, "Sergi": 8, "Festival": 9, "Soylesi": 10, "Gezi": 11, "Yemek": 12}
for name, tid in types.items():
    r = requests.get(f"{base_url}?turIds={tid}", headers=headers, timeout=15)
    soup = BeautifulSoup(r.content, 'xml')
    items = soup.find_all('item')
    for item in items:
        link = item.find('link')
        if link:
            all_urls.add(link.text.strip())
    results.append(f"Type {name} (id={tid}): {len(items)} items, total={len(all_urls)}")
    time.sleep(0.5)

# City+Type combos for Istanbul
for tname, tid in types.items():
    r = requests.get(f"{base_url}?sehirIds=40&turIds={tid}", headers=headers, timeout=15)
    soup = BeautifulSoup(r.content, 'xml')
    items = soup.find_all('item')
    for item in items:
        link = item.find('link')
        if link:
            all_urls.add(link.text.strip())
    results.append(f"Istanbul+{tname}: {len(items)} items, total={len(all_urls)}")
    time.sleep(0.5)

# site-api/search 
for q in ["konser", "tiyatro", "festival", "stand-up", "sergi", "atölye", "spor"]:
    try:
        r = requests.get(f"https://etkinlik.io/site-api/search?query={q}", headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                res = data.get("result", data.get("results", []))
                if isinstance(res, list):
                    for item in res:
                        url = item.get("url") or item.get("link") or ""
                        if url:
                            all_urls.add(f"https://etkinlik.io{url}" if url.startswith("/") else url)
                    results.append(f"Search '{q}': {len(res)} results, total={len(all_urls)}")
                else:
                    results.append(f"Search '{q}': keys={list(data.keys())}")
            elif isinstance(data, list):
                results.append(f"Search '{q}': {len(data)} results")
        else:
            results.append(f"Search '{q}': HTTP {r.status_code}")
    except Exception as e:
        results.append(f"Search '{q}': error={e}")
    time.sleep(0.5)

results.append(f"\nTOTAL UNIQUE EVENT URLS: {len(all_urls)}")

with open("artifacts/probes/etkinlik_rss_probe.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(results))
print(f"Done - {len(all_urls)} unique URLs. See artifacts/probes/etkinlik_rss_probe.txt")

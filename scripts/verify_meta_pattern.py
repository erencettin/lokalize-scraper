import requests
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0'}
urls = [
    "https://etkinlik.io/etkinlik/276690/tuzbiber-6li",
    "https://etkinlik.io/etkinlik/256671/aynur-dogan-konseri-izmir", # Let me try the correct URL now
    "https://etkinlik.io/etkinlik/278546/melike-sahin-antalya-konseri"
]

for url in urls:
    print(f"\nURL: {url}")
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # 1. Start Time
        start_time = soup.find("meta", property="event:start_time")
        if not start_time:
            start_time = soup.find("meta", {"name": "event:start_time"})
        print(f"  Start Time: {start_time['content'] if start_time else 'NOT FOUND'}")
        
        # 2. Keywords (Venue)
        keywords = soup.find("meta", {"name": "keywords"})
        if keywords:
            kw_list = [k.strip() for k in keywords['content'].split(',')]
            venue = kw_list[-2] if len(kw_list) >= 2 else "NOT FOUND"
            print(f"  Venue: {venue}")
            print(f"  Full Keywords: {kw_list}")
        else:
            print("  Keywords: NOT FOUND")
            
        # 3. Image
        og_image = soup.find("meta", property="og:image")
        print(f"  Image: {og_image['content'] if og_image else 'NOT FOUND'}")
        
    except Exception as e:
        print(f"  Error: {e}")

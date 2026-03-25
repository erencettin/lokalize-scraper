import logging
import sys
import os
from playwright.sync_api import sync_playwright

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_browser_payload():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto("https://www.passo.com.tr/tr", wait_until="domcontentloaded")
        
        payload = {
            "CountRequired": True,
            "HastagId": None,
            "CityId": "101", # uppercase C, string
            "date": None,
            "VenueId": None,
            "LanguageId": 118,
            "from": 0,
            "size": 53
        }
        
        logging.info("Fetching with browser payload...")
        result = page.evaluate("""async ([payload]) => {
            const resp = await fetch('https://ticketingweb.passo.com.tr/api/passoweb/allevents', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
                body: JSON.stringify(payload)
            });
            return await resp.json();
        }""", [payload])
        
        items = result.get("valueList", [])
        date_available = [i for i in items if i.get("date") and not i["date"].startswith("0001")]
        
        type_counts = {}
        for i in items:
            etype = i.get("eventType")
            type_counts[etype] = type_counts.get(etype, 0) + 1
            
        print(f"Total items: {len(items)}")
        print(f"Items with dates: {len(date_available)}")
        print(f"EventType Counts: {type_counts}")
        
        if date_available:
            for d in date_available[:3]:
                print(f"  Event with date: {d['name']} ({d['date']}) Type: {d['eventType']}")
        
        browser.close()

if __name__ == "__main__":
    test_browser_payload()

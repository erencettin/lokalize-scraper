import logging
import sys
import os
from playwright.sync_api import sync_playwright

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def count_istanbul_total():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto("https://www.passo.com.tr/tr", wait_until="domcontentloaded")
        
        # Fetch with large size to see total Istanbul count
        payload = {
            "CountRequired": True,
            "CityId": "101",
            "LanguageId": 118,
            "from": 0,
            "size": 500 # Should be enough for Istanbul
        }
        
        logging.info("Fetching complete Istanbul listing...")
        result = page.evaluate("""async ([payload]) => {
            const resp = await fetch('https://ticketingweb.passo.com.tr/api/passoweb/allevents', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
                body: JSON.stringify(payload)
            });
            return await resp.json();
        }""", [payload])
        
        items = result.get("valueList", [])
        total_count = result.get("totalItemCount", 0)
        
        type_counts = {}
        date_available = 0
        for i in items:
            etype = i.get("eventType")
            type_counts[etype] = type_counts.get(etype, 0) + 1
            raw_date = i.get("date") or i.get("startDate")
            if raw_date and not raw_date.startswith("0001"):
                 date_available += 1
        
        print(f"Total Istanbul Items (API): {total_count}")
        print(f"Items fetched in this run: {len(items)}")
        print(f"EventType 0 (Performances): {type_counts.get(0, 0)}")
        print(f"EventType 2 (Groups/Tournaments): {type_counts.get(2, 0)}")
        print(f"Items with valid/parsed dates: {date_available}")
        
        browser.close()

if __name__ == "__main__":
    count_istanbul_total()

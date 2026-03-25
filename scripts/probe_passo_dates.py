import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
import time
import logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def dump_more_events():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto("https://www.passo.com.tr/tr", wait_until="domcontentloaded")
        
        logging.info("Fetching 100 events for Istanbul (locationId=101)...")
        result = page.evaluate("""
            async () => {
                const resp = await fetch('https://ticketingweb.passo.com.tr/api/passoweb/allevents', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
                    body: JSON.stringify({"LanguageId": 118, "from": 0, "size": 100, "locationId": 101})
                });
                return await resp.json();
            }
        """)
        
        items = result.get("valueList", [])
        events_with_dates = [i for i in items if i.get("date") and not i["date"].startswith("0001")]
        
        logging.info(f"Total items fetched: {len(items)}")
        logging.info(f"Items with dates: {len(events_with_dates)}")
        
        if events_with_dates:
            logging.info(f"Sample date: {events_with_dates[0]['date']}")
            with open("artifacts/probes/passo_events_with_dates.json", "w", encoding="utf-8") as f:
                json.dump(events_with_dates, f, ensure_ascii=False, indent=2)
        else:
            logging.info("NO events found with dates in the first 100 items.")
            # Save first 10 items anyway for inspection
            with open("artifacts/probes/passo_events_first10.json", "w", encoding="utf-8") as f:
                json.dump(items[:10], f, ensure_ascii=False, indent=2)

        browser.close()

if __name__ == "__main__":
    dump_more_events()

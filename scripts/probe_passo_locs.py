import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import json
import time
import logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_locations():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = context.new_page()
        page.goto("https://www.passo.com.tr/tr", wait_until="domcontentloaded")
        
        logging.info("Fetching locations...")
        result = page.evaluate("""
            async () => {
                const resp = await fetch('https://ticketingweb.passo.com.tr/api/passoweb/getalleventlocation', {
                    method: 'GET',
                    headers: {'Accept': 'application/json'}
                });
                return await resp.json();
            }
        """)
        
        items = result.get("valueList", [])
        for item in items:
            if 'İstanbul' in item.get('locationName', ''):
                print(f"ISTANBUL LOCATION: {item}")
        
        with open("artifacts/probes/passo_locations_full.json", "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

        browser.close()

if __name__ == "__main__":
    get_locations()

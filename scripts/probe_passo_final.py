import json
import time
import logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def test_logic():
    API_BASE = "https://ticketingweb.passo.com.tr/api/passoweb"
    LANGUAGE_ID = 118
    PAGE_SIZE = 100
    CITY_ID_ISTANBUL = "101"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        logging.info("Going to homepage...")
        page.goto("https://www.passo.com.tr/tr", wait_until="domcontentloaded")
        time.sleep(2)
        
        payload = {
            "LanguageId": LANGUAGE_ID,
            "from": 0,
            "size": PAGE_SIZE,
            "locationId": 101 # lowercase, int
        }
        
        logging.info(f"Fetching with payload: {payload}")
        result = page.evaluate("""async ([url, payload]) => {
            const resp = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                body: JSON.stringify(payload)
            });
            return await resp.json();
        }""", [f"{API_BASE}/allevents", payload])
        
        logging.info(f"Result sample: {str(result)[:500]}")
        items = result.get("valueList", [])
        print(f"Items found: {len(items)}")
        
        browser.close()

if __name__ == "__main__":
    test_logic()

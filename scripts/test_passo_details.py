import logging
import sys
import os
from playwright.sync_api import sync_playwright

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_details():
    EVENT_ID = 52187019 # From listing
    SEO_SLUG = "max-korzh-ataturk-olimpiyat-stadi-konser-bileti"
    LANG_ID = 118
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto("https://www.passo.com.tr/tr", wait_until="domcontentloaded")
        
        detail_url = f"https://ticketingweb.passo.com.tr/api/passoweb/geteventdetails/{SEO_SLUG}/{EVENT_ID}/{LANG_ID}"
        logging.info(f"Fetching details from: {detail_url}")
        
        result = page.evaluate("""async ([url]) => {
            const resp = await fetch(url);
            return await resp.json();
        }""", [detail_url])
        
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False))
        browser.close()

if __name__ == "__main__":
    test_details()

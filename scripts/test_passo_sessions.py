import logging
import sys
import os
from playwright.sync_api import sync_playwright

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_sessions():
    EVENT_ID = 52187019 # Max Korzh
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto("https://www.passo.com.tr/tr", wait_until="domcontentloaded")
        
        logging.info(f"Fetching sessions for event {EVENT_ID}...")
        result = page.evaluate("""async ([id]) => {
            const resp = await fetch('https://ticketingweb.passo.com.tr/api/passoweb/getsessions', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
                body: JSON.stringify({"LanguageId": 118, "id": id})
            });
            return await resp.json();
        }""", [EVENT_ID])
        
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False))
        browser.close()

if __name__ == "__main__":
    test_sessions()

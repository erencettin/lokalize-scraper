"""
Probe Passo event detail endpoint to discover date and session fields.
Uses Playwright's page.evaluate() approach.
"""
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
import time
import logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

API_BASE = "https://ticketingweb.passo.com.tr/api/passoweb"
LANGUAGE_ID = 118

def probe():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Prime session
        page.goto("https://www.passo.com.tr/tr", wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)

        # 1. Get first few events from allevents
        logging.info("Fetching first 3 events from allevents...")
        result = page.evaluate("""
            async () => {
                const resp = await fetch('https://ticketingweb.passo.com.tr/api/passoweb/allevents', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
                    body: JSON.stringify({"LanguageId": 118, "from": 0, "size": 3})
                });
                return await resp.json();
            }
        """)
        
        items = result.get("valueList", [])
        logging.info(f"Got {len(items)} events")
        
        # Save full first item to see all fields
        if items:
            with open("artifacts/probes/passo_first_item_all_keys.json", "w", encoding="utf-8") as f:
                json.dump(items[0], f, ensure_ascii=False, indent=2)
            print(f"\nFirst item ALL keys: {list(items[0].keys())}")
            print(f"First item: {json.dumps(items[0], ensure_ascii=False, indent=2)[:1000]}")
        
        # 2. Try to get event detail for first item
        if items:
            event_id = items[0]["id"]
            seo_url = items[0].get("seoUrl", "")
            logging.info(f"Probing detail for event {event_id} ({seo_url})...")
            
            # Try various detail endpoint patterns
            endpoints = [
                ("GET", f"https://ticketingweb.passo.com.tr/api/passoweb/geteventdetail/{event_id}"),
                ("POST", f"https://ticketingweb.passo.com.tr/api/passoweb/geteventdetail", {"LanguageId": LANGUAGE_ID, "eventId": event_id}),
                ("GET", f"https://ticketingweb.passo.com.tr/api/passoweb/geteventbyseourl/{seo_url}/tr"),
                ("POST", f"https://ticketingweb.passo.com.tr/api/passoweb/geteventbyseourl", {"SeoUrl": seo_url, "LanguageId": LANGUAGE_ID}),
            ]
            
            for method, url, *body_args in endpoints:
                body = body_args[0] if body_args else None
                js_code = f"""
                    (async () => {{
                        try {{
                            const opts = {{
                                method: '{method}',
                                headers: {{'Content-Type': 'application/json', 'Accept': 'application/json'}},
                                {f"body: JSON.stringify({json.dumps(body)})" if body else ""}
                            }};
                            const resp = await fetch('{url}', opts);
                            if (!resp.ok) return {{status: resp.status, data: null}};
                            const data = await resp.json();
                            return {{status: resp.status, data: data}};
                        }} catch (e) {{
                            return {{status: 0, error: e.toString()}};
                        }}
                    }})()
                """
                r = page.evaluate(js_code)
                print(f"\n{method} {url}: Status={r.get('status')}")
                if r.get("data"):
                    data = r["data"]
                    data_keys = list(data.keys()) if isinstance(data, dict) else type(data).__name__
                    print(f"  Keys: {data_keys}")
                    print(f"  Snippet: {str(data)[:300]}")
                    with open(f"artifacts/probes/passo_detail_{event_id}_{method}.json", "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                elif r.get("error"):
                    print(f"  Error: {r['error']}")
            
            # Also try sessions endpoint
            sessions_js = f"""
                (async () => {{
                    try {{
                        const resp = await fetch('https://ticketingweb.passo.com.tr/api/passoweb/getsessions', {{
                            method: 'POST',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify({{"LanguageId": 118, "EventId": {event_id}}})
                        }});
                        if (!resp.ok) return {{status: resp.status, data: null}};
                        return {{status: resp.status, data: await resp.json()}};
                    }} catch (e) {{
                        return {{status: 0, error: e.toString()}};
                    }}
                }})()
            """
            r = page.evaluate(sessions_js)
            print(f"\nPOST getsessions for {event_id}: Status={r.get('status')}")
            if r.get("data"):
                print(f"  Data keys: {list(r['data'].keys()) if isinstance(r['data'], dict) else 'list'}")
                print(f"  Data snippet: {str(r['data'])[:500]}")
                with open(f"artifacts/probes/passo_sessions_{event_id}.json", "w", encoding="utf-8") as f:
                    json.dump(r["data"], f, ensure_ascii=False, indent=2)
        
        browser.close()

if __name__ == "__main__":
    probe()

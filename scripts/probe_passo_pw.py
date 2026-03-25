from playwright.sync_api import sync_playwright
import json
import time
import os

os.makedirs("artifacts/probes", exist_ok=True)

discovered_requests = []
discovered_responses = []

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = context.new_page()

    def handle_request(request):
        url = request.url
        if "passo" in url or "ticketing" in url:
            discovered_requests.append(f"{request.method} {url}")

    def handle_response(response):
        url = response.url
        if (("passo" in url or "ticketing" in url) and response.status == 200
            and "application/json" in (response.headers.get("content-type") or "")):
            try:
                data = response.json()
                entry = {
                    "url": url,
                    "keys": list(data.keys()) if isinstance(data, dict) else type(data).__name__,
                    "snippet": str(data)[:500]
                }
                discovered_responses.append(entry)
            except:
                pass

    page.on("request", handle_request)
    page.on("response", handle_response)

    print("--- Navigating to homepage ---")
    page.goto("https://www.passo.com.tr/tr", wait_until="networkidle", timeout=30000)
    time.sleep(2)
    
    print("--- Navigating to events list ---")
    try:
        page.goto("https://www.passo.com.tr/tr/etkinlikler", wait_until="networkidle", timeout=30000)
        time.sleep(3)
    except:
        print("Events page timed out or failed")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)

# Write clean output
with open("artifacts/probes/passo_discovered_requests.txt", "w", encoding="utf-8") as f:
    f.write("=== DISCOVERED API REQUESTS ===\n")
    seen = set()
    for r in discovered_requests:
        if r not in seen:
            f.write(r + "\n")
            seen.add(r)

with open("artifacts/probes/passo_discovered_responses.json", "w", encoding="utf-8") as f:
    json.dump(discovered_responses, f, ensure_ascii=False, indent=2)

print(f"Found {len(discovered_requests)} requests and {len(discovered_responses)} JSON responses")
print("Results saved to artifacts/probes/")

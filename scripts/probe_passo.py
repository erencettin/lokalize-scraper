from curl_cffi import requests
import json
import re
import sys
import os
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def probe_passo():
    url = "https://www.passo.com.tr/tr"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    endpoints_to_test = [
        "https://api.passo.com.tr/api/Search/GetCategories",
        "https://api.passo.com.tr/api/Event/GetEvents",
        "https://www.passo.com.tr/tr" # Main HTML to see if impersonation works
    ]
    
    for ep in endpoints_to_test:
        logging.info(f"Probing {ep} with curl_cffi ...")
        try:
            resp = requests.get(ep, headers=headers, impersonate="chrome110", timeout=15)
            logging.info(f" - Status: {resp.status_code}")
            if resp.status_code == 200:
                logging.info(f" - Content length: {len(resp.content)}")
                try:
                    data = resp.json()
                    logging.info(f" - JSON format success! keys: {list(data.keys())[:10]}")
                    with open(f"artifacts/probes/passo_api_{ep.split('/')[-1] if '/' in ep else 'root'}.json", "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                except:
                    logging.info(" - Not JSON. Saving raw HTML.")
                    with open(f"artifacts/probes/passo_raw_{ep.split('/')[-1] if '/' in ep else 'root'}.html", "w", encoding="utf-8") as f:
                        f.write(resp.text)
        except Exception as e:
            logging.error(f" - Failed: {e}")

if __name__ == "__main__":
    probe_passo()

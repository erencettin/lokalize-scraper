import requests
import json
from datetime import datetime
import pytz

def check_solr():
    url = "https://www.biletix.com/solr/tr/select"
    now_str = datetime.now(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "start": 0,
        "rows": 10,
        "fq": 'region:"ISTANBUL"',
        "q": "*:*",
        "wt": "json",
        "sort": "score desc,start asc"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    res = requests.get(url, params=params, headers=headers)
    print(f"Solr Status: {res.status_code}")
    if res.status_code != 200:
        print(f"Error Body: {res.text[:500]}")
    data = res.json()
    print(f"Top-level keys: {list(data.keys())}")
    resp_val = data.get("response")
    print(f"Response value type: {type(resp_val)}")
    if isinstance(resp_val, str):
        print(f"Response string preview: {resp_val[:200]}")
    
    docs = []
    if isinstance(resp_val, dict):
        docs = resp_val.get("docs", [])
    print(f"Found {len(docs)} docs in Solr")
    for doc in docs:
        if isinstance(doc, dict):
            print(f"Full Doc: {json.dumps(doc, indent=2)}")
        else:
            print(f"  - Unexpected doc type: {type(doc)}: {str(doc)[:100]}")

if __name__ == "__main__":
    check_solr()

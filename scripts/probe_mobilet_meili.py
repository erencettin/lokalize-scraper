import json
import requests

with open("mobilet_next_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

state = data["props"]["pageProps"]["initialState"]
api = state.get("api", {})
rc = data.get("runtimeConfig", {})

# Print raw event types
et_q = api["queries"].get("getEventTypes(undefined)", {})
print("=== Event Types Raw ===")
print(json.dumps(et_q.get("data"), ensure_ascii=False)[:600])

# Print homepage data structure
hp_q = api["queries"].get("getHomePage(undefined)", {})
hp = hp_q.get("data", {}).get("homepage", {})
print(f"\n=== Homepage keys: {list(hp.keys())} ===")
for k, v in hp.items():
    if isinstance(v, list):
        print(f"\n--- {k}: {len(v)} items ---")
        if len(v) > 0:
            item = v[0]
            if isinstance(item, dict):
                for ik, iv in item.items():
                    print(f"  {ik}: {str(iv)[:120]}")
            else:
                print(f"  value: {str(item)[:200]}")

# Test MeiliSearch
print("\n\n=== MeiliSearch Test ===")
meili_url = rc.get("NEXT_PUBLIC_MEILI_SEARCH_URL", "")
meili_key = rc.get("NEXT_PUBLIC_MEILI_SEARCH_KEY", "")
meili_index = rc.get("NEXT_PUBLIC_MEILI_INDEX", "")
print(f"URL={meili_url}  Key={meili_key[:30] if meili_key else 'N/A'}  Index={meili_index}")

if meili_url and meili_key and meili_index:
    search_url = f"{meili_url}indexes/{meili_index}/search"
    headers = {
        "Authorization": f"Bearer {meili_key}",
        "Content-Type": "application/json"
    }
    payload = {"q": "", "limit": 5, "offset": 0}
    try:
        r = requests.post(search_url, json=payload, headers=headers, timeout=10)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            result = r.json()
            print(f"totalHits: {result.get('estimatedTotalHits', result.get('totalHits', '?'))}")
            print(f"hits: {len(result.get('hits', []))}")
            if result.get("hits"):
                hit = result["hits"][0]
                print(f"First hit keys: {list(hit.keys())}")
                for k, v in hit.items():
                    print(f"  {k}: {str(v)[:120]}")
        else:
            print(f"Response: {r.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")

# Test CMS GraphQL
print("\n\n=== CMS GraphQL Test ===")
gql_url = rc.get("NEXT_PUBLIC_GRAPHQL_URL", "")
if gql_url:
    # Try a simple events query
    query = '{ events(pagination: {limit: 2}) { data { id attributes { title slug startDate endDate } } meta { pagination { total pageCount } } } }'
    try:
        r = requests.post(gql_url, json={"query": query}, headers={"Content-Type": "application/json"}, timeout=10)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text[:800]}")
    except Exception as e:
        print(f"Error: {e}")

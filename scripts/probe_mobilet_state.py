import json

with open("mobilet_next_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Explore initialState
state = data["props"]["pageProps"]["initialState"]

# Look at API slice
api = state.get("api", {})
hasura = state.get("hasuraApi", {})

print("=== api keys ===")
print(list(api.keys())[:20])

print("\n=== hasuraApi keys ===")
print(list(hasura.keys())[:20])

# Check if queries contain event data
if "queries" in api:
    print(f"\napi queries: {len(api['queries'])} entries")
    for key in list(api["queries"].keys())[:5]:
        q = api["queries"][key]
        print(f"  Key: {key[:120]}")
        if isinstance(q, dict) and "data" in q:
            d = q["data"]
            if isinstance(d, list):
                print(f"    -> list of {len(d)} items")
                if len(d) > 0 and isinstance(d[0], dict):
                    print(f"    -> first item keys: {list(d[0].keys())[:15]}")
            elif isinstance(d, dict):
                print(f"    -> dict keys: {list(d.keys())[:10]}")

if "queries" in hasura:
    print(f"\nhasuraApi queries: {len(hasura['queries'])} entries")
    for key in list(hasura["queries"].keys())[:10]:
        q = hasura["queries"][key]
        print(f"  Key: {key[:150]}")
        if isinstance(q, dict) and "data" in q:
            d = q["data"]
            if isinstance(d, list):
                print(f"    -> list of {len(d)} items")
            elif isinstance(d, dict):
                for k2, v2 in d.items():
                    if isinstance(v2, list):
                        print(f"    -> {k2}: list of {len(v2)} items")
                        if len(v2) > 0 and isinstance(v2[0], dict):
                            print(f"       first item keys: {list(v2[0].keys())[:15]}")
                            # Print one sample
                            sample = {k: str(v)[:80] for k, v in v2[0].items()}
                            print(f"       sample: {json.dumps(sample, ensure_ascii=False)[:300]}")
                    else:
                        print(f"    -> {k2}: {type(v2).__name__}")

# Also check buildId for _next/data pattern
print(f"\nbuildId: {data.get('buildId', 'N/A')}")

# Check runtimeConfig
rc = data.get("runtimeConfig", {})
print(f"\nruntimeConfig keys: {list(rc.keys())}")
for k, v in rc.items():
    if isinstance(v, str) and ("api" in k.lower() or "url" in k.lower() or "graph" in k.lower() or "hasura" in k.lower()):
        print(f"  {k}: {v}")

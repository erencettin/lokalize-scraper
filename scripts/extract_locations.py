import json
with open('artifacts/probes/passo_discovered_responses.json', encoding='utf-8') as f:
    data = json.load(f)

for d in data:
    if 'getalleventlocation' in d['url']:
        # The snippet only shows a part, let me find the full list in the JSON if possible
        # Actually the snippet in the json is just a string of the data anyway
        print(d['snippet'])

# I'll also try to fetch it directly via playwright to be 100% sure

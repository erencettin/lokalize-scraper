import json
import ast

with open('artifacts/probes/passo_discovered_responses.json', encoding='utf-8') as f:
    data = json.load(f)

for d in data:
    if 'getalleventlocation' in d['url']:
        try:
            # The snippet is a string representation of a Python dict/list
            locs = ast.literal_eval(d['snippet'])
            val_list = locs.get('valueList', [])
            for loc in val_list:
                if 'İstanbul' in loc.get('locationName', ''):
                    print(f"FOUND: {loc}")
        except Exception as e:
            print(f"Error parsing snippet: {e}")
            # Fallback: simple string search in snippet
            if 'İstanbul' in d['snippet']:
                import re
                match = re.search(r"{'locationId': (\d+), 'locationName': 'İstanbul'}", d['snippet'])
                if match:
                    print(f"REGEX FOUND: {match.group(1)}")

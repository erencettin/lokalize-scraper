import json
from collections import Counter

with open('artifacts/probes/passo_events_with_dates.json', encoding='utf-8') as f:
    data = json.load(f)

names = [d['name'] for d in data]
name_counts = Counter(names)
dups = {name: count for name, count in name_counts.items() if count > 1}

print(f"Total events in sample: {len(data)}")
print(f"Unique event names: {len(name_counts)}")
print(f"Events with multiple entries: {len(dups)}")

for name, count in list(dups.items())[:5]:
    dates = [d['date'] for d in data if d['name'] == name]
    print(f"\n{name} ({count} entries):")
    for d in dates:
        print(f"  - {d}")

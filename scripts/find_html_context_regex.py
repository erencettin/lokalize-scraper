with open('artifacts/probes/etkinlik_raw.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re

# Find venue container
venue_match = re.search(r'[^>]*JJ Pub Kanyon[^<]*', text)
if venue_match:
    start = max(0, venue_match.start() - 100)
    end = min(len(text), venue_match.end() + 100)
    print("--- VENUE CONTEXT ---")
    print(text[start:end])

# Find date container
date_match = re.search(r'[^>]*23 Mart[^<]*', text)
if date_match:
    start = max(0, date_match.start() - 100)
    end = min(len(text), date_match.end() + 100)
    print("\n--- DATE CONTEXT ---")
    print(text[start:end])
